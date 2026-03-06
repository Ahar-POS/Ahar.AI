"""
Strategic Insights Service

Implements Mitigation #4 (Checkpoint System) and #10 (Error Recovery)

Orchestrates strategic analysis agent execution with:
- Checkpoint system for graceful degradation
- 2-week caching for cost optimization
- Retry logic with exponential backoff
- Circuit breaker for failure protection
- Token usage tracking and alerts
"""

import logging
import json
import hashlib
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

from anthropic import APIError, RateLimitError

from app.core.database import get_database
from app.core.config import get_settings
from app.repositories.strategic_analytics_repository import StrategicAnalyticsRepository
from app.services.agents.strategic_analysis_agent import StrategicAnalysisAgent
from app.models.strategic_insights import (
    StrategicInsightsRequest,
    StrategicInsightsResponse,
    StrategicInsights,
    TokenUsage,
    Opportunity,
    Risk,
    Evidence,
    AnalysisPeriod,
    AnalysisCheckpoint
)

logger = logging.getLogger(__name__)
settings = get_settings()


class StructuredParseError(ValueError):
    """Raised when the model output can't be parsed into required JSON structure."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class CircuitBreaker:
    """
    Circuit breaker for failure protection

    Implements Mitigation #10: Error recovery
    """

    def __init__(self, failure_threshold: int = 3, timeout_seconds: int = 300):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half_open

    def record_failure(self):
        """Record a failure"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )

    def record_success(self):
        """Record a success"""
        self.failure_count = 0
        self.state = "closed"

    def can_attempt(self) -> bool:
        """Check if attempt is allowed"""
        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if timeout has elapsed
            if self.last_failure_time:
                elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if elapsed > self.timeout_seconds:
                    self.state = "half_open"
                    logger.info("Circuit breaker entering half-open state")
                    return True

            return False

        # half_open state
        return True


