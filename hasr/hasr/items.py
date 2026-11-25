"""Classification of IFC elements into bilingual BOQ items.

Item names follow Egyptian / Gulf BOQ (فهرس بنود) conventions.

Classification rules:
- IFC type alone never asserts an engineering material. A slab is "Slabs"
  unless the model's own material name supports "Reinforced concrete".
- Material refinement uses keywords matched against the material name stored
  in the IFC file, so it is grounded in the model, not guessed.
- Element types with no BOQ meaning (e.g. IfcBuildingElementProxy) are
  UNCLASSIFIED: they are reported and flagged, never summed into BOQ totals.

Each family entry: (Arabic item, English item, quantity priority keys, unit key).
"""

UNITS = {
    "m3": ("م³", "m³"),
    "m2": ("م²", "m²"),
    "m": ("م طولي", "m"),
    "count": ("عدد", "No."),
}

UNCLASSIFIED = "unclassified"

# Material keyword refinement: (keywords, Arabic item, English item, priority keys, unit)
# Checked in order; first keyword hit wins.
# "Reinforced" is asserted only when the model itself says so (material name).
# Plain concrete stays neutral "Concrete" — concrete alone does not establish
# reinforcement.
RC_KEYWORDS = ("reinforced", "مسلح", "مسلحة", "r.c.")
CONCRETE_KEYWORDS = ("concrete", "خرسانة", "خرساني")
MATERIAL_REFINEMENTS = {
    "wall": [
        (("gypsum", "fiber-board", "fiberboard", "plasterboard", "drywall"),
         "حوائط جبس بورد", "Gypsum board walls",
         ["NetSideArea", "GrossSideArea", "Area"], "m2"),
        (("stone", "brick", "block", "sand-lime", "masonry"),
         "أعمال المباني - حوائط", "Masonry works - Walls",
         ["NetVolume", "GrossVolume", "NetSideArea", "Length"], "m3"),
        (RC_KEYWORDS,
         "أعمال الخرسانة المسلحة - حوائط", "Reinforced concrete - Walls",
         ["NetVolume", "GrossVolume"], "m3"),
        (CONCRETE_KEYWORDS,
         "خرسانة - حوائط", "Concrete - Walls",
         ["NetVolume", "GrossVolume"], "m3"),
    ],
    "slab": [
        (RC_KEYWORDS,
         "أعمال الخرسانة المسلحة - بلاطات", "Reinforced concrete - Slabs",
         ["NetVolume", "GrossVolume", "NetArea"], "m3"),
        (CONCRETE_KEYWORDS,
         "خرسانة - بلاطات", "Concrete - Slabs",
         ["NetVolume", "GrossVolume", "NetArea"], "m3"),
    ],
    "column": [
        (RC_KEYWORDS,
         "أعمال الخرسانة المسلحة - أعمدة", "Reinforced concrete - Columns",
         ["NetVolume", "GrossVolume"], "m3"),
        (CONCRETE_KEYWORDS,
         "خرسانة - أعمدة", "Concrete - Columns",
         ["NetVolume", "GrossVolume"], "m3"),
    ],
    "beam": [
        (RC_KEYWORDS,
         "أعمال الخرسانة المسلحة - كمرات", "Reinforced concrete - Beams",
         ["NetVolume", "GrossVolume"], "m3"),
        (CONCRETE_KEYWORDS,
         "خرسانة - كمرات", "Concrete - Beams",
         ["NetVolume", "GrossVolume"], "m3"),
    ],
}

# Neutral per-type defaults when no material keyword matches.
# Engineering material is NOT asserted in these labels.
TYPE_DEFAULTS = {
    "IfcWall": ("حوائط", "Walls", ["NetVolume", "GrossVolume", "NetSideArea", "Length"], "m3", "wall"),
    "IfcWallStandardCase": ("حوائط", "Walls", ["NetVolume", "GrossVolume", "NetSideArea", "Length"], "m3", "wall"),
    "IfcSlab": ("بلاطات", "Slabs", ["NetVolume", "GrossVolume", "NetArea"], "m3", "slab"),
    "IfcColumn": ("أعمدة", "Columns", ["NetVolume", "GrossVolume"], "m3", "column"),
    "IfcBeam": ("كمرات", "Beams", ["NetVolume", "GrossVolume"], "m3", "beam"),
    "IfcStairFlight": ("سلالم", "Stairs", ["NetVolume", "GrossVolume"], "m3", "stair"),
    "IfcStair": ("سلالم", "Stairs", ["NetVolume", "GrossVolume"], "m3", "stair"),
    "IfcRamp": ("منحدرات", "Ramps", ["NetVolume", "GrossVolume"], "m3", None),
    "IfcRoof": ("أعمال الأسقف والأسطح", "Roofing works", ["NetArea", "GrossArea"], "m2", "roof"),
    "IfcDoor": ("أعمال الأبواب", "Doors", ["Count"], "count", None),
    "IfcWindow": ("أعمال الشبابيك", "Windows", ["Count"], "count", None),
    "IfcSpace": ("المساحات", "Spaces", ["NetFloorArea", "GrossFloorArea", "Area"], "m2", None),
    "IfcCovering": ("أعمال التشطيبات - تغطيات", "Finishes - Coverings", ["Area", "NetArea"], "m2", None),
    "IfcCurtainWall": ("واجهات زجاجية", "Curtain walls", ["Area", "NetArea"], "m2", "curtain_wall"),
    "IfcRailing": ("الدرابزينات", "Railings", ["Length"], "m", None),
    "IfcFooting": ("الأساسات والقواعد", "Footings", ["NetVolume", "GrossVolume"], "m3", "footing"),
    "IfcPile": ("الخوازيق", "Piles", ["Count"], "count", None),
}

# Fallback quantity keys per unit when the priority keys don't match
UNIT_FALLBACK_KEYS = {
    "m3": ["NetVolume", "GrossVolume", "Volume"],
    "m2": ["NetArea", "GrossArea", "NetSideArea", "NetFloorArea", "Area"],
    "m": ["Length"],
    "count": ["Count"],
}


def classify(ifc_type: str, material: str):
    """Return (item_ar, item_en, priority_keys, unit_key) or UNCLASSIFIED.

    Material comes from the IFC model itself; only keyword matches refine
    the label toward an engineering description.
    """
    entry = TYPE_DEFAULTS.get(ifc_type)
    if entry is None:
        return UNCLASSIFIED
    item_ar, item_en, keys, unit, family = entry
    if family and material:
        mat = material.lower()
        for keywords, r_ar, r_en, r_keys, r_unit in MATERIAL_REFINEMENTS.get(family, []):
            if any(k in mat for k in keywords):
                return r_ar, r_en, r_keys, r_unit
    return item_ar, item_en, keys, unit
