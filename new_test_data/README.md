# Generate 100 Days of Realistic Test Data for ML Training

This directory contains scripts to generate, validate, and import 100 days of synthetic restaurant data for ML model training.

## 📋 Overview

**Date Range:** November 26, 2025 → March 4, 2026 (100 days)

**Expected Output:**
- ~8,500-9,000 orders
- ~15,000 order line items
- 8-10 promotional events
- 150-200 purchase orders
- 100 days of wastage logs
- 6-8 stock-out events

**Realistic Patterns:**
- Bimodal time distribution (lunch at 14:00, dinner at 19-20:00)
- Weekend pattern (-15% volume, +6% AOV)
- Holiday spikes (+50% volume)
- Promotion-driven demand increases
- Realistic wastage and stock-out scenarios

## 🚀 Quick Start

### Prerequisites

```bash
# Ensure Python dependencies are installed
cd backend
pip install -r requirements.txt

# Ensure MongoDB is running
docker compose up -d mongodb
# OR
mongod --dbpath /path/to/data
```

### Step 1: Generate Data

```bash
cd new_test_data
python generate_realistic_data.py
```

**Expected Output:**
- `orders.csv` (~8,500 orders)
- `order_line_items.csv` (~15,000 items)
- `promotions.csv` (8-10 promotions)
- `purchase_history.csv` (150-200 purchases)
- `wastage_log.csv` (100 days of wastage)
- `stockout_log.csv` (6-8 stock-outs)

**Time:** ~2-5 minutes

### Step 2: Validate Data

```bash
python validate_data.py
```

**Expected Output:**
```
✅ ALL VALIDATION CHECKS PASSED!
```

If validation fails, review the error messages and regenerate data if needed.

**Time:** ~30 seconds

### Step 3: Import to MongoDB

```bash
python import_to_mongodb.py
```

**Expected Output:**
```
✓ Imported X,XXX orders
✓ Imported X promotions
✓ Imported X purchase orders
✓ Imported X wastage records
✓ Imported X stock-out events
🎉 IMPORT COMPLETE!
```

**Time:** ~1-2 minutes

### Step 4: Verify ML Readiness

```bash
cd ../backend
python test_ml_data_readiness.py
```

**Expected Output:**
```
✅ ALL TESTS PASSED - DATA IS ML-READY!
```

Plus visualization plots saved to `backend/ml_readiness_plots/`:
- `daily_orders.png` - Daily volume over 100 days
- `hourly_distribution.png` - Bimodal time pattern
- `promotion_impact.png` - Promotion effect visualization
- `aov_distribution.png` - Order value distribution

**Time:** ~30 seconds

### Step 5: Test Existing Features

```bash
# Start backend server
cd backend
docker compose up -d

# Test API endpoints
curl http://localhost:8000/api/v1/orders?page=1&limit=10
curl http://localhost:8000/api/v1/inventory
curl http://localhost:8000/api/v1/forecast/ingredient/RM001?days=7
```

**Expected:** All endpoints return valid data, no errors

## 📊 Data Schema

### Orders
- `order_id`: Unique identifier (ORD00001, ORD00002, ...)
- `order_number`: Date-based number (2025-11-26-001)
- `order_date`: Date of order (YYYY-MM-DD)
- `order_time`: Time of order (HH:MM:SS)
- `order_hour`: Hour of order (11-22)
- `order_weekday`: Day of week (0=Monday, 6=Sunday)
- `is_weekend`: Boolean (Saturday/Sunday)
- `is_holiday`: Boolean
- `holiday_name`: Name of holiday (if applicable)
- `order_type`: TAKEAWAY, DINE_IN, or DELIVERY
- `table_id`: Table identifier (for DINE_IN)
- `staff_id`: Staff identifier
- `status`: COMPLETED or CANCELLED
- `total_amount`: Total in paise (integer)
- `created_at`: ISO 8601 timestamp

