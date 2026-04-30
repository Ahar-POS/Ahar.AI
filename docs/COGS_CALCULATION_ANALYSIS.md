# COGS (Cost of Goods Sold) Calculation Analysis
## Ahar.AI Restaurant POS System

**Date:** April 12, 2026  
**Scope:** Complete data flow from order → ingredient consumption → COGS calculation in P&L  

---

## Executive Summary

The Ahar.AI system calculates COGS through a **recipe-based BOM (Bill of Materials)** approach linked to ingredient costs. When an order is completed, the system:

1. Deducts ingredients from inventory based on recipe formulas
2. Logs consumption with ingredient costs
3. Includes packaging costs and wastage
4. Rolls up COGS into P&L reports (via P&L generation script)

**Key Finding:** COGS calculation is **recipe-driven**, not item-level costed. The system has recipes linking menu items → ingredients with quantities, plus packaging costs. However, **historical cost tracking is not yet implemented** — costs are calculated using current unit prices only.

---

## 1. Data Structures & Collections

### 1.1 Menu Item Model
**File:** `/Users/pandiarajan/Ahar.AI/backend/app/models/menu_item.py`

```
Collection: menu_items
Fields:
  _id: ObjectId (MongoDB internal ID)
  menu_item_id: str (e.g., "MENU001") — PRIMARY IDENTIFIER FOR RECIPES
  name: str
  description: str
  price: int (in paise, e.g., 12500 = ₹125.00)
  category: str
  tags: [IngredientTag enum]
  prep_type: PrepType enum
  is_available: bool
  created_at, updated_at: datetime
```

**Key Field:** `menu_item_id` — used to link orders to recipes via `recipe_bom.menu_item_id`

---

### 1.2 Recipe BOM (Bill of Materials)
**File:** `/Users/pandiarajan/Ahar.AI/backend/app/repositories/recipe_repository.py`

```
Collection: recipe_bom
Fields:
  _id: ObjectId
  menu_item_id: str (e.g., "MENU001") — LINKS TO menu_items.menu_item_id
  menu_item_name: str
  ingredients: [
    {
      material_id: str (e.g., "RM001")
      material_name: str
      quantity_per_serving: float (e.g., 140 grams)
      unit: str (e.g., "Gram", "ML", "Piece")
      is_critical: bool
    },
    ...
  ]
  created_at, updated_at: datetime
```

**Key Field:** `ingredients[].quantity_per_serving` — amount consumed per menu item order

---

### 1.3 Raw Material Inventory
**File:** `/Users/pandiarajan/Ahar.AI/backend/app/models/inventory.py`

```
Collection: raw_material_inventory
Fields:
  _id: ObjectId
  material_id: str (e.g., "RM001") — PRIMARY COST KEY
  material_name: str
  category: str (e.g., "Bakery", "Proteins", "Vegetables")
  unit: str (e.g., "Gram", "Liter", "Piece")
  unit_cost_inr: int (COST PER UNIT IN PAISE)
    ↑↑↑ CRITICAL: This is the cost field used in COGS calculation
  current_stock: int
  reorder_level, reorder_qty, max_stock: int
  lead_time_days, shelf_life_days: int
  supplier_id: str
  is_perishable: str ("Yes"/"No")
  storage_temp_c: str
  created_at, updated_at: datetime
```

**Cost Field:** `unit_cost_inr` — cost per unit in paise. Used in COGS formula:
```
ingredient_cost = quantity_per_serving × unit_cost_inr × order_quantity
```

---

### 1.4 Packaging BOM
**File:** `/Users/pandiarajan/Ahar.AI/backend/app/models/packaging_bom.py`

```
Collection: packaging_bom
Fields:
  _id: ObjectId
  menu_item_id: str (LINKS TO menu_items.menu_item_id)
  packaging_material_id: str (LINKS TO packaging_materials.packaging_id)
  quantity_per_serving: float (e.g., 1 box per order)
  is_critical: bool
  created_at, updated_at: datetime
```

