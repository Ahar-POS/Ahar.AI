# Demand Forecast Data Access Guide

## Overview

Demand predictions are stored in MongoDB and accessible via REST API. This guide shows you how to view, use, and understand forecast data.

---

## 📊 Database Storage

### **Collection: `demand_forecasts`**

**Location:** MongoDB → `ahar_pos` database → `demand_forecasts` collection

**Storage Details:**
- **Records:** One forecast per ingredient (40 ingredients = 40 forecasts)
- **Cache Duration:** 24 hours (TTL)
- **Auto-Refresh:** Weekly on Sundays at midnight
- **Indexes:** `material_id`, `forecast_date`, `generated_at` (with TTL)

---

## 📁 Forecast Data Structure

### **Complete Forecast Document**

```javascript
{
  // Identification
  "_id": ObjectId("..."),
  "material_id": "RM001",                    // Raw material identifier

  // Metadata
  "forecast_date": "2026-02-24T10:03:05Z",   // When forecast was generated
  "horizon_days": 7,                         // Forecast horizon (7 days)
  "model_type": "aggregated_prophet",        // Forecasting method used

  // Predictions
  "predicted_consumption": 13650.0,          // Total units needed for 7 days
  "confidence_lower": 9555.0,                // Lower bound (80% confidence)
  "confidence_upper": 17745.0,               // Upper bound (80% confidence)
  "confidence_score": 0.3,                   // Confidence (0-1, higher = better)

  // Daily Breakdown (7 days)
  "daily_breakdown": [
    {
      "date": "2026-02-25",                  // Day 1
      "predicted": 1950.0,                   // Expected consumption
      "lower": 1365.0,                       // Pessimistic estimate (80% CI)
      "upper": 2535.0                        // Optimistic estimate (80% CI)
    },
    // ... 6 more days
  ],

  // Menu Item Contributors (how we calculated this)
  "menu_item_breakdown": [
    {
      "menu_item_id": "MENU001",
      "menu_item_name": "Smoky Chicken Burger",
      "quantity_per_serving": 140.0,         // Grams per burger
      "total_menu_items_predicted": 35.0,    // Expected burger sales (7 days)
      "total_ingredient_needed": 4900.0,     // = 35 × 140g
      "confidence": 0.3
    },
    // ... other menu items using this ingredient
  ],

  // Caching Info
  "cached_at": ISODate("2026-02-24T10:03:05Z"),
  "expires_at": ISODate("2026-02-25T10:03:05Z"),  // 24 hours later

  // AI Enhancement (if enabled)
  "ai_adjustments": {
    "weather_impact_pct": -15,               // Weather adjustment
    "events_impact_pct": 0,                  // Events adjustment
    "adjusted_forecast": 11602.5,            // After AI adjustments
    "reasoning": "Light rain expected...",
    "weather_summary": "Rain on 3 days",
    "events_summary": "No major events"
  },
  "final_forecast": 11602.5,                 // Use this for inventory
  "enhancement_status": "success"            // AI enhancement result
}
```

---

## 🔍 Accessing Forecasts

### **1. REST API (Recommended)**

#### **Get Single Ingredient Forecast**

```bash
# Get cached forecast (fastest)
curl "http://localhost:8000/api/v1/forecast/ingredient/RM001?use_cache=true"

# Force regenerate (slower, uses API tokens)
curl "http://localhost:8000/api/v1/forecast/ingredient/RM001?use_cache=false&enhance_with_ai=true"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "material_id": "RM001",
    "predicted_consumption": 13650.0,
    "daily_breakdown": [
      {"date": "2026-02-25", "predicted": 1950.0, "lower": 1365.0, "upper": 2535.0},
      // ... 6 more days
    ],
    "menu_item_breakdown": [
      {
        "menu_item_name": "Smoky Chicken Burger",
        "total_ingredient_needed": 4900.0
      }
    ],
    "confidence_score": 0.3,
    "final_forecast": 13650.0
  }
}
```

#### **Get All Forecasts**

