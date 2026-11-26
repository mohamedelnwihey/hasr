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

## Roadmap

- pyRevit / Revit add-in wrapper (no IFC export step)
- Roof quantities when the exporter gives no quantity set (a few roofs still fail)
- More element coverage (MEP, finishes by room)

## Status

Test suite (16 checks) covers IFC2x3 and IFC4 extraction, unit handling,
classification honesty, duplicate-quantity safety, and an end-to-end run on
the Autodesk `rac_advanced_sample_project` IFC2x3 export (5,415 elements):
door/window counts verified against the file's entity counts, and 410
quantity-less structural elements estimated from geometry. Not yet
battle-tested on live project models — feedback and sample files welcome.

## License

MIT — see [LICENSE](LICENSE). Test sample IFC files are third-party content
and are not redistributed; see [samples/README.md](samples/README.md).
