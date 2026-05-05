"""Repository for agent_decisions — read-only, chatbot tool backing."""

from datetime import datetime
from typing import List, Dict, Any

from app.core.database import get_database


class AgentDecisionRepository:
    def __init__(self):
        self.db = None

    def _get_db(self):
        if self.db is None:
            self.db = get_database()
        return self.db

    async def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent agent decisions, newest first."""
        db = self._get_db()
        cursor = db.agent_decisions.find({}).sort("timestamp", -1).limit(limit)
        docs = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            if isinstance(doc.get("timestamp"), datetime):
                doc["timestamp"] = doc["timestamp"].isoformat()
            docs.append(doc)
        return docs


agent_decision_repository = AgentDecisionRepository()
