"""Command-line interface: hasr model.ifc -o boq.xlsx"""

from __future__ import annotations

import argparse
import os
import sys

from .excel import write_boq
from .extract import aggregate, extract, summarize_issues
from .items import UNITS


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="hasr",
        description="Hasr (حصر): extract a bilingual Arabic/English BOQ from an IFC model.",
    )
    parser.add_argument("ifc", help="Path to the IFC file (IFC2x3 or IFC4)")
    parser.add_argument("-o", "--out", default=None, help="Output .xlsx path")
    args = parser.parse_args(argv)

    if not os.path.exists(args.ifc):
        print(f"error: file not found: {args.ifc}", file=sys.stderr)
        return 2

    project_name, schema, unit_note, records = extract(args.ifc)
    lines = aggregate(records)
    unclassified, no_qty, geometry = summarize_issues(records)

    out = args.out or os.path.splitext(os.path.basename(args.ifc))[0] + "-boq.xlsx"
    write_boq(
        project_name, schema, unit_note, records, lines,
        unclassified, no_qty, geometry, out,
        source_name=os.path.basename(args.ifc),
    )

    print(f"project : {project_name or '(unnamed)'}")
    print(f"schema  : {schema}")
    if unit_note:
        print(f"unit    : WARNING {unit_note}")
    print(f"elements: {len(records)} (classified {len(records) - len(unclassified)}, "
          f"unclassified {len(unclassified)}, geometry-estimated {len(geometry)}, "
          f"no-quantity {len(no_qty)})")
    print(f"boq rows: {len(lines)}")
    for (item_ar, item_en, unit_key), stats in sorted(lines.items()):
        unit_ar, unit_en = UNITS.get(unit_key, (unit_key, unit_key))
        shown = round(stats["qty"]) if unit_key == "count" else round(stats["qty"], 3)
        src = f"file:{stats['file_n']} est:{stats['geo_n']} missing:{stats['missing_n']}"
        print(f"  - {item_ar} / {item_en}: {shown} {unit_ar}  [{src}]")
    print(f"saved   : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
