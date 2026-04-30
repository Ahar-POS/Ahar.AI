# Ahar.AI: Autonomous Real-Time Restaurant Operations

## Context

The current system has autonomous agents (Inventory, Financial, Strategic) running on fixed cron schedules with a fully-wired event bus that is never actually used — no service publishes events. Agents feel like batch jobs, not intelligent real-time operators.

The goal is to make Ahar truly autonomous: agents react to what's happening in the restaurant *now* (stock crossing reorder level mid-service, perishables about to expire, revenue falling behind historical pace). Actions are auto-executed when low-risk; flagged for manager approval when high-cost, unusual quantity, new supplier, or discount-based.

User requirements:
- **Smart hybrid autonomy**: low-risk auto-executes, high-risk gets approval
- **Priority**: Inventory & reordering + Waste & expiry management
- **Notifications**: In-app only (MongoDB-backed, polled via API)
- **Triggers**: Inventory update events, time-of-day revenue thresholds, manual staff "report low stock"
- **Expiry action**: Agent suggests "Today's Special" using expiring ingredient → manager approves before staff sees it
- **Multi-role routing**: alerts route to the right role (manager, chef, store keeper)

---

## Phase 1: Wire the Event Bus (Inventory Events)

**Goal**: `inventory.low_stock` becomes a real signal published from three sources, triggered against a **dynamic reorder level** computed from the demand forecast — not the static integer stored on each item.

---

### Why the static `reorder_level` field is wrong

`reorder_level` is currently a hardcoded integer set when an item is created and never updated. The inventory agent already fetches a demand forecast per item but then ignores it for the trigger decision, falling back to this dumb static field. This means:

- On a high-demand day (Monday pre-weekend), the trigger fires too late — stock is already critically low before the threshold is crossed.
- On a slow day, it may trigger unnecessary orders.
- `reorder_qty` has the same problem — a fixed field, not demand-aware.

**The correct approach**: compute the reorder level dynamically at trigger time using the standard supply chain formula:

```
dynamic_reorder_level = (avg_daily_demand × lead_time_days) + safety_stock

safety_stock = 1.65 × σ_demand × √lead_time_days
  where 1.65 = Z-score for 95% service level
        σ_demand = std deviation of daily demand (fallback: 20% of avg)
        lead_time_days = from the item record (already stored)
```

The stored `reorder_level` field becomes a **manual floor** — a minimum threshold the manager explicitly sets. The trigger fires when `current_stock <= max(dynamic_reorder_level, item.reorder_level)`.

---

### New file: `backend/app/services/reorder_calculator.py`

```python
import math

def compute_dynamic_reorder_level(
    avg_daily_demand: float,
    demand_std_dev: float,
    lead_time_days: int,
    service_level_z: float = 1.65   # 95% service level
) -> float:
    """
    Compute dynamic reorder point using demand forecast + lead time.

    reorder_point = (avg_daily_demand × lead_time_days) + safety_stock
    safety_stock  = Z × σ_demand × √lead_time_days
    """
    demand_during_lead = avg_daily_demand * lead_time_days
    safety_stock = service_level_z * demand_std_dev * math.sqrt(lead_time_days)
    return demand_during_lead + safety_stock


def compute_order_quantity(
    avg_daily_demand: float,
    demand_std_dev: float,
    lead_time_days: int,
    current_stock: float,
    is_perishable: bool,
    restock_horizon_days: int = 7
) -> float:
    """
    Compute how much to order: enough to cover restock_horizon + safety,
    minus what's already in stock. Reduce buffer for perishables.
    """
    safety_stock = 1.65 * demand_std_dev * math.sqrt(lead_time_days)
    if is_perishable:
        safety_stock *= 0.7   # prefer slight stockout risk over waste
    target = avg_daily_demand * (lead_time_days + restock_horizon_days) + safety_stock
    return max(0.0, target - current_stock)
```

---

### Modify `backend/app/services/inventory_service.py`

