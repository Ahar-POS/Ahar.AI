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

Response contract:
  place_order() returns a HyperpureOrderResult with:
    status:  "confirmed" | "partial" | "rejected" | "error"
    order_id: Hyperpure order reference (str, may be None on error)
    confirmed_items: list of material_ids that were accepted
    rejected_items:  list of material_ids that were rejected / OOS
    message:  human-readable outcome

  check_order_status() returns a HyperpureStatusResult with:
    status:  "processing" | "dispatched" | "delivered" | "cancelled" | "unknown"
    order_id: str
    message:  str
"""

import logging
import os
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class HyperpureOrderResult:
    status: str                          # confirmed | partial | rejected | error
    order_id: Optional[str]             # Hyperpure's reference number
    confirmed_items: List[str]          # material_ids accepted
    rejected_items: List[str]           # material_ids rejected / OOS
    message: str


@dataclass
class HyperpureStatusResult:
    status: str                          # processing | dispatched | delivered | cancelled | unknown
    order_id: str
    message: str


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class HyperpureClient:
    """
    Abstract Hyperpure ordering interface.

    Both the mock and the future Playwright implementation satisfy this
    interface. The orchestrator should depend only on this class.
    """

    async def place_order(self, items: List[Dict[str, Any]]) -> HyperpureOrderResult:
        """
        Place an order on Hyperpure.

        Args:
            items: List of dicts, each with at minimum:
                   material_id, material_name, quantity_to_order, unit, supplier_id

        Returns:
            HyperpureOrderResult
        """
        raise NotImplementedError

    async def check_order_status(self, order_id: str) -> HyperpureStatusResult:
        """
        Check the status of a previously placed Hyperpure order.

        Args:
            order_id: Hyperpure's order reference number

        Returns:
            HyperpureStatusResult
        """
        raise NotImplementedError

    async def get_prices(self, items: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Fetch current Hyperpure prices for a list of items.

        Args:
            items: List of dicts with at minimum: material_id, material_name, unit

        Returns:
            Dict mapping material_id → current price per unit in rupees (float).
            Items not found in Hyperpure's catalogue are omitted.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Mock implementation
# ---------------------------------------------------------------------------

class MockHyperpureClient(HyperpureClient):
    """
    Simulates Hyperpure responses without any browser automation.

    Behaviour is controlled by the HYPERPURE_MOCK_MODE env var:
      "full"      — all items confirmed (default)
      "partial"   — random subset confirmed, rest OOS
      "rejected"  — entire order rejected (e.g., minimum order not met)
      "error"     — simulates browser/network failure
    """

    # Prices in rupees per kg/litre/unit — sourced from typical Hyperpure/mandi
    # wholesale rates for Indian restaurant ingredients (as of early 2026).
    # Keys are lowercase, stripped; fuzzy-matched against material_name.
    _MOCK_PRICES: Dict[str, float] = {
        # Vegetables
        "tomato": 38, "tomatoes": 38,
        "onion": 28, "onions": 28,
        "potato": 22, "potatoes": 22,
        "garlic": 130, "garlic paste": 120,
        "ginger": 95, "ginger paste": 85,
        "green chilli": 60, "green chillies": 60,
        "coriander": 18, "coriander leaves": 18, "dhaniya": 18,
        "spinach": 30, "palak": 30,
        "capsicum": 55, "bell pepper": 55,
        "carrot": 35, "carrots": 35,
        "cabbage": 20, "cauliflower": 40,
        "lemon": 80, "lemons": 80,
        "cucumber": 25, "beetroot": 40,
        "curry leaves": 50, "mint": 25, "mint leaves": 25,
        # Dairy & Protein
        "paneer": 310, "cottage cheese": 310,
        "milk": 58, "curd": 52, "yogurt": 52, "dahi": 52,
        "butter": 460, "ghee": 540,
        "cream": 220, "cheese": 380,
        "egg": 7, "eggs": 7,
        "chicken": 225, "chicken breast": 260,
        "mutton": 680, "fish": 280,
        # Staples & Grains
        "rice": 62, "basmati rice": 95,
        "wheat flour": 36, "maida": 34, "atta": 36,
        "dal": 90, "lentils": 90, "toor dal": 95, "moong dal": 110,
        "chana dal": 88, "urad dal": 105,
        "chickpeas": 82, "rajma": 100,
        # Oils & Condiments
        "refined oil": 122, "sunflower oil": 118, "groundnut oil": 135,
        "mustard oil": 145, "coconut oil": 165,
        "salt": 18, "sugar": 44, "jaggery": 65,
        "vinegar": 55, "soy sauce": 120,
        # Spices (per 100g equivalent pricing scaled to /kg)
        "turmeric": 180, "haldi": 180,
        "red chilli powder": 220, "chilli powder": 220,
        "coriander powder": 160, "cumin": 280, "jeera": 280,
        "garam masala": 350, "black pepper": 620,
        "cardamom": 1800, "cloves": 950, "cinnamon": 480,
        # Beverages & Misc
        "tea": 380, "coffee": 720,
        "tomato puree": 75, "tomato ketchup": 95,
    }

    def __init__(self):
        self.mock_mode = os.getenv("HYPERPURE_MOCK_MODE", "full")

    def _lookup_price(self, material_name: str) -> Optional[float]:
        """Fuzzy-match a material name against the mock price table."""
        key = material_name.lower().strip()
        if key in self._MOCK_PRICES:
            return self._MOCK_PRICES[key]
        # Partial match: check if any catalogue key is contained in the name
        for catalogue_key, price in self._MOCK_PRICES.items():
            if catalogue_key in key or key in catalogue_key:
                return price
        return None

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

        # Default: full confirmation
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
        """Return mock Hyperpure prices with ±10% variance to simulate live pricing."""
        prices: Dict[str, float] = {}
        for item in items:
            mid = item.get("material_id", "")
            name = item.get("material_name", "")
            base = self._lookup_price(name)
            if base is not None:
                # ±10% random variance around the base price
                variance = random.uniform(0.90, 1.10)
                prices[mid] = round(base * variance, 2)
        return prices


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_hyperpure_client: Optional[HyperpureClient] = None


def get_hyperpure_client() -> HyperpureClient:
    """
    Return the Hyperpure client singleton.

    Set HYPERPURE_USE_MOCK=false (and implement PlaywrightHyperpureClient)
    to switch to real browser automation. Until then the mock is always used.
    """
    global _hyperpure_client
    if _hyperpure_client is None:
        use_mock = os.getenv("HYPERPURE_USE_MOCK", "true").lower() != "false"
        if use_mock:
            _hyperpure_client = MockHyperpureClient()
            logger.info("HyperpureClient: using MOCK implementation")
        else:
            # Placeholder — swap in PlaywrightHyperpureClient when ready
            raise NotImplementedError(
                "Real Hyperpure Playwright client not yet implemented. "
                "Set HYPERPURE_USE_MOCK=true or implement PlaywrightHyperpureClient."
            )
    return _hyperpure_client
