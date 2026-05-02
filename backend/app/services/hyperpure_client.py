"""
Hyperpure Client

Abstract interface for placing orders on Hyperpure.

Hyperpure has no public API. The production implementation will use
browser automation (Playwright) to log into the Hyperpure website,
navigate the cart, and place orders programmatically.

This module provides:
- A stable Python interface (`HyperpureClient`) that the orchestrator calls.
- A mock implementation (`MockHyperpureClient`) that returns simulated
  responses for development and testing.
- A factory (`get_hyperpure_client()`) that returns the correct implementation
  based on the HYPERPURE_USE_MOCK env var.

Pricing contract:
  The canonical mock catalogue is `_MOCK_PRICES_BY_ID`, keyed by `material_id`
  (RM001..RM049). Each entry stores `price_paise_per_base` (integer paise per
  base unit) and `base_unit` ("gram" | "ml" | "piece" | "portion"). This is
  the single source of truth used by `pricing_service` for all read paths
  across the system.

  The legacy `get_prices()` method (returning rupees/kg floats keyed by
  material_id) is preserved so the inventory agent's anomaly check keeps
  working until it is migrated to the new helper.
"""

import logging
import os
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class HyperpureOrderResult:
    status: str
    order_id: Optional[str]
    confirmed_items: List[str]
    rejected_items: List[str]
    message: str


