# COGS Calculation — Quick Reference

## Core Formula

```python
ingredient_cost = (quantity_per_serving × order_qty × unit_cost_inr) / 100
packaging_cost = (qty_per_serving × order_qty × pkg_unit_cost) / 100
total_cogs = sum(ingredient_costs) + sum(packaging_costs) + wastage + staff_meals + qc_sampling
```

## Collections & Key Fields

### recipe_bom
**Links:** menu_items.menu_item_id → ingredients.material_id  
**Cost Key:** raw_material_inventory[material_id].unit_cost_inr

```
{
  menu_item_id: "MENU001",
  ingredients: [
    { material_id: "RM001", quantity_per_serving: 140 },  // grams
    { material_id: "RM002", quantity_per_serving: 50 }
  ]
}
```

### raw_material_inventory
**Cost Field:** `unit_cost_inr` (paise per unit)

```
{
  material_id: "RM001",
  material_name: "Chicken Breast",
  unit_cost_inr: 60,          // 60 paise per gram
  category: "Proteins"
}
```

### packaging_bom + packaging_materials
**Cost Key:** packaging_materials[packaging_id].unit_cost_inr

```
packaging_bom:
{
  menu_item_id: "MENU001",
  packaging: [
    { packaging_material_id: "PKG001", quantity_per_serving: 1 }  // 1 box
  ]
}

packaging_materials:
{
  packaging_id: "PKG001",
  packaging_name: "Box",
  unit_cost_inr: 500  // 500 paise per box
}
```

### orders.items
**Links:** menu_item_id → recipe_bom.menu_item_id

```
{
  menu_item_id: "MENU001",
  quantity: 2,           // Order qty (2 burgers)
  price_snapshot: 25000  // ₹250 per burger
}
```

## COGS Calculation Entry Points

### 1. When Order Completes
**File:** `backend/app/services/order_service.py:mark_complete()`
- Calls `inventory_service.consume_for_order()`
- Deducts inventory based on recipe BOM
- Logs consumption (but does NOT calculate cost yet)

### 2. For P&L Reports
**File:** `skills/pnl-statement/scripts/generate_pnl.py:calculate_cogs()`
- Fetches all completed orders in date range
- Iterates orders → items → recipes → ingredients → costs
- Returns breakdown by category

### 3. For Item-Level Profit Analysis
**File:** `backend/app/services/profit_analysis_service.py:_calculate_item_cogs()`
- Takes menu_item_id + quantity_sold
- Looks up recipe, packages, calculates total COGS
- Returns cogs_per_serving for margin calculation

## Cost Calculation Example

```
Order: 2 × "Smoky Chicken Burger" (MENU001)

Recipe: RM001 (Chicken): 150g @ 60p/g, RM002 (Bun): 1 @ 3000p, ...
Packaging: PKG001 (Box): 1 @ 500p

Raw Materials:
  RM001: 150 × 2 × 60 / 100 = ₹180
  RM002: 1 × 2 × 3000 / 100 = ₹60
  Subtotal: ₹240

Packaging:
  PKG001: 1 × 2 × 500 / 100 = ₹10

Total COGS for order: ₹250 (cost of goods, not selling price!)
COGS per serving: ₹125
```

## Database Links Diagram

```
orders
  └─ items[].menu_item_id
       ├─ recipe_bom
       │   └─ ingredients[].material_id
       │        └─ raw_material_inventory.unit_cost_inr ← COST
       │
       └─ packaging_bom
            └─ packaging[].packaging_material_id
                 └─ packaging_materials.unit_cost_inr ← COST

stock_movement_log
  └─ material_id
       └─ raw_material_inventory.unit_cost_inr ← COST
```

## Functions to Know

| Function | File | Purpose |
|----------|------|---------|
| `consume_for_order()` | inventory_service.py | Deducts inventory when order completes |
| `_calculate_item_cogs()` | profit_analysis_service.py | COGS for single menu item |
| `calculate_cogs()` | generate_pnl.py | Full COGS breakdown for period |
| `get_top_items(metric="margin")` | profit_analysis_service.py | Items ranked by profit/margin |
| `get_menu_item_cost()` | recipe_repository.py | Lookup ingredient cost for menu item |

## Common Queries

### COGS for a single order
```python
order_items = [{"menu_item_id": "MENU001", "quantity": 2}]
cogs_result = await inventory_service.consume_for_order(order_items)
# cogs_result["consumed"] = list of materials with quantities
# But cost_per_unit is currently 0 (limitation)
```

### Top 10 items by margin
```python
items = await profit_analysis_service.get_top_items(
    metric="margin",
    period_days=30,
    limit=10
)
# Returns: [{item_name, revenue, profit, margin_percentage, ...}, ...]
```

### Item details with COGS breakdown
```python
details = await profit_analysis_service.get_item_details(
    item_name="Smoky Burger",
    period_days=30
)
# Returns: {item_name, revenue, profit, margin_percentage, cogs_breakdown: {ingredients: [...], ...}}
```

### Full P&L with COGS
```
# Triggered via chatbot skill or API
python generate_pnl.py "2025-01-01" "2025-01-31"
# Outputs: pnl_report_2025-01-01_2025-01-31.xlsx
# Includes: COGS breakdown by category
```

## Cost Fields Summary

| Where | Field | Unit | Example |
|-------|-------|------|---------|
| recipe_bom.ingredients | quantity_per_serving | user-defined (gram/ml/piece) | 140 |
| raw_material_inventory | unit_cost_inr | paise per unit | 60 |
| packaging_bom | quantity_per_serving | user-defined | 1 |
| packaging_materials | unit_cost_inr | paise per unit | 500 |

**ALWAYS DIVIDE BY 100 TO GET RUPEES** (all _inr fields are in paise)

## Limitations (As of April 2026)

1. **No cost snapshot** — consumption_logs.cost_per_unit = 0 (not captured at order time)
2. **No historical costs** — uses current prices, not prices at order date
3. **Optional recipes** — items without recipe BOM show as 100% margin
4. **No COGS in logs** — total_cost field not populated in inventory_consumption_logs

## Next Steps

- [ ] Populate `cost_per_unit` when inventory consumed
- [ ] Calculate and store `total_cost` in consumption logs
- [ ] Add material price history tracking
- [ ] Create consumption cost reconciliation report