```bash
# Generate forecasts for all 40 ingredients
curl -X POST "http://localhost:8000/api/v1/forecast/generate-all?use_cache=false"
```

#### **Get Specific Menu Item Forecast**

```bash
# Get forecast for a menu item (not ingredient)
curl "http://localhost:8000/api/v1/forecast/menu-item/MENU001?horizon_days=7"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "menu_item_id": "MENU001",
    "predictions": [
      {"date": "2026-02-25", "predicted_quantity": 5.0},
      // ... 6 more days
    ],
    "total_predicted": 35.0,
    "model_type": "prophet",
    "confidence_score": 0.3
  }
}
```

---

### **2. MongoDB Queries**

#### **View All Forecasts Summary**

```bash
docker compose exec -T mongodb mongosh --quiet ahar_pos --eval "
  db.demand_forecasts.find({}, {
    material_id: 1,
    predicted_consumption: 1,
    confidence_score: 1,
    expires_at: 1
  }).sort({material_id: 1}).pretty()
"
```

#### **Get Specific Ingredient Forecast**

```bash
docker compose exec -T mongodb mongosh --quiet ahar_pos --eval "
  db.demand_forecasts.findOne({material_id: 'RM001'})
" | python3 -m json.tool
```

#### **Find High-Demand Items (Top 10)**

```bash
docker compose exec -T mongodb mongosh --quiet ahar_pos --eval "
  db.demand_forecasts.find({})
    .sort({predicted_consumption: -1})
    .limit(10)
    .forEach(f => {
      print(f.material_id + ': ' + f.predicted_consumption + ' units');
    })
"
```

#### **Check Cache Freshness**

```bash
docker compose exec -T mongodb mongosh --quiet ahar_pos --eval "
  const now = new Date();
  const valid = db.demand_forecasts.countDocuments({expires_at: {\$gt: now}});
  const expired = db.demand_forecasts.countDocuments({expires_at: {\$lte: now}});
  print('Valid forecasts:', valid);
  print('Expired forecasts:', expired);
"
```

---

### **3. Python (Programmatic Access)**

```python
from app.services.demand_forecaster import get_demand_forecaster
from app.core.database import connect_to_database

# Initialize
await connect_to_database()
forecaster = get_demand_forecaster()

# Get cached forecast
forecast = await forecaster.get_cached_forecast("RM001")
print(f"Predicted: {forecast['predicted_consumption']} units")
print(f"Daily breakdown: {forecast['daily_breakdown']}")

# Get fresh forecast with AI enhancement
forecast = await forecaster.forecast_ingredient_demand("RM001", horizon_days=7)
enhanced = await forecaster.enhance_with_context(forecast)
print(f"AI-adjusted: {enhanced['final_forecast']} units")
```

---

## 📈 Understanding Forecast Values

### **Key Fields Explained**

#### **1. `predicted_consumption` (Total for 7 days)**

**What it means:** Total units of this ingredient you'll need for the next 7 days

**Example:**
```json
{
  "material_id": "RM001",
  "predicted_consumption": 13650.0  // 13,650 grams of chicken
}
```

**How to use:**
- Compare with current stock
- Calculate reorder quantity
- Plan purchasing budget

#### **2. `daily_breakdown` (Day-by-day predictions)**

**What it means:** Daily consumption split

**Example:**
```json
{
  "daily_breakdown": [
    {"date": "2026-02-25", "predicted": 1950.0},  // Monday: 1,950g
    {"date": "2026-02-26", "predicted": 1950.0},  // Tuesday: 1,950g
    // ...
  ]
}
```

**How to use:**
- Identify high-demand days
- Plan daily prep schedules
- Detect weekly patterns

#### **3. `confidence_score` (0-1)**

**What it means:** How confident the model is in this prediction

| Score | Meaning | Interpretation |
|-------|---------|----------------|
| 0.8-1.0 | High | Narrow prediction interval, reliable data |
| 0.5-0.8 | Medium | Some uncertainty, use with caution |
| 0.0-0.5 | Low | Wide interval or fallback forecast |

