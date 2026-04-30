# Item-Level vs Restaurant-Level Forecasting

Complete guide on forecasting granularity and item-level predictions.

---

## Quick Answer

### Current Model: **Restaurant-Level Total**

The saved model predicts **total daily units** (all items combined), NOT individual item forecasts.

```python
# What the model predicts
prediction = {
    "date": "2026-03-15",
    "total_units": 171  # Sum of ALL menu items
}
```

### For Item-Level: **Use Hierarchical Allocation**

We've created a script that:
1. Uses the restaurant model to predict total
2. Allocates to items based on historical mix

```bash
python scripts/predict_item_level.py --days 7
```

---

## Detailed Comparison

### Option 1: Restaurant-Level (Current Model) ✅

**What it predicts:**
- Single daily total (e.g., 171 units)
- Aggregates ALL menu items

**Training data:**
```
Date       | Total Units
2025-10-01 | 156
2025-10-02 | 145
2025-10-03 | 399  (high discount day)
```

**Best for:**
- Overall inventory planning
- Total ingredient procurement
- Staff scheduling
- Revenue forecasting

**Example:**
```
Tomorrow's forecast: 171 units
→ Need ingredients for ~171 portions total
→ Schedule staff for ~171 order volume
```

---

### Option 2: Item-Level with Hierarchical Allocation (New) ✅

**What it predicts:**
- Total forecast (171 units)
- Allocated to each item based on historical mix

**Example output:**

```
Date: 2026-03-10 (Tuesday) - Total: 101 units

Item-Level Breakdown:
  Katsu Chilli Chicken Sandwich        10 units (10.1%)
  The Bombay Broski Sandwich            8 units ( 7.7%)
  Katsu Chilli Paneer Sandwich          7 units ( 7.0%)
  Grilled Chicken & Bacon Sandwich      7 units ( 6.7%)
  Truffle Mushroom Melt Sandwich        5 units ( 4.7%)
  Peri Peri Fries                       4 units ( 3.7%)
  Lamb Birria Sandwich                  4 units ( 3.5%)
  Other items (48 items)               56 units (56.0%)
```

**Best for:**
- Individual item prep planning
- Per-item ingredient requirements
- Menu optimization
- Item-specific inventory

**Usage:**
```bash
# Predict top 10 items for next 7 days
python scripts/predict_item_level.py --days 7 --top-n 10

# Save to CSV for inventory system
python scripts/predict_item_level.py --days 30 --output march_items.csv
```

---

## Your Menu Insights (Last 30 Days)

### Top 10 Items by Volume

| Rank | Item | % of Sales | Units |
|------|------|------------|-------|
| 1 | Katsu Chilli Chicken Sandwich | 10.1% | 459 |
| 2 | The Bombay Broski Sandwich | 7.7% | 350 |
| 3 | Katsu Chilli Paneer Sandwich | 7.0% | 321 |
| 4 | Grilled Chicken & Bacon (OG Pork) | 6.7% | 304 |
| 5 | Truffle Mushroom Melt Sandwich | 4.7% | 216 |
| 6 | Peri Peri Fries | 3.7% | 168 |
| 7 | Lamb Birria Sandwich | 3.5% | 159 |
| 8 | Pesto Grilled Chicken Parmigiana | 3.5% | 158 |
| 9 | Truffle Parmesan Fries | 3.1% | 141 |
| 10 | Grilled Chicken & Bacon (Chicken) | 3.0% | 137 |

**Key stats:**
- **Total items:** 58 on menu
- **Top 10 items:** 52.9% of sales
- **Top 20 items:** 76.2% of sales

**Recommendation:** Focus inventory precision on top 20 items (76% of volume)

---

## When to Use Each Approach

### Use Restaurant-Level Total When:

✅ **Planning total inventory**
- "How much chicken do I need total?"
- "How many orders will we have?"

✅ **Staffing decisions**
- "How many cooks/servers do I need?"
- "What will be the order volume?"

✅ **Revenue forecasting**
- "What's the expected revenue?"
- "How many deliveries?"

### Use Item-Level Allocation When:

✅ **Prep planning**
- "How many Biryanis to prep?"
- "How much Paneer to defrost?"

✅ **Individual ingredient planning**
- "How many chicken breasts?"
- "How many burger buns?"

✅ **Menu optimization**
- "Which items sell better on weekends?"
- "Should I promote item X?"

---

## How the Hierarchical Allocation Works

### Step 1: Calculate Historical Item Mix

```python
# From last 30 days of sales
Katsu Chilli Chicken: 10.1% of total sales
Bombay Broski: 7.7% of total sales
# ... etc
```

### Step 2: Predict Total Demand

```python
# Using restaurant-level model
tomorrow_total = 171 units
```

### Step 3: Allocate to Items

```python
# Multiply total by each item's percentage
Katsu Chilli Chicken = 171 × 10.1% = 17 units
Bombay Broski = 171 × 7.7% = 13 units
# ... etc
```

