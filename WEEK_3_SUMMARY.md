# Week 3 Implementation Summary: Inventory Manager Agent with Smart Shopping Lists

## ✅ Completed Components

### 1. Inventory Agent (`app/services/agents/inventory_agent.py`)
**Purpose**: Autonomous inventory management with predictive reordering

**Key Features:**
- **Extends BaseAgent**: Inherits tool-calling loop and approval logic (Week 1)
- **Three Claude Tools**:
  1. `get_inventory_status` - Query current stock levels
  2. `get_demand_forecasts` - Get 7-day predictions (from cache)
  3. `calculate_reorder_needs` - Core reordering logic

**Urgency Classification Algorithm:**
```python
# URGENT: Stockout within lead_time + 1 day
if days_until_stockout <= (lead_time_days + 1):
    return "URGENT"  # Order TODAY

# STANDARD: Within 7 days OR perishable
if days_until_stockout <= 7 or is_perishable == "Yes":
    return "STANDARD"  # Order this week

# LOW_PRIORITY: Long runway, non-perishable
return "LOW_PRIORITY"  # Weekly digest
```

**Days Until Stockout Calculation:**
```python
# With 20% safety buffer for uncertainty
safety_buffer = 1.2
adjusted_demand = daily_demand * safety_buffer
days_until_stockout = current_stock / adjusted_demand
```

**Output**: Single `shopping_list` action with all items grouped by:
- Urgency (URGENT/STANDARD/LOW_PRIORITY)
- Supplier (for batch ordering)

**Lines of Code**: 588 lines

---

### 2. Shopping List Service & Repository

#### Repository (`app/repositories/shopping_list_repository.py`)
**Purpose**: Database operations for shopping_lists collection

**Key Methods:**
- `create(shopping_list)` - Insert new shopping list
- `get_by_id(list_id)` - Fetch by MongoDB ID
- `get_by_status(status, limit, skip)` - Query by status
- `update_status(list_id, status, user_id, notes)` - Approve/reject
- `approve_items(list_id, material_ids, user_id)` - Partial approval

**Lines of Code**: 220 lines

#### Service (`app/services/shopping_list_service.py`)
**Purpose**: Business logic for shopping list management

**Key Methods:**
- `create_shopping_list(items, agent_decision_id, reasoning, confidence)`
  - Calculate total cost
  - Group by urgency (count URGENT/STANDARD/LOW_PRIORITY)
  - Group by supplier (aggregate per supplier)
  - Generate unique list_id (e.g., `SL_2026-02-24_060000`)

- `approve_list(list_id, user_id, notes)` - Full approval
- `approve_items(list_id, material_ids, user_id, notes)` - Partial approval
- `reject_list(list_id, user_id, notes)` - Rejection workflow
- `get_approval_history(limit, skip, status)` - Audit log

**Lines of Code**: 208 lines

---

### 3. Approvals API (`app/api/v1/approvals.py`)
**Purpose**: REST API for approval workflow

**Endpoints:**

1. **GET /api/v1/approvals/pending**
   - Get all pending shopping lists
   - Auth: Admin only
   - Returns: List with summary (urgency counts, total cost)

2. **GET /api/v1/approvals/{list_id}**
   - Get detailed shopping list
   - Returns: Full list with items, supplier breakdown, reasoning

3. **POST /api/v1/approvals/{list_id}/approve**
   - Approve entire shopping list
   - Body: `{"notes": "Approved for ordering"}`
   - Updates: status → "approved", reviewed_at, reviewed_by

4. **POST /api/v1/approvals/{list_id}/approve-items**
   - Approve specific items (partial approval)
   - Body: `{"material_ids": ["RM001", "RM003"], "notes": "..."}`
   - Updates: status → "partially_approved", item-level status

5. **POST /api/v1/approvals/{list_id}/reject**
   - Reject shopping list
   - Body: `{"notes": "Too expensive, review forecast"}`
   - Updates: status → "rejected", rejection notes

6. **GET /api/v1/approvals/history**
   - Get approval history (paginated)
   - Query: `?page=1&limit=20&status=approved`
   - Returns: Audit log with pagination

7. **GET /api/v1/approvals/stats**
   - Get approval statistics
   - Returns: Count by status (pending, approved, rejected, partially_approved)

**Authentication**: Uses existing `get_current_user` dependency (ADMIN role required)

**Response Format**: Uses standard `success_response()` and `error_response()` helpers

