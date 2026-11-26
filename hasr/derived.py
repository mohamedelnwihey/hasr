"""Derived quantities: the items a quantity surveyor needs that IFC does not state.

Everything here is an ESTIMATE computed from the model's own geometry and
materials (plus ratios YOU supply for reinforcement). Each derived quantity is
stored as a normal ElementRecord with status "geometry", so it shows up in the
BOQ, the per-storey sheet, the audit sheet and the price columns, always
labeled as a geometry-derived estimate. Hasr ships no ratios and no prices.

Derived items:
- Wall face area (both faces, openings already removed by the model), plaster
  (masonry walls only) and paint (masonry and gypsum walls).
- Concrete formwork, only for elements whose own material says concrete:
  slabs and beams (everything except the top face), columns, footings and
  walls (vertical faces).
- Reinforcement steel in tonnes, only when you give kg/m3 ratios.
- Room finishes from IfcSpace: floor, ceiling, skirting length, wall finish
  area (perimeter x height, no opening deduction).
"""

from __future__ import annotations

import csv
import math
import sys

from .extract import STATUS_GEOMETRY, ElementRecord, _storey_of
from .items import TYPE_DEFAULTS

CONCRETE_WORDS = ("concrete", "خرسانة", "خرساني", "reinforced", "مسلح", "r.c.")
MASONRY_ITEM = "Masonry works - Walls"
GYPSUM_ITEM = "Gypsum board walls"

REBAR_FAMILIES = {
    "slabs": ("Slabs", "بلاطات"),
    "beams": ("Beams", "كمرات"),
    "columns": ("Columns", "أعمدة"),
    "footings": ("Footings", "قواعد"),
    "walls": ("Walls", "حوائط"),
}

FORMWORK_NAMES = {
    "slab": ("شدة خشبية - بلاطات", "Formwork - Slabs"),
    "beam": ("شدة خشبية - كمرات", "Formwork - Beams"),
    "column": ("شدة خشبية - أعمدة", "Formwork - Columns"),
    "footing": ("شدة خشبية - قواعد", "Formwork - Footings"),
    "wall": ("شدة خشبية - حوائط", "Formwork - Walls"),
}

ASSUMPTIONS = [
    ("مسطحات الحوائط", "Wall faces",
     "مساحة الوجهين الكبيرين للحائط من المجسم، بعد خصم الفتحات اللي الموديل مفرغها. "
     "ما فيهاش كوالح الفتحات ولا الأطراف.",
     "Area of the two large faces of each wall from the solid, after the openings "
     "the model voids. Excludes reveals and wall ends."),
    ("بياض", "Plaster",
     "وجهين كل حائط ماديته مباني (طوب/بلوك/حجر) حسب اسم الخامة في الموديل فقط.",
     "Both faces of walls whose own material is masonry (brick/block/stone). Nothing else."),
    ("دهانات", "Paint",
     "وجهين حوائط المباني والجبس بورد حسب الخامة. مفيش خصم لتشطيب تاني.",
     "Both faces of masonry and gypsum walls by material. No deduction for other finishes."),
    ("شدة خشبية", "Formwork",
     "لعناصر ماديتها خرسانة بس. بلاطات وكمرات: كل الأسطح ماعدا الوش العلوي. "
     "أعمدة وقواعد وحوائط: الأسطح الرأسية.",
     "Only elements whose own material says concrete. Slabs and beams: all faces except "
     "the top. Columns, footings, walls: vertical faces."),
    ("حديد التسليح", "Reinforcement",
     "بالطن = حجم الخرسانة x معامل كجم/م³ من ملفك. مفيش معاملات جاهزة في البرنامج.",
     "Tonnes = concrete volume x your kg/m3 ratio. Hasr ships no ratios."),
    ("تشطيبات الغرف", "Room finishes",
     "من IfcSpace: أرضية وسقف = مساحة الغرفة، وزرة = المحيط، حوائط = المحيط x الارتفاع "
     "بدون خصم أبواب وشبابيك.",
     "From IfcSpace: floor and ceiling = room area, skirting = perimeter, wall finish = "
     "perimeter x height with no door or window deduction."),
]


