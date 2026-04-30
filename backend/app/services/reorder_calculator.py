"""
Reorder Calculator — dynamic safety-stock formulas.

All three public functions are pure maths: no I/O, easy to unit-test.
Used by inventory_agent.py to replace static reorder_level/reorder_qty fields.
"""
import math


def compute_dynamic_reorder_level(
    avg_daily_demand: float,
    demand_std_dev: float,
    lead_time_days: float,
    service_level_z: float = 1.65,
) -> float:
    """
    Reorder point = (avg_daily_demand × lead_time) + safety_stock
    Safety stock  = Z × σ_demand × √lead_time

    Z=1.65 → 95% in-stock service level (default).
    Returns 0.0 for degenerate inputs.
    """
    if avg_daily_demand <= 0 or lead_time_days <= 0:
        return 0.0
    safety_stock = service_level_z * demand_std_dev * math.sqrt(lead_time_days)
    return avg_daily_demand * lead_time_days + safety_stock


def compute_order_quantity(
    avg_daily_demand: float,
    demand_std_dev: float,
    lead_time_days: float,
    current_stock: float,
    is_perishable: bool,
    restock_horizon_days: float = 7.0,
    shelf_life_days: float = None,
) -> float:
    """
    How much to order today so we reach target stock.

    target = demand over (lead_time + restock_horizon) + safety_stock
    order  = max(0, target - current_stock)

    For perishables, cap at min(shelf_life_days, restock_horizon_days) × avg_daily_demand
    so we never order more than we can consume before the item expires.
    """
    if avg_daily_demand <= 0:
        return 0.0

    safety_stock = 1.65 * demand_std_dev * math.sqrt(max(lead_time_days, 1.0))
    target = avg_daily_demand * (lead_time_days + restock_horizon_days) + safety_stock

    if is_perishable:
        usable_days = (
            min(restock_horizon_days, float(shelf_life_days))
            if shelf_life_days and shelf_life_days > 0
            else restock_horizon_days
        )
        max_perishable = current_stock + avg_daily_demand * usable_days
        target = min(target, max_perishable)

    quantity = max(0.0, target - current_stock)
    return round(quantity, 2)


def effective_reorder_level(
    avg_daily_demand: float,
    demand_std_dev: float,
    lead_time_days: float,
    static_reorder_level: float,
) -> float:
    """
    Return the higher of the dynamic safety-stock level and the
    manually-configured static floor, so we never reorder below the
    operator's hard minimum.
    """
    dynamic = compute_dynamic_reorder_level(avg_daily_demand, demand_std_dev, lead_time_days)
    return max(dynamic, float(static_reorder_level))
