"""
Hybrid ABC Forecaster — v7

Wraps the pre-trained v7 model artifacts for production inference.

Architecture (matches antara_item_forecast_v7.py exactly):
  Class A (5.1% zeros)  → Global LightGBM regression        (31 BASE_FEATURES)
  Class B (20.8% zeros) → Tweedie regression                (35 features incl. sparse)
  Class C (72.6% zeros) → Rolling mean 7-day               (rolling_mean winner in v7 eval)

Prediction flow:
  1. Load artifacts from antara_forecast_results_v7/ (done once, lazy)
  2. Build name map: menu_item_id → canonical name (async, done once per DB)
  3. Per item: check eligibility → build features → autoregressive 7-day rollout
  4. Falls back to Prophet (in DemandForecaster) if item is ineligible

Class C note: The hurdle classifier (model_C_classifier.joblib) exists but the v7
evaluation showed rolling mean 7-day beats it (R²=0.298 vs 0.194). We use rolling
mean for Class C inference — no classifier call needed.
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Path to saved artifacts relative to this file
_ARTIFACTS_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "new_test_data"
    / "antara_forecast_results_v7"
)

# Confidence score and interval multiplier per class (reflects R²)
_CLASS_CONF = {
    "A": (0.85, 0.15),   # (confidence_score, interval_fraction_of_yhat)
    "B": (0.70, 0.25),
    "C": (0.55, 0.40),
}


class HybridABCForecaster:
    """
    Production wrapper around the v7 Hybrid ABC model artifacts.

    Usage (inside an async context):
        forecaster = HybridABCForecaster()
        forecaster.load_artifacts()           # sync — call at startup
        await forecaster.load_name_map(db)    # async — call before first predict
        result = forecaster.predict_item(menu_item_id, history_df)
    """

    MIN_HISTORY_DAYS: int = 14

    def __init__(self):
        self._loaded: bool = False
        self._model_A = None
        self._model_B = None
        # model_C_classifier exists but rolling mean wins — not used at inference
        self._feature_cols_A: List[str] = []
        self._feature_cols_BC: List[str] = []
        self._item_abc: Dict[str, str] = {}          # canonical_name → "A"/"B"/"C"
        self._item_global_mean: Dict[str, float] = {}
        self._cond_mean_C: Dict[str, float] = {}     # per-item (not used for C inference now)
        self._global_cond_mean_C: float = 1.5
        self._model_C_desc: str = ""

        self._id_to_canonical: Dict[str, str] = {}  # menu_item_id → canonical name
        self._name_map_loaded: bool = False
        self._name_map_lock: Optional[asyncio.Lock] = None

    # -------------------------------------------------------------------------
    # Artifact loading
    # -------------------------------------------------------------------------

    def load_artifacts(self) -> None:
        """
        Load all model artifacts from disk. Call once at application startup.
        Raises on missing files so the caller can fall back to Prophet gracefully.
        """
        import joblib  # noqa: PLC0415

        if self._loaded:
            return

        if not _ARTIFACTS_DIR.exists():
            raise FileNotFoundError(f"v7 artifacts directory not found: {_ARTIFACTS_DIR}")

        self._model_A = joblib.load(_ARTIFACTS_DIR / "model_A.joblib")
        self._model_B = joblib.load(_ARTIFACTS_DIR / "model_B_tweedie.joblib")
        # classifier not loaded — rolling mean used for C

        meta = joblib.load(_ARTIFACTS_DIR / "metadata.joblib")
        self._feature_cols_A = meta["feature_cols_A"]
        self._feature_cols_BC = meta["feature_cols_BC"]
        self._item_abc = meta["item_abc"]               # {canonical_name: "A"/"B"/"C"}
        self._item_global_mean = meta["item_global_mean"]
        self._cond_mean_C = meta["cond_mean_C"]
        self._global_cond_mean_C = meta.get("global_cond_mean_C", 1.5)
        self._model_C_desc = meta.get("model_C_desc", "rolling_mean")

        self._loaded = True
        n_items = len(self._item_abc)
        logger.info(
            f"HybridABCForecaster v7 loaded — {n_items} items in ABC map, "
            f"Class C uses: {self._model_C_desc}"
        )

    # -------------------------------------------------------------------------
    # Name map (async — requires DB)
    # -------------------------------------------------------------------------

    async def load_name_map(self, db) -> None:
        """
        Build menu_item_id → canonical_name lookup from the menu_items collection.
        Idempotent — safe to call multiple times; protected by asyncio.Lock.
        Canonical name = name.strip().title() to match v7 training normalization.
        """
        if self._name_map_lock is None:
            self._name_map_lock = asyncio.Lock()

        async with self._name_map_lock:
            if self._name_map_loaded:
                return

            # Orders and recipe_bom reference menu items by their MongoDB _id (hex
            # string), NOT by the human-readable menu_item_id field (e.g. MENU001).
            # Key the name map by str(_id) so can_use_v7() lookups match.
            cursor = db.menu_items.find({}, {"name": 1})
            async for doc in cursor:
                raw_name = (doc.get("name") or "").strip().title()
                mid = str(doc["_id"])
                if mid and raw_name:
                    self._id_to_canonical[mid] = raw_name

            self._name_map_loaded = True
            logger.info(
                f"HybridABCForecaster name map loaded — {len(self._id_to_canonical)} menu items"
            )

    # -------------------------------------------------------------------------
    # Eligibility check
    # -------------------------------------------------------------------------

    def can_use_v7(
        self, menu_item_id: str, history_df: pd.DataFrame
    ) -> Tuple[bool, str]:
        """
        Check whether v7 can be used for this item.

        Returns:
            (True, "ok") if eligible
            (False, reason_string) if not
        """
        if not self._loaded:
            return False, "artifacts_not_loaded"

        canonical = self._id_to_canonical.get(menu_item_id)
        if not canonical:
            return False, "item_not_in_name_map"

        if canonical not in self._item_abc:
            return False, "item_not_in_abc_map"

        if len(history_df) < self.MIN_HISTORY_DAYS:
            return False, f"insufficient_history_{len(history_df)}_days"

        return True, "ok"

    # -------------------------------------------------------------------------
    # Feature engineering
    # -------------------------------------------------------------------------

    @staticmethod
    def _try_import_holidays():
        """Import holidays library; return None if unavailable."""
        try:
            import holidays as hol  # noqa: PLC0415
            return hol.India(years=list(range(2024, 2028)))
        except ImportError:
            logger.warning("holidays package not installed — is_holiday feature will be 0")
            return None

    _india_holidays = None  # class-level cache

    @classmethod
    def _get_holidays(cls):
        if cls._india_holidays is None:
            cls._india_holidays = cls._try_import_holidays()
        return cls._india_holidays

    def _build_feature_row(
        self,
        extended_history: pd.DataFrame,
        forecast_date: datetime,
        canonical_name: str,
        abc_class: str,
    ) -> np.ndarray:
        """
        Build a single feature vector for forecast_date given an extended history
        (real data + prior-predicted days appended as rows).

        Args:
            extended_history: DataFrame with columns ds (datetime), y (float).
                              Must include all dates up to (forecast_date - 1 day).
            forecast_date: The date we are predicting.
            canonical_name: Title-cased menu item name (from v7 training).
            abc_class: "A", "B", or "C".

        Returns:
            numpy array shaped (1, n_features) ready for LightGBM.predict().
        """
        # Work on a copy sorted by date (ascending)
        h = extended_history.copy().sort_values("ds").reset_index(drop=True)
        y = h["y"].values  # convenience alias

        n = len(y)

        def lag(k: int) -> float:
            """lag_k: value k rows before the end (i.e. k days ago)."""
            idx = n - k
            return float(y[idx]) if idx >= 0 else 0.0

        def roll_mean(w: int) -> float:
            window = y[max(0, n - w): n]
            return float(window.mean()) if len(window) > 0 else 0.0

        def roll_std(w: int) -> float:
            window = y[max(0, n - w): n]
            return float(window.std()) if len(window) >= 2 else 0.0

        def roll_max(w: int) -> float:
            window = y[max(0, n - w): n]
            return float(window.max()) if len(window) > 0 else 0.0

        def roll_min(w: int) -> float:
            window = y[max(0, n - w): n]
            return float(window.min()) if len(window) > 0 else 0.0

        # same_dow_last_week: most recent prior row with matching day-of-week
        target_dow = forecast_date.weekday()
        same_dow_rows = h[h["ds"].dt.dayofweek == target_dow]["y"].values
        same_dow_last_week = float(same_dow_rows[-1]) if len(same_dow_rows) > 0 else 0.0

        # sell_rate over last w days
        def sell_rate(w: int) -> float:
            window = y[max(0, n - w): n]
            return float((window > 0).mean()) if len(window) > 0 else 0.0

        # days_since_last_sale
        nonzero_idx = np.where(y > 0)[0]
        if len(nonzero_idx) > 0:
            last_sale_date = h["ds"].iloc[nonzero_idx[-1]]
            days_since_last_sale = float((forecast_date - last_sale_date).days)
            qty_at_last_sale = float(y[nonzero_idx[-1]])
        else:
            days_since_last_sale = float(n)
            qty_at_last_sale = 0.0

        # Calendar features
        dow = forecast_date.weekday()
        month = forecast_date.month
        day_of_month = forecast_date.day
        week_of_year = forecast_date.isocalendar()[1]
        day_of_year = forecast_date.timetuple().tm_yday

        india_holidays = self._get_holidays()
        is_holiday = int(
            india_holidays is not None
            and forecast_date.date() in india_holidays
        )

        # item_global_mean from training data (constant for this item)
        item_global_mean = self._item_global_mean.get(canonical_name, 0.0)
        abc_id = {"A": 0, "B": 1, "C": 2}[abc_class]

        # Build feature dict matching training script column names exactly
        feat: Dict[str, float] = {
            "item_global_mean": item_global_mean,
            "abc_id": abc_id,
            "day_of_week": dow,
            "day_of_month": day_of_month,
            "week_of_year": week_of_year,
            "month": month,
            "is_weekend": int(dow >= 5),
            "is_monday": int(dow == 0),
            "is_friday": int(dow == 4),
            "is_holiday": is_holiday,
            "day_of_year": day_of_year,
            "dow_sin": math.sin(2 * math.pi * dow / 7),
            "dow_cos": math.cos(2 * math.pi * dow / 7),
            "month_sin": math.sin(2 * math.pi * month / 12),
            "month_cos": math.cos(2 * math.pi * month / 12),
            # Lags
            "lag_1": lag(1),
            "lag_2": lag(2),
            "lag_3": lag(3),
            "lag_7": lag(7),
            "lag_14": lag(14),
            # Rolling means
            "roll_mean_3": roll_mean(3),
            "roll_mean_7": roll_mean(7),
            "roll_mean_14": roll_mean(14),
            "roll_mean_28": roll_mean(28),
            # Rolling stds
            "roll_std_3": roll_std(3),
            "roll_std_7": roll_std(7),
            "roll_std_14": roll_std(14),
            "roll_std_28": roll_std(28),
            # Rolling max/min
            "roll_max_7": roll_max(7),
            "roll_min_7": roll_min(7),
            # Same day of week last week
            "same_dow_last_week": same_dow_last_week,
            # Sparse features (only used for B/C feature cols)
            "sell_rate_7d": sell_rate(7),
            "sell_rate_14d": sell_rate(14),
            "days_since_last_sale": days_since_last_sale,
            "qty_at_last_sale": qty_at_last_sale,
        }

        # Select and order columns exactly as training
        feature_cols = (
            self._feature_cols_A if abc_class == "A" else self._feature_cols_BC
        )
        row = np.array([[feat[col] for col in feature_cols]], dtype=np.float64)
        return row

    # -------------------------------------------------------------------------
    # Prediction
    # -------------------------------------------------------------------------

    def predict_item(
        self,
        menu_item_id: str,
        history_df: pd.DataFrame,
        horizon_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Predict daily menu item quantities for the next horizon_days days.

        Uses autoregressive rollout: each day's prediction is appended to history
        before computing features for the next day (required for lag features to
        reflect predicted values, not stale actuals).

        Args:
            menu_item_id: Menu item identifier (maps to canonical name via name map).
            history_df: DataFrame with columns ds (datetime), y (float).
                        Must be zero-filled for missing dates (as _get_historical_orders does).
            horizon_days: Days to forecast (default 7).

        Returns:
            Dict matching DemandForecaster.forecast_menu_item() output schema, with
            model_type set to "hybrid_abc_v7_A", "hybrid_abc_v7_B", or "hybrid_abc_v7_C".
        """
        canonical = self._id_to_canonical[menu_item_id]
        abc_class = self._item_abc[canonical]
        conf_score, interval_frac = _CLASS_CONF[abc_class]

        # Determine base date: last date in history
        history_sorted = history_df.copy().sort_values("ds").reset_index(drop=True)
        last_actual_date = pd.Timestamp(history_sorted["ds"].iloc[-1])
        today = last_actual_date  # we predict days after the last known date

        extended = history_sorted.copy()
        predictions = []

        for day_offset in range(1, horizon_days + 1):
            forecast_dt = today + timedelta(days=day_offset)
            forecast_date = forecast_dt.to_pydatetime() if hasattr(forecast_dt, "to_pydatetime") else forecast_dt

            if abc_class == "C":
                # Rolling mean 7-day wins for Class C (v7 result)
                qty = float(
                    extended["y"].iloc[-7:].mean()
                    if len(extended) >= 1
                    else self._global_cond_mean_C
                )
                qty = max(0.0, qty)
            else:
                feat_row = self._build_feature_row(
                    extended, forecast_date, canonical, abc_class
                )
                if abc_class == "A":
                    raw = float(self._model_A.predict(feat_row)[0])
                else:  # B
                    raw = float(self._model_B.predict(feat_row)[0])
                qty = max(0.0, raw)

            # Confidence bounds
            lower = max(0.0, qty * (1.0 - interval_frac))
            upper = qty * (1.0 + interval_frac)

            predictions.append({
                "date": forecast_date.strftime("%Y-%m-%d") if hasattr(forecast_date, "strftime") else str(forecast_date)[:10],
                "predicted_quantity": qty,
                "lower_bound": lower,
                "upper_bound": upper,
            })

            # Extend history with predicted value for next iteration
            new_row = pd.DataFrame([{"ds": forecast_dt, "y": qty}])
            extended = pd.concat([extended, new_row], ignore_index=True)

        total_predicted = sum(p["predicted_quantity"] for p in predictions)
        historical_avg = float(history_sorted["y"].mean())

        return {
            "menu_item_id": menu_item_id,
            "forecast_date": datetime.utcnow().isoformat(),
            "horizon_days": horizon_days,
            "predictions": predictions,
            "total_predicted": total_predicted,
            "confidence_score": conf_score,
            "historical_avg": historical_avg,
            "model_type": f"hybrid_abc_v7_{abc_class}",
        }
