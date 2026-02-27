# Data Sources

## Primary: MongoDB delivery_orders collection

Directly queried from MongoDB database. The P&L script connects to MongoDB and filters orders by date range and restaurant ID in real-time.

### MongoDB Fields Used for P&L

| Field (MongoDB) | Data Type | Description | Example |
|-----------------|-----------|-------------|---------|
| order_date | DateTime | Order placement date | 2024-01-15T10:30:00 |
| total_inr | Float | Gross order value | 450.00 |
| promo_discount_inr | Float | Promotional discounts applied | 50.00 |
| item_discount_inr | Float | Item-level discounts | 25.00 |
| tax_gst_inr | Float | GST tax amount | 38.00 |
| delivery_fee_inr | Float | Delivery charges | 30.00 |
| packaging_charge_inr | Float | Packaging costs | 10.00 |
| order_channel | String | Sales channel | Zomato, Swiggy, WalkIn |
| restaurant_id | String | Restaurant identifier | default |

### Naming Convention

MongoDB fields use **snake_case** but are internally converted to **PascalCase_With_Underscores** for P&L calculations.

### Data Quality

- Dates are in YYYY-MM-DD format
- All numeric fields are non-negative
- Order_Channel has only 3 values: Zomato, Swiggy, WalkIn
- Missing values are handled by backend filtering

## Future Data Sources (Planned)

### daily_aggregates.xlsx
Pre-aggregated daily metrics for trend analysis and dashboards.
- Columns: Date, Total_Orders, Total_Revenue, Avg_Order_Value, Cancellation_Rate, etc.
- Use case: Daily/weekly summary reports

### order_line_items.xlsx
Line-item level order details for actual COGS calculation.
- Columns: Order_ID, Item_Name, Quantity, Unit_Cost_INR, COGS_INR
- Use case: Replace estimated COGS with actual values

### raw_material_inventory.xlsx
Material costs and stock levels.
- Columns: Material_ID, Material_Name, Unit_Cost_INR, Stock_Quantity
- Use case: Cost tracking and inventory reports

### stock_movement_log.xlsx
Inventory movement tracking.
- Columns: Date, Material_ID, Movement_Type, Quantity
- Use case: COGS reconciliation

## Notes

- All currency values are in INR (Indian Rupees)
- COGS is currently estimated at 35% of net revenue
- Actual COGS will be calculated when order_line_items data is integrated
