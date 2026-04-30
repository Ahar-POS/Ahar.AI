# ADR-008: Shopping List Approval UX — Permanent Panel, Owner Modal, Hyperpure Orders Page

**Date**: 2026-04-29
**Status**: Accepted
**Decider**: Pandiarajan + Voj
**Context**: Owner-facing approval workflow for Inventory Agent shopping lists — replacing the Trello card pattern with a permanent widget and dedicated review modal.

---

## Problem

The original Action Queue (ADR-004) treated PO approval as a Trello-style card that appeared when a new shopping list was generated and disappeared when it was acted on. This created three problems:

1. **Wrong mental model**: The shopping list is a *living document* — the Inventory Agent updates it on every run, adjusting quantities as demand changes. Treating it as a transient card implied it was a one-off alert, not the current state of "what the restaurant needs to buy."
2. **Reasoning hidden from owner**: The LLM-based auto-approval layer (ADR-007) generates a per-item reason for each classification decision. This reasoning was stored in MongoDB but had no display surface — the owner couldn't see *why* 23 items were escalated.
3. **Verbose notifications**: Notification bell messages included full item lists, costs, and LLM rationale — too much for a scanning widget designed for quick triage.

The ApprovalsPage was also named and framed as an "approval queue" — but with the dashboard modal handling the actual approval workflow, the page should instead serve as a read-only PO tracking surface ("did the order go through? was it delivered?").

---

## Decisions Made

### Decision: Shopping List as permanent panel widget in Action Queue (not a Trello card)

- **Chosen**: `ShoppingListPanel` is a fixed component rendered above the Trello board in Zone 2 of the owner dashboard. It is always visible regardless of whether there are pending items. When there are pending items: shows badge count, top-3 preview rows (name, urgency tag, Hyperpure price), and a "Review →" button. When empty: shows "No active shopping list" or "All items approved" state.
- **Rejected**: Keeping the PO Approval Trello card; a standalone page reached via navigation; an expandable section inside the Trello board.
- **Reason**: The shopping list is the single most important recurring action item for a restaurant owner. Making it a permanent widget communicates that it is always their current shopping list, not one of many equal alerts. A badge on a permanent widget is also a cleaner signal for "something needs your attention" than a card that appears and disappears.

### Decision: Full approval popup modal with per-item LLM reasoning visible

- **Chosen**: Clicking "Review →" opens `ShoppingListModal` — a scrollable popup showing all escalated items. Each item row displays: name, urgency tag, quantity + unit, Hyperpure price, days until stockout, and the agent's reason string (from `item.agent_reason`, e.g. *"Price 2.4× baseline (₹200 avg)"*). Per-item approve/reject toggles with reject-reason picker. Bulk "Approve All & Order" fires immediately.
- **Rejected**: Inline editing in the panel widget; a separate page for item review; hiding LLM reasoning unless explicitly expanded.
- **Reason**: The owner's key question when reviewing is "why is this here?". Showing the LLM reason tag on each item answers that immediately — the owner can scan reasons and decide in seconds rather than inferring from price or urgency alone. A modal (not a page) keeps the owner in context of the dashboard and allows quick dismiss if they want to return to Zone 1/3.

### Decision: Owner approval triggers immediate Hyperpure order

- **Chosen**: When the owner approves items in the modal (`POST /approvals/{list_id}/approve-items`), the orchestrator immediately calls `execute_approved_order()` and places the Hyperpure order without any additional confirmation step or scheduling delay.
- **Rejected**: Queuing approved items for the next agent run (6 AM batch); showing a "place order" button as a second step after approval.
- **Reason**: If the owner is reviewing the shopping list at 2 PM and approves urgent items, they need those items ordered *now*, not at next morning's scheduled run. A second "place order" button adds a step that serves no purpose — the owner's intention is unambiguous when they hit "Approve."

### Decision: ApprovalsPage renamed to "Hyperpure Orders" with read-only PO tracking focus

