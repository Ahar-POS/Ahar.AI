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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import httpx
from anthropic import Anthropic
from app.core.config import get_settings
from app.services.skill_uploader import SkillUploader
from app.services.data_loader import DataLoader

logger = logging.getLogger(__name__)

# In-memory conversation history per user
_chat_history: Dict[str, List[Dict[str, str]]] = {}

# Cap history to avoid token limits
MAX_HISTORY_MESSAGES = 20

# System prompt for general chat
SYSTEM_PROMPT = """You are a helpful restaurant operations advisor. Answer questions about restaurant financials, demand forecasting, and inventory management in general terms only. Do not reference or use any specific restaurant data, figures, or databases. Keep answers concise and in plain text."""


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

    async def process_message(self, user_id: str, message: str) -> dict:
        """
        Main entry point for processing user messages

        Cost optimization:
        1. Local intent detection (0 cost)
        2. Local date parsing (0 cost)
        3. LLM only if needed (clarification or general chat)

        Args:
            user_id: User identifier
            message: User message

        Returns:
            dict with reply, optional download_url, usage stats
        """
        # Add to history
        history = self._get_history(user_id)
        history.append({"role": "user", "content": message.strip()})

        # Step 1: Check if P&L intent (0 cost)
        if not self._is_pnl_intent(message):
            # General chat
            result = await self._general_chat(message, user_id)
            history.append({"role": "assistant", "content": result["reply"]})
            _chat_history[user_id] = self._trim_history(history)
            return result

        # Step 2: Extract dates locally (0 cost)
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

        # Step 3: Generate P&L via Skills API
        result = await self._generate_pnl_via_skills(
            start_date=dates['start'],
            end_date=dates['end'],
            user_id=user_id
        )

        # Add to history
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