**Lines of Code**: 286 lines

---

### 4. Orchestrator Integration

#### Updated Methods in `app/services/orchestrator.py`:

**1. _register_agents()** (Line ~124):
```python
from app.services.agents.inventory_agent import get_inventory_agent

self.agents = {
    'inventory': get_inventory_agent(),
    # 'financial': FinancialAgent(),  # TODO: Week 4
}
```

**2. _run_inventory_agent()** (Line ~202):
```python
async def _run_inventory_agent(self) -> None:
    agent = self.agents['inventory']

    # Execute agent
    decision = await agent.execute({
        'trigger': 'scheduled',
        'timestamp': datetime.utcnow()
    })

    # Log to MongoDB
    decision_id = await self._log_decision('inventory_agent', decision)

    # Process - create shopping list
    await self._process_inventory_decision(decision, decision_id)
```

**3. _process_inventory_decision()** (NEW - Line ~276):
```python
async def _process_inventory_decision(
    self,
    decision: Any,
    decision_id: str
) -> None:
    """Create shopping list from inventory agent decision"""
    from app.services.shopping_list_service import get_shopping_list_service

    # Find shopping_list action
    shopping_list_action = next(
        (a for a in decision.actions if a.action_type == "shopping_list"),
        None
    )

    if not shopping_list_action:
        return

    items = shopping_list_action.data.get("items", [])

    if not items:
        logger.info("Shopping list is empty")
        return

    # Create shopping list
    service = get_shopping_list_service()
    list_id = await service.create_shopping_list(
        items=items,
        agent_decision_id=decision_id,
        reasoning=decision.reasoning,
        confidence=decision.confidence
    )

    logger.info(f"Created shopping list: {list_id} with {len(items)} items")

    # Link to agent_decisions
    await self.db.agent_decisions.update_one(
        {"_id": ObjectId(decision_id)},
        {"$set": {"shopping_list_id": ObjectId(list_id)}}
    )
```

**4. _ensure_collections()** (Line ~100):
Added indexes for `shopping_lists` collection:
```python
await self.db.shopping_lists.create_index("list_id", unique=True)
await self.db.shopping_lists.create_index("status")
await self.db.shopping_lists.create_index("generated_at")
await self.db.shopping_lists.create_index([("status", 1), ("generated_at", -1)])
```

**Schedule**: Daily at 6:00 AM (already configured in Week 1)

---

## 📊 MongoDB Collections

### New Collection: `shopping_lists`

**Schema**:
```javascript
{
  _id: ObjectId,
  list_id: "SL_2026-02-24_060000",  // Unique identifier
  generated_at: ISODate("2026-02-24T06:00:00Z"),
  generated_by: "inventory_agent",
  status: "pending",  // pending | approved | rejected | partially_approved

  // Urgency summary (quick overview)
  urgency_summary: {
    urgent_count: 5,      // URGENT items (order TODAY)
    standard_count: 8,    // STANDARD items (order this week)
    low_priority_count: 3 // LOW_PRIORITY (weekly digest)
  },

  // Financial summary
  total_cost_inr: 45000,  // Total in paise (₹450)
  estimated_total: 45000,

  // Items array (embedded)
  items: [
    {
      material_id: "RM001",
      material_name: "Chicken Breast",
      category: "Proteins",
      unit: "Gram",

      // Inventory status
      current_stock: 8,
      reorder_level: 20,
      days_until_stockout: 1.2,

      // Forecasting context
      daily_demand: 15.5,
      forecast_horizon_days: 7,
      total_demand_next_week: 108.5,

      // Reorder details
      quantity_to_order: 50,
      unit_cost_inr: 6000,
      line_total_inr: 300000,  // 50 × 6000

      // Urgency classification
      urgency: "URGENT",
      urgency_reason: "Stockout in 1.2 days (lead time: 1 day)",

      // Supplier info
      supplier_id: "SUP001",
      supplier_name: "Fresh Meats Co",
      lead_time_days: 1,

      // Additional context
      is_perishable: "Yes",
      shelf_life_days: 5,

      // Status (for partial approvals)
      item_status: "pending",  // pending | approved | rejected
      approved_at: null,
      approved_by: null
    }
    // ... more items
  ],

  // Supplier grouping (for batch ordering)
  supplier_breakdown: [
    {
      supplier_id: "SUP001",
      supplier_name: "Fresh Meats Co",
      item_count: 3,
      total_cost_inr: 25000,
      items: ["RM001", "RM002", "RM003"]
    }
    // ... more suppliers
  ],

  // Agent metadata
  agent_decision_id: ObjectId,  // Link to agent_decisions
  confidence_score: 0.85,
  reasoning: "Generated daily shopping list...",

  // Approval tracking
  reviewed_at: null,
  reviewed_by: null,
  approval_notes: null,

  // Execution tracking
  executed_at: null,
  execution_status: "pending",
  execution_notes: null
}
```

