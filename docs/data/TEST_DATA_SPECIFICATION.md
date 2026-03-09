# Test Data Specification for Autonomous AI Restaurant OS

**Purpose:** Complete specification for generating test data for demand forecasting and autonomous agents.

**Timeline:** 90-120 days of historical data (recommended: October 2025 - January 2026)

**QSR Context:** Quick Service Restaurant in India (Bangalore)

---

## Overview: Required Files


| File Name                    | Purpose                       | Records Needed             | Priority |
| ---------------------------- | ----------------------------- | -------------------------- | -------- |
| `menu_items.csv`             | Menu catalog with pricing     | 15-25 items                | CRITICAL |
| `recipe_bom.csv`             | Menu-to-ingredient mapping    | 45-150 rows (3-8 per item) | CRITICAL |
| `raw_material_inventory.csv` | Ingredient master data        | 30-50 materials            | CRITICAL |
| `orders.csv`                 | Historical order transactions | 6,000-8,000 orders         | CRITICAL |
| `order_line_items.csv`       | Order details (items ordered) | 12,000-20,000 rows         | CRITICAL |
| `stock_movement_log.csv`     | Inventory movements           | 500-800 movements          | MEDIUM   |
| `supplier_master.csv`        | Supplier information          | 10-15 suppliers            | LOW      |


---

## File 1: menu_items.csv

### Purpose

Complete menu catalog with all dishes offered by the restaurant.

### Schema

```csv
menu_item_id,name,category,price_inr,description,prep_type,tags,is_available,popularity_score,created_at
```

### Column Definitions


| Column             | Type     | Description                       | Example                      | Required | Constraints                                          |
| ------------------ | -------- | --------------------------------- | ---------------------------- | -------- | ---------------------------------------------------- |
| `menu_item_id`     | String   | Unique menu item ID               | MENU001                      | Yes      | Format: MENU###                                      |
| `name`             | String   | Dish name                         | Chicken Burger               | Yes      | 3-50 chars                                           |
| `category`         | String   | Menu category                     | Main Course                  | Yes      | Enum: Starters, Main Course, Beverages, Desserts     |
| `price_inr`        | Integer  | Price in paise                    | 25000 (₹250)                 | Yes      | 5000-100000 (₹50-₹1000)                              |
| `description`      | String   | Dish description                  | Grilled chicken with lettuce | No       | Max 200 chars                                        |
| `prep_type`        | String   | Preparation method                | GRILL                        | Yes      | Enum: FRY, GRILL, STEAM, RAW, BEVERAGE, DESSERT      |
| `tags`             | String   | Ingredient tags (comma-separated) | CHICKEN,DAIRY,VEGETABLES     | Yes      | BEEF,CHICKEN,FISH,VEGETABLES,DAIRY,PASTA,SPICY,VEGAN |
| `is_available`     | Boolean  | Currently available?              | TRUE                         | Yes      | TRUE/FALSE                                           |
| `popularity_score` | Integer  | Popularity (1-10)                 | 8                            | Yes      | 1-10 (8-10=bestseller, 5-7=medium, 1-4=slow)         |
| `created_at`       | DateTime | When added to menu                | 2024-01-15                   | Yes      | ISO 8601 format                                      |


### Sample Data

```csv
menu_item_id,name,category,price_inr,description,prep_type,tags,is_available,popularity_score,created_at
MENU001,Chicken Burger,Main Course,25000,Grilled chicken patty with fresh veggies,GRILL,"CHICKEN,DAIRY,VEGETABLES",TRUE,9,2024-01-15
MENU002,Veg Sandwich,Main Course,15000,Mixed vegetable sandwich with cheese,RAW,"VEGETABLES,DAIRY",TRUE,7,2024-01-15
MENU003,French Fries,Starters,8000,Crispy golden fries,FRY,VEGETABLES,TRUE,10,2024-01-15
MENU004,Masala Dosa,Main Course,12000,Crispy dosa with potato filling,FRY,"VEGETABLES,SPICY",TRUE,8,2024-01-15
MENU005,Mango Lassi,Beverages,7000,Sweet mango yogurt drink,BEVERAGE,"DAIRY,MANGO",TRUE,6,2024-01-20
```

### Business Rules