In `consume_for_order()` — after the `bulk_decrement_stock()` call (line ~261):

```python
from app.services.event_bus import get_event_bus
from app.services.reorder_calculator import compute_dynamic_reorder_level

event_bus = get_event_bus()
for c in consumed:
    item = await inventory_repository.get_by_material_id(c["material_id"])
    if not item:
        continue

    current_stock = item.get("current_stock", 0)

    # Fetch latest forecast for this material (7-day window)
    forecast = await forecast_repository.get_latest(c["material_id"])
    if forecast:
        avg_daily = forecast["predicted_consumption"] / 7.0
        std_dev = forecast.get("demand_std_dev", avg_daily * 0.2)
    else:
        # No forecast yet — fall back to stored static level only
        avg_daily = None
        std_dev = None

    if avg_daily is not None:
        dynamic_level = compute_dynamic_reorder_level(
            avg_daily_demand=avg_daily,
            demand_std_dev=std_dev,
            lead_time_days=item["lead_time_days"]
        )
        # Static field acts as a manual floor set by the manager
        effective_reorder_level = max(dynamic_level, item.get("reorder_level", 0))
    else:
        effective_reorder_level = item.get("reorder_level", 0)

    if current_stock <= effective_reorder_level:
        await event_bus.publish("inventory.low_stock", {
            "material_id": c["material_id"],
            "material_name": c["material_name"],
            "current_stock": current_stock,
            "dynamic_reorder_level": round(effective_reorder_level, 1),
            "static_reorder_level": item.get("reorder_level", 0),
            "unit": c["unit"],
            "trigger": "order_consumption",
            "order_id": order_id
        })
```

Apply the same pattern in `update_item()` — if `current_stock` was patched and is now below `effective_reorder_level`, publish with `"trigger": "manual_stock_update"`.

---

### Modify `backend/app/services/agents/inventory_agent.py`

In `calculate_reorder_needs()` (line ~318), replace the static comparison and fixed order qty:

```python
# BEFORE (static, wrong):
reorder_level = item["reorder_level"]
should_reorder = current_stock <= reorder_level or urgency == "URGENT"
quantity_to_order = item["reorder_qty"]   # fixed field, demand-unaware

# AFTER (dynamic):
from app.services.reorder_calculator import compute_dynamic_reorder_level, compute_order_quantity

avg_daily = forecast["predicted_consumption"] / 7.0
std_dev = forecast.get("demand_std_dev", avg_daily * 0.2)

dynamic_level = compute_dynamic_reorder_level(avg_daily, std_dev, item["lead_time_days"])
effective_reorder_level = max(dynamic_level, item["reorder_level"])  # manual floor

should_reorder = current_stock <= effective_reorder_level or urgency == "URGENT"

quantity_to_order = compute_order_quantity(
    avg_daily_demand=avg_daily,
    demand_std_dev=std_dev,
    lead_time_days=item["lead_time_days"],
    current_stock=current_stock,
    is_perishable=item["is_perishable"] == "Yes"
)
```

Also expose `dynamic_reorder_level` in the reorder item dict so the manager sees the computed threshold (not the static one) in the PO review UI.

---

### Modify `backend/app/api/v1/inventory.py`

Add endpoint `POST /inventory/{item_id}/report-low-stock`:
- Open to any authenticated user (not just ADMIN)
- Fetches the item, publishes `inventory.low_stock` with `"trigger": "staff_manual_report"` and `"reported_by": current_user.id`
- No dynamic level computation here — staff report is a manual override, bypass thresholds
- Returns `success_response`

---

## Phase 2: Hourly Revenue Monitor

**Goal**: APScheduler job runs every hour, compares current-hour revenue vs. historical same-hour average, publishes `revenue.anomaly` if below threshold.

### Modify `backend/app/services/orchestrator.py`

