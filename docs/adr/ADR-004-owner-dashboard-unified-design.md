# ADR-004: Owner Dashboard — Unified 3-Zone Design

**Date**: 2026-04-14
**Status**: Accepted (backend implemented; frontend implemented)
**Decider**: Pandiarajan
**Context**: Frontend architecture and owner-facing dashboard — consolidating 6 disconnected surfaces into one unified view

---

## Problem

The owner-facing side of Ahar had 6 separate surfaces with no shared context:
`OperationsDashboardWidget`, `CommandDashboard`, `FinancialDashboard`, `AnalyticsPage`, `ReportsPage`, `InsightsPage`. An owner checking on the restaurant had to navigate across all of them to answer three basic questions: *Is today going well? What needs my attention right now? Why?*

The autonomous agent system (ADR-003) further amplified this problem — agent alerts, shopping list approvals, and Today's Special suggestions had nowhere natural to land.

---

## Decisions Made

### Decision: 3-zone layout replacing all 6 surfaces

- **Chosen**: Single `CommandCenterScreen` with three vertically stacked zones:
  - **Zone 1 — Pulse Strip** (always pinned): today's revenue vs same day last week, food cost %, covers today, avg ticket, items needing attention count, explicit "All clear" signal when nothing requires action
  - **Zone 2 — Action Queue**: agent-generated items requiring owner decision — Low Stock Alert Cards, PO Pending Approval Cards (collapsed + expanded with inline editing), Today's Special Suggestion Cards, Revenue Anomaly Cards, All Clear state
  - **Zone 3 — Intelligence Panels** (scroll): Menu Performance, Stock Health, P&L Snapshot, Revenue Pattern
- **Rejected**: Adding a new standalone `OwnerDashboardPage` route — unnecessary route split when `CommandCenterScreen` already owns the owner view
- **Reason**: The three zones map directly to the three cognitive modes an owner uses: quick health check (Zone 1), triage (Zone 2), deep dive (Zone 3). A single screen eliminates navigation between surfaces.

---

### Decision: Delete CommandDashboard component — absorb into CommandCenterScreen

- **Chosen**: `frontend/src/components/CommandDashboard.tsx` deleted. Its responsibility absorbed into `CommandCenterScreen.tsx` directly, which now renders the 3-zone layout.
- **Rejected**: Keeping CommandDashboard as a sub-component — it was a redundant wrapper with no clear boundary from CommandCenterScreen.
- **Reason**: The component had grown into a page-level concern. Keeping it as a "component" created confusion about where logic should live. Single-responsibility: the screen owns its layout.

---

### Decision: Backend dashboard service aggregating all zone data

- **Chosen**: New `dashboard_service.py` + `dashboard.py` API layer with dedicated endpoints per zone:

| Endpoint | Zone | Polling |
|---|---|---|
| `GET /dashboard/pulse` | Zone 1 — Pulse Strip | Every 30 s |
| `GET /dashboard/action-queue` | Zone 2 — Action Queue | Every 30 s |
| `GET /dashboard/menu-performance` | Zone 3 — Intelligence | On mount + manual |
| `GET /dashboard/stock-health` | Zone 3 — Intelligence | On mount + manual |
| `GET /dashboard/pnl-snapshot` | Zone 3 — Intelligence | On mount + manual |
| `GET /dashboard/revenue-pattern` | Zone 3 — Intelligence | On mount + manual |

- **Rejected**: Having the frontend call each underlying service endpoint directly (approvals, inventory, orders, financial) — too many round trips and no unified aggregation point.
- **Reason**: The dashboard service acts as a read-side aggregator. It calls existing repositories without adding new business logic. Zone 1/2 poll every 30 s (real-time feel); Zone 3 only reloads on mount or explicit refresh (stable reference data).

---

### Decision: PO approval progressive disclosure — collapsed + expanded inline

> ⚠️ **Superseded by ADR-008 (2026-04-29).** The PO Approval Trello card has been removed from the Action Queue board. Shopping list approval is now a permanent panel widget with a dedicated modal. See ADR-008.

- **Chosen** _(original)_: PO cards in Zone 2 use progressive disclosure:
  - **Compact (board tile)**: `SL_094941 · ₹6.0L · 5 pending` (gist-only)
  - **Detail (click-to-open)**: a focused detail view shows Approve All / Review Items and then expands into per-item rows with approve/reject toggle, quantity edit field, quick-reason picker (price too high / not needed / wrong item / other)
  - Partial submission supported — undecided items stay pending across shifts
