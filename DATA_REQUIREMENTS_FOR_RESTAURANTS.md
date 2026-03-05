# Data Requirements for AI-Powered Demand Forecasting & Inventory Optimization

**Prepared for:** Restaurant Partners
**Prepared by:** Ahar.AI
**Date:** March 2026
**Purpose:** Implementing ML-based demand forecasting to reduce wastage and improve margins

---

## Executive Summary

To build an industry-benchmark level demand forecasting system, we need **minimum 6 months of historical data** (ideally 12+ months for best accuracy). The more complete and accurate the data, the better our predictions will be.

**Expected Outcomes:**
- 50-70% reduction in food wastage
- 3-5% improvement in gross margins
- 80-90% reduction in stock-out events
- Better cash flow management

---

## SECTION 1: HISTORICAL DATA REQUIRED

### 📊 **1. ORDER HISTORY DATA**

**Duration Required:** Minimum 6 months, Ideal 12-24 months

**What We Need:**

| Field Name | Description | Example | Format |
|------------|-------------|---------|--------|
| Order ID | Unique order identifier | ORD00001 | Text |
| Order Date | Date order was placed | 2025-10-21 | YYYY-MM-DD |
| Order Time | Time order was placed | 13:45:30 | HH:MM:SS |
| Order Type | Dine-in or Takeaway/Delivery | DINE_IN | Text |
| Table Number | For dine-in orders | Table 5 | Text/Number |
| Order Status | Completed, Cancelled, etc. | COMPLETED | Text |
| Total Amount | Total bill amount | 450.00 | Number (INR) |

**Why We Need This:** Understand order patterns by time, day, and type

---

### 🍔 **2. ORDER LINE ITEMS (Individual Menu Items)**

**Duration Required:** Same as order history (6-12 months)

**What We Need:**

| Field Name | Description | Example | Format |
|------------|-------------|---------|--------|
| Order ID | Links to order | ORD00001 | Text |
| Menu Item Name | Name of dish ordered | Smoky Chicken Burger | Text |
| Menu Item ID/Code | Unique item code (if any) | MENU001 | Text |
| Quantity | Number of items ordered | 2 | Number |
| Unit Price | Price per item | 225.00 | Number (INR) |
| Category | Menu category | Burgers | Text |

**Why We Need This:** Predict demand for each menu item

---

### 📋 **3. MENU MASTER DATA**

**Duration Required:** Current menu + any historical menu changes

**What We Need:**

| Field Name | Description | Example | Format |
|------------|-------------|---------|--------|
| Menu Item ID | Unique identifier | MENU001 | Text |
| Menu Item Name | Dish name | Smoky Chicken Burger | Text |
| Category | Menu category | Burgers | Text |
| Price | Current selling price | 225.00 | Number (INR) |
| Is Available | Currently on menu? | Yes | Yes/No |
| Prep Time | Cooking time in minutes | 12 | Number |
| Is Vegetarian | Veg or Non-Veg | No | Yes/No |

**Why We Need This:** Map items to ingredients and understand menu structure

---

### 🥬 **4. RECIPE / BILL OF MATERIALS (BOM)**

**Duration Required:** Current recipes (critical for forecasting)

**What We Need:** For each menu item, list of ingredients and quantities

| Field Name | Description | Example | Format |
|------------|-------------|---------|--------|
| Menu Item Name | Dish name | Smoky Chicken Burger | Text |
| Ingredient Name | Raw material name | Chicken Breast | Text |
| Quantity per Serving | Amount needed per dish | 140 | Number |
| Unit | Unit of measurement | Grams | Text |
| Is Critical | Must-have ingredient? | Yes | Yes/No |

**Example:**
```
Smoky Chicken Burger:
- Chicken Breast: 140g (Critical)
- Burger Bun: 1 piece (Critical)
- Lettuce: 20g
- Tomato: 25g
- Cheese Slice: 1 piece
- Mayonnaise: 18g
```

