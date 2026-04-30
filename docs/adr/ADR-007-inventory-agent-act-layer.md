# ADR-007: Inventory Agent — Act Layer Design

**Date**: 2026-04-16
**Status**: Accepted
**Decider**: Voj + team
**Context**: Completing the Inventory Agent's Observe → Reason → Act loop for the first restaurant onboarding (Hyperpure-only MVP).

---

## Problem

The Inventory Agent's Observe and Reason layers were solid — stock observation, 7-day demand forecast, safety stock math, urgency tiers. The Act layer was entirely missing: no way to place orders on Hyperpure, no single shopping list for the owner to see, no delivery receiving, no duplicate order guard. The gap meant the agent could reason correctly but couldn't take any real action.

---

## Decisions Made

### Decision: Remove LLM from Inventory Agent execution loop (2026-04-28)

- **Chosen**: `InventoryAgent.execute()` is overridden to call `_get_inventory_status` → `_get_demand_forecasts` → `_calculate_reorder_needs` → `_parse_agent_response` directly, bypassing `BaseAgent._run_agent_loop` entirely. No Claude API call is made during inventory agent runs.
- **Rejected**: Keeping Claude as an orchestrator for tool sequencing.
- **Reason**: Code audit showed that `_parse_agent_response` was ignoring Claude's text output entirely and reading directly from `tool_results["calculate_reorder_needs"]`. Claude was acting purely as a tool-call sequencer with no influence on the math. Removing it eliminates API latency, token cost, and the failure mode of Claude hallucinating or reordering tool calls. The three tools are always called in the same fixed order — no orchestration intelligence was needed. Other agents (`FinancialAgent`, `StrategicAnalysisAgent`) retain the LLM loop.

### Decision: Compute demand σ from actual 7-day daily breakdown (2026-04-28)

- **Chosen**: `statistics.stdev(daily_values)` computed from `forecast["daily_breakdown"]` replaces the hardcoded `daily_demand * 0.25` CV assumption. Falls back to 0.25 CV only when no breakdown is available (forecast cache miss).
- **Rejected**: Keeping 0.25 as a permanent coefficient.
- **Reason**: The 7-day `daily_breakdown` was already being fetched and passed through the forecast object but was unused in safety stock math. Using actual variance makes safety stock respond to real demand volatility — a smooth item gets less buffer, a spiky item gets more. The 0.25 constant was systematically under-buffering spiky items and over-buffering stable ones.

### Decision: Model-based σ multipliers replace LLM prompt guidance (2026-04-28)

- **Chosen**: After computing σ from daily breakdown, the agent multiplies by a confidence factor based on `forecast_model`: `fallback` → ×1.40, `hybrid_abc_v7_C` → ×1.30, `hybrid_abc_v7_B` → ×1.10. High-confidence models (`v7_A`, `prophet`) use σ as-is.
- **Rejected**: Leaving this as a Claude system prompt instruction (previous approach).
- **Reason**: The system prompt told Claude to widen safety buffers by model type, but since Claude's text was never used, this guidance was silently dead. Moving it into explicit code makes it auditable, testable, and actually effective.

### Decision: Shelf life caps order quantity for perishables (2026-04-28)

- **Chosen**: `compute_order_quantity()` now accepts `shelf_life_days`. For perishable items, the order cap uses `min(shelf_life_days, restock_horizon_days)` instead of always `restock_horizon_days`.
- **Rejected**: Relying solely on `restock_horizon_days` for perishable capping.
- **Reason**: Cocktail mocktail mixes had `shelf_life=1` day but `restock_horizon=30` days (Cocktails category). Without this fix the agent would order 30 days of stock that expires in 1 day. The shelf life cap prevents waste orders for any item where shelf life is shorter than the purchase frequency window. For the majority of categories (Proteins, Seafood, Dairy, Vegetables) the restock horizon is already 1–2 days, so no change in practice — the fix only materially affects Cocktails and some Condiments.

### Decision: `is_perishable` normalised to bool at read site (2026-04-28)

- **Chosen**: `is_perishable = str(item.get("is_perishable", "No")).strip().lower() == "yes"` converts the MongoDB `"Yes"/"No"` string to a Python bool once, at the start of item processing. All downstream comparisons use the bool.
- **Rejected**: Leaving string comparisons scattered through `_classify_urgency` and `_build_urgency_reason`.
- **Reason**: Python treats any non-empty string as truthy, so `"No"` was evaluating as `True`. Every item was being classified as perishable — hitting the perishable urgency tier and the perishable order cap incorrectly. Non-perishable groceries with months of runway were generating STANDARD urgency flags daily.

