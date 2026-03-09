"""
Time Series Utilities

Provides utilities for time series analysis:
- Stationarity testing (ADF, KPSS)
- Differencing
- Autocorrelation analysis
- Seasonality detection

Critical for SARIMA model selection (requires stationary data).
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from statsmodels.tsa.stattools import adfuller, kpss, acf, pacf
from statsmodels.tsa.seasonal import seasonal_decompose

logger = logging.getLogger(__name__)


class TimeSeriesUtils:
    """
    Utilities for time series analysis and preprocessing

    Use cases:
    - Test stationarity before using SARIMA
    - Determine differencing order (d in ARIMA)
    - Detect seasonality patterns
    - Analyze autocorrelation
    """

    @staticmethod
    def test_stationarity(
        data: pd.Series,
        significance_level: float = 0.05
    ) -> Dict[str, Any]:
        """
        Test if time series is stationary using ADF and KPSS tests

        Stationarity requirements for SARIMA:
        - Constant mean over time
        - Constant variance over time
        - No seasonality (or seasonality removed)

        Args:
            data: Time series data
            significance_level: Significance level for tests (default 0.05)

        Returns:
            {
                "is_stationary": bool,
                "adf_statistic": float,
                "adf_pvalue": float,
                "adf_conclusion": str,
                "kpss_statistic": float,
                "kpss_pvalue": float,
                "kpss_conclusion": str,
                "recommendation": str
            }
        """
        if len(data) < 20:
            return {
                "is_stationary": False,
                "recommendation": f"Insufficient data for stationarity testing (need >= 20 points, got {len(data)})",
                "error": "insufficient_data"
            }

        try:
            # Augmented Dickey-Fuller test (null hypothesis: non-stationary)
            adf_result = adfuller(data.dropna(), autolag='AIC')
            adf_statistic = adf_result[0]
            adf_pvalue = adf_result[1]
            adf_is_stationary = adf_pvalue < significance_level

            # KPSS test (null hypothesis: stationary)
            kpss_result = kpss(data.dropna(), regression='c', nlags="auto")
            kpss_statistic = kpss_result[0]
            kpss_pvalue = kpss_result[1]
            kpss_is_stationary = kpss_pvalue > significance_level

            # Combined conclusion
            # Both tests should agree for strong stationarity conclusion
            if adf_is_stationary and kpss_is_stationary:
                is_stationary = True
                conclusion = "Stationary"
                recommendation = "Data is stationary. SARIMA can be used."
            elif not adf_is_stationary and not kpss_is_stationary:
                is_stationary = False
                conclusion = "Non-stationary"
                recommendation = "Data is non-stationary. Apply differencing before using SARIMA."
            else:
                is_stationary = False
                conclusion = "Inconclusive"
                recommendation = (
                    "Tests disagree. Data may have trend or seasonality. "
                    "Try differencing or use Prophet/XGBoost instead."
                )

            return {
                "is_stationary": is_stationary,
                "adf_statistic": round(float(adf_statistic), 4),
                "adf_pvalue": round(float(adf_pvalue), 4),
                "adf_conclusion": "Stationary" if adf_is_stationary else "Non-stationary",
                "kpss_statistic": round(float(kpss_statistic), 4),
                "kpss_pvalue": round(float(kpss_pvalue), 4),
                "kpss_conclusion": "Stationary" if kpss_is_stationary else "Non-stationary",
                "overall_conclusion": conclusion,
                "recommendation": recommendation
            }

        except Exception as e:
            logger.error(f"Stationarity test failed: {e}")
            return {
                "is_stationary": False,
                "recommendation": f"Stationarity test failed: {str(e)}",
                "error": str(e)
            }

    @staticmethod
    def difference_data(
        data: pd.Series,
        order: int = 1,
        seasonal_period: Optional[int] = None
    ) -> pd.Series:
        """
        Apply differencing to make data stationary

        Differencing removes trend and seasonality:
        - First-order: y'(t) = y(t) - y(t-1)
        - Second-order: y''(t) = y'(t) - y'(t-1)
        - Seasonal: y'(t) = y(t) - y(t-s) where s is seasonal period

        Args:
            data: Time series data
            order: Differencing order (1 or 2)
            seasonal_period: Seasonal period for seasonal differencing (e.g., 7 for weekly)

        Returns:
            Differenced series
        """
        result = data.copy()

        # Regular differencing
        for i in range(order):
            result = result.diff()

        # Seasonal differencing
        if seasonal_period:
            result = result.diff(seasonal_period)

        return result.dropna()

    @staticmethod
    def find_optimal_differencing(
        data: pd.Series,
        max_order: int = 2,
        significance_level: float = 0.05
    ) -> Dict[str, Any]:
        """
        Find optimal differencing order to achieve stationarity

        Args:
            data: Time series data
            max_order: Maximum differencing order to try
            significance_level: Significance level for stationarity tests

        Returns:
            {
                "optimal_order": int,
                "is_stationary_after": bool,
                "adf_pvalue": float
            }
        """
        for order in range(max_order + 1):
            if order == 0:
                test_data = data
            else:
                test_data = TimeSeriesUtils.difference_data(data, order=order)

            if len(test_data) < 20:
                continue

            stationarity_result = TimeSeriesUtils.test_stationarity(
                test_data,
                significance_level
            )

            if stationarity_result.get("is_stationary", False):
                return {
                    "optimal_order": order,
                    "is_stationary_after": True,
                    "adf_pvalue": stationarity_result.get("adf_pvalue", 1.0),
                    "recommendation": f"Apply {order}-order differencing"
                }

        # If no order achieved stationarity
        return {
            "optimal_order": 1,
            "is_stationary_after": False,
            "adf_pvalue": 1.0,
            "recommendation": "Could not achieve stationarity with differencing. Use Prophet/XGBoost."
        }

    @staticmethod
    def detect_seasonality(
        data: pd.Series,
        freq: int = 7
    ) -> Dict[str, Any]:
        """
        Detect seasonality in time series

        Args:
            data: Time series data
            freq: Expected seasonal frequency (e.g., 7 for weekly)

        Returns:
            {
                "has_seasonality": bool,
                "seasonal_strength": float,  # 0-1
                "trend_strength": float,  # 0-1
                "seasonal_period": int
            }
        """
        if len(data) < 2 * freq:
            return {
                "has_seasonality": False,
                "seasonal_strength": 0.0,
                "trend_strength": 0.0,
                "seasonal_period": freq,
                "error": f"Insufficient data for seasonality detection (need >= {2*freq} points)"
            }

        try:
            # Seasonal decomposition
            decomposition = seasonal_decompose(
                data.dropna(),
                model='additive',
                period=freq,
                extrapolate_trend='freq'
            )

            # Calculate strength of seasonality
            seasonal_var = np.var(decomposition.seasonal)
            residual_var = np.var(decomposition.resid.dropna())
            seasonal_strength = seasonal_var / (seasonal_var + residual_var)

            # Calculate strength of trend
            trend_var = np.var(decomposition.trend.dropna())
            trend_strength = trend_var / (trend_var + residual_var)

            return {
                "has_seasonality": seasonal_strength > 0.3,  # Threshold
                "seasonal_strength": round(float(seasonal_strength), 3),
                "trend_strength": round(float(trend_strength), 3),
                "seasonal_period": freq
            }

        except Exception as e:
            logger.error(f"Seasonality detection failed: {e}")
            return {
                "has_seasonality": False,
                "seasonal_strength": 0.0,
                "trend_strength": 0.0,
                "seasonal_period": freq,
                "error": str(e)
            }

    @staticmethod
    def get_acf_pacf(
        data: pd.Series,
        nlags: int = 20
    ) -> Dict[str, Any]:
        """
        Calculate ACF and PACF for ARIMA order selection

        ACF (Autocorrelation Function): Correlation with lagged values
        PACF (Partial ACF): Correlation after removing effects of shorter lags

        Use for determining (p, q) in ARIMA(p, d, q):
        - p (AR order): Number of significant PACF lags
        - q (MA order): Number of significant ACF lags

        Args:
            data: Time series data
            nlags: Number of lags to calculate

        Returns:
            {
                "acf_values": List[float],
                "pacf_values": List[float],
                "suggested_p": int,  # AR order
                "suggested_q": int   # MA order
            }
        """
        if len(data) < nlags + 5:
            nlags = max(1, len(data) // 2)

        try:
            # Calculate ACF and PACF
            acf_values = acf(data.dropna(), nlags=nlags)
            pacf_values = pacf(data.dropna(), nlags=nlags)

            # Find significant lags (outside confidence interval)
            # Confidence interval: ±1.96/sqrt(n)
            n = len(data.dropna())
            conf_interval = 1.96 / np.sqrt(n)

            # Suggested p (AR order): first significant PACF lag
            suggested_p = 0
            for i in range(1, len(pacf_values)):
                if abs(pacf_values[i]) > conf_interval:
                    suggested_p = i
                    break

            # Suggested q (MA order): first significant ACF lag
            suggested_q = 0
            for i in range(1, len(acf_values)):
                if abs(acf_values[i]) > conf_interval:
                    suggested_q = i
                    break

            return {
                "acf_values": [round(float(v), 3) for v in acf_values[:min(10, len(acf_values))]],
                "pacf_values": [round(float(v), 3) for v in pacf_values[:min(10, len(pacf_values))]],
                "suggested_p": suggested_p,
                "suggested_q": suggested_q,
                "confidence_interval": round(conf_interval, 3)
            }

        except Exception as e:
            logger.error(f"ACF/PACF calculation failed: {e}")
            return {
                "acf_values": [],
                "pacf_values": [],
                "suggested_p": 1,
                "suggested_q": 1,
                "error": str(e)
            }

    @staticmethod
    def recommend_sarima_order(
        data: pd.Series,
        seasonal_period: int = 7
    ) -> Dict[str, Any]:
        """
        Recommend SARIMA(p,d,q)(P,D,Q,s) order

        Args:
            data: Time series data
            seasonal_period: Seasonal period (default 7 for weekly)

        Returns:
            {
                "order": (p, d, q),
                "seasonal_order": (P, D, Q, s),
                "is_suitable": bool,
                "reason": str
            }
        """
        # Test stationarity
        stationarity = TimeSeriesUtils.test_stationarity(data)

        if not stationarity.get("is_stationary", False):
            # Find optimal differencing
            diff_result = TimeSeriesUtils.find_optimal_differencing(data)
            d = diff_result["optimal_order"]
            differenced_data = TimeSeriesUtils.difference_data(data, order=d)
        else:
            d = 0
            differenced_data = data

        # Get ACF/PACF for AR and MA orders
        acf_pacf = TimeSeriesUtils.get_acf_pacf(differenced_data)
        p = min(acf_pacf["suggested_p"], 3)  # Cap at 3 for efficiency
        q = min(acf_pacf["suggested_q"], 3)

        # Detect seasonality
        seasonality = TimeSeriesUtils.detect_seasonality(data, freq=seasonal_period)

        if seasonality["has_seasonality"]:
            # Seasonal ARIMA parameters (typically keep simple)
            P, D, Q = 1, 1, 1
            s = seasonal_period
        else:
            P, D, Q, s = 0, 0, 0, 0

        # Check if SARIMA is suitable
        is_suitable = len(data) >= 60  # Need at least 60 days for SARIMA

        if not is_suitable:
            reason = f"Insufficient data for SARIMA (need >= 60 points, got {len(data)})"
        elif not stationarity.get("is_stationary", False) and d == 0:
            is_suitable = False
            reason = "Could not achieve stationarity. Use Prophet/XGBoost instead."
        else:
            reason = "SARIMA suitable for this data"

        return {
            "order": (p, d, q),
            "seasonal_order": (P, D, Q, s),
            "is_suitable": is_suitable,
            "reason": reason,
            "data_length": len(data),
            "stationarity": stationarity.get("overall_conclusion", "Unknown"),
            "seasonality_strength": seasonality.get("seasonal_strength", 0.0)
        }


# Singleton instance
_time_series_utils: Optional[TimeSeriesUtils] = None


def get_time_series_utils() -> TimeSeriesUtils:
    """Get singleton time series utils instance"""
    global _time_series_utils
    if _time_series_utils is None:
        _time_series_utils = TimeSeriesUtils()
    return _time_series_utils