- **Chosen**: The page title changes to "Hyperpure Orders". Navigation label in `SettingsScreen` changes from "Approvals" to "Hyperpure Orders". Tabs renamed: "Pending" → "Open Orders", "History" → "Order History". The page's role shifts to *tracking* (was this order placed? delivered?) rather than *approving* (the modal now owns approval).
- **Rejected**: Deleting the page entirely; keeping the name "Approvals" with the old pending-first tab layout.
- **Reason**: Owners still need a surface to check the status of orders placed by the agent — especially to see which auto-approved orders went through and which were delivered. "Hyperpure Orders" is the correct mental model: this is a log of what was ordered, not a queue of what needs deciding. The underlying data model is unchanged; only the framing and tab labels change.

### Decision: Hyperpure Orders page reads from `purchase_orders` collection, not shopping lists (2026-04-29)

- **Chosen**: `ApprovalsPage.tsx` was fully rewritten (~160 lines). It calls `GET /approvals/hyperpure-orders` which queries `purchase_orders` where `source = "hyperpure"`. Tabs: "Open Orders" (`status: "pending"`) and "Delivered" (`status: "fully_received"`). Each card shows: Hyperpure ref, ordered-at timestamp, item count, total cost, status badge. Items are expandable inline. No approval controls — completely read-only.
- **Rejected**: Keeping the old page that queried shopping lists via `getPendingApprovals()`; adding a filter to the existing approval history tab.
- **Reason**: The prior implementation queried shopping lists (pending/partially_approved) — those are the input to ordering, not the output. A PO tracking page must show actual placed orders. Since ADR-007 now writes proper PO documents to `purchase_orders` on every Hyperpure order, the correct data source is that collection. The complete rewrite removed all approval workflow code (ConfirmModal, selectedItems, notes, stats tab) that belonged to the old mental model.

### Decision: `HYPERPURE_USE_MOCK` route guard prevents delivery simulation in production (2026-04-29)

- **Chosen**: `_mock_deliver_after_delay` is only scheduled when `os.getenv("HYPERPURE_USE_MOCK", "true").lower() != "false"`. In production (real Playwright mode), delivery confirmation remains a manual staff action via `POST /confirm-delivery`.
- **Rejected**: Always running the simulation; a separate `MOCK_DELIVERY_ENABLED` env var.
- **Reason**: Inventory is the most sensitive data in the system — incorrect stock levels cause immediate operational failures (ordering items already in stock, not ordering items that are out). Gating the simulation on the same env var as the mock client means the two always move together: real Playwright + real delivery = no simulation. The flag was already used in `get_hyperpure_client()` so no new configuration surface is introduced.

### Decision: Unit cost displayed using `formatInventoryQuantity` with automatic scaling (2026-04-29)

- **Chosen**: `ShoppingListModal` and `ShoppingListPanel` use `formatInventoryQuantity(quantity, unit, unit_cost_inr)` from `inventoryUnits.ts` instead of manual `(unit_cost_inr / 100).toFixed(0)`. This function applies a `costFactor` (×1000 for gram→kg, ×1000 for mL→L) and returns a pre-formatted `costPerUnit` string (e.g. "₹600.00/kg").
- **Rejected**: Computing the scaled price inline in JSX; a separate utility function for price scaling.
- **Reason**: The raw DB value `unit_cost_inr = 60` is paise-per-gram for Chicken. `60 / 100 = ₹0.60/gram` rounds to ₹1, then the display unit was "kg" (because the quantity was ≥1000g) — producing the nonsensical "₹1/kg". `formatInventoryQuantity` already has the correct scaling logic (`costFactor = 1000` when gram → kg) — it just wasn't being used for the price display. Reusing it eliminates the display inconsistency and ensures the price unit always matches the quantity unit shown alongside it.

### Decision: Escalated items only shown in the panel and modal (not auto-approved items)

- **Chosen**: `ShoppingListPanel` and `ShoppingListModal` filter to items with `item_status` in `{pending_review, pending}` only. Auto-approved items (already ordered) are not shown in the dashboard widget.
- **Rejected**: Showing all items including auto-approved ones with a status badge.
- **Reason**: Auto-approved items require no owner action — showing them alongside pending items would dilute the signal and increase cognitive load. The owner can see auto-approved orders in "Hyperpure Orders" page if they want to audit them. The badge count on the panel widget should mean exactly "number of items waiting for you" — not "total items in the list."

---

## Decisions Rejected / Deferred

