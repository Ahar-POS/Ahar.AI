import logging
from typing import Optional, List, Dict

from app.utils.timezone import now_ist
from app.core.database import get_database

logger = logging.getLogger(__name__)


class PromotionService:
    def __init__(self):
        self.db = get_database()

    async def get_active_promotions(self, restaurant_id: str) -> List[Dict]:
        """Returns all promotions where status='active' AND start_date <= today <= end_date."""
        today_str = now_ist().strftime("%Y-%m-%d")
        try:
            cursor = self.db.promotions.find({
                "restaurant_id": restaurant_id,
                "status": "active",
                "start_date": {"$lte": today_str},
                "end_date": {"$gte": today_str},
            })
            promos = await cursor.to_list(length=50)
            
            # Convert ObjectId to string for JSON serialization
            for p in promos:
                if "_id" in p:
                    p["id"] = str(p.pop("_id"))
            return promos
        except Exception as e:
            logger.error(f"Error fetching active promotions: {e}")
            return []

    async def get_active_promo_for_item(self, menu_item_id: str, restaurant_id: str) -> Optional[Dict]:
        """Returns highest-discount active promotion for a specific menu item."""
        promos = await self.get_active_promotions(restaurant_id)
        matching = [p for p in promos if menu_item_id in p.get("menu_item_ids_array", [])]
        return max(matching, key=lambda p: p.get("discount_pct", 0)) if matching else None


_promotion_service: Optional[PromotionService] = None


def get_promotion_service() -> PromotionService:
    global _promotion_service
    if _promotion_service is None:
        _promotion_service = PromotionService()
    return _promotion_service