**Why We Need This:** Convert menu item demand to raw material requirements

---

### 📦 **5. RAW MATERIAL INVENTORY DATA**

**Duration Required:** Current inventory + 6-12 months of history if available

**What We Need:**

| Field Name | Description | Example | Format |
|------------|-------------|---------|--------|
| Material Name | Ingredient name | Chicken Breast | Text |
| Material ID/Code | Unique identifier (if any) | RM001 | Text |
| Category | Type of ingredient | Proteins | Text |
| Unit | Measurement unit | Grams/Kg/Liters/Pieces | Text |
| Unit Cost | Cost per unit | 0.60 | Number (INR per gram) |
| Current Stock | Stock on hand today | 5000 | Number |
| Reorder Level | When to reorder | 3000 | Number |
| Max Stock | Maximum storage capacity | 15000 | Number |
| Shelf Life | Days before expiry | 5 | Number (days) |
| Lead Time | Days for supplier delivery | 2 | Number (days) |
| Storage Temp | Storage requirement | 4°C / Room Temp | Text |
| Is Perishable | Perishable or not | Yes | Yes/No |
| Supplier Name | Primary supplier | ABC Suppliers | Text |

**Why We Need This:** Understand inventory constraints, costs, and limitations

---

### 📥 **6. PURCHASE / RESTOCK HISTORY**

**Duration Required:** 6-12 months

**What We Need:**

| Field Name | Description | Example | Format |
|------------|-------------|---------|--------|
| Purchase Date | Date of purchase | 2025-10-15 | YYYY-MM-DD |
| Material Name | What was purchased | Chicken Breast | Text |
| Quantity | Amount purchased | 10000 | Number |
| Unit | Measurement unit | Grams | Text |
| Total Cost | Total amount paid | 6000.00 | Number (INR) |
| Supplier Name | Who supplied | ABC Suppliers | Text |
| Expected Delivery Date | When ordered | 2025-10-13 | YYYY-MM-DD |
| Actual Delivery Date | When delivered | 2025-10-15 | YYYY-MM-DD |

**Why We Need This:** Understand supplier reliability and purchasing patterns

---

## SECTION 2: CRITICAL OPERATIONAL DATA (START COLLECTING NOW)

### 🗑️ **7. DAILY WASTAGE LOG** ⚠️ **MOST IMPORTANT**

**Duration Required:** Start collecting immediately, need minimum 4 weeks for model training

**What We Need:** End-of-day wastage for each ingredient

| Field Name | Description | Example | Format |
|------------|-------------|---------|--------|
| Date | Date of wastage | 2026-03-05 | YYYY-MM-DD |
| Material Name | Ingredient wasted | Chicken Breast | Text |
| Quantity Wasted | Amount thrown away | 250 | Number |
| Unit | Measurement unit | Grams | Text |
| Reason | Why wasted | Expired / Over-prep / Spoilage / Quality Issue | Text |
| Estimated Cost | Value of waste | 150.00 | Number (INR) |
| Recorded By | Staff name | Chef Kumar | Text |

**How to Collect:**
- Kitchen staff fills form at end of each day
- Takes 5 minutes per day
- Mobile/tablet app or simple paper form

**Why Critical:** This is your PRIMARY metric for measuring success. Without wastage data, we cannot prove ROI.

---

### ⛔ **8. STOCK-OUT EVENTS LOG**

**Duration Required:** Start collecting immediately

**What We Need:** Record when you run out of ingredients

| Field Name | Description | Example | Format |
|------------|-------------|---------|--------|
| Date | Date of stock-out | 2026-03-05 | YYYY-MM-DD |
| Time | Time ran out | 14:30 | HH:MM |
| Material Name | What ran out | Burger Buns | Text |
| Orders Affected | How many orders couldn't be fulfilled | 8 | Number |
| Menu Items Affected | Which dishes unavailable | Smoky Chicken Burger, Veggie Burger | Text |
| Estimated Revenue Loss | Lost sales | 1800.00 | Number (INR) |
| When Restocked | When back in stock | 2026-03-06 10:00 | YYYY-MM-DD HH:MM |

