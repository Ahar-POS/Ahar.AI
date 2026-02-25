# Demand Forecasting Accuracy Guide

## Overview

This guide explains how to measure and improve the accuracy of your demand forecasting system.

## Current Prediction Accuracy: Unknown ⚠️

**Important:** The system currently calculates "confidence scores" based on prediction interval width, but this is **NOT the same as accuracy**.

To measure actual accuracy, you need to compare predictions against what actually happened (backtesting).

---

## Quick Start: Testing Accuracy

### Method 1: Via API (Recommended for production monitoring)

```bash
# Test menu item forecasting accuracy
curl -X POST "http://localhost:8000/api/v1/forecast/validate/backtest/menu-items?lookback_days=60&test_days=7"

# Test ingredient forecasting accuracy
curl -X POST "http://localhost:8000/api/v1/forecast/validate/validate/ingredients?test_days=7"

# Get metrics explanation
curl "http://localhost:8000/api/v1/forecast/validate/metrics/explain"

# Get industry benchmarks
curl "http://localhost:8000/api/v1/forecast/validate/benchmark"
```

### Method 2: Via Python Script (Recommended for analysis)

```bash
cd backend
docker compose exec backend python test_forecast_accuracy.py
```

---

## Understanding Accuracy Metrics

### 1. MAE (Mean Absolute Error) - "How far off are we on average?"

**Formula:** `mean(|actual - predicted|)`

**Example:**
- Actual sales: [10, 15, 12, 8, 14]
- Predictions: [12, 14, 10, 9, 15]
- Errors: [2, 1, 2, 1, 1]
- **MAE = 1.4 units**

**Interpretation:** On average, predictions are off by 1.4 units

**Good value:** < 10% of average demand
- If average sales = 50 units/day → MAE < 5 is good

**When to use:** Easy to interpret, same units as your data

---

### 2. RMSE (Root Mean Squared Error) - "How bad are the worst errors?"

**Formula:** `sqrt(mean((actual - predicted)²))`

**Example:**
- Same data as above
- Squared errors: [4, 1, 4, 1, 1]
- **RMSE = 1.7 units**

**Interpretation:** Penalizes large errors more than MAE

**Good value:** Close to MAE indicates consistent errors
- If RMSE >> MAE → You have some very bad predictions

**When to use:** When large errors are particularly costly (stockouts)

---

### 3. MAPE (Mean Absolute Percentage Error) - "What % are we off?"

**Formula:** `mean(|actual - predicted| / actual) × 100%`

**Example:**
- Actual: 50, Predicted: 45 → Error: 10%
- Actual: 100, Predicted: 85 → Error: 15%
- **MAPE = 12.5%**

**Interpretation:** Predictions are 12.5% off on average

**Industry benchmarks:**
- **< 15%** = Excellent ✅
- **15-25%** = Good ✓
- **25-40%** = Acceptable ⚠️
- **> 40%** = Poor ❌

**When to use:** Comparing across different items (chicken vs rice)

---

### 4. Forecast Bias - "Do we consistently over or under predict?"

**Formula:** `mean(predicted - actual)`

**Example:**
- Bias = +3 → Over-forecasting by 3 units
- Bias = -3 → Under-forecasting by 3 units
- Bias = 0 → Perfectly balanced

**Business Impact:**
- **Positive bias** (over-forecasting):
  - Consequence: Food waste, tied-up capital, spoilage
  - Cost: Direct waste + storage costs

- **Negative bias** (under-forecasting):
  - Consequence: Stockouts, lost sales, unhappy customers
  - Cost: Lost revenue + customer satisfaction

**Good value:** Close to 0 (unbiased)

---

### 5. Hit Rate - "How often are we 'close enough'?"

**Formula:** `% of predictions within 20% of actual`

**Example:**
- 7 predictions, 5 are within 20% of actual
- **Hit Rate = 71%**

**Interpretation:** 71% of the time, predictions are "good enough"

**Good value:** > 70% for reliable inventory planning

**When to use:** Understanding prediction reliability

---

## Expected Accuracy for Restaurant Forecasting

### Menu Items (Daily)
```
Horizon        Typical MAPE    Why
1-day ahead    15-25%          High daily variability
7-days ahead   20-30%          Longer horizon = more uncertainty
30-days ahead  30-50%          Many unknown factors
```

### Ingredients (Weekly Aggregation)
```
Excellent:  < 10% MAPE
Good:       10-20% MAPE
Acceptable: 20-30% MAPE
Poor:       > 30% MAPE
```

**Why weekly is better:**
- Daily sales: [5, 8, 3, 12, 7, 6, 9] → High variance
- Weekly total: 50 → Smoother, more predictable

### Factors Affecting Accuracy

