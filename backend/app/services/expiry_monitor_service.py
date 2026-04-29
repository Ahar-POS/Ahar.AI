"""
Expiry Monitor Service — daily "Today's Special" suggestion.

Called by the orchestrator every day at 7 AM (CronTrigger hour=7).
Queries perishable inventory items expiring within 2 days, asks Claude to
suggest a discounted "Today's Special" dish, and writes a pending record to
the `expiry_specials` collection for manager approval.
"""
import logging
from datetime import datetime
from app.utils.timezone import now_ist
from typing import Optional, Dict, Any, List

import anthropic

from app.core.database import get_database
from app.core.config import get_settings
from app.repositories.inventory_repository import get_inventory_repository

logger = logging.getLogger(__name__)

RESTAURANT_ID = "antera_jubilee_hills"


class ExpiryMonitorService:

    async def run(self) -> Optional[Dict[str, Any]]:
        """
        Find expiring ingredients, generate a Today's Special via Claude,
        and write a pending approval record to `expiry_specials`.

        Returns the inserted document on success, None if no expiring items found.
        """
        db = get_database()
        settings = get_settings()

        # ── 1. Find items expiring within 2 days ────────────────────────────
        repo = get_inventory_repository()
        expiring_items = await repo.get_expiring_soon(days=2)

        if not expiring_items:
            logger.info("Expiry monitor: no items expiring within 2 days — skipping")
            return None

        logger.info(
            f"Expiry monitor: found {len(expiring_items)} item(s) expiring soon"
        )

        # ── 2. Build LLM prompt ─────────────────────────────────────────────
        ingredient_lines = []
        for item in expiring_items:
            expiry = item.get("expiry_date")
            if isinstance(expiry, datetime):
                expiry_str = expiry.strftime("%Y-%m-%d")
            else:
                expiry_str = str(expiry) if expiry else "unknown"
            ingredient_lines.append(
                f"- {item.get('material_name')} "
                f"({item.get('current_stock')} {item.get('unit', '')} remaining, "
                f"expires {expiry_str})"
            )

        ingredient_list = "\n".join(ingredient_lines)
        prompt = (
            "You are a creative chef at Antera restaurant in Hyderabad. "
            "The following ingredients expire within 2 days and must be used today. "
            "Suggest ONE discounted \"Today's Special\" dish that uses as many as possible.\n\n"
            f"Ingredients expiring:\n{ingredient_list}\n\n"
            "Respond in 2-3 sentences: name the dish, mention the key ingredients used, "
            "and give a brief customer-facing description. Be specific and appetising."
        )

        # ── 3. Call Claude API ───────────────────────────────────────────────
        suggestion = await self._call_llm(prompt, settings)

        # ── 4. Build and insert record ───────────────────────────────────────
        now = now_ist()
        special_id = f"ES_{now.strftime('%Y%m%d_%H%M%S')}"

        # Nearest expiry date for the card display
        nearest_expiry = expiring_items[0].get("expiry_date")
        if isinstance(nearest_expiry, datetime):
            expiry_date_str = nearest_expiry.strftime("%Y-%m-%d")
        else:
            expiry_date_str = str(nearest_expiry) if nearest_expiry else ""

        material_names = ", ".join(
            item.get("material_name", "") for item in expiring_items
        )

        doc: Dict[str, Any] = {
            "special_id": special_id,
            "status": "pending",
            "restaurant_id": RESTAURANT_ID,
            "expiring_items": [
                {
                    "material_id": item.get("material_id"),
                    "material_name": item.get("material_name"),
                    "current_stock": item.get("current_stock"),
                    "unit": item.get("unit"),
                    "expiry_date": item.get("expiry_date"),
                }
                for item in expiring_items
            ],
            "material_name": material_names,
            "suggestion": suggestion,
            "expiry_date": expiry_date_str,
            "created_at": now,
            "reviewed_at": None,
            "reviewed_by": None,
            "approval_notes": None,
        }

        try:
            await db.expiry_specials.insert_one(doc)
            logger.info(f"Expiry monitor: created special {special_id}")
        except Exception as e:
            logger.error(f"Expiry monitor: failed to insert expiry_special: {e}")
            return None

        return doc

    async def _call_llm(self, prompt: str, settings) -> str:
        """Call Claude API and return the suggestion text."""
        if not settings.CLAUDE_API_KEY:
            logger.warning("CLAUDE_API_KEY not set — returning placeholder suggestion")
            return "Chef's special using today's freshest ingredients. Ask your server for details."

        try:
            client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)
            response = client.messages.create(
                model=settings.AGENT_MODEL_DEFAULT,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"LLM call failed in expiry monitor: {e}")
            return "Today's special features our freshest ingredients. Ask your server for details."


_instance: Optional[ExpiryMonitorService] = None


def get_expiry_monitor() -> ExpiryMonitorService:
    global _instance
    if _instance is None:
        _instance = ExpiryMonitorService()
    return _instance
