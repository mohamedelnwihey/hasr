# مقايسة (Moqayasa) — Revit add-in, part of Hasr

ضغطة واحدة على **تشغيل** تجمع الموديل كله، وتحصر الكميات، وتطلّع ملف Excel وتقرير HTML.
One click on **Run** collects the model, takes off quantities, and writes an Excel workbook and an HTML report.

## What it covers
- Architectural: walls, curtain walls, doors, windows, floors, ceilings, roofs, stairs, ramps, railings, columns.
- Structural: columns, framing, foundations, rebar (length, weight), formwork area derived from solid faces.
- Furniture and joinery, plumbing / lighting / electrical fixtures, generic models.
- Finishes from the model's own materials: paint, gypsum, plaster, tile, stone, wood (Revit material takeoff, painted and layered).
- Finishing systems per room (floor, walls, ceiling) to a purchase list with waste and packs, a "what's missing" check (green / orange / red), and evidence per number.

## Revit versions
One source tree, one build per year (`build.sh` / `build.ps1`):

| Revit | Target | Status |
|---|---|---|
| 2022, 2023, 2024 | .NET Framework 4.8 | compiles against that year's API, not run in Revit |
| 2025, 2026 | .NET 8 | compiles against that year's API, not run in Revit |
| 2027 | .NET 10 | compiles against that year's API, not run in Revit |

The tests (`dotnet run --project Tests`) run the Core on plain .NET. **Nobody has run the add-in inside Revit yet.** Try it on a copy of a project first.

## Install
Run `install.ps1` from the folder containing `R2022 … R2027` (right-click, Run with PowerShell). It installs only for Revit years that are really installed and prints which. `install.ps1 -Uninstall` removes it. No SDK or download needed; restart Revit and open the **مقايسة** tab.
Reports go to `Documents\Moqayasa`. Your editable files are in `%APPDATA%\Moqayasa`: `prices.csv`, `systems.json`, `price_sources.json`.

## Prices
The tool ships **no prices**. All rates in `systems.json` are examples marked `approved: false` and show orange until you approve them.
Prices come from your `prices.csv` (always wins) or from `price_sources.json`: a per-item feed (vendor, page, extraction rule, unit factor, refresh daily / weekly / monthly).
A source is fetched only when `verified` is true, meaning a person opened the page and checked the rule reads the right number. See `PRICE_SOURCES.md`.

## Limits
- Wall paint and plaster areas come from Revit materials. If walls have no finish material or paint, nothing is invented: the check shows it.
- Formwork from faces is an estimate, marked unverified. Rebar weight = modelled bar volume x 7850 kg/m3.
- Linked models are not read in this version.