- **Bestsellers (score 8-10):** 20% of menu should be bestsellers (order frequently)
- **Medium popularity (score 5-7):** 50% of menu
- **Slow movers (score 1-4):** 30% of menu (rarely ordered)
- **Price distribution:**
  - Starters: ₹50-₹150
  - Main Course: ₹100-₹300
  - Beverages: ₹50-₹100
  - Desserts: ₹80-₹150

---

## File 2: recipe_bom.csv

### Purpose

**CRITICAL:** Maps menu items to raw materials (ingredients). This is the key file for demand forecasting.

### Schema

```csv
menu_item_id,menu_item_name,material_id,material_name,quantity_per_serving,unit,is_critical
```

### Column Definitions


| Column                 | Type    | Description                        | Example        | Required | Constraints                              |
| ---------------------- | ------- | ---------------------------------- | -------------- | -------- | ---------------------------------------- |
| `menu_item_id`         | String  | Menu item reference                | MENU001        | Yes      | Must exist in menu_items.csv             |
| `menu_item_name`       | String  | Menu item name (for readability)   | Chicken Burger | Yes      | Match menu_items.name                    |
| `material_id`          | String  | Raw material reference             | RM001          | Yes      | Must exist in raw_material_inventory.csv |
| `material_name`        | String  | Material name (for readability)    | Chicken Breast | Yes      | Match inventory name                     |
| `quantity_per_serving` | Decimal | Amount needed per 1 order          | 150            | Yes      | Must be > 0                              |
| `unit`                 | String  | Unit of measurement                | Gram           | Yes      | Must match material unit                 |
| `is_critical`          | Boolean | Cannot substitute this ingredient? | TRUE           | Yes      | TRUE/FALSE                               |


### Sample Data

```csv
menu_item_id,menu_item_name,material_id,material_name,quantity_per_serving,unit,is_critical
MENU001,Chicken Burger,RM001,Chicken Breast,150,Gram,TRUE
MENU001,Chicken Burger,RM002,Burger Bun,1,Piece,TRUE
MENU001,Chicken Burger,RM003,Lettuce,30,Gram,FALSE
MENU001,Chicken Burger,RM004,Tomato,2,Slice,FALSE
MENU001,Chicken Burger,RM005,Cheese Slice,1,Piece,FALSE
MENU001,Chicken Burger,RM006,Mayonnaise,20,Gram,FALSE
MENU002,Veg Sandwich,RM002,Burger Bun,2,Piece,TRUE
MENU002,Veg Sandwich,RM003,Lettuce,20,Gram,FALSE
MENU002,Veg Sandwich,RM004,Tomato,3,Slice,FALSE
MENU002,Veg Sandwich,RM005,Cheese Slice,2,Piece,TRUE
MENU002,Veg Sandwich,RM007,Cucumber,4,Slice,FALSE
MENU003,French Fries,RM008,Potato,200,Gram,TRUE
MENU003,French Fries,RM009,Cooking Oil,50,ML,TRUE
MENU003,French Fries,RM010,Salt,5,Gram,FALSE
```

### Business Rules

- **Each menu item:** Must have 3-8 ingredients
- **Critical ingredients:** At least 1 per item (usually main protein/base)
- **Quantities:** Must be realistic for one serving
- **Total recipes:** If you have 20 menu items × 5 ingredients avg = ~100 rows

---

## File 3: raw_material_inventory.csv

### Purpose

Master list of all raw materials (ingredients) with stock levels and reorder parameters.

### Schema

```csv
material_id,material_name,category,unit,unit_cost_inr,reorder_level,reorder_qty,current_stock,max_stock,lead_time_days,shelf_life_days,storage_temp_c,is_perishable,supplier_id,last_restock_date,created_at
```

### Column Definitions


