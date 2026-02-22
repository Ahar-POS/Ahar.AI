"""
Admin chatbot service with Skills API integration.

Cost-optimized approach:
- Local intent detection (0 LLM cost)
- Local date parsing (0 LLM cost)
- Skills API for P&L generation (minimal tokens)
- Multi-turn conversation support
"""

import re
import logging
import io
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import httpx
from anthropic import Anthropic
from app.core.config import get_settings
from app.services.skill_uploader import SkillUploader
from app.services.data_loader import DataLoader
from app.services.inventory_service import inventory_service
from app.repositories.inventory_repository import inventory_repository
from app.models.inventory import InventoryItemUpdate, InventoryItemResponse

logger = logging.getLogger(__name__)

# In-memory conversation history per user
_chat_history: Dict[str, List[Dict[str, str]]] = {}

# Cap history to avoid token limits
MAX_HISTORY_MESSAGES = 20

# System prompt for general chat
SYSTEM_PROMPT = """You are a helpful restaurant operations advisor. Answer questions about restaurant financials, demand forecasting, and inventory management in general terms only. Do not reference or use any specific restaurant data, figures, or databases. Keep answers concise and in plain text."""


def _item_to_dict(item: InventoryItemResponse) -> dict:
    """Convert InventoryItemResponse to a plain dict safe for JSON serialization"""
    return {
        "material_id": item.material_id,
        "material_name": item.material_name,
        "category": item.category,
        "unit": item.unit,
        "current_stock": item.current_stock,
        "reorder_level": item.reorder_level,
        "reorder_qty": item.reorder_qty,
        "max_stock": item.max_stock,
        "unit_cost_inr": item.unit_cost_inr,  # in paise
        "is_perishable": item.is_perishable,
        "supplier_id": item.supplier_id,
    }


# Tool definitions for inventory operations via Claude native tool calling
INVENTORY_TOOLS = [
    {
        "name": "search_inventory",
        "description": (
            "Search inventory items by name keyword and/or category. "
            "Use when the user asks about specific ingredients, lists items in a category, "
            "or asks what items are available. "
            "Either query or category can be omitted but at least one must be provided."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Substring to search in item name (e.g. 'bread', 'flour')"
                },
                "category": {
                    "type": "string",
                    "description": "Exact category filter (e.g. 'Bakery', 'Dairy', 'Meat')"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_low_stock_items",
        "description": (
            "Get all inventory items where current stock is at or below the reorder level. "
            "Use when the user asks about low stock, what needs restocking, or reorder alerts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_inventory_item",
        "description": (
            "Get full details of a single inventory item by its name or material ID. "
            "Use when the user asks about a specific item's stock, cost, supplier, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name_or_id": {
                    "type": "string",
                    "description": "Item name (partial match) or material ID (e.g. 'RM001')"
                }
            },
            "required": ["name_or_id"]
        }
    },
    {
        "name": "update_inventory_field",
        "description": (
            "Update one of three allowed fields on an inventory item: "
            "current_stock, unit_cost_inr, or reorder_level. "
            "Use when the user explicitly asks to update/change/set one of these values. "
            "IMPORTANT: unit_cost_inr is stored in paise - if user says '60 rupees', "
            "multiply by 100 before calling (pass 6000)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name_or_id": {
                    "type": "string",
                    "description": "Item name or material ID to identify the item"
                },
                "field": {
                    "type": "string",
                    "enum": ["current_stock", "unit_cost_inr", "reorder_level"],
                    "description": "The field to update"
                },
                "value": {
                    "type": "number",
                    "description": "New value for the field (for unit_cost_inr, pass value in paise)"
                }
            },
            "required": ["name_or_id", "field", "value"]
        }
    }
]


