"""
Analytics aggregator service for preparing MongoDB data for AI analysis.

Aggregates data from multiple collections into pandas DataFrames ready for
CSV export and AI analysis via Skills API.
"""

from datetime import datetime, timedelta
from typing import Dict, Any
import pandas as pd

from app.core.database import get_database
from app.repositories.inventory_repository import inventory_repository


class AnalyticsAggregator:
    """Aggregate MongoDB data for AI analysis"""

    def __init__(self):
        self.db = None

    def _get_database(self):
        """Get database instance"""
        if self.db is None:
            self.db = get_database()
        return self.db

    async def aggregate_financial_data(
        self,
        start_date: str,
        end_date: str,
        restaurant_id: str = "default"
    ) -> pd.DataFrame:
        """
        Aggregate financial metrics from orders collection.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            restaurant_id: Restaurant identifier for multi-tenancy

        Returns:
            DataFrame with columns:
            - order_id: Order identifier
            - order_number: Human-readable order number
            - order_date: Order creation date
            - order_time: Order creation time
            - order_type: DINE_IN or TAKEAWAY
            - table_id: Table identifier (if dine-in)
            - status: Order status
            - total_amount: Total amount in paise
            - items_count: Number of items in order
            - created_by_user_id: Staff who created the order
            - kitchen_time_mins: Time from creation to completion
            - is_cancelled: Boolean flag for cancelled orders
        """
        # Parse dates
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)  # Include end date

        # Query orders collection
        db = self._get_database()
        orders_collection = db.orders

        pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": start_dt, "$lt": end_dt},
                }
            },
            {
                "$project": {
                    "order_id": {"$toString": "$_id"},
                    "order_number": 1,
                    "order_date": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$created_at"
                        }
                    },
                    "order_time": {
                        "$dateToString": {
                            "format": "%H:%M:%S",
                            "date": "$created_at"
                        }
                    },
                    "order_type": 1,
                    "table_id": {"$ifNull": ["$table_id", ""]},
                    "status": 1,
                    "total_amount": 1,
                    "items_count": {"$size": "$items"},
                    "created_by_user_id": 1,
                    "created_at": 1,
                    "completed_at": 1,
                    "is_cancelled": {"$eq": ["$status", "CANCELLED"]}
                }
            },
            {
                "$addFields": {
                    "kitchen_time_mins": {
                        "$cond": {
                            "if": {"$ne": ["$completed_at", None]},
                            "then": {
                                "$divide": [
                                    {"$subtract": ["$completed_at", "$created_at"]},
                                    60000  # Convert ms to minutes
                                ]
                            },
                            "else": None
                        }
                    }
                }
            }
        ]

        cursor = orders_collection.aggregate(pipeline)
        orders_data = await cursor.to_list(length=None)

        if not orders_data:
            # Return empty DataFrame with proper schema
            return pd.DataFrame(columns=[
                'order_id', 'order_number', 'order_date', 'order_time',
                'order_type', 'table_id', 'status', 'total_amount',
                'items_count', 'created_by_user_id', 'kitchen_time_mins',
                'is_cancelled'
            ])

        return pd.DataFrame(orders_data)

    async def aggregate_inventory_data(
        self,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Aggregate inventory metrics.

        Returns:
            DataFrame with columns:
            - material_id: Material identifier
            - material_name: Material name
            - category: Inventory category
            - current_stock: Current stock level
            - max_stock: Maximum capacity
            - reorder_level: Reorder threshold
            - unit_cost_inr: Cost per unit in paise
            - is_perishable: Yes/No
            - shelf_life_days: Shelf life in days
            - storage_temp_c: Storage temperature requirement
            - days_to_expiry: Estimated days until expiry
            - is_low_stock: Boolean flag for low stock
            - stock_value: Total value of current stock
        """
        # Get all inventory items
        items = await inventory_repository.get_all(skip=0, limit=1000)

        if not items:
            return pd.DataFrame(columns=[
                'material_id', 'material_name', 'category', 'current_stock',
                'max_stock', 'reorder_level', 'unit_cost_inr', 'is_perishable',
                'shelf_life_days', 'storage_temp_c', 'days_to_expiry',
                'is_low_stock', 'stock_value'
            ])

        # Process items
        inventory_data = []
        for item in items:
            # Calculate days to expiry (rough estimate based on last restock)
            days_to_expiry = None
            if item.get('last_restock_date') and item.get('shelf_life_days'):
                try:
                    last_restock = datetime.fromisoformat(item['last_restock_date'])
                    days_since_restock = (datetime.utcnow() - last_restock).days
                    days_to_expiry = item['shelf_life_days'] - days_since_restock
                except:
                    pass

            inventory_data.append({
                'material_id': item['material_id'],
                'material_name': item['material_name'],
                'category': item['category'],
                'current_stock': item['current_stock'],
                'max_stock': item['max_stock'],
                'reorder_level': item['reorder_level'],
                'unit_cost_inr': item['unit_cost_inr'],
                'is_perishable': item['is_perishable'],
                'shelf_life_days': item['shelf_life_days'],
                'storage_temp_c': item['storage_temp_c'],
                'days_to_expiry': days_to_expiry,
                'is_low_stock': item['current_stock'] <= item['reorder_level'],
                'stock_value': item['current_stock'] * item['unit_cost_inr']
            })

        return pd.DataFrame(inventory_data)

    async def aggregate_operational_data(
        self,
        start_date: str,
        end_date: str,
        restaurant_id: str = "default"
    ) -> pd.DataFrame:
        """
        Aggregate operational metrics from orders, menu items, and tables.

        Returns:
            DataFrame with columns:
            - order_id: Order identifier
            - order_date: Order date
            - order_hour: Hour of day (0-23)
            - order_weekday: Day of week (0=Monday)
            - menu_item_name: Item name
            - menu_item_category: Item category
            - prep_type: Preparation type
            - quantity: Quantity ordered
            - kitchen_time_mins: Kitchen preparation time
            - item_status: Item status
            - staff_id: Staff member who created order
            - table_number: Table number (if dine-in)
        """
        # Parse dates
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)

        # Query orders with items
        db = self._get_database()
        orders_collection = db.orders

        pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": start_dt, "$lt": end_dt},
                    "status": {"$in": ["completed", "in_progress", "sent_to_kitchen"]}
                }
            },
            {
                "$unwind": "$items"  # Flatten items array
            },
            {
                "$project": {
                    "order_id": {"$toString": "$_id"},
                    "order_date": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$created_at"
                        }
                    },
                    "order_hour": {"$hour": "$created_at"},
                    "order_weekday": {"$dayOfWeek": "$created_at"},
                    "menu_item_id": "$items.menu_item_id",
                    "menu_item_name": "$items.name_snapshot",
                    "quantity": "$items.quantity",
                    "item_status": "$items.status",
                    "staff_id": "$created_by_user_id",
                    "table_id": {"$ifNull": ["$table_id", ""]},
                    "created_at": 1,
                    "completed_at": 1
                }
            },
            {
                "$addFields": {
                    "kitchen_time_mins": {
                        "$cond": {
                            "if": {"$ne": ["$completed_at", None]},
                            "then": {
                                "$divide": [
                                    {"$subtract": ["$completed_at", "$created_at"]},
                                    60000
                                ]
                            },
                            "else": None
                        }
                    }
                }
            }
        ]

        cursor = orders_collection.aggregate(pipeline)
        operational_data = await cursor.to_list(length=None)

        if not operational_data:
            return pd.DataFrame(columns=[
                'order_id', 'order_date', 'order_hour', 'order_weekday',
                'menu_item_id', 'menu_item_name', 'quantity', 'item_status',
                'staff_id', 'table_id', 'kitchen_time_mins'
            ])

        # Get menu items to enrich with category and prep_type
        menu_items_cursor = db.menu_items.find({"is_active": True})
        menu_items = await menu_items_cursor.to_list(length=None)
        menu_lookup = {str(item['_id']): item for item in menu_items}

        # Enrich operational data with menu details
        for record in operational_data:
            menu_item_id = record.get('menu_item_id', '')
            menu_item = menu_lookup.get(menu_item_id, {})
            record['menu_item_category'] = menu_item.get('category', 'Unknown')
            record['prep_type'] = menu_item.get('prep_type', 'Unknown')

        return pd.DataFrame(operational_data)

    async def aggregate_all_data(
        self,
        start_date: str,
        end_date: str,
        scope: list = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Aggregate all data types for comprehensive analysis.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            scope: List of scopes to aggregate (financial, inventory, operational)

        Returns:
            Dictionary with DataFrames:
            {
                'financial': financial_df,
                'inventory': inventory_df,
                'operational': operational_df
            }
        """
        if scope is None:
            scope = ['financial', 'inventory', 'operational']

        result = {}

        if 'financial' in scope:
            result['financial'] = await self.aggregate_financial_data(start_date, end_date)

        if 'inventory' in scope:
            result['inventory'] = await self.aggregate_inventory_data(start_date, end_date)

        if 'operational' in scope:
            result['operational'] = await self.aggregate_operational_data(start_date, end_date)

        return result


# Singleton instance
analytics_aggregator = AnalyticsAggregator()