In `_register_schedules()`, add:
```python
self.scheduler.add_job(
    self._run_revenue_monitor,
    CronTrigger(minute=5),   # 5 min past every hour
    id='revenue_hourly',
    name='Hourly Revenue Monitor',
    replace_existing=True
)
```

Add method `_run_revenue_monitor()` that instantiates `RevenueMonitorService` and calls `check_hourly_revenue()`; publishes `revenue.anomaly` if anomaly detected.

### New file: `backend/app/services/revenue_monitor_service.py`

`RevenueMonitorService.check_hourly_revenue()`:
1. Aggregate `orders` collection for revenue in the current hour (`status != "cancelled"`, `SUM(total_amount)`)
2. Aggregate last 30 days for same hour + same day-of-week average (avoids weekend/weekday distortion)
3. If `current < avg * REVENUE_ANOMALY_THRESHOLD` and sufficient history (≥ 7 days), return anomaly dict with `anomaly_detected: True`, `current_revenue_inr`, `historical_avg_inr`, `deviation_pct`, `hour`

### Modify `backend/app/core/config.py`

Add to Settings:
```python
REVENUE_ANOMALY_THRESHOLD: float = 0.60   # alert if below 60% of historical avg
REVENUE_ANOMALY_MIN_HISTORY_DAYS: int = 7
```

---

## Phase 3: Expiry Monitoring + "Today's Special" Suggestion

**Goal**: Daily job detects perishables expiring within 2 days, LLM suggests a discounted special dish, creates a `pending_approval` record managers approve before staff see it.

### Modify `backend/app/services/orchestrator.py`

In `_register_schedules()`, add daily 5 AM job `_run_expiry_monitor()`.

`_run_expiry_monitor()`:
- Calls `ExpiryMonitorService.get_expiring_soon(days_threshold=2)`
- Publishes `inventory.expiring_soon` if items found
- Calls `ExpiryMonitorService.generate_specials_for_expiring(items)`

### New file: `backend/app/services/expiry_monitor_service.py`

**`get_expiring_soon(days_threshold=2)`**:
- Query `raw_material_inventory` where `is_perishable == "Yes"` and `last_restock_date` not null
- Compute: `expiry_date = last_restock_date + timedelta(days=shelf_life_days)`
- Return items where `today <= expiry_date <= today + timedelta(days=days_threshold)`

**`generate_specials_for_expiring(items)`**:
- Use `BaseAgent._call_claude()` with a targeted prompt per expiring item
- Prompt: given ingredient X, Y units, expires in Z days → suggest dish name, description, discount %
- Write to `expiry_specials` collection with `status: "pending_approval"`, `visible_to_staff: false`

### New MongoDB collection: `expiry_specials`

```json
{
  "material_id": "RM012",
  "material_name": "Fresh Cream",
  "days_until_expiry": 1,
  "current_stock": 5,
  "unit": "Liters",
  "suggested_dish_name": "Cream of Mushroom Soup",
  "description": "...",
  "suggested_discount_pct": 15,
  "ai_reasoning": "...",
  "status": "pending_approval",
  "visible_to_staff": false,
  "created_at": "datetime",
  "approved_at": null,
  "approved_by": null
}
```

Indexes: `status`, `created_at`, `[status, visible_to_staff]`

### Modify `backend/app/api/v1/approvals.py`

Add three endpoints under existing approvals router:
- `GET /approvals/expiry-specials` — list pending (ADMIN only)
- `POST /approvals/expiry-specials/{special_id}/approve` — set `status: approved`, `visible_to_staff: true`
- `POST /approvals/expiry-specials/{special_id}/reject` — set `status: rejected`

### Modify `backend/app/api/v1/inventory.py`

Add `GET /inventory/today-specials` — returns `expiry_specials` where `status == "approved"` and `visible_to_staff == true` and `created_at >= today`. Available to all authenticated users (staff/waiters poll this).

---

## Phase 4: In-App Notification System