**Good accuracy (< 15% MAPE):**
- ✓ 90+ days of consistent historical data
- ✓ Clear weekly patterns (weekend vs weekday)
- ✓ Stable menu (no major changes)
- ✓ Predictable customer base

**Poor accuracy (> 40% MAPE):**
- ✗ < 30 days of historical data
- ✗ Irregular sales patterns
- ✗ Frequent menu changes
- ✗ Highly seasonal items (e.g., ice cream)
- ✗ New restaurant (no history)

---

## How Backtesting Works

### Walk-Forward Validation

```
Timeline:
|------- 60 days training -------|--- 7 days test ---|
                                  ↑                    ↑
                                Train                Test
                                cutoff              period

Step 1: Use orders from 67 days ago → 7 days ago for training
Step 2: Predict next 7 days (today → 6 days from now)
Step 3: Compare predictions to actual sales for those 7 days
Step 4: Calculate MAE, RMSE, MAPE, etc.
```

**Why this is realistic:**
- Simulates real forecasting (predicting future using only past data)
- Tests on data the model has never seen
- Prevents "cheating" (data leakage)

---

## Running Your First Accuracy Test

### Step 1: Check if you have enough data

```bash
# Check how many days of order history you have
docker compose exec -T mongodb mongosh --quiet ahar_pos --eval "
  db.orders.aggregate([
    {
      \$group: {
        _id: null,
        min_date: {\$min: '\$order_date'},
        max_date: {\$max: '\$order_date'},
        total_orders: {\$sum: 1}
      }
    }
  ]).pretty()
"
```

**Minimum requirements:**
- At least 30 days of order history
- At least 100 total orders
- Orders on most days (not too sparse)

### Step 2: Run backtest via Python script

```bash
cd backend
docker compose exec backend python test_forecast_accuracy.py
```

**Expected output:**
```
╔═══════════════════════════════════════════════════════════════╗
║          DEMAND FORECASTING ACCURACY REPORT                   ║
╚═══════════════════════════════════════════════════════════════╝

AGGREGATE METRICS (across all menu items):

  MAE (Mean Absolute Error):          2.34 units
  MAPE (Mean Absolute % Error):       18.5%
  Forecast Bias:                       +0.8 units
  Hit Rate (within 20%):               68.2%

INTERPRETATION:
  ✓ GOOD: MAPE 15-25% - Acceptable accuracy for inventory planning
  ✅ Minimal bias - Balanced forecasts
```

### Step 3: Run backtest via API

```bash
# Basic test
curl -X POST "http://localhost:8000/api/v1/forecast/validate/backtest/menu-items"

# Custom parameters
curl -X POST "http://localhost:8000/api/v1/forecast/validate/backtest/menu-items?lookback_days=90&test_days=14"

# Test specific items only
curl -X POST "http://localhost:8000/api/v1/forecast/validate/backtest/menu-items?menu_item_ids=MENU001&menu_item_ids=MENU002"
```

### Step 4: Interpret results

**Good results:**
```json
{
  "aggregate": {
    "mape": 18.5,      // ✓ Good (15-25%)
    "bias": 0.8,       // ✓ Minimal bias
    "hit_rate": 68.2   // ⚠ Could be better (aim for >70%)
  }
}
```

**Poor results:**
```json
{
  "aggregate": {
    "mape": 45.3,      // ❌ Poor (>40%)
    "bias": -8.2,      // ❌ Under-forecasting (stockouts)
    "hit_rate": 42.1   // ❌ Low reliability
  }
}
```

---

## Improving Accuracy

### If MAPE is high (> 30%)

**Problem:** Predictions are way off

**Solutions:**
1. **Get more data:**
   - Minimum 60 days, ideally 90+ days
   - Ensure consistent data collection

2. **Check for outliers:**
   ```python
   # Remove special events that distort patterns
   # E.g., New Year's Eve with 10x normal sales
   ```

3. **Improve Prophet parameters:**
   - Increase `changepoint_prior_scale` for more flexibility
   - Add custom seasonality for your business
   - Add regressors for known events (holidays)

