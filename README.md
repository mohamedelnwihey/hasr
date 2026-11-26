# Hasr (حصر)

**Arabic-first, open-source BOQ / quantity takeoff from IFC models.**
**استخراج جدول كميات (مقايسة) عربي من ملفات IFC، مفتوح المصدر.**

Export an IFC file from Revit (or any BIM tool), run one command, and get a
formatted, bilingual Arabic/English bill of quantities in Excel — with an
element-level audit sheet so every number can be traced back to a GUID.

اعمل Export IFC من الريفيت، شغّل أمر واحد، وخد جدول كميات منسّق بالعربي
والإنجليزي في Excel، ومعاه شيت تفاصيل يربط كل رقم بالعنصر اللي طلّعه.

## Why this exists / ليه المشروع ده موجود

Architects and quantity surveyors across Egypt and the Gulf work in Arabic.
In a limited survey of public open-source takeoff projects (late 2026) we
found mostly English-only or inactive repos, while the polished Arabic tools
are paid subscriptions. Hasr aims at that gap: free, open, Arabic-first, and
vendor-neutral (IFC works with Revit, ArchiCAD, and more).

المعماريين وحاسري الكميات في مصر والخليج بيشتغلوا بالعربي. في بحث محدود عن
المشاريع المفتوحة المصدر (أواخر 2026) لقينا أغلبها إنجليزي أو متروك، والأدوات
العربية الجاهزة اشتراكات مدفوعة. حصر بيحاول يسد الفجوة دي: مجاني، مفتوح،
عربي أولاً، وبيشتغل مع أي برنامج بيطلّع IFC.

## Install

```bash
pip install -r requirements.txt
```

Dependencies (installed by pip, not bundled): ifcopenshell (LGPL-3.0-or-later,
used unmodified) and openpyxl (MIT).

## Usage

```bash
python -m hasr model.ifc -o boq.xlsx
```

Output workbook:

- **جدول الكميات** — aggregated BOQ: serial, item (Arabic + English), unit, total quantity. Right-to-left, print-ready.
- **تفاصيل العناصر** — every element: type, name, storey, material, item, quantity, GUID.

## What v0.1 covers

- IFC2x3 and IFC4
- Quantities from `IfcElementQuantity` base quantities (volume, area, length, count)
- Unit handling: per-kind conversion from `IfcUnitAssignment` (e.g. mm lengths
  with m²/m³ areas and volumes, as SketchUp and some Revit exports do)
- Honest classification: IFC type alone never asserts an engineering material —
  labels refine from the model's own material names (stone walls ≠ gypsum walls)
- Doors/windows counted automatically even without quantity sets
- Egyptian/Gulf BOQ item mapping (مباني، خرسانة مسلحة، أبواب، شبابيك، تشطيبات…)
- Nothing hidden: unclassified elements and elements with no quantities are
  flagged in a notes section and a per-element status column — never silently
  dropped from, or summed into, the totals
- Geometry fallback: when an export has no quantity sets (common in Revit IFC
  exports), volumes/areas are estimated from the element geometry via the
  OpenCASCADE engine and labeled "geometry-derived estimate" (تقديرية من المجسم)
  in both sheets, so they are never confused with file quantities

## New in v0.2

- IfcMember and IfcPlate are classified from the model's own material names
  (aluminium mullions, metal sections, glass panels, stone panels). Without a
  material they get a neutral label, never an assumed one.
- IfcCovering is split by its PredefinedType (ceilings, floors, cladding).
  Railings are measured by length.
- Geometry fallback now also estimates member length (longest side of the
  bounding box), panel area (half the surface area, edges ignored) and ceiling
  area. These are estimates and stay labeled "geometry-derived estimate".
  Check them against your own takeoff before relying on them.
- Optional pricing: `python -m hasr model.ifc --prices-template prices.csv`
  writes a blank item list; fill in the `price` column, then
  `python -m hasr model.ifc --prices prices.csv -o boq.xlsx` adds unit price and
  total columns (live Excel formulas) and a grand total. Items with no price are
  left out of the total. Hasr ships no prices; they come from your file.
- Fixed: `python -m hasr` now works as documented.
- Fixed: on some exports (seen on an IFC4 millimetre file) the geometry engine
  returned file units instead of metres, inflating volumes a billion times. Hasr now
  checks each model against the raw sizes of a few elements and rescales, and
  says so in the unit note.
- On the Autodesk `rac_advanced_sample_project` export (5,415 elements),
  unclassified elements dropped from 4,732 to 75.

## New in v0.3 — derived quantities / كميات مشتقة

Beyond what the IFC states, Hasr now estimates the items a quantity surveyor
usually needs. All of them are estimates from the model's own geometry and
materials, labeled "geometry-derived estimate", and listed with their basis in
the "افتراضات الكميات المشتقة" sheet. Turn them off with `--no-derived`.

