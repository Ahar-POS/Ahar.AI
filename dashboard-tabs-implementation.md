# Build Main Dashboard Tabs: Tables, Orders, Kitchen (KOT), and Menu Management

## TL;DR
Implement the four core dashboard tabs (Tables, Waiter/Orders, Kitchen/KOT, Menu) with full CRUD functionality, order flow from waiter → kitchen, and menu upload capability. Remove demo mode references from UI.

## Current State
- ✅ Tab navigation structure exists (Kitchen, Waiter, Tables, Menu tabs defined)
- ✅ All tabs currently show "Coming Soon" placeholder
- ❌ No backend APIs for tables, orders, menu items, or kitchen operations
- ❌ No frontend components for any of these features
- ❌ "Demo Mode" button visible in header (needs removal)
- ❌ No data models for tables, orders, menu items

## Expected Outcome
Four fully functional tabs:

### 1. Tables Management Tab
- Grid view of all tables with cards showing:
  - Table name/number and location identifier (e.g., "Table 1 — Window Seat")
  - Current status badge (Available, Occupied, Reserved, Closed/Maintenance)
  - Capacity indicator (number of seats)
  - Quick status toggle buttons (Available, Occupied, Reserved, Closed)
- Summary bar showing counts: Available, Occupied, Reserved
- "Add Table" button to create new tables
- Real-time status updates

### 2. Waiter/Orders Tab
- Two sub-tabs: "New Order" and "My Tables"
- **New Order:**
  - Table selection (Table Name input, Table Number dropdown)
  - Menu category tabs (Antipasti, Primi Piatti, Secondi Piatti, Pizze, Dolci, Bevande)
  - Menu items display with:
    - Item name, description, price
    - Quantity controls (+/- buttons)
    - Current quantity counter
  - Order summary/cart with total
  - Place order button (sends to Kitchen)
- **My Tables:**
  - List of tables assigned to waiter
  - View active orders per table
  - Ability to modify/cancel orders

### 3. Kitchen/KOT Tab
- Two sections: "Waiting" and "Next Up" (In Progress)
- Order cards showing:
  - Table number and wait time
  - Status badge (Waiting/In Progress)
  - List of items with quantities and special notes
  - Special instructions/notes (e.g., "Anniversary dinner - please add candle")
  - Action buttons:
    - "Start Cooking" (moves from Waiting → In Progress)
    - "Mark Complete" (removes from queue)
    - "Move to Waiting" (revert to waiting)
- Real-time order updates
- Optional: "AI Optimize" button for order prioritization

### 4. Menu Management Tab
- Header with:
  - Title "Menu Management"
  - Summary: "X items across Y categories"
  - "+ Add Item" button
- Category sections (e.g., Antipasti, Primi Piatti) with item counts
- Menu item cards showing:
  - Item name, description, price
  - Ingredient/tag pills
  - Preparation type badge (cold, fry, pasta, oven, etc.)
- Add/Edit item modal/form
- Menu upload functionality (CSV/JSON import)
- Category management

## Relevant Files

### Backend (New)
- `backend/app/models/table.py` - Table model (name, number, capacity, status, location)
- `backend/app/models/menu_item.py` - Menu item model (name, description, price, category, tags, prep_type)
- `backend/app/models/order.py` - Order model (table_id, items, status, special_notes, timestamps)
- `backend/app/repositories/table_repository.py` - Table CRUD operations
- `backend/app/repositories/menu_repository.py` - Menu item CRUD operations
- `backend/app/repositories/order_repository.py` - Order CRUD operations
- `backend/app/api/v1/tables.py` - Tables API endpoints
- `backend/app/api/v1/menu.py` - Menu API endpoints
- `backend/app/api/v1/orders.py` - Orders API endpoints
- `backend/app/api/v1/kitchen.py` - Kitchen/KOT API endpoints

### Frontend (New)
- `frontend/src/pages/TablesPage.tsx` - Tables management component
- `frontend/src/pages/WaiterPage.tsx` - Order taking component
- `frontend/src/pages/KitchenPage.tsx` - Kitchen view component
- `frontend/src/pages/MenuPage.tsx` - Menu management component
- `frontend/src/components/TableCard.tsx` - Table card component
- `frontend/src/components/MenuItemCard.tsx` - Menu item card component
- `frontend/src/components/OrderCard.tsx` - Order card component
- `frontend/src/components/OrderForm.tsx` - Order creation form
- `frontend/src/services/tables.ts` - Tables API service
- `frontend/src/services/menu.ts` - Menu API service
- `frontend/src/services/orders.ts` - Orders API service
- `frontend/src/services/kitchen.ts` - Kitchen API service
- `frontend/src/types/tables.ts` - Table TypeScript types
- `frontend/src/types/menu.ts` - Menu TypeScript types
- `frontend/src/types/orders.ts` - Order TypeScript types

### Frontend (Update)
- `frontend/src/pages/HomePage.tsx` - Remove "Demo Mode" button, wire up tab content
- `frontend/src/services/api.ts` - Add new service endpoints

## Implementation Notes

### Data Flow
1. **Order Flow:** Waiter creates order → Order saved with status "waiting" → Kitchen sees in "Waiting" → Kitchen starts cooking → Status "in_progress" → Kitchen marks complete → Order archived
2. **Table Status:** Real-time updates via WebSocket (future) or polling (initial)
3. **Menu Upload:** Support CSV/JSON import with validation and error handling

### Key Features
- Status management for tables (Available/Occupied/Reserved/Closed)
- Order items with quantities and special notes
- Kitchen order tickets (KOT) with timestamps and wait times
- Menu categorization and tagging system
- Responsive design matching existing UI patterns

### Design Consistency
- Match existing HomePage styling and color scheme
- Use orange/red accents for interactive elements
- Card-based layouts for items/tables/orders
- Pill-shaped badges for status indicators
- Consistent button styles and spacing

## Type
Feature

## Priority
High (core functionality for restaurant management)

## Effort
Large (8-12 hours)
- Backend models & APIs: 3-4 hours
- Frontend components: 4-5 hours
- Integration & testing: 1-2 hours
- Menu upload feature: 1 hour

## Dependencies
- ✅ Authentication system (exists)
- ✅ Database connection (exists)
- ❌ WebSocket for real-time updates (optional, can use polling initially)
- ❌ File upload handling (needed for menu import)

## Risks
- Real-time updates may require WebSocket implementation (can defer to polling)
- Menu upload needs file validation and error handling
- Order state management complexity (multiple status transitions)
- Concurrent order updates (optimistic locking may be needed)

## Acceptance Criteria
- [ ] Tables tab shows all tables with status management
- [ ] Waiter tab allows creating orders and selecting tables
- [ ] Kitchen tab displays orders in Waiting/In Progress sections
- [ ] Menu tab shows all items by category with add/edit capability
- [ ] Orders flow from Waiter → Kitchen correctly
- [ ] Menu upload functionality works (CSV/JSON)
- [ ] All demo mode references removed
- [ ] Responsive design works on mobile/tablet
- [ ] Error handling for API failures
- [ ] Loading states for async operations