### Advantages

✅ **Always sums to total** - No over/under estimation
✅ **Works with current model** - No retraining needed
✅ **Handles new items** - Based on recent mix
✅ **Simple and interpretable** - Easy to understand

### Limitations

⚠️ **Assumes static mix** - Doesn't capture day-of-week item variations
⚠️ **No item-specific trends** - Can't predict if item is gaining/losing popularity
⚠️ **Based on recent history** - Uses last 30 days by default

---

## Advanced: Separate Models Per Item

If you need **item-specific trend forecasting**, you can train separate models:

### Requirements

- **Minimum 60-90 days of data per item**
- Items must have regular sales (not sporadic)
- Works best for top 10-20 items

### Implementation

```python
# Train one model per top item
for item in ['Katsu Chilli Chicken', 'Bombay Broski', ...]:
    # Filter data for this item
    item_data = df[df['Item Name'] == item]
    daily_sales = item_data.groupby('Date')['Qty'].sum()

    # Train separate model
    model = train_xgboost(daily_sales, features)
    save_model(model, version=f'v1.0_{item}')
```

### When to Consider This

- Have 6+ months of data per item
- Top items have distinct patterns (e.g., Biryani spikes on weekends)
- Need precise item-level forecasts
- Have resources to maintain multiple models

**Trade-off:** More accurate per item, but 10-20x more models to maintain

---

## Practical Example: Weekly Prep Planning

### Scenario: Plan prep for next week

```bash
# Get item-level forecast
python scripts/predict_item_level.py --days 7 --output week_forecast.csv
```

### Output in CSV:

```csv
date,day_of_week,item_name,predicted_qty,item_percentage
2026-03-10,Tuesday,Katsu Chilli Chicken Sandwich,10,10.06
2026-03-10,Tuesday,The Bombay Broski Sandwich,8,7.67
...
2026-03-16,Monday,Katsu Chilli Chicken Sandwich,13,10.06
```

### Use in Prep Sheet:

```
WEEKLY PREP PLAN (Mar 10-16)

Katsu Chilli Chicken Sandwich:  91 units  (13/day avg)
→ Prep: 100 portions (add 10% buffer)
→ Chicken: 100 × 200g = 20kg
→ Buns: 100 units

The Bombay Broski Sandwich:     69 units  (10/day avg)
→ Prep: 75 portions
→ Ingredients: ...

Weekend peak items:
→ Saturday/Sunday expect +40% on sandwiches
```

---

## Comparison Table

| Feature | Restaurant-Level | Hierarchical Allocation | Separate Models |
|---------|-----------------|------------------------|-----------------|
| **Granularity** | Total only | Item breakdown | Item-specific |
| **Data needed** | 60-90 days | 60-90 days + 30 days mix | 60-90 days per item |
| **Models to maintain** | 1 | 1 | 10-50+ |
| **Accuracy** | High for total | Good for items | Best for items |
| **Setup time** | ✅ Done | ✅ Done | ❌ 1-2 weeks |
| **Best for** | Total planning | Prep planning | Item trends |
| **Maintenance** | Low | Low | High |

---

## Current Implementation Status

### ✅ Available Now

1. **Restaurant-level model** (v1.0)
   - Location: `/models/v1.0/`
   - Performance: 21.91% MAPE
   - Features: 50 (discounts, weather, calendar)

2. **Item-level allocation script**
   - Script: `scripts/predict_item_level.py`
   - Method: Hierarchical allocation
   - Customizable: Top N items, lookback period

### 📝 Example Commands

```bash
# Restaurant-level (total only)
python scripts/predict_with_saved_model.py --days 7

# Item-level (with allocation)
python scripts/predict_item_level.py --days 7 --top-n 20

# Export to CSV for inventory system
python scripts/predict_item_level.py \
  --days 30 \
  --top-n 20 \
  --output march_items.csv
```

---

## Recommendations

### For Immediate Use

**Use hierarchical allocation (Option 2):**
- ✅ Works with current model
- ✅ Provides item-level breakdown
- ✅ Accurate enough for prep planning
- ✅ Easy to maintain

```bash
python scripts/predict_item_level.py --days 7 --top-n 20
```

### For Future Enhancement

**After 6+ months of data:**
- Consider separate models for top 5-10 items
- Track item-specific seasonality
- Optimize per-item accuracy

---

## Summary

**Current model predicts:** Restaurant-level total (e.g., 171 units/day)

**For item-level needs:** Use hierarchical allocation script
- Takes total forecast
- Allocates to items based on historical mix
- Works with existing model
- Ready to use now

**Command:**
```bash
python scripts/predict_item_level.py --days 7
```

**Output:** Daily forecast broken down by top items

---

**Last Updated:** 2026-03-10
**Status:** ✅ Both restaurant-level and item-level forecasting available