### Decision: `expiry_date` added to `InventoryItem` Pydantic model (2026-04-28)

- **Chosen**: `expiry_date: Optional[datetime]` added to `InventoryItem` and `InventoryItemResponse`. This is a per-batch field (set when a delivery is received) distinct from `shelf_life_days` (a per-material property).
- **Rejected**: Leaving `expiry_date` as an unmodelled MongoDB field.
- **Reason**: `inventory_repository.get_expiring_soon()` was querying on `expiry_date` but the field was absent from the Pydantic schema — a silent schema mismatch. The field is populated via the confirm-delivery flow (ADR-007 delivery receiving decision). `shelf_life_days` informs how much to order; `expiry_date` informs when existing stock expires.

### Decision: Single Rolling Shopping List (upsert model)

- **Chosen**: One active shopping list per restaurant at all times. The Inventory Agent upserts into this list on every run — updating quantities and urgency for pending items, leaving owner-approved/ordered/delivered items untouched. When the owner approves items, they become a Purchase Order.
- **Rejected**: Creating a new shopping list (PO) on every agent run.
- **Reason**: Multiple POs per day would overwhelm the owner with decisions and create confusion about which PO is current. A live rolling list matches how a restaurant owner actually thinks — "what do I need to buy today?" — and follows Nielsen's Heuristic of matching the system to the real world.

### Decision: Item-level status lifecycle on the shopping list

- **Chosen**: Items in the shopping list track their own status independently: `pending_review → auto_approved | owner_approved | owner_rejected → ordered → delivered`. The list-level status reflects the aggregate.
- **Rejected**: Treating the shopping list as an atomic approve/reject unit.
- **Reason**: Owners routinely approve some items and defer or reject others in a single review session. Item-level granularity prevents blocking an entire order because one item is uncertain.

### Decision: Hyperpure via abstract Python interface (browser automation, mock-first)

- **Chosen**: `HyperpureClient` abstract class with a `MockHyperpureClient` now and `PlaywrightHyperpureClient` swapped in later. Mock mode controlled by `HYPERPURE_MOCK_MODE` env var (full / partial / rejected / error).
- **Rejected**: Direct Playwright calls from the orchestrator; REST API integration (Hyperpure has no public API).
- **Reason**: No public Hyperpure API exists — all integration must be browser automation. Abstracting behind an interface means the orchestrator code never changes when the mock is replaced by real Playwright. The mock enables full end-to-end testing of the approval and ordering flow before the automation is built.

### Decision: LLM-based auto-approval with pre- and post-guardrail sandwiching

- **Chosen**: `_reason_about_approvals()` uses a three-stage pattern: (1) deterministic pre-guardrail flags items for forced escalation (price anomaly >configured multiplier × baseline, qty spike >3× reorder qty); (2) single Claude API call classifies each remaining item as `auto_approve | escalate | defer` with a one-sentence reason; (3) post-guardrail enforces a hard total budget cap (cheapest items first, surplus moved to escalate). Force-escalate overrides LLM decisions unconditionally.
- **Rejected**: Pure rules-based escalation; pure LLM decision with no guardrails.
- **Reason**: Rules alone can't handle nuanced trade-offs (e.g. URGENT item at normal price vs STANDARD item with slight price uptick). LLM alone is unauditable and could auto-approve anomalous spends. The sandwich pattern gets the best of both: guardrails handle the clear-cut dangerous cases deterministically, LLM handles the judgment calls in between, and the budget cap prevents runaway spend regardless of LLM output.

### Decision: Hyperpure price queried before LLM reasoning (2026-04-29)

- **Chosen**: Before building the LLM prompt in `_reason_about_approvals()`, the agent calls `await hyperpure_client.get_prices(items)` to fetch current Hyperpure catalogue prices. Each item in the LLM context now includes `hyperpure_price_rupees` and `price_delta_pct` (deviation from historical baseline). The system prompt instructs the LLM: if `price_delta_pct > 20%`, lean toward escalate; if within ±10%, treat price as normal.
- **Rejected**: Fetching prices only at order time (post-approval); showing price in UI only without feeding it to the LLM.
- **Reason**: Price at the moment of order is the most actionable signal for whether to auto-approve. If a supplier has spiked prices 40% above baseline, that information should change the LLM's classification — not just appear in the owner's approval screen after the fact. Fetching before the LLM call costs one extra async call but eliminates a class of bad auto-approvals where the price anomaly wasn't visible to the reasoning layer.

