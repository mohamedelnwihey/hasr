"""Extract building elements and their quantities from an IFC model."""

from __future__ import annotations

from dataclasses import dataclass, field

import ifcopenshell

from .items import UNCLASSIFIED, UNIT_FALLBACK_KEYS, classify

# Element types that carry no BOQ meaning on their own
NON_BOQ_TYPES = {"IfcBuildingElementProxy", "IfcOpeningElement"}

QUANTITY_KIND_ATTR = {
    "IfcQuantityLength": ("LengthValue", "length"),
    "IfcQuantityArea": ("AreaValue", "area"),
    "IfcQuantityVolume": ("VolumeValue", "volume"),
    "IfcQuantityCount": ("CountValue", "count"),
}

STATUS_OK = "ok"
STATUS_GEOMETRY = "geometry"  # estimated from element geometry, no quantities in file
STATUS_NO_QUANTITY = "no_quantity"
STATUS_UNCLASSIFIED = "unclassified"

# IFC type -> geometry family for the estimate fallback
from .items import TYPE_DEFAULTS
from .geometry import GEOMETRY_MEASURE, geometry_measure


@dataclass
class ElementRecord:
    guid: str
    ifc_type: str
    name: str
    storey: str
    material: str
    item_ar: str
    item_en: str
    unit_key: str
    status: str
    quantities: dict = field(default_factory=dict)  # quantity name -> value in m/m2/m3/count
    value: float | None = None


def _unit_factors(model):
    """Per-kind conversion factors to m / m2 / m3 from IfcUnitAssignment.

    IFC declares separate units per measure kind: a model can have lengths in
    millimetres while areas and volumes are already in square/cubic metres.
    Quantities follow the unit of their own kind, so each kind gets its own
    factor. Returns (length_factor, area_factor, volume_factor, note).
    SI prefixes honored; conversion-based units (feet/inches) are flagged in
    the note and treated as 1.0.
    """
    note = ""
    # (unit type, exponent of the SI prefix, target unit)
    kinds = {"LENGTHUNIT": 1, "AREAUNIT": 2, "VOLUMEUNIT": 3}
    factors = {1: 1.0, 2: 1.0, 3: 1.0}
    try:
        for assignment in model.by_type("IfcUnitAssignment"):
            for unit in assignment.Units or []:
                exponent = kinds.get(getattr(unit, "UnitType", None))
                if exponent is None:
                    continue
                if unit.is_a("IfcSIUnit"):
                    factors[exponent] = _si_prefix_scale(unit) ** exponent
                elif unit.is_a("IfcConversionBasedUnit"):
                    note = (f"conversion-based {unit.UnitType.lower()} ({unit.Name}); "
                            "values assumed as-is")
    except Exception:
        pass
    return factors[1], factors[2], factors[3], note


def _si_prefix_scale(unit):
    """SI prefix scale of an IfcSIUnit, exponent applied by caller."""
    prefix_scale = {
        "ATTO": 1e-18, "FEMTO": 1e-15, "PICO": 1e-12, "NANO": 1e-9,
        "MICRO": 1e-6, "MILLI": 1e-3, "CENTI": 1e-2, "DECI": 1e-1,
        "DECA": 1e1, "HECTO": 1e2, "KILO": 1e3, "MEGA": 1e6,
        "GIGA": 1e9, "TERA": 1e12, "PETA": 1e15, "EXA": 1e18,
    }
    prefix = getattr(unit, "Prefix", None)
    return prefix_scale.get(str(prefix), 1.0) if prefix else 1.0


def _quantity_override_factor(q, kind, project_factor):
    """IFC4 per-quantity unit override: IfcPhysicalSimpleQuantity.Unit.

    When a quantity carries its own IfcSIUnit, it wins over the project unit
    for that kind. Returns the factor to convert that quantity to m/m2/m3.
    """
    unit = getattr(q, "Unit", None)
    if unit is None:
        return project_factor
    exponent = {"length": 1, "area": 2, "volume": 3}.get(kind)
    if exponent is None:
        return 1.0
    try:
        if unit.is_a("IfcSIUnit"):
            return _si_prefix_scale(unit) ** exponent
    except Exception:
        pass
    return project_factor


def _read_quantities(element, factors):
    """Walk IfcElementQuantity sets; return {name: value} in m/m2/m3/count.

    Each quantity converts by its own kind's factor, honoring an IFC4
    per-quantity unit override. If duplicate quantity names appear (e.g. a
    qto set repeated via multiple relations), the last wins — values are
    never summed, so nothing is double-counted.
    """
    lf, af, vf = factors
    project_factor = {"length": lf, "area": af, "volume": vf}
    out = {}
    try:
        for rel in element.IsDefinedBy or []:
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            qto = rel.RelatingPropertyDefinition
            if not qto or not qto.is_a("IfcElementQuantity"):
                continue
            for q in qto.Quantities or []:
                spec = QUANTITY_KIND_ATTR.get(q.is_a())
                if not spec:
                    continue
                attr, kind = spec
                val = getattr(q, attr, None)
                if val is None:
                    continue
                factor = _quantity_override_factor(q, kind, project_factor.get(kind, 1.0))
                out[q.Name] = float(val) * factor
    except Exception:
        pass
    return out