**Why Critical:** Measures opportunity cost of under-ordering

---

### 🔄 **9. DAILY STOCK LEVELS** (Optional but Helpful)

**Duration Required:** Start collecting if possible

**What We Need:** Opening and closing stock each day

| Field Name | Description | Example | Format |
|------------|-------------|---------|--------|
| Date | Date of measurement | 2026-03-05 | YYYY-MM-DD |
| Material Name | Ingredient name | Chicken Breast | Text |
| Opening Stock | Stock at start of day | 5000 | Number |
| Closing Stock | Stock at end of day | 3500 | Number |
| Unit | Measurement unit | Grams | Text |

**Why Helpful:** Validates actual consumption vs predicted consumption

---

## SECTION 3: EXTERNAL CONTEXT DATA (WE CAN COLLECT)

### 🌤️ **10. WEATHER DATA**
**We will collect this automatically via API**
- Temperature, rainfall, weather conditions
- Just need your restaurant location/city

### 📅 **11. LOCAL HOLIDAYS & EVENTS**
**We will collect this, but need your input on:**
- Local festivals important in your area
- Nearby events that affect traffic (markets, sports events, etc.)
- School holidays / exam periods

### 📢 **12. PROMOTIONS & OFFERS** (If Applicable)
**Duration Required:** Historical data + ongoing updates

| Field Name | Description | Example |
|------------|-------------|---------|
| Promotion Date | When offer ran | 2025-12-25 |
| Promotion Name | Name/type of offer | "Buy 1 Get 1" |
| Menu Items Affected | Which items | All Burgers |
| Discount % | Discount amount | 50% |

---

## SECTION 4: DATA QUALITY REQUIREMENTS

### ✅ **Minimum Quality Standards**