### Decision: Mock Hyperpure price table seeded with real Indian wholesale prices + ±10% variance (2026-04-29)

- **Chosen**: `MockHyperpureClient._MOCK_PRICES` contains ~60 common Indian restaurant ingredients with prices sourced from typical Hyperpure/mandi wholesale rates (e.g. tomato ₹38/kg, paneer ₹310/kg, chicken ₹225/kg, basmati rice ₹95/kg). `get_prices()` applies ±10% random variance per call to simulate live price fluctuation. Fuzzy name matching handles partial name matches (e.g. "coriander leaves" → "coriander").
- **Rejected**: Keeping the mock without a price table; using arbitrary placeholder values.
- **Reason**: The price-in-LLM-flow logic is meaningless if mock prices are unrealistic. With real wholesale prices, the `price_delta_pct` computation against historical baselines (from `purchase_history` collection) produces meaningful signals — e.g. a spike month for tomatoes will genuinely trigger escalation in the mock environment. The ±10% variance tests that the price delta guardrail fires at the right threshold, not just on exact boundary values.

### Decision: Notification bell messages slimmed to single-sentence headings (2026-04-29)

- **Chosen**: `_notify_owner_shopping_update()` now emits one short sentence per notification (e.g. *"Shopping list created at 6:00 AM with 26 items. 3 auto-ordered, 23 need review — check Dashboard."*). Order placement notifications similarly trimmed (e.g. *"Order HP-MOCK-232444 placed — 3 items. Check Hyperpure Orders for status."*). Detailed per-item reasoning is no longer included in notification message bodies.
- **Rejected**: Keeping verbose notifications that list every item, reason, and cost breakdown inline.
- **Reason**: The notification bell is a signalling layer, not a review surface. An owner scanning 5–10 notifications in a bell dropdown needs to quickly understand *what happened* and *whether action is needed* — not read a wall of item details. Per-item LLM reasoning is now surfaced in the Shopping List Modal (ADR-008) where the owner is actively reviewing, not passively skimming alerts.

### Decision: Auto-approve triggers immediate Hyperpure order placement

- **Chosen**: When the orchestrator auto-approves a shopping list (all 4 auto-approve gates pass), it immediately calls `execute_approved_order()` which places the Hyperpure order in the same flow.
- **Rejected**: Auto-approve only sets list status, leaving order placement to a separate scheduled job.
- **Reason**: URGENT items that qualify for auto-approval need to be ordered immediately. Introducing a second scheduling step adds latency for no benefit. Manual approvals fire `execute_approved_order()` as a background task (non-blocking) via `asyncio.create_task`.

### Decision: Duplicate order guard in execute_approved_order

- **Chosen**: Before calling Hyperpure, filter out any items with `item_status` in `{ordered, delivered}`. Only items in `{auto_approved, owner_approved, approved}` and NOT already in a locked state are sent.
- **Rejected**: Trusting the caller to never call `execute_approved_order` twice.
- **Reason**: Background tasks, retries, and the rolling-list model all create opportunities for the same item to be ordered twice. The guard is cheap and prevents a real operational problem.

### Decision: Hyperpure outcome → 4-path handling with owner notifications

- **Chosen**: confirmed → mark all items `ordered`, notify owner; partial → mark confirmed items `ordered`, notify owner of shortfall; rejected → park PO, high-severity alert to admin; error → park PO, high-severity alert to admin with "order manually" instruction.
- **Rejected**: Treating partial and rejected as equivalent failure states.
- **Reason**: A partial order still delivers real value — the restaurant gets most of what it needs. Conflating partial with rejected would suppress useful information and cause unnecessary manual re-ordering.

### Decision: Write a `purchase_orders` document on every confirmed or partial Hyperpure order (2026-04-29)

