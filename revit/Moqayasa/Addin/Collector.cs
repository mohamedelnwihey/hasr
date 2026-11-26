using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Architecture;
using Moqayasa.Core;

namespace Moqayasa;

/// <summary>Reads the open Revit model: every quantified architectural and structural category, rooms, and material areas.</summary>
sealed class Collector
{
    readonly Document _doc;
    public Collector(Document doc) { _doc = doc; }

    static readonly (BuiltInCategory Bic, string Key)[] Cats =
    {
        (BuiltInCategory.OST_Walls, "Walls"), (BuiltInCategory.OST_CurtainWallPanels, "CurtainWalls"),
        (BuiltInCategory.OST_Doors, "Doors"), (BuiltInCategory.OST_Windows, "Windows"),
        (BuiltInCategory.OST_Floors, "Floors"), (BuiltInCategory.OST_Ceilings, "Ceilings"), (BuiltInCategory.OST_Roofs, "Roofs"),
        (BuiltInCategory.OST_Stairs, "Stairs"), (BuiltInCategory.OST_Ramps, "Ramps"), (BuiltInCategory.OST_Railings, "Railings"),
        (BuiltInCategory.OST_Columns, "Columns"),
        (BuiltInCategory.OST_StructuralColumns, "StructuralColumns"), (BuiltInCategory.OST_StructuralFraming, "StructuralFraming"),
        (BuiltInCategory.OST_StructuralFoundation, "StructuralFoundation"), (BuiltInCategory.OST_Rebar, "Rebar"),
        (BuiltInCategory.OST_Furniture, "Furniture"), (BuiltInCategory.OST_Casework, "Casework"),
        (BuiltInCategory.OST_PlumbingFixtures, "PlumbingFixtures"), (BuiltInCategory.OST_LightingFixtures, "LightingFixtures"),
        (BuiltInCategory.OST_ElectricalFixtures, "ElectricalFixtures"), (BuiltInCategory.OST_GenericModel, "GenericModels"),
    };

    public List<ElementData> Elements { get; } = new();
    public List<MaterialArea> MaterialAreas { get; } = new();
    public List<RoomData> Rooms { get; } = new();
    public List<string> Warnings { get; } = new();

    public void Run()
    {
        foreach (var (bic, key) in Cats)
        {
            var col = new FilteredElementCollector(_doc).OfCategory(bic).WhereElementIsNotElementType();
            foreach (var e in col)
            {
                try { var d = Read(e, key); if (d != null) Elements.Add(d); }
                catch (Exception ex) { Warnings.Add($"{key} {Compat.IdText(e)}: {ex.Message}"); }
            }
        }
        CollectRooms();
    }

    string LevelOf(Element e)
    {
        var id = e.LevelId;
        if (id != null && id != ElementId.InvalidElementId && _doc.GetElement(id) is Level l) return l.Name;
        return "";
    }

    static double? P(Element e, BuiltInParameter bip)
    {
        var p = e.get_Parameter(bip);
        return p != null && p.HasValue && p.StorageType == StorageType.Double ? p.AsDouble() : (double?)null;
    }

    static double? TypeDim(Element type, params BuiltInParameter[] bips)
    {
        foreach (var b in bips) { var v = P(type, b); if (v is > 0) return v; }
        return null;
    }

    string MainMaterial(Element e)
    {
        try
        {
            var ids = e.GetMaterialIds(false);
            Material? best = null; double bestArea = -1;
            foreach (var id in ids)
            {
                var m = _doc.GetElement(id) as Material; if (m == null) continue;
                double a = e.GetMaterialArea(id, false); double v = e.GetMaterialVolume(id);
                double score = v > 0 ? v : a;
                if (score > bestArea) { bestArea = score; best = m; }
            }
            if (best != null) return best.Name;
        }
        catch { }
        var sm = e.get_Parameter(BuiltInParameter.STRUCTURAL_MATERIAL_PARAM);
        if (sm != null && sm.HasValue && _doc.GetElement(sm.AsElementId()) is Material mm) return mm.Name;
        return "";
    }

