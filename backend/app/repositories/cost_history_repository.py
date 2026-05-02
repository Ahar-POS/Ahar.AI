"""
Cost History Repository

Stores historical price points for raw materials so profit analysis can ask
"what did this ingredient cost on date D?" rather than always reading today's
price. Each entry is keyed by material_id and effective_date.

Schema:
    {
        "_id": ObjectId,
        "material_id": str,                  # e.g. "RM019"
        "price_paise_per_base": int,         # paise per base unit (gram/ml/piece)
        "base_unit": str,                    # "gram" | "ml" | "piece" | "portion"
        "effective_date": datetime,          # when this price became effective (IST)
        "source": str,                       # "hyperpure" | "bill" | "manual" | "seed"
        "recorded_at": datetime,             # when the entry was written
        "metadata": dict,                    # optional: bill_id, po_id, etc.
    }
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from app.core.database import get_database
from app.utils.timezone import now_ist


VALID_SOURCES = {"hyperpure", "bill", "manual", "seed"}


class CostHistoryRepository:
    """Repository for cost_history collection."""

    def __init__(self):
        self.db = None
        self.collection_name = "cost_history"

    def _get_collection(self):
        if self.db is None:
            self.db = get_database()
        return self.db[self.collection_name]

    async def ensure_indexes(self) -> None:
        """Create the indexes needed for fast lookups. Idempotent."""
        collection = self._get_collection()
        await collection.create_index(
            [("material_id", 1), ("effective_date", -1)],
            name="material_effective_desc",
        )
        await collection.create_index(
            [("material_id", 1), ("effective_date", 1), ("source", 1)],
            unique=True,
            name="material_effective_source_unique",
        )

    async def insert(
        self,
        material_id: str,
        price_paise_per_base: int,
        base_unit: str,
        source: str,
        effective_date: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Insert one cost history entry. Returns inserted ObjectId as string."""
        if source not in VALID_SOURCES:
            raise ValueError(f"source must be one of {VALID_SOURCES}, got {source!r}")

        doc = {
            "material_id": material_id,
            "price_paise_per_base": int(price_paise_per_base),
            "base_unit": base_unit,
            "source": source,
            "effective_date": effective_date or now_ist(),
            "recorded_at": now_ist(),
            "metadata": metadata or {},
        }

        collection = self._get_collection()
        result = await collection.insert_one(doc)
        return str(result.inserted_id)

    async def bulk_insert(self, entries: List[Dict[str, Any]]) -> int:
        """Insert many entries at once. Returns count inserted."""
        if not entries:
            return 0

        now = now_ist()
        prepared = []
        for e in entries:
            source = e.get("source", "manual")
            if source not in VALID_SOURCES:
                raise ValueError(f"source must be one of {VALID_SOURCES}, got {source!r}")
            prepared.append({
                "material_id": e["material_id"],
                "price_paise_per_base": int(e["price_paise_per_base"]),
                "base_unit": e["base_unit"],
                "source": source,
                "effective_date": e.get("effective_date") or now,
                "recorded_at": now,
                "metadata": e.get("metadata") or {},
            })

        collection = self._get_collection()
        result = await collection.insert_many(prepared, ordered=False)
        return len(result.inserted_ids)

    async def get_price_at(
        self, material_id: str, as_of: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Latest cost_history entry with effective_date <= as_of.
        Returns the document (with `price_paise_per_base`, `base_unit`, etc.)
        or None if no entry exists at or before that date.
        """
        collection = self._get_collection()
        doc = await collection.find_one(
            {
                "material_id": material_id,
                "effective_date": {"$lte": as_of},
            },
            sort=[("effective_date", -1)],
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_current(self, material_id: str) -> Optional[Dict[str, Any]]:
        """Most recent cost_history entry for a material, regardless of effective_date."""
        collection = self._get_collection()
        doc = await collection.find_one(
            {"material_id": material_id},
            sort=[("effective_date", -1)],
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_series(
        self,
        material_id: str,
        since: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """All cost_history entries for a material, newest first."""
        collection = self._get_collection()
        query: Dict[str, Any] = {"material_id": material_id}
        if since is not None:
            query["effective_date"] = {"$gte": since}
        cursor = collection.find(query).sort("effective_date", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    async def delete_by_source(self, source: str) -> int:
        """
        Delete all entries with the given source. Used by seed scripts to reset
        their own data without touching real bill / hyperpure / manual entries.
        Returns deleted count.
        """
        if source not in VALID_SOURCES:
            raise ValueError(f"source must be one of {VALID_SOURCES}, got {source!r}")
        collection = self._get_collection()
        result = await collection.delete_many({"source": source})
        return result.deleted_count


# Singleton
_cost_history_repository: Optional[CostHistoryRepository] = None


def get_cost_history_repository() -> CostHistoryRepository:
    """Get singleton CostHistoryRepository instance."""
    global _cost_history_repository
    if _cost_history_repository is None:
        _cost_history_repository = CostHistoryRepository()
    return _cost_history_repository
