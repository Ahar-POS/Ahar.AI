# ADR-006: Data Foundation Strategy — Real + Synthetic Data for Demo

**Date**: 2026-04-15
**Status**: Accepted
**Decider**: Voj
**Context**: The demo data situation was broken — only Dec 2025 real data, corrupted synthetic data, and garbage recipe BOMs — requiring a complete rebuild of the data pipeline.

---

## Problem

Ahar.AI demos required a believable, continuous dataset spanning several months. The existing state had three failure modes:

1. **Real data gap**: Only December 2025 POS export existed; Jan–Mar 2026 had no real orders.
2. **Corrupted synthetic data**: Previous synthetic orders did not match realistic restaurant patterns (hourly distribution, weekday variation, item frequency).
3. **Unusable recipe BOMs**: BOMs were manually authored for a small subset of items; the remaining 400+ menu items had no ingredient mappings, breaking inventory depletion logic.

---

## Decisions Made

### Decision 1: Authoritative real data source

- **Chosen**: Anterra's Kitchen POS export (`Restaurant_Data.xlsx`, single sheet, 213,537 rows) covering Dec 1, 2025 – Mar 29, 2026. After deduplication: 48,915 unique orders.
- **Rejected**: Fabricating all historical data synthetically.
- **Reason**: Real POS data gives authentic item mix, pricing, and order patterns. Using real data as the anchor makes the demo credible and prevents pattern drift.

### Decision 2: Invoice deduplication — composite key fix

- **Chosen**: Group by composite key `(date, invoice_no)` instead of `invoice_no` alone. Order numbers reassigned as sequential integers sorted by timestamp.
- **Rejected**: Trusting `invoice_no` as a globally unique identifier.
- **Reason**: The xlsx resets invoice numbers each month. Grouping by invoice number alone caused cross-month collisions (e.g., invoice #1 in January collapsing with invoice #1 in December), inflating item counts per order and creating phantom "mega-orders".

### Decision 3: Synthetic data covers gap period only

- **Chosen**: Synthetic orders generated only for Mar 30 – Apr 14, 2026 (and forward). Patterns derived from real Dec 2025 data: hourly distribution weights, weekday volume variation, top-30 item frequency weights. Remaining 414 items get long-tail weights.
- **Rejected**: Regenerating all historical data synthetically; extending synthetic data far back into past months.
- **Reason**: Synthetic data should supplement, not replace, real data. Anchoring synthetic patterns to real Dec 2025 observations ensures consistency across the dataset.

### Decision 4: Daily simulation script for keeping dataset current

- **Chosen**: `simulate_daily_orders.py` run manually each morning to generate the previous day's synthetic orders. Idempotent — skips if orders already exist for that date.
- **Rejected**: Automated cron job; regenerating the full synthetic window on each run.
- **Reason**: Manual invocation avoids unintended data generation during debugging. Idempotency prevents duplicate records if the script is run more than once.

### Decision 5: Category-based BOM generation for all 444 menu items

- **Chosen**: `generate_recipe_bom.py` auto-generates BOM rows using category → ingredient set templates, with name-keyword overrides for protein type (chicken / mutton / prawn / fish). Result: 1,972 ingredient rows (avg 4.4 per item).
- **Rejected**: Manual BOM authoring per item; leaving non-covered items without BOMs.
- **Reason**: 444 items makes manual authoring impractical. Category templates produce structurally correct BOMs fast enough for demo purposes; accuracy is sufficient because demos are not used for real procurement decisions.

### Decision 6: RM049 — Alcohol/Spirits Generic as single abstracted SKU

- **Chosen**: All alcohol items (detected by name keywords: `ml`, `btl`, `bottle`, `beer`, `wine`, etc.) map to raw material RM049 (Alcohol/Spirits Generic, 1 Portion). Supplier: SUP004 (placeholder).
- **Rejected**: Creating individual raw material SKUs per alcoholic beverage.
- **Reason**: Per-SKU alcohol inventory is unnecessary overhead for the demo. A single abstracted unit lets stock depletion logic function without maintaining a full alcohol catalogue.
- **Update (2026-04-28)**: 120 alcohol/tobacco items were subsequently deleted from `menu_items`, `recipe_bom`, and `orders` via `remove_alcohol_from_mongo.py` to align the database with the v9 forecasting model scope (see ADR-001). RM049 remains in `raw_materials` for cost accounting but is no longer linked to any `menu_items` BOM.

### Decision 7: Stock movement recording strategy

- **Chosen**: Per-order stock consumption recorded in `stock_movement_log` by looking up `recipe_bom` for each ordered item. Items with no BOM entry are silently skipped. SALE type for consumption; WASTE type for daily waste estimate (~4% of revenue).
- **Rejected**: Blocking order seeding on missing BOMs; raising errors for unmapped items.
- **Reason**: Silent skipping keeps the seed pipeline robust against partial BOM coverage. The 4% waste estimate is a standard industry heuristic suitable for demo data.

---

## Decisions Rejected / Deferred

- **Per-SKU alcohol inventory tracking**: Deferred indefinitely for demo context. Should be revisited for real restaurant onboarding.
- **Automated daily cron for simulate_daily_orders.py**: Deferred. Manual invocation is sufficient until a staging environment is established.
- **BOM accuracy validation against real recipes**: Deferred. Category templates are good enough for demos; a validation pass against real kitchen recipes is needed before production use.

---

## Known Limitations

1. Invoice numbers in the source xlsx are month-scoped, not globally unique. The composite key fix handles this, but any future POS exports must be checked for the same pattern.
2. Synthetic data patterns are derived from Dec 2025 only. December may be atypical (holiday season). If seasonal bias is visible in demos, consider averaging patterns across multiple real months.
3. RM049 abstracts all alcohol. Stock-level reports for the bar will show a single "Alcohol/Spirits Generic" line, which is not useful for real bar management.
4. The ~4% waste estimate is hardcoded. Real waste rates vary by category and day.
5. BOM ingredient quantities are template-derived, not measured. COGS calculations from these BOMs will have systematic errors against actual kitchen costs.

---

## Output / Affected Files

| File | Change |
|---|---|
| `backend/new_test_data/generate_antera_csvs.py` | Fixed composite key grouping `(date, invoice_no)` |
| `backend/new_test_data/seed_mar_apr_2026.py` | New — synthetic seed script for gap period |
| `backend/new_test_data/simulate_daily_orders.py` | New — idempotent daily runner |
| `backend/new_test_data/generate_recipe_bom.py` | New — category-based BOM generator |
| `backend/new_test_data/_shared_patterns.py` | New — shared helpers (hourly weights, weekday variation) |
| `backend/new_test_data/recipe_bom.csv` | Replaced — 1,972 generated rows for 444 items |
| `backend/new_test_data/raw_material_inventory.csv` | Added RM049 (Alcohol/Spirits Generic) |

---

## Next Decisions Pending

1. **Seasonal pattern correction**: Should synthetic data use an average of real Dec + Jan + Feb patterns once those exports are available, rather than Dec alone?
2. **BOM validation pass**: When does the category-template BOM get replaced with real kitchen recipes? What is the trigger (first real restaurant onboarding)?
3. **Automated daily data pipeline**: Should `simulate_daily_orders.py` be scheduled in the staging environment, and who owns triggering it?
4. **Alcohol inventory granularity**: What is the right cutoff for switching from RM049 (abstracted) to per-SKU tracking — demo only, or also first-customer staging?
