# Data Sources

## Primary: orders.csv

Pre-filtered by backend before upload to container. Contains only orders within the requested date range.

### Columns Used for P&L

| Column | Data Type | Description | Example |
|--------|-----------|-------------|---------|
| Order_Date | Date | Order placement date | 2024-01-15 |
| Total_INR | Decimal | Gross order value | 450.00 |
| Promo_Discount_INR | Decimal | Promotional discounts applied | 50.00 |
| Item_Discount_INR | Decimal | Item-level discounts | 25.00 |
| Tax_GST_INR | Decimal | GST tax amount | 38.00 |
| Delivery_Fee_INR | Decimal | Delivery charges | 30.00 |
| Packaging_Charge_INR | Decimal | Packaging costs | 10.00 |
| Order_Channel | String | Sales channel | Zomato, Swiggy, WalkIn |

### Naming Convention

All columns use **PascalCase_With_Underscores**

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
