# Unified Owner Dashboard: Design & Architecture

## Problem Statement

Ahar currently has 6 disconnected surfaces showing restaurant data:
- `OperationsDashboardWidget` — 4 tabs, all hardcoded mock data
- `CommandDashboard` — real financial data, trapped as a chat overlay
- `FinancialDashboard` — real data, framed around agent alerts, not owner decisions
- `AnalyticsPage` — hardcoded
- `ReportsPage` — hardcoded
- `InsightsPage` — real AI analysis, standalone

No single place answers: *"How is my restaurant doing right now?"*

Agent notifications (low stock, pending POs, expiry specials) are planned as a separate bell/drawer system — which recreates fragmentation at the notification layer.

## Design Principle

**Agent alerts are not a sidebar. They are embedded in the section they belong to.**

Low stock appears in the stock section. A pending PO approval appears in the procurement section. The owner never context-switches between "looking at my data" and "responding to agent alerts." Visibility and action are the same surface.

---

## Three-Zone Layout

### Zone 1: Pulse Strip (always visible, pinned top)

Answers "Am I OK?" in 2 seconds. Non-scrollable.

| Metric | Source |
|---|---|
| Today's revenue | `orders` aggregation, `status != cancelled` |
| vs same day last week | Same query, 7 days ago |
| Food cost % | COGS from `profit_analysis_service` / today's revenue |
| Covers today | Count of completed orders |
| Avg ticket | Revenue / covers |
| Items needing attention | Count of pending Zone 2 cards |

When "items needing attention" = 0, shows: **"All clear"** — this is a positive signal, shown explicitly.

---

### Zone 2: Action Queue (what needs the owner right now)

Renders agent-generated items requiring a decision. Cards come from:
- `notifications` collection (Phase 4 of agent plan), filtered by `is_read: false` and `target_role: admin`
- `pending_approvals` / `shopping_list` where `status: pending_approval`
- `expiry_specials` where `status: pending_approval`

**Card types:**

#### Low Stock Alert Card
```
⚠ Tomatoes running low
2 kg left · Reorder at 5 kg (dynamic) · Used 8 kg yesterday
Agent suggests: Order 15 kg from FreshMart (₹450)
[Approve]  [Modify & Approve]  [Dismiss]
```
- Approve → inline, no navigation
- Modify → inline quantity edit, then confirm
- Dismiss → marks notification read, card disappears

#### PO Pending Approval Card (see full spec below)

#### Today's Special Suggestion Card
```
✦ Suggested Today's Special
Cream of Mushroom Soup · Fresh cream expires tomorrow
Discount: 15% · Est. waste saved: ₹280 · AI reasoning ↓
[Approve for Staff]  [Edit]  [Skip]
```

#### Revenue Anomaly Card
```
📉 Revenue below expected — 7 PM slot
₹420 actual vs ₹1,800 historical average (−77%)
Possible causes: staffing, kitchen delay, external event
[Acknowledge]  [View Pattern]
```

#### All Clear State (when queue is empty)
```
✅ All clear
3 orders auto-processed · No anomalies · Agents healthy
Last checked: 2 mins ago
```

---

### Zone 3: Intelligence Panels (scroll to understand)

Each panel shows real data and surfaces agent activity as context annotations — not separate alerts.

#### Menu Performance Panel
Sourced from `profit_analysis_service.get_top_items()`

| Item | Margin | Sales today | vs yesterday | |
|---|---|---|---|---|
| Chicken Burger | ₹180 | 23 orders | ↑ 8 | |
| Paneer Tikka | ₹95 | 6 orders | ↓ 12 | ← flagged |
| Dal Fry | ₹220 | 31 orders | → same | |

Agent annotations appear inline: *"Paneer Tikka down — kitchen time 34 min avg today vs 18 min usual"*

Sort options: by margin, by volume, by revenue contribution.

#### Stock Health Panel
Sourced from `raw_material_inventory`

| Item | Stock | Status | Agent activity |
|---|---|---|---|
| Tomatoes | 2 kg | 🔴 Critical | PO pending approval → links to Zone 2 card |
| Fresh Cream | 3 L | 🟡 Low | Auto-reordered 2hrs ago ✓ |
| Rice | 12 kg | 🟢 Good | |
| Chicken | 8 kg | 🟢 Good | |