**Purpose:** Specifies packaging requirements per menu item for cost calculation

---

### 1.5 Packaging Materials
**File:** `/Users/pandiarajan/Ahar.AI/backend/app/models/packaging_material.py`

```
Collection: packaging_materials
Fields:
  _id: ObjectId
  packaging_id: str (e.g., "PKG001") — PRIMARY COST KEY
  packaging_name: str (e.g., "Corrugated Box Medium")
  category: PackagingCategory enum ("PRIMARY", "SECONDARY", "LABELS")
  unit_cost_inr: int (COST PER UNIT IN PAISE)
  unit: str (e.g., "Piece", "Gram")
  supplier_id: str
  description: str
  created_at, updated_at: datetime
```

---

### 1.6 Orders & Order Items
**File:** `/Users/pandiarajan/Ahar.AI/backend/app/models/order.py`

```
Collection: orders
Fields:
  _id: ObjectId
  order_number: int
  restaurant_id: str
  items: [
    {
      menu_item_id: str (LINKS TO recipes via recipe_bom.menu_item_id)
      name_snapshot: str
      price_snapshot: int (in paise)
      quantity: int (number of items ordered)
      notes: str
      status: OrderItemStatus enum
    },
    ...
  ]
  status: OrderStatus enum ("DRAFT", "SENT_TO_KITCHEN", "IN_PROGRESS", "COMPLETED")
  total_amount: int (in paise)
  created_at: datetime
  sent_to_kitchen_at, completed_at: datetime
```

**Key:** `items[].menu_item_id` used to look up recipe and calculate ingredient consumption

---

### 1.7 Inventory Consumption Log
**File:** `/Users/pandiarajan/Ahar.AI/backend/app/models/inventory_consumption.py`

```
Collection: inventory_consumption_logs
Fields:
  _id: ObjectId
  order_id: str (links to orders._id)
  order_number: int
  restaurant_id: str
  consumed_materials: [
    {
      material_id: str (e.g., "RM001")
      material_name: str
      quantity: float (total consumed)
      unit: str
      cost_per_unit: int (in paise) — OPTIONAL, currently set to 0
    },
    ...
  ]
  total_cost: int (in paise) — CURRENTLY NOT CALCULATED, set to 0
  warnings: [str] (e.g., "LOW STOCK: Ciabatta Bread at 10")
  errors: [str]
  consumed_at: datetime
```

**Note:** `total_cost` is currently **NOT populated** — cost is calculated on-demand from unit prices

---

### 1.8 Stock Movement Log
**File:** Referenced in profit_analysis_service.py, generate_pnl.py

```
Collection: stock_movement_log
Fields:
  _id: ObjectId
  material_id: str
  movement_type: str ("WASTE", "STAFF_MEAL", "QC_SAMPLE", "PURCHASE", etc.)
  quantity: float
  movement_date: datetime
  created_at: datetime
```

**Purpose:** Track non-order-related inventory movements (waste, staff meals, QC sampling)

---

## 2. COGS Calculation Flow

### 2.1 Order Completion → Inventory Deduction

**File:** `/Users/pandiarajan/Ahar.AI/backend/app/services/order_service.py` (lines 338-422)

```
OrderService.mark_complete()
  └─→ Calls: inventory_service.consume_for_order()
       ├─ Input: order_items = [{"menu_item_id": "MENU001", "quantity": 2}, ...]
       └─→ For each order_item:
            ├─ Fetch menu_item from DB (to get menu_item_id string)
            ├─ Fetch recipe_bom where recipe_bom.menu_item_id = menu_item_id
            ├─ For each ingredient in recipe.ingredients:
            │   ├─ material_id = ingredient.material_id
            │   ├─ qty_needed = ingredient.quantity_per_serving × order_quantity
            │   └─ Increment ingredient_totals[material_id] += qty_needed
            ├─ Call: inventory_repository.bulk_decrement_stock(ingredient_totals)
            │   └─ Updates raw_material_inventory.current_stock for each material
            └─ Log InventoryConsumption with consumed_materials and warnings
```

