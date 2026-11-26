using Autodesk.Revit.DB;

namespace Moqayasa;

/// <summary>Everything that differs between Revit 2022..2027 lives here, so the rest of the code is one source for all years.</summary>
static class Compat
{
    public static long IdValue(ElementId id) =>
#if REVIT2022 || REVIT2023
        id.IntegerValue;
#else
        id.Value;
#endif

    public static string IdText(Element e) => IdValue(e.Id).ToString();

    public static double M(double feet) => UnitUtils.ConvertFromInternalUnits(feet, UnitTypeId.Meters);
    public static double M2(double sqft) => UnitUtils.ConvertFromInternalUnits(sqft, UnitTypeId.SquareMeters);
    public static double M3(double cuft) => UnitUtils.ConvertFromInternalUnits(cuft, UnitTypeId.CubicMeters);

    public static BuiltInCategory Bic(Element e)
    {
        var c = e.Category; if (c == null) return BuiltInCategory.INVALID;
        return (BuiltInCategory)IdValue(c.Id);
    }
}
