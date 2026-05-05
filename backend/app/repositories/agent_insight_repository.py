"""Repository for agent_insights — chatbot hydration only."""

from typing import Optional, Dict, Any
from bson import ObjectId

from app.core.database import get_database


class AgentInsightRepository:
    def __init__(self):
        self.db = None

    def _get_db(self):
        if self.db is None:
            self.db = get_database()
        return self.db

    async def get_by_id(self, insight_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single insight by its string ObjectId."""
        db = self._get_db()
        try:
            doc = await db.agent_insights.find_one({"_id": ObjectId(insight_id)})
        except Exception:
            return None
        if not doc:
            return None
        doc["id"] = str(doc.pop("_id"))
        return doc


agent_insight_repository = AgentInsightRepository()
