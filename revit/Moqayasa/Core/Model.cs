namespace Moqayasa.Core;

/// <summary>One thing collected from the model (or from a fixture). Units are metres, m2, m3, kg.</summary>
public sealed class ElementData
{
    public string Id { get; set; } = "";
    public string Category { get; set; } = "";      // key from Policy.Categories
    public string TypeName { get; set; } = "";
    public string Level { get; set; } = "";
    public string Material { get; set; } = "";
    public double? Area { get; set; }
    public double? Volume { get; set; }
    public double? Length { get; set; }
    public double? Width { get; set; }
    public double? Height { get; set; }
    public double? WeightKg { get; set; }
    public double? FormworkArea { get; set; }       // derived from geometry by the add-in, concrete elements only
    public int Count { get; set; } = 1;
    public string Note { get; set; } = "";
}

/// <summary>Area of one material on one element (Revit material takeoff), used for paint, gypsum, plaster, tiles.</summary>
public sealed class MaterialArea
{
    public string ElementId { get; set; } = "";
    public string HostCategory { get; set; } = "";   // Walls, Ceilings, Floors
    public string Level { get; set; } = "";
    public string Material { get; set; } = "";
    public bool Painted { get; set; }                // true = applied with the Paint tool, false = a material layer
    public double Area { get; set; }
}

public sealed class RoomData
{
    public string Id { get; set; } = "";
    public string Name { get; set; } = "";
    public string LongName { get; set; } = "";
    public string Level { get; set; } = "";
    public double Area { get; set; }
    public double Perimeter { get; set; }
    public double Height { get; set; }
}

public sealed class BoqLine
{
    public int Order { get; set; }
    public string GroupAr { get; set; } = "";
    public string GroupEn { get; set; } = "";
    public string ItemAr { get; set; } = "";
    public string ItemEn { get; set; } = "";
    public string Unit { get; set; } = "";           // m2 m3 m count ton
    public double Qty { get; set; }
    public int Elements { get; set; }
    public string Basis { get; set; } = "";
    public double? Price { get; set; }
    public string PriceKind { get; set; } = "";       // "manual" (prices.csv) | "reference" (market feed) | "" (needs quote)
    public string PriceNote { get; set; } = "";       // source, date, scope for a reference price
    public string Material { get; set; } = "";        // material of the first element, used only to match reference prices
    public string Key => ItemEn;
}

public sealed class Finding
{
    public string Status { get; set; } = "orange";   // green orange red
    public string Where { get; set; } = "";
    public string Ar { get; set; } = "";
    public string En { get; set; } = "";
}

public sealed class TakeoffResult
{
    public List<BoqLine> Lines { get; } = new();
    public List<ElementData> Elements { get; } = new();
    public List<MaterialArea> MaterialAreas { get; } = new();
    public List<string> Notes { get; } = new();
    public List<PurchaseLine> Purchase { get; } = new();
    public List<EvidenceRow> Evidence { get; } = new();
    public List<Finding> Findings { get; } = new();
    public List<RoomData> Rooms { get; } = new();
    public string ProjectName { get; set; } = "";
}

public sealed class PurchaseLine
{
    public string SystemAr = "", SystemEn = "", Ar = "", En = "", Unit = "", PackAr = "", PackEn = "";
    public double Net, Waste, Gross;
    public double? PackSize;
    public int? Packs;
    public bool Approved;
    public int Rooms;
    public double? PricePerPack;
}

public sealed class EvidenceRow
{
    public string Room = "", Guid = "", Scope = "", System = "", Component = "", BaseLabel = "", BaseNote = "", Formula = "", Unit = "", Source = "";
    public double Base, Net, Waste;
    public bool Approved;
}
