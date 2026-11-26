"""Dump an IFC file to the JSON fixture the Moqayasa C# core reads (test data only).
In Revit the add-in collects the same fields live. Each IFC record carries ONE measure (its natural one), so fixture
runs show fewer measures per category than a live Revit run."""
import json, sys
from hasr.extract import extract
from hasr.derived import _rooms
import ifcopenshell, ifcopenshell.util.unit as uu
from hasr.geometry import geometry_unit_correction

MAP = {"IfcWall": "Walls", "IfcWallStandardCase": "Walls", "IfcCurtainWall": "CurtainWalls", "IfcDoor": "Doors", "IfcWindow": "Windows",
       "IfcSlab": "Floors", "IfcCovering": "Ceilings", "IfcRoof": "Roofs", "IfcStair": "Stairs", "IfcStairFlight": "Stairs", "IfcRamp": "Ramps",
       "IfcRailing": "Railings", "IfcColumn": "StructuralColumns", "IfcBeam": "StructuralFraming", "IfcMember": "StructuralFraming",
       "IfcFooting": "StructuralFoundation", "IfcFurniture": "Furniture", "IfcFurnishingElement": "Furniture",
       "IfcSanitaryTerminal": "PlumbingFixtures", "IfcLightFixture": "LightingFixtures", "IfcReinforcingBar": "Rebar", "IfcBuildingElementProxy": "GenericModels"}
FIELD = {"m3": "Volume", "m2": "Area", "m": "Length", "count": "Count"}

def main(src, out, project):
    recs = [x for x in extract(src) if isinstance(x, list)][0]
    els = []
    for r in recs:
        cat = MAP.get(r.ifc_type)
        if not cat or r.value is None: continue
        d = {"Id": r.guid, "Category": cat, "TypeName": r.name.split(":")[0] if r.name else r.ifc_type, "Level": r.storey, "Material": r.material}
        f = FIELD.get(r.unit_key)
        if f == "Count": d["Count"] = 1
        elif f: d[f] = round(r.value, 4)
        els.append(d)
    m = ifcopenshell.open(src)
    lf = uu.calculate_unit_scale(m)
    rooms = [{"Id": s["guid"], "Name": s["name"], "LongName": s["long_name"], "Level": s["storey"], "Area": s["area"], "Perimeter": s["perimeter"], "Height": s["height"]}
             for s in _rooms(m, geometry_unit_correction(m, m.by_type("IfcSpace"), lf) if m.by_type("IfcSpace") else 1.0, lf)]
    json.dump({"project": project, "elements": els, "rooms": rooms, "materialAreas": []}, open(out, "w"), ensure_ascii=False)
    print(len(els), "elements", len(rooms), "rooms")

if __name__ == "__main__": main(*sys.argv[1:4])
