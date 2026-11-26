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


def geometry_measure(element, measure: str):
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
        if measure == "volume":
            return float(get_volume(g))
        if measure == "area":
            return float(get_area(g))
        if measure == "top_area":
            return float(get_top_area(g))
        if measure == "panel_area":
            # a flat panel has two big faces: half the surface, edges ignored
            return float(get_area(g)) / 2.0
        if measure == "length":
            # longest side of the bounding box: the run length of a linear member
            import numpy as np

            v = np.array(g.verts).reshape(-1, 3)
            return float((v.max(axis=0) - v.min(axis=0)).max())
    except Exception:
        return None
    return None