| Column              | Type     | Description             | Example         | Required | Constraints                                                        |
| ------------------- | -------- | ----------------------- | --------------- | -------- | ------------------------------------------------------------------ |
| `material_id`       | String   | Unique material ID      | RM001           | Yes      | Format: RM###                                                      |
| `material_name`     | String   | Material name           | Chicken Breast  | Yes      | 3-50 chars                                                         |
| `category`          | String   | Material category       | Proteins        | Yes      | Enum: Proteins, Vegetables, Dairy, Bakery, Spices, Beverages, Oils |
| `unit`              | String   | Unit of measurement     | Gram            | Yes      | Gram, Kg, Piece, Litre, ML                                         |
| `unit_cost_inr`     | Integer  | Cost per unit (paise)   | 50 (₹0.50/gram) | Yes      | > 0                                                                |
| `reorder_level`     | Integer  | When to reorder         | 500             | Yes      | 20-30% of max_stock                                                |
| `reorder_qty`       | Integer  | How much to order       | 2000            | Yes      | Enough for 5-7 days                                                |
| `current_stock`     | Integer  | Current stock level     | 1200            | Yes      | 0 to max_stock                                                     |
| `max_stock`         | Integer  | Storage capacity        | 3000            | Yes      | > reorder_level                                                    |
| `lead_time_days`    | Integer  | Supplier delivery time  | 2               | Yes      | 1-7 days                                                           |
| `shelf_life_days`   | Integer  | How long it lasts       | 3               | No       | For perishables                                                    |
| `storage_temp_c`    | Integer  | Storage temperature     | 4               | No       | Fridge=4, Freezer=-18, Room=25                                     |
| `is_perishable`     | Boolean  | Does it expire quickly? | TRUE            | Yes      | TRUE/FALSE                                                         |
| `supplier_id`       | String   | Supplier reference      | SUP001          | No       | From supplier_master.csv                                           |
| `last_restock_date` | Date     | Last restocked          | 2025-02-20      | No       | YYYY-MM-DD                                                         |
| `created_at`        | DateTime | When added              | 2024-01-15      | Yes      | ISO 8601                                                           |


### Sample Data

```csv
material_id,material_name,category,unit,unit_cost_inr,reorder_level,reorder_qty,current_stock,max_stock,lead_time_days,shelf_life_days,storage_temp_c,is_perishable,supplier_id,last_restock_date,created_at
RM001,Chicken Breast,Proteins,Gram,50,500,2000,1200,3000,2,3,4,TRUE,SUP001,2025-02-20,2024-01-15
RM002,Burger Bun,Bakery,Piece,800,20,100,45,150,1,2,25,TRUE,SUP002,2025-02-22,2024-01-15
RM003,Lettuce,Vegetables,Gram,10,300,1000,650,1500,1,2,4,TRUE,SUP003,2025-02-21,2024-01-15
RM004,Tomato,Vegetables,Slice,500,50,200,120,300,1,3,25,TRUE,SUP003,2025-02-21,2024-01-15
RM005,Cheese Slice,Dairy,Piece,1500,30,100,55,150,3,7,4,TRUE,SUP001,2025-02-19,2024-01-15
RM006,Mayonnaise,Dairy,Gram,20,500,2000,1100,3000,5,30,4,FALSE,SUP002,2025-02-15,2024-01-15
RM007,Cucumber,Vegetables,Slice,300,50,200,85,250,1,3,4,TRUE,SUP003,2025-02-22,2024-01-15
RM008,Potato,Vegetables,Gram,5,1000,5000,2800,8000,2,7,25,FALSE,SUP003,2025-02-20,2024-01-15
RM009,Cooking Oil,Oils,ML,5,2000,10000,6500,15000,7,90,25,FALSE,SUP004,2025-02-10,2024-01-15
RM010,Salt,Spices,Gram,1,1000,5000,3200,8000,7,365,25,FALSE,SUP004,2025-01-15,2024-01-15
```

### Business Rules

- **Perishables:** Fresh produce, dairy, meats (2-7 day shelf life)
- **Non-perishables:** Spices, oils, frozen items (30-365 day shelf life)
- **Reorder level:** 20-30% of max stock
- **Lead times:**
  - Local suppliers (vegetables): 1-2 days
  - Dairy/meat: 2-3 days
  - Dry goods: 5-7 days
- **Storage temps:**
  - Fridge: 4°C (dairy, vegetables, meats)
  - Freezer: -18°C (frozen items)
  - Room: 25°C (dry goods, spices)

---

## File 4: orders.csv

### Purpose

Historical order transactions. This is the PRIMARY data for demand forecasting.

### Schema

```csv
order_id,order_number,order_date,order_time,order_hour,order_weekday,is_weekend,is_holiday,holiday_name,order_type,table_id,staff_id,status,total_amount,created_at,sent_to_kitchen_at,completed_at
```

### Column Definitions