### Order Line Items
- `order_item_id`: Unique identifier (ITEM00001, ...)
- `order_id`: Foreign key to orders
- `menu_item_id`: Foreign key to menu items
- `menu_item_name`: Item name snapshot
- `quantity`: Quantity ordered (integer)
- `price_snapshot`: Price at time of order (paise)
- `notes`: Special instructions
- `item_status`: READY or PENDING
- `created_at`: ISO 8601 timestamp

### Promotions
- `promo_id`: Unique identifier (PROMO001, ...)
- `start_date`: Promotion start date
- `end_date`: Promotion end date
- `promo_type`: WEEKEND_SPECIAL, HOLIDAY_SPECIAL, MIDWEEK_COMBO
- `menu_item_ids`: Comma-separated menu item IDs (or 'ALL')
- `discount_pct`: Discount percentage (integer)
- `description`: Human-readable description
- `demand_boost`: Expected demand multiplier (float)

### Purchase History
- `purchase_id`: Unique identifier (PUR00001, ...)
- `purchase_date`: Date of purchase
- `material_id`: Raw material identifier
- `quantity`: Quantity purchased
- `unit_cost_inr`: Unit cost in paise
- `supplier_id`: Supplier identifier
- `total_cost`: Total cost in paise

### Wastage Log
- `date`: Date of wastage
- `material_id`: Raw material identifier
- `quantity_wasted`: Quantity wasted (decimal)
- `reason`: expired, over_prep, spoilage, quality_issue
- `cost_inr`: Cost of wastage in paise

### Stock-out Log
- `date`: Date of stock-out
- `time`: Time of stock-out
- `material_id`: Raw material that stocked out
- `orders_affected`: Number of orders affected
- `menu_items_affected`: Menu items affected
- `estimated_revenue_loss`: Lost revenue in paise

## 🎯 Realistic Patterns

The generated data contains these learnable patterns:

### 1. Time Series Patterns
- **Weekly seasonality:** Weekend dip (-15% volume)
- **Daily seasonality:** Bimodal peaks (14:00 lunch, 19-20:00 dinner)
- **Holiday spikes:** +50% orders on holidays
- **Growth trend:** Gradual +10% increase from start to end

### 2. Causal Relationships
- **Promotions → Demand:** +30-40% for promoted items
- **Weekends → AOV:** Higher average order value (+6%)
- **Holidays → Volume:** Significant volume increase
- **Rain → Orders:** -15% overall orders (synthetic)

### 3. Stochastic Noise
- Random daily variation (±20% around mean)
- Unpredictable promotions (not on fixed schedule)
- Random wastage events
- Occasional supplier delays

### 4. Feature Interactions
- Weekend + Promotion → Extra boost
- Holiday + Rain → Muted spike
- High demand → Stock-out risk → Wastage reduction

## 🔧 Customization

### Adjust Data Volume

Edit `generate_realistic_data.py`:

```python
# Change these constants
MEAN_DAILY_ORDERS = 87  # Average orders per day
STD_DAILY_ORDERS = 15   # Standard deviation
MIN_DAILY_ORDERS = 60   # Minimum orders
MAX_DAILY_ORDERS = 120  # Maximum orders
```

### Adjust Patterns

```python
# Time distribution
HOURLY_DISTRIBUTION = {
    14: 0.14,  # Lunch peak (14%)
    19: 0.16,  # Dinner peak (16%)
    20: 0.14,  # Dinner peak (14%)
    # ... adjust as needed
}

# Weekend modifier
WEEKEND_VOLUME_MODIFIER = 0.85  # -15% volume

# Holiday modifier
HOLIDAY_VOLUME_MODIFIER = 1.50  # +50% orders
```

### Add More Holidays

```python
HOLIDAYS = [
    (datetime(2025, 12, 25), "Christmas"),
    (datetime(2026, 1, 1), "New Year"),
    (datetime(2026, 1, 14), "Sankranti"),
    (datetime(2026, 1, 26), "Republic Day"),
    # Add more here
]
```

### Adjust Wastage