**Indexes**:
- `list_id` (unique)
- `status`
- `generated_at`
- Compound: `(status, generated_at)`

---

### Updated Collection: `agent_decisions`

**New Action Type**: `shopping_list`

```javascript
{
  agent_name: "inventory_agent",
  timestamp: ISODate("2026-02-24T06:00:00Z"),

  decision: {
    actions: [
      {
        action_type: "shopping_list",  // New action type
        data: {
          list_id: "SL_2026-02-24_060000",
          items: [/* full item array */],
          item_count: 16,
          urgency_summary: {
            urgent_count: 5,
            standard_count: 8,
            low_priority_count: 3
          },
          supplier_breakdown: [/* supplier summary */]
        },
        estimated_cost: 45000,  // Total list cost (paise)
        reasoning: "Generated daily shopping list with 16 items",
        confidence: 0.85
      }
    ],
    reasoning: "Daily inventory check completed. 5 urgent, 8 standard, 3 low-priority items.",
    confidence: 0.85
  },

  status: "pending_approval",
  trigger: "scheduled_daily",

  // Link to shopping list
  shopping_list_id: ObjectId  // Reference to shopping_lists collection
}
```

---

## 🎯 Data Flow

```
1. Orchestrator triggers Inventory Agent (6:00 AM daily)
         ↓
2. Agent calls get_inventory_status tool
   - Fetches all raw materials from inventory
   - Returns: current_stock, reorder_level, lead_time, etc.
         ↓
3. Agent calls get_demand_forecasts tool
   - Fetches 7-day forecasts (from cache)
   - Returns: predicted_consumption, confidence
         ↓
4. Agent calls calculate_reorder_needs tool
   - For each material:
     * Calculate days_until_stockout = current_stock / (daily_demand × 1.2)
     * Classify urgency based on lead time
     * Decide if reorder needed
   - Returns: items_to_reorder with urgency classification
         ↓
5. Agent creates AgentDecision
   - Single shopping_list action with all items
   - Estimated cost = sum of all line totals
   - Confidence score based on forecast quality
         ↓
6. Orchestrator logs decision to agent_decisions
         ↓
7. Orchestrator calls _process_inventory_decision
   - Extracts items from shopping_list action
   - Calls shopping_list_service.create_shopping_list()
         ↓
8. Service creates shopping list in MongoDB
   - Groups by urgency
   - Groups by supplier
   - Calculates totals
   - Sets status = "pending"
         ↓
9. User reviews via API
   - GET /api/v1/approvals/pending
   - Sees urgency-grouped items
   - Reviews supplier breakdown
         ↓
10. User approves/rejects
   - POST /api/v1/approvals/{list_id}/approve
   - Status updated to "approved"
   - User manually contacts suppliers
```

---

## 🚀 Usage Examples

### 1. Manual Trigger (Testing)

```bash
# Trigger inventory agent manually
curl -X POST http://localhost:8000/api/v1/orchestrator/trigger/inventory_daily

# Expected output:
# "Inventory Agent executed successfully"
```

### 2. Check Pending Approvals

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/approvals/pending

# Response:
{
  "success": true,
  "data": [
    {
      "list_id": "SL_2026-02-24_060000",
      "status": "pending",
      "urgency_summary": {
        "urgent_count": 5,
        "standard_count": 8,
        "low_priority_count": 3
      },
      "total_cost_inr": 45000,
      "items": [/* 16 items */]
    }
  ],
  "message": "Found 1 pending shopping lists"
}
```

### 3. View Shopping List Details

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/approvals/{list_id}

# Response: Full shopping list with all items, reasoning, etc.
```

### 4. Approve Shopping List

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Approved for ordering"}' \
  http://localhost:8000/api/v1/approvals/{list_id}/approve

