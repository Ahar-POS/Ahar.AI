"""
Insights service with Skills API integration for comprehensive restaurant analysis.

Generates AI-powered insights for financial losses, inventory waste, and operational
inefficiencies using MongoDB data and Anthropic Skills API.
"""

import logging
import json
import hashlib
from datetime import datetime
from app.utils.timezone import now_ist
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import httpx
from anthropic import Anthropic

from app.core.config import get_settings
from app.services.analytics_aggregator import analytics_aggregator
from app.services.skill_uploader import SkillUploader
from app.models.insights import (
    InsightsResponse,
    InsightsResponseWithUsage,
    TokenUsage,
    Issue,
    FinancialSummary,
    InventorySummary,
    OperationalSummary,
    AnalysisPeriod
)

logger = logging.getLogger(__name__)


class InsightsService:
    """AI-powered insights generation service"""

    def __init__(self):
        """Initialize insights service"""
        self.settings = get_settings()
        self.client = None
        self._skill_uploader = None

        # Initialize Anthropic client if API key is configured
        if self.settings.CLAUDE_API_KEY and self.settings.CLAUDE_API_KEY.strip():
            http_client = httpx.Client(
                timeout=httpx.Timeout(self.settings.CHATBOT_TIMEOUT, connect=10.0)
            )
            self.client = Anthropic(
                api_key=self.settings.CLAUDE_API_KEY.strip(),
                http_client=http_client
            )

        # Ensure cache directory exists
        self.cache_dir = Path(self.settings.INSIGHTS_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def skill_uploader(self):
        """Lazy initialization of SkillUploader"""
        if self._skill_uploader is None and self.client:
            self._skill_uploader = SkillUploader(
                client=self.client,
                skills_path=Path(self.settings.SKILLS_PATH)
            )
        return self._skill_uploader

    def _generate_cache_key(
        self,
        start_date: str,
        end_date: str,
        scope: List[str]
    ) -> str:
        """Generate cache key for insights"""
        scope_str = '_'.join(sorted(scope))
        key_str = f"{start_date}_{end_date}_{scope_str}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cached_insights(
        self, cache_key: str
    ) -> Optional[Tuple[InsightsResponse, Optional[TokenUsage]]]:
        """
        Retrieve cached insights and persisted token usage if available and not expired.

        Returns:
            (insights, usage) or None if not found/expired. usage is from the first run that populated the cache.
        """
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        # Check if cache is expired (TTL from settings)
        file_age = now_ist().timestamp() - cache_file.stat().st_mtime
        if file_age > self.settings.INSIGHTS_CACHE_TTL:
            logger.info(f"Cache expired for key: {cache_key}")
            cache_file.unlink()  # Delete expired cache
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            logger.info(f"Cache hit for key: {cache_key}")

            # New format: {"insights": {...}, "usage": {"input_tokens": n, "output_tokens": m}}
            if "insights" in data:
                insights = InsightsResponse(**data["insights"])
                usage = None
                if data.get("usage") and isinstance(data["usage"], dict):
                    usage = TokenUsage(
                        input_tokens=data["usage"].get("input_tokens", 0),
                        output_tokens=data["usage"].get("output_tokens", 0),
                        total_cost=data["usage"].get("total_cost"),
                    )
                return (insights, usage)

            # Legacy format: file is the insights object directly (no usage persisted)
            return (InsightsResponse(**data), None)
        except Exception as e:
            logger.error(f"Failed to load cached insights: {e}")
            return None

    def _save_to_cache(
        self, cache_key: str, insights: InsightsResponse, usage: Optional[TokenUsage] = None
    ):
        """Save insights and token usage from the first run to cache file."""
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            payload = {
                "insights": insights.model_dump(),
                "usage": (
                    {
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "total_cost": usage.total_cost,
                    }
                    if usage
                    else None
                ),
            }
            with open(cache_file, 'w') as f:
                json.dump(payload, f, default=str)
            logger.info(f"Cached insights with key: {cache_key}")
        except Exception as e:
            logger.error(f"Failed to cache insights: {e}")

    async def _prepare_csv_data(
        self,
        start_date: str,
        end_date: str,
        scope: List[str]
    ) -> Dict[str, str]:
        """
        Aggregate MongoDB data and convert to CSV strings.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            scope: List of analysis scopes

        Returns:
            Dictionary mapping scope to CSV string
        """
        # Aggregate data
        data = await analytics_aggregator.aggregate_all_data(
            start_date=start_date,
            end_date=end_date,
            scope=scope
        )

        # Convert DataFrames to CSV strings
        csv_data = {}
        for scope_name, df in data.items():
            if df.empty:
                logger.warning(f"No data for scope: {scope_name}")
                csv_data[scope_name] = ""
            else:
                csv_data[scope_name] = df.to_csv(index=False)
                logger.info(f"Prepared CSV for {scope_name}: {len(df)} rows")

        return csv_data

    def _parse_insights_response(self, response_text: str) -> Dict:
        """
        Parse AI response to extract structured insights.

        Args:
            response_text: Raw AI response text

        Returns:
            Parsed insights dictionary
        """
        try:
            # Try to extract JSON from response
            # AI should return pure JSON, but handle potential wrapping
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in response")

            json_str = response_text[start_idx:end_idx]
            return json.loads(json_str)

        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            # Return default structure
            return {
                "critical_issues": [],
                "financial_summary": {
                    "total_revenue": 0,
                    "revenue_loss": 0,
                    "avg_order_value": 0,
                    "cancelled_orders_count": 0,
                    "discount_amount": 0
                },
                "inventory_summary": {
                    "total_stock_value": 0,
                    "waste_value": 0,
                    "low_stock_items": 0,
                    "near_expiry_items": 0
                },
                "operational_summary": {
                    "avg_kitchen_time_mins": 0.0,
                    "table_turnover_rate": 0.0,
                    "staff_efficiency_score": 0.0,
                    "orders_completed": 0
                },
                "estimated_monthly_savings": 0
            }

    async def generate_insights(
        self,
        start_date: str,
        end_date: str,
        scope: List[str] = None,
        user_id: str = "admin"
    ) -> InsightsResponseWithUsage:
        """
        Generate comprehensive AI insights for restaurant operations.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            scope: List of analysis scopes (financial, inventory, operational)
            user_id: User requesting insights

        Returns:
            Insights response with token usage information

        Raises:
            ValueError: If API key not configured or dates invalid
            Exception: If AI analysis fails
        """
        if not self.client:
            raise ValueError("Claude API key not configured")

        if scope is None:
            scope = ['financial', 'inventory', 'operational']

        # Generate cache key
        cache_key = self._generate_cache_key(start_date, end_date, scope)

        # Check cache first
        cached = self._get_cached_insights(cache_key)
        if cached:
            insights, usage = cached
            return InsightsResponseWithUsage(insights=insights, usage=usage)

        logger.info(f"Generating insights for {start_date} to {end_date}, scope: {scope}")

        # Step 1: Prepare CSV data from MongoDB
        csv_data = await self._prepare_csv_data(start_date, end_date, scope)

        # Step 2: For MVP, we'll use direct Messages API instead of Skills API
        # Skills API integration can be added later for cost optimization
        logger.info("Calling AI for insights generation...")

        # Construct analysis prompt
        prompt = self._construct_analysis_prompt(csv_data, start_date, end_date)

        try:
            # Call Claude API (without Skills for MVP - using direct messages)
            response = self.client.messages.create(
                model=self.settings.INSIGHTS_MODEL,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Parse response
            response_text = response.content[0].text
            parsed_insights = self._parse_insights_response(response_text)

            # Create insights response
            insights = InsightsResponse(
                critical_issues=[Issue(**issue) for issue in parsed_insights.get('critical_issues', [])],
                financial_summary=FinancialSummary(**parsed_insights.get('financial_summary', {})),
                inventory_summary=InventorySummary(**parsed_insights.get('inventory_summary', {})),
                operational_summary=OperationalSummary(**parsed_insights.get('operational_summary', {})),
                estimated_monthly_savings=parsed_insights.get('estimated_monthly_savings', 0),
                analysis_period=AnalysisPeriod(start=start_date, end=end_date),
                generated_at=now_ist(),
                cache_key=cache_key
            )

            # Track token usage
            usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_cost=None  # Calculate if needed
            )

            # Cache the results and persist usage so cache hits can show it
            self._save_to_cache(cache_key, insights, usage)

            return InsightsResponseWithUsage(insights=insights, usage=usage)

        except Exception as e:
            logger.error(f"Failed to generate insights: {e}")
            raise

    def _construct_analysis_prompt(
        self,
        csv_data: Dict[str, str],
        start_date: str,
        end_date: str
    ) -> str:
        """Construct analysis prompt for AI"""
        prompt = f"""You are a restaurant operations analyst. Analyze the following data for the period {start_date} to {end_date} and identify critical issues with root causes and actionable recommendations.

IMPORTANT: Return ONLY a valid JSON object with this exact structure (no markdown, no explanations):

{{
  "critical_issues": [
    {{
      "id": "unique_id",
      "category": "financial|inventory|operational",
      "title": "Brief title",
      "root_cause": "Why this is happening",
      "impact": "₹X/month or X% loss",
      "recommendation": "Specific actionable steps",
      "priority": "high|medium|low",
      "estimated_savings": 0
    }}
  ],
  "financial_summary": {{
    "total_revenue": 0,
    "revenue_loss": 0,
    "avg_order_value": 0,
    "cancelled_orders_count": 0,
    "discount_amount": 0
  }},
  "inventory_summary": {{
    "total_stock_value": 0,
    "waste_value": 0,
    "low_stock_items": 0,
    "near_expiry_items": 0
  }},
  "operational_summary": {{
    "avg_kitchen_time_mins": 0.0,
    "table_turnover_rate": 0.0,
    "staff_efficiency_score": 7.0,
    "orders_completed": 0
  }},
  "estimated_monthly_savings": 0
}}

DATA:

"""

        for scope_name, csv_content in csv_data.items():
            if csv_content:
                prompt += f"\n{scope_name.upper()} DATA:\n{csv_content}\n"

        prompt += "\nAnalyze the data and return ONLY the JSON object."

        return prompt


# Singleton instance
insights_service = InsightsService()