| Column               | Type     | Description                | Example             | Required | Constraints                                               |
| -------------------- | -------- | -------------------------- | ------------------- | -------- | --------------------------------------------------------- |
| `order_id`           | String   | Unique order ID            | ORD00001            | Yes      | Format: ORD#####                                          |
| `order_number`       | String   | Human-readable number      | 2024-10-15-001      | Yes      | YYYY-MM-DD-###                                            |
| `order_date`         | Date     | Order date                 | 2024-10-15          | Yes      | YYYY-MM-DD                                                |
| `order_time`         | Time     | Order time                 | 12:35:00            | Yes      | HH:MM:SS                                                  |
| `order_hour`         | Integer  | Hour of day                | 12                  | Yes      | 0-23                                                      |
| `order_weekday`      | Integer  | Day of week                | 2                   | Yes      | 0=Mon, 6=Sun                                              |
| `is_weekend`         | Boolean  | Is Saturday/Sunday?        | FALSE               | Yes      | TRUE/FALSE                                                |
| `is_holiday`         | Boolean  | Is public holiday?         | FALSE               | Yes      | TRUE/FALSE                                                |
| `holiday_name`       | String   | Holiday name if applicable | Diwali              | No       | India holidays                                            |
| `order_type`         | String   | Order type                 | DINE_IN             | Yes      | DINE_IN, TAKEAWAY                                         |
| `table_id`           | String   | Table reference            | TBL001              | No       | For DINE_IN only                                          |
| `staff_id`           | String   | Staff who took order       | STF001              | Yes      | Format: STF###                                            |
| `status`             | String   | Order status               | COMPLETED           | Yes      | DRAFT, SENT_TO_KITCHEN, IN_PROGRESS, COMPLETED, CANCELLED |
| `total_amount`       | Integer  | Total in paise             | 50000 (₹500)        | Yes      | Sum of items                                              |
| `created_at`         | DateTime | Order created              | 2024-10-15T12:35:00 | Yes      | ISO 8601                                                  |
| `sent_to_kitchen_at` | DateTime | Sent to kitchen            | 2024-10-15T12:36:00 | No       | For non-DRAFT                                             |
| `completed_at`       | DateTime | Order completed            | 2024-10-15T13:05:00 | No       | For COMPLETED                                             |


### Sample Data

```csv
order_id,order_number,order_date,order_time,order_hour,order_weekday,is_weekend,is_holiday,holiday_name,order_type,table_id,staff_id,status,total_amount,created_at,sent_to_kitchen_at,completed_at
ORD00001,2024-10-15-001,2024-10-15,12:35:00,12,1,FALSE,FALSE,,DINE_IN,TBL001,STF001,COMPLETED,50000,2024-10-15T12:35:00,2024-10-15T12:36:00,2024-10-15T13:05:00
ORD00002,2024-10-15-002,2024-10-15,12:48:00,12,1,FALSE,FALSE,,TAKEAWAY,,STF002,COMPLETED,33000,2024-10-15T12:48:00,2024-10-15T12:49:00,2024-10-15T13:12:00
ORD00003,2024-10-15-003,2024-10-15,13:15:00,13,1,FALSE,FALSE,,DINE_IN,TBL003,STF001,COMPLETED,45000,2024-10-15T13:15:00,2024-10-15T13:16:00,2024-10-15T13:40:00
ORD00004,2024-10-15-004,2024-10-15,19:20:00,19,1,FALSE,FALSE,,DINE_IN,TBL005,STF003,COMPLETED,62000,2024-10-15T19:20:00,2024-10-15T19:21:00,2024-10-15T19:55:00
ORD00005,2024-10-15-005,2024-10-15,20:10:00,20,1,FALSE,FALSE,,TAKEAWAY,,STF002,CANCELLED,28000,2024-10-15T20:10:00,,,
```

### Business Rules - CRITICAL for Forecasting

**Time Patterns:**

- **Lunch rush (12:00-14:00):** 35% of daily orders
- **Dinner rush (19:00-21:00):** 25% of daily orders
- **Morning (11:00-12:00):** 10% of daily orders
- **Afternoon (14:00-17:00):** 15% of daily orders
- **Late evening (21:00-22:00):** 15% of daily orders

**Weekly Patterns:**

- **Monday-Tuesday:** 40-50 orders/day (slow)
- **Wednesday-Thursday:** 60-70 orders/day
- **Friday-Sunday:** 90-130 orders/day (busy)
- **Weekend boost:** 50-80% higher than weekday

**Holiday/Event Patterns:**