- **Rejected**: Always-expanded PO editing inside the board column by default — too much density in Zone 2 when multiple categories are active.
- **Reason** _(original)_: Zone 2 is triage-first. Trello-style columns improve scanability, while click-to-open detail preserves a clean queue and still supports deep actioning when needed.
- **Why superseded**: The shopping list is a living document that the agent updates on every run — treating it as a transient Trello card that appears and disappears created confusion about the current state of items. A permanent widget conveys that "this is always your shopping list" rather than "an alert arrived." See ADR-008 for the full replacement design.

---

### Decision: Polling strategy — Zone 1/2 at 30 s, Zone 3 on mount only

- **Chosen**: Zones 1 and 2 poll every 30 s using `setInterval` in the screen component. Zone 3 panels load once on mount with a manual "Refresh" affordance.
- **Rejected**: WebSocket for real-time push — over-engineered for a single-restaurant tool where 30 s latency is acceptable.
- **Reason**: Notifications already use 30 s polling (ADR-003). Matching the interval keeps network load predictable. Zone 3 data (P&L snapshots, menu performance) doesn't change faster than the refresh cycle.

---

### Decision: Frontend notification service as a separate file

- **Chosen**: `frontend/src/services/notifications.ts` — dedicated API client for notification endpoints (list, unread-count, mark-read, mark-all-read). `AppNavBar.tsx` updated to render notification bell with unread badge using this service.
- **Rejected**: Inline fetch calls inside AppNavBar — harder to test and reuse.
- **Reason**: Consistent with the pattern in `services/` — one file per resource. Bell state can be shared across components via context in a future iteration.

---

## Decisions Rejected / Deferred

### Rejected: New top-level route `/owner-dashboard`
- **Reason**: CommandCenterScreen already serves the owner. Adding a new route would split navigation. The existing screen was extended in place.

### Deferred: Today's Special approval card in Action Queue (Resolved)
- **Resolution**: Implemented in Zone 2 as a compact board tile with a click-to-open detail view for approve/reject.

### Deferred: Revenue Anomaly card in Action Queue (Resolved)
- **Resolution**: Implemented in Zone 2 as a compact board tile with a click-to-open detail view. Stale alerts are visually muted and older alerts are filtered to reduce clutter.

### Deferred: Intelligence Panel components (Zone 3) (Resolved)
- **Resolution**: Implemented as tabbed panels (Menu Performance, Stock Health, P&L Snapshot, Revenue Pattern).

---

## Known Limitations

| Issue | Impact | Path forward |
|---|---|---|
| Revenue anomaly lifecycle not persisted | Dismissed alerts return on next refresh/reload | Add a backend endpoint to dismiss/ack alerts persistently, or store dismiss state per-user in DB |
| `ownerDashboard.ts` service exists but Zone 3 endpoints may return stubs | Dashboard data may be incomplete until `dashboard_service.py` aggregation is fully implemented | Audit `dashboard_service.py` for placeholder vs real implementations |

---

## Output / Affected Files

| File | What changed or was created |
|---|---|
| `backend/app/api/v1/dashboard.py` | **New file**. 6 endpoints for pulse, action-queue, and 4 intelligence panels. |
| `backend/app/services/dashboard_service.py` | **New file**. Read-side aggregator: calls inventory, orders, approvals, financial repositories. |
| `backend/app/api/v1/__init__.py` | Registered `dashboard_router` at `/dashboard` prefix. |
| `frontend/src/pages/screens/CommandCenterScreen.tsx` | Modified — 3-zone layout, 30 s polling for Zones 1/2, ownerDashboard service calls. |
| `frontend/src/components/CommandDashboard.tsx` | **Deleted** — absorbed into CommandCenterScreen. |
| `frontend/src/components/CommandDashboard.css` | **Deleted** — styles merged into CommandCenterScreen or global CSS. |
| `frontend/src/services/ownerDashboard.ts` | **New file**. API client for all dashboard endpoints. |
| `frontend/src/services/notifications.ts` | **New file**. API client for notification endpoints. |
| `frontend/src/components/AppNavBar.tsx` | Modified — notification bell with unread count badge added. |

---

## Next Decisions Pending

1. **Today's Special card** — component design: does it show ingredient list + suggested dish name + approve/reject buttons? Should the chef name appear as the "owner" of the decision?
2. **Revenue Anomaly card** — what information density? Current-hour revenue vs historical average + severity badge sufficient, or should it link to Revenue Pattern panel?
3. **Zone 3 panel stubs vs real data** — audit `dashboard_service.py` to confirm which panel endpoints are returning real aggregated data vs placeholders; prioritise completing the ones with the most decision value (P&L Snapshot likely highest).
4. **Notification context provider** — bell unread count is currently fetched inside AppNavBar; if other components need unread state, lift to a React context to avoid duplicate polling.
5. **P&L chatbot integration point** — the P&L chatbot (see `skills/pnl-statement/`) generates Excel reports; does the P&L Snapshot panel in Zone 3 replace or complement this? Define the boundary.