### Deferred: Batch vs urgent ordering
- **Reason**: Hyperpure likely has a minimum order value below which placing an individual order is uneconomical (e.g. ordering only coriander leaves). The right policy — whether to batch small approvals with the next agent run vs place an urgent order immediately — depends on Hyperpure's actual minimum order rules, which require a conversation with the restaurant owner who operates with a real Hyperpure account. Deferred until first live onboarding. The deferred design sketch: owner sees an "Urgent" vs "Add to next batch" toggle per item; the agent factors this into its scheduling logic.

### Rejected: Displaying auto-approved items in the dashboard widget
- **Reason**: The widget is an action surface, not an information surface. Auto-approved items are already handled — showing them creates noise without enabling any action.

---

## Known Limitations

| Issue | Impact | Path forward |
|---|---|---|
| `ShoppingListPanel` polls via `getPendingApprovals()` independently of the Zone 2 polling cycle | Minor: up to 2 separate API calls to the approvals endpoint per 30s cycle | Lift shopping list state into `OwnerDashboard` polling loop and pass down as a prop |
| `agent_reason` field relies on orchestrator writing it into each shopping list item at upsert time | If orchestrator is updated without writing `agent_reason`, the field silently disappears from UI | Add `agent_reason` as an explicit field in `ShoppingListItem` Pydantic model if/when one is created |
| ~~ApprovalsPage "Open Orders" tab still shows pending-status lists (not all Hyperpure orders)~~ | **Resolved 2026-04-29** — page fully rewritten to read from `purchase_orders` with `source: "hyperpure"` filter | — |
| `ShoppingListPanel` disappears when `getPendingApprovals()` returns empty (all items approved) | Panel visible only when pending items exist — wrong for a "permanent widget" | **Resolved 2026-04-29** — when API returns 0 lists, panel keeps last known list state and shows "All items approved" |

---

## Output / Affected Files

| File | What changed or was created |
|---|---|
| `frontend/src/components/dashboard/ShoppingListPanel.tsx` | **New** — permanent widget with badge, preview rows, "Review →" trigger |
| `frontend/src/components/dashboard/ShoppingListModal.tsx` | **New** — full approval modal with per-item LLM reason tags, approve/reject toggles, bulk approve |
| `frontend/src/components/dashboard/ActionQueue.tsx` | Removed `POApprovalCard` column; added `ShoppingListPanel` above board; `po_approval` cards silently skipped in `groupCards()` |
| `frontend/src/pages/ApprovalsPage.tsx` | **Fully rewritten 2026-04-29** — now a read-only Hyperpure PO tracker. All approval workflow code removed. Reads from `GET /approvals/hyperpure-orders`. Two tabs: Open Orders / Delivered. Expandable item table per PO using `formatInventoryQuantity` for costs. |
| `frontend/src/pages/screens/SettingsScreen.tsx` | Nav label "Approvals" → "Hyperpure Orders" |
| `frontend/src/types/approvals.ts` | `ItemStatus` union expanded to include all backend statuses; `agent_reason` and `agent_decision` added to `ShoppingListItem` |
| `frontend/src/components/OwnerDashboard.css` | Added CSS for `sl-panel`, `sl-modal`, urgency tags, decision buttons, `action-queue-content` layout |

---

## Next Decisions Pending

1. **Batch vs urgent ordering policy** — needs real Hyperpure minimum order knowledge from owner. When resolved, add an "Urgent / Batch" toggle to `ShoppingListModal` and wire the agent's scheduling logic accordingly.
2. **Panel polling consolidation** — decide whether `ShoppingListPanel` should fetch independently or share the Zone 2 polling loop in `OwnerDashboard`.
3. ~~**Open Orders tab completeness**~~ — **Resolved 2026-04-29**. "Hyperpure Orders" page now reads from `purchase_orders` directly.
4. **Delivery confirmation surface** — where does the store keeper confirm delivery in production (no mock simulation)? Currently requires navigating to "Hyperpure Orders" page; consider a dedicated Delivered tab action or a mobile-friendly quick-confirm flow.
5. **Notification timestamp display** — `formatAge` (relative "9h ago") was causing confusion when events just happened; replaced with `formatTimestamp` showing absolute date/time in `en-IN` locale. Pending: decide whether to show both ("29 Apr, 10:35 am · just now") for context or absolute-only (current).
