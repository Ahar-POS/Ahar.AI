# Quick Start Guide: Generate Test Data for ML Training

## TL;DR - Run These Commands

```bash
# 1. Navigate to test data directory
cd new_test_data

# 2. Generate 100 days of realistic data (~2 minutes)
python generate_realistic_data.py

# 3. Validate the generated data (~30 seconds)
python validate_data.py

# 4. Start MongoDB
cd ..
docker compose up -d mongodb

# 5. Import data to MongoDB (~1 minute)
cd new_test_data
python import_to_mongodb.py

# 6. Run ML readiness tests (~30 seconds)
cd ../backend
python test_ml_data_readiness.py

# 7. View the results
ls ml_readiness_plots/
# - daily_orders.png
# - hourly_distribution.png
# - promotion_impact.png
# - aov_distribution.png
```

## Expected Output

### Step 2: Data Generation
```
================================================================================
DATA GENERATION COMPLETE!
================================================================================

Summary Statistics:
  Total Orders: 9,056
  Average Orders/Day: 91.5
  Total Revenue: ₹2,676,444.44
  Average Order Value: ₹295.54
  Promotions: 21
  Purchase Orders: 273
  Wastage Events: 3,833
  Stock-outs: 6
```

### Step 3: Validation
```
================================================================================
✅ ALL VALIDATION CHECKS PASSED!
================================================================================
```

### Step 5: Import
```
================================================================================
🎉 IMPORT COMPLETE!
================================================================================
✓ orders: 9,056 documents
✓ promotions: 21 documents
✓ purchase_history: 273 documents
✓ wastage_log: 3,833 documents
✓ stockout_log: 6 documents
```

### Step 6: ML Readiness
```
================================================================================
✅ ALL TESTS PASSED - DATA IS ML-READY!
================================================================================

Total Tests: 16
Passed: 16 ✓
Failed: 0 ✗
```

## What Gets Generated

- **orders.csv** - 9,056 orders with realistic patterns
- **order_line_items.csv** - 14,309 order items
- **promotions.csv** - 21 promotional events
- **purchase_history.csv** - 273 purchase orders
- **wastage_log.csv** - 3,833 wastage records
- **stockout_log.csv** - 6 stock-out events

## Key Patterns in the Data

✅ **Bimodal Time Distribution** - Lunch peak at 14:00, dinner peaks at 19-20:00
✅ **Weekend Pattern** - 11% lower volume on weekends
✅ **Holiday Spikes** - 32% higher volume on holidays
✅ **Promotion Effects** - 16% boost during promotional periods
✅ **Growth Trend** - Gradual 10% increase over 100 days
✅ **Realistic Wastage** - 5-8% of consumption
✅ **Stock-outs** - Occasional inventory shortages

## Troubleshooting

### "ModuleNotFoundError: No module named 'motor'"
```bash
cd backend
pip install motor
```

### "MongoDB not running"
```bash
docker compose up -d mongodb
# Wait 5 seconds for MongoDB to start
sleep 5
```

### "Validation failed"
Check error messages and regenerate:
```bash
python generate_realistic_data.py
```

### "Import failed"
Ensure MongoDB is running:
```bash
docker compose ps mongodb
# Should show "healthy" status
```

## Next Steps

1. **Train ML Models** - Data is now ready for Prophet, SARIMA, XGBoost
2. **Test APIs** - Start backend and test forecast endpoints
3. **Customize Patterns** - Edit `generate_realistic_data.py` constants
4. **Add More Data** - Regenerate with different parameters

## Documentation

- **Full Details:** See `new_test_data/README.md`
- **Implementation Summary:** See `IMPLEMENTATION_SUMMARY.md`
- **Data Schema:** See `new_test_data/README.md#data-schema`

## Success Criteria Checklist

After running all steps, verify:
- [x] 9,000+ orders generated
- [x] All validation checks passed
- [x] Data imported to MongoDB
- [x] All ML readiness tests passed
- [x] Visualization plots generated
- [x] No errors in console output

If all checkboxes are ✅, you're ready to train ML models!