**Example:**
```json
{
  "confidence_score": 0.3,  // Low confidence
  "confidence_lower": 9555.0,   // Could be as low as 9,555g
  "confidence_upper": 17745.0   // Could be as high as 17,745g
}
```

**How to use:**
- Low confidence (< 0.5): Use upper bound + extra safety stock
- High confidence (> 0.8): Can use predicted value with normal buffer

#### **4. `menu_item_breakdown` (Contributors)**

**What it means:** Which menu items use this ingredient

**Example:**
```json
{
  "menu_item_breakdown": [
    {
      "menu_item_name": "Smoky Chicken Burger",
      "quantity_per_serving": 140.0,
      "total_menu_items_predicted": 35.0,
      "total_ingredient_needed": 4900.0  // 35 × 140g
    },
    {
      "menu_item_name": "Chicken Rice Bowl",
      "quantity_per_serving": 130.0,
      "total_menu_items_predicted": 35.0,
      "total_ingredient_needed": 4550.0  // 35 × 130g
    }
  ]
}
```

**How to use:**
- Understand demand drivers
- Identify which menu items contribute most
- Plan prep by menu item

#### **5. `ai_adjustments` (Context Enhancement)**

**What it means:** How weather and events adjust the baseline forecast

**Example:**
```json
{
  "ai_adjustments": {
    "weather_impact_pct": -15,        // 15% decrease due to rain
    "events_impact_pct": 0,           // No major events
    "adjusted_forecast": 11602.5,     // 13650 × 0.85
    "reasoning": "Light rainfall expected on Tuesday-Thursday may reduce dine-in traffic by 15%",
    "weather_summary": "Rain on 3 days",
    "events_summary": "No major holidays"
  }
}
```

**How to use:**
- Adjust inventory based on external factors
- Understand why forecast changed
- Plan staffing based on predicted traffic

---

## 🔄 Forecast Lifecycle

### **1. Generation (Weekly - Sundays at Midnight)**

```
Orchestrator Scheduler
  ↓
Weekly Job: _run_demand_forecaster()
  ↓
For each of 40 ingredients:
  ├─ forecast_ingredient_demand() → Statistical baseline (Prophet)
  ├─ enhance_with_context() → AI adjustments (Claude + weather/events)
  └─ cache_forecast() → Store in demand_forecasts collection
```

### **2. Caching (24-hour TTL)**

```json
{
  "cached_at": "2026-02-24T00:00:00Z",
  "expires_at": "2026-02-25T00:00:00Z"  // 24 hours later
}
```

**After expiration:**
- MongoDB TTL index auto-deletes expired forecasts
- Next request triggers on-demand regeneration
- Weekly job refreshes all forecasts

### **3. Usage (Daily - 6 AM)**

```
Daily Job: Inventory Agent
  ↓
get_demand_forecasts() → Uses cached forecasts
  ↓
calculate_reorder_needs() → Determines what to order
  ↓
Generates Shopping List
```

---

## 📊 Viewing Forecasts in the UI (Future Feature)

Currently, forecasts are backend-only. To add a frontend dashboard:

### **Forecast Dashboard Page (Recommended)**

Create: `frontend/src/pages/ForecastDashboard.tsx`

**Features:**
1. **Ingredient Table**
   - Show all 40 ingredients with predictions
   - Sort by demand, confidence, or stock level
   - Filter by category

2. **Daily Demand Chart**
   - Line chart showing 7-day predictions
   - Confidence interval shading
   - Actual vs predicted (if available)

3. **Menu Item Contributors**
   - Breakdown by menu item
   - Contribution percentage
   - Recipe details

4. **AI Insights**
   - Weather impact display
   - Event notifications
   - Adjustment reasoning

**API Integration:**
```typescript
// Fetch all forecasts
const forecasts = await api.get('/api/v1/forecast/generate-all?use_cache=true');

// Fetch specific ingredient
const chicken = await api.get('/api/v1/forecast/ingredient/RM001');
```