- **Chosen**: `execute_approved_order()` now inserts a raw document into the `purchase_orders` collection (via `PurchaseOrderRepository.create()`) immediately after placing a confirmed or partial order. Fields: `po_number` (Hyperpure ref), `source: "hyperpure"`, `supplier_id: "hyperpure"`, `supplier_name: "Hyperpure"`, `shopping_list_id`, `status: "pending"`, per-item line details, `total_cost_inr`, `ordered_at`. Existing `mark_items_ordered()` still updates item-level status inside the shopping list document — that is unchanged.
- **Rejected**: Relying solely on item-level `po_id` inside the shopping list document; using the existing Pydantic `PurchaseOrder` model (which requires `document_upload_id` and `ocr_result_id` — fields only meaningful for OCR-created POs).
- **Reason**: Item-level `po_id` inside the shopping list served as an internal reference but provided no queryable PO surface. The Hyperpure Orders tracking page needs to `find({source: "hyperpure"})` and show order status without joining through the shopping list. Writing a proper PO document decouples order tracking from the shopping list lifecycle. Using a raw dict (not the Pydantic model) avoids polluting OCR-specific mandatory fields into a programmatically-created record.

### Decision: Mock delivery simulation — 60s sleep → inventory update → PO status to `fully_received` (2026-04-29)

- **Chosen**: After a confirmed or partial Hyperpure order (mock mode only), `execute_approved_order()` schedules `_mock_deliver_after_delay()` as a non-blocking `asyncio.create_task`. That coroutine: (1) sleeps 60 seconds, (2) calls `service.mark_items_delivered()` to set `item_status: "delivered"` on confirmed items, (3) calls `inv_service.add_stock(material_id, quantity)` for each delivered item, (4) calls `po_repo.update()` to set `status: "fully_received"` and `delivered_at: now` on the corresponding PO document, (5) fires an "Order delivered" notification. Gated on `HYPERPURE_USE_MOCK != "false"` so real Playwright mode is unaffected.
- **Rejected**: Manual delivery confirmation only (was `POST /confirm-delivery`); a separate cron job that polls order status; setting `delivered_at` on the shopping list instead of on the PO.
- **Reason**: The manual confirm-delivery endpoint remains for staff-initiated confirmation, but in mock mode the owner needs to see the full loop — order → delivered → inventory updated — without a staff member manually confirming. 60 seconds is fast enough to demonstrate the loop in a demo without being instant (which would obscure the pending→delivered transition on the Hyperpure Orders page). Setting `delivered_at` on the PO document (not the shopping list) keeps delivery metadata co-located with order metadata where it will be queried.

### Decision: `source: "hyperpure"` tag on Hyperpure-placed POs to distinguish from OCR POs (2026-04-29)

- **Chosen**: All PO documents created by `execute_approved_order()` include `"source": "hyperpure"`. The `GET /approvals/hyperpure-orders` endpoint queries `{"source": "hyperpure"}`. OCR-created POs (created by `POST /api/v1/approvals/purchase-orders` or similar document-upload flow) do not include this field.
- **Rejected**: A separate collection for Hyperpure POs; a boolean `is_hyperpure` field; using `supplier_id: "hyperpure"` as the discriminator.
- **Reason**: Using `source` as the discriminator is semantically cleaner than `supplier_id` (which implies the vendor, not the origination channel). A future where the same Hyperpure supplier has both OCR-uploaded invoices and programmatically-placed orders would break if `supplier_id` were the filter. Separate collections would require separate indexes, repos, and API surface without any benefit at current scale.

### Decision: Delivery receiving endpoint updates inventory directly

- **Chosen**: `POST /api/v1/approvals/{list_id}/confirm-delivery` marks items `delivered` and calls `inventory_service.add_stock()` to increment `raw_material_inventory.current_stock` with an audit log entry.
- **Rejected**: Requiring OCR bill scan before inventory is updated (OCR already exists but is a separate flow).
- **Reason**: Staff needs to be able to confirm a delivery even if OCR fails or is bypassed. OCR bill matching (price discrepancy detection) remains a P1 overlay on top of this baseline — it doesn't block the delivery loop.

---

## Decisions Rejected / Deferred

### Deferred: Revenue anomaly → IA urgency modulation
- **Reason**: The `revenue.anomaly` event already fires from `revenue_monitor_service.py`. Wiring it as an urgency input to the Inventory Agent is P1 — low effort but not blocking first onboarding. Revisit after Hyperpure mock is replaced by real automation.

### Deferred: Playwright browser automation (real Hyperpure)
- **Reason**: Playwright setup requires credential management (OTP, session persistence) and a headless browser environment in production Docker. The mock gives full end-to-end behavior now. Swap in when first restaurant is live and Hyperpure credentials are obtained.

### Deferred: Approval timeout / auto-escalate
- **Reason**: P1. Needs a clear SLA decision from the owner (how many hours before a pending item auto-escalates or expires). Defer until first onboarding feedback.

