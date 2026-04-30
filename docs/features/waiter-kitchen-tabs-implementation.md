# Waiter Tab & Kitchen Tab Implementation

**Type:** Feature  
**Priority:** High  
**Effort:** Large

## TL;DR

Implement the Waiter Tab for order creation (table selection + menu items) and Kitchen Tab for order workflow management (Waiting → Next Up → Complete). Remove table name text input, use dropdown only. No AI features in this phase.

## Current State

- ✅ Order models exist in backend (`backend/app/models/order.py`) with status workflow defined
- ✅ Menu and Tables pages are functional
- ✅ Tab navigation structure exists (`HomePage.tsx`, `TabNavigation.tsx`)
- ✅ **Backend order repository created** (`backend/app/repositories/order_repository.py`)
- ✅ **Backend order service created** (`backend/app/services/order_service.py`)
- ✅ **Backend order API endpoints created** (`backend/app/api/v1/orders.py`)
- ✅ **Frontend order types created** (`frontend/src/types/orders.ts`)
- ✅ **Frontend order service created** (`frontend/src/services/orders.ts`)
- ✅ **OrderCard component created** (`frontend/src/components/OrderCard.tsx`)
- ✅ **OrderItemSelector component created** (`frontend/src/components/OrderItemSelector.tsx`)
- ✅ **WaiterPage created** (`frontend/src/pages/WaiterPage.tsx`)
- ✅ **KitchenPage created** (`frontend/src/pages/KitchenPage.tsx`)
- ✅ **HomePage updated** to include WaiterPage and KitchenPage

## Expected Outcome

### Waiter Tab
- **Table Selection:** Dropdown only (remove text input field)
  - Shows table list with format: "Table {number} — {location}" (e.g., "Table 1 — Window Seat")
  - Required field before adding items
- **Menu Item Selection:**
  - Display menu items by category (similar to MenuPage layout)
  - Quantity selectors (+/-) for each item
  - Show running total/cart summary
  - Special instructions/notes field per item (optional)
- **Order Actions:**
  - "Send to Kitchen" button (creates order with status `SENT_TO_KITCHEN`)
  - Order appears in Kitchen's "Waiting" section immediately
  - Clear/reset form after sending

### Kitchen Tab
- **Two Sections:**
  - **"Waiting"** - Orders with status `SENT_TO_KITCHEN`
    - Display: Table number, wait time, order items, special notes
    - Action: "Start Cooking" button → moves to "Next Up" (status → `IN_PROGRESS`)
  - **"Next Up"** - Orders with status `IN_PROGRESS`
    - Display: Same as Waiting, but with "In Progress" badge
    - Actions: 
      - "Mark Complete" button → status → `COMPLETED`
      - "Move to Waiting" button (optional, for re-prioritization)
- **Order Cards:**
  - Table identifier (number/name)
  - Elapsed time since order sent
  - List of items with quantities
  - Special instructions/notes highlighted
  - Status badge (Waiting/In Progress)

## Relevant Files

### Backend
- `backend/app/api/v1/orders.py` (NEW - create order endpoints)
- `backend/app/repositories/order_repository.py` (NEW - database operations)
- `backend/app/services/order_service.py` (NEW - business logic)
- `backend/app/models/order.py` (EXISTS - verify status enums match requirements)

### Frontend
- `frontend/src/pages/WaiterPage.tsx` (NEW)
- `frontend/src/pages/KitchenPage.tsx` (NEW)
- `frontend/src/pages/HomePage.tsx` (UPDATE - add WaiterPage/KitchenPage to renderTabContent)
- `frontend/src/components/OrderCard.tsx` (NEW - reusable order display)
- `frontend/src/components/OrderItemSelector.tsx` (NEW - menu item + quantity selector)
- `frontend/src/services/orders.ts` (NEW - API client)
- `frontend/src/types/orders.ts` (NEW - TypeScript types)
- `frontend/src/pages/WaiterPage.css` (NEW)
- `frontend/src/pages/KitchenPage.css` (NEW)

## Implementation Notes

### Order Status Flow
```
DRAFT → SENT_TO_KITCHEN → IN_PROGRESS → COMPLETED
```

- Waiter creates order in `DRAFT` state (not visible to kitchen)
- "Send to Kitchen" transitions to `SENT_TO_KITCHEN` (visible in Waiting)
- "Start Cooking" transitions to `IN_PROGRESS` (moves to Next Up)
- "Mark Complete" transitions to `COMPLETED` (removed from active view)

### Table Selection
- Remove "Table Name" text input field completely
- Use only dropdown with format: `Table {table_number} — {location}`
- Dropdown should show all tables (or filter by status if needed)
- Store `table_id` in order, not table name

