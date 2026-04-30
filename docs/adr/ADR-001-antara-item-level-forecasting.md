# ADR-001: AnTeRa Kitchen & Bar — Item-Level Daily Sales Forecasting

**Date**: 2026-04-10
**Status**: Accepted
**Decider**: Pandiarajan
**Context**: AnTeRa Kitchen & Bar, single restaurant, 119 days of POS data (Dec 2025 – Mar 2026)

---

## Problem

Predict daily quantity sold per menu item so the restaurant can plan procurement,
prep, and staffing. The data is a POS transaction log — one row per order line —
that needed to be aggregated before any modelling could begin.

---

## Data Decisions

### Decision: Filter to SuccessOrder only
- **Rejected**: Including CancleOrder and ComplementaryOrder rows
- **Reason**: Cancelled orders were never fulfilled (no demand signal). Complementary orders are not paid demand and would distort item popularity.

### Decision: Item name normalisation via `.str.title()`
- **Reason**: Raw data had casing inconsistencies (`Coriander (kothimeera)` vs `Coriander (Kothimeera)`) causing the same item to appear as two separate items, inflating item count and splitting its history.

### Decision: Drop items present on fewer than 5% of days
- **Threshold**: 5% day-presence (i.e. sold on fewer than ~6 of 119 days)
- **Reason**: Items with near-zero presence have no learnable pattern. Including them adds noise and inflates the item count from 394 to 323 active items.
- **Result**: 323 items retained out of 394 unique items.

### Decision: Build a dense panel (fill missing item-days with 0)
- **Reason**: The raw aggregation only has rows for days when an item was sold. Lag and rolling features require a continuous time index per item. Missing days filled with 0 quantity.

---

## ABC Classification

### Decision: Classify items into A / B / C using Pareto on total volume
- **Thresholds**:
  - Class A: items that cumulatively account for the first 80% of total qty sold
  - Class B: items from 80% → 95% cumulative volume
  - Class C: remaining tail items (last 5% of volume)
- **Result**:
  - A: 81 items — 80.1% of volume
  - B: 89 items — 15.0% of volume
  - C: 153 items — 4.9% of volume
- **Reason**: Demand behaviour is fundamentally different across classes. A single model trying to serve all three compromises on all three. ABC classification is the basis for the hybrid model strategy.

---

## Feature Engineering Decisions

### Decision: Use lag features (1, 2, 3, 7, 14 days) and rolling statistics
- **Reason**: Sales on day N are strongly correlated with recent sales history. Lag-7 captures the same-day-of-week effect. Rolling means capture trend. All computed with a shift(1) to prevent data leakage.

### Decision: Cyclical encoding for day_of_week and month
- `dow_sin`, `dow_cos`, `month_sin`, `month_cos`
- **Reason**: Day 6 (Sunday) and Day 0 (Monday) are one day apart but numerically far. Cyclical encoding preserves the circular nature of calendar features.

### Decision: item_global_mean computed from train only
- **Reason**: Using the full dataset's item mean would leak future information into training. The mean is computed on the training period and mapped onto val/test.

### Decision: Add abc_id as a feature
- **Reason**: Allows the model to learn that Class A items behave differently from B and C without requiring separate models at the feature level.

---

## Train / Val / Test Split

### Decision: Temporal split — no shuffling
```
Train : Dec 01 2025 → Feb 28 2026  (90 days, ~76%)
Val   : Mar 01 2026 → Mar 15 2026  (15 days, ~12%)
Test  : Mar 16 2026 → Mar 29 2026  (14 days, ~12%)
```
- **Reason**: Sales forecasting is a forward-looking problem. Shuffling would leak future data into training. The model must always be trained on past data and evaluated on unseen future data.
- **Each split is at item × day level**: all 323 items are present in all three splits.

---

## Model Selection Journey

### v1 — Single Global LightGBM (baseline)
- **Approach**: One LightGBM model trained on all 323 items together. Hyperparameters hand-tuned.
- **Test results**:
  - Overall: RMSE=7.017, R²=0.944
  - Class A: RMSE=13.034, R²=0.945
  - Class B: RMSE=4.507,  R²=0.139  ← problem
  - Class C: RMSE=1.486,  R²=0.250