- **Normal days:** Baseline orders
- **Major holidays (Diwali, Holi):** +50-100% orders
- **Minor holidays:** +20-30% orders
- Include 2-3 major holidays in your 90-120 day period

**Cancellation Rate:**

- 5-8% of orders should be CANCELLED
- More cancellations during peak hours

**Total Orders Needed:**

- 90 days: ~6,000 orders (avg 66/day)
- 120 days: ~8,000 orders (avg 66/day)

---

## File 5: order_line_items.csv

### Purpose

Line items for each order (what items were ordered).

### Schema

```csv
order_item_id,order_id,menu_item_id,menu_item_name,quantity,price_snapshot,notes,item_status,created_at
```

### Column Definitions


| Column           | Type     | Description                 | Example             | Required | Constraints                  |
| ---------------- | -------- | --------------------------- | ------------------- | -------- | ---------------------------- |
| `order_item_id`  | String   | Unique item ID              | ITEM00001           | Yes      | Format: ITEM#####            |
| `order_id`       | String   | Order reference             | ORD00001            | Yes      | Must exist in orders.csv     |
| `menu_item_id`   | String   | Menu item reference         | MENU001             | Yes      | Must exist in menu_items.csv |
| `menu_item_name` | String   | Item name snapshot          | Chicken Burger      | Yes      | Historical record            |
| `quantity`       | Integer  | Quantity ordered            | 2                   | Yes      | 1-10 (rarely >4)             |
| `price_snapshot` | Integer  | Price at order time (paise) | 25000               | Yes      | From menu_items              |
| `notes`          | String   | Special instructions        | No onions           | No       | Max 100 chars                |
| `item_status`    | String   | Item status                 | READY               | Yes      | PENDING, COOKING, READY      |
| `created_at`     | DateTime | When added                  | 2024-10-15T12:35:00 | Yes      | ISO 8601                     |


### Sample Data

```csv
order_item_id,order_id,menu_item_id,menu_item_name,quantity,price_snapshot,notes,item_status,created_at
ITEM00001,ORD00001,MENU001,Chicken Burger,2,25000,,READY,2024-10-15T12:35:00
ITEM00002,ORD00001,MENU003,French Fries,1,8000,,READY,2024-10-15T12:35:00
ITEM00003,ORD00002,MENU002,Veg Sandwich,1,15000,No mayo,READY,2024-10-15T12:48:00
ITEM00004,ORD00002,MENU005,Mango Lassi,2,7000,,READY,2024-10-15T12:48:00
ITEM00005,ORD00003,MENU001,Chicken Burger,1,25000,,READY,2024-10-15T13:15:00
ITEM00006,ORD00003,MENU004,Masala Dosa,1,12000,Extra spicy,READY,2024-10-15T13:15:00
ITEM00007,ORD00003,MENU003,French Fries,1,8000,,READY,2024-10-15T13:15:00
```

### Business Rules

- **Average items per order:** 1.5-2.5 items
- **Popular combinations:**
  - Main course + beverage (40%)
  - Main course + starter (30%)
  - Main course only (20%)
  - Multiple main courses (10%)
- **Quantity distribution:**
  - Qty 1: 70% of items
  - Qty 2: 25% of items
  - Qty 3+: 5% of items

---

## File 6: stock_movement_log.csv

### Purpose

Track all inventory movements (consumption, restocks, waste).

### Schema

```csv
movement_id,material_id,material_name,movement_type,quantity,movement_date,movement_time,reference_order_id,notes,created_by,created_at
```

### Column Definitions


| Column               | Type     | Description                             | Example              | Required | Constraints                             |
| -------------------- | -------- | --------------------------------------- | -------------------- | -------- | --------------------------------------- |
| `movement_id`        | String   | Unique movement ID                      | MOV00001             | Yes      | Format: MOV#####                        |
| `material_id`        | String   | Material reference                      | RM001                | Yes      | From inventory                          |
| `material_name`      | String   | Material name                           | Chicken Breast       | Yes      | For readability                         |
| `movement_type`      | String   | Type of movement                        | CONSUMPTION          | Yes      | RESTOCK, CONSUMPTION, WASTE, ADJUSTMENT |
| `quantity`           | Integer  | Amount (negative for consumption/waste) | -150                 | Yes      | Can be negative                         |
| `movement_date`      | Date     | Movement date                           | 2024-10-15           | Yes      | YYYY-MM-DD                              |
| `movement_time`      | Time     | Movement time                           | 13:05:00             | Yes      | HH:MM:SS                                |
| `reference_order_id` | String   | Order reference if consumption          | ORD00001             | No       | For CONSUMPTION                         |
| `notes`              | String   | Additional notes                        | Chicken Burger order | No       | Max 200 chars                           |
| `created_by`         | String   | Who created this                        | SYSTEM               | Yes      | SYSTEM, STF###                          |
| `created_at`         | DateTime | When created                            | 2024-10-15T13:05:00  | Yes      | ISO 8601                                |