### Deferred: Bill price ≠ PO price discrepancy flagging
- **Reason**: P1. OCR bill scan already exists. Wiring it to compare against PO unit_cost_inr requires price-matching logic and a UI surface for the owner to act on discrepancies. Defer to next sprint.

### Rejected: Multi-vendor fallback
- **Reason**: Out of scope for MVP. Hyperpure-only. If Hyperpure rejects/is down, the owner is notified and orders manually. No alternate vendor routing.

---

## Known Limitations

| Issue | Impact | Path forward |
|---|---|---|
| Hyperpure mock only — no real orders placed | Cannot go live until Playwright automation is built | Build `PlaywrightHyperpureClient`, swap behind same interface |
| `add_stock` uses `$push` on `stock_log` — unbounded array growth | Log will grow indefinitely per material | Add TTL or capped log in a future schema migration |
| `get_active_list()` picks the most recent active list — no restaurant_id scoping | Multi-tenant: wrong if two restaurants share one DB | Add `restaurant_id` field to shopping_list documents before multi-tenant onboarding |

---

## Output / Affected Files

| File | What changed |
|---|---|
| `backend/app/repositories/shopping_list_repository.py` | Added `get_active_list()`, `upsert_items()`, `mark_items_ordered()`, `mark_items_delivered()` |
| `backend/app/services/shopping_list_service.py` | Added `upsert_shopping_list()` (upsert-or-create), `get_active_shopping_list()`, `mark_items_ordered()`, `mark_items_delivered()` |
| `backend/app/services/hyperpure_client.py` | **Created** — `HyperpureClient` abstract interface + `MockHyperpureClient`; later extended with `get_prices()` abstract method, `_MOCK_PRICES` table (~60 Indian wholesale prices), `_lookup_price()` fuzzy matcher, and `get_prices()` mock implementation with ±10% variance |
| `backend/app/services/orchestrator.py` | Changed `create_shopping_list` → `upsert_shopping_list`; added `execute_approved_order()`, `_execute_hyperpure_order()`, `_mock_deliver_after_delay()`. `execute_approved_order()` now writes to `purchase_orders` on confirmed/partial results and schedules mock delivery simulation. |
| `backend/app/api/v1/approvals.py` | Wired `execute_approved_order` after manual approval; added `POST /{list_id}/confirm-delivery`; added `GET /hyperpure-orders` (must be declared before `GET /{list_id}` to avoid FastAPI route shadowing); wired `execute_approved_order` into `POST /{list_id}/approve-items` (was missing — bug fix). |
| `backend/app/services/inventory_service.py` | Added `add_stock()` and `get_inventory_service()` factory |
| `backend/app/repositories/purchase_order_repository.py` | `create()` and `update()` now used by orchestrator for Hyperpure PO lifecycle |
| `backend/app/services/agents/inventory_agent.py` | Added deterministic `execute()` override; σ computed from daily_breakdown; model-based σ multipliers; `is_perishable` normalised to bool; `shelf_life_days` passed to order quantity calculator; added `_reason_about_approvals()` (LLM sandwiched between guardrails); added Hyperpure price fetch before LLM call; `hyperpure_price_rupees` and `price_delta_pct` injected into LLM context |
| `backend/app/services/reorder_calculator.py` | `compute_order_quantity()` accepts `shelf_life_days`; perishable cap uses `min(shelf_life_days, restock_horizon_days)` |
| `backend/app/models/inventory.py` | Added `expiry_date: Optional[datetime]` to `InventoryItem` and `InventoryItemResponse` |

---

## Next Decisions Pending

1. **Playwright credential strategy** — how to store Hyperpure login (OTP, session cookie) in production without exposing credentials in env vars or Docker images.
2. **Restaurant-id scoping** — shopping list and notification collections need `restaurant_id` before second restaurant is onboarded.
3. **Approval SLA** — how long before a pending shopping list item auto-escalates or expires (owner input needed).
4. **Price discrepancy UX** — when OCR bill price differs from PO unit cost by >5%, what does the owner see and what actions can they take?
5. **Revenue anomaly wiring** — subscribe Inventory Agent to `revenue.anomaly` and define the urgency modulation formula (spike ratio → URGENT elevation, drop ratio → LOW_PRIORITY suppression).
6. **Batch vs urgent ordering** — Hyperpure has a minimum order value; owner conversation needed to determine when to batch items across a day vs place an urgent order for a single item. Deferred to first real Hyperpure onboarding. See ADR-008 Deferred section.