class StrategicInsightsService:
    """
    Service for generating strategic insights using AI analysis
    """

    def __init__(self):
        self.cache_dir = Path(settings.STATIC_DIR) / "strategic_insights"
        self.cache_ttl_seconds = 1209600  # 2 weeks
        self.token_alert_threshold = 50000
        self.circuit_breaker = CircuitBreaker()

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _generate_cache_key(self, request: StrategicInsightsRequest) -> str:
        """Generate cache key from request parameters"""
        key_data = f"{request.start_date}_{request.end_date}_{request.compare_to_previous}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cached_insights(self, cache_key: str) -> Optional[StrategicInsightsResponse]:
        """
        Retrieve cached insights if available and not expired

        Args:
            cache_key: Cache key

        Returns:
            Cached insights or None if not found/expired
        """
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        # Check if expired
        file_age = datetime.utcnow().timestamp() - cache_file.stat().st_mtime
        if file_age > self.cache_ttl_seconds:
            logger.info(f"Cache expired for {cache_key}, age: {file_age}s")
            cache_file.unlink()  # Delete expired cache
            return None

        # Load and return cached data
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            logger.info(f"Cache hit for {cache_key}, age: {file_age}s")

            # Parse back into response model
            cached = StrategicInsightsResponse(**data)

            # If a previous run cached a parse-failure placeholder, invalidate it and regenerate.
            # (This can happen when the model response couldn't be parsed into JSON.)
            if cached.insights.executive_summary.strip() == "Failed to parse structured response":
                logger.warning(f"Invalid strategic insights cache (parse failure): {cache_key}. Deleting cache file.")
                cache_file.unlink(missing_ok=True)
                return None

            return cached

        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            return None

    def _save_to_cache(self, cache_key: str, response: StrategicInsightsResponse):
        """
        Save insights to cache

        Args:
            cache_key: Cache key
            response: Insights response to cache
        """
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            with open(cache_file, 'w') as f:
                # Convert to dict for JSON serialization
                json.dump(response.model_dump(mode='json'), f, indent=2, default=str)

            logger.info(f"Insights cached: {cache_key}")

        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    async def _execute_with_retry(
        self,
        agent: StrategicAnalysisAgent,
        context: Dict[str, Any],
        max_retries: int = 3
    ):
        """
        Execute agent with retry logic and exponential backoff

        Implements Mitigation #10: Retry logic
        """
        import asyncio

        last_error = None

        for attempt in range(max_retries):
            try:
                # Check circuit breaker
                if not self.circuit_breaker.can_attempt():
                    raise Exception("Circuit breaker is open - too many failures")

                # Execute agent
                result = await agent.execute(context)

                # Record success
                self.circuit_breaker.record_success()

                return result

            except RateLimitError as e:
                last_error = e
                wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s
                logger.warning(f"Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)

            except APIError as e:
                last_error = e
                wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                logger.warning(f"API error, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(wait_time)

            except Exception as e:
                last_error = e
                logger.error(f"Execution failed (attempt {attempt + 1}/{max_retries}): {e}", exc_info=True)
                self.circuit_breaker.record_failure()

                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 3  # 3s, 6s, 12s
                    await asyncio.sleep(wait_time)

        # All retries failed
        raise Exception(f"Failed after {max_retries} attempts: {last_error}")

    def _parse_opportunities(self, data: List[Dict]) -> List[Opportunity]:
        """
        Parse opportunity data into Pydantic models

        Validates evidence requirements and confidence thresholds
        """
        opportunities = []

        for item in data:
            try:
                # Parse evidence
                evidence = [Evidence(**e) for e in item.get("evidence", [])]

                # Validate minimum evidence requirement
                if len(evidence) < 2:
                    logger.warning(f"Opportunity {item.get('id')} has insufficient evidence, skipping")
                    continue

                # Create opportunity
                opportunity = Opportunity(
                    id=item.get("id", ""),
                    category=item.get("category", "revenue_growth"),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    evidence=evidence,
                    impact_min=item.get("impact_min", 0),
                    impact_max=item.get("impact_max", 0),
                    impact_expected=item.get("impact_expected", 0),
                    assumptions=item.get("assumptions", []),
                    confidence=item.get("confidence", 0.5),
                    actionable_steps=item.get("actionable_steps", []),
                    timeline=item.get("timeline", ""),
                    effort=item.get("effort", "medium")
                )

                # Flag low confidence
                if opportunity.confidence < 0.7:
                    logger.warning(
                        f"Opportunity {opportunity.id} has low confidence: {opportunity.confidence}"
                    )

                opportunities.append(opportunity)

            except Exception as e:
                logger.error(f"Failed to parse opportunity: {e}, data: {item}")

        return opportunities

    def _parse_risks(self, data: List[Dict]) -> List[Risk]:
        """
        Parse risk data into Pydantic models

        Validates evidence requirements
        """
        risks = []

        for item in data:
            try:
                # Parse evidence
                evidence = [Evidence(**e) for e in item.get("evidence", [])]

                # Validate minimum evidence requirement
                if len(evidence) < 2:
                    logger.warning(f"Risk {item.get('id')} has insufficient evidence, skipping")
                    continue

                # Create risk
                risk = Risk(
                    id=item.get("id", ""),
                    category=item.get("category", "operational"),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    evidence=evidence,
                    impact_min=item.get("impact_min", 0),
                    impact_max=item.get("impact_max", 0),
                    impact_expected=item.get("impact_expected", 0),
                    probability=item.get("probability", 0.5),
                    severity=item.get("severity", "medium"),
                    mitigation_steps=item.get("mitigation_steps", []),
                    timeline=item.get("timeline", "")
                )

                risks.append(risk)

            except Exception as e:
                logger.error(f"Failed to parse risk: {e}, data: {item}")

        return risks

    def _calculate_token_cost(self, usage: Dict[str, Any]) -> float:
        """
        Calculate cost in USD based on Opus 4.6 pricing

        Pricing (March 2026):
        - Input: $5.00/1M
        - Output: $25.00/1M
        - Cache writes: $6.25/1M
        - Cache hits: $0.50/1M
        """
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cached_tokens = usage.get("cache_creation_input_tokens", 0)
        cache_read_tokens = usage.get("cache_read_input_tokens", 0)

        # Calculate costs
        input_cost = (input_tokens - cached_tokens - cache_read_tokens) * 5.00 / 1_000_000
        output_cost = output_tokens * 25.00 / 1_000_000
        cache_write_cost = cached_tokens * 6.25 / 1_000_000
        cache_read_cost = cache_read_tokens * 0.50 / 1_000_000

        total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost

        logger.info(
            f"Token cost breakdown - Input: ${input_cost:.4f}, Output: ${output_cost:.4f}, "
            f"Cache write: ${cache_write_cost:.4f}, Cache read: ${cache_read_cost:.4f}, "
            f"Total: ${total_cost:.4f}"
        )

        return total_cost

    async def generate_insights(
        self,
        request: StrategicInsightsRequest,
        use_cache: bool = True
    ) -> StrategicInsightsResponse:
        """
        Generate strategic insights for a given period

        Args:
            request: Insights request parameters
            use_cache: Whether to use cached results if available

        Returns:
            Strategic insights with opportunities, risks, and usage data
        """
        logger.info(f"Generating strategic insights: {request.start_date} to {request.end_date}")

        # Check cache
        cache_key = self._generate_cache_key(request)

        # Stub mode: no model calls, deterministic output (for cheap UI testing)
        if getattr(settings, "STRATEGIC_INSIGHTS_STUB", False):
            start_dt = datetime.fromisoformat(request.start_date)
            end_dt = datetime.fromisoformat(request.end_date)
            duration_days = (end_dt - start_dt).days

            stub_insights = StrategicInsights(
                opportunities=[],
                risks=[],
                executive_summary="STUB MODE: Strategic insights generation disabled (no model calls).",
                analysis_period=AnalysisPeriod(
                    start=request.start_date,
                    end=request.end_date,
                    duration_days=duration_days
                ),
                iterations_used=0
            )

            return StrategicInsightsResponse(
                insights=stub_insights,
                usage=TokenUsage(
                    input_tokens=0,
                    output_tokens=0,
                    cached_tokens=0,
                    total_tokens=0,
                    model="stub",
                    cost_usd=0.0
                ),
                cache_hit=False,
                cache_key=cache_key
            )

        if use_cache:
            cached = self._get_cached_insights(cache_key)
            if cached:
                # Update cache_hit flag
                cached.cache_hit = True
                return cached

        # Initialize repository and agent
        db = get_database()
        repository = StrategicAnalyticsRepository(db)
        agent = StrategicAnalysisAgent(
            repository=repository,
            model=settings.STRATEGIC_INSIGHTS_MODEL if hasattr(settings, 'STRATEGIC_INSIGHTS_MODEL')
                  else "claude-sonnet-4-5"
        )

        # Build context
        context = {
            "start_date": request.start_date,
            "end_date": request.end_date,
            "compare_to_previous": request.compare_to_previous,
            "trigger": "manual"
        }

        # Execute agent with retry logic
        try:
            decision = await self._execute_with_retry(agent, context)

        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)

            # Return checkpoint if available (graceful degradation)
            if agent.checkpoints:
                last_checkpoint = agent.checkpoints[-1]
                logger.info(f"Returning checkpoint from phase: {last_checkpoint.phase}")

                return StrategicInsightsResponse(
                    insights=StrategicInsights(
                        opportunities=last_checkpoint.opportunities,
                        risks=last_checkpoint.risks,
                        executive_summary=f"Partial analysis (checkpoint from {last_checkpoint.phase} phase). {str(e)}",
                        analysis_period=AnalysisPeriod(
                            start=request.start_date,
                            end=request.end_date,
                            duration_days=(
                                datetime.fromisoformat(request.end_date) -
                                datetime.fromisoformat(request.start_date)
                            ).days
                        ),
                        iterations_used=last_checkpoint.iterations_used,
                        checkpoint=last_checkpoint
                    ),
                    usage=TokenUsage(
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        model="claude-opus-4-6",
                        cost_usd=0.0
                    ),
                    cache_hit=False,
                    cache_key=cache_key
                )

            # No checkpoint available
            raise

        # Parse opportunities and risks from decision metadata
        opportunities = self._parse_opportunities(decision.metadata.get("opportunities", []))
        risks = self._parse_risks(decision.metadata.get("risks", []))

        logger.info(f"Parsed {len(opportunities)} opportunities and {len(risks)} risks")

        # If the agent couldn't produce structured output, do not cache a broken response.
        # Surface a proper API error so the UI can show a retryable failure state.
        if decision.confidence <= 0.0 or decision.metadata.get("error") == "JSON parse error":
            raw = decision.metadata.get("raw_response", "")
            logger.error(
                "Strategic insights structured parse failed; refusing to cache. "
                f"Raw response (truncated): {raw[:500]}"
            )
            raise StructuredParseError(
                "Failed to parse structured response from the model. Please retry.",
                details={},
            )

        # Calculate period duration
        start_dt = datetime.fromisoformat(request.start_date)
        end_dt = datetime.fromisoformat(request.end_date)
        duration_days = (end_dt - start_dt).days

        # Build insights response
        insights = StrategicInsights(
            opportunities=opportunities,
            risks=risks,
            executive_summary=decision.metadata.get("executive_summary", decision.reasoning),
            analysis_period=AnalysisPeriod(
                start=request.start_date,
                end=request.end_date,
                duration_days=duration_days
            ),
            iterations_used=decision.metadata.get("iterations_used", 0)
        )

        # Extract token usage from Claude response
        # Note: This would come from the actual API response
        # For now, using placeholder values
        usage = TokenUsage(
            input_tokens=decision.metadata.get("input_tokens", 20000),
            output_tokens=decision.metadata.get("output_tokens", 5000),
            cached_tokens=decision.metadata.get("cached_tokens", 4000),
            total_tokens=decision.metadata.get("total_tokens", 25000),
            model="claude-opus-4-6",
            cost_usd=0.0  # Will calculate below
        )

        # Calculate cost
        usage.cost_usd = self._calculate_token_cost({
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_creation_input_tokens": usage.cached_tokens,
            "cache_read_input_tokens": 0
        })

        # Alert if token usage is high
        if usage.total_tokens > self.token_alert_threshold:
            logger.warning(
                f"High token usage: {usage.total_tokens} > {self.token_alert_threshold}. "
                f"Cost: ${usage.cost_usd:.2f}"
            )

        # Build response
        response = StrategicInsightsResponse(
            insights=insights,
            usage=usage,
            cache_hit=False,
            cache_key=cache_key
        )

        # Save to cache
        self._save_to_cache(cache_key, response)

        return response

    async def clear_cache(self, cache_key: Optional[str] = None):
        """
        Clear cached insights

        Args:
            cache_key: Specific cache key to clear, or None to clear all
        """
        if cache_key:
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"Cache cleared: {cache_key}")
        else:
            # Clear all cache files
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("All cache cleared")