4. **Use AI enhancement:**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/forecast/generate-all?enhance_with_ai=true"
   ```

### If Bias is high (|bias| > 3)

**Problem:** Consistently over or under forecasting

**Solutions:**

**Over-forecasting (positive bias):**
- Reduce safety buffer in inventory agent
- Check if Prophet is using outdated high-sales data
- Consider post-processing adjustment: `prediction × 0.9`

**Under-forecasting (negative bias):**
- Increase safety buffer (currently 20%)
- Check for trend (growing business)
- Consider post-processing adjustment: `prediction × 1.1`

### If Hit Rate is low (< 60%)

**Problem:** Predictions are unreliable

**Solutions:**
1. **Increase prediction intervals:**
   - Use `yhat_upper` instead of `yhat` for inventory
   - Add more safety stock

2. **Segment by item type:**
   - Staples (rice, bread) → More predictable
   - Specials (limited time) → Less predictable
   - Use different models/buffers for each

3. **Add external factors:**
   - Weather forecasts
   - Nearby events (concerts, games)
   - Competitor activity

---

## Continuous Monitoring

### Weekly Accuracy Report (Recommended)

Create a scheduled job to monitor ongoing accuracy:

```python
# Add to orchestrator.py
scheduler.add_job(
    _run_weekly_accuracy_report,
    CronTrigger(day_of_week='mon', hour=9, minute=0),
    id='accuracy_weekly',
    name='Weekly Accuracy Report'
)
```

### Accuracy Dashboard Metrics

Track these metrics over time:

1. **7-day rolling MAPE** - Is accuracy improving?
2. **Bias trend** - Are we drifting toward over/under forecasting?
3. **Per-item accuracy** - Which items need attention?
4. **Accuracy by day of week** - Weekends harder to predict?

### Alert Thresholds

Set up alerts when accuracy degrades:

```python
if weekly_mape > 40:
    alert("Forecast accuracy degraded - investigate data quality")

if abs(weekly_bias) > 5:
    alert("Systematic bias detected - review model parameters")

if hit_rate < 50:
    alert("Low prediction reliability - increase safety stock")
```

---

## Comparison with Other Methods

### Prophet (Your Current Method)

**Pros:**
- ✓ Handles missing data and outliers
- ✓ Works with limited data (30+ days)
- ✓ Automatic seasonality detection
- ✓ Provides confidence intervals

**Cons:**
- ✗ Can't predict sudden changes
- ✗ Struggles with very irregular patterns
- ✗ Needs weekly/yearly cycles to work well

**Typical Accuracy:** 15-30% MAPE for restaurant forecasting

### Alternative: Simple Moving Average

```python
forecast = mean(last_7_days)
```

**Typical Accuracy:** 20-40% MAPE (worse than Prophet)

### Alternative: ML Models (LSTM, XGBoost)

**Typical Accuracy:** 10-25% MAPE (better with lots of data)

**Trade-offs:**
- Requires 6+ months of data
- Much more complex
- Harder to interpret
- May not be worth the effort for <50 items

---

## FAQ

### Q: What's a "good" MAPE for restaurant forecasting?

**A:**
- **< 15%** = Excellent (rare for daily restaurant forecasting)
- **15-25%** = Good (achievable with Prophet and good data)
- **25-40%** = Acceptable (common for new restaurants)
- **> 40%** = Poor (needs improvement)

Daily restaurant sales are inherently variable, so 15-25% is realistic and acceptable.

### Q: Should I trust "confidence score" from forecasts?

**A:** No - confidence scores measure uncertainty (interval width), not accuracy. A model can be very confident but very wrong.

Always measure actual accuracy using backtest results.

### Q: How often should I retrain the model?

**A:**
- **Weekly** (current setup) - Recommended
- Updates forecasts with latest data
- Adapts to changing patterns
- Not too frequent (computationally expensive)

### Q: Why are some items harder to predict than others?

**A:**

**Easy to predict:**
- High-volume staples (burgers, rice)
- Consistent demand patterns
- Available year-round

**Hard to predict:**
- Low-volume items (specials)
- Seasonal items (cold drinks in summer)
- New menu items (no history)
- Weekend-only items

**Solution:** Use different accuracy thresholds and safety buffers per category.

### Q: How do I know if AI enhancement is helping?

**A:** Run backtests with and without AI:

```bash
# Without AI
curl -X POST "http://localhost:8000/api/v1/forecast/generate-all?enhance_with_ai=false"
# Run backtest, record MAPE

# With AI
curl -X POST "http://localhost:8000/api/v1/forecast/generate-all?enhance_with_ai=true"
# Run backtest, compare MAPE
```

If MAPE decreases by 3-5%, AI is adding value.

---

## Next Steps

1. ✅ **Run your first backtest** using the Python script
2. ✅ **Review the MAPE** - Is it < 25%?
3. ✅ **Check for bias** - Over or under forecasting?
4. ✅ **Set up weekly monitoring** - Track accuracy over time
5. ✅ **Tune parameters** if MAPE > 30%
6. ✅ **Document your findings** in your accuracy report

---

## Resources

- [Facebook Prophet Documentation](https://facebook.github.io/prophet/)
- [Forecasting: Principles and Practice (free textbook)](https://otexts.com/fpp3/)
- [MAPE vs MAE vs RMSE](https://stats.stackexchange.com/questions/48267)
- [Restaurant demand forecasting best practices](https://www.sciencedirect.com/science/article/pii/S0278431919308254)

---

**Last Updated:** 2026-02-24
**Maintainer:** Claude Code