@dataclass
class HyperpureStatusResult:
    status: str
    order_id: str
    message: str


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class HyperpureClient:
    """Abstract Hyperpure ordering interface."""

    async def place_order(self, items: List[Dict[str, Any]]) -> HyperpureOrderResult:
        raise NotImplementedError

    async def check_order_status(self, order_id: str) -> HyperpureStatusResult:
        raise NotImplementedError

    async def get_prices(self, items: List[Dict[str, Any]]) -> Dict[str, float]:
        """Legacy: returns rupees per (kg|litre|unit) float, keyed by material_id."""
        raise NotImplementedError

    def get_price_paise_per_base(self, material_id: str) -> Optional[int]:
        """Canonical: integer paise per base unit (gram|ml|piece|portion). None if unknown."""
        raise NotImplementedError

    def get_price_info(self, material_id: str) -> Optional[Dict[str, Any]]:
        """Canonical: {price_paise_per_base, base_unit, name}. None if unknown."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Mock implementation
# ---------------------------------------------------------------------------

class MockHyperpureClient(HyperpureClient):
    """
    Simulates Hyperpure responses without browser automation.

    Behaviour controlled by HYPERPURE_MOCK_MODE env var:
      "full" (default) | "partial" | "rejected" | "error"
    """

    # Canonical price catalogue, keyed by material_id.
    # Prices are integer paise per BASE unit (gram/ml/piece/portion).
    # Realistic Indian wholesale prices (Bangalore, early 2026) — covers
    # every material in backend/new_test_data/raw_material_inventory.csv.
    _MOCK_PRICES_BY_ID: Dict[str, Dict[str, Any]] = {
        # Proteins (paise per gram)
        "RM001": {"price_paise_per_base": 22,  "base_unit": "gram",  "name": "Chicken (Whole)"},
        "RM002": {"price_paise_per_base": 28,  "base_unit": "gram",  "name": "Chicken (Boneless)"},
        "RM003": {"price_paise_per_base": 70,  "base_unit": "gram",  "name": "Mutton (Bone-in)"},
        "RM004": {"price_paise_per_base": 85,  "base_unit": "gram",  "name": "Mutton (Boneless)"},
        # Seafood
        "RM005": {"price_paise_per_base": 55,  "base_unit": "gram",  "name": "Prawns (Medium)"},
        "RM006": {"price_paise_per_base": 28,  "base_unit": "gram",  "name": "Fish (Rohu/Catla)"},
        # Grains & Rice
        "RM007": {"price_paise_per_base": 10,  "base_unit": "gram",  "name": "Basmati Rice"},
        "RM008": {"price_paise_per_base": 6,   "base_unit": "gram",  "name": "Sona Masoori Rice"},
        "RM009": {"price_paise_per_base": 4,   "base_unit": "gram",  "name": "Wheat Flour (Maida)"},
        "RM010": {"price_paise_per_base": 4,   "base_unit": "gram",  "name": "Whole Wheat Flour"},
        "RM011": {"price_paise_per_base": 8,   "base_unit": "gram",  "name": "Ragi Flour"},
        # Dairy
        "RM012": {"price_paise_per_base": 6,   "base_unit": "gram",  "name": "Curd (Yoghurt)"},
        "RM013": {"price_paise_per_base": 50,  "base_unit": "gram",  "name": "Butter"},
        "RM014": {"price_paise_per_base": 22,  "base_unit": "ml",    "name": "Fresh Cream"},
        "RM015": {"price_paise_per_base": 32,  "base_unit": "gram",  "name": "Paneer"},
        "RM016": {"price_paise_per_base": 6,   "base_unit": "ml",    "name": "Milk"},
        "RM017": {"price_paise_per_base": 700, "base_unit": "piece", "name": "Eggs"},
        # Vegetables
        "RM018": {"price_paise_per_base": 3,   "base_unit": "gram",  "name": "Onion"},
        "RM019": {"price_paise_per_base": 4,   "base_unit": "gram",  "name": "Tomato"},
        "RM020": {"price_paise_per_base": 6,   "base_unit": "gram",  "name": "Green Chilli"},
        "RM021": {"price_paise_per_base": 10,  "base_unit": "gram",  "name": "Ginger"},
        "RM022": {"price_paise_per_base": 13,  "base_unit": "gram",  "name": "Garlic"},
        "RM023": {"price_paise_per_base": 6,   "base_unit": "gram",  "name": "Capsicum"},
        "RM024": {"price_paise_per_base": 2,   "base_unit": "gram",  "name": "Coriander (Fresh)"},
        "RM025": {"price_paise_per_base": 3,   "base_unit": "gram",  "name": "Mint Leaves"},
        "RM026": {"price_paise_per_base": 800, "base_unit": "piece", "name": "Lemon"},
        "RM027": {"price_paise_per_base": 4,   "base_unit": "gram",  "name": "Brinjal (Vankaya)"},
        # Spices
        "RM028": {"price_paise_per_base": 60,  "base_unit": "gram",  "name": "Biryani Masala"},
        "RM029": {"price_paise_per_base": 30,  "base_unit": "gram",  "name": "Red Chilli Powder"},
        "RM030": {"price_paise_per_base": 22,  "base_unit": "gram",  "name": "Turmeric Powder"},
        "RM031": {"price_paise_per_base": 50,  "base_unit": "gram",  "name": "Garam Masala"},
        "RM032": {"price_paise_per_base": 18,  "base_unit": "gram",  "name": "Coriander Powder"},
        "RM033": {"price_paise_per_base": 35,  "base_unit": "gram",  "name": "Cumin Seeds"},
        "RM034": {"price_paise_per_base": 25,  "base_unit": "gram",  "name": "Bay Leaves"},
        "RM035": {"price_paise_per_base": 250, "base_unit": "gram",  "name": "Cardamom"},
        "RM036": {"price_paise_per_base": 3000,"base_unit": "gram",  "name": "Saffron"},
        # Oils & Fats
        "RM037": {"price_paise_per_base": 14,  "base_unit": "ml",    "name": "Cooking Oil (Sunflower)"},
        "RM038": {"price_paise_per_base": 60,  "base_unit": "gram",  "name": "Ghee"},
        # Bakery
        "RM039": {"price_paise_per_base": 6,   "base_unit": "gram",  "name": "Tandoor Dough"},
        # Beverages & sweet bases
        "RM040": {"price_paise_per_base": 5,   "base_unit": "gram",  "name": "Sugar"},
        "RM041": {"price_paise_per_base": 18,  "base_unit": "ml",    "name": "Rose Syrup"},
        "RM042": {"price_paise_per_base": 14,  "base_unit": "ml",    "name": "Mango Pulp"},
        # Condiments
        "RM043": {"price_paise_per_base": 12,  "base_unit": "gram",  "name": "Mirchi Ka Salan Base"},
        "RM044": {"price_paise_per_base": 8,   "base_unit": "gram",  "name": "Raita Base"},
        "RM045": {"price_paise_per_base": 200, "base_unit": "piece", "name": "Papadum"},
        # Packaging
        "RM046": {"price_paise_per_base": 1500,"base_unit": "piece", "name": "Biryani Container (Large)"},
        "RM047": {"price_paise_per_base": 800, "base_unit": "piece", "name": "Parcel Box (Medium)"},
        "RM048": {"price_paise_per_base": 200, "base_unit": "piece", "name": "Swiggy/Zomato Bag"},
        # Beverages (alcohol per portion)
        "RM049": {"price_paise_per_base": 15000,"base_unit": "portion","name": "Alcohol/Spirits (Generic)"},
        # Mocktails / mixers (added to cover live inventory ids beyond the CSV)
        "RM063": {"price_paise_per_base": 25,   "base_unit": "ml",     "name": "Ginger Ale"},          # ₹25/100ml
        "RM094": {"price_paise_per_base": 8000, "base_unit": "portion","name": "Virgin Mojito Mocktail Mix"},   # ₹80/portion
        "RM095": {"price_paise_per_base": 9000, "base_unit": "portion","name": "Virgin Pina Colada Mocktail Mix"},# ₹90/portion
    }

    # Conversion factor from base unit to "1 (kg|litre|unit)" — for legacy
    # rupees-per-(kg|L|piece) helpers.
    _BASE_TO_LARGE: Dict[str, int] = {
        "gram": 1000,    # 1000 g per kg
        "ml": 1000,      # 1000 ml per litre
        "piece": 1,
        "portion": 1,
    }

    # Built lazily from _MOCK_PRICES_BY_ID for fuzzy name lookups (legacy path).
    _NAME_INDEX: Optional[Dict[str, str]] = None

    def __init__(self):
        self.mock_mode = os.getenv("HYPERPURE_MOCK_MODE", "full")

    # ----- canonical helpers -----

    def get_price_paise_per_base(self, material_id: str) -> Optional[int]:
        info = self._MOCK_PRICES_BY_ID.get(material_id)
        return info["price_paise_per_base"] if info else None

    def get_price_info(self, material_id: str) -> Optional[Dict[str, Any]]:
        info = self._MOCK_PRICES_BY_ID.get(material_id)
        return dict(info) if info else None

    def list_catalogue(self) -> Dict[str, Dict[str, Any]]:
        """Full catalogue (deep-copy-safe). Used by seed scripts."""
        return {mid: dict(info) for mid, info in self._MOCK_PRICES_BY_ID.items()}

    # ----- legacy lookups (kept until callers migrate to pricing_service) -----

    @classmethod
    def _ensure_name_index(cls) -> Dict[str, str]:
        if cls._NAME_INDEX is None:
            cls._NAME_INDEX = {
                info["name"].lower().strip(): mid
                for mid, info in cls._MOCK_PRICES_BY_ID.items()
            }
        return cls._NAME_INDEX

    def _price_per_large_unit(self, material_id: str) -> Optional[float]:
        """Rupees per kg / litre / piece / portion (legacy contract)."""
        info = self._MOCK_PRICES_BY_ID.get(material_id)
        if not info:
            return None
        paise_per_base = info["price_paise_per_base"]
        factor = self._BASE_TO_LARGE.get(info["base_unit"], 1)
        # paise/base × bases/large ÷ 100 paise/rupee
        return round(paise_per_base * factor / 100.0, 2)

    def _lookup_price(self, material_name: str) -> Optional[float]:
        """Legacy fuzzy-by-name lookup → rupees per (kg|L|piece)."""
        if not material_name:
            return None
        index = self._ensure_name_index()
        key = material_name.lower().strip()
        if key in index:
            return self._price_per_large_unit(index[key])
        for cat_key, mid in index.items():
            if cat_key in key or key in cat_key:
                return self._price_per_large_unit(mid)
        return None

    # ----- order placement (unchanged behaviour) -----

    async def place_order(self, items: List[Dict[str, Any]]) -> HyperpureOrderResult:
        material_ids = [i["material_id"] for i in items]
        logger.info(
            f"[MockHyperpure] place_order called: {len(items)} items, "
            f"mode={self.mock_mode}"
        )

        if self.mock_mode == "error":
            return HyperpureOrderResult(
                status="error",
                order_id=None,
                confirmed_items=[],
                rejected_items=material_ids,
                message="Browser automation failed: Hyperpure website unreachable",
            )

        if self.mock_mode == "rejected":
            return HyperpureOrderResult(
                status="rejected",
                order_id=None,
                confirmed_items=[],
                rejected_items=material_ids,
                message="Order rejected by Hyperpure: minimum order value not met",
            )

        if self.mock_mode == "partial":
            split = max(1, len(material_ids) // 2)
            confirmed = material_ids[:split]
            rejected = material_ids[split:]
            order_id = f"HP-MOCK-{random.randint(100000, 999999)}"
            return HyperpureOrderResult(
                status="partial",
                order_id=order_id,
                confirmed_items=confirmed,
                rejected_items=rejected,
                message=(
                    f"Partial order accepted (Hyperpure ref: {order_id}). "
                    f"{len(rejected)} item(s) out of stock."
                ),
            )

        order_id = f"HP-MOCK-{random.randint(100000, 999999)}"
        return HyperpureOrderResult(
            status="confirmed",
            order_id=order_id,
            confirmed_items=material_ids,
            rejected_items=[],
            message=f"Order fully confirmed (Hyperpure ref: {order_id})",
        )

    async def check_order_status(self, order_id: str) -> HyperpureStatusResult:
        logger.info(f"[MockHyperpure] check_order_status: {order_id}")
        return HyperpureStatusResult(
            status="processing",
            order_id=order_id,
            message="Order is being processed by Hyperpure (mock response)",
        )

    async def get_prices(self, items: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Legacy contract — rupees per (kg|L|piece|portion) with ±10% jitter.
        New code should use pricing_service.get_current_price() instead.
        """
        prices: Dict[str, float] = {}
        for item in items:
            mid = item.get("material_id", "")
            base = self._price_per_large_unit(mid)
            if base is None:
                # Fall back to fuzzy name lookup for callers that pass only names
                base = self._lookup_price(item.get("material_name", ""))
            if base is not None:
                variance = random.uniform(0.90, 1.10)
                prices[mid] = round(base * variance, 2)
        return prices


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_hyperpure_client: Optional[HyperpureClient] = None


def get_hyperpure_client() -> HyperpureClient:
    """Return the Hyperpure client singleton."""
    global _hyperpure_client
    if _hyperpure_client is None:
        use_mock = os.getenv("HYPERPURE_USE_MOCK", "true").lower() != "false"
        if use_mock:
            _hyperpure_client = MockHyperpureClient()
            logger.info("HyperpureClient: using MOCK implementation")
        else:
            raise NotImplementedError(
                "Real Hyperpure Playwright client not yet implemented. "
                "Set HYPERPURE_USE_MOCK=true or implement PlaywrightHyperpureClient."
            )
    return _hyperpure_client