- **Finding**: Class B R²=0.139 means the model explains almost none of Class B variance. The global model was dominated by Class A patterns and failed on mid-tier items.

### v1 — Other models compared (same setup)
All models compared on test set. LightGBM was best overall:

| Model | RMSE | R² |
|---|---|---|
| LightGBM | 7.017 | 0.944 |
| Gradient Boosting | 7.261 | 0.940 |
| Random Forest | 7.525 | 0.936 |
| XGBoost | 8.196 | 0.924 |
| Ridge Regression | 8.199 | 0.924 |
| Baseline (roll mean 7d) | 10.657 | 0.874 |

**Decision**: LightGBM selected as the base model for all subsequent work.

### v2 — Three Separate Per-class LightGBM Models + Optuna
- **Approach**: Dedicated LightGBM per class (A, B, C), each Optuna-tuned on overall val RMSE.
- **Key finding**: Class B R² improved from 0.139 → 0.321. Class A slightly worsened (less training data per model).
- **Problem identified**: Optuna for the global/Class A model was tuning on all items' val RMSE, meaning Class B and C noise was influencing the Class A tuning objective.

### v3 — Hybrid (Global for A, Dedicated for B, Rolling mean for C)
- **Approach**: Picked the best model type per class from v1/v2 findings. But Optuna objectives were still not class-specific.
- **Problem**: Class B R² dropped back to 0.131. Root cause: Optuna tuned on overall val RMSE again, not Class B val RMSE specifically.

### v4 — Optimal Hybrid (superseded by v7)
- **Fix**: Each model's Optuna objective now targets its own class's validation RMSE exclusively.
  - Model A: trains on all items, Optuna optimises Class A val RMSE only
  - Model B: trains on Class B items only, Optuna optimises Class B val RMSE only
  - Model C: rolling mean 7-day, no ML
- **Test results**:
  - Overall: RMSE=6.900, R²=0.946
  - Class A: RMSE=12.840, R²=0.947
  - Class B: RMSE=4.381,  R²=0.187
  - Class C: RMSE=1.437,  R²=0.298

### v5 — Remove item_id (superseded by v7)
- **Change**: Dropped `item_id` from feature set (31 features from 32).
- **Reason**: `item_id` is a restaurant-specific label with no causal relationship to demand. It caused the model to memorise item identities rather than learn generalisable patterns. `item_global_mean` and `abc_id` already proxy everything useful it captured.
- **Cross-restaurant benefit**: Removing it is a prerequisite for any future cross-restaurant model transfer.
- **Test results**:
  - Overall: RMSE=6.573, R²=0.951 ← marginal gain over v4
  - Class B R²=0.172 ← slight drop (no improvement to Class B from this change alone)

### v6 — Hurdle Model for Class B (rejected — wrong class targeted)
- **Hypothesis**: Class B has ~40–70% zero days; a single regression model can't distinguish "didn't sell" from "sold less."
- **Approach**: Two-part hurdle for Class B — LightGBM classifier for sell/no-sell, then conditional LightGBM regressor trained on non-zero rows only.
- **Result**: Class B R² collapsed to 0.052 (worse than all prior versions).
- **Post-mortem**: Multiplying P(sell) × E(qty|sells) compounds errors when sell probability is already high (~0.8 for Class B). The hurdle architecture is suited for near-zero items — it belongs on Class C, not Class B.

### v7 — Statistically Correct Architecture Per Class (superseded by v9)
- **Key insight from v6**: Each class has a fundamentally different demand distribution that requires a matched model family.
  - Class A (5.1% zeros): standard regression is appropriate
  - Class B (20.8% zeros): zero-inflated but not sparse — needs a distribution that naturally handles it
  - Class C (72.6% zeros): truly sparse — the sell/no-sell decision dominates
