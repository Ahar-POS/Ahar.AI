---
name: pnl-statement
description: Generate comprehensive operational P&L (Profit & Loss) reports with detailed COGS, OPEX, depreciation, and KPIs. Use when user requests P&L, profit and loss statement, financial report, or mentions date ranges like "last week", "this month", or specific dates.
---

# Detailed P&L Statement Generator

## When to use

User requests P&L report with date range:
- "Generate P&L for last week" → Use **text format**
- "P&L for January 2024" → Use **text format**
- "Show me profit and loss from 2024-01-01 to 2024-12-31" → Use **text format**
- "Give me detailed P&L with COGS breakdown" → Use **text format**

User explicitly requests Excel file:
- "Generate P&L Excel for last month" → Use **excel format** (not yet implemented)
- "Download P&L spreadsheet for Q1" → Use **excel format** (not yet implemented)

**Default: Always use text format unless user explicitly asks for Excel file**

## Workflow

Copy this checklist and check off as you complete:

```
P&L Generation Progress:
- [ ] Step 1: Validate dates
- [ ] Step 2: Verify settings exist
- [ ] Step 3: Generate report
- [ ] Step 4: Verify output
```

**Step 1: Validate dates**

Run validation script:
```bash
python scripts/validate_dates.py <start_date> <end_date>
```

If output is "ERROR:", stop and report the issue to the user.
If output is "VALID", proceed to Step 2.

**Step 2: Verify settings exist**

The P&L generator requires restaurant settings to be configured. Settings are automatically created by the setup script.

If this is the first time running P&L, execute setup:
```bash
cd /backend
python scripts/setup_pnl_data.py default
```

This one-time setup creates:
- Restaurant configuration (commissions, salaries, OPEX budgets)
- Packaging materials and BOM
- Fixed assets for depreciation
- Sample historical data

**Step 3: Generate report**

Execute the generation script:
```bash
# Text format (default) - displays in chat
python scripts/generate_pnl.py <start_date> <end_date>

# Text format (explicit)
python scripts/generate_pnl.py <start_date> <end_date> text

# With custom restaurant ID
python scripts/generate_pnl.py <start_date> <end_date> text my_restaurant_id
```

Script will:
- Connect to MongoDB and query multiple collections
- Calculate detailed revenue breakdown (veg/non-veg/sides/beverages)
- Compute actual COGS from recipe BOM and material costs
- Add packaging costs from packaging BOM
- Calculate labour costs from active staff and role salaries
- Add proportionate OPEX from settings (rent, utilities, marketing, etc.)
- Calculate depreciation and amortization
- Compute finance costs and taxes
- Display formatted P&L table in chat output

**Step 4: Verify output**

Check script output for "SUCCESS:" message.

The P&L report includes:
- Section A: GMV breakdown by category
- Section B: Net Revenue (after commissions & GST)
- Section C: Detailed COGS (raw materials, packaging, wastage)
- Section D: Gross Profit & Margin
- Section E: OPEX (labour, occupancy, technology, marketing, G&A)
- Section F: EBITDA & Margin
- Section G: Depreciation & Amortization
- Section H: EBIT
- Section I: Finance Costs
- Section J: PBT
- Section K: Income Tax
- Section L: PAT (Profit After Tax) ★
- Section M: Key Performance Indicators

## Report Structure

### A. Gross Merchandise Value (GMV)
- Sandwich Revenue (Veg/Non-Veg breakdown)
- Sides Revenue
- Beverages Revenue
- Desserts Revenue
- Less: Cancellations (1.5% default)
- **Net GMV**

### B. Revenue (Net Platform Commissions & GST)
- Less: Zomato Commission (configurable %, default 23%)
- Less: Swiggy Commission (configurable %, default 23%)
- Less: GST on Food (configurable %, default 5%)
- **NET REVENUE**

### C. Cost of Goods Sold (COGS)

#### C1. Raw Material – Food & Beverage
Actual costs calculated from:
- recipe_bom (ingredients per menu item)
- raw_material_inventory (unit costs)
- order_line_items (quantities sold)

Breakdown by category: Proteins, Vegetables, Bakery, Dairy, Condiments, etc.

