# ADR-009: Customer Experience Agent — Promotion Engine & POS Discount Integration

**Date**: 2026-05-04
**Status**: Accepted
**Decider**: Pandiarajan
**Context**: Autonomous promotion generation — turning sales-pattern signals into time-limited discounts that flow from agent suggestion through owner approval to the POS order screen

---

## Problem

Ahar.AI had no mechanism for generating promotions from data. Owners set discounts manually — an ad-hoc, reactive process that missed signals like:
- Items frequently ordered together (upsell opportunity)
- Demand spikes on specific items (leverage while hot)
- Expiring inventory that needs to move (margin preservation)
- Slow-moving items on a particular day (stimulate demand)

The goal is an agent that surfaces 2–4 data-driven promotion suggestions daily, routes them through owner approval, and — when approved — makes them immediately visible to waiters on the order screen so they can proactively up-sell.

---

## Decisions Made

### Decision: Four promotion types covering distinct demand signals

- **Chosen**: `PERCENTAGE_OFF` (general discount on a specific item), `COMBO_DEAL` (pair two co-occurring items at a bundle price), `EXPIRY_CLEAR` (aggressive discount on items expiring within 48 hours), `SPIKE_LEVERAGE` (limited-time promotion on an item showing an unusual demand surge).
- **Rejected**: A single generic "discount" type — loses signal fidelity. The promotion type tells the waiter *why* to recommend it, which affects how they pitch it.
- **Reason**: Each type maps to a distinct analysis signal (co-occurrence matrix, expiry window, spike detector). Keeping them separate lets the owner quickly assess whether the agent's reasoning is sound.

---

### Decision: Daily 7:30 AM cron — agent runs after expiry monitor (7:00 AM), before service

- **Chosen**: `customer_experience_daily` APScheduler job at 7:30 AM IST. Runs after `expiry_monitor_daily` (7:00 AM) so `EXPIRY_CLEAR` suggestions can reference the morning's expiry scan output. Suggestions persist as `status: "pending"` in a `promotion_suggestions` collection. Owner reviews before the lunch rush.
- **Rejected**: Running on demand only — sales-trend signals are most actionable in the morning before the day's service starts. A cron ensures the owner always has suggestions ready at opening.
- **Reason**: The 30-minute gap after the expiry monitor ensures expiry data is committed before the promo agent reads it.

---

### Decision: Human-in-the-loop approval before promotion goes live

- **Chosen**: Promotion suggestions require explicit owner approval via `POST /api/v1/approvals/promotions/{id}/approve`. On approval, the document is inserted into a `promotions` collection with `status: "active"`, `valid_from`, `valid_until`. Rejections are logged with an optional reason.
- **Rejected**: Auto-applying suggestions — discounts are margin-affecting decisions. The agent doesn't know the owner's current food cost situation or supplier commitments that might make a discount inadvisable.
- **Reason**: Consistent with the approval pattern used for shopping lists (ADR-007/008) and expiry specials (ADR-003). The agent proposes; the owner decides.

---

### Decision: POS discount fields added to `OrderItem` — tracked per line

- **Chosen**: Three optional fields added to `OrderItem` model: `original_price_snapshot` (price at time of order, before discount), `discount_paise` (amount discounted), `applied_promo_id` (reference to `promotions` collection). Fields are `None` when no promotion applies.
- **Rejected**: Storing discount as a computed diff at checkout — losing the `applied_promo_id` reference means reports can't attribute revenue impact back to the specific promotion.
- **Reason**: Per-line discount tracking enables post-hoc analysis: "Did this promotion actually increase covers, or did it just reduce revenue on items that would have sold anyway?"

---

### Decision: Waiter-facing active promotions endpoint — `GET /promotions/active`

- **Chosen**: New `promotion_service.py` utility returns all currently-active promotions (within `valid_from`/`valid_until` window, `status: "active"`). The waiter order screen calls this on mount and shows a visual indicator on promoted items in the menu grid.
- **Rejected**: Embedding promotion data inside the menu items API response — promotions have their own lifecycle (agent-driven, time-limited) that's orthogonal to the menu catalogue.
- **Reason**: A separate endpoint keeps the menu API stable and lets the order screen selectively overlay promotion badges without re-rendering the entire menu.

---

## Decisions Rejected / Deferred

### Deferred: Promotion performance analytics
- **Reason**: First iteration establishes the data model (`applied_promo_id` on `OrderItem`). Analytics queries (revenue lift, attach rate per promo type) deferred until several promotion cycles have run and there's enough data to be meaningful.

### Deferred: Automatic promotion expiry notifications to waiters
- **Reason**: "This combo deal expires in 30 minutes" push-style alerts to waiter devices requires a websocket or push channel not yet built. The current solution relies on the `valid_until` field and the order screen's on-mount fetch.

### Rejected: LLM-generated promotion copy (pitch text for waiters)
- **Reason**: Added latency and cost for marginal value. Waiters already see the item name, discount value, and promo type — enough to pitch naturally. Copy generation can be revisited if field feedback says waiters are unsure how to describe combos.

---

## Known Limitations

| Issue | Impact | Path forward |
|---|---|---|
| No promotion conflict resolution | Two promotions on the same item in the same window both show as active | Add a uniqueness guard in `promotion_service.py` — reject approval if an active promo already exists for the same item |
| Spike detection is heuristic | Demand spike uses a simple ratio vs 7-day rolling average; can fire on noise | Calibrate threshold with live data once several weeks of orders accumulate |
| `valid_until` not configurable per type | All promotions default to same-day expiry | Add type-specific defaults (EXPIRY_CLEAR: 24h, COMBO_DEAL: 3 days) in config |

---

## Output / Affected Files

| File | What changed or was created |
|---|---|
| `backend/app/services/agents/customer_experience_agent.py` | **New agent**. Daily analysis: co-occurrence, demand spikes, expiry signals. Generates 2–4 suggestions. |
| `backend/app/services/promotion_service.py` | **New file**. Queries active promotions by current timestamp window. |
| `backend/app/api/v1/promotions.py` | **New file**. `GET /promotions/active` endpoint. |
| `backend/app/api/v1/approvals.py` | Added `POST /approvals/promotions/{id}/approve` and `/reject` endpoints. |
| `backend/app/models/order.py` | Added optional `original_price_snapshot`, `discount_paise`, `applied_promo_id` to `OrderItem`. |
| `backend/app/services/orchestrator.py` | Registered `customer_experience_daily` APScheduler job at 7:30 AM IST. |
| `frontend/src/pages/screens/IntelligenceHubScreen.tsx` | "Run Customer Experience Agent" manual trigger button added. |

---

## Next Decisions Pending

1. **Promotion conflict resolution** — define what happens when two agent runs both suggest a discount on the same item in overlapping windows.
2. **Analytics layer** — when to build the "promotion performance" view: revenue vs. baseline, covers attributed, discount cost.
3. **Promo type expansion** — `HAPPY_HOUR` (time-of-day discounts) and `LOYALTY_BUNDLE` (repeat-customer targeting) are logical next types once the core four are validated in production.