### Sample Data

```csv
movement_id,material_id,material_name,movement_type,quantity,movement_date,movement_time,reference_order_id,notes,created_by,created_at
MOV00001,RM001,Chicken Breast,CONSUMPTION,-300,2024-10-15,13:05:00,ORD00001,Used for 2x Chicken Burger,SYSTEM,2024-10-15T13:05:00
MOV00002,RM002,Burger Bun,CONSUMPTION,-2,2024-10-15,13:05:00,ORD00001,Used for 2x Chicken Burger,SYSTEM,2024-10-15T13:05:00
MOV00003,RM001,Chicken Breast,RESTOCK,2000,2024-10-16,08:00:00,,Supplier delivery,STF001,2024-10-16T08:00:00
MOV00004,RM003,Lettuce,WASTE,-100,2024-10-17,10:00:00,,Expired - browning,STF002,2024-10-17T10:00:00
MOV00005,RM008,Potato,ADJUSTMENT,500,2024-10-17,11:00:00,,Stock count correction,STF001,2024-10-17T11:00:00
```

### Business Rules

- **CONSUMPTION:** Create one movement per material per order (based on recipe_bom)
- **RESTOCK:** Every 3-7 days per material (based on lead_time_days)
- **WASTE:** 2-5% of perishables should have waste movements
- **ADJUSTMENT:** Occasional stock count corrections

**Total Movements (90 days):**

- Consumption: ~400-600 (based on orders × items × ingredients)
- Restocks: ~100-150 (materials × restocks)
- Waste: ~20-30
- Adjustments: ~5-10

---

## File 7: supplier_master.csv (OPTIONAL - Low Priority)

### Purpose

Supplier contact information.

### Schema

```csv
supplier_id,supplier_name,contact_person,phone,email,address,city,state,pincode,payment_terms,is_active,created_at
```

### Sample Data

```csv
supplier_id,supplier_name,contact_person,phone,email,address,city,state,pincode,payment_terms,is_active,created_at
SUP001,Fresh Meats Co,Rajesh Kumar,+91-9876543210,rajesh@freshmeats.com,123 MG Road,Bangalore,Karnataka,560001,NET_30,TRUE,2024-01-10
SUP002,Daily Bakery,Priya Sharma,+91-9876543211,priya@dailybakery.com,45 Brigade Road,Bangalore,Karnataka,560025,CASH,TRUE,2024-01-10
SUP003,Veggie Fresh,Amit Patel,+91-9876543212,amit@veggiefresh.com,78 Indiranagar,Bangalore,Karnataka,560038,NET_15,TRUE,2024-01-10
SUP004,Spice World,Sunita Reddy,+91-9876543213,sunita@spiceworld.com,90 Koramangala,Bangalore,Karnataka,560034,NET_30,TRUE,2024-01-10
```

---

## MongoDB Collections Schema

### Required Collections (Auto-created by Orchestrator)

**1. menu_items**

```javascript
{
  _id: ObjectId("..."),
  menu_item_id: "MENU001",
  name: "Chicken Burger",
  category: "Main Course",
  price: 25000,  // paise
  description: "...",
  prep_type: "GRILL",
  tags: ["CHICKEN", "DAIRY"],
  is_available: true,
  popularity_score: 9,
  created_at: ISODate("2024-01-15"),
  updated_at: ISODate("2024-01-15")
}
```

**Indexes:**

- `menu_item_id` (unique)
- `category`
- `is_available`

---

**2. recipe_bom**

```javascript
{
  _id: ObjectId("..."),
  menu_item_id: "MENU001",
  menu_item_name: "Chicken Burger",
  ingredients: [
    {
      material_id: "RM001",
      material_name: "Chicken Breast",
      quantity_per_serving: 150,
      unit: "Gram",
      is_critical: true
    },
    {
      material_id: "RM002",
      material_name: "Burger Bun",
      quantity_per_serving: 1,
      unit: "Piece",
      is_critical: true
    }
  ],
  created_at: ISODate("2024-01-15"),
  updated_at: ISODate("2024-01-15")
}
```