**Goal**: Persistent role-targeted notification records. Frontend polls `GET /notifications/unread-count` for badge; full list on `GET /notifications`.

### New MongoDB collection: `notifications`

```json
{
  "type": "low_stock",
  "title": "Low Stock: Fresh Cream",
  "message": "Fresh Cream at 2 units (reorder at 5)",
  "target_role": "admin",
  "target_user_id": null,
  "related_entity_type": "inventory",
  "related_entity_id": "RM012",
  "is_read": false,
  "created_at": "datetime",
  "read_at": null,
  "metadata": {}
}
```

Indexes: `[target_role, is_read]`, `created_at` TTL 30 days, `target_user_id`

### New file: `backend/app/services/notification_service.py`

Methods:
- `create(type, title, message, target_role, related_entity_type, related_entity_id, metadata)` — inserts to collection
- `create_for_low_stock(event_data)` — wraps `create()` targeting `"admin"`
- `create_for_expiry_special(special_doc)` — type `"expiry_special_pending"`, targets `"admin"`
- `create_for_revenue_anomaly(event_data)` — type `"revenue_anomaly"`, targets `"admin"`
- `get_for_user(user_role, user_id, unread_only, limit=50)` — query by role or specific user
- `mark_read(notification_id)`, `mark_all_read(user_role, user_id)`

### Modify `backend/app/services/orchestrator.py`

Update all three event handlers to call `NotificationService` before (or after) their existing logic:
- `_handle_low_stock()` → `create_for_low_stock(event_data)`
- `_handle_expiring_soon()` → `create_for_expiry_special()` (remove current placeholder insert)
- `_handle_revenue_anomaly()` → `create_for_revenue_anomaly(event_data)`

Also in `_log_decision()`: when `status == "pending_approval"`, create a `shopping_list_pending` notification.

### New file: `backend/app/api/v1/notifications.py`

```python
GET  /notifications               # list (paginated), returns unread_count in metadata
GET  /notifications/unread-count  # fast poll: {"unread_count": N}
POST /notifications/{id}/read     # mark one read
POST /notifications/mark-all-read # mark all read for current user
```

All endpoints use `Depends(get_current_user)`.

### Modify `backend/app/api/v1/__init__.py`

Register `notifications_router`.

---

## Phase 5: Smart Approval Thresholds

**Goal**: Replace the `return False` stub in `orchestrator._requires_approval()` with configurable real logic.

### New MongoDB collection: `approval_thresholds`

Single config document (upserted on startup with defaults):
```json
{
  "cost_threshold_paise": 500000,
  "quantity_multiplier": 2.0,
  "expiry_discount_always_approve": true
}
```

### New file: `backend/app/services/approval_threshold_service.py`

- `get_thresholds()` — fetch config doc
- `check_cost(estimated_cost_paise) -> bool` — `cost > threshold`
- `check_quantity(material_id, ordered_qty) -> bool` — compare to 30-day avg from `inventory_consumption_logs`; default `True` if < 7 days of history
- `check_new_supplier(supplier_id) -> bool` — check against distinct supplier_ids in inventory
- `check_expiry_discount(action) -> bool` — checks `action.data.get("is_expiry_discount")` + config flag

### Modify `backend/app/services/orchestrator.py`

Replace `_requires_approval()` stub. Change to `async def _requires_approval()` and update the one call site in `_log_decision()`. Logic iterates `decision.actions` and calls `ApprovalThresholdService` checks — returns `True` on first match.

### Modify `backend/app/api/v1/settings.py`

Add two endpoints (ADMIN only):
- `GET /settings/approval-thresholds`
- `PUT /settings/approval-thresholds`

---

## Dependency Order

```
Phase 1: event_bus wired in inventory_service.py
    ↓
Phase 2: APScheduler hourly job → revenue.anomaly published
    ↓
Phase 3: APScheduler daily job → expiry_specials collection + approval endpoints
    ↓
Phase 4: NotificationService consumes all events → notifications collection + API
    ↓
Phase 5: _requires_approval() reads approval_thresholds → config API
```