```python
BASE_WASTAGE_RATE = 0.065  # 6.5% average
MONDAY_WASTAGE_RATE = 0.11  # Higher on Mondays
PERISHABLE_WASTAGE_BONUS = 0.03  # Extra for perishables
```

## 🧪 Validation Checks

The validation script checks:

### Schema Compliance
- All required fields present
- Data types correct (integers for paise, datetime for dates)
- Foreign keys valid
- No orphaned records

### Business Logic
- Order amounts = sum(item prices × quantities)
- Stock movements balance
- Promotion dates valid
- No negative quantities

### Pattern Validation
- Daily order distribution (60-120 orders/day)
- Hourly distribution (bimodal peaks)
- Weekend/weekday ratios
- Holiday spikes detectable
- Promotion impact visible
- AOV within expected range (₹600-1200)

### Data Quality
- No duplicate IDs
- Date range correct (100 days)
- Sufficient records in all tables
- Items per order realistic (~1.7)

## 📈 ML Features

The feature engineering service extracts:

### Temporal Features
- hour_of_day, day_of_week, day_of_month
- week_of_year, month, quarter
- is_weekend, is_holiday
- days_until_next_holiday
- season (winter/spring/summer/monsoon)

### Lag Features
- demand_lag_1, demand_lag_7, demand_lag_30
- demand_7day_rolling_mean, demand_7day_rolling_std
- demand_30day_rolling_mean

### Promotion Features
- is_promotion_active
- promotion_discount_pct
- days_since_last_promotion
- promotion_type

### External Features
- temperature_avg (synthetic)
- is_rainy (synthetic)
- weather_condition

### Inventory Features
- days_of_stock_remaining
- stockout_risk_score
- wastage_rate_7day_avg

## 🐛 Troubleshooting

### "File not found" errors
Ensure you're in the `new_test_data/` directory when running scripts.

### Validation failures
Check error messages for specific issues. Common causes:
- Date range incorrect
- Missing required fields
- Foreign key mismatches

Regenerate data if needed.

### Import errors
Ensure MongoDB is running:
```bash
docker compose up -d mongodb
# OR
mongod --dbpath /path/to/data
```

### ML readiness test fails
Check:
- Data was imported successfully
- Backend dependencies installed
- Database connection working

### Low pattern detection
If promotion or weekend effects aren't detectable:
1. Increase effect sizes in constants
2. Regenerate data
3. Re-run validation

## 📚 Next Steps

After data generation:

1. **Train ML Models**
   - Prophet for time series forecasting
   - SARIMA for seasonal patterns
   - XGBoost for complex interactions
   - Ensemble methods

2. **Test Forecasting APIs**
   - `/api/v1/forecast/demand`
   - `/api/v1/forecast/ingredient/{material_id}`
   - `/api/v1/insights/generate`

3. **Compare with Real Data**
   - When real restaurant data arrives
   - Compare distributions
   - Adjust synthetic data generation parameters
   - Retrain models

4. **Build Data Ingestion Pipeline**
   - CSV/Excel upload
   - Schema mapping
   - Data validation
   - Incremental imports

## 📞 Support

If you encounter issues:

1. Check this README
2. Review error messages carefully
3. Check validation output
4. Review generated plots
5. Check MongoDB collections directly

## ✅ Success Criteria Checklist

- [ ] 100 days of data generated (Nov 26, 2025 - Mar 4, 2026)
- [ ] 8,500-9,000 total orders (~85 orders/day average)
- [ ] Bimodal time distribution visible (14:00 and 19-20:00 peaks)
- [ ] Weekend pattern detectable (-15% volume, +6% AOV)
- [ ] 8-10 promotions with correlated demand spikes
- [ ] Purchase history matches consumption (±5% variance)
- [ ] Wastage averages 5-8% of consumption
- [ ] 6-8 stock-out events recorded
- [ ] All existing API endpoints functional
- [ ] Prophet forecasting produces predictions (no errors)
- [ ] Data validation passes all checks
- [ ] Feature engineering extracts all planned features
- [ ] ML readiness test confirms patterns exist

## 📝 License

Internal use only - Ahar.AI project
