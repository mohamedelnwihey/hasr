"""Command-line interface: hasr model.ifc -o boq.xlsx"""

from __future__ import annotations

import argparse
import os
import sys

from .excel import write_boq
from .extract import aggregate, extract, summarize_issues
from .items import UNITS


def load_prices(path):
    """Read item,price rows. Keys: lowercase English name or Arabic name. Blank prices skipped."""
    import csv

    prices = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            item = (row.get("item") or "").strip()
            raw = (row.get("price") or "").strip().replace(",", "")
            if not item or not raw:
                continue
            try:
                prices[item.lower() if item.isascii() else item] = float(raw)
            except ValueError:
                print(f"warning: bad price for '{item}': {raw!r}", file=sys.stderr)
    return prices


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="hasr",
        description="Hasr (حصر): extract a bilingual Arabic/English BOQ from an IFC model.",
    )
    parser.add_argument("ifc", help="Path to the IFC file (IFC2x3 or IFC4)")
    parser.add_argument("-o", "--out", default=None, help="Output .xlsx path")
    parser.add_argument("--prices", default=None,
                        help="CSV of unit prices: item,price (item = English or Arabic name)")
    parser.add_argument("--prices-template", default=None, metavar="CSV",
                        help="write a blank prices CSV for this model's BOQ items and exit")
    parser.add_argument("--rebar", default=None, metavar="CSV",
                        help="CSV of reinforcement ratios: family,kg_per_m3 (slabs, beams, columns, footings, walls)")
    parser.add_argument("--rebar-template", default=None, metavar="CSV",
                        help="write a blank rebar ratio CSV and exit")
    parser.add_argument("--no-derived", action="store_true",
                        help="skip derived quantities (finishes, formwork, rooms)")
    parser.add_argument("--xray", nargs="?", const="", default=None, metavar="SYSTEMS_JSON",
                        help="X-RAY: finishing systems -> purchase list, evidence, what is missing "
                             "(optional JSON of your own systems; default = unapproved examples)")
    parser.add_argument("--boq-file", default=None, metavar="FILE",
                        help="your existing BOQ (CSV/XLSX) for the X-RAY double-counting check")
    parser.add_argument("--xray-plan", default=None, metavar="PNG",
                        help="write a colored plan of the rooms (needs matplotlib)")
    parser.add_argument("--xray-template", default=None, metavar="JSON",
                        help="copy the example finishing systems to edit, and exit")
    args = parser.parse_args(argv)

    if args.xray_template:
        import shutil

        from .xray import DEFAULT_PATH

        shutil.copyfile(DEFAULT_PATH, args.xray_template)
        print(f"saved example systems: {args.xray_template} (rates are unapproved examples)")
        return 0

    if args.rebar_template:
        from .derived import write_rebar_template

        write_rebar_template(args.rebar_template)
        print(f"saved rebar template: {args.rebar_template}")
        return 0

    if not os.path.exists(args.ifc):
        print(f"error: file not found: {args.ifc}", file=sys.stderr)
        return 2

    project_name, schema, unit_note, records = extract(args.ifc)
    n_source = len(records)
    extras = None
    if not args.no_derived:
        from .derived import derive, load_rebar_ratios

        ratios = load_rebar_ratios(args.rebar) if args.rebar else None
        new_records, extras = derive(args.ifc, records, ratios)
        records = records + new_records
    xres = None
    if args.xray is not None:
        if extras is None:
            print("error: --xray needs derived quantities (remove --no-derived)", file=sys.stderr)
            return 2
        from .xray import analyze, load_systems, read_boq_rows, render_plan, summary

        config = load_systems(args.xray or None)
        boq_rows = read_boq_rows(args.boq_file) if args.boq_file else None
        xres = analyze(extras["rooms"], config, boq_rows)
        extras["xray"] = xres
        if args.xray_plan:
            render_plan(xres, args.xray_plan)
    lines = aggregate(records)
    unclassified, no_qty, geometry = summarize_issues(records)

    if args.prices_template:
        import csv

        with open(args.prices_template, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["item", "unit", "price"])
            for (item_ar, item_en, unit_key), _s in sorted(lines.items()):
                w.writerow([item_en, UNITS.get(unit_key, (unit_key, unit_key))[1], ""])
        print(f"saved prices template: {args.prices_template}")
        return 0

    prices = None
    if args.prices:
        prices = load_prices(args.prices)

    out = args.out or os.path.splitext(os.path.basename(args.ifc))[0] + "-boq.xlsx"
    write_boq(
        project_name, schema, unit_note, records, lines,
        unclassified, no_qty, geometry, out,
        source_name=os.path.basename(args.ifc), prices=prices, extras=extras,
    )

    print(f"project : {project_name or '(unnamed)'}")
    print(f"schema  : {schema}")
    if unit_note:
        print(f"unit    : WARNING {unit_note}")
    print(f"elements: {n_source} (classified {n_source - len(unclassified)}, "
          f"unclassified {len(unclassified)}, geometry-estimated {len(geometry)}, "
          f"no-quantity {len(no_qty)})")
    if extras is not None:
        print(f"derived : {len(records) - n_source} estimated quantity records "
              f"({len(extras['rooms'])} rooms, {len(extras['openings'])} door/window types)")
    print(f"boq rows: {len(lines)}")
    for (item_ar, item_en, unit_key), stats in sorted(lines.items()):
        unit_ar, unit_en = UNITS.get(unit_key, (unit_key, unit_key))
        shown = round(stats["qty"]) if unit_key == "count" else round(stats["qty"], 3)
        src = f"file:{stats['file_n']} est:{stats['geo_n']} missing:{stats['missing_n']}"
        print(f"  - {item_ar} / {item_en}: {shown} {unit_ar}  [{src}]")
    if xres is not None:
        c = summary(xres)
        print(f"x-ray   : {len(extras['rooms'])} rooms, room-scopes green {c['green']} / orange {c['orange']} / red {c['red']}, "
              f"{len(xres['purchase'])} purchase lines, {len(xres['missing'])} findings")
    print(f"saved   : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
