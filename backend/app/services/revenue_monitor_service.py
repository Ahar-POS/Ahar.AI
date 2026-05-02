"""
Revenue Monitor Service — thin shim for backward compatibility.

Logic has moved to OperationsPulseService. This shim keeps any external
callers (tests, scripts) working without changes.
"""
from app.services.operations_pulse_service import OperationsPulseService, get_operations_pulse
from typing import Optional, Dict, Any


class RevenueMonitorService:
    """Deprecated: delegates to OperationsPulseService._check_revenue_anomaly."""

    async def check_hourly_revenue(self) -> Optional[Dict[str, Any]]:
        await get_operations_pulse()._check_revenue_anomaly("antera_jubilee_hills")
        return None  # event is published on the bus; callers that checked return value should migrate


def get_revenue_monitor() -> RevenueMonitorService:
    return RevenueMonitorService()