Each phase is independently deployable. Phases 1–2 are backend-only. Phases 3–4 expose new APIs the frontend consumes. Phase 5 is backend logic only.

---

## Files to Create / Modify

| Phase | New Files | Modified Files |
|-------|-----------|----------------|
| 1 | `reorder_calculator.py` | `inventory_service.py`, `agents/inventory_agent.py`, `api/v1/inventory.py` |
| 2 | `revenue_monitor_service.py` | `orchestrator.py`, `core/config.py` |
| 3 | `expiry_monitor_service.py` | `orchestrator.py`, `api/v1/approvals.py`, `api/v1/inventory.py` |
| 4 | `notification_service.py`, `api/v1/notifications.py` | `orchestrator.py`, `api/v1/__init__.py` |
| 5 | `approval_threshold_service.py` | `orchestrator.py`, `api/v1/settings.py` |

## New MongoDB Collections

| Collection | Phase | Purpose |
|------------|-------|---------|
| `expiry_specials` | 3 | AI-generated specials pending manager approval |
| `notifications` | 4 | In-app alerts per role, polled by frontend |
| `approval_thresholds` | 5 | Configurable thresholds for auto-execute vs approval |

---

## Verification

1. **Phase 1**: Place an order that exhausts an ingredient below reorder level → check `event_bus.get_history()` shows `inventory.low_stock`; orchestrator log shows `_handle_low_stock` fired.
2. **Phase 2**: Seed orders with low revenue for today's hour → call `_run_revenue_monitor()` manually via `trigger_agent("revenue_monitor")` → check `financial_alerts` collection for `revenue_anomaly_hourly` entry.
3. **Phase 3**: Set a perishable item's `last_restock_date` to 2 days before expiry → call `_run_expiry_monitor()` manually → check `expiry_specials` collection has a `pending_approval` record; approve via `POST /approvals/expiry-specials/{id}/approve` → `GET /inventory/today-specials` returns it.
4. **Phase 4**: Trigger a low stock event → `GET /notifications/unread-count` returns `{"unread_count": 1}`; `GET /notifications` returns the record; `POST /notifications/{id}/read` sets `is_read: true`.
5. **Phase 5**: Set `cost_threshold_paise: 100` (very low) → trigger inventory agent → check `agent_decisions` has `status: "pending_approval"` and notification of type `shopping_list_pending` was created.

---

# Frontend Plan: Nielsen's 10 Heuristics Applied

Each feature built in the MVP loop is mapped to the specific Nielsen principles it must satisfy. Design decisions are concrete — component choices, copy, interaction patterns.

---

## Heuristic Cheatsheet (reference)

| # | Principle | One-line |
|---|-----------|----------|
| H1 | Visibility of system status | Always tell the user what's happening |
| H2 | Match real world | Use restaurant language, not tech jargon |
| H3 | User control and freedom | Support undo, easy exits |
| H4 | Consistency and standards | Same patterns everywhere |
| H5 | Error prevention | Stop mistakes before they happen |
| H6 | Recognition over recall | Surface options; don't make them remember |
| H7 | Flexibility and efficiency | Power users get shortcuts |
| H8 | Aesthetic and minimalist design | Only show what's needed right now |
| H9 | Help recover from errors | Clear, human error messages with a fix path |
| H10 | Help and documentation | Contextual, not a wall of text |

---

## Feature 1: Opening Stock Log

**Context**: Manager/store keeper logs today's baseline stock at 6 AM.

### UI Component
`StockCheckInPage` — a single-screen checklist. One row per ingredient. Left: ingredient name + unit. Right: editable number input pre-filled with last closing stock (best guess).

### Heuristics Applied

**H1 — Visibility of status**: Header shows `"Stock Check-in · Today, Apr 12"`. A progress indicator `"14 / 32 items confirmed"` updates live as manager taps through.