class ChatbotService:
    """Cost-optimized chatbot with Skills API integration"""

    def __init__(self):
        """Initialize chatbot service"""
        self.settings = get_settings()
        self.client = None
        self._skill_uploader = None  # Lazy initialization
        self._data_loader = None  # Lazy initialization

        # Initialize only if API key is configured
        if self.settings.CLAUDE_API_KEY and self.settings.CLAUDE_API_KEY.strip():
            # Configure custom timeout for Skills API (can take 2-3 minutes)
            http_client = httpx.Client(
                timeout=httpx.Timeout(self.settings.CHATBOT_TIMEOUT, connect=10.0)
            )
            self.client = Anthropic(
                api_key=self.settings.CLAUDE_API_KEY.strip(),
                http_client=http_client
            )
            # Skill uploader and data loader initialized lazily when needed

    @property
    def data_loader(self):
        """Lazy initialization of DataLoader"""
        if self._data_loader is None:
            self._data_loader = DataLoader(Path(self.settings.DATA_PATH))
        return self._data_loader

    @property
    def skill_uploader(self):
        """Lazy initialization of SkillUploader"""
        if self._skill_uploader is None and self.client:
            self._skill_uploader = SkillUploader(
                client=self.client,
                skills_path=Path(self.settings.SKILLS_PATH)
            )
        return self._skill_uploader

    def _get_history(self, user_id: str) -> List[Dict[str, str]]:
        """Get conversation history for user"""
        if user_id not in _chat_history:
            _chat_history[user_id] = []
        return _chat_history[user_id]

    def _trim_history(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Keep only recent messages within cap"""
        if len(messages) <= MAX_HISTORY_MESSAGES:
            return messages
        return messages[-MAX_HISTORY_MESSAGES:]

    def _is_pnl_intent(self, message: str) -> bool:
        """
        Local keyword matching for P&L intent - 0 LLM cost

        Args:
            message: User message

        Returns:
            True if message is about P&L generation
        """
        msg_lower = message.lower()
        keywords = [
            'p&l', 'p & l', 'pnl', 'p n l',
            'profit', 'loss', 'profit and loss',
            'financial report', 'financial statement',
            'revenue report', 'income statement'
        ]
        return any(kw in msg_lower for kw in keywords)

    def _is_inventory_intent(self, message: str) -> bool:
        """
        Local keyword matching for inventory intent - 0 LLM cost

        Args:
            message: User message

        Returns:
            True if message is about inventory operations
        """
        msg_lower = message.lower()
        keywords = [
            'inventory', 'stock', 'ingredient', 'item', 'material',
            'low stock', 'reorder', 'restock', 'category', 'supplier',
            'perishable', 'shelf life', 'out of stock',
            # Common food category words
            'bread', 'dairy', 'meat', 'vegetable', 'spice', 'grain',
            'protein', 'sauce', 'oil', 'flour', 'rice', 'bakery',
            # Action words
            'update stock', 'update cost', 'update reorder',
            'how much', 'how many', 'do we have', 'what do we have',
        ]
        return any(kw in msg_lower for kw in keywords)

    def _extract_dates_local(self, message: str) -> dict:
        """
        Parse dates locally - 0 LLM cost

        Supports:
        - Explicit range: "2024-01-01 to 2024-12-31"
        - Relative: "last week", "this month", "last month", "this year"

        Args:
            message: User message

        Returns:
            dict with keys:
                - start: start date (YYYY-MM-DD)
                - end: end date (YYYY-MM-DD)
                - ambiguous: bool indicating if clarification needed
                - clarification_question: str if ambiguous
        """
        msg = message.lower()
        today = datetime.now()

        # Pattern 1: Explicit date range "YYYY-MM-DD to YYYY-MM-DD"
        match = re.search(r'(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})', msg)
        if match:
            return {
                'start': match.group(1),
                'end': match.group(2),
                'ambiguous': False
            }

        # Pattern 2: Single month "january 2024", "jan 2024"
        month_match = re.search(
            r'(january|february|march|april|may|june|july|august|september|october|november|december|'
            r'jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{4})',
            msg
        )
        if month_match:
            month_name = month_match.group(1)
            year = int(month_match.group(2))

            # Map month names to numbers
            months = {
                'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
                'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
                'may': 5, 'june': 6, 'jun': 6,
                'july': 7, 'jul': 7, 'august': 8, 'aug': 8,
                'september': 9, 'sep': 9, 'sept': 9,
                'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
                'december': 12, 'dec': 12
            }
            month = months.get(month_name)

            if month:
                start = datetime(year, month, 1)
                # Last day of month
                if month == 12:
                    end = datetime(year, 12, 31)
                else:
                    end = datetime(year, month + 1, 1) - timedelta(days=1)

                return {
                    'start': start.strftime('%Y-%m-%d'),
                    'end': end.strftime('%Y-%m-%d'),
                    'ambiguous': False
                }

        # Pattern 3: Relative dates
        if 'last week' in msg:
            # Previous Monday to Sunday
            days_since_monday = today.weekday()
            last_monday = today - timedelta(days=days_since_monday + 7)
            last_sunday = last_monday + timedelta(days=6)
            return {
                'start': last_monday.strftime('%Y-%m-%d'),
                'end': last_sunday.strftime('%Y-%m-%d'),
                'ambiguous': False
            }

        if 'this week' in msg:
            # Current week Monday to today
            days_since_monday = today.weekday()
            this_monday = today - timedelta(days=days_since_monday)
            return {
                'start': this_monday.strftime('%Y-%m-%d'),
                'end': today.strftime('%Y-%m-%d'),
                'ambiguous': False
            }

        if 'last month' in msg:
            # Previous month, full month
            first_of_this_month = today.replace(day=1)
            last_month_end = first_of_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return {
                'start': last_month_start.strftime('%Y-%m-%d'),
                'end': last_month_end.strftime('%Y-%m-%d'),
                'ambiguous': False
            }

        if 'this month' in msg:
            # Current month, start to today
            start = today.replace(day=1)
            return {
                'start': start.strftime('%Y-%m-%d'),
                'end': today.strftime('%Y-%m-%d'),
                'ambiguous': False
            }

        if 'this year' in msg or f'{today.year}' in msg:
            # Current year, Jan 1 to today
            start = today.replace(month=1, day=1)
            return {
                'start': start.strftime('%Y-%m-%d'),
                'end': today.strftime('%Y-%m-%d'),
                'ambiguous': False
            }

        # No clear date found - need clarification
        return {
            'ambiguous': True,
            'clarification_question': (
                "Please specify the date range for the P&L report.\n\n"
                "Examples:\n"
                "• 'last week'\n"
                "• 'last month'\n"
                "• 'January 2024'\n"
                "• '2024-01-01 to 2024-01-31'"
            )
        }

    async def _generate_pnl_via_skills(
        self,
        start_date: str,
        end_date: str,
        user_id: str
    ) -> dict:
        """
        Generate P&L using Skills API

        Steps:
        1. Filter data locally (backend)
        2. Convert to CSV and upload to container
        3. Get/upload skill
        4. Call Skills API with container
        5. Download generated Excel
        6. Save and return download URL

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            user_id: User identifier

        Returns:
            dict with reply, download_url, filename, usage
        """
        try:
            # 1. Filter data locally (0 LLM cost)
            logger.info(f"Filtering orders from {start_date} to {end_date}")
            filtered_data = self.data_loader.get_orders_filtered(start_date, end_date)

            if filtered_data.empty:
                return {
                    "reply": f"No order data found for {start_date} to {end_date}",
                    "success": False
                }

            # 2. Convert to CSV for upload
            csv_content = filtered_data.to_csv(index=False).encode('utf-8')
            logger.info(f"Filtered data: {len(filtered_data)} orders, {len(csv_content)} bytes")

            # 3. Upload CSV file using Files API
            # Files API requires SDK >= 0.80.0
            data_file = self.client.beta.files.upload(
                file=io.BytesIO(csv_content),
                betas=["files-api-2025-04-14"]
            )
            logger.info(f"Uploaded data file: {data_file.id}")

            # 4. Get/upload skill (cached after first upload)
            skill_id = self.skill_uploader.get_or_upload_skill("pnl-statement")
            logger.info(f"Using skill: {skill_id}")

            # 5. Call Skills API with file passed via container_upload in message content
            logger.info("Calling Skills API to generate P&L")
            response = self.client.beta.messages.create(
                model=self.settings.CHATBOT_MODEL,
                max_tokens=2048,
                betas=[
                    "code-execution-2025-08-25",
                    "skills-2025-10-02",
                    "files-api-2025-04-14"
                ],
                container={
                    "skills": [{
                        "type": "custom",
                        "skill_id": skill_id,
                        "version": "latest"
                    }]
                },
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Generate P&L report from {start_date} to {end_date} using the uploaded CSV data."
                        },
                        {
                            "type": "container_upload",
                            "file_id": data_file.id
                        }
                    ]
                }],
                tools=[{
                    "type": "code_execution_20250825",
                    "name": "code_execution"
                }]
            )

            logger.info(f"Skills API response received. Usage: {response.usage}")

            # 6. Extract file_id from response
            file_id = self._extract_file_id(response)

            if not file_id:
                return {
                    "reply": "P&L generation failed. No output file created.",
                    "success": False,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens
                    }
                }

            # 7. Download Excel file
            logger.info(f"Downloading file: {file_id}")
            # Files API requires SDK >= 0.80.0
            excel_content = self.client.beta.files.download(
                file_id=file_id,
                betas=["files-api-2025-04-14"]
            )

            # 8. Save locally
            filename = f"pnl_{start_date}_{end_date}.xlsx"
            download_url = self._save_file(excel_content, filename, user_id)

            # 9. Return success response
            return {
                "reply": f"P&L report generated for {start_date} to {end_date}",
                "download_url": download_url,
                "filename": filename,
                "success": True,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
            }

        except Exception as e:
            logger.error(f"P&L generation failed: {e}", exc_info=True)
            return {
                "reply": f"Failed to generate P&L report: {str(e)}",
                "success": False
            }

    def _extract_file_id(self, response) -> Optional[str]:
        """Extract file_id from Skills API response"""
        try:
            for block in response.content:
                # Check bash_code_execution_tool_result
                if block.type == "bash_code_execution_tool_result":
                    content_item = block.content
                    if content_item.type == "bash_code_execution_result":
                        # content is a list of items, check each one
                        if hasattr(content_item, 'content'):
                            for file_item in content_item.content:
                                if hasattr(file_item, 'file_id'):
                                    return file_item.file_id
                # Also check legacy tool_use format for compatibility
                elif block.type == "tool_use" and hasattr(block, 'content'):
                    for content_item in block.content:
                        if hasattr(content_item, 'content'):
                            for result in content_item.content:
                                if hasattr(result, 'file_id'):
                                    return result.file_id
        except Exception as e:
            logger.error(f"Failed to extract file_id: {e}", exc_info=True)
        return None

    def _save_file(self, file_content, filename: str, user_id: str) -> str:
        """
        Save downloaded file and return URL

        Args:
            file_content: File content from Anthropic
            filename: Filename to save as
            user_id: User identifier

        Returns:
            Download URL for frontend
        """
        # Create reports directory
        reports_dir = Path(self.settings.REPORTS_DIR)
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = reports_dir / filename

        # Handle different response types
        if hasattr(file_content, 'write_to_file'):
            # Newer API with write_to_file method
            with open(file_path, 'wb') as f:
                file_content.write_to_file(f.name)
        elif isinstance(file_content, bytes):
            # Raw bytes
            with open(file_path, 'wb') as f:
                f.write(file_content)
        else:
            # Try to read as file-like object
            with open(file_path, 'wb') as f:
                f.write(file_content.read() if hasattr(file_content, 'read') else file_content)

        logger.info(f"Saved file: {file_path}")

        # Return URL (relative to API base)
        return f"/api/v1/chatbot/download/{filename}"

    async def _general_chat(self, message: str, user_id: str) -> dict:
        """
        Handle general chat (non-P&L) using standard Claude

        Args:
            message: User message
            user_id: User identifier

        Returns:
            dict with reply and usage
        """
        if not self.client:
            return {
                "reply": "API key not configured. Add CLAUDE_API_KEY to your .env to enable the chatbot.",
                "success": False
            }

        try:
            history = self._get_history(user_id)

            api_messages = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in self._trim_history(history)
            ]

            response = self.client.messages.create(
                model=self.settings.CHATBOT_MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=api_messages,
            )

            reply_text = ""
            if response.content:
                for block in response.content:
                    if hasattr(block, "text"):
                        reply_text += block.text

            reply_text = reply_text.strip() or "I couldn't generate a reply."

            return {
                "reply": reply_text,
                "success": True,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
            }

        except Exception as e:
            logger.error(f"General chat failed: {e}")
            return {
                "reply": "Sorry, I couldn't process that. Please try again.",
                "success": False
            }

    def _assistant_content_to_dicts(self, content: list) -> list:
        """
        Convert response content blocks to plain dicts.
        Avoids Anthropic SDK serialization bug (by_alias NoneType) when passing
        assistant content back into messages.create() in the tool-use loop.
        """
        out = []
        for block in content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                out.append({"type": "text", "text": getattr(block, "text", "") or ""})
            elif block_type == "tool_use":
                inp = getattr(block, "input", None)
                if hasattr(inp, "model_dump"):
                    inp = inp.model_dump()
                elif inp is None:
                    inp = {}
                elif not isinstance(inp, dict):
                    inp = dict(inp) if getattr(inp, "items", None) else {}
                out.append({
                    "type": "tool_use",
                    "id": getattr(block, "id", ""),
                    "name": getattr(block, "name", ""),
                    "input": inp,
                })
        return out

    async def _execute_inventory_tool(self, tool_name: str, tool_input: dict) -> str:
        """
        Execute an inventory tool call and return result as a JSON string

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool parameters from Claude

        Returns:
            JSON string with results or error
        """
        try:
            if tool_name == "search_inventory":
                query = tool_input.get("query", "")
                category = tool_input.get("category")

                if query:
                    # Search by name
                    items = await inventory_service.search_items_by_name(query)
                else:
                    # Get all, optionally filtered by category
                    items, _ = await inventory_service.get_all_items(limit=200, category=category)

                # If both query and category provided, intersect results
                if category and query:
                    items = [i for i in items if i.category.lower() == category.lower()]

                return json.dumps([_item_to_dict(i) for i in items])

            elif tool_name == "get_low_stock_items":
                items = await inventory_service.get_low_stock_items()
                return json.dumps([_item_to_dict(i) for i in items])

            elif tool_name == "get_inventory_item":
                name_or_id = tool_input["name_or_id"]

                # Try material_id first (exact match)
                item = await inventory_repository.get_by_material_id(name_or_id)

                # Fall back to name search (partial match)
                if not item:
                    results = await inventory_repository.search_by_name(name_or_id)
                    item = results[0] if results else None

                if not item:
                    return json.dumps({"error": f"No item found matching '{name_or_id}'"})

                # Convert ObjectId to string for JSON serialization
                item["_id"] = str(item["_id"])
                return json.dumps(item, default=str)

            elif tool_name == "update_inventory_field":
                ALLOWED_FIELDS = {"current_stock", "unit_cost_inr", "reorder_level"}
                field = tool_input["field"]
                value = tool_input["value"]
                name_or_id = tool_input["name_or_id"]

                # Validate field
                if field not in ALLOWED_FIELDS:
                    return json.dumps({"error": f"Field '{field}' is not updatable via chatbot"})

                # Resolve item (try material_id, then name search)
                item = await inventory_repository.get_by_material_id(name_or_id)
                if not item:
                    results = await inventory_repository.search_by_name(name_or_id)
                    item = results[0] if results else None

                if not item:
                    return json.dumps({"error": f"No item found matching '{name_or_id}'"})

                # Update via service layer
                item_id = str(item["_id"])
                update_data = InventoryItemUpdate(**{field: int(value)})
                updated = await inventory_service.update_item(item_id, update_data)

                updated_dict = _item_to_dict(updated)
                return json.dumps({"success": True, "updated": updated_dict})

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as e:
            logger.error(f"Inventory tool '{tool_name}' failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    async def _handle_inventory_message(self, message: str, user_id: str) -> dict:
        """
        Handle inventory-related messages using Claude tool calling

        Implements agentic loop:
        1. Call Claude with tools parameter
        2. While stop_reason == "tool_use":
           - Execute each tool_use block
           - Append assistant turn + tool results
           - Call Claude again
        3. Extract final text reply

        Args:
            message: User message
            user_id: User identifier

        Returns:
            dict with reply, success, usage stats
        """
        if not self.client:
            return {
                "reply": "API key not configured. Add CLAUDE_API_KEY to your .env to enable the chatbot.",
                "success": False
            }

        history = self._get_history(user_id)

        # System prompt for inventory context
        INVENTORY_SYSTEM_PROMPT = (
            "You are an inventory assistant for a restaurant. "
            "Answer questions about the restaurant's raw material inventory using the provided tools. "
            "Be concise and clear. Format lists using bullet points or Markdown tables. "
            "Use **bold** for emphasis where appropriate. Keep each table row on a single line (no line breaks inside cells). "
            "When showing stock and reorder levels, include the unit in the value (e.g. '18 kg') and omit a separate Unit column if it would be redundant. "
            "\n\n"
            "IMPORTANT DATA CONVENTIONS:\n"
            "- unit_cost_inr is stored in PAISE (not rupees). Always divide by 100 when displaying costs to users. "
            "For example, if unit_cost_inr is 6000, display as '₹60'.\n"
            "- When updating unit_cost_inr, multiply rupees by 100 before passing to the tool. "
            "If user says 'set cost to 60 rupees', call update_inventory_field with value=6000.\n"
            "- current_stock and reorder_level are integers (no decimals).\n"
            "- is_perishable is 'Yes' or 'No' (not a boolean).\n"
            "\n"
            "Only update fields when the user explicitly asks you to. "
            "Always confirm what was updated after making changes."
        )

        # Build API messages from history
        api_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in self._trim_history(history)
        ]

        try:
            # Initial call to Claude with tools
            response = self.client.messages.create(
                model=self.settings.CHATBOT_MODEL,
                max_tokens=1024,
                system=INVENTORY_SYSTEM_PROMPT,
                tools=INVENTORY_TOOLS,
                messages=api_messages,
            )

            # Agentic loop: keep processing until Claude stops calling tools
            while response.stop_reason == "tool_use":
                tool_results = []
                assistant_content = response.content

                # Execute all tool_use blocks in the response
                for block in response.content:
                    if block.type == "tool_use":
                        result_str = await self._execute_inventory_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        })

                # Append assistant turn as plain dicts to avoid SDK/Pydantic by_alias bug
                api_messages.append({
                    "role": "assistant",
                    "content": self._assistant_content_to_dicts(assistant_content),
                })

                # Append user turn with tool results
                api_messages.append({"role": "user", "content": tool_results})

                # Call Claude again with updated messages
                response = self.client.messages.create(
                    model=self.settings.CHATBOT_MODEL,
                    max_tokens=1024,
                    system=INVENTORY_SYSTEM_PROMPT,
                    tools=INVENTORY_TOOLS,
                    messages=api_messages,
                )

            # Extract final text reply from response
            reply_text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            ).strip() or "I couldn't generate a reply."

            return {
                "reply": reply_text,
                "success": True,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
            }

        except Exception as e:
            logger.error(f"Inventory message handling failed: {e}", exc_info=True)
            return {
                "reply": "Sorry, I couldn't process that inventory query. Please try again.",
                "success": False
            }

    async def process_message(self, user_id: str, message: str) -> dict:
        """
        Main entry point for processing user messages

        Cost optimization:
        1. Local intent detection (0 cost)
        2. Local date parsing (0 cost) for P&L
        3. LLM only if needed (clarification or general chat)

        Routing order:
        1. Inventory intent → tool calling
        2. P&L intent → Skills API
        3. General chat → simple messages

        Args:
            user_id: User identifier
            message: User message

        Returns:
            dict with reply, optional download_url, usage stats
        """
        # Add to history
        history = self._get_history(user_id)
        history.append({"role": "user", "content": message.strip()})

        # Route 1: Inventory intent (local keywords → Claude with tools)
        if self._is_inventory_intent(message):
            result = await self._handle_inventory_message(message, user_id)
            history.append({"role": "assistant", "content": result["reply"]})
            _chat_history[user_id] = self._trim_history(history)
            return result

        # Route 2: P&L intent (existing flow)
        if self._is_pnl_intent(message):
            # Extract dates locally (0 cost)
            dates = self._extract_dates_local(message)

            if dates.get('ambiguous'):
                # Need clarification - no LLM call
                reply = dates['clarification_question']
                history.append({"role": "assistant", "content": reply})
                _chat_history[user_id] = self._trim_history(history)
                return {
                    "reply": reply,
                    "needs_clarification": True,
                    "success": True
                }

            # Generate P&L via Skills API
            result = await self._generate_pnl_via_skills(
                start_date=dates['start'],
                end_date=dates['end'],
                user_id=user_id
            )

            # Add to history
            history.append({"role": "assistant", "content": result["reply"]})
            _chat_history[user_id] = self._trim_history(history)

            return result

        # Route 3: General chat (fallback)
        result = await self._general_chat(message, user_id)
        history.append({"role": "assistant", "content": result["reply"]})
        _chat_history[user_id] = self._trim_history(history)
        return result


# Global service instance
_chatbot_service: Optional[ChatbotService] = None


def get_chatbot_service() -> ChatbotService:
    """Get or create chatbot service singleton"""
    global _chatbot_service
    if _chatbot_service is None:
        _chatbot_service = ChatbotService()
    return _chatbot_service


# Legacy function for backward compatibility
def get_reply(user_id: str, message: str) -> str:
    """
    Legacy function - returns just the reply text

    For new code, use: await get_chatbot_service().process_message()
    """
    import asyncio
    service = get_chatbot_service()
    result = asyncio.run(service.process_message(user_id, message))
    return result.get("reply", "Error processing message")
