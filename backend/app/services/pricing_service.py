"""
Pricing Service

The single source of truth for ingredient prices across Ahar.AI.

Every other service — chatbot, agents, dashboard, profit analysis,
shopping list — reads prices through this module so that all surfaces
display the same number.

Public API:
    await get_current_price(material_id) -> int           # paise per base unit
    await get_price_at(material_id, as_of) -> int         # historical lookup
    await record_price(material_id, paise, source, ...)   # write a cost_history entry
    await get_current_price_info(material_id) -> dict     # {price_paise_per_base, base_unit, source}

Resolution order for `get_current_price`:
    1. Latest entry in `cost_history` collection (any source)
    2. HyperPure mock catalogue
    3. Legacy `raw_material_inventory.unit_cost_inr` cache (deprecated path,
       kept while consumers are being migrated)

`get_price_at` reads cost_history only (with HyperPure as fallback when no
entry covers the requested date — typical for newly added materials).

A small in-process TTL cache avoids hammering Mongo when many requests for
the same material come in within a short window. Cache is invalidated when
`record_price` is called.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from app.core.database import get_database
from app.repositories.cost_history_repository import get_cost_history_repository
from app.services.hyperpure_client import get_hyperpure_client
from app.utils.timezone import now_ist


logger = logging.getLogger(__name__)


_CACHE_TTL_SECONDS = 60.0


class PricingService:
    """Resolves ingredient prices through cost_history → HyperPure → legacy."""

    def __init__(self):
        self._cost_history = get_cost_history_repository()
        self._hp = get_hyperpure_client()
        # cache: material_id -> (expires_at_monotonic, info_dict)
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_current_price(self, material_id: str) -> Optional[int]:
        """Paise per base unit, latest known. None if not catalogued anywhere."""
        info = await self.get_current_price_info(material_id)
        return info["price_paise_per_base"] if info else None

    async def get_current_price_info(
        self, material_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Returns {price_paise_per_base, base_unit, source} or None.
        `source` is one of: "cost_history" | "hyperpure" | "inventory_cache".
        """
        cached = self._cache.get(material_id)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        # 1. cost_history (most recent entry)
        latest = await self._cost_history.get_current(material_id)
        if latest:
            info = {
                "price_paise_per_base": int(latest["price_paise_per_base"]),
                "base_unit": latest["base_unit"],
                "source": "cost_history",
                "underlying_source": latest.get("source"),
                "effective_date": latest.get("effective_date"),
            }
            self._cache_set(material_id, info)
            return info

        # 2. HyperPure mock catalogue
        hp_info = self._hp.get_price_info(material_id)
        if hp_info:
            info = {
                "price_paise_per_base": int(hp_info["price_paise_per_base"]),
                "base_unit": hp_info["base_unit"],
                "source": "hyperpure",
            }
            self._cache_set(material_id, info)
            return info

        # 3. Legacy inventory cache (deprecated)
        legacy = await self._read_legacy_inventory_cache(material_id)
        if legacy:
            self._cache_set(material_id, legacy)
            return legacy

        return None

    async def get_price_at(
        self, material_id: str, as_of: datetime
    ) -> Optional[int]:
        """Paise per base unit on the given date. None if unknown."""
        info = await self.get_price_at_info(material_id, as_of)
        return info["price_paise_per_base"] if info else None

    async def get_price_at_info(
        self, material_id: str, as_of: datetime
    ) -> Optional[Dict[str, Any]]:
        doc = await self._cost_history.get_price_at(material_id, as_of)
        if doc:
            return {
                "price_paise_per_base": int(doc["price_paise_per_base"]),
                "base_unit": doc["base_unit"],
                "source": "cost_history",
                "underlying_source": doc.get("source"),
                "effective_date": doc.get("effective_date"),
            }

        # Fallback: no history at or before that date — use HyperPure mock so
        # callers don't crash on freshly added materials.
        hp_info = self._hp.get_price_info(material_id)
        if hp_info:
            return {
                "price_paise_per_base": int(hp_info["price_paise_per_base"]),
                "base_unit": hp_info["base_unit"],
                "source": "hyperpure",
            }
        return None

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def record_price(
        self,
        material_id: str,
        price_paise_per_base: int,
        source: str,
        base_unit: Optional[str] = None,
        effective_date: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Append a cost_history entry. If `base_unit` is omitted we fall back to
        HyperPure's catalogue or the previous cost_history entry to keep units
        consistent across entries for the same material.
        """
        if base_unit is None:
            base_unit = await self._infer_base_unit(material_id)
            if base_unit is None:
                raise ValueError(
                    f"Cannot record price for unknown material {material_id} "
                    "— pass base_unit explicitly."
                )

        inserted_id = await self._cost_history.insert(
            material_id=material_id,
            price_paise_per_base=int(price_paise_per_base),
            base_unit=base_unit,
            source=source,
            effective_date=effective_date or now_ist(),
            metadata=metadata,
        )

        # Invalidate cache for this material so next read picks up the new value.
        self._cache.pop(material_id, None)
        return inserted_id

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _cache_set(self, material_id: str, info: Dict[str, Any]) -> None:
        self._cache[material_id] = (time.monotonic() + _CACHE_TTL_SECONDS, info)

    def invalidate(self, material_id: Optional[str] = None) -> None:
        if material_id is None:
            self._cache.clear()
        else:
            self._cache.pop(material_id, None)

    async def _infer_base_unit(self, material_id: str) -> Optional[str]:
        latest = await self._cost_history.get_current(material_id)
        if latest:
            return latest.get("base_unit")
        hp_info = self._hp.get_price_info(material_id)
        if hp_info:
            return hp_info.get("base_unit")
        # Last resort: read inventory record's `unit` field.
        try:
            db = get_database()
            doc = await db["raw_material_inventory"].find_one(
                {"material_id": material_id}, {"unit": 1}
            )
            if doc and doc.get("unit"):
                return _normalize_unit(doc["unit"])
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not infer base_unit for %s: %s", material_id, exc)
        return None

    async def _read_legacy_inventory_cache(
        self, material_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            db = get_database()
            doc = await db["raw_material_inventory"].find_one(
                {"material_id": material_id},
                {"unit_cost_inr": 1, "unit": 1},
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("legacy inventory read failed for %s: %s", material_id, exc)
            return None
        if not doc or doc.get("unit_cost_inr") is None:
            return None
        return {
            "price_paise_per_base": int(doc["unit_cost_inr"]),
            "base_unit": _normalize_unit(doc.get("unit") or "gram"),
            "source": "inventory_cache",
        }


def _normalize_unit(unit: str) -> str:
    """CSV uses 'Gram', 'ML', 'Piece', 'Portion' — normalise to lowercase."""
    if not unit:
        return "gram"
    u = unit.strip().lower()
    if u in {"g", "gram", "grams"}:
        return "gram"
    if u in {"ml", "millilitre", "milliliter"}:
        return "ml"
    if u in {"piece", "pieces", "pc", "pcs"}:
        return "piece"
    if u in {"portion", "portions"}:
        return "portion"
    return u


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_pricing_service: Optional[PricingService] = None


def get_pricing_service() -> PricingService:
    global _pricing_service
    if _pricing_service is None:
        _pricing_service = PricingService()
    return _pricing_service