**File:** `/Users/pandiarajan/Ahar.AI/backend/app/services/inventory_service.py` (lines 156-333)

**Key Logic:**
```python
# For each order item
for ingredient in recipe.get("ingredients", []):
    material_id = ingredient["material_id"]
    qty_per_serving = ingredient["quantity_per_serving"]
    total_qty = qty_per_serving * order_qty
    
    # Track total consumption
    ingredient_totals[material_id] += total_qty

# Deduct from inventory
updated_count = await inventory_repository.bulk_decrement_stock(decrements)

# Log consumption (cost_per_unit currently 0)
consumed_materials=[
    ConsumedMaterial(
        material_id=c["material_id"],
        material_name=c["material_name"],
        quantity=c["quantity"],
        unit=c["unit"],
        cost_per_unit=0  # ← NOT POPULATED (enhancement needed)
    )
    for c in consumed
]
```

---

### 2.2 COGS Calculation for P&L Reports

**File:** `/Users/pandiarajan/Ahar.AI/skills/pnl-statement/scripts/generate_pnl.py` (lines 197-319)

**Function:** `calculate_cogs(db, restaurant_id, start_dt, end_dt)`

```
Step 1: Fetch Orders
  └─ Query: orders.find({
       created_at: {$gte: start_dt, $lte: end_dt},
       status: {$in: ["COMPLETED", "sent_to_kitchen", "in_progress"]}
     })

Step 2: Index Data
  ├─ recipe_bom indexed by menu_item_id
  ├─ raw_material_inventory indexed by material_id
  ├─ packaging_bom indexed by menu_item_id
  └─ packaging_materials indexed by packaging_id

Step 3: Calculate Raw Material Cost
  └─ For each order:
       └─ For each item in order.items:
            └─ menu_id = item.menu_item_id
               └─ If menu_id in recipe_bom:
                    └─ For each ingredient in recipe_bom[menu_id].ingredients:
                         ├─ material_id = ingredient.material_id
                         ├─ qty_needed = ingredient.quantity_per_serving × item.quantity
                         ├─ unit_cost = raw_material_inventory[material_id].unit_cost_inr
                         └─ cost = (qty_needed × unit_cost) / 100  # Convert paise to rupees
                             └─ material_costs[category] += cost

Step 4: Calculate Packaging Cost
  └─ For each order:
       └─ For each item in order.items:
            └─ menu_id = item.menu_item_id
               └─ If menu_id in packaging_bom:
                    └─ For each pkg in packaging_bom[menu_id]:
                         ├─ pkg_id = pkg.packaging_material_id
                         ├─ qty_needed = pkg.quantity_per_serving × item.quantity
                         ├─ unit_cost = packaging_materials[pkg_id].unit_cost_inr
                         └─ cost = (qty_needed × unit_cost) / 100
                             └─ packaging_costs[pkg_category] += cost

Step 5: Add Wastage, Staff Meals, QC Sampling
  └─ Query: stock_movement_log.find({
       movement_date: {$gte: start_dt, $lte: end_dt},
       movement_type: {$in: ["WASTE", "STAFF_MEAL", "QC_SAMPLE"]}
     })
     └─ For each movement:
          ├─ material_id = movement.material_id
          ├─ qty = abs(movement.quantity)
          ├─ unit_cost = raw_material_inventory[material_id].unit_cost_inr
          └─ cost = (qty × unit_cost) / 100
              └─ if movement_type == "WASTE": wastage += cost
                 elif movement_type == "STAFF_MEAL": staff_meals += cost
                 elif movement_type == "QC_SAMPLE": qc_sampling += cost

Step 6: Return COGS Breakdown
  └─ {
       "raw_material_by_category": {...},
       "total_raw_material": sum(material_costs),
       "packaging_by_category": {...},
       "total_packaging": sum(packaging_costs),
       "wastage": wastage,
       "staff_meals": staff_meals,
       "qc_sampling": qc_sampling,
       "total_wastage_other": wastage + staff_meals + qc_sampling,
       "total_cogs": total_raw_material + total_packaging + total_wastage_other
     }
```

