# Shopping List Approval API

## Overview

The Inventory Agent automatically generates daily shopping lists based on:
- Current inventory levels
- 7-day demand forecasts
- Reorder thresholds
- Supplier lead times
- Urgency classification (URGENT/STANDARD/LOW_PRIORITY)

Shopping lists require owner approval before execution.

## API Endpoints

All endpoints are under `/api/v1/approvals/` and require authentication (admin role).

### 1. Get Pending Shopping Lists

```http
GET /api/v1/approvals/pending
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "list_id": "SL_2026-02-27_093000",
      "generated_at": "2026-02-27T10:07:25.841000",
      "status": "pending",
      "total_cost_inr": 185000,
      "urgency_summary": {
        "urgent_count": 3,
        "standard_count": 2,
        "low_priority_count": 0
      },
      "item_count": 5
    }
  ],
  "message": "Found 1 pending shopping lists"
}
```

### 2. Get Shopping List Details

```http
GET /api/v1/approvals/{list_id}
```

**Response includes:**
- Complete item list with quantities, costs, urgency
- Supplier breakdown (grouped by supplier)
- Demand forecasts
- Days until stockout for each item

### 3. Approve Entire List

```http
POST /api/v1/approvals/{list_id}/approve
Content-Type: application/json

{
  "notes": "Approved for purchase"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/approvals/69a16cdd8f592ff6093f118c/approve \
  -H "Content-Type: application/json" \
  -H "Cookie: session_token=YOUR_TOKEN" \
  -d '{"notes": "Approved - all items needed"}'
```

### 4. Approve Specific Items (Partial Approval)

```http
POST /api/v1/approvals/{list_id}/approve-items
Content-Type: application/json

{
  "material_ids": ["RM001", "RM002"],
  "notes": "Approved urgent items only"
}
```

**Use case:** Owner wants to approve only URGENT items immediately and review STANDARD/LOW_PRIORITY items later.

**Result:**
- List status changes to `partially_approved`
- Approved items get `item_status: "approved"`
- Remaining items stay `item_status: "pending"`

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/approvals/69a16dbf0170f013c408493a/approve-items \
  -H "Content-Type: application/json" \
  -H "Cookie: session_token=YOUR_TOKEN" \
  -d '{
    "material_ids": ["RM020", "RM021"],
    "notes": "Approved urgent items only"
  }'
```

### 5. Reject Shopping List

```http
POST /api/v1/approvals/{list_id}/reject
Content-Type: application/json

{
  "notes": "Not needed at this time"
}
```

### 6. Get Approval History

```http
GET /api/v1/approvals/history?page=1&limit=20&status=approved
```

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20, max: 100)
- `status`: Filter by status (pending/approved/rejected/partially_approved)

### 7. Get Approval Statistics

```http
GET /api/v1/approvals/stats
```

**Response:**
```json
{
  "success": true,
  "data": {
    "pending": 0,
    "approved": 1,
    "rejected": 1,
    "partially_approved": 1,
    "total": 3
  }
}
```

## Shopping List Structure

### Urgency Levels

1. **URGENT** - Stockout within lead_time + 1 day
   - Action: Order TODAY
   - Example: Item runs out in 0.5 days, supplier lead time is 2 days

2. **STANDARD** - Stockout within 7 days OR perishable items
   - Action: Order this week
   - Example: Item runs out in 4 days OR is perishable

3. **LOW_PRIORITY** - Stockout >7 days AND non-perishable
   - Action: Weekly digest / bulk order
   - Example: Non-perishable item with 15 days of stock remaining

### Item Data

Each item includes:
- `material_id`, `material_name`, `category`
- `current_stock`, `reorder_level`, `quantity_to_order`
- `unit_cost_inr`, `line_total_inr`
- `urgency`, `urgency_reason`
- `days_until_stockout`
- `daily_demand`, `total_demand_next_week`
- `supplier_id`, `supplier_name`, `lead_time_days`
- `is_perishable`, `shelf_life_days`
- `item_status`: pending/approved/rejected

### Supplier Breakdown

Items are grouped by supplier for batch ordering:

```json
{
  "supplier_id": "SUP002",
  "supplier_name": "Meats R Us",
  "item_count": 2,
  "total_cost_inr": 35000,
  "items": ["RM002", "RM003"]
}
```

## Testing Scripts

For testing without authentication, use these scripts in the backend container:

### View Pending Lists
```bash
docker exec ahar-backend python get_shopping_list.py
```

### Approve List
```bash
docker exec ahar-backend python approve_shopping_list.py
```

### Partial Approval Demo
```bash
docker exec ahar-backend python partial_approve_demo.py
```

## Agent Trigger

To manually trigger the inventory agent:

```bash
curl -X POST http://localhost:8000/api/v1/health/trigger-agent/inventory
```

**Note:** Agent runs automatically daily at 6:00 AM (configured in orchestrator).

## Database Collections

- `shopping_lists` - All generated shopping lists
- `agent_decisions` - Agent execution logs
- `raw_material_inventory` - Current inventory levels
- `demand_forecasts` - 7-day demand predictions

## Example Workflow

1. **Daily at 6 AM**: Inventory agent runs automatically
   - Checks all inventory items
   - Gets demand forecasts
   - Calculates urgency
   - Generates shopping list with status `pending`

2. **Owner reviews**: Via `/api/v1/approvals/pending`
   - Views items grouped by urgency
   - Sees supplier breakdown
   - Reviews costs and stockout warnings

3. **Owner approves**:
   - Option A: Approve all items (`/approve`)
   - Option B: Approve only urgent items (`/approve-items`)
   - Option C: Reject list (`/reject`)

4. **Next steps** (future implementation):
   - Generate purchase orders from approved items
   - Send to suppliers
   - Track delivery status
   - Update inventory upon receipt

## Current Demo Status

✅ Inventory Agent configured and working (when API has credits)
✅ Shopping list generation with urgency classification
✅ Full approval workflow
✅ Partial approval workflow
✅ Approval history and statistics
✅ Supplier grouping
✅ Cost calculations

**Currently demonstrated:**
- Manual shopping list creation
- Full approval: `SL_2026-02-27_093000` (approved)
- Partial approval: `SL_2026-02-27_PARTIAL` (2 items approved, 2 pending)
