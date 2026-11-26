# Price sources (مصادر الأسعار)

Hasr ships **no prices**. `hasr/price_sources_example.json` ships only *where to look* and *how to read it*. The add-in fetches a source only when `verified` is true and it is due (daily / weekly / monthly), keeps the old price if the page changes, and your own `prices.csv` always wins.

## Status on 2026-11-26

One free public aggregator covers most categories: **QS Mind** (prices.qsmind.app, 745 items, each price dated and linked to its underlying vendor page, `robots.txt` allows crawling, stale rows are flagged). Individual vendors (Ezz, Suez Cement, Scib, Jotun, Knauf, Lecico, Sipes, Cleopatra) were not found to publish their own machine-readable price pages. Their prices reach the market through dealers, so the feed reads the dealer / list price the aggregator reports.

| Item | Vendor named | Online source | Rule verified |
|---|---|---|---|
| Rebar (Ezz, Suez Steel) | Ezz Steel, Suez Steel | QS Mind /steel | yes |
| Cement (Suez, Helwan) | Suez Cement, Helwan Cement | QS Mind /cement | yes |
| Red clay brick, hollow cement block | local plants | QS Mind /bricks | yes (unit is per 1000 / per lot, check the page) |
| Porcelain / ceramic tile 60x60 | Egyptian-made lines (Gemma, Cleopatra, Royal) | QS Mind /finishes | yes |
| Tile adhesive, wall putty | dealers | QS Mind /finishes | yes (pack size, check the page) |
| Interior paint | Scib | QS Mind /paints | yes |
| Exterior paint | Jotun | QS Mind /paints | yes (pack size, check the page) |
| Gypsum board, moisture-resistant board | Knauf / G-Board | QS Mind /finishes | yes |
| Galvanised stud 70 mm | Knauf / roll-formers | QS Mind /gypsum | yes |
| Aluminium sliding window | local fabricators | QS Mind /aluminium | yes |
| Internal door (HDF) | local makers | QS Mind /wood | yes |
| WC set | Lecico | QS Mind /sanitary | yes |
| Ready-mix concrete 300 | ready-mix companies | QS Mind /concrete | yes (row was stale on the check date) |
| Armoured cable | El Sewedy | QS Mind /electrical | yes |

"Rule verified" means: on 2026-11-26 the extraction rule read the same number the page displayed for that row. It does **not** mean the price is right for your job. Each row states its VAT, unit and conditions; confirm them before use.

Other daily sources seen: Arab Finance "Prices Hub" (cement, Ezz rebar; from the Cabinet information centre) and borsaegy.com (cement, rebar, bricks). Not wired in: no stable markup checked.

## Not covered by an online source
Furniture, casework and joinery made to order, lighting and electrical fittings by model, curtain wall, formwork and rebar labour, and anything specific to one brand and model. These need a supplier quotation. Leave them blank in `prices.csv`; they stay outside the total.

## Known limits
- The feed fills BOQ items whose name matches a source `item`. Purchase-list pack prices are not auto-filled yet, because page units (m2, kg, pail) do not always equal the pack.
- Pages can change layout. A failed match keeps the last price and writes a note in the report.
- Please read the site's terms before pointing the fetcher at another site. Default is one request per page per refresh.
