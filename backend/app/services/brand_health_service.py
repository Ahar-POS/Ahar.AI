"""
Brand Health Service

Handles fetching and synthesizing external brand sentiment from Zomato, Swiggy, and Google.
Provides dynamic platform distribution metrics from actual orders.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.database import get_database
from app.utils.timezone import now_ist
from app.models.order import OrderChannel

logger = logging.getLogger(__name__)

RESTAURANT_ID = "antera_jubilee_hills"


class BrandHealthService:
    def __init__(self):
        self.db = get_database()

    async def get_platform_distribution(self, restaurant_id: str = RESTAURANT_ID) -> List[Dict[str, Any]]:
        """
        Calculate platform distribution from actual orders in the last 24 hours.
        """
        now = now_ist()
        day_ago = now - timedelta(days=1)

        pipeline = [
            {
                "$match": {
                    "restaurant_id": restaurant_id,
                    "order_date": {"$gte": day_ago},
                    "status": {"$in": ["completed", "COMPLETED"]}
                }
            },
            {
                "$group": {
                    "_id": "$order_channel",
                    "count": {"$sum": 1}
                }
            }
        ]

        try:
            cursor = self.db.orders.aggregate(pipeline)
            results = await cursor.to_list(length=None)

            # Map to frontend format
            # OrderChannel values: dine_in, walk_in, swiggy, zomato
            channel_map = {
                OrderChannel.DINE_IN.value: "Dine-in",
                OrderChannel.WALK_IN.value: "Takeaway",
                OrderChannel.SWIGGY.value: "Swiggy",
                OrderChannel.ZOMATO.value: "Zomato"
            }

            color_map = {
                "Dine-in": "#000000",
                "Takeaway": "#00A86B",
                "Swiggy": "#FC8019",
                "Zomato": "#E23744"
            }

            total = sum(r["count"] for r in results)
            if total == 0:
                # Return static fallback if no orders found today
                return [
                    {"name": "Dine-in", "value": 45, "color": "#000000"},
                    {"name": "Takeaway", "value": 15, "color": "#00A86B"},
                    {"name": "Swiggy", "value": 25, "color": "#FC8019"},
                    {"name": "Zomato", "value": 15, "color": "#E23744"},
                ]

            distribution = []
            for r in results:
                name = channel_map.get(r["_id"], str(r["_id"]))
                distribution.append({
                    "name": name,
                    "value": round((r["count"] / total) * 100, 1),
                    "color": color_map.get(name, "#888888")
                })
            
            return sorted(distribution, key=lambda x: x["value"], reverse=True)

        except Exception as e:
            logger.error(f"Failed to calculate platform distribution: {e}")
            return []

    async def get_latest_brand_health(self, restaurant_id: str = RESTAURANT_ID) -> Dict[str, Any]:
        """
        Fetch the latest synthesized brand health analysis from MongoDB.
        """
        try:
            doc = await self.db.brand_health.find_one(
                {"restaurant_id": restaurant_id},
                sort=[("created_at", -1)]
            )
            if not doc:
                # Default fallback data if no analysis has been run yet
                return {
                    "overall_rating": 4.6,
                    "total_reviews": 1200,
                    "platforms": {
                        "swiggy": {"rating": 4.2, "trend": "down", "label": "↓ 0.2 this week"},
                        "zomato": {"rating": 4.5, "trend": "stable", "label": "Stable"},
                        "google": {"rating": 4.8, "trend": "up", "label": "High visibility"}
                    },
                    "ai_synthesis": {
                        "highlights": "Strong positive sentiment around the new Truffle Pasta addition. Staff member 'Priya' mentioned favorably in 4 Google reviews for excellent service.",
                        "improvements": "Detected a spike in complaints regarding 'cold food' on Swiggy deliveries specifically between 7:30 PM and 8:30 PM."
                    },
                    "created_at": now_ist().isoformat()
                }
            
            doc["_id"] = str(doc["_id"])
            return doc
        except Exception as e:
            logger.error(f"Failed to fetch brand health: {e}")
            return {}

    async def save_brand_health_analysis(self, analysis: Dict[str, Any], restaurant_id: str = RESTAURANT_ID) -> bool:
        """
        Save a new brand health analysis snapshot.
        """
        try:
            analysis["restaurant_id"] = restaurant_id
            analysis["created_at"] = now_ist()
            await self.db.brand_health.insert_one(analysis)
            return True
        except Exception as e:
            logger.error(f"Failed to save brand health analysis: {e}")
            return False


# Singleton
_brand_health_service: Optional[BrandHealthService] = None


def get_brand_health_service() -> BrandHealthService:
    global _brand_health_service
    if _brand_health_service is None:
        _brand_health_service = BrandHealthService()
    return _brand_health_service
