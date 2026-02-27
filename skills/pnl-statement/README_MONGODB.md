# P&L Skill - MongoDB Integration

The P&L skill now connects **directly to MongoDB** instead of reading from CSV files.

## Architecture

```
User Request → P&L Skill → MongoDB (delivery_orders collection) → Generate Report
```

## Database Setup

### 1. Collection: `delivery_orders`

Stores order data from external delivery platforms (Zomato, Swiggy) and walk-in orders.

**Schema:**
```javascript
{
  _id: ObjectId,
  order_date: DateTime,
  total_inr: Float,
  promo_discount_inr: Float,
  item_discount_inr: Float,
  tax_gst_inr: Float,
  delivery_fee_inr: Float,
  packaging_charge_inr: Float,
  order_channel: String,  // "Zomato", "Swiggy", or "WalkIn"
  restaurant_id: String,
  created_at: DateTime,
  updated_at: DateTime
}
```

### 2. Environment Variables

The P&L script uses these environment variables:

```bash
MONGODB_URI=mongodb://localhost:27017
DB_NAME=ahar_pos
RESTAURANT_ID=default
```

## Usage

### Generate P&L Report

```bash
# Text format (default) - displays in chat
python scripts/generate_pnl.py 2024-01-01 2024-01-31

# Excel format - generates downloadable file
python scripts/generate_pnl.py 2024-01-01 2024-01-31 excel

# With custom restaurant ID
python scripts/generate_pnl.py 2024-01-01 2024-01-31 text my_restaurant_id
```

### Import Data from CSV

If you have existing CSV files with delivery order data:

```bash
cd backend

# Import orders for default restaurant
python scripts/import_delivery_orders.py /path/to/orders.csv

# Import orders for specific restaurant
python scripts/import_delivery_orders.py /path/to/orders.csv my_restaurant_id
```

**CSV Format Required:**
```csv
Order_Date,Total_INR,Promo_Discount_INR,Item_Discount_INR,Tax_GST_INR,Delivery_Fee_INR,Packaging_Charge_INR,Order_Channel
2024-01-15,450.00,50.00,25.00,38.00,30.00,10.00,Zomato
2024-01-16,320.00,0.00,15.00,25.00,0.00,5.00,WalkIn
```

## Dependencies

Install required Python packages:

```bash
cd skills/pnl-statement
pip install -r requirements.txt
```

Required packages:
- `pymongo` - MongoDB driver
- `pandas` - Data processing
- `openpyxl` - Excel file generation

## New Backend Components

### Models
- `backend/app/models/delivery_order.py` - Pydantic models for delivery orders

### Repositories
- `backend/app/repositories/delivery_order_repository.py` - Database operations

### Scripts
- `backend/scripts/import_delivery_orders.py` - Import CSV data to MongoDB

## Migration from CSV

If you previously used CSV files:

1. **Import existing CSV data** to MongoDB using `import_delivery_orders.py`
2. **Update any automation** that was creating CSV files to instead write directly to MongoDB using the `DeliveryOrderRepository`
3. The P&L skill will automatically query MongoDB when generating reports

## Benefits

✅ **Real-time data** - No need to export CSV files
✅ **Scalability** - MongoDB handles large datasets efficiently
✅ **Query flexibility** - Filter by date range, channel, restaurant
✅ **Data integrity** - Schema validation via Pydantic models
✅ **Async support** - Backend can use async Motor driver

## Troubleshooting

**"Failed to connect to MongoDB"**
- Verify MongoDB is running: `docker compose ps`
- Check `MONGODB_URI` environment variable
- Ensure network connectivity to MongoDB

**"No orders found for restaurant"**
- Verify data exists: `db.delivery_orders.find({restaurant_id: "default"})`
- Check date format is YYYY-MM-DD
- Confirm restaurant_id matches imported data

**"Missing required columns"**
- Ensure all required fields exist in MongoDB documents
- Run data import script again if schema is incorrect
