### Prerequisites

```bash
docker compose up -d --build
# Confirm all 3 services healthy
docker compose ps
```

---

## Phase 1 — Event Bus: Low Stock Events

**What changed:** `inventory_service.py` now fires `inventory.low_stock` from three places:
1. Order consumption (`consume_for_order`)
2. Manual stock patch (`update_item`)
3. On negative stock detection

**Test Steps:**

1. Log in as **admin**
2. Go to Inventory — pick any item, manually edit its `current_stock` to a value below its `reorder_level` via the UI
3. Check backend logs: `docker compose logs backend -f`
4. **Expected**: See `low stock event` log line + `Running Inventory Agent` triggered immediately
5. Go to Approvals — a new shopping list should appear within seconds for the low-stock item

---

## Phase 2 — Hourly Revenue Monitor

**What changed:** Orchestrator schedules `_run_revenue_monitor` every hour at :05. Anomalies write to `financial_alerts` collection and create a notification.

**Test Steps (manual trigger since cron runs at :05):**

1. Hit Swagger at `http://localhost:8000/docs`
2. Find any admin-only endpoint to trigger the financial agent, or insert a test anomaly directly in Mongo:
```js
// MongoDB shell
db.financial_alerts.insertOne({
  hour: 14,
  ratio: 0.45,
  severity: "high",
  status: "active",
  created_at: new Date()
})
```
3. **Expected**: Notification bell (once Phase 4 UI is wired) shows a revenue alert for admins
4. Check logs: `docker compose logs backend | grep "Revenue monitor"`

---

## Phase 3 — Expiry Monitor + Today's Special

**What changed:** New `_run_expiry_monitor` runs daily at 7 AM. Detects items expiring within 2 days, calls Claude for a dish suggestion, stores in `expiry_specials` collection as `pending`.

**Test Steps:**

1. In Mongo, insert an inventory item with `expiry_date` within 2 days and `current_stock > 0`:
```js
db.raw_material_inventory.updateOne(
  { material_name: "Tomatoes" },
  { $set: { expiry_date: new Date(Date.now() + 1.5*24*60*60*1000) } }
)
```
2. Trigger the expiry monitor via Swagger (or wait for 7 AM cron)
3. Check `expiry_specials` collection: `db.expiry_specials.find({})`
4. **Expected**: A document with `status: "pending"` and an LLM-generated `suggestion` field
5. Test the approval endpoints via Swagger:
   - `POST /api/v1/approvals/expiry-specials/{special_id}/approve` — status should become `approved`
   - `POST /api/v1/approvals/expiry-specials/{special_id}/reject` — status should become `rejected`
6. After approving: check backend logs for "Today's Special approved — chef notified"

---

## Phase 4 — In-App Notification System

**What changed:** New `notifications` collection, `notifications_router` registered, `_create_notification()` helper used in low_stock and revenue_anomaly handlers.

**Test Steps:**

1. Trigger a low stock event (same as Phase 1 test)
2. Call `GET /api/v1/notifications` as admin — **Expected**: see a notification with `type: "low_stock"`
3. Call `GET /api/v1/notifications` as a chef — **Expected**: no low_stock notification (role-targeted)
4. Check notification has fields: `title`, `message`, `severity`, `is_read: false`, `target_roles`
5. Mark it read via `PATCH /api/v1/notifications/{id}/read`
6. Call GET again — **Expected**: `is_read: true`

---

## Phase 5 — Smart Approval Thresholds

**What changed:** `_requires_approval()` now implements 4 real gates. `_process_inventory_decision()` auto-approves or routes to manual review.

**Test A — Auto-approve (small order, known supplier):**

1. Set in `.env`: `AUTO_APPROVE_LIMIT_INR=99999` (very high limit so everything passes)
2. `docker compose up -d --build`
3. Trigger inventory agent or cause a low-stock event
4. Go to `GET /api/v1/approvals/history`
5. **Expected**: New list with `approved_by: "orchestrator_auto"` and status `approved`

**Test B — Manual review (cost gate):**

1. Set `AUTO_APPROVE_LIMIT_INR=1` (₹1 limit — everything gets flagged)
2. Restart and trigger inventory agent
3. Go to `GET /api/v1/approvals/pending`
4. **Expected**: New list sitting in `pending` state (not auto-approved)
5. Check logs: `Shopping list flagged for manual approval: Total cost ₹X meets or exceeds...`

**Test C — Manual review (unknown supplier gate):**

1. Reset limit to `AUTO_APPROVE_LIMIT_INR=5000`
2. In Mongo, update an inventory item: `{ $set: { supplier_name: "" } }`
3. Trigger inventory agent so that item is included in a shopping list
4. **Expected**: List stays in `pending` — logs show "Unknown supplier for [item name]"

**Test D — PO per-item review (Option B):**

1. Get a pending shopping list ID from `GET /api/v1/approvals/pending`
2. POST to `POST /api/v1/approvals/purchase-orders/{id}/review`:
```json
{
  "items": [
    { "material_id": "MAT001", "action": "approve", "quantity": 10 },
    { "material_id": "MAT002", "action": "reject", "reason": "Price too high" }
  ]
}
```
3. **Expected**: Response shows `approved_items: 1`, `rejected_items: 1`, `pending_items: N`
4. List status should be `partially_approved`
5. Submit remaining items → status becomes `approved` or `rejected`

---

## Sanity Checks (run after all phases)

| Check | How | Expected |
|---|---|---|
| Startup resilience | `docker compose up` with MongoDB down | Backend starts with warnings, doesn't crash |
| TLS for remote DB | Set Atlas URI in `.env`, restart | Connection succeeds with certifi TLS |
| Notification TTL | Check `notifications` index | `expireAfterSeconds: 604800` (7 days) exists |
| Expiry special TTL | Check `expiry_specials` index | `expireAfterSeconds: 1209600` (14 days) exists |
| Dynamic reorder level | Check shopping list items | `dynamic_reorder_level` field present alongside `reorder_level` |