Critical and Low items float to top. Agent activity shown as annotation on the row — not a separate notification.

#### P&L Snapshot Panel
Sourced from `profit_analysis_service` + `generate_pnl` logic

```
This week
Revenue          ₹1,24,000
COGS              ₹42,160  (34%)  ↑ from 31% last week
  Raw materials   ₹38,200
  Waste            ₹3,960  ← 3 items expired
Gross Margin     ₹81,840  (66%)
```

Plain-language callout: *"Waste cost ₹3,960 this week. Fresh cream expired twice — agent is now suggesting daily specials to prevent this."*

Link: "See full P&L →" opens InsightsPage or generates Excel export.

#### Revenue Pattern Panel
Sourced from `orders` aggregation by hour

Live bar chart: today's hourly revenue vs same-day-last-week average overlay.
Agent anomaly annotations on specific hours: *"7 PM: ₹420 actual vs ₹1,800 expected"*

---

## PO Approval: Progressive Disclosure Spec

### Interaction Model

The PO card has two states. No navigation. No modal. Accordion expand in-place.

**Collapsed:**
```
🕐 PO Pending Approval
5 items · ₹2,840 · FreshMart · requested 45 mins ago
[Approve All]  [Review Items ↓]
```

**Expanded (tap "Review Items"):**
```
🕐 PO Pending Approval · FreshMart

Item           Qty (editable)   Cost    Decision
─────────────────────────────────────────────────
Tomatoes       [15] kg          ₹450    [✓] [✗]
Fresh Cream    [10] L           ₹620    [✓] [✗]
Onions         [20] kg          ₹360    [✓] [✗]
Coriander      [ 5] kg          ₹180    [✓] [✗]
Butter         [ 3] kg          ₹460    [✓] [✗]

3 approved · 1 rejected · 1 pending
Approved total: ₹1,610

[Submit Decisions]  [Approve Remaining]
```

- Quantity is tappable inline — opens numeric input
- Reject shows quick-reason picker: Too expensive / Already have stock / Wrong supplier / Other
- "Approve Remaining" approves all items still in pending state
- "Submit Decisions" sends one API call — mixed state is valid

### Partial Approval Data Model (Option B)

**Decision: Single PO record with per-item status.**

PO record `status` field:
- `pending_approval` — all items awaiting decision
- `partially_approved` — mixed item decisions, submission not yet complete
- `approved` — all items approved (or remaining after rejections)
- `rejected` — all items rejected
- `completed` — supplier notified, order placed for approved items

Each item in the PO gains:
```json
{
  "material_id": "RM001",
  "material_name": "Tomatoes",
  "requested_quantity": 15,
  "approved_quantity": 15,
  "status": "approved",
  "rejection_reason": null,
  "decided_at": "2026-04-12T08:30:00Z",
  "decided_by": "user_id"
}
```

Supplier receives only `status: approved` line items. Rejected items stay on the same record for audit trail. Owner can always see: "I approved 3, rejected 2, here's why."

### Backend Endpoint

```
POST /approvals/purchase-orders/{po_id}/review
Authorization: ADMIN role required

Body:
{
  "items": [
    { "material_id": "RM001", "action": "approve", "quantity": 15 },
    { "material_id": "RM002", "action": "reject",  "reason": "Already have stock" },
    { "material_id": "RM003", "action": "approve", "quantity": 8 }
  ]
}

Response:
{
  "success": true,
  "data": {
    "po_id": "...",
    "status": "partially_approved",
    "approved_items": 2,
    "rejected_items": 1,
    "pending_items": 2,
    "approved_total_paise": 161000
  }
}
```

Partial submissions are valid — owner can approve 2 now, come back for the rest. Status becomes `partially_approved` until all items have a decision, then transitions to `approved` or `rejected`.

---

## Agent Plan Integration

How the autonomous agent phases (from AUTONOMOUS-AGENT-WORKFLOWS-NIELSEN-UX-PLAN.md) surface in this dashboard:

| Agent phase | Backend output | Dashboard surface |
|---|---|---|
| Phase 1: Low stock events | `inventory.low_stock` event → notification record | Zone 2 low stock card + Stock Health panel annotation |
| Phase 2: Revenue anomaly | `revenue.anomaly` event → notification record | Zone 2 revenue anomaly card + Revenue Pattern panel annotation |
| Phase 3: Expiry special | `expiry_specials` collection | Zone 2 Today's Special card |
| Phase 4: Notification system | `notifications` collection | Zone 2 reads from this collection directly |
| Phase 5: Approval thresholds | Auto-executed below threshold | Stock Health panel shows "auto-reordered" annotation; no Zone 2 card |

The notification bell icon still exists for when the owner is on *other* screens (kitchen, tables view). The dashboard is the primary consumption surface — not the bell.

---

## Frontend Consolidation

| Current file | Fate |
|---|---|
| `CommandDashboard.tsx` | Promoted — base of Zone 1 + Zone 2 real data |
| `OperationsDashboardWidget.tsx` | Replaced — Zone 3 panels with real data |
| `FinancialDashboard.tsx` | Merged into Zone 2 alerts + Zone 3 P&L panel |
| `AnalyticsPage.tsx` | Replaced by Zone 3 menu + revenue panels |
| `ReportsPage.tsx` | Zone 3 P&L snapshot replaces summary view |
| `InsightsPage.tsx` | Kept as deep-dive — linked from Zone 3 "See full analysis →" |

New files:
- `pages/OwnerDashboardPage.tsx` — main page, three-zone layout
- `components/dashboard/PulseStrip.tsx` — Zone 1
- `components/dashboard/ActionQueue.tsx` — Zone 2, renders typed cards
- `components/dashboard/ActionCards/LowStockCard.tsx`
- `components/dashboard/ActionCards/POApprovalCard.tsx` — collapsed + expanded states
- `components/dashboard/ActionCards/ExpirySpecialCard.tsx`
- `components/dashboard/ActionCards/RevenueAnomalyCard.tsx`
- `components/dashboard/MenuPerformancePanel.tsx` — Zone 3
- `components/dashboard/StockHealthPanel.tsx` — Zone 3
- `components/dashboard/PnLSnapshotPanel.tsx` — Zone 3
- `components/dashboard/RevenuePatternPanel.tsx` — Zone 3
- `services/ownerDashboard.ts` — aggregates API calls for the dashboard

---

## New Backend Endpoints Required

| Endpoint | Purpose | Data source |
|---|---|---|
| `GET /dashboard/pulse` | Zone 1 metrics (revenue, food cost %, covers, attention count) | `orders` + `profit_analysis_service` |
| `GET /dashboard/action-queue` | Zone 2 cards: pending notifications + approvals | `notifications` + `shopping_list` + `expiry_specials` |
| `POST /approvals/purchase-orders/{id}/review` | Partial/full PO approval with item-level decisions | `shopping_list` collection |
| `GET /dashboard/menu-performance` | Zone 3 menu panel: margin + sales per item | `profit_analysis_service.get_top_items()` |
| `GET /dashboard/stock-health` | Zone 3 stock panel: status + agent activity annotations | `raw_material_inventory` + `notifications` |
| `GET /dashboard/pnl-snapshot` | Zone 3 P&L panel: revenue, COGS, margin, waste | `profit_analysis_service` + `inventory_consumption_logs` |
| `GET /dashboard/revenue-pattern` | Zone 3 revenue panel: hourly today vs historical | `orders` aggregation |

All endpoints under `/api/v1/`. All require authentication. Zone 1 + Zone 2 endpoints should be fast (<200ms) — they're polled every 30s.

---

## Polling Strategy

| Zone | Poll interval | Why |
|---|---|---|
| Zone 1 (Pulse Strip) | 30s | Owner needs near-real-time revenue visibility during service |
| Zone 2 (Action Queue) | 30s | Agent alerts should surface quickly |
| Zone 3 panels | On mount + manual refresh | Historical data, doesn't change second-to-second |

Zone 3 panels have a refresh button and show "Last updated: 3 mins ago" — they don't auto-poll to avoid unnecessary computation load on the P&L and menu performance queries.
