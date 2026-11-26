"""Geometry-derived quantities for elements with no IfcElementQuantity.

Uses ifcopenshell's geometry engine (OpenCASCADE) to compute mesh-based
measures. These are ESTIMATES: gross or net depending on the exporter's
solids, and always labeled geometry-derived in the output.
"""

from __future__ import annotations

# Which measure each BOQ unit needs per family
GEOMETRY_MEASURE = {
    "wall": "volume",
    "slab": "volume",
    "column": "volume",
    "beam": "volume",
    "stair": "volume",
    "roof": "top_area",
    "footing": "volume",
    "curtain_wall": "area",
    "member": "length",
    "plate": "panel_area",
    "covering": "top_area",
    "railing": "length",
}

_SETTINGS = None


def _settings():
    global _SETTINGS
    if _SETTINGS is None:
        import ifcopenshell.geom as geom

        _SETTINGS = geom.settings()
    return _SETTINGS


def _raw_extent(item):
    """Largest raw (file-unit) dimension of an IfcExtrudedAreaSolid, or None."""
    try:
        prof = item.SweptArea
        dims = [float(item.Depth)]
        if prof.is_a("IfcRectangleProfileDef"):
            dims += [float(prof.XDim), float(prof.YDim)]
        elif prof.is_a("IfcCircleProfileDef"):
            dims.append(2 * float(prof.Radius))
        elif prof.is_a("IfcArbitraryClosedProfileDef") and prof.OuterCurve.is_a("IfcPolyline"):
            pts = [p.Coordinates for p in prof.OuterCurve.Points]
            for axis in (0, 1):
                vals = [c[axis] for c in pts]
                dims.append(max(vals) - min(vals))
        else:
            return None
        return max(dims)
    except Exception:
        return None


def geometry_unit_correction(model, elements, unit_scale: float, probes: int = 25):
    """Factor that turns the geometry engine's numbers into metres.

    Some exports come back from the engine in the file's own length unit
    instead of metres (seen on an IFC4 millimetre file). We probe a few
    elements whose raw size is readable (extruded solids), compare it with
    the engine's output, and vote. Returns 1.0 when the file is already in
    metres or when no probe is conclusive.
    """
    import math

    if abs(unit_scale - 1.0) < 1e-9:
        return 1.0
    unscaled = scaled = 0
    for el in elements:
        if unscaled + scaled >= probes:
            break
        try:
            reps = el.Representation.Representations if el.Representation else []
            item = next((i for r in reps if r.RepresentationIdentifier == "Body"
                         for i in r.Items if i.is_a("IfcExtrudedAreaSolid")), None)
            if item is None:
                continue
            raw = _raw_extent(item)
            if not raw:
                continue
            import ifcopenshell.geom as geom
            import numpy as np

            v = np.array(geom.create_shape(_settings(), el).geometry.verts).reshape(-1, 3)
            ext = float((v.max(axis=0) - v.min(axis=0)).max())
            if ext <= 0:
                continue
            ratio = ext / raw
            if abs(math.log(ratio)) < abs(math.log(ratio / unit_scale)):
                unscaled += 1
            else:
                scaled += 1
        except Exception:
            continue
    if unscaled > scaled:
        return unit_scale
    return 1.0


def geometry_measure(element, measure: str, correction: float = 1.0):
    """Return the requested measure in m / m2 / m3.

    ifcopenshell's geometry engine normalizes coordinates to meters
    regardless of the file's declared length unit (verified against a
    mm-declared Revit export whose wall bounding boxes come out in meters).
    measure: volume | area | top_area. None when the shape fails.
    """
    try:
        import ifcopenshell.geom as geom
        from ifcopenshell.util.shape import get_area, get_top_area, get_volume

        shape = geom.create_shape(_settings(), element)
        g = shape.geometry
        c = correction
        if measure == "volume":
            return float(get_volume(g)) * c ** 3
        if measure == "area":
            return float(get_area(g)) * c ** 2
        if measure == "top_area":
            return float(get_top_area(g)) * c ** 2
        if measure == "panel_area":
            # a flat panel has two big faces: half the surface, edges ignored
            return float(get_area(g)) / 2.0 * c ** 2
        if measure == "length":
            # longest side of the bounding box: the run length of a linear member
            import numpy as np

            v = np.array(g.verts).reshape(-1, 3)
            return float((v.max(axis=0) - v.min(axis=0)).max()) * c
    except Exception:
        return None
    return None