- Wall faces (both sides, openings removed by the model), plaster (masonry
  walls only) and paint (masonry and gypsum walls).
- Concrete formwork for elements whose own material says concrete (slabs and
  beams: all faces except the top; columns, footings, walls: vertical faces).
- Reinforcement steel in tonnes, only if you give ratios:
  `python -m hasr model.ifc --rebar-template ratios.csv`, fill `kg_per_m3`,
  then `python -m hasr model.ifc --rebar ratios.csv`. Hasr ships no ratios.
- Room finishes from IfcSpace (floor, ceiling, skirting, wall finish) and a room
  schedule sheet. Wall finish is perimeter x height with no door/window
  deduction. Needs rooms in the export (Revit only exports rooms if asked).
- New sheets: quantities per storey (الكميات حسب الدور), door and window
  schedule by type and size (جدول الأبواب والشبابيك), room schedule.
- Derived items flow into the price columns like any other BOQ row.

## New in v0.4 — X-RAY (finishing systems to purchase list) / كشف التشطيبات

`python -m hasr model.ifc --xray [systems.json] [--boq-file my-boq.xlsx] [--xray-plan plan.png]`

Takes the rooms (IfcSpace) of the model, assigns a finishing system per room and
scope (floor, wall, ceiling), and breaks each system into what you actually buy
(tiles, adhesive, grout, skirting, boards, channels, putty, primer, paint ...)
with a declared waste percentage and pack sizes. Three outputs: the engineering
takeoff (the existing sheets), the purchase list, and the findings.

- **Evidence for every number** (sheet "X-RAY دليل الأرقام"): room and GUID, base
  measure, formula, rate, waste, source of the rate, approved or not.
- **What is missing** (sheet "X-RAY إيه اللي ناقص"): green = measured and every
  rate approved by you; orange = an unapproved example rate, or an item your BOQ
  may already include; red = no system for that scope, a required item missing
  (e.g. bathroom without waterproofing), nothing in your BOQ for it, or no rooms.
- **No double counting**: with `--boq-file`, a BOQ row such as "gypsum ceiling
  incl. metal frame" produces "likely included, do not add separately" instead of
  a duplicate frame line.
- `--xray-plan plan.png` draws the rooms colored by status (needs matplotlib).
- **Rates are examples.** `systems_example.json` is a starting point with
  `approved: false` on every rate. Copy it (`--xray-template mine.json`), check each
  value against your spec or the product data sheet, set `approved: true`.
  Until then every purchase number built on it stays orange. Hasr does not vouch
  for them.
- Limits: wall area is perimeter x height with no door/window deduction; ceilings
  are assumed flat and equal to the room area; Revit exports rooms only if you ask.

## Roadmap

- pyRevit / Revit add-in wrapper (no IFC export step)
- Roof quantities when the exporter gives no quantity set (a few roofs still fail)
- More element coverage (MEP, finishes by room)

## Status

Test suite (31 checks, 15 of them on a small in-memory IFC with hand-computed answers) covers IFC2x3 and IFC4 extraction, unit handling,
classification honesty, duplicate-quantity safety, and an end-to-end run on
the Autodesk `rac_advanced_sample_project` IFC2x3 export (5,415 elements):
door/window counts verified against the file's entity counts, and 410
quantity-less structural elements estimated from geometry. Not yet
battle-tested on live project models — feedback and sample files welcome.

## License

MIT — see [LICENSE](LICENSE). Test sample IFC files are third-party content
and are not redistributed; see [samples/README.md](samples/README.md).

## v0.5: مقايسة (Moqayasa), the Revit add-in, merged into Hasr

Hasr (takeoff) and the cost estimate are now one tool, **مقايسة**, in `revit/Moqayasa/`. One click on **Run** in Revit collects the model (architectural and structural elements, rooms, finish materials), takes off the quantities, checks what is missing (green / orange / red), builds the purchase list with waste, and writes an Excel workbook and an Arabic RTL HTML report.

- Revit 2022 to 2027, one source tree, one build per year (.NET Framework 4.8 for 2022-2024, .NET 8 for 2025-2026, .NET 10 for 2027). All six compile against each year's API. **Not yet run inside Revit.**
- Prices: none shipped. Rates in `hasr/systems_example.json` are unapproved examples. The price feed (`hasr/price_sources_example.json`, see `revit/Moqayasa/PRICE_SOURCES.md`) reads dated market prices from a public source and your `prices.csv` always wins.
- 49 checks for the C# core (`dotnet run --project revit/Moqayasa/Tests`), 31 for the Python side.
- No secrets in this repo.