- **Architecture**:
  - Model A: Global LightGBM regression, 31 features, Optuna on Class A val RMSE (unchanged from v5)
  - Model B: LightGBM with Tweedie loss (compound Poisson-Gamma), `tweedie_variance_power=1.622` tuned by Optuna — single model, no compound error risk
  - Model C: Hurdle model tested but rolling mean wins (hurdle R²=0.194 vs rolling mean R²=0.298 — conditional quantity is nearly constant at 1–2 units per item, so a fixed per-item conditional mean dominates)
- **Test results**:
  - Overall: RMSE=6.532, R²=0.952 ← best overall
  - Class A: RMSE=12.122, R²=0.953 ← best Class A
  - Class B: RMSE=4.189,  R²=0.256 ← best Class B (major improvement)
  - Class C: RMSE=1.437,  R²=0.298 ← rolling mean retained

### v8 — MongoDB-Native Training (superseded — synthetic data regression)

- **Goal**: Replace static Excel source with live MongoDB (`status=COMPLETED`) so retraining always uses the latest orders.
- **Change**: Data pulled from `orders` collection via aggregation pipeline; `TRAIN_END` extended to 2026-03-31 (~135 days including synthetic Mar 30–Apr data); ABC assignments locked from v7 for the original 323 items.
- **Architecture**: Unchanged from v7 (Model A: global LightGBM, Model B: Tweedie, Model C: rolling mean).
- **Result**: Overall R²=0.403, RMSE=7.398 — a severe regression from v7 (R²=0.952).
  - Class A: R²=0.530, Class B: R²=0.232, Class C: R²=0.406
  - 398 items in ABC map (323 real + 75 newly seen in synthetic orders)
- **Root cause**: MongoDB contained synthetic orders seeded from Dec 2025 patterns (via `seed_mar_apr_2026.py`). These synthetic rows introduced volume patterns inconsistent with real demand, corrupting the training signal for all three classes. The model memorised synthetic patterns that do not generalise to real held-out data.
- **Additional problem**: Alcohol and tobacco items were included in training. Alcohol demand is driven by social occasions and weekday/weekend spikes fundamentally different from food demand. Mixing alcohol into the same ABC classification framework distorted item-level volume rankings, misclassifying several food items into the wrong tier.

### v9 — Real Data Only, Food Items Only (ACCEPTED — current production model)

- **Key changes from v8**:
  1. **Data source reverted to Excel** (`Restaurant_Data.xlsx`, real POS data Dec 1 2025 – Mar 29 2026). All synthetic orders excluded. This restores the same clean 119-day training window as v7, eliminating synthetic contamination.
  2. **Alcohol/tobacco items explicitly excluded**: 120 items (whisky, gin, vodka, rum, beer, wine, cocktails, AnTeRa signature cocktails, tobacco) removed before any feature engineering. The exclusion is hardcoded in an `ALCOHOL_ITEMS` set and applied as a filter after raw load.
  3. **ABC locked from v8 food items**: Items that existed in v8 and are not alcohol retain their v8 ABC tier. Only genuinely new food items are classified fresh. This prevents tier boundary shifts from destabilising stable production items.