---

### 2.3 COGS Calculation for Profit Analysis (Item-Level)

**File:** `/Users/pandiarajan/Ahar.AI/backend/app/services/profit_analysis_service.py` (lines 555-623)

**Function:** `_calculate_item_cogs(menu_item_id, quantity_sold, detailed=False)`

```
Purpose: Calculate COGS per menu item for profit margin analysis

Step 1: Fetch Recipe
  └─ recipe = recipe_bom.find_one({menu_item_id: menu_item_id})

Step 2: If No Recipe
  └─ Return zeros:
       {
         "total_cogs": 0,
         "cogs_per_serving": 0,
         "raw_materials": 0,
         "packaging": 0,
         "ingredients": []
       }

Step 3: Calculate Raw Material Cost Per Serving
  └─ Fetch raw_material_inventory for all materials
  └─ For each ingredient in recipe.ingredients:
       ├─ material_id = ingredient.material_id
       ├─ quantity = ingredient.quantity_per_serving (or .quantity)
       ├─ unit_cost = raw_material_inventory[material_id].unit_cost_inr
       └─ cost = quantity × unit_cost
           └─ raw_materials_cost += cost
               └─ [if detailed] ingredient_details.append({
                     "name": material_name,
                     "quantity": quantity,
                     "unit": unit,
                     "cost_per_serving": cost / 100
                   })

Step 4: Calculate Packaging Cost Per Serving
  └─ packaging_bom = packaging_bom.find_one({menu_item_id: menu_item_id})
  └─ If packaging_bom exists:
       └─ For each pkg in packaging_bom.packaging:
            ├─ pkg_id = pkg.packaging_material_id
            ├─ pkg_item = packaging_materials[pkg_id]
            └─ packaging_cost += pkg_item.unit_cost_inr

Step 5: Calculate Total COGS
  └─ cogs_per_serving = raw_materials_cost + packaging_cost
  └─ total_cogs = cogs_per_serving × quantity_sold

Step 6: Return
  └─ {
       "total_cogs": total_cogs,
       "cogs_per_serving": cogs_per_serving,
       "raw_materials": raw_materials_cost × quantity_sold,
       "packaging": packaging_cost × quantity_sold,
       "ingredients": ingredient_details  # if detailed=True
     }
```

---

## 3. Data Flow Diagram: Order → COGS