1. **Completeness:** At least 90% of orders should have complete data (no missing dates/items)
2. **Accuracy:** Menu item names should be consistent (not "Chkn Burger" one day, "Chicken Burger" another)
3. **Consistency:** Units should be consistent (don't mix grams and kilograms)
4. **Cancelled Orders:** Include cancelled orders (marked as cancelled)
5. **Date Range:** No gaps in data (if closed on Mondays, that's fine, but no missing random days)

### 🚨 **Common Data Issues to Avoid**

- ❌ Inconsistent naming: "Chicken Burger" vs "Chkn Brgr" vs "Smoky Chicken Burger"
- ❌ Missing dates or times
- ❌ Aggregated data: Don't give us "50 burgers sold this week" - we need daily/hourly details
- ❌ Mixed units: Switching between grams, kg, ml, liters inconsistently
- ❌ Incomplete recipes: "We use chicken" - we need exact quantities (140g per burger)

---

## SECTION 5: DATA DELIVERY FORMAT

### 📁 **Preferred Formats**

1. **Excel (.xlsx) or CSV files** - Most common and easy
2. **Database dump** - If you have a POS system
3. **POS System Export** - Direct export from your billing software
4. **Google Sheets** - Can work for ongoing data collection

### 📋 **File Organization**

Please provide separate files for each data type:
```
1. orders.csv
2. order_line_items.csv
3. menu_items.csv
4. recipes_bom.csv
5. raw_materials.csv
6. purchase_history.csv
7. wastage_log.csv (start collecting now!)
8. stockout_log.csv (start collecting now!)
```

---

## SECTION 6: TIMELINE & EXPECTATIONS

### ⏱️ **Data Collection Timeline**

| Phase | Duration | Activities |
|-------|----------|------------|
| **Phase 1: Historical Data** | Week 1-2 | Restaurant provides 6-12 months historical data |
| **Phase 2: Data Cleaning** | Week 3 | We clean and validate data |
| **Phase 3: Wastage Tracking Setup** | Week 4 | Set up daily wastage/stockout logging |
| **Phase 4: Model Development** | Week 5-8 | Build and train forecasting models |
| **Phase 5: Pilot Testing** | Week 9-12 | Test predictions, measure accuracy |
| **Phase 6: Full Deployment** | Week 13+ | Go live with automated forecasting |

### 🎯 **Minimum Data for Industry-Benchmark Accuracy**

| Accuracy Level | Data Duration | Expected Results |
|----------------|---------------|------------------|
| **Basic** | 3 months | 60-70% accuracy, 30-40% wastage reduction |
| **Good** | 6 months | 75-85% accuracy, 50-60% wastage reduction |
| **Industry Benchmark** | 12+ months | 85-95% accuracy, 60-70% wastage reduction |

**Recommendation:** Start with 6 months minimum, but keep collecting data to continuously improve.

---

## SECTION 7: SUPPORT & NEXT STEPS

### 📞 **How We Can Help**

1. **Data Extraction:** If you're unsure how to export from your POS system, we can help
2. **Templates:** We can provide Excel templates for data you don't have in digital format
3. **Training:** We'll train your staff on daily wastage/stockout logging
4. **Ongoing Support:** Weekly check-ins during data collection phase

### 📝 **What Restaurant Needs to Do**

**Immediate (This Week):**
1. ✅ Identify who owns this data (manager, accountant, POS vendor)
2. ✅ Check if you can export historical order data from POS system
3. ✅ Confirm you have recipes documented (or can document them)
4. ✅ Start daily wastage tracking (even on paper)

**Within 2 Weeks:**
1. ✅ Provide historical order data (6-12 months)
2. ✅ Provide menu items and recipes
3. ✅ Provide raw material inventory list
4. ✅ Set up daily wastage logging routine

**Ongoing:**
1. ✅ Log daily wastage (5 min/day)
2. ✅ Log stock-out events when they happen
3. ✅ Inform us of menu changes, promotions

---

## SECTION 8: CONFIDENTIALITY & DATA SECURITY

- All data will be kept **strictly confidential**
- Data used only for building forecasting models for your restaurant
- No data shared with competitors or third parties
- Secure encrypted storage and transmission
- You retain full ownership of your data

---

## APPENDIX: SAMPLE DATA FORMATS

### Sample: orders.csv
```
order_id,order_date,order_time,order_type,table_number,status,total_amount
ORD00001,2025-10-21,11:03:34,DINE_IN,Table 2,COMPLETED,357.00
ORD00002,2025-10-21,11:36:34,DINE_IN,Table 16,COMPLETED,211.00
ORD00003,2025-10-21,11:40:30,TAKEAWAY,,COMPLETED,363.00
```

### Sample: order_line_items.csv
```
order_id,menu_item_name,quantity,unit_price
ORD00001,Smoky Chicken Burger,2,225.00
ORD00001,French Fries,1,89.00
ORD00002,Paneer Tikka Wrap,1,189.00
```

### Sample: recipes_bom.csv
```
menu_item_name,ingredient_name,quantity,unit,is_critical
Smoky Chicken Burger,Chicken Breast,140,Grams,Yes
Smoky Chicken Burger,Burger Bun,1,Piece,Yes
Smoky Chicken Burger,Lettuce,20,Grams,No
Smoky Chicken Burger,Tomato,25,Grams,No
```

### Sample: wastage_log.csv
```
date,material_name,quantity_wasted,unit,reason,cost_inr
2026-03-05,Chicken Breast,250,Grams,Expired,150.00
2026-03-05,Lettuce,100,Grams,Spoilage,12.00
2026-03-05,Burger Buns,5,Pieces,Quality Issue,45.00
```

---

## QUESTIONS?

For any questions or clarifications, please contact:
- **Email:** [Your contact email]
- **Phone:** [Your contact number]
- **Support Hours:** [Your support hours]

---

**Thank you for partnering with us to reduce wastage and improve profitability!**

*Ahar.AI - Intelligent Restaurant Operations*