def _mesh_stats(g, correction=1.0):
    """Areas by face direction, in m2. Returns dict or None."""
    import numpy as np

    v = np.array(g.verts, dtype=float).reshape(-1, 3) * correction
    f = np.array(g.faces, dtype=int).reshape(-1, 3)
    if len(f) == 0:
        return None
    cr = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    ln = np.linalg.norm(cr, axis=1)
    ok = ln > 1e-12
    cr, ln = cr[ok], ln[ok]
    area = ln / 2.0
    n = cr / ln[:, None]
    nz = n[:, 2]
    top = float(area[nz > 0.5].sum())
    bottom = float(area[nz < -0.5].sum())
    vert_mask = np.abs(nz) <= 0.5
    vertical = float(area[vert_mask].sum())
    # the two big wall faces: opposite horizontal directions with the most area
    ang = np.degrees(np.arctan2(n[vert_mask, 1], n[vert_mask, 0])) % 360.0
    bins = {}
    for a, ar in zip(ang, area[vert_mask]):
        b = int(round(a / 5.0)) % 72
        bins[b] = bins.get(b, 0.0) + float(ar)
    best = 0.0
    for b in range(72):
        pair = bins.get(b, 0.0) + bins.get((b + 36) % 72, 0.0)
        best = max(best, pair)
    zs = v[:, 2]
    return {"total": float(area.sum()), "top": top, "bottom": bottom,
            "vertical": vertical, "faces_pair": best,
            "height": float(zs.max() - zs.min())}


def _family(ifc_type):
    entry = TYPE_DEFAULTS.get(ifc_type)
    return entry[4] if entry else None


def _is_concrete(rec):
    mat = (rec.material or "").lower()
    return any(w in mat for w in CONCRETE_WORDS)


def _derived(src, item, value, unit, storey=None):
    return ElementRecord(
        guid=src.guid, ifc_type=src.ifc_type, name=src.name,
        storey=src.storey if storey is None else storey, material=src.material,
        item_ar=item[0], item_en=item[1], unit_key=unit,
        status=STATUS_GEOMETRY, quantities={}, value=value,
    )


def load_rebar_ratios(path):
    """family,kg_per_m3 rows. family: slabs|beams|columns|footings|walls."""
    ratios = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            fam = (row.get("family") or "").strip().lower()
            raw = (row.get("kg_per_m3") or "").strip().replace(",", "")
            if not fam or not raw:
                continue
            if fam not in REBAR_FAMILIES:
                print(f"warning: unknown rebar family '{fam}'", file=sys.stderr)
                continue
            try:
                ratios[fam] = float(raw)
            except ValueError:
                print(f"warning: bad ratio for '{fam}': {raw!r}", file=sys.stderr)
    return ratios


def write_rebar_template(path):
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["family", "kg_per_m3"])
        for fam in REBAR_FAMILIES:
            w.writerow([fam, ""])


def _rebar_records(records, ratios):
    out = []
    fam_by_type = {"IfcSlab": "slabs", "IfcBeam": "beams", "IfcColumn": "columns",
                   "IfcFooting": "footings", "IfcWall": "walls", "IfcWallStandardCase": "walls"}
    for r in records:
        fam = fam_by_type.get(r.ifc_type)
        if not fam or fam not in ratios or r.unit_key != "m3" or r.value is None:
            continue
        if r.status not in ("ok", "geometry") or not _is_concrete(r):
            continue
        en, ar = REBAR_FAMILIES[fam]
        out.append(_derived(r, (f"حديد تسليح - {ar} (بمعامل المستخدم)",
                                f"Reinforcement steel - {en} (user ratio)"),
                            r.value * ratios[fam] / 1000.0, "ton"))
    return out


def _openings(model, lf):
    """Door and window schedule rows: type, width, height, storey, count."""
    from ifcopenshell.util.element import get_type

    groups = {}
    for el in list(model.by_type("IfcDoor")) + list(model.by_type("IfcWindow")):
        try:
            t = get_type(el)
            name = (t.Name if t is not None and t.Name else el.Name) or ""
            w = getattr(el, "OverallWidth", None)
            h = getattr(el, "OverallHeight", None)
            w = round(float(w) * lf, 3) if w else None
            h = round(float(h) * lf, 3) if h else None
            key = (el.is_a(), name, w, h, _storey_of(el))
            groups[key] = groups.get(key, 0) + 1
        except Exception:
            continue
    return [
        {"kind": k[0], "type": k[1], "width": k[2], "height": k[3], "storey": k[4], "count": n}
        for k, n in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][4]))
    ]