```
┌──────────────────┐
│  ORDER CREATED   │
│  (DRAFT STATUS)  │
└────────┬─────────┘
         │
         │ items = [{menu_item_id: "MENU001", quantity: 2}, ...]
         │
         ▼
┌──────────────────────────┐
│  ORDER COMPLETED         │
│  Status → COMPLETED      │
└────────┬─────────────────┘
         │
         │ Call: inventory_service.consume_for_order()
         │
         ▼
┌──────────────────────────────────────────────┐
│ LOOKUP RECIPE BOM                            │
│ recipe_bom.find_one({                        │
│   menu_item_id: "MENU001"                    │
│ })                                           │
│ Returns: {                                   │
│   ingredients: [                             │
│     {material_id: "RM001",                   │
│      quantity_per_serving: 140},             │
│     {material_id: "RM002",                   │
│      quantity_per_serving: 50}               │
│   ]                                          │
│ }                                            │
└────────┬─────────────────────────────────────┘
         │
         │ For each ingredient:
         │ qty_total = qty_per_serving × order_qty
         │
         ▼
┌──────────────────────────────────────────────┐
│ DEDUCT FROM INVENTORY                        │
│ raw_material_inventory.update_one({          │
│   material_id: "RM001"                       │
│ }, {                                         │
│   $inc: {current_stock: -280}  # 140 × 2    │
│ })                                           │
└────────┬─────────────────────────────────────┘
         │
         │ Log consumption
         │
         ▼
┌──────────────────────────────────────────────┐
│ CREATE CONSUMPTION LOG                       │
│ inventory_consumption_logs.insert_one({      │
│   order_id: "...",                           │
│   consumed_materials: [                      │
│     {material_id: "RM001",                   │
│      quantity: 280,                          │
│      cost_per_unit: 0}  ← NOT POPULATED     │
│   ],                                         │
│   total_cost: 0  ← NOT CALCULATED           │
│ })                                           │
└──────────────────────────────────────────────┘

         ▼ [LATER: P&L REPORT REQUEST]

┌──────────────────────────────────────────────┐
│ GENERATE P&L REPORT                          │
│ generate_pnl.py:calculate_cogs()             │
│                                              │
│ 1. Fetch all COMPLETED orders in date range │
│ 2. For each order.items[]:                   │
│    - Look up recipe_bom[menu_item_id]       │
│    - For each ingredient:                    │
│      * qty = qty_per_serving × qty_ordered  │
│      * cost = qty × unit_cost_inr / 100     │
│      * material_costs[category] += cost      │
│ 3. Fetch packaging_bom & add packaging cost  │
│ 4. Fetch stock_movement_log & add wastage    │
│ 5. SUM: total_cogs                           │
└──────────────────────────────────────────────┘

         ▼

┌──────────────────────────────────────────────┐
│ P&L STATEMENT                                │
│ ─────────────────────────                    │
│ Revenue: ₹10,000                             │
│ COGS:                                        │
│  - Raw Materials: ₹3,500                     │
│  - Packaging: ₹300                           │
│  - Wastage: ₹200                             │
│ TOTAL COGS: ₹4,000                           │
│ ─────────────────────────                    │
│ GROSS PROFIT: ₹6,000 (60%)                   │
└──────────────────────────────────────────────┘
```

---

## 4. Key Field References

### Cost Fields (in paise)

| Collection | Field | Use | Example |
|-----------|-------|-----|---------|
| `raw_material_inventory` | `unit_cost_inr` | Cost per unit (gram/ml/piece) | 60 paise per gram |
| `packaging_materials` | `unit_cost_inr` | Cost per packaging unit | 500 paise per box |
| `orders.items` | `price_snapshot` | Item selling price (snapshot) | 12500 (₹125) |
| `recipe_bom.ingredients` | `quantity_per_serving` | Amount used per item | 140 grams |
| `packaging_bom` | `quantity_per_serving` | Packaging per item | 1 box |

### Cost Calculation Formula

```
ingredient_cost = (
    recipe_bom[menu_item_id].ingredients[i].quantity_per_serving
    × order_item.quantity
    × raw_material_inventory[material_id].unit_cost_inr
) / 100  # Convert paise to rupees

packaging_cost = (
    packaging_bom[menu_item_id][i].quantity_per_serving
    × order_item.quantity
    × packaging_materials[packaging_id].unit_cost_inr
) / 100

total_cogs = sum(ingredient_costs) + sum(packaging_costs) + wastage + staff_meals + qc_sampling
```

---

## 5. Current Limitations & Gaps

### 5.1 No Historical Cost Tracking
**Issue:** `inventory_consumption_logs.consumed_materials[].cost_per_unit` is always 0.