#### C2. Packaging Material
Actual costs calculated from:
- packaging_bom (packaging per menu item)
- packaging_materials (packaging unit costs)

Breakdown: Primary, Secondary, Labels

#### C3. Wastage & Other Food Costs
- Wastage & Spoilage (from stock_movement_log)
- Staff Meals (from stock_movement_log)
- Quality Control (from stock_movement_log)

### D. Gross Profit
- Net Revenue - Total COGS
- Gross Margin % (of Net Revenue)

### E. Operating Expenses (OPEX)

#### E1. Labour & HR Costs
- Staff Salaries (from users collection × role salaries)
- PF/ESIC Contributions (13.75% of salaries)
- Overtime Allowance (configurable per role)

#### E2. Occupancy & Utilities
- Kitchen Rent (configurable)
- Electricity & Power (configurable)
- Water Charges (configurable)
- Internet & Communication (configurable)

#### E3. Technology & Software
- POS Software License (configurable)
- Platform Subscriptions (configurable)
- Menu Photography Amortized (configurable)

#### E4. Sales & Marketing
- Zomato Ads (configurable)
- Swiggy Ads (configurable)
- Social Media Marketing (configurable)
- Influencer Marketing (configurable)
- Self-funded Discounts (configurable)

#### E5. General & Administrative
- Accounting/Bookkeeping (configurable)
- Legal & Compliance (configurable)
- Business Insurance (configurable)
- Cleaning Supplies (configurable)
- Pest Control (configurable)
- Repairs & Maintenance (configurable)
- Gas/LPG (configurable)
- Office Supplies (configurable)
- Miscellaneous (configurable)

**Note:** All OPEX values are proportionately calculated based on date range.
Example: For 15-day period, OPEX = (Monthly Budget / 30) × 15

### F. EBITDA
- Gross Profit - Total OPEX
- EBITDA Margin % (of Net Revenue)

### G. Depreciation & Amortization
- Equipment Depreciation (from fixed_assets)
- Brand Amortization (from fixed_assets)

### H. EBIT
- EBITDA - Depreciation & Amortization

### I. Finance Costs
- Interest on Loans (configurable)
- Bank/Payment Gateway Charges (configurable)

### J. Profit Before Tax (PBT)
- EBIT - Finance Costs

### K. Income Tax
- Presumptive Tax (26% default, configurable)

### L. Profit After Tax (PAT) ★
- PBT - Income Tax
- PAT Margin % (of Net Revenue)

### M. Key Performance Indicators
- Total Orders
- Average Order Value
- Food Cost % (of Net Revenue) - Target: <35%
- Labour Cost % (of Net Revenue) - Target: <25%
- Platform Commission % (of GMV)

## Data Sources

### Primary Collections

1. **delivery_orders** - Delivery platform orders (Zomato, Swiggy)
   - total_inr, discounts, tax, delivery_fee, packaging_charge, order_channel

2. **orders** - Dine-in/takeaway orders
   - order_date, total_amount, status

3. **order_line_items** - Line item details
   - menu_item_id, quantity, price_snapshot

4. **menu_items** - Menu catalog with categories
   - name, category, price, tags (for veg/non-veg classification)

5. **recipe_bom** - Recipe Bill of Materials
   - Links menu_item_id → material_id with quantities

6. **raw_material_inventory** - Material costs
   - material_id, unit_cost_inr, category

7. **packaging_bom** - Packaging requirements
   - Links menu_item_id → packaging_material_id

8. **packaging_materials** - Packaging costs
   - packaging_id, unit_cost_inr, category (PRIMARY/SECONDARY/LABELS)

9. **stock_movement_log** - Inventory movements
   - WASTE, STAFF_MEAL, QC_SAMPLE transactions

10. **users** - Staff directory
    - role, status (for active employee count)

11. **restaurant_settings** - Configuration
    - Platform commissions, role salaries, OPEX budgets, tax rates

12. **fixed_assets** - Asset register
    - Equipment, brand assets with depreciation schedules

### Database Connection