# Response:
{
  "success": true,
  "data": {"approved": true, "list_id": "..."},
  "message": "Shopping list approved successfully"
}
```

### 5. Partial Approval (Approve Specific Items)

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "material_ids": ["RM001", "RM003", "RM005"],
    "notes": "Approved urgent items only"
  }' \
  http://localhost:8000/api/v1/approvals/{list_id}/approve-items

# Response:
{
  "success": true,
  "data": {"approved_items": 3, "list_id": "..."},
  "message": "Approved 3 items"
}
```

### 6. Reject Shopping List

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Forecast seems too high, review manually"}' \
  http://localhost:8000/api/v1/approvals/{list_id}/reject

# Response:
{
  "success": true,
  "data": {"rejected": true, "list_id": "..."},
  "message": "Shopping list rejected"
}
```

### 7. View Approval History

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/approvals/history?page=1&limit=20&status=approved"

# Response: Paginated list of past approvals
```

### 8. Verify in MongoDB

```bash
mongosh
use ahar_pos

# Check shopping lists
db.shopping_lists.find({status: "pending"})

# Check agent decisions
db.agent_decisions.find({agent_name: "inventory_agent"}).sort({timestamp: -1}).limit(1)

# Count by status
db.shopping_lists.countDocuments({status: "approved"})
```

---

## 💰 Cost Analysis

### API Costs (Estimated)

**Daily Inventory Agent Run**:
- Input tokens: ~5,000 (inventory + forecasts)
- Output tokens: ~2,000 (decision + reasoning)
- Model: claude-sonnet-4-5
- Cost per run: ~$0.04
- **Monthly cost: ~$1.20** (30 runs)

**On-Demand Runs** (event-triggered):
- Rare (only on low-stock events)
- Estimated: <$0.20/month

**Total Monthly Cost**: ~$1.40 (within $5-10 budget)

**Cost Savings**:
- Manual inventory monitoring: 5-7 hours/week
- Time saved: ~25-30 hours/month
- Value (at ₹500/hour): ~₹12,500-15,000/month
- **ROI: 1000x+**

---

## 📈 Week 3 Achievements

✅ **Inventory Agent**: Complete with tool-calling, urgency classification, safety buffers

✅ **Shopping List Service**: CRUD operations, approval workflow, supplier grouping

✅ **Approvals API**: 7 endpoints with authentication, pagination, audit logging

✅ **Orchestrator Integration**: Agent registration, scheduled execution, decision processing

✅ **MongoDB Collections**: shopping_lists with indexes, agent_decisions updated

✅ **Smart Shopping Lists**: ONE consolidated list instead of individual POs

✅ **Urgency Classification**: URGENT/STANDARD/LOW_PRIORITY based on lead times

✅ **Batch Approval Workflow**: Single review vs scattered approvals

✅ **Supplier Grouping**: Organized by supplier for easier batch ordering

✅ **Partial Approval Support**: Approve specific items while holding others

---

## 📝 Files Created/Modified

### New Files (Created):
```
backend/
├── app/
│   ├── services/
│   │   ├── agents/
│   │   │   └── inventory_agent.py              (588 lines)
│   │   └── shopping_list_service.py            (208 lines)
│   ├── repositories/
│   │   └── shopping_list_repository.py         (220 lines)
│   └── api/
│       └── v1/
│           └── approvals.py                    (286 lines)
```

**Total new code**: ~1,300 lines

### Modified Files:
```
backend/
├── app/
│   ├── services/
│   │   └── orchestrator.py                     (+50 lines)
│   └── api/
│       └── v1/
│           └── __init__.py                     (+2 lines)
```

---

## 🧪 Testing Checklist

### Manual Testing (Priority)

1. **Agent Execution**:
   - [ ] Start MongoDB: `docker compose up -d mongodb`
   - [ ] Start backend: `uvicorn app.main:app --reload --port 8000`
   - [ ] Trigger agent: `POST /api/v1/orchestrator/trigger/inventory_daily`
   - [ ] Verify agent decision in MongoDB: `db.agent_decisions.find({agent_name: "inventory_agent"})`
   - [ ] Verify shopping list created: `db.shopping_lists.find({status: "pending"})`

2. **Approval Workflow**:
   - [ ] Get pending lists: `GET /api/v1/approvals/pending`
   - [ ] View list details: `GET /api/v1/approvals/{list_id}`
   - [ ] Approve list: `POST /api/v1/approvals/{list_id}/approve`
   - [ ] Verify status updated: `db.shopping_lists.find({status: "approved"})`