**Impact:** Cannot calculate historical COGS (what ingredient cost at time of order) — only current COGS (using today's prices).

**Solution Needed:** Populate `cost_per_unit` from `raw_material_inventory.unit_cost_inr` at consumption time:

```python
# In inventory_service.py, line 309
consumed_materials=[
    ConsumedMaterial(
        material_id=c["material_id"],
        material_name=c["material_name"],
        quantity=c["quantity"],
        unit=c["unit"],
        cost_per_unit=item["unit_cost_inr"]  # ← FETCH & STORE
    )
    for c in consumed
]
```

### 5.2 No Total Cost in Consumption Log
**Issue:** `inventory_consumption_logs.total_cost` is always 0.

**Impact:** Quick lookups of order COGS require re-calculating from consumed_materials.

**Solution Needed:**

```python
consumed_materials = [...]
total_cost = sum(
    m.quantity * m.cost_per_unit 
    for m in consumed_materials
)  # in paise
```

### 5.3 Recipe & Packaging BOM Optional
**Issue:** If `menu_item_id` has no recipe or packaging BOM, COGS is 0 (not an error).

**Impact:** 
- Menu items without recipes show as 100% margin
- P&L reports may understate COGS if some items aren't BODed

**Solution:** Enforce recipe creation for all menu items (or flag warnings in P&L).

### 5.4 No Price History for Ingredients
**Issue:** When `unit_cost_inr` changes in `raw_material_inventory`, historical orders recalculate with new cost.

**Impact:** Monthly COGS reports may not match actual costs from that month if ingredient prices changed.

**Solution:** Implement a `material_price_history` collection:

```
Collection: material_price_history
Fields:
  material_id: str
  unit_cost_inr: int
  effective_date: datetime
  ended_date: Optional[datetime]
```

Then in COGS calculation, look up historical cost based on order date.

### 5.5 Packaging Cost Per Serving Not in BOM
**Issue:** `packaging_bom` has `quantity_per_serving`, but aggregation occurs only in P&L script.

**Impact:** Item-level profit margin calculation (`profit_analysis_service._calculate_item_cogs()`) doesn't distinguish between primary/secondary packaging by cost.

---

## 6. Collections Dependency Map

```
orders (orders completed)
  ├─→ items[].menu_item_id
       ├─→ recipe_bom (recipe_bom.menu_item_id)
       │    └─→ ingredients[].material_id
       │         └─→ raw_material_inventory (material_id)
       │              └─→ unit_cost_inr (COST)
       │
       └─→ packaging_bom (packaging_bom.menu_item_id)
            └─→ packaging[].packaging_material_id
                 └─→ packaging_materials (packaging_id)
                      └─→ unit_cost_inr (COST)

stock_movement_log
  └─→ material_id
       └─→ raw_material_inventory (material_id)
            └─→ unit_cost_inr (COST)
```

---

## 7. Contribution Margin Per Menu Item

### 7.1 Formula

```
Contribution Margin = Revenue - COGS

For Menu Item "Smoky Chicken Burger":
  ├─ price_snapshot: 25000 paise (₹250)
  ├─ recipe_bom[MENU001]:
  │   ├─ Chicken Breast: 150g @ 60p/g = 9,000p
  │   ├─ Bun: 1 @ 3,000p = 3,000p
  │   ├─ Toppings: 50g @ 10p/g = 500p
  │   └─ Total Raw: 12,500p
  ├─ packaging_bom[MENU001]:
  │   └─ Box: 1 @ 500p = 500p
  ├─ COGS per serving: 13,000p (₹130)
  ├─ Revenue per serving: 25,000p (₹250)
  └─ Contribution Margin: 12,000p (₹120) = 48% margin
```

### 7.2 Calculation Implementation
**File:** `/Users/pandiarajan/Ahar.AI/backend/app/services/profit_analysis_service.py`

```python
async def get_top_items(metric="margin", limit=10):
    """
    Get top menu items by metric (revenue, profit, margin, volume)
    """
    items = []
    for item in menu_items:
        item_id = item["menu_item_id"]
        quantity_sold = get_quantity_sold(item_id, period)
        total_revenue = quantity_sold × item["price_snapshot"]
        
        cogs_data = await self._calculate_item_cogs(item_id, quantity_sold)
        total_cogs = cogs_data["total_cogs"]
        
        profit = total_revenue - total_cogs
        margin_pct = (profit / total_revenue × 100) if total_revenue > 0 else 0
        
        items.append({
            "item_id": item_id,
            "revenue": total_revenue / 100,
            "profit": profit / 100,
            "margin_percentage": margin_pct,
            "cogs_per_serving": cogs_data["cogs_per_serving"] / 100
        })
    
    return sorted(items, key=lambda x: x[metric], reverse=True)[:limit]
```

---

## 8. File Manifest

### Backend Services
| File | Purpose | Key Functions |
|------|---------|---|
| `backend/app/services/inventory_service.py` | Inventory management | `consume_for_order()` — deducts stock & logs consumption |
| `backend/app/services/order_service.py` | Order lifecycle | `mark_complete()` — triggers inventory consumption |
| `backend/app/services/profit_analysis_service.py` | Item-level profit analysis | `_calculate_item_cogs()`, `get_top_items()` |
| `backend/app/services/agents/financial_agent.py` | Financial AI agent | Autonomous profit tracking & anomaly detection |

### Repositories
| File | Purpose |
|------|---------|
| `backend/app/repositories/recipe_repository.py` | Recipe BOM CRUD & lookups |
| `backend/app/repositories/inventory_repository.py` | Raw material inventory operations |
| `backend/app/repositories/order_repository.py` | Order CRUD & queries |
| `backend/app/repositories/packaging_bom_repository.py` | Packaging BOM operations |

### Models
| File | Collections |
|------|---|
| `backend/app/models/order.py` | `orders` |
| `backend/app/models/menu_item.py` | `menu_items` |
| `backend/app/models/inventory.py` | `raw_material_inventory` |
| `backend/app/models/inventory_consumption.py` | `inventory_consumption_logs` |
| `backend/app/models/packaging_bom.py` | `packaging_bom` |
| `backend/app/models/packaging_material.py` | `packaging_materials` |

### P&L Generation
| File | Purpose |
|------|---------|
| `skills/pnl-statement/scripts/generate_pnl.py` | P&L report generation (includes `calculate_cogs()`) |
| `docs/features/pnl-chatbot-implementation.md` | P&L chatbot architecture (Skills API) |

---

## 9. Recommended Next Steps

### 9.1 SHORT TERM: Fix Cost Tracking
1. **Populate `cost_per_unit` in consumption logs** — Store `raw_material_inventory.unit_cost_inr` at order completion time
2. **Calculate `total_cost` in consumption logs** — Sum `quantity × cost_per_unit` for each material
3. **Add unit costs to packaging consumption** — Track packaging cost at time of order

### 9.2 MEDIUM TERM: Add Price History
1. Create `material_price_history` collection with `effective_date` ranges
2. Refactor COGS calculation to use historical costs (lookup by order date)
3. Update both P&L reports and item-level analytics

### 9.3 LONG TERM: Enhancements
1. **Variance Analysis** — Compare actual COGS (from consumption logs) vs standard COGS (from recipes)
2. **Recipe Costing Dashboard** — Visual breakdown of ingredient costs per menu item
3. **Material Cost Forecasting** — Predict COGS impact if supplier prices change
4. **Yield & Waste Tracking** — Monitor actual yield % vs recipe assumptions

---

## 10. Summary Table: COGS Data Sources

| Data Element | Source Collection | Field | Updated When |
|---|---|---|---|
| Menu Item Identity | `menu_items` | `menu_item_id` | Item created |
| Item Selling Price | `orders.items` | `price_snapshot` | Order placed |
| Recipe Ingredients | `recipe_bom` | `ingredients[].{material_id, quantity_per_serving}` | Recipe created/updated |
| Ingredient Unit Cost | `raw_material_inventory` | `unit_cost_inr` | Inventory updated (real-time) |
| Ingredient Consumed | `inventory_consumption_logs` | `consumed_materials[].quantity` | Order completed |
| Packaging Requirements | `packaging_bom` | `quantity_per_serving` | BOM created/updated |
| Packaging Unit Cost | `packaging_materials` | `unit_cost_inr` | Material updated |
| Waste/Staff Meals | `stock_movement_log` | `quantity, movement_type` | Waste logged |

---

**Document Version:** 1.0  
**Last Updated:** April 12, 2026  
**Reviewed By:** Code Analysis Agent