def _storey_of(element) -> str:
    try:
        for rel in element.ContainedInStructure or []:
            struct = rel.RelatingStructure
            if struct and struct.is_a("IfcBuildingStorey"):
                return struct.Name or ""
    except Exception:
        pass
    return ""


def _material_of(element) -> str:
    try:
        from ifcopenshell.util.element import get_material

        mat = get_material(element)
        if mat is None:
            return ""
        if mat.is_a("IfcMaterial"):
            return mat.Name or ""
        if mat.is_a("IfcMaterialList") and mat.Materials:
            return ", ".join(m.Name or "" for m in mat.Materials if m.is_a("IfcMaterial"))
        if mat.is_a("IfcMaterialLayerSet") and mat.MaterialLayers:
            return ", ".join(
                layer.Material.Name or "" for layer in mat.MaterialLayers if layer.Material
            )
    except Exception:
        pass
    return ""


def _choose_value(quantities: dict, priority_keys: list, unit_key: str):
    for key in priority_keys:
        if key in quantities and quantities[key] is not None:
            return quantities[key]
    for key in UNIT_FALLBACK_KEYS.get(unit_key, []):
        if key in quantities and quantities[key] is not None:
            return quantities[key]
    return None


def extract(path: str, use_geometry: bool = True):
    """Open an IFC file and return (project_name, schema, unit_note, [ElementRecord]).

    use_geometry: when an element has no quantity sets, estimate its measure
    from its geometry (labeled STATUS_GEOMETRY, always shown as estimated).
    """
    model = ifcopenshell.open(path)
    schema = model.schema

    project_name = ""
    projects = model.by_type("IfcProject")
    if projects:
        project_name = projects[0].Name or ""

    lf, af, vf, unit_note = _unit_factors(model)
    factors = (lf, af, vf)

    records = []
    for element in model.by_type("IfcBuildingElement"):
        ifc_type = element.is_a()
        material = _material_of(element)
        result = classify(ifc_type, material)

        if result == UNCLASSIFIED or ifc_type in NON_BOQ_TYPES:
            records.append(
                ElementRecord(
                    guid=element.GlobalId, ifc_type=ifc_type, name=element.Name or "",
                    storey=_storey_of(element), material=material,
                    item_ar="", item_en="", unit_key="", status=STATUS_UNCLASSIFIED,
                )
            )
            continue

        item_ar, item_en, priority_keys, unit_key = result
        quantities = _read_quantities(element, factors)
        if unit_key == "count" and "Count" not in quantities:
            quantities["Count"] = 1.0
        value = _choose_value(quantities, priority_keys, unit_key)
        status = STATUS_OK if value is not None else STATUS_NO_QUANTITY

        if value is None and use_geometry:
            family = (TYPE_DEFAULTS.get(ifc_type) or (None, None, None, None, None))[4]
            measure = GEOMETRY_MEASURE.get(family or "")
            if measure:
                raw = geometry_measure(element, measure)
                if raw is not None:
                    # the geometry engine normalizes coordinates to meters,
                    # so geometry measures are already m / m2 / m3
                    value = raw
                    status = STATUS_GEOMETRY

        records.append(
            ElementRecord(
                guid=element.GlobalId, ifc_type=ifc_type, name=element.Name or "",
                storey=_storey_of(element), material=material,
                item_ar=item_ar, item_en=item_en, unit_key=unit_key,
                status=status,
                quantities=quantities, value=value,
            )
        )
    return project_name, schema, unit_note, records


def aggregate(records):
    """Aggregate classified records into BOQ lines with per-row provenance.

    Returns {key: stats} where key = (item_ar, item_en, unit_key) and stats:
      qty        total quantity (file + geometry)
      file_qty   quantity from the file's own quantity sets
      file_n     elements contributing file quantities
      geo_qty    geometry-derived estimated quantity
      geo_n      elements contributing geometry estimates
      missing_n  classified elements of this item with no quantity at all
    """
    lines = {}
    for rec in records:
        if rec.status == STATUS_UNCLASSIFIED:
            continue
        key = (rec.item_ar, rec.item_en, rec.unit_key)
        stats = lines.setdefault(key, {
            "qty": 0.0, "file_qty": 0.0, "file_n": 0,
            "geo_qty": 0.0, "geo_n": 0, "missing_n": 0,
        })
        if rec.status == STATUS_OK and rec.value is not None:
            stats["file_qty"] += rec.value
            stats["file_n"] += 1
        elif rec.status == STATUS_GEOMETRY and rec.value is not None:
            stats["geo_qty"] += rec.value
            stats["geo_n"] += 1
        else:
            stats["missing_n"] += 1
    for stats in lines.values():
        stats["qty"] = stats["file_qty"] + stats["geo_qty"]
    # items whose elements ALL lack quantities are not BOQ rows; they stay
    # flagged in the notes/detail, never shown as a zero-quantity line
    return {k: s for k, s in lines.items() if s["file_n"] + s["geo_n"] > 0}


def summarize_issues(records):
    """Counts and types of elements that did not make it into the BOQ."""
    unclassified = [r for r in records if r.status == STATUS_UNCLASSIFIED]
    no_qty = [r for r in records if r.status == STATUS_NO_QUANTITY]
    geometry = [r for r in records if r.status == STATUS_GEOMETRY]
    return unclassified, no_qty, geometry
