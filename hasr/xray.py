"""X-RAY: finishing systems -> purchase quantities, evidence per number, "what is missing".

Input: the rooms (IfcSpace) of the model, a finishing-systems file you can edit
(JSON), and optionally your existing BOQ (CSV or XLSX).

What it does
- Measures each room: floor area, ceiling area, perimeter, wall area.
- Assigns a finishing system per room and scope (floor, wall, ceiling) by rules.
- Breaks every system into components (tiles, adhesive, boards, paint ...) and
  converts to purchase quantities with a DECLARED waste percentage and packs.
- Shows the evidence for every number: where in the model, the base measure,
  the formula, the rate and its source.
- Lists what is missing, in three colors:
    green  = measured from the model and every rate used is approved by you
    orange = a rate or rule that is still an unapproved example, or an item that
             your BOQ may already include
    red    = no system for that scope, a required item missing, no rooms, or
             nothing in your BOQ for it

Hasr ships EXAMPLE rates (systems_example.json) marked approved=false. They are
typical-looking starting points, not specifications. Check them against your
spec or the product data sheet, then set "approved": true. Until then every
purchase number built on them stays orange.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re

GREEN, ORANGE, RED = "green", "orange", "red"
STATUS_LABEL = {GREEN: ("أخضر", "green"), ORANGE: ("برتقالي", "orange"), RED: ("أحمر", "red")}
SCOPES = ("floor", "wall", "ceiling")
SCOPE_LABEL = {"floor": ("أرضية", "Floor"), "wall": ("حوائط", "Walls"), "ceiling": ("سقف", "Ceiling")}

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "systems_example.json")


def load_systems(path=None):
    with open(path or DEFAULT_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _base_measure(room, scope):
    """(value, unit, label_ar, label_en, formula note)"""
    if scope in ("floor", "ceiling"):
        return room["area"], "m2", "مساحة الغرفة", "room area", "from the IfcSpace footprint"
    return (room["perimeter"] * room["height"], "m2", "محيط × ارتفاع", "perimeter x height",
            "gross wall area, NO deduction for doors/windows")


def _component_net(comp, room, base):
    """Net quantity (before waste) and the formula text."""
    kind = comp["kind"]
    if kind == "per_m2":
        return base * comp["rate"], f"{base:.2f} m2 x {comp['rate']} {comp['unit']}/m2"
    if kind == "piece":
        n = base / comp["piece_area"]
        return n, f"{base:.2f} m2 / {comp['piece_area']} m2 per piece"
    if kind == "per_m_perimeter":
        p = room["perimeter"]
        return p * comp.get("rate", 1.0), f"perimeter {p:.2f} m x {comp.get('rate', 1.0)} (no door deduction)"
    raise ValueError(f"unknown component kind {kind}")


def _match(rule_pattern, name):
    return bool(re.search(rule_pattern, name or "", re.IGNORECASE)) if rule_pattern else True


def assign(config, room, scope):
    """First matching rule for this room and scope -> system id or None."""
    text = f"{room['name']} {room['long_name']}"
    for rule in config["assignments"]:
        if rule["scope"] != scope:
            continue
        if rule.get("exclude") and _match(rule["exclude"], text):
            continue
        if _match(rule.get("room_match"), text):
            return rule.get("system")
    return None


def read_boq_rows(path):
    """Existing BOQ: list of (row number, text of the row). CSV or XLSX."""
    rows = []
    if path.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        ws = load_workbook(path, read_only=True, data_only=True).active
        for i, r in enumerate(ws.iter_rows(values_only=True), start=1):
            text = " | ".join(str(c) for c in r if c not in (None, ""))
            if text:
                rows.append((i, text))
    else:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            for i, r in enumerate(csv.reader(fh), start=1):
                text = " | ".join(c for c in r if c)
                if text:
                    rows.append((i, text))
    return rows


def _has(text, words):
    t = text.lower()
    return any(w.lower() in t for w in words)


def analyze(rooms, config, boq_rows=None):
    """Return dict: scopes, purchase, evidence, missing."""
    systems = config["systems"]
    scopes, evidence, missing = [], [], []
    totals = {}  # (system, comp id) -> dict

    if not rooms:
        missing.append({
            "status": RED, "where": "(model)", "scope": "",
            "ar": "الموديل مفيهوش غرف (IfcSpace). صدّر الغرف من الريفيت مع الـ IFC وشغّل تاني.",
            "en": "The model has no rooms (IfcSpace). Export rooms from Revit with the IFC and run again.",
        })

    room_systems = {}  # room guid -> list of (scope, system id)
    for room in rooms:
        for scope in SCOPES:
            sid = assign(config, room, scope)
            room_systems.setdefault(room["guid"], []).append((scope, sid))
            base, unit, lab_ar, lab_en, note = _base_measure(room, scope)
            where = f"{room['name']} {room['long_name']}".strip() + (f" / {room['storey']}" if room["storey"] else "")
            if not sid or sid not in systems:
                scopes.append({"room": room, "scope": scope, "system": None, "status": RED, "base": base})
                missing.append({
                    "status": RED, "where": where, "scope": scope,
                    "ar": f"{SCOPE_LABEL[scope][0]}: مفيش نظام تشطيب محدد للغرفة دي ({base:.1f} م²).",
                    "en": f"{SCOPE_LABEL[scope][1]}: no finishing system assigned to this room ({base:.1f} m2).",
                })
                continue
            sysdef = systems[sid]
            unapproved = []
            for comp in sysdef["components"]:
                net, formula = _component_net(comp, room, base)
                waste = comp.get("waste", 0.0)
                approved = bool(comp.get("approved", False))
                if not approved:
                    unapproved.append(comp["en"])
                evidence.append({
                    "room": where, "guid": room["guid"], "scope": scope, "system": sysdef["en"],
                    "component_ar": comp["ar"], "component_en": comp["en"],
                    "base_label": lab_en, "base": base, "base_note": note,
                    "formula": formula, "net": net, "unit": comp["unit"], "waste": waste,
                    "source": comp.get("source", ""), "approved": approved,
                })
                t = totals.setdefault((sid, comp["id"]), {"comp": comp, "system": sysdef, "net": 0.0,
                                                          "approved": True, "rooms": 0})
                t["net"] += net
                t["rooms"] += 1
                t["approved"] = t["approved"] and approved
            status = ORANGE if unapproved else GREEN
            scopes.append({"room": room, "scope": scope, "system": sid, "status": status, "base": base})
            if unapproved:
                missing.append({
                    "status": ORANGE, "where": where, "scope": scope,
                    "ar": f"{SCOPE_LABEL[scope][0]}: معدلات غير معتمدة في «{sysdef['ar']}» ({', '.join(unapproved)}). راجعها واعتمدها.",
                    "en": f"{SCOPE_LABEL[scope][1]}: unapproved rates in '{sysdef['en']}' ({', '.join(unapproved)}). Review and approve.",
                })

    # required items per room (e.g. a bathroom needs waterproofing and skirting)
    for req in config.get("required_items", []):
        for room in rooms:
            text = f"{room['name']} {room['long_name']}"
            if not _match(req["room_match"], text):
                continue
            tags = set()
            for scope, sid in room_systems[room["guid"]]:
                if sid in systems:
                    for comp in systems[sid]["components"]:
                        tags.update(comp.get("tags", []))
            for tag in req["tags"]:
                if tag not in tags:
                    where = f"{room['name']} {room['long_name']}".strip()
                    missing.append({
                        "status": RED, "where": where, "scope": "",
                        "ar": f"ناقص بند «{req['labels'][tag][0]}» في هذه الغرفة.",
                        "en": f"Missing item '{req['labels'][tag][1]}' for this room.",
                    })

    # purchase list: waste and packs applied once, on the total
    purchase = []
    for (sid, cid), t in sorted(totals.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        comp = t["comp"]
        gross = t["net"] * (1 + comp.get("waste", 0.0) / 100.0)
        pack = comp.get("pack_size")
        packs = math.ceil(gross / pack - 1e-9) if pack else None
        purchase.append({
            "system_ar": t["system"]["ar"], "system_en": t["system"]["en"],
            "ar": comp["ar"], "en": comp["en"], "unit": comp["unit"], "net": t["net"],
            "waste": comp.get("waste", 0.0), "gross": gross,
            "pack_size": pack, "pack_ar": comp.get("pack_ar", ""), "pack_en": comp.get("pack_en", ""),
            "packs": packs, "approved": t["approved"], "rooms": t["rooms"],
            "status": GREEN if t["approved"] else ORANGE,
        })

    # compare with the user's BOQ: warn about possible double counting, list uncovered systems
    if boq_rows is not None:
        used = {sid for (sid, _c) in totals}
        for sid in sorted(used):
            sysdef = systems[sid]
            hits = [(n, txt) for n, txt in boq_rows if _has(txt, sysdef.get("boq_keywords", []))]
            if not hits:
                missing.append({
                    "status": RED, "where": "BOQ", "scope": "",
                    "ar": f"مفيش بند في المقايسة يغطي «{sysdef['ar']}».",
                    "en": f"No item in your BOQ covers '{sysdef['en']}'.",
                })
                continue
            n, txt = hits[0]
            for comp in sysdef["components"]:
                kws = comp.get("included_keywords")
                if not kws:
                    continue
                if _has(txt, kws):
                    missing.append({
                        "status": ORANGE, "where": f"BOQ row {n}", "scope": "",
                        "ar": f"وصف البند في صف {n} بيذكر «{comp['ar']}» غالبًا داخل السعر. ما تضيفوش لوحده.",
                        "en": f"BOQ row {n} already mentions '{comp['en']}', likely included in its price. Do not add it separately.",
                    })
                else:
                    missing.append({
                        "status": ORANGE, "where": f"BOQ row {n}", "scope": "",
                        "ar": f"المقايسة فيها بند «{sysdef['ar']}» (صف {n}). راجع هل الوصف شامل «{comp['ar']}» قبل إضافته كبند منفصل.",
                        "en": f"Your BOQ has a '{sysdef['en']}' item (row {n}). Check whether its description includes '{comp['en']}' before adding it separately.",
                    })
    return {"scopes": scopes, "purchase": purchase, "evidence": evidence, "missing": missing,
            "rooms": rooms, "boq_checked": boq_rows is not None}


def summary(result):
    counts = {GREEN: 0, ORANGE: 0, RED: 0}
    for s in result["scopes"]:
        counts[s["status"]] += 1
    return counts


def render_plan(result, path, title="MOQAYSA X-RAY"):
    """Plan view of the rooms colored by status. Optional: needs matplotlib."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        def ar(t):
            return get_display(arabic_reshaper.reshape(t))
    except Exception:
        def ar(t):
            return t
    colors = {GREEN: "#2e9e4f", ORANGE: "#f0a030", RED: "#d9453b"}
    rank = {GREEN: 0, ORANGE: 1, RED: 2}
    worst = {}
    for s in result["scopes"]:
        g = s["room"]["guid"]
        if g not in worst or rank[s["status"]] > rank[worst[g]]:
            worst[g] = s["status"]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    for room in result["rooms"]:
        for tri in room["tris"]:
            ax.add_patch(Polygon(tri, closed=True, fc=colors[worst[room["guid"]]], ec="none", lw=0, alpha=0.9))
    for room in result["rooms"]:
        xs = [p[0] for t in room["tris"] for p in t]
        ys = [p[1] for t in room["tris"] for p in t]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        per_scope = {s["scope"]: s["status"] for s in result["scopes"] if s["room"]["guid"] == room["guid"]}
        dots = "  ".join({GREEN: "●", ORANGE: "●", RED: "✖"}[per_scope[k]] + " " + SCOPE_LABEL[k][1][0] for k in SCOPES if k in per_scope)
        ax.text(cx, cy + 0.25, ar(f"{room['name']} {room['long_name']}".strip()), ha="center", va="center",
                fontsize=9, color="white", weight="bold")
        ax.text(cx, cy - 0.25, f"{room['area']:.1f} m²   {dots}", ha="center", va="center", fontsize=8, color="white")
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.axis("off")
    c = summary(result)
    ax.set_title(f"{title}   |   green {c[GREEN]}   orange {c[ORANGE]}   red {c[RED]}   (room x floor/wall/ceiling)", fontsize=11)
    import matplotlib.lines as ml
    ax.legend(handles=[
        ml.Line2D([], [], marker="s", ls="", color=colors[GREEN], label="measured + every rate approved"),
        ml.Line2D([], [], marker="s", ls="", color=colors[ORANGE], label="unapproved example rate / may be in your BOQ"),
        ml.Line2D([], [], marker="s", ls="", color=colors[RED], label="no system or required item missing"),
    ], loc="lower center", ncol=3, frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.04))
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return path
