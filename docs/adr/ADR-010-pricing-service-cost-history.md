# ADR-010: Pricing Service — Single Source of Truth for Ingredient Costs

**Date**: 2026-05-04
**Status**: Accepted
**Decider**: Pandiarajan
**Context**: Cross-cutting price resolution — every backend service that computes food cost, P&L, or shopping list value must read ingredient prices from one place

---

## Problem

Multiple backend services (chatbot P&L skill, profit analysis, inventory agent, dashboard, shopping list) each fetched ingredient prices independently from `raw_material_inventory.unit_cost_inr`. This created three failure modes:

1. **Stale costs**: `unit_cost_inr` was set at seed time and never updated. When a supplier raised prices, the chatbot and profit analysis continued using the old number.
2. **Cross-surface inconsistency**: The same ingredient could show a different cost in the P&L Snapshot panel vs the chatbot vs the shopping list, because each service read from a slightly different field or used a different fallback.
3. **No price history**: There was no way to ask "what did chicken breast cost in January?" — historical P&L accuracy required the price at time-of-sale, not today's price applied retroactively.

---

## Decisions Made

### Decision: Centralise all price reads through `PricingService` singleton

- **Chosen**: New `pricing_service.py` exposes four public async functions (`get_current_price`, `get_current_price_info`, `get_price_at`, `get_price_at_info`). Every service that needs ingredient prices calls this module. No service reads `raw_material_inventory.unit_cost_inr` directly for cost computation.
- **Rejected**: Continuing direct reads from `raw_material_inventory` — the field is a single scalar with no history and no source attribution.
- **Reason**: A single resolution point guarantees all surfaces show the same number. It also lets the resolution logic change (e.g. switch from HyperPure mock to live API) in one place without touching every consumer.

---

### Decision: Three-tier resolution chain with explicit priority

- **Chosen**: Price resolution falls through three tiers in order:
  1. **`cost_history` collection** (most recent entry for the material) — authoritative; populated by OCR bill scans, manual price edits, and future supplier API feeds.
  2. **HyperPure mock catalogue** — fallback for materials not yet in cost history; uses the static price catalogue from `hyperpure_client.py`.
  3. **Legacy `unit_cost_inr` field** — deprecated path; kept while remaining consumers are migrated. Tagged `source: "inventory_cache"` in the returned dict so callers can identify stale data.
- **Rejected**: Skipping the legacy fallback entirely at launch — too many consumers still depend on `unit_cost_inr`; a hard cut would break profit analysis and the chatbot before migration is complete.
- **Reason**: The tiered design lets the team migrate incrementally. Once all materials have `cost_history` entries, tiers 2 and 3 become dead code and can be removed.

---

### Decision: `cost_history` collection as the price ledger

- **Chosen**: New `cost_history` collection. Each document: `material_id`, `price_paise_per_base`, `base_unit`, `source` (who recorded it: `ocr_bill`, `manual`, `hyperpure_import`), `effective_date`, optional `metadata`. Append-only — prices are never updated in place; new entries are inserted with a new `effective_date`. `get_price_at(material_id, as_of)` queries for the latest entry with `effective_date ≤ as_of`.
- **Rejected**: Storing price history as an embedded array on the `raw_material_inventory` document — unbounded array growth on a hot document; harder to query across materials for a given date.
- **Reason**: A separate collection with an indexed `(material_id, effective_date)` compound key makes point-in-time queries O(log n) and keeps the inventory document lean.

---

### Decision: 60-second in-process TTL cache per material

- **Chosen**: `PricingService` maintains a dict keyed by `material_id` with monotonic expiry timestamps. Cache is invalidated immediately when `record_price` is called for that material. TTL is 60 seconds.
- **Rejected**: No cache — the inventory agent and dashboard both fan out over hundreds of materials in a single request; a cold MongoDB round-trip per material would make those endpoints unacceptably slow.
- **Rejected**: Redis — over-engineered for a single-process server. The in-process cache is sufficient until horizontal scaling is needed.
- **Reason**: 60 seconds is short enough that a price update is visible within one minute, but long enough to absorb the burst reads from a single dashboard or agent run.

---

### Decision: `record_price` called by OCR bill processor on document approval

- **Chosen**: When an OCR-reviewed bill is approved, `document_processor.py` calls `pricing_service.record_price(material_id, price_paise, source="ocr_bill", effective_date=bill_date)` for each line item. This automatically updates the price ledger with supplier-confirmed prices.
- **Rejected**: Requiring a separate manual price-update step after bill approval — operators won't do it; the OCR flow is the only moment the system has a confirmed price with a date.
- **Reason**: Bill approval is the point of highest confidence for a price: the store keeper has reviewed the OCR extraction and confirmed the numbers. Capturing it here requires zero additional operator action.

---

## Decisions Rejected / Deferred

### Deferred: Live HyperPure API integration replacing mock catalogue
- **Reason**: HyperPure doesn't expose a public pricing API. The mock catalogue covers the demo; live prices would require a supplier data feed agreement.

### Deferred: Multi-supplier price comparison
- **Reason**: First iteration assumes one primary supplier (HyperPure). When a second supplier is onboarded, `cost_history` already stores `source` so per-supplier price tracking is additive.

### Deferred: Remove legacy `inventory_cache` fallback
- **Condition**: Once all `raw_material_inventory` items have at least one `cost_history` entry, tier 3 can be deleted. Track migration progress via `db.cost_history.distinct("material_id").length vs db.raw_material_inventory.countDocuments()`.

---

## Known Limitations

| Issue | Impact | Path forward |
|---|---|---|
| Unit normalisation is heuristic | `_normalize_unit` maps common variants; unusual units silently fall through as-is | Extend the normalisation map as new suppliers are added |
| Cache is per-process | In a multi-worker deployment, each worker has its own cache — a price update invalidates only the worker that called `record_price` | Acceptable at single-worker scale; migrate to Redis cache when horizontally scaling |
| `base_unit` inference can fail | If a new material has no `cost_history`, no HyperPure entry, and no `unit` field in inventory, `record_price` raises `ValueError` requiring explicit `base_unit` | Callers from OCR processor always have the unit from the bill line item; only edge case is programmatic inserts |

---

## Output / Affected Files

| File | What changed or was created |
|---|---|
| `backend/app/services/pricing_service.py` | **New file**. `PricingService` class + `get_pricing_service()` singleton factory. |
| `backend/app/repositories/cost_history_repository.py` | **New file**. `insert`, `get_current`, `get_price_at` for the `cost_history` collection. |
| `backend/app/services/document_processor.py` | Modified — calls `record_price` for each line item when an OCR bill is approved. |

---

## Next Decisions Pending

1. **Migration completion gate** — define the query to measure what % of active materials have `cost_history` entries; set a target date to drop the legacy fallback.
2. **Price change notifications** — should agents and the dashboard alert the owner when an ingredient's cost jumps by more than X% vs the previous entry? Useful for catching supplier price hikes before they erode margin.
3. **Supplier-level price tracking** — when the second supplier onboards, `cost_history.source` can encode the supplier ID; `get_current_price` could then accept an optional `prefer_supplier` param to return that supplier's latest price for comparison.