**H2 — Real world match**: Call it **"Morning Stock Check"** not "Opening Inventory Log". Use restaurant units — "2 kg", "500 ml", not raw numbers. Ingredients grouped by station: *Dry Store · Fridge · Freezer*.

**H5 — Error prevention**: If a value entered deviates >50% from yesterday's closing stock, inline warning: `"Yesterday's closing was 8 kg — sure it's 1 kg today?"` before submission. Not a blocker — just a flag.

**H6 — Recognition**: Previous day's closing stock shown in muted text next to the input as a reference. Manager recognises the number rather than recalling it from memory.

**H7 — Efficiency**: Keyboard tab-through across inputs. A **"Mark all as unchanged"** bulk action for days when nothing moved overnight. Power users can be done in 20 seconds.

**H8 — Minimalist**: Only show items that are tracked (is_perishable OR reorder_level set). Hide seasonal items that are out-of-menu. No columns for supplier, cost, etc — wrong context.

**H3 — Control**: `"Save as Draft"` button lets manager pause and resume. Closing the page mid-way asks: `"You have 18 unsaved entries — save draft or discard?"`.

---

## Feature 2: Closing Stock Log

**Context**: Same pattern as opening, run at end of day.

### Heuristics Applied

**H1 — Status**: Show `"Expected vs Actual"` column — system calculates expected closing based on opening stock minus orders consumed. If actual ≠ expected, flag in amber: `"12 items differ from expected — review before submitting"`.

**H2 — Real world**: Call discrepancy column **"Difference"** not "Variance". Use plain language: `"Used more than expected"` or `"More stock than expected — possible over-purchase?"`.

**H9 — Error recovery**: If large discrepancy on submit, block with a modal: `"Fresh Cream: Expected 2L remaining, you entered 0L. Possible causes: spillage, unlogged usage, theft. Add a note?"`. Textarea for note. Can still submit.

**H4 — Consistency**: Opening and closing stock screens are visually identical — same layout, same grouping, same input style. Only the header and context change.

---

## Feature 3: Notification Bell (In-App Alerts)

**Context**: Persistent bell icon in top nav; polling `GET /notifications/unread-count` every 30s.

### UI Component
Bell icon in top navigation bar. Red badge with count. Clicking opens a slide-out drawer (not a modal — non-blocking).

### Heuristics Applied

**H1 — Status**: Badge number updates in real time (polling). Drawer shows timestamp for each notification: `"2 minutes ago"`, not `"2026-04-12T06:14:00Z"`.

**H2 — Real world**: Notification copy uses kitchen language:
- `"Tomatoes are running low — 2 kg left (reorder at 5 kg)"`
- Not: `"inventory.low_stock event for material_id RM012"`

**H4 — Consistency**: All notifications follow the same card pattern: `[Icon] [Title] [Body copy] [Timestamp] [Action button if applicable]`. Action button text matches the workflow: **"Review PO"**, **"Approve Special"**, **"View Stock"**.

**H8 — Minimalist**: Drawer shows max 10 most recent. Unread notifications are white-background; read ones are grey-background. No metadata clutter. `"See all"` link at the bottom goes to a full notifications page.

**H6 — Recognition**: Notification type communicated by icon + colour strip on left edge:
- Red strip = low stock / urgent
- Amber strip = pending approval
- Green strip = auto-executed (informational)
- Blue strip = suggestion (expiry special)

**H3 — Control**: `"Mark all as read"` in drawer header. Each individual notification has an `×` to dismiss. Dismissed notifications are not deleted — moved to archived state accessible via "See all".

---

## Feature 4: Low Stock Alert → PO Review

**Context**: Inventory agent generates a PO suggestion; autonomy mode = Hybrid → owner must approve.

### UI Component
`PurchaseOrderReviewPage` accessible from notification action button or `/approvals` nav item. Shows the AI-generated PO with reasoning.

### Heuristics Applied