- **Architecture**: Unchanged (Model A: global LightGBM, Model B: Tweedie, Model C: rolling mean — hurdle tested again for C but rolling mean wins at R²=0.778 vs hurdle on this food-only dataset).
- **Item count**: 247 food items (vs 323 in v7, 398 in v8). The reduction reflects both the alcohol exclusion and the 5% day-presence threshold applied to the shorter real-data window.
- **Test results**:
  - Overall: RMSE=8.992, R²=0.926
  - Class A: RMSE=15.751, R²=0.921 (42 items — higher RMSE than v7 due to larger absolute volumes on real data)
  - Class B: RMSE=2.906, R²=0.533 (35 items — best Class B result across all versions)
  - Class C: RMSE=0.775, R²=0.778 (170 items — substantial improvement over v8's 0.41)
- **MongoDB cleanup**: `remove_alcohol_from_mongo.py` purged alcohol items from `menu_items`, `recipe_bom`, `orders` (fully-alcohol orders deleted; mixed orders stripped), `inventory_consumption_logs`, `stock_movement_log`, and `packaging_bom`. This aligns the live database with the v9 training scope.

---

## Version Performance Summary

| Version | Overall R² | Overall RMSE | Class A R² | Class B R² | Class C R² | Key change |
|---|---|---|---|---|---|---|
| v4 | 0.946 | 6.900 | 0.947 | 0.187 | 0.298 | Class-specific Optuna objectives |
| v5 | 0.951 | 6.573 | 0.953 | 0.172 | 0.298 | Remove item_id |
| v6 | 0.950 | 6.633 | 0.953 | 0.052 | 0.298 | Hurdle on B (wrong — hurt B badly) |
| v7 | 0.952 | 6.532 | 0.953 | 0.256 | 0.298 | Tweedie B, rolling mean C |
| v8 | 0.403 | 7.398 | 0.530 | 0.232 | 0.406 | MongoDB-native (synthetic data contamination) |
| **v9** | **0.926** | **8.992** | **0.921** | **0.533** | **0.778** | Real data only + alcohol excluded |

---

## Decisions Rejected / Deferred

### Rejected: Hurdle model for Class B
- **Reason**: Tested in v6. Class B sell rate is ~80%, so multiplying P(sell) × E(qty|sells) compounds error without benefit. Tweedie regression (v7) is the correct approach for moderately zero-inflated continuous demand.

### Rejected: Hurdle model for Class C (conditional regressor component)
- **Reason**: Tested in v7. The conditional quantity for Class C items is nearly constant (1–2 units/day). A fixed per-item conditional mean beats a learned regressor. Rolling mean 7-day remains Class C's model.

### Rejected: Including alcohol/tobacco items in the food demand model
- **Reason**: Tested implicitly in v8. Alcohol demand is driven by social occasions, weekend spikes, and discretionary spend — fundamentally different dynamics from food items. Including 120 alcohol items in the same LightGBM/Tweedie framework distorted ABC tier boundaries and hurt food item predictions. The RM049 abstracted SKU (ADR-006) means alcohol does not need forecasting for inventory purposes. Excluded permanently from v9 onward; a separate bar forecaster would be required if granular alcohol inventory is added.

### Rejected: Synthetic order data as a training data source
- **Reason**: v8 demonstrated that synthetic orders seeded from Dec 2025 patterns contaminate the training signal. Synthetic volumes do not match real demand patterns; training on them caused R² to collapse from 0.952 (v7) to 0.403 (v8). Synthetic data should not enter the training pipeline until it can be clearly tagged and filtered.

### Rejected: Exponential Smoothing
- **Reason**: lag and rolling features in LightGBM already capture the same effect. Adding exponential smoothing as a separate model per item (323 fits) adds complexity with negligible marginal gain.

### Deferred: Weather data
- **Reason**: Only 119 days of data across a narrow Dec–Mar window. Insufficient to learn weather–sales correlations reliably. Revisit when 12+ months of data is available.

### Rejected (for now): LLM to improve accuracy
- **Reason**: An LLM has no access to live data at inference time and cannot improve predictive accuracy. Useful only as a reporting/explanation layer on top of model output — a separate concern.

### Deferred: Promotions and events as features
- **Reason**: The `Discount Reason` and `Order Type` columns are available and likely informative for Class B. Not yet implemented — highest-priority next step after having more data.

---

## Known Limitations

| Issue | Impact | Path forward |
|---|---|---|
| Class A RMSE=15.75 (v9) | Higher absolute error vs v7 — real data has larger volume spikes | Promotions/events features expected to explain peak variance |
| Class B R²=0.533 (v9) | Mid-tier items partially predicted; best result so far | Add promotions/discount features; R² should push above 0.6 |
| Class C R²=0.778 (v9) | Sparse items well-modelled by rolling mean; diminishing ML returns | Accept; revisit only if hurdle beats rolling mean on a future data window |
| Only 119 days of real training data (v9) | Model hasn't seen seasonal variation (Dec–Mar only) | Retrain when 12+ months of real data available |
| Alcohol items fully excluded from model | Bar demand completely unforecasted; RM049 abstraction absorbs cost | Design a separate bar forecaster when per-SKU alcohol tracking is enabled |
| Single restaurant | Model is AnTeRa-specific; cannot generalise | item_id removed (v5) as prerequisite for transfer learning |
| High MAPE (55–71%) | Percentage errors large for low-volume items | Expected with sparse demand; use MAE for business decisions |

---

## Output Files

| File | Purpose |
|---|---|
| `backend/new_test_data/antara_item_forecast.py` | v1 — global model, all model comparisons |
| `backend/new_test_data/antara_item_forecast_v2.py` | v2 — per-class models, Optuna |
| `backend/new_test_data/antara_item_forecast_v3.py` | v3 — hybrid attempt (superseded) |
| `backend/new_test_data/antara_item_forecast_v4.py` | v4 — class-specific Optuna objectives (superseded) |
| `backend/new_test_data/antara_item_forecast_v5.py` | v5 — remove item_id (superseded) |
| `backend/new_test_data/antara_item_forecast_v6.py` | v6 — hurdle on Class B (rejected approach) |
| `backend/new_test_data/antara_item_forecast_v7.py` | v7 — Tweedie B + rolling mean C (superseded) |
| `backend/new_test_data/antara_forecast_results_v7/` | Test plots and results JSON for v7 |
| `backend/new_test_data/antara_item_forecast_v8.py` | v8 — MongoDB-native (superseded, synthetic contamination) |
| `backend/new_test_data/antara_forecast_results_v8/` | Test plots and results JSON for v8 |

---

## Production Deployment Findings (2026-04-14)

v7 was integrated into the inventory agent as the primary forecaster (see ADR-003). The following data-reconciliation facts were established during integration testing:

### Training vs Production data reconciliation

| Dimension | Training (v7) | MongoDB menu_items | Notes |
|---|---|---|---|
| Unique canonical item names | 323 | 444 | DB has more items added after training cutoff |
| Names matched (`.strip().title()`) | — | 365 of 444 | 79 DB items have no v7 model (new or renamed items) |
| Matched items by v7 ABC class | A=95, B=91, C=179 | — | Higher than training counts due to duplicate names in DB |
| Duplicate canonical names in DB | — | 46 names | Same name, multiple `_id` documents |
| Items in recipe_bom (eligible for ingredient forecasting) | 60 | — | Of these: A=57, B=3, C=0 |

**Implication**: In the current AnTeRa recipe BOM, 57 of 60 recipe items are Class A. Class B and C items in the menu are rarely used as recipe ingredients. Almost all ingredient-level demand forecasts will use the LightGBM path.

### Class B eligibility gap

The 3 Class B recipe items had orders only in Dec 2025. With a 90-day lookback from April 2026, their history was empty and v7 eligibility failed (`insufficient_history`). **Fix applied**: extended live lookback window from 90 days → 180 days in `demand_forecaster.py`. This brings Dec 2025 data into scope.

### Name-map keying fix

`load_name_map()` was originally keying by `doc["menu_item_id"]` (a MENU001-style field). But `orders.items.menu_item_id` and `recipe_bom.menu_item_id` store MongoDB `_id` hex strings. **Fix applied**: changed to key by `str(doc["_id"])` so the lookup succeeds for all recipe items reaching `can_use_v7()`.

---

## v9 Production Migration (2026-04-28)

v9 replaced v7 as the production model. The following changes were applied:

### Alcohol purge from MongoDB

`remove_alcohol_from_mongo.py` was run against live `ahar_pos`. Scope of deletions:

| Collection | Action |
|---|---|
| `menu_items` | Deleted all alcohol item documents |
| `recipe_bom` | Deleted all BOM rows for alcohol items |
| `orders` | Deleted fully-alcohol orders; stripped alcohol line items from mixed orders and recalculated `total_amount` |
| `inventory_consumption_logs` | Deleted logs tied to fully-alcohol orders |
| `stock_movement_log` | Deleted movements referencing removed order IDs or alcohol material names |
| `packaging_bom` | Deleted packaging rows for alcohol `menu_item_id` references |

**Reason**: v9 is trained exclusively on food items. Alcohol items in `menu_items` would reach the name-map lookup and receive a fallback Rolling Mean forecast based on their order history — but that history is now deleted from `orders`. Purging them from the DB prevents stale forecasts and keeps `menu_items` in sync with the model's scope.

### Item count after purge

| Dimension | Before purge | After purge |
|---|---|---|
| `menu_items` documents | ~444 | ~324 |
| `recipe_bom` rows | ~1,972 | ~1,500 (approx) |
| v9 ABC map items | — | 247 food items |

### Production wrapper update

`hybrid_abc_forecaster.py` updated to load v9 artifacts from `antara_forecast_results_v9/` instead of v7. Method names retain `v8` in some internal references (legacy naming) but inference path is fully v9.

---

## Output Files

| File | Purpose |
|---|---|
| `backend/new_test_data/antara_item_forecast.py` | v1 — global model, all model comparisons |
| `backend/new_test_data/antara_item_forecast_v2.py` | v2 — per-class models, Optuna |
| `backend/new_test_data/antara_item_forecast_v3.py` | v3 — hybrid attempt (superseded) |
| `backend/new_test_data/antara_item_forecast_v4.py` | v4 — class-specific Optuna objectives (superseded) |
| `backend/new_test_data/antara_item_forecast_v5.py` | v5 — remove item_id (superseded) |
| `backend/new_test_data/antara_item_forecast_v6.py` | v6 — hurdle on Class B (rejected approach) |
| `backend/new_test_data/antara_item_forecast_v7.py` | v7 — Tweedie B + rolling mean C (superseded) |
| `backend/new_test_data/antara_forecast_results_v7/` | Test plots and results JSON for v7 |
| `backend/new_test_data/antara_item_forecast_v8.py` | v8 — MongoDB-native (superseded, synthetic contamination) |
| `backend/new_test_data/antara_forecast_results_v8/` | Test plots and results JSON for v8 |
| `backend/new_test_data/antara_item_forecast_v9.py` | v9 — real data only, food items only (current) |
| `backend/new_test_data/antara_forecast_results_v9/` | Test plots and results JSON for v9 |
| `backend/new_test_data/remove_alcohol_from_mongo.py` | Purge script — removes alcohol items from all MongoDB collections to match v9 scope |
| `backend/app/services/ml/hybrid_abc_forecaster.py` | **Production wrapper** — v9 inference, name-map loading, autoregressive rollout |

---

## Next Decisions Pending

1. **Promotions/events features for Class B** — `Discount Reason` and `Order Type` columns available; expected to push Class B R² from 0.533 toward 0.65+
2. **Retrain trigger** — define how often the model should be retrained (weekly? monthly? data-drift triggered?). At 119 days real data, a monthly retrain cadence would expand the training window meaningfully.
3. ~~**Serving the model**~~ — **Resolved**: v9 integrated into inventory agent via `HybridABCForecaster` wrapper (see ADR-003)
4. **Synthetic data strategy for retraining** — v8 proved synthetic orders contaminate training. Either (a) gate MongoDB queries to `order_date ≤ 2026-03-29` (last real data date) or (b) tag synthetic orders in the DB so they can be excluded. Currently v9 bypasses the problem by using Excel, but the MongoDB retraining path must be fixed before daily data extension is useful.
5. **Multi-restaurant strategy** — one model per restaurant (current path, item_id removed as prerequisite) vs shared model with restaurant embeddings; requires cross-restaurant transfer evaluation
6. **Alcohol forecasting** — v9 and the DB cleanup removed all alcohol from training and from `menu_items`. If/when bar management is added back, a dedicated bar demand model is needed (separate from the food ABC framework).
7. **Handling new food items** — items added to the menu after v9 training fall back to rolling mean. Define retraining cadence to close this gap.