- Uses environment variables: `MONGODB_URI` (default: mongodb://localhost:27017)
- Database name: `DB_NAME` (default: ahar_pos)
- Restaurant ID: `RESTAURANT_ID` (default: 'default')

## Configuration

All configurable values are stored in `restaurant_settings` collection:

### Platform Settings
- Zomato commission rate (default: 23%)
- Swiggy commission rate (default: 23%)
- GST rate (default: 5%)
- Cancellation rate (default: 1.5%)

### Role Salaries (Monthly, in paise)
- cook, helper, packing_staff, supervisor, manager, waiter, admin

### PF/ESIC Settings
- PF employer rate (default: 12%)
- ESIC employer rate (default: 1.75%)

### Overtime Allowances (Monthly per role)

### OPEX Budgets (Monthly, in paise)
- Occupancy: rent, electricity, water, internet
- Technology: POS software, subscriptions, photography
- Marketing: platform ads, social media, influencer, discounts
- G&A: accounting, legal, insurance, cleaning, pest control, repairs, gas, office, misc

### Depreciation & Finance
- Equipment depreciation (monthly)
- Brand amortization (monthly)
- Loan interest (monthly)
- Bank charges (monthly)

### Tax
- Presumptive tax rate (default: 26%)

**To update settings:** Edit the `restaurant_settings` document in MongoDB or use the settings API (when implemented).

## Setup & Troubleshooting

### First-Time Setup

Before generating P&L for the first time, run:

```bash
cd /backend
python scripts/setup_pnl_data.py default
```

This creates:
- Default restaurant_settings
- 10 packaging materials (boxes, bags, stickers)
- Packaging BOM for all menu items
- 6 fixed assets (equipment, brand)
- Sample wastage/staff meal stock movements (4 months)

Safe to re-run - skips existing data.

### Common Issues

**Issue:** "No settings found, using defaults"
**Solution:** Run `python scripts/setup_pnl_data.py default`

**Issue:** "No orders found"
**Solution:** Check date range matches your order data period

**Issue:** "COGS is 0"
**Solution:** Ensure recipe_bom and raw_material_inventory are populated

**Issue:** "Packaging cost is 0"
**Solution:** Run setup script to create packaging_bom

**Issue:** "Labour cost is 0"
**Solution:** Ensure users collection has active staff with roles

## Important Notes

- Dates must be in YYYY-MM-DD format
- All monetary values stored in paise (smallest currency unit)
- OPEX is proportionately calculated based on date range
- Depreciation is proportionately calculated based on date range
- **Revenue categorization:**
  - Veg/Non-Veg: Based on menu item tags (CHICKEN, FISH, EGG = Non-Veg)
  - Sides: Items with category "Starter", "Appetizer", or "Side"
  - Beverages: Items with category "Beverage" or "Drink"
  - Desserts: Items with category "Dessert" or "Sweet"
- **COGS categorization:**
  - Raw materials: Grouped by category field (Proteins, Vegetables, Dairy, Bakery, Spices, Oils, Beverages)
  - Packaging: Grouped by category (PRIMARY, SECONDARY, LABELS)
- Staff count from active users in database
- Commission rates applied per channel (Zomato/Swiggy)
- Wastage/Staff Meals tracked via stock_movement_log
- Orders without restaurant_id field are included in calculations

## Example Output

```
======================================================================
PROFIT & LOSS STATEMENT
Period: 2024-01-01 to 2024-01-31
======================================================================

A. GROSS MERCHANDISE VALUE (GMV)
----------------------------------------------------------------------
  Main Course Revenue – Vegetarian                         ₹3,95,120
  Main Course Revenue – Non-Vegetarian                     ₹6,58,680
  Sides Revenue                                            ₹2,47,500
  Beverages Revenue                                           ₹50,000
  Gross GMV                                              ₹13,01,300
  Less: Cancellations (1.5%)                               ₹-19,520
----------------------------------------------------------------------
  Net GMV                                                ₹12,81,781

B. REVENUE (Net Platform Commissions & GST)
----------------------------------------------------------------------
  Less: Zomato Commission (23%)                           ₹-2,06,367
  Less: Swiggy Commission (23%)                             ₹-88,443
  Less: GST on Food (5%)                                    ₹-61,037
----------------------------------------------------------------------
  NET REVENUE                                              ₹9,25,934

C. COST OF GOODS SOLD (COGS)
----------------------------------------------------------------------
  C1. Raw Material – Food & Beverage
    Bakery                                                  ₹25,000
    Dairy                                                   ₹18,000
    Proteins                                               ₹1,10,000
    Vegetables                                              ₹20,000
    Sub-Total: Raw Material                                ₹2,65,000

  C2. Packaging Material
    Labels Packaging                                         ₹3,000
    Primary Packaging                                       ₹22,000
    Secondary Packaging                                     ₹12,000
    Sub-Total: Packaging                                    ₹37,000

  C3. Wastage & Other Food Costs
    Wastage & Spoilage                                      ₹18,000
    Staff Meals                                              ₹5,000
    Quality Control                                          ₹2,000
    Sub-Total: Wastage & Other                              ₹25,000
----------------------------------------------------------------------
  TOTAL COGS                                               ₹3,27,000

D. GROSS PROFIT
----------------------------------------------------------------------
  Gross Profit                                             ₹5,98,934
  Gross Margin %                                               64.7%

E. OPERATING EXPENSES (OPEX)
----------------------------------------------------------------------
  E1. Labour & HR Costs
    Staff Salaries (7 employees)                           ₹2,00,000
    PF/ESIC (13.75%)                                        ₹27,500
    Overtime Allowance                                       ₹5,000
    Sub-Total: Labour                                      ₹2,32,500

  E2. Occupancy & Utilities
    Rent                                                    ₹32,000
    Electricity                                             ₹18,000
    Water                                                    ₹3,000
    Internet                                                 ₹2,000
    Sub-Total: Occupancy                                    ₹55,000

  E3. Technology & Software
    Pos Software                                            ₹10,000
    Platform Subscriptions                                   ₹2,000
    Menu Photography Amortized                               ₹1,500
    Sub-Total: Technology                                   ₹13,500

  E4. Sales & Marketing
    Zomato Ads                                              ₹25,000
    Swiggy Ads                                              ₹10,000
    Social Media                                             ₹8,000
    Influencer                                               ₹5,000
    Self Funded Discounts                                   ₹15,000
    Sub-Total: Marketing                                    ₹63,000

  E5. General & Administrative
    Accounting                                               ₹5,000
    Legal Compliance                                         ₹2,000
    Insurance                                                ₹3,000
    Cleaning Supplies                                        ₹4,000
    Pest Control                                             ₹1,500
    Repairs Maintenance                                      ₹3,000
    Gas Lpg                                                  ₹6,000
    Office Supplies                                          ₹1,000
    Miscellaneous                                            ₹3,000
    Sub-Total: General & Admin                              ₹28,500
----------------------------------------------------------------------
  TOTAL OPEX                                               ₹3,92,500

F. EBITDA
----------------------------------------------------------------------
  EBITDA                                                   ₹2,06,434
  EBITDA Margin %                                              22.3%

G. DEPRECIATION & AMORTIZATION
----------------------------------------------------------------------
  Equipment Depreciation                                    ₹15,000
  Brand Amortization                                         ₹2,000
  Total D&A                                                 ₹17,000

H. EBIT
----------------------------------------------------------------------
  EBIT                                                     ₹1,89,434

I. FINANCE COSTS
----------------------------------------------------------------------
  Interest on Loans                                          ₹8,000
  Bank Charges                                               ₹1,500
  Total Finance Costs                                        ₹9,500

J. PROFIT BEFORE TAX (PBT)
----------------------------------------------------------------------
  PBT                                                      ₹1,79,934

K. INCOME TAX
----------------------------------------------------------------------
  Income Tax (26%)                                          ₹46,783

======================================================================
L. PROFIT AFTER TAX (PAT) ★
======================================================================
  PAT                                                      ₹1,33,151
  PAT Margin %                                                 14.4%
======================================================================

M. KEY PERFORMANCE INDICATORS
----------------------------------------------------------------------
  Total Orders                                                 2,200
  Average Order Value                                       ₹582.63
  Food Cost % (of Net Revenue)                                 28.6%
  Labour Cost % (of Net Revenue)                               25.1%
  Platform Commission % (of GMV)                               23.0%
======================================================================
```