def _container_storey(space):
    try:
        from ifcopenshell.util.element import get_container

        c = get_container(space)
        while c is not None and not c.is_a("IfcBuildingStorey"):
            c = get_container(c)
        return c.Name if c is not None and c.Name else ""
    except Exception:
        return ""


def _rooms(model, correction):
    """One dict per IfcSpace: name, storey, floor area, perimeter, height."""
    import ifcopenshell.geom as geom
    from ifcopenshell.util.shape import get_footprint_area, get_footprint_perimeter

    from .geometry import _settings

    rows = []
    for sp in model.by_type("IfcSpace"):
        try:
            shape = geom.create_shape(_settings(), sp)
            g = shape.geometry
            stats = _mesh_stats(g, correction)
            area = float(get_footprint_area(g)) * correction ** 2
            perim = float(get_footprint_perimeter(g)) * correction
            if area <= 0 or stats is None:
                continue
            rows.append({
                "guid": sp.GlobalId, "name": sp.Name or "", "long_name": sp.LongName or "",
                "storey": _container_storey(sp), "area": area, "perimeter": perim,
                "height": stats["height"],
            })
        except Exception:
            continue
    return rows


def derive(path, records, ratios=None, use_geometry=True):
    """Return (new_records, extras). extras: openings, rooms, assumptions."""
    import ifcopenshell
    import ifcopenshell.geom as geom
    from ifcopenshell.util.unit import calculate_unit_scale

    from .extract import _unit_factors
    from .geometry import _settings, geometry_unit_correction

    model = ifcopenshell.open(path)
    lf = _unit_factors(model)[0]
    correction = 1.0
    if use_geometry:
        try:
            correction = geometry_unit_correction(
                model, model.by_type("IfcBuildingElement"), calculate_unit_scale(model))
        except Exception:
            correction = 1.0

    new = []
    if use_geometry:
        for rec in records:
            fam = _family(rec.ifc_type)
            if fam not in ("wall", "slab", "beam", "column", "footing") or not rec.item_en:
                continue
            is_conc = _is_concrete(rec)
            masonry = rec.item_en == MASONRY_ITEM
            gypsum = rec.item_en == GYPSUM_ITEM
            if not (is_conc or (fam == "wall")):
                continue
            try:
                el = model.by_guid(rec.guid)
                g = geom.create_shape(_settings(), el).geometry
                st = _mesh_stats(g, correction)
            except Exception:
                continue
            if st is None:
                continue
            if fam == "wall":
                faces = st["faces_pair"]
                if faces > 0:
                    new.append(_derived(rec, ("مسطحات الحوائط (الوجهين)", "Wall faces, both sides (derived)"), faces, "m2"))
                    if masonry:
                        new.append(_derived(rec, ("بياض حوائط (مشتق)", "Wall plaster (derived)"), faces, "m2"))
                    if masonry or gypsum:
                        new.append(_derived(rec, ("دهانات حوائط (مشتق)", "Wall paint (derived)"), faces, "m2"))
            if is_conc:
                if fam in ("slab", "beam"):
                    area = st["total"] - st["top"]
                else:
                    area = st["vertical"]
                if area > 0:
                    new.append(_derived(rec, FORMWORK_NAMES[fam], area, "m2"))

    if ratios:
        new += _rebar_records(records, ratios)

    rooms = _rooms(model, correction) if use_geometry else []
    for r in rooms:
        src = ElementRecord(guid=r["guid"], ifc_type="IfcSpace", name=r["name"],
                            storey=r["storey"], material="", item_ar="", item_en="",
                            unit_key="", status=STATUS_GEOMETRY)
        new.append(_derived(src, ("تشطيب أرضيات الغرف", "Room floor finish"), r["area"], "m2"))
        new.append(_derived(src, ("تشطيب أسقف الغرف", "Room ceiling finish"), r["area"], "m2"))
        new.append(_derived(src, ("وزرات الغرف (المحيط)", "Room skirting (perimeter)"), r["perimeter"], "m"))
        new.append(_derived(src, ("تشطيب حوائط الغرف", "Room wall finish"), r["perimeter"] * r["height"], "m2"))

    extras = {"openings": _openings(model, lf), "rooms": rooms, "assumptions": ASSUMPTIONS}
    return new, extras