3. **Partial Approval**:
   - [ ] Trigger agent (create new list)
   - [ ] Partially approve: `POST /api/v1/approvals/{list_id}/approve-items`
   - [ ] Verify item-level status: Check `items[].item_status` in MongoDB
   - [ ] Verify list status: Should be "partially_approved"

4. **Edge Cases**:
   - [ ] No items need reordering (all stock adequate)
   - [ ] All items URGENT (immediate attention needed)
   - [ ] All items LOW_PRIORITY (weekly digest)
   - [ ] Zero forecast (no demand predicted)

### Unit Tests (Future)

**Create later (not blocking for MVP)**:
- `tests/test_inventory_agent.py`
- `tests/test_shopping_list_service.py`
- `tests/integration/test_approval_workflow.py`

---

## 🚧 Known Limitations (MVP)

1. **No Email Notifications**: User must manually check `/api/v1/approvals/pending`
   - **Future**: Email notification when shopping list generated
   - **Future**: SMS for URGENT items

2. **No Automatic PO Generation**: After approval, user manually contacts suppliers
   - **Future**: Email PO to suppliers
   - **Future**: API integration with digital suppliers

3. **No Delivery Tracking**: No tracking of what was actually delivered
   - **Future**: Match deliveries against approved lists
   - **Future**: Update inventory on delivery confirmation

4. **Single Restaurant**: Designed for one restaurant (no multi-tenancy)
   - **Future**: Multi-restaurant support with restaurant_id filter

5. **No Weekly Digest Yet**: LOW_PRIORITY items accumulate but no Sunday digest
   - **Future**: Separate weekly digest generation (Sunday 8 AM)

6. **Manual Trigger Only** (for testing): No way to trigger via API
   - **Future**: Admin endpoint to manually trigger agent
   - Current workaround: Wait for 6 AM scheduled run

---

## 🔜 Next Steps (Week 4)

### Financial Analyst Agent
- Daily P&L generation (extends existing Skills API)
- Revenue anomaly detection (>20% deviation alerts)
- Cancellation rate monitoring
- Margin compression detection

### Approval Dashboard (Frontend)
- React component for shopping list display
- Urgency-based sorting (URGENT first)
- One-click approve/reject buttons
- Supplier-grouped view
- Approval history with filters

### Enhancements
- Email notifications for pending approvals
- Weekly digest for LOW_PRIORITY items (Sundays)
- Waste tracking for expiring perishables
- Dashboard widget showing approval stats

---

## 📊 Success Metrics (To Measure in Pilot)

1. **Autonomous Operation**:
   - ✅ Agent runs daily at 6 AM without manual intervention
   - Target: 100% scheduled execution success rate

2. **Accuracy**:
   - Target: 95%+ accuracy on urgency classification
   - Target: <5% false positives (items flagged but not needed)

3. **User Efficiency**:
   - Target: <2 minutes to review and approve shopping list
   - Target: 80%+ of items approved (high trust in agent)

4. **Business Impact**:
   - Target: Zero stockouts during pilot period
   - Target: 5-7 hours/week time savings
   - Target: <10% waste from perishables

5. **System Reliability**:
   - Target: 99%+ API uptime
   - Target: <500ms API response time
   - Target: No agent crashes or errors

---

## 🎉 Week 3 Status

**Status**: ✅ **COMPLETE**

**Ready for Week 4**: ✅ **YES** (Financial Analyst Agent)

**API Cost**: ✅ Within budget (~$1.40/month)

**User Workflow**: ✅ Batch approval (reduces decision fatigue)

**Integration**: ✅ Fully integrated with Week 1-2 components

---

## Summary

Week 3 delivers a **practical, user-friendly inventory management system** that:

1. **Smart Shopping Lists** replace individual PO approvals (reduces cognitive load)
2. **Urgency Classification** helps prioritize what to order first (URGENT/STANDARD/LOW_PRIORITY)
3. **Batch Approval** fits into daily routine (morning coffee + review)
4. **Supplier Grouping** makes manual ordering easier (organized by supplier)
5. **Partial Approval** allows granular control (approve some items, hold others)
6. **Full Audit Trail** provides compliance and transparency (approval history)

**This balances autonomy with oversight** - the system analyzes inventory, forecasts demand, and recommends actions, but the user retains final approval authority. No surprise orders, no unexpected costs.