---

## 🎯 Practical Use Cases

### **Use Case 1: Daily Inventory Check**

```bash
# Get today's predictions for all ingredients
docker compose exec -T mongodb mongosh --quiet ahar_pos --eval "
  const today = new Date().toISOString().split('T')[0];
  db.demand_forecasts.find({}).forEach(f => {
    const todayForecast = f.daily_breakdown.find(d => d.date === today);
    if (todayForecast) {
      print(f.material_id + ': ' + todayForecast.predicted + ' units needed today');
    }
  });
"
```

### **Use Case 2: Weekly Purchasing Budget**

```bash
# Calculate total purchasing cost for next 7 days
docker compose exec -T mongodb mongosh --quiet ahar_pos --eval "
  let totalCost = 0;
  db.demand_forecasts.find({}).forEach(f => {
    const inventory = db.raw_material_inventory.findOne({material_id: f.material_id});
    if (inventory) {
      const cost = f.predicted_consumption * inventory.unit_cost_inr;
      totalCost += cost;
      print(f.material_id + ': ₹' + (cost/100).toFixed(2));
    }
  });
  print('\\nTotal estimated cost: ₹' + (totalCost/100).toFixed(2));
"
```

### **Use Case 3: Low Stock Alert**

```bash
# Find ingredients that will run out soon
docker compose exec -T mongodb mongosh --quiet ahar_pos --eval "
  db.demand_forecasts.find({}).forEach(f => {
    const inventory = db.raw_material_inventory.findOne({material_id: f.material_id});
    if (inventory) {
      const dailyDemand = f.predicted_consumption / 7;
      const daysUntilStockout = inventory.current_stock / (dailyDemand * 1.2);
      if (daysUntilStockout < 3) {
        print('⚠️  ' + f.material_id + ': Only ' + daysUntilStockout.toFixed(1) + ' days of stock left');
      }
    }
  });
"
```

---

## 🔧 Manual Operations

### **Regenerate All Forecasts**

```bash
# Without AI (faster, free)
curl -X POST "http://localhost:8000/api/v1/forecast/generate-all?use_cache=false&enhance_with_ai=false"

# With AI (slower, uses API tokens)
curl -X POST "http://localhost:8000/api/v1/forecast/generate-all?use_cache=false&enhance_with_ai=true"
```

### **Clear Forecast Cache**

```bash
# Delete all forecasts (will regenerate on next request)
curl -X DELETE "http://localhost:8000/api/v1/forecast/cache/clear"
```

### **Trigger Inventory Agent Manually**

```bash
# Use forecasts to generate shopping list
curl -X POST "http://localhost:8000/api/v1/health/trigger-agent/inventory"
```

---

## 📝 Quick Reference

### **Most Common Queries**

```bash
# 1. Get forecast for specific ingredient
curl "http://localhost:8000/api/v1/forecast/ingredient/RM001"

# 2. View all forecasts in MongoDB
docker compose exec -T mongodb mongosh ahar_pos --eval "db.demand_forecasts.find().pretty()"

# 3. Check how many forecasts are cached
docker compose exec -T mongodb mongosh ahar_pos --eval "db.demand_forecasts.countDocuments({})"

# 4. Regenerate all forecasts
curl -X POST "http://localhost:8000/api/v1/forecast/generate-all?use_cache=false"

# 5. Find top 10 high-demand ingredients
docker compose exec -T mongodb mongosh ahar_pos --eval "
  db.demand_forecasts.find().sort({predicted_consumption: -1}).limit(10)
"
```

---

## 🎓 Summary

**Where:** MongoDB `demand_forecasts` collection
**How Many:** 40 forecasts (one per ingredient)
**Refresh:** Weekly (Sundays at midnight) + 24-hour cache
**Access:** REST API or direct MongoDB queries
**Use:** Inventory agent reads these for reorder calculations

The forecasts are the **foundation** of your demand-driven inventory management system!

---

**Last Updated:** 2026-02-24