**H1 — Status**: Page header shows the PO state as a pill: `Pending Approval · Generated 6 mins ago`. After approving: `Approved · Sent to supplier at 6:32 AM`. After rejecting: `Rejected · No order placed`.

**H2 — Real world**: Table uses familiar PO language — **Item**, **Current Stock**, **Order Qty**, **Unit Price**, **Subtotal**, **Supplier**. Total at bottom like a real invoice. "Why is the agent suggesting this?" expandable section shows the AI reasoning in plain English: `"Tomatoes typically last 2 days. You have 2 kg. Forecast shows 8 kg needed tomorrow based on last 4 Mondays."` — not raw JSON.

**H3 — Control**: Three actions: **Approve All**, **Modify & Approve**, **Reject**. "Modify & Approve" opens inline quantity editors per row — owner can change order qty before approving. Reject requires a reason (dropdown: Too expensive / Wrong supplier / Already ordered / Other).

**H5 — Error prevention**: If owner reduces qty below minimum order from supplier, inline warning: `"Min order from FreshMart is 5 kg — you entered 2 kg"`. If owner approves a PO >₹5,000 (threshold), a confirmation modal: `"This PO totals ₹6,200 — confirm send to supplier?"`.

**H6 — Recognition**: Supplier name shown with last-used date: `"FreshMart · Last ordered 3 days ago"`. No need to recall who supplies what.

**H9 — Error recovery**: If approval API call fails, toast: `"Couldn't submit approval — try again"` with a Retry button. PO status stays `Pending` — no silent failure.

**H8 — Minimalist**: Default view hides per-item AI reasoning. Only show total cost, item count, urgency. Expandable `"See agent reasoning"` for those who want it.

---

## Feature 5: Autonomy Settings

**Context**: Owner configures Full / Hybrid / No Autonomous mode.

### UI Component
Card in Settings page (not buried in a sub-menu). Radio button group with three options. Each option has a one-sentence explanation.

### Heuristics Applied

**H2 — Real world**:

| Option | Label | Explanation |
|--------|-------|-------------|
| Full | `"Full Autopilot"` | `"Agent places orders automatically. You'll be notified after."` |
| Hybrid | `"Supervised"` | `"Agent handles small orders automatically. Big or unusual ones need your OK."` |
| No Auto | `"Manual Mode"` | `"Agent only suggests. You approve everything before any order is placed."` |

**H5 — Error prevention**: Switching to "Full Autopilot" shows a confirmation: `"In Full Autopilot, orders above ₹500 will be placed automatically. You can switch back anytime."` Switching FROM Full Autopilot to Manual shows: `"Any pending auto-orders will be paused and moved to your approval queue."` — prevents accidental runaway orders.

**H1 — Status**: Current mode shown in a persistent status chip in the Inventory dashboard header: `"Supervised Mode · Active"`. Owner always knows the current autonomy level at a glance.

**H6 — Recognition**: Threshold configuration shown only when "Supervised" is selected — the rest is hidden. Shows: `"Auto-approve orders below ₹[____]"` and `"Flag if order quantity is [2×] the usual amount"`. Values pre-filled with current config.

**H4 — Consistency**: Threshold inputs follow the same pattern as all other monetary inputs in the app (prefix ₹, integer, no decimals).

---

## Feature 6: Bulk Order Flag on Order Creation

**Context**: Staff creating a large catering order must mark it as bulk so ML excludes it from normal demand training.

### UI Component
Checkbox + tooltip at the bottom of the `CreateOrderPage` form, near the Submit button.

### Heuristics Applied

**H2 — Real world**: Label: `"This is a catering / event order"`. Not `"is_bulk_order: true"`. Tooltip: `"Check this for large party or event orders. These won't affect your daily stock predictions."`.

**H5 — Error prevention**: If order total > ₹3,000 and checkbox is unchecked, soft prompt appears: `"This looks like a large order — is it for an event?"` with a one-click `"Yes, mark as event"` option. Prevents ML poisoning by omission.