### Menu Item Selection
- Reuse menu item display from MenuPage (category grouping)
- Add quantity controls (+/- buttons with number display)
- Calculate total in real-time (client-side)
- Allow special instructions per item (notes field)
- Only show available items (`is_available: true`)

### Kitchen View
- Real-time updates (polling or WebSocket - start with polling)
- Calculate wait time: `(now - sent_to_kitchen_at)`
- Display items with quantities and notes
- Group by status (Waiting vs Next Up)
- Show count in section headers: "Waiting (3)", "Next Up (2)"

### Data Requirements
- Order must include:
  - `table_id` (from dropdown selection)
  - `items[]` with `menu_item_id`, `quantity`, `notes` (optional)
  - `total_amount` (calculated in cents)
  - `created_by_user_id` (from auth context)
  - `restaurant_id` (from user context)

## Risks & Dependencies

- **Multi-tenancy:** Ensure `restaurant_id` is properly set from user context
- **Order Numbering:** Need sequential order numbers (consider atomic counter or timestamp-based)
- **Real-time Updates:** Kitchen view needs refresh mechanism (start with polling, consider WebSocket later)
- **Menu Item Snapshots:** Order items should snapshot menu data (name, price) at order time
- **Table Status:** Consider updating table status to "occupied" when order is created
- **Error Handling:** Handle cases where menu item becomes unavailable between selection and order creation

## Out of Scope (This Phase)

- ❌ AI optimization features
- ❌ Order editing after sent to kitchen
- ❌ Order cancellation workflow
- ❌ Item-level status tracking (cooking/ready per item)
- ❌ WebSocket real-time updates
- ❌ Order history/archives
- ❌ Print/kitchen display integration

## Acceptance Criteria

- [x] Waiter can select table from dropdown (no text input)
- [x] Waiter can browse menu by category and add items with quantities
- [x] Waiter can add special instructions per item
- [x] Waiter can see running total
- [x] Waiter can send order to kitchen (status → SENT_TO_KITCHEN)
- [x] Kitchen sees order in "Waiting" section immediately
- [x] Kitchen can click "Start Cooking" to move order to "Next Up"
- [x] Kitchen can click "Mark Complete" to finish order
- [x] Kitchen can click "Move to Waiting" to re-prioritize orders
- [x] Order cards display table info, items, wait time, and notes
- [x] All API endpoints return proper error messages
- [x] Frontend handles loading and error states gracefully
- [x] Kitchen view polls every 5 seconds for updates
- [x] Table status updated to OCCUPIED when order is created
- [x] Order number generated using timestamp-based approach
- [x] Menu item validation (availability, existence, quantities)
- [x] Wait time calculated in backend and displayed in minutes

## Implementation Progress: 100% ✅

## Code Review Improvements ✅

### Code Quality Enhancements
- ✅ Fixed `useEffect` dependency issue in WaiterPage to prevent infinite loop
- ✅ Extracted table display logic in OrderCard to helper function for better readability
- ✅ Made polling interval configurable via environment variable (`VITE_KITCHEN_POLL_INTERVAL_MS`)
- ✅ Removed redundant error state reset in WaiterPage
- ✅ Added per-order loading states in KitchenPage to prevent double-clicks during actions
- ✅ Added documentation for double filtering in WaiterPage (active items + availability check)

### Backend Implementation ✅
- ✅ Order repository with database operations
- ✅ Order service with business logic and validation
- ✅ Order API routes with status transition endpoints
- ✅ Order number generation (timestamp-based)
- ✅ Menu item validation and snapshot creation
- ✅ Table status update on order creation
- ✅ Wait time calculation in backend
- ✅ Restaurant ID automatically set from authenticated user

### Frontend Implementation ✅
- ✅ Order TypeScript types and interfaces
- ✅ Order API service client
- ✅ OrderCard component for kitchen view
- ✅ OrderItemSelector component for waiter view
- ✅ WaiterPage with table selection and menu items
- ✅ KitchenPage with Waiting and Next Up sections
- ✅ Real-time polling (5 second interval)
- ✅ Error handling and loading states
- ✅ HomePage integration

### Key Features Implemented ✅
1. ✅ Table selection dropdown (no text input)
2. ✅ Menu items by category with quantity selectors
3. ✅ Special instructions per item
4. ✅ Running total calculation
5. ✅ Order creation and send to kitchen
6. ✅ Status transitions (DRAFT → SENT_TO_KITCHEN → IN_PROGRESS → COMPLETED)
7. ✅ Move to Waiting functionality (IN_PROGRESS → SENT_TO_KITCHEN)
8. ✅ Wait time display in minutes
9. ✅ Order cards with all required information
10. ✅ Kitchen view with automatic polling