**Indexes:**

- `menu_item_id` (unique)
- `ingredients.material_id`

---

**3. raw_material_inventory**

```javascript
{
  _id: ObjectId("..."),
  material_id: "RM001",
  material_name: "Chicken Breast",
  category: "Proteins",
  unit: "Gram",
  unit_cost_inr: 50,  // paise
  reorder_level: 500,
  reorder_qty: 2000,
  current_stock: 1200,
  max_stock: 3000,
  lead_time_days: 2,
  shelf_life_days: 3,
  storage_temp_c: 4,
  is_perishable: true,
  supplier_id: "SUP001",
  last_restock_date: ISODate("2025-02-20"),
  created_at: ISODate("2024-01-15"),
  updated_at: ISODate("2025-02-20")
}
```

**Indexes:**

- `material_id` (unique)
- `category`
- `is_perishable`
- `current_stock` (for low-stock queries)

---

**4. orders**

```javascript
{
  _id: ObjectId("..."),
  order_id: "ORD00001",
  order_number: "2024-10-15-001",
  order_date: ISODate("2024-10-15"),
  order_time: "12:35:00",
  order_hour: 12,
  order_weekday: 1,
  is_weekend: false,
  is_holiday: false,
  holiday_name: null,
  order_type: "DINE_IN",
  table_id: "TBL001",
  staff_id: "STF001",
  status: "COMPLETED",
  items: [
    {
      menu_item_id: "MENU001",
      menu_item_name: "Chicken Burger",
      quantity: 2,
      price_snapshot: 25000,
      notes: "",
      item_status: "READY"
    }
  ],
  total_amount: 50000,  // paise
  created_at: ISODate("2024-10-15T12:35:00"),
  sent_to_kitchen_at: ISODate("2024-10-15T12:36:00"),
  completed_at: ISODate("2024-10-15T13:05:00")
}
```

**Indexes:**

- `order_id` (unique)
- `order_date`
- `status`
- `order_date + order_hour` (for time-series queries)

---

**5. stock_movements**

```javascript
{
  _id: ObjectId("..."),
  movement_id: "MOV00001",
  material_id: "RM001",
  material_name: "Chicken Breast",
  movement_type: "CONSUMPTION",
  quantity: -300,  // negative for consumption/waste
  movement_date: ISODate("2024-10-15"),
  movement_time: "13:05:00",
  reference_order_id: "ORD00001",
  notes: "Used for 2x Chicken Burger",
  created_by: "SYSTEM",
  created_at: ISODate("2024-10-15T13:05:00")
}
```

**Indexes:**

- `movement_id` (unique)
- `material_id`
- `movement_type`
- `movement_date`

---

**6. demand_forecasts** (Created by Orchestrator)

```javascript
{
  _id: ObjectId("..."),
  material_id: "RM001",
  forecast_date: ISODate("2025-02-24"),
  forecast_horizon_days: 7,
  predicted_consumption: 45.2,
  confidence_lower: 38.1,
  confidence_upper: 52.3,
  confidence_score: 0.85,
  model_version: "prophet_v1",
  ai_adjustments: {
    baseline_forecast: 42.0,
    weather_adjustment: 2.0,
    event_adjustment: 1.2,
    reasoning: "Local food festival expected"
  },
  contributing_menu_items: [
    {
      menu_item_id: "MENU001",
      forecast_qty: 35,
      ingredient_qty_required: 35
    }
  ],
  generated_at: ISODate("2025-02-23T00:00:00"),
  generated_by: "demand_forecaster_v1"
}
```

---

**7. agent_decisions** (Created by Orchestrator)

```javascript
{
  _id: ObjectId("..."),
  agent_name: "inventory",
  timestamp: ISODate("2025-02-24T06:00:00"),
  decision: {
    actions: [
      {
        action_type: "purchase_order",
        data: {
          material_id: "RM001",
          quantity: 2000,
          estimated_cost: 100000
        },
        estimated_cost: 100000,
        reasoning: "Forecast shows stockout in 4 days, lead time is 2 days",
        confidence: 0.92
      }
    ],
    reasoning: "Daily inventory check",
    confidence: 0.92
  },
  status: "pending_approval",  // or "executed" or "approved"
  approved_at: null,
  approved_by: null
}
```