**H6 — Recognition**: The checkbox is only shown when order subtotal exceeds a threshold (₹2,000) — not visible on every order. Staff don't need to remember when to check it; the UI surfaces it contextually.

**H8 — Minimalist**: No extra fields for bulk orders — just the checkbox. Don't ask for event date, party size, etc. at this stage.

---

## Feature 7: Today's Specials (Expiry-Based)

**Context**: Agent suggests a dish using an expiring ingredient. Manager approves → staff sees it.

### Two-screen flow:
1. **Manager approval screen** (`/approvals/expiry-specials`) — only visible to ADMIN
2. **Staff view** (`/inventory/today-specials`) — visible after approval

### Manager Approval Screen

**H2 — Real world**: Card title: `"Suggested Today's Special"`. Show: ingredient name, qty remaining, days until expiry, suggested dish, suggested discount %. Section: `"Why this suggestion"` with the AI reasoning.

**H3 — Control**: Approve, Edit & Approve (change dish name/description/discount), Reject. After approving: instant confirmation `"Today's Special is now live for staff"`.

**H1 — Status**: If approved earlier today, a green banner: `"Today's Special is active · Fresh Cream Soup · 15% off · Approved by you at 8:14 AM"`.

### Staff View

**H8 — Minimalist**: A single highlighted card at the top of the menu/order screen: `"Today's Special: Cream of Mushroom Soup · 15% off · Uses fresh cream expiring today"`. One tap to add to an order.

**H4 — Consistency**: Special card follows the same visual style as regular menu item cards — just with an amber "Special" badge and strikethrough original price.

---

## Feature 8: Cross-Feature Patterns (Apply Everywhere)

These apply globally across all inventory MVP features.

### H4 — Consistency Standards

| Element | Standard |
|---------|----------|
| Monetary display | Always `₹X,XXX` — never raw paise |
| Stock units | Always show unit: `2 kg`, `500 ml`, not just `2` |
| Timestamps | Relative for recent (<24h): `"3 mins ago"`. Absolute for older: `"Apr 11, 8:14 PM"` |
| Status pills | Pending = amber, Approved = green, Rejected = red, Auto-executed = blue |
| Destructive actions | Always red text, always require confirmation |

### H7 — Efficiency (Power User Shortcuts)

- Morning stock check: `Tab` moves between inputs; `Enter` confirms and advances
- Notification drawer: `K` keyboard shortcut to open (discoverable via tooltip on bell icon)
- Approvals list: Bulk approve with checkbox selection + "Approve Selected" — don't force one-by-one

### H10 — Help and Documentation

Contextual `?` tooltip on every non-obvious field:
- Reorder level: `"When stock drops to this number, the agent will suggest a reorder"`
- Lead time: `"How many days until the supplier delivers after an order is placed"`
- Autonomy mode: `"Controls how much the agent can act without your approval"`

No separate help page for these — inline, at point of need.

---

## New Frontend Files

| File | Purpose |
|------|---------|
| `pages/StockCheckInPage.tsx` | Opening + closing stock log (shared component, different mode prop) |
| `pages/PurchaseOrderReviewPage.tsx` | PO approval detail view |
| `pages/TodaySpecialsApprovalPage.tsx` | Manager expiry specials approval queue |
| `components/NotificationDrawer.tsx` | Slide-out notification panel |
| `components/NotificationBell.tsx` | Bell icon + badge, polls unread count |
| `components/AutonomySettingsCard.tsx` | Full/Hybrid/No mode selector |
| `components/BulkOrderCheckbox.tsx` | Contextual bulk flag on order form |
| `services/notifications.ts` | API calls: fetch, mark read, poll unread count |
| `services/stockLog.ts` | Opening/closing stock API calls |
| `services/purchaseOrders.ts` | PO approval API calls |
| `hooks/useNotificationPoll.ts` | 30s polling hook for unread count |