    ElementData? Read(Element e, string key)
    {
        var d = new ElementData { Id = Compat.IdText(e), Category = key, Level = LevelOf(e), Material = MainMaterial(e) };
        var type = _doc.GetElement(e.GetTypeId());
        d.TypeName = type != null ? $"{(type as ElementType)?.FamilyName}: {type.Name}".Trim(' ', ':') : e.Name;

        var area = P(e, BuiltInParameter.HOST_AREA_COMPUTED);
        var vol = P(e, BuiltInParameter.HOST_VOLUME_COMPUTED);
        var len = P(e, BuiltInParameter.CURVE_ELEM_LENGTH) ?? P(e, BuiltInParameter.INSTANCE_LENGTH_PARAM);
        if (area is > 0) d.Area = Compat.M2(area.Value);
        if (vol is > 0) d.Volume = Compat.M3(vol.Value);
        if (len is > 0) d.Length = Compat.M(len.Value);

        if (key == "Doors" || key == "Windows")
        {
            var w = (type != null ? TypeDim(type, BuiltInParameter.DOOR_WIDTH, BuiltInParameter.WINDOW_WIDTH, BuiltInParameter.FAMILY_WIDTH_PARAM) : null)
                    ?? TypeDim(e, BuiltInParameter.DOOR_WIDTH, BuiltInParameter.WINDOW_WIDTH, BuiltInParameter.FAMILY_WIDTH_PARAM);
            var h = (type != null ? TypeDim(type, BuiltInParameter.DOOR_HEIGHT, BuiltInParameter.WINDOW_HEIGHT, BuiltInParameter.FAMILY_HEIGHT_PARAM) : null)
                    ?? TypeDim(e, BuiltInParameter.DOOR_HEIGHT, BuiltInParameter.WINDOW_HEIGHT, BuiltInParameter.FAMILY_HEIGHT_PARAM);
            if (w != null) d.Width = Compat.M(w.Value);
            if (h != null) d.Height = Compat.M(h.Value);
        }

        if (key is "StructuralColumns" or "StructuralFraming" or "StructuralFoundation" or "Columns" or "Floors" or "Walls" && d.Volume is null)
        {
            var gv = SolidVolume(e); if (gv > 0) d.Volume = Compat.M3(gv);
        }

        if (key == "Rebar" && e is Autodesk.Revit.DB.Structure.Rebar rb)
        {
            try { d.Length = Compat.M(rb.TotalLength); } catch { }
            var rv = d.Volume ?? (SolidVolume(e) is double sv && sv > 0 ? Compat.M3(sv) : (double?)null);
            if (rv != null) d.WeightKg = rv.Value * 7850.0;     // steel density; weight is derived from the modelled bar volume
        }

        bool concrete = Policy.IsConcrete(d.Material);
        if (concrete && key is "StructuralColumns" or "StructuralFraming" or "StructuralFoundation" or "Columns")
        {
            var fw = FormworkArea(e, key); if (fw > 0) { d.FormworkArea = Compat.M2(fw); d.Note = "formwork from solid faces, unverified in Revit"; }
        }

        if (key is "Walls" or "Ceilings" or "Floors") CollectMaterialAreas(e, key, d.Level);
        return d;
    }

    void CollectMaterialAreas(Element e, string host, string level)
    {
        foreach (var painted in new[] { false, true })
        {
            ICollection<ElementId> ids;
            try { ids = e.GetMaterialIds(painted); } catch { continue; }
            foreach (var id in ids)
            {
                var m = _doc.GetElement(id) as Material; if (m == null) continue;
                double a; try { a = e.GetMaterialArea(id, painted); } catch { continue; }
                if (a <= 0) continue;
                MaterialAreas.Add(new MaterialArea { ElementId = Compat.IdText(e), HostCategory = host, Level = level, Material = m.Name, Painted = painted, Area = Compat.M2(a) });
            }
        }
    }

    static IEnumerable<Solid> Solids(Element e)
    {
        var opt = new Options { DetailLevel = ViewDetailLevel.Fine, ComputeReferences = false };
        var ge = e.get_Geometry(opt); if (ge == null) yield break;
        foreach (var s in Flatten(ge)) yield return s;
    }

    static IEnumerable<Solid> Flatten(GeometryElement ge)
    {
        foreach (var o in ge)
        {
            if (o is Solid s && s.Volume > 1e-9) yield return s;
            else if (o is GeometryInstance gi) foreach (var x in Flatten(gi.GetInstanceGeometry())) yield return x;
        }
    }

    static double SolidVolume(Element e) { double v = 0; foreach (var s in Solids(e)) v += s.Volume; return v; }

    static double FormworkArea(Element e, string key)
    {
        double a = 0;
        foreach (var s in Solids(e))
            foreach (Face f in s.Faces)
            {
                XYZ n;
                try { n = f.ComputeNormal(new UV(0.5, 0.5)); } catch { continue; }
                if (n.Z > 0.99) continue;                                            // top face is poured against air
                if (n.Z < -0.99 && key is "StructuralColumns" or "Columns" or "StructuralFoundation") continue; // column ends / footing base sit on other concrete or soil
                a += f.Area;
            }
        return a;
    }

    void CollectRooms()
    {
        var col = new FilteredElementCollector(_doc).OfCategory(BuiltInCategory.OST_Rooms).WhereElementIsNotElementType();
        foreach (var e in col)
        {
            if (e is not Room r || r.Area <= 1e-6) continue;       // unplaced / unenclosed rooms have no area
            var lvl = r.Level?.Name ?? "";
            Rooms.Add(new RoomData { Id = Compat.IdText(r), Name = r.Number ?? "", LongName = r.get_Parameter(BuiltInParameter.ROOM_NAME)?.AsString() ?? "", Level = lvl,
                Area = Compat.M2(r.Area), Perimeter = Compat.M(r.Perimeter), Height = Compat.M(r.UnboundedHeight) });
        }
    }
}