---

## Data Import Script Template

After creating CSV files, use this script to import into MongoDB:

```python
import pandas as pd
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

async def import_test_data():
    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["ahar_pos"]

    # Import menu items
    menu_df = pd.read_csv("menu_items.csv")
    menu_df['price'] = menu_df['price_inr']  # Rename for DB
    menu_df['tags'] = menu_df['tags'].str.split(',')  # Convert to array
    await db.menu_items.insert_many(menu_df.to_dict('records'))

    # Import recipe BOM (needs aggregation)
    recipe_df = pd.read_csv("recipe_bom.csv")
    recipes = recipe_df.groupby('menu_item_id').apply(lambda x: {
        'menu_item_id': x.iloc[0]['menu_item_id'],
        'menu_item_name': x.iloc[0]['menu_item_name'],
        'ingredients': x[['material_id', 'material_name', 'quantity_per_serving', 'unit', 'is_critical']].to_dict('records')
    }).tolist()
    await db.recipe_bom.insert_many(recipes)

    # Import raw materials
    inventory_df = pd.read_csv("raw_material_inventory.csv")
    await db.raw_material_inventory.insert_many(inventory_df.to_dict('records'))

    # Import orders (with embedded items)
    orders_df = pd.read_csv("orders.csv")
    items_df = pd.read_csv("order_line_items.csv")

    for _, order in orders_df.iterrows():
        order_items = items_df[items_df['order_id'] == order['order_id']]
        order_doc = order.to_dict()
        order_doc['items'] = order_items[['menu_item_id', 'menu_item_name', 'quantity', 'price_snapshot', 'notes', 'item_status']].to_dict('records')
        await db.orders.insert_one(order_doc)

    # Import stock movements
    movements_df = pd.read_csv("stock_movement_log.csv")
    await db.stock_movements.insert_many(movements_df.to_dict('records'))

    print("Import complete!")

asyncio.run(import_test_data())
```

---

## Validation Checklist

Before proceeding to Week 2 implementation:

- **menu_items.csv:** 15-25 items, all columns filled
- **recipe_bom.csv:** Every menu item has 3-8 ingredients
- **raw_material_inventory.csv:** 30-50 materials, realistic stock levels
- **orders.csv:** 6,000-8,000 orders over 90-120 days
- **order_line_items.csv:** Avg 1.5-2.5 items per order
- **stock_movement_log.csv:** 500-800 movements (optional for now)
- All material_id in recipe_bom exist in raw_material_inventory
- All menu_item_id in recipe_bom exist in menu_items
- Order dates follow realistic time patterns (lunch/dinner rush)
- Prices in paise (multiply by 100)
- Dates in ISO 8601 format (YYYY-MM-DD)

---

## Quick Start Guide

1. **Create CSV files** in `/Users/pandiarajan/Ahar.AI/test_data/`
2. **Start with small dataset first:**
  - 5 menu items
  - 15 ingredients
  - 500 orders (1 week)
  - Verify it works
3. **Scale up to full dataset:**
  - 20 menu items
  - 40 ingredients
  - 7,000 orders (90 days)
4. **Import to MongoDB** using script above
5. **Verify in MongoDB:**
  ```bash
   mongosh
   use ahar_pos
   db.orders.countDocuments()  # Should show order count
   db.recipe_bom.find().limit(3)  # Verify structure
  ```

---

## Timeline Recommendation

- **Day 1:** Create menu_items.csv + recipe_bom.csv (2-3 hours)
- **Day 2:** Create raw_material_inventory.csv (1 hour)
- **Day 3:** Generate orders.csv + order_line_items.csv (3-4 hours or use generator)
- **Day 4:** Create stock_movement_log.csv (optional, 1-2 hours)
- **Day 5:** Import to MongoDB, verify, ready for Week 2!

---

## Need Help?

- **Realistic quantities:** 1 burger = 150g chicken, 1 bun, 2 tomato slices
- **Price ranges:** Main course ₹100-300, Starters ₹50-150
- **Order patterns:** 65% lunch (12-2pm), 35% dinner (7-9pm)
- **Stock levels:** Current = 40-60% of max_stock

**When ready, share the CSV files location and I'll help with MongoDB import!**