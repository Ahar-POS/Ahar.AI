"""
Admin chatbot service with Skills API integration.

Cost-optimized approach:
- Local intent detection (0 LLM cost)
- Local date parsing (0 LLM cost)
- Skills API for P&L generation (minimal tokens)
- Multi-turn conversation support
"""

import os
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
from app.core.database import get_database
from app.services.skill_uploader import SkillUploader
from app.services.data_loader import DataLoader
from app.services.inventory_service import inventory_service
from app.repositories.inventory_repository import inventory_repository
from app.models.inventory import InventoryItemUpdate, InventoryItemResponse

logger = logging.getLogger(__name__)

# In-memory conversation history per user
_chat_history: Dict[str, List[Dict[str, str]]] = {}

# In-memory P&L context per user (stores list of generated P&L reports)
_pnl_context: Dict[str, List[Dict]] = {}

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


# Tool definitions for profit analysis via Claude native tool calling
PROFIT_ANALYSIS_TOOLS = [
    {
        "name": "get_top_items",
        "description": (
            "Get top or bottom performing items ranked by a specific metric. "
            "Use when user asks about best/worst items, top performers, rankings, sales leaders, most sold items. "
            "Metrics available: revenue (sales value), profit (profit amount), margin (profit %), "
            "volume (quantity sold), avg_order_value. "
            "For 'which sold most' queries, use metric=volume. "
            "For 'highest sales' queries, use metric=revenue. "
            "Supports both relative (period_days) and explicit (start_date_str/end_date_str) date ranges."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["revenue", "profit", "margin", "volume", "avg_order_value"],
                    "description": "Metric to rank by (revenue=sales value, profit=revenue-COGS, margin=profit%, volume=quantity sold)"
                },
                "period_days": {
                    "type": "integer",
                    "description": "Number of days to analyze (relative mode: 7=last week, 30=last month). Omit if using explicit dates."
                },
                "start_date_str": {
                    "type": "string",
                    "description": "Explicit start date YYYY-MM-DD (e.g., '2025-11-01'). Use for month-based queries."
                },
                "end_date_str": {
                    "type": "string",
                    "description": "Explicit end date YYYY-MM-DD (e.g., '2025-11-30'). Use for month-based queries."
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of items to return (default 10, max 50)"
                },
                "order": {
                    "type": "string",
                    "enum": ["desc", "asc"],
                    "description": "desc for top performers, asc for bottom performers (default desc)"
                },
                "category": {
                    "type": "string",
                    "description": "Optional filter by category (e.g. 'sandwich', 'beverage')"
                }
            },
            "required": ["metric"]
        }
    },
    {
        "name": "get_item_details",
        "description": (
            "Get detailed performance data for a specific menu item including revenue, profit, "
            "margin, COGS breakdown, trends, and changes over time. "
            "Use for deep-dive analysis on a single item. "
            "Supports both relative (period_days) and explicit (start_date_str/end_date_str) date ranges."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Name of menu item (partial match OK, e.g. 'chicken tikka')"
                },
                "period_days": {
                    "type": "integer",
                    "description": "Number of days to analyze (relative mode, default 30). Omit if using explicit dates."
                },
                "start_date_str": {
                    "type": "string",
                    "description": "Explicit start date YYYY-MM-DD (e.g., '2025-11-01'). Use for month-based queries."
                },
                "end_date_str": {
                    "type": "string",
                    "description": "Explicit end date YYYY-MM-DD (e.g., '2025-11-30'). Use for month-based queries."
                }
            },
            "required": ["item_name"]
        }
    },
    {
        "name": "get_ingredient_costs",
        "description": (
            "Get ingredient-level cost analysis including total spend, unit costs, cost trends, "
            "and which dishes use each ingredient. "
            "Use when user asks about ingredient costs, cost drivers, or 'what ingredient cost me most'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period_days": {
                    "type": "integer",
                    "description": "Number of days to analyze (default 7)"
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["total_cost", "unit_cost", "volume", "cost_change"],
                    "description": "How to sort results (total_cost=most spend, cost_change=biggest price change)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of ingredients to return (default 10, max 50)"
                },
                "category": {
                    "type": "string",
                    "description": "Optional filter by ingredient category (e.g. 'Protein', 'Dairy')"
                }
            },
            "required": ["period_days"]
        }
    },
    {
        "name": "compare_periods",
        "description": (
            "Compare metrics between two time periods to show changes and trends. "
            "Use when user asks to compare months, track changes over time, or analyze performance trends. "
            "Supports both relative periods ('last 30 days') and explicit calendar periods ('November vs December'). "
            "For month comparisons, use period1_start/end and period2_start/end parameters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period1_days": {
                    "type": "integer",
                    "description": "Number of days in first period (for relative comparisons)"
                },
                "period2_days": {
                    "type": "integer",
                    "description": "Number of days in second period (for relative comparisons)"
                },
                "period2_offset": {
                    "type": "integer",
                    "description": "Days before period 1 that period 2 starts (for relative comparisons)"
                },
                "period1_start": {
                    "type": "string",
                    "description": "ISO date for period 1 start (YYYY-MM-DD), use for calendar month comparisons"
                },
                "period1_end": {
                    "type": "string",
                    "description": "ISO date for period 1 end (YYYY-MM-DD), use for calendar month comparisons"
                },
                "period2_start": {
                    "type": "string",
                    "description": "ISO date for period 2 start (YYYY-MM-DD), use for calendar month comparisons"
                },
                "period2_end": {
                    "type": "string",
                    "description": "ISO date for period 2 end (YYYY-MM-DD), use for calendar month comparisons"
                },
                "metric": {
                    "type": "string",
                    "enum": ["revenue", "profit", "margin", "volume", "cogs"],
                    "description": "Metric to compare"
                },
                "item_name": {
                    "type": "string",
                    "description": "Optional: specific item to compare (omit for overall comparison)"
                },
                "category": {
                    "type": "string",
                    "description": "Optional: category to compare"
                }
            },
            "required": ["metric"]
        }
    },
    {
        "name": "identify_losses",
        "description": (
            "Identify sources of profit loss including low margin items, high cost ingredients, "
            "waste, pricing issues, and declining items. "
            "Use when user asks 'where am I losing money', 'what's wrong', or loss analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional: focus on specific category (e.g. 'sandwich', 'beverage')"
                },
                "period_days": {
                    "type": "integer",
                    "description": "Number of days to analyze (default 30)"
                },
                "min_margin_threshold": {
                    "type": "number",
                    "description": "Margin threshold % to flag low-margin items (default 25)"
                }
            },
            "required": []
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

    def _wants_excel_format(self, message: str) -> bool:
        """
        Check if user explicitly wants Excel format - 0 LLM cost

        Args:
            message: User message

        Returns:
            True if user explicitly requests Excel file
        """
        msg_lower = message.lower()
        excel_keywords = [
            'excel', 'xlsx', 'spreadsheet',
            'download', 'file', 'export'
        ]
        return any(kw in msg_lower for kw in excel_keywords)

    def _get_pnl_script_path(self) -> Path:
        """Resolve path to generate_pnl.py so it works both locally and in Docker."""
        # backend/app/services/chatbot_service.py -> backend -> repo root
        backend_dir = Path(__file__).resolve().parent.parent.parent
        repo_root = backend_dir.parent
        local_script = repo_root / "skills" / "pnl-statement" / "scripts" / "generate_pnl.py"
        if local_script.exists():
            return local_script
        # Docker: script is at /app/skills/...
        return Path("/app/skills/pnl-statement/scripts/generate_pnl.py")

    def _get_reports_dir_abs(self) -> Path:
        """Absolute path to reports directory (where Excel is saved and served from)."""
        backend_dir = Path(__file__).resolve().parent.parent.parent
        return (backend_dir / self.settings.REPORTS_DIR).resolve()

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

    def _is_profit_analysis_intent(self, message: str) -> bool:
        """
        Local keyword matching for profit/sales analysis intent - 0 LLM cost

        Args:
            message: User message

        Returns:
            True if message is about profit/performance/sales analysis
        """
        msg_lower = message.lower()

        # Strong indicators (high confidence for profit/sales analysis)
        strong_keywords = [
            # Performance keywords
            'top items', 'top performing', 'best selling', 'worst performing',
            'best items', 'bottom items', 'rank', 'ranking', 'performers',
            'top 5', 'top 10', 'top seller', 'top revenue', 'top profit',
            # Profit/margin keywords
            'profit', 'margin', 'profitability', 'contribution',
            # Loss keywords
            'losing money', 'loss', 'losses', 'where am i losing',
            'low margin', 'negative margin', 'unprofitable',
            # Ingredient cost keywords
            'ingredient cost', 'cogs', 'cost of goods',
            'what ingredient cost', 'which ingredient cost', 'ingredient spend',
            # Analysis/comparison
            'analyze performance', 'compare revenue', 'compare profit',
            'performance trend', 'profit trend', 'margin trend',
            # NEW: Sales-specific keywords
            'sales', 'sold', 'selling', 'sell', 'sold most', 'sold least',
            'best selling', 'top selling', 'most sold', 'least sold',
            'sales volume', 'sales revenue', 'units sold',
            'how many sold', 'how much sold', 'sales performance',
            'sales trend', 'sales comparison',
        ]

        # If any strong keyword matches, it's definitely profit/sales analysis
        if any(kw in msg_lower for kw in strong_keywords):
            return True

        # Weaker keywords (need additional context)
        weak_keywords = [
            'revenue', 'sales', 'earnings',
            'analyze', 'analysis', 'performance', 'trend', 'trending',
            'compare', 'comparison',
        ]

        # Time period indicators (strengthen weak keywords)
        time_indicators = [
            'last week', 'last month', 'this month', 'last quarter',
            'last 2 weeks', 'last 4 months', 'last year',
            'past week', 'past month', 'this week',
        ]

        # NEW: Month name indicators
        month_indicators = [
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december',
            'jan', 'feb', 'mar', 'apr', 'may', 'jun',
            'jul', 'aug', 'sep', 'sept', 'oct', 'nov', 'dec'
        ]

        # If weak keyword + time indicator, it's likely profit analysis
        has_weak_keyword = any(kw in msg_lower for kw in weak_keywords)
        has_time_indicator = any(ti in msg_lower for ti in time_indicators)

        if has_weak_keyword and has_time_indicator:
            return True

        # NEW: Month detection logic
        has_month = any(month in msg_lower for month in month_indicators)
        has_sales_context = any(word in msg_lower for word in ['sales', 'revenue', 'sold', 'selling'])

        # If month name + sales/revenue context, route to profit_analysis
        if has_month and has_sales_context:
            return True

        # NEW: Check for comparison patterns
        comparative_patterns = ['compared to', 'vs', 'versus', 'compare', 'how was', 'difference between']
        has_comparison = any(pattern in msg_lower for pattern in comparative_patterns)

        if has_comparison and has_month:
            return True

        # Check for "how has X changed" patterns
        has_how_pattern = 'how has' in msg_lower or 'how have' in msg_lower
        has_change_word = any(word in msg_lower for word in ['changed', 'performing', 'doing'])

        if has_how_pattern and has_change_word:
            return True

        # Check for specific dish names with analysis context
        dish_keywords = ['sandwich', 'burger', 'wrap', 'chai', 'coffee', 'beverage']
        has_dish = any(dish in msg_lower for dish in dish_keywords)
        analysis_words = ['performance', 'margin', 'profit', 'revenue', 'selling']
        has_analysis = any(word in msg_lower for word in analysis_words)

        if has_dish and has_analysis:
            return True

        return False

    def _parse_month_from_message(self, message: str, year: int = None) -> Optional[List[Dict[str, str]]]:
        """
        Extract month names from message and convert to date ranges

        Args:
            message: User message (e.g., "sales in November")
            year: Year to use (defaults to current year)

        Returns:
            List of date ranges with start/end dates, or None if no months found

        Examples:
            "sales in November" → [{'start': '2026-11-01', 'end': '2026-11-30', 'month_name': 'November'}]
            "compare Nov and Dec" → [{'start': '2026-11-01', ...}, {'start': '2026-12-01', ...}]
        """
        import calendar
        import re

        month_map = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }

        # Extract year from message (e.g., "November 2025")
        year_match = re.search(r'\b(20\d{2})\b', message)
        if year_match:
            year = int(year_match.group(1))
        elif year is None:
            year = datetime.now().year

        # Find all months in message
        msg_lower = message.lower()
        found_months = []

        for month_name, month_num in month_map.items():
            if re.search(r'\b' + month_name + r'\b', msg_lower):
                if month_num not in [m['month_num'] for m in found_months]:
                    found_months.append({'month_num': month_num, 'month_name': calendar.month_name[month_num]})

        if not found_months:
            return None

        # Convert to date ranges
        date_ranges = []
        for month_info in found_months:
            month_num = month_info['month_num']
            start_date = datetime(year, month_num, 1)

            # Last day of month
            if month_num == 12:
                end_date = datetime(year, 12, 31)
            else:
                end_date = datetime(year, month_num + 1, 1) - timedelta(days=1)

            date_ranges.append({
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
                'month_name': month_info['month_name'],
                'month_num': month_num,
                'year': year
            })

        return date_ranges

    def _is_pnl_followup(self, message: str, user_id: str) -> bool:
        """
        Check if message is a follow-up question about P&L

        Args:
            message: User message
            user_id: User identifier

        Returns:
            True if this is a follow-up question about a previous P&L
        """
        # Must have previous P&L context
        if user_id not in _pnl_context or not _pnl_context[user_id]:
            return False

        msg_lower = message.lower()

        # Follow-up keywords
        followup_keywords = [
            'explain', 'why', 'what does', 'what is', 'how did',
            'tell me about', 'analyze', 'breakdown', 'detail',
            'compare', 'comparison', 'difference', 'vs', 'versus',
            'this', 'that', 'the report', 'these numbers', 'these reports',
            'both', 'between'
        ]

        # Comparison keywords
        comparison_keywords = [
            'compare', 'comparison', 'vs', 'versus', 'difference',
            'november', 'december', 'october', 'jan', 'feb', 'mar',
            'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
            'last month', 'this month', 'previous', 'current', 'recent'
        ]

        return any(kw in msg_lower for kw in followup_keywords + comparison_keywords)

    async def _handle_pnl_followup(self, message: str, user_id: str) -> dict:
        """
        Handle follow-up questions about P&L using Claude

        Args:
            message: User question
            user_id: User identifier

        Returns:
            dict with reply, success, and token_usage
        """
        try:
            # Get stored P&L context (list of reports)
            pnl_reports = _pnl_context.get(user_id, [])
            if not pnl_reports:
                return {
                    "reply": "No recent P&L reports found. Please generate a P&L first.",
                    "success": False,
                    "usage": {"input_tokens": 0, "output_tokens": 0}
                }

            # Check if user wants to compare multiple periods
            if any(kw in message.lower() for kw in ['compare', 'comparison', 'vs', 'versus', 'difference', 'between']):
                # If user has multiple reports in context, use those for comparison
                if len(pnl_reports) >= 2:
                    # Use the two most recent reports
                    report1 = pnl_reports[-2]
                    report2 = pnl_reports[-1]

                    comparison_prompt = f"""Compare these two P&L reports and provide detailed insights:

**Report 1: {report1['start_date']} to {report1['end_date']}**
{report1['report_text']}

**Report 2: {report2['start_date']} to {report2['end_date']}**
{report2['report_text']}

User question: {message}

Provide a clear comparison focusing on:
- Revenue changes (absolute and percentage)
- Cost differences and trends
- Margin improvements or declines
- Key insights and actionable recommendations"""

                    response = self.client.messages.create(
                        model=self.settings.CHATBOT_MODEL,
                        max_tokens=2048,
                        messages=[{"role": "user", "content": comparison_prompt}]
                    )

                    reply = response.content[0].text

                    return {
                        "reply": reply,
                        "success": True,
                        "usage": {
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens
                        }
                    }
                else:
                    # Try to extract dates from the message
                    dates = self._extract_comparison_dates(message)
                    if dates and len(dates) >= 2:
                        # Generate both P&Ls
                        pnl1_result = await self._generate_pnl_text_only(dates[0]['start'], dates[0]['end'])
                        pnl2_result = await self._generate_pnl_text_only(dates[1]['start'], dates[1]['end'])

                        if pnl1_result['success'] and pnl2_result['success']:
                            comparison_prompt = f"""Compare these two P&L reports and provide detailed insights:

**Report 1: {dates[0]['start']} to {dates[0]['end']}**
{pnl1_result['reply']}

**Report 2: {dates[1]['start']} to {dates[1]['end']}**
{pnl2_result['reply']}

User question: {message}

Provide a clear comparison focusing on:
- Revenue changes (absolute and percentage)
- Cost differences and trends
- Margin improvements or declines
- Key insights and actionable recommendations"""

                            response = self.client.messages.create(
                                model=self.settings.CHATBOT_MODEL,
                                max_tokens=2048,
                                messages=[{"role": "user", "content": comparison_prompt}]
                            )

                            reply = response.content[0].text

                            return {
                                "reply": reply,
                                "success": True,
                                "usage": {
                                    "input_tokens": response.usage.input_tokens,
                                    "output_tokens": response.usage.output_tokens
                                }
                            }
                    else:
                        return {
                            "reply": "Please generate at least two P&L reports first, or specify the periods you want to compare (e.g., 'compare November and December 2025').",
                            "success": False,
                            "usage": {"input_tokens": 0, "output_tokens": 0}
                        }

            # Regular follow-up question about the most recent P&L
            latest_report = pnl_reports[-1]
            analysis_prompt = f"""Analyze this P&L report and answer the user's question:

**P&L Report ({latest_report['start_date']} to {latest_report['end_date']})**
{latest_report['report_text']}

User question: {message}

Provide a clear, concise answer with specific numbers and insights."""

            response = self.client.messages.create(
                model=self.settings.CHATBOT_MODEL,
                max_tokens=1536,
                messages=[{"role": "user", "content": analysis_prompt}]
            )

            reply = response.content[0].text

            return {
                "reply": reply,
                "success": True,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
            }

        except Exception as e:
            logger.error(f"P&L follow-up handling failed: {e}", exc_info=True)
            return {
                "reply": f"Failed to analyze P&L: {str(e)}",
                "success": False,
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }

    def _extract_comparison_dates(self, message: str) -> list:
        """
        Extract two date ranges for comparison from message

        Args:
            message: User message

        Returns:
            List of dict with 'start' and 'end' dates
        """
        msg_lower = message.lower()
        dates = []

        # Common month patterns
        month_map = {
            'jan': 1, 'january': 1,
            'feb': 2, 'february': 2,
            'mar': 3, 'march': 3,
            'apr': 4, 'april': 4,
            'may': 5,
            'jun': 6, 'june': 6,
            'jul': 7, 'july': 7,
            'aug': 8, 'august': 8,
            'sep': 9, 'september': 9,
            'oct': 10, 'october': 10,
            'nov': 11, 'november': 11,
            'dec': 12, 'december': 12
        }

        # Extract year (default to current year)
        import re
        year_match = re.search(r'\b(20\d{2})\b', message)
        year = int(year_match.group(1)) if year_match else datetime.now().year

        # Find months mentioned
        mentioned_months = []
        for month_name, month_num in month_map.items():
            if month_name in msg_lower:
                mentioned_months.append(month_num)

        # Remove duplicates and sort
        mentioned_months = sorted(list(set(mentioned_months)))

        # Convert to date ranges
        for month_num in mentioned_months:
            # First day of month
            start_date = datetime(year, month_num, 1)
            # Last day of month
            if month_num == 12:
                end_date = datetime(year, 12, 31)
            else:
                end_date = datetime(year, month_num + 1, 1) - timedelta(days=1)

            dates.append({
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            })

        return dates

    async def _generate_pnl_text_only(
        self,
        start_date: str,
        end_date: str
    ) -> dict:
        """
        Generate detailed P&L report using enhanced generate_pnl.py script

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            dict with reply (detailed P&L text), success status
        """
        try:
            import subprocess
            import sys

            # Run the enhanced P&L generation script (path works locally and in Docker)
            script_path = self._get_pnl_script_path()
            restaurant_id = "default"

            logger.info(f"Generating detailed P&L for {start_date} to {end_date}")

            result = subprocess.run(
                [sys.executable, str(script_path), start_date, end_date, "text", restaurant_id],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"P&L script failed: {result.stderr}")
                return {
                    "reply": f"Failed to generate P&L report: {result.stderr}",
                    "success": False
                }

            # Extract the P&L report from stdout (skip the "Calculating..." progress lines)
            output_lines = result.stdout.strip().split('\n')

            # Find where the actual report starts (after "Calculating tax..." line)
            report_start = 0
            for i, line in enumerate(output_lines):
                if line.startswith('='):
                    report_start = i
                    break

            # Get the report (everything from the first === line onwards, except the last SUCCESS line)
            report_lines = []
            for line in output_lines[report_start:]:
                if line.startswith('SUCCESS:'):
                    break
                report_lines.append(line)

            text_report = '\n'.join(report_lines)

            # Wrap in markdown code block for proper formatting
            formatted_reply = f"```\n{text_report}\n```"

            logger.info(f"Detailed P&L generated successfully")

            return {
                "reply": formatted_reply,
                "success": True,
                "usage": {"input_tokens": 0, "output_tokens": 0}  # No LLM used
            }

        except subprocess.TimeoutExpired:
            logger.error("P&L generation timed out")
            return {
                "reply": "P&L generation timed out. Please try a shorter date range.",
                "success": False,
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }
        except Exception as e:
            logger.error(f"P&L text generation failed: {e}", exc_info=True)
            return {
                "reply": f"Failed to generate P&L report: {str(e)}",
                "success": False,
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }

    async def _generate_pnl_excel(
        self,
        start_date: str,
        end_date: str
    ) -> dict:
        """
        Generate P&L as Excel file

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            dict with reply, download_url, success status
        """
        try:
            import subprocess
            import sys

            script_path = self._get_pnl_script_path()
            reports_dir_abs = self._get_reports_dir_abs()
            reports_dir_abs.mkdir(parents=True, exist_ok=True)
            restaurant_id = "default"

            logger.info(f"Generating Excel P&L for {start_date} to {end_date}")

            env = {**os.environ, "REPORTS_DIR": str(reports_dir_abs)}
            result = subprocess.run(
                [sys.executable, str(script_path), start_date, end_date, "excel", restaurant_id],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            if result.returncode != 0:
                logger.error(f"Excel P&L script failed: {result.stderr}")
                return {
                    "reply": f"Failed to generate Excel report: {result.stderr}",
                    "success": False
                }

            # Extract file path from output
            output_lines = result.stdout.strip().split('\n')
            file_path = None
            for line in output_lines:
                if line.startswith('FILE_PATH:'):
                    file_path = line.replace('FILE_PATH:', '').strip()
                    break

            if not file_path:
                return {
                    "reply": "Excel report generated but file path not found",
                    "success": False
                }

            # Filename for download endpoint (path may use / or \)
            filename = Path(file_path).name
            download_url = f"/static/reports/{filename}"

            reply = f"✅ Excel P&L Report generated successfully!\n\n📊 Period: {start_date} to {end_date}\n\n[Download Excel Report]({download_url})"

            logger.info(f"Excel P&L generated: {download_url}")

            return {
                "reply": reply,
                "download_url": download_url,
                "filename": filename,
                "success": True,
                "usage": {"input_tokens": 0, "output_tokens": 0}  # No LLM used
            }

        except subprocess.TimeoutExpired:
            logger.error("Excel P&L generation timed out")
            return {
                "reply": "Excel generation timed out. Please try a shorter date range.",
                "success": False,
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }
        except Exception as e:
            logger.error(f"Excel P&L generation failed: {e}", exc_info=True)
            return {
                "reply": f"Failed to generate Excel report: {str(e)}",
                "success": False,
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }

    async def _calculate_cogs_from_orders(self, db, start_dt, end_dt) -> float:
        """
        Calculate COGS from recipe BOM and order items

        Args:
            db: MongoDB database
            start_dt: Start datetime
            end_dt: End datetime

        Returns:
            Total COGS in rupees
        """
        try:
            # Get all orders in date range with items
            orders_cursor = db.orders.find({
                "order_date": {"$gte": start_dt, "$lte": end_dt},
                "status": {"$nin": ["cancelled", "CANCELLED"]}
            })

            # Get all recipes (BOM)
            recipes_cursor = db.recipe_bom.find({})
            recipes = {r["menu_item_id"]: r async for r in recipes_cursor}

            # Get inventory for unit costs
            inventory_cursor = db.raw_material_inventory.find({})
            inventory = {i["material_id"]: i async for i in inventory_cursor}

            total_cogs = 0.0

            async for order in orders_cursor:
                for item in order.get("items", []):
                    menu_item_id = item.get("menu_item_id")
                    quantity = item.get("quantity", 1)

                    # Get recipe for this menu item
                    recipe = recipes.get(menu_item_id)
                    if not recipe:
                        continue

                    # Calculate COGS for this item
                    item_cogs = 0.0
                    for ingredient in recipe.get("ingredients", []):
                        material_id = ingredient.get("material_id")
                        qty_per_serving = ingredient.get("quantity_per_serving", 0)

                        # Get material cost from inventory
                        material = inventory.get(material_id)
                        if material:
                            unit_cost = material.get("unit_cost_inr", 0)  # in paise
                            item_cogs += (qty_per_serving * unit_cost * quantity)

                    total_cogs += item_cogs

            # Convert from paise to rupees
            return total_cogs / 100.0

        except Exception as e:
            logger.error(f"COGS calculation failed: {e}", exc_info=True)
            # Fallback to 35% estimate
            return 0.0

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
        user_id: str,
        output_format: str = 'text'
    ) -> dict:
        """
        Generate P&L using Skills API

        Steps:
        1. Filter data locally (backend from MongoDB)
        2. Convert to CSV and upload to container
        3. Get/upload skill
        4. Call Skills API with container
        5. For text format: Extract text output
        6. For excel format: Download file and return URL

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            user_id: User identifier
            output_format: 'text' (default) or 'excel'

        Returns:
            dict with reply, optional download_url/filename, usage
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
            logger.info(f"Calling Skills API to generate P&L in {output_format} format")

            # Build prompt based on format
            if output_format == 'text':
                prompt_text = f"Generate P&L report from {start_date} to {end_date} using the uploaded CSV data. Use text format (default)."
            else:
                prompt_text = f"Generate P&L report from {start_date} to {end_date} using the uploaded CSV data. Use excel format."

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
                            "text": prompt_text
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

            # 6. Handle response based on format
            if output_format == 'text':
                # Extract text output from response
                text_output = self._extract_text_output(response)

                if not text_output:
                    return {
                        "reply": "P&L generation failed. No text output found.",
                        "success": False,
                        "usage": {
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens
                        }
                    }

                # Return text table directly
                return {
                    "reply": text_output,
                    "success": True,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens
                    }
                }

            else:  # excel format
                # Extract file_id from response
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
                    "reply": f"P&L Excel report generated for {start_date} to {end_date}",
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

    def _extract_text_output(self, response) -> Optional[str]:
        """Extract text output from Skills API response (for text format P&L)"""
        try:
            text_parts = []
            for block in response.content:
                # Check bash_code_execution_tool_result for stdout
                if block.type == "bash_code_execution_tool_result":
                    content_item = block.content
                    if content_item.type == "bash_code_execution_result":
                        # Extract stdout text
                        if hasattr(content_item, 'content'):
                            for item in content_item.content:
                                if hasattr(item, 'text'):
                                    text_parts.append(item.text)
                # Also check for regular text blocks
                elif block.type == "text":
                    text_parts.append(block.text)

            # Join all text parts
            full_text = "\n".join(text_parts).strip()

            # Extract P&L table (everything before "SUCCESS:" line)
            if "SUCCESS:" in full_text:
                pnl_text = full_text.split("SUCCESS:")[0].strip()
                return pnl_text if pnl_text else None

            return full_text if full_text else None

        except Exception as e:
            logger.error(f"Failed to extract text output: {e}", exc_info=True)
        return None

    def _extract_file_id(self, response) -> Optional[str]:
        """Extract file_id from Skills API response (for excel format)"""
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
                "success": False,
                "usage": {"input_tokens": 0, "output_tokens": 0}
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
                "success": False,
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }

    async def _execute_profit_analysis_tool(self, tool_name: str, tool_input: dict) -> str:
        """
        Execute a profit analysis tool call and return result as JSON string

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool parameters from Claude

        Returns:
            JSON string with results or error
        """
        try:
            from app.services.profit_analysis_service import get_profit_analysis_service
            service = get_profit_analysis_service()

            if tool_name == "get_top_items":
                result = await service.get_top_items(
                    metric=tool_input["metric"],
                    period_days=tool_input.get("period_days"),
                    limit=tool_input.get("limit", 10),
                    order=tool_input.get("order", "desc"),
                    category=tool_input.get("category"),
                    start_date_str=tool_input.get("start_date_str"),
                    end_date_str=tool_input.get("end_date_str")
                )
                return json.dumps(result, default=str)

            elif tool_name == "get_item_details":
                result = await service.get_item_details(
                    item_name=tool_input["item_name"],
                    period_days=tool_input.get("period_days"),
                    start_date_str=tool_input.get("start_date_str"),
                    end_date_str=tool_input.get("end_date_str")
                )
                return json.dumps(result, default=str)

            elif tool_name == "get_ingredient_costs":
                result = await service.get_ingredient_costs(
                    period_days=tool_input.get("period_days"),
                    sort_by=tool_input.get("sort_by", "total_cost"),
                    limit=tool_input.get("limit", 10),
                    category=tool_input.get("category"),
                    start_date_str=tool_input.get("start_date_str"),
                    end_date_str=tool_input.get("end_date_str")
                )
                return json.dumps(result, default=str)

            elif tool_name == "compare_periods":
                result = await service.compare_periods(
                    period1_days=tool_input.get("period1_days"),
                    period2_days=tool_input.get("period2_days"),
                    period2_offset=tool_input.get("period2_offset"),
                    period1_start=tool_input.get("period1_start"),
                    period1_end=tool_input.get("period1_end"),
                    period2_start=tool_input.get("period2_start"),
                    period2_end=tool_input.get("period2_end"),
                    metric=tool_input["metric"],
                    item_name=tool_input.get("item_name"),
                    category=tool_input.get("category")
                )
                return json.dumps(result, default=str)

            elif tool_name == "identify_losses":
                result = await service.identify_losses(
                    category=tool_input.get("category"),
                    period_days=tool_input.get("period_days"),
                    min_margin_threshold=tool_input.get("min_margin_threshold", 25),
                    start_date_str=tool_input.get("start_date_str"),
                    end_date_str=tool_input.get("end_date_str")
                )
                return json.dumps(result, default=str)

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as e:
            logger.error(f"Profit analysis tool '{tool_name}' failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    async def _handle_profit_analysis_message(self, message: str, user_id: str) -> dict:
        """
        Handle profit analysis messages using Claude tool calling

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

        # System prompt for profit analysis context
        PROFIT_ANALYSIS_SYSTEM_PROMPT = (
            "You are a restaurant sales and performance analysis assistant. "
            "Analyze sales, revenue, profitability, costs, and losses at granular level (item, ingredient, category). "
            "Use the provided tools to query data from the restaurant's database. "
            "\n\n"
            "CRITICAL: DATE PARAMETER SELECTION\n"
            "- When the system provides month ranges in [System: ...] context, YOU MUST use start_date_str and end_date_str parameters\n"
            "- DO NOT use period_days when explicit dates are provided in the context\n"
            "- Example: If context says '2025-11-01 to 2025-11-30', use start_date_str='2025-11-01', end_date_str='2025-11-30'\n"
            "- Only use period_days for relative queries like 'last 30 days' without specific month names\n"
            "\n"
            "QUERY TYPE DETECTION:\n"
            "- Sales queries (volume/revenue focus): Emphasize quantity sold, revenue totals, sales trends\n"
            "- Profit queries (margin focus): Emphasize profit margins, COGS, profitability\n"
            "- Comparison queries: Use compare_periods tool with appropriate metrics\n"
            "\n"
            "METRIC SELECTION GUIDE:\n"
            "- 'Which item sold the most' → Use metric: volume (quantity sold)\n"
            "- 'Top revenue items' → Use metric: revenue (sales value)\n"
            "- 'Best margin items' → Use metric: margin (profitability %)\n"
            "- 'Most profitable' → Use metric: profit (absolute profit amount)\n"
            "\n"
            "MONTH-BASED QUERIES:\n"
            "- System automatically parses month names (November, Dec, etc.) and provides date ranges\n"
            "- When you see [System: ...] with month ranges, use those exact dates with start_date_str/end_date_str\n"
            "- For month comparisons, use compare_periods with period1_start/end and period2_start/end\n"
            "\n"
            "PRESENTATION GUIDELINES:\n"
            "- For SALES queries: Lead with volume and revenue, optionally show profit if relevant\n"
            "- For PROFIT queries: Lead with profit and margin, include COGS breakdown\n"
            "- For COMPARISON queries: Show both periods side-by-side with % changes and trends\n"
            "- Present data in clear, formatted tables using Markdown\n"
            "- Use **bold** for emphasis on key insights\n"
            "- For top/bottom lists, use numbered lists or tables\n"
            "- Always provide actionable insights, not just raw numbers\n"
            "- When showing trends, use emojis: 📈 (growing sales), 📉 (declining sales), ➡️ (stable)\n"
            "- Use emojis: 🏆 (top seller), 💰 (high revenue), 💚 (good margin), 🔴 (low margin)\n"
            "- Highlight problems with 🔴 and opportunities with 💚\n"
            "- For loss analysis, give overview first, offer to drill deeper\n"
            "\n"
            "DATA CONVENTIONS:\n"
            "- All monetary values from tools are in RUPEES (already converted from paise)\n"
            "- Display as ₹X,XXX with proper formatting\n"
            "- Margins are in percentage (e.g., 25.5%)\n"
            "- Target margins: Premium items >25%, Economy items >15%\n"
            "- Food cost target: <35% of revenue\n"
            "\n"
            "INTELLIGENCE:\n"
            "- Compare metrics to industry benchmarks when relevant\n"
            "- Identify trends and explain probable causes\n"
            "- For loss analysis, categorize by: pricing issues, cost issues, waste issues, volume issues\n"
            "- Suggest specific actions (e.g., 'Increase price by ₹10' not just 'optimize pricing')\n"
            "\n"
            "Be concise but thorough. Focus on actionable insights."
        )

        # Build API messages from history
        api_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in self._trim_history(history)
        ]

        # Parse month ranges if present in the message
        month_ranges = self._parse_month_from_message(message)
        if month_ranges:
            # Add context hint for Claude
            month_names = [m['month_name'] for m in month_ranges]
            context_note = f"\n\n[System: User is asking about {', '.join(month_names)}. "
            context_note += f"Month ranges parsed: {json.dumps(month_ranges, indent=2)}. "
            if len(month_ranges) == 2:
                context_note += f"For comparison: Use compare_periods with period1_start='{month_ranges[0]['start']}', period1_end='{month_ranges[0]['end']}', "
                context_note += f"period2_start='{month_ranges[1]['start']}', period2_end='{month_ranges[1]['end']}'.]"
            elif len(month_ranges) == 1:
                context_note += f"For single month analysis: Use get_item_details, get_top_items, or get_ingredient_costs with "
                context_note += f"start_date_str='{month_ranges[0]['start']}', end_date_str='{month_ranges[0]['end']}' (NOT period_days).]"
            else:
                context_note += f"Use tools with start_date_str/end_date_str parameters for these months.]"

            # Add to most recent user message
            if api_messages and api_messages[-1]["role"] == "user":
                api_messages[-1]["content"] += context_note
                logger.info(f"Month context added for {month_names}: {month_ranges}")

        try:
            # Initial call to Claude with tools
            response = self.client.messages.create(
                model=self.settings.CHATBOT_MODEL,
                max_tokens=2048,
                system=PROFIT_ANALYSIS_SYSTEM_PROMPT,
                tools=PROFIT_ANALYSIS_TOOLS,
                messages=api_messages,
            )

            # Agentic loop: keep processing until Claude stops calling tools
            while response.stop_reason == "tool_use":
                tool_results = []
                assistant_content = response.content

                # Execute all tool_use blocks in the response
                for block in response.content:
                    if block.type == "tool_use":
                        result_str = await self._execute_profit_analysis_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        })

                # Append assistant turn
                api_messages.append({
                    "role": "assistant",
                    "content": self._assistant_content_to_dicts(assistant_content),
                })

                # Append user turn with tool results
                api_messages.append({"role": "user", "content": tool_results})

                # Call Claude again with updated messages
                response = self.client.messages.create(
                    model=self.settings.CHATBOT_MODEL,
                    max_tokens=2048,
                    system=PROFIT_ANALYSIS_SYSTEM_PROMPT,
                    tools=PROFIT_ANALYSIS_TOOLS,
                    messages=api_messages,
                )

            # Extract final text reply
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
            logger.error(f"Profit analysis message handling failed: {e}", exc_info=True)
            return {
                "reply": "Sorry, I couldn't process that profit analysis query. Please try again.",
                "success": False,
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }

    async def process_message(self, user_id: str, message: str) -> dict:
        """
        Main entry point for processing user messages

        Cost optimization:
        1. Local intent detection (0 cost)
        2. Local date parsing (0 cost) for P&L
        3. LLM only if needed (clarification or general chat)

        Routing order:
        1. Profit analysis intent → tool calling (granular profit/loss analysis) [CHECKED FIRST - most specific]
        1.5. Inventory intent → tool calling (stock levels, reordering)
        2. P&L intent → script execution (comprehensive P&L statement)
        2.5. P&L follow-up → LLM analysis of P&L reports
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

        # Route 1: Profit analysis intent (CHECK FIRST - more specific than inventory)
        # Handles queries about performance, top items, margins, losses, trends
        if self._is_profit_analysis_intent(message):
            result = await self._handle_profit_analysis_message(message, user_id)
            history.append({"role": "assistant", "content": result["reply"]})
            _chat_history[user_id] = self._trim_history(history)
            return result

        # Route 1.5: Inventory intent (local keywords → Claude with tools)
        # Handles queries about stock levels, reordering, ingredient details
        if self._is_inventory_intent(message):
            result = await self._handle_inventory_message(message, user_id)
            history.append({"role": "assistant", "content": result["reply"]})
            _chat_history[user_id] = self._trim_history(history)
            return result

        # Route 2: P&L intent
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
                    "success": True,
                    "usage": {"input_tokens": 0, "output_tokens": 0}
                }

            # Check if user wants Excel format
            if self._wants_excel_format(message):
                # Generate Excel file
                result = await self._generate_pnl_excel(
                    start_date=dates['start'],
                    end_date=dates['end']
                )
            else:
                # Default: Generate text table only (no files)
                result = await self._generate_pnl_text_only(
                    start_date=dates['start'],
                    end_date=dates['end']
                )

            # Store P&L context for follow-up questions (append to list)
            if user_id not in _pnl_context:
                _pnl_context[user_id] = []

            _pnl_context[user_id].append({
                "start_date": dates['start'],
                "end_date": dates['end'],
                "report_text": result.get("reply", ""),
                "timestamp": datetime.now().isoformat()
            })

            # Keep only last 5 P&L reports to avoid memory bloat
            if len(_pnl_context[user_id]) > 5:
                _pnl_context[user_id] = _pnl_context[user_id][-5:]

            # Add to history
            history.append({"role": "assistant", "content": result["reply"]})
            _chat_history[user_id] = self._trim_history(history)

            return result

        # Route 2.5: P&L follow-up questions (after P&L generation, before general chat)
        if self._is_pnl_followup(message, user_id):
            result = await self._handle_pnl_followup(message, user_id)
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
