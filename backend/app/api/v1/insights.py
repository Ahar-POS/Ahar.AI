"""
Insights API endpoints for AI-powered restaurant analysis.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from app.models.insights import InsightsRequest, InsightsResponseWithUsage
from app.models.strategic_insights import (
    StrategicInsightsRequest,
    StrategicInsightsResponse,
    InsightFeedback
)
from app.models.user import UserResponse, UserRole
from app.core.dependencies import get_current_user
from app.services.insights_service import insights_service
from app.services.strategic_insights_service import StrategicInsightsService, StructuredParseError
from app.utils.response import success_response, error_response

router = APIRouter(prefix="/insights", tags=["insights"])

# Initialize strategic insights service
strategic_insights_service = StrategicInsightsService()


@router.post("/generate", response_model=dict)
async def generate_insights(
    body: InsightsRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Generate AI-powered insights for restaurant operations (Admin only).

    Analyzes financial, inventory, and operational data to identify:
    - Financial losses and revenue leakage
    - Inventory waste and optimization opportunities
    - Operational inefficiencies and bottlenecks

    Returns structured insights with root causes, impacts, and recommendations.

    **Note:** Analysis may take 30-60 seconds. Results are cached for 24 hours.

    Args:
        body: Insights request with date range and scope
        current_user: Authenticated admin user

    Returns:
        Success response with insights data and token usage
    """
    # Admin-only access
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can generate insights"
        )

    try:
        # Generate insights
        result = await insights_service.generate_insights(
            start_date=body.start_date,
            end_date=body.end_date,
            scope=body.scope,
            user_id=current_user.id
        )

        # Format response
        response_data = {
            "insights": result.insights.model_dump(by_alias=False),
            "cache_key": result.insights.cache_key,
        }

        # Include token usage if available (not from cache)
        if result.usage:
            response_data["usage"] = {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            }

        return success_response(
            data=response_data,
            message="Insights generated successfully" if result.usage else "Insights retrieved from cache"
        )

    except StructuredParseError as e:
        return error_response(
            code="INVALID_REQUEST",
            message=str(e),
            details=getattr(e, "details", {}) or {}
        )
    except ValueError as e:
        return error_response(
            code="INVALID_REQUEST",
            message=str(e)
        )
    except Exception as e:
        return error_response(
            code="GENERATION_FAILED",
            message=f"Failed to generate insights: {str(e)}"
        )


@router.get("/cached/{cache_key}", response_model=dict)
async def get_cached_insights(
    cache_key: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Retrieve cached insights by cache key (Admin only).

    Args:
        cache_key: Cache key identifier
        current_user: Authenticated admin user

    Returns:
        Cached insights or error if not found/expired
    """
    # Admin-only access
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can access insights"
        )

    try:
        # Retrieve from cache (returns (insights, usage) or None)
        cached = insights_service._get_cached_insights(cache_key)

        if not cached:
            return error_response(
                code="NOT_FOUND",
                message="Cached insights not found or expired"
            )

        insights, usage = cached
        response_data = {"insights": insights.model_dump(by_alias=False)}
        if usage:
            response_data["usage"] = {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            }
        return success_response(
            data=response_data,
            message="Cached insights retrieved successfully"
        )

    except Exception as e:
        return error_response(
            code="RETRIEVAL_FAILED",
            message=f"Failed to retrieve cached insights: {str(e)}"
        )


# ===== Strategic Insights Endpoints (Agent-based) =====


@router.get("/strategic/latest", response_model=dict)
async def get_latest_strategic_insights(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get the most recently cached strategic insights (Admin only).

    Used so the Insights tab can display the last generated insight automatically
    without requiring the user to choose a date range first.

    Returns:
        Latest cached insights and usage, or 404 if none exist.
    """
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can access strategic insights"
        )

    result = strategic_insights_service.get_latest_cached_insights()
    if not result:
        return error_response(
            code="NOT_FOUND",
            message="No cached strategic insights found. Generate insights for a date range first."
        )

    response_data = {
        "insights": result.insights.model_dump(mode='json'),
        "usage": result.usage.model_dump(mode='json'),
        "cache_hit": True,
        "cache_key": result.cache_key or ""
    }
    return success_response(
        data=response_data,
        message="Latest strategic insights retrieved"
    )


@router.post("/strategic", response_model=dict)
async def generate_strategic_insights(
    body: StrategicInsightsRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Generate strategic insights using AI agent analysis (Admin only).

    **Agent-based Analysis:**
    - Uses Claude Opus 4.6 for deep reasoning and iterative investigation
    - Identifies 3-7 business opportunities with impact estimates
    - Identifies 2-5 critical risks with probability and severity
    - Provides evidence-based insights with statistical validation

    **Analysis Duration:** 2-5 minutes (runs iteratively with multiple data queries)

    **Caching:** Results cached for 2 weeks. Subsequent requests return instantly.

    **Cost:** ~$0.21 per analysis with prompt caching (first run: ~$0.23)

    Args:
        body: Strategic insights request with date range
        current_user: Authenticated admin user

    Returns:
        Success response with opportunities, risks, and usage data
    """
    # Admin-only access
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can generate strategic insights"
        )

    try:
        # Generate strategic insights
        result = await strategic_insights_service.generate_insights(
            request=body,
            use_cache=True
        )

        # Format response
        response_data = {
            "insights": result.insights.model_dump(mode='json'),
            "usage": result.usage.model_dump(mode='json'),
            "cache_hit": result.cache_hit,
            "cache_key": result.cache_key
        }

        message = "Strategic insights retrieved from cache" if result.cache_hit \
                  else "Strategic insights generated successfully"

        return success_response(
            data=response_data,
            message=message
        )

    except StructuredParseError as e:
        return error_response(
            code="INVALID_REQUEST",
            message=str(e),
            details=getattr(e, "details", {}) or {}
        )
    except ValueError as e:
        return error_response(
            code="INVALID_REQUEST",
            message=str(e)
        )
    except Exception as e:
        return error_response(
            code="GENERATION_FAILED",
            message=f"Failed to generate strategic insights: {str(e)}"
        )


@router.post("/strategic/{insight_id}/feedback", response_model=dict)
async def submit_insight_feedback(
    insight_id: str,
    feedback: InsightFeedback,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Submit feedback on a strategic insight (Admin only).

    Implements Mitigation #8: Human feedback loop for continuous improvement

    Feedback helps improve future insights by tracking:
    - Which insights were helpful
    - Which insights led to actions
    - Actual impact vs predicted impact

    Args:
        insight_id: ID of the opportunity or risk
        feedback: Feedback data
        current_user: Authenticated admin user

    Returns:
        Success response
    """
    # Admin-only access
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can submit feedback"
        )

    try:
        # TODO: Store feedback in database for analysis
        # For now, just log it
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Insight feedback: {insight_id} - "
            f"Helpful: {feedback.helpful}, "
            f"Action taken: {feedback.action_taken}, "
            f"Actual impact: {feedback.actual_impact}"
        )

        return success_response(
            data={"insight_id": insight_id},
            message="Feedback submitted successfully"
        )

    except Exception as e:
        return error_response(
            code="SUBMISSION_FAILED",
            message=f"Failed to submit feedback: {str(e)}"
        )


@router.delete("/strategic/cache/{cache_key}", response_model=dict)
async def clear_strategic_cache(
    cache_key: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Clear cached strategic insights (Admin only).

    Useful for forcing a fresh analysis when:
    - Data has changed significantly
    - Previous analysis had errors
    - Testing new features

    Args:
        cache_key: Cache key to clear, or "all" to clear everything
        current_user: Authenticated admin user

    Returns:
        Success response
    """
    # Admin-only access
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can clear cache"
        )

    try:
        if cache_key == "all":
            await strategic_insights_service.clear_cache(cache_key=None)
            message = "All strategic insights cache cleared"
        else:
            await strategic_insights_service.clear_cache(cache_key=cache_key)
            message = f"Cache cleared for key: {cache_key}"

        return success_response(
            data={"cache_key": cache_key},
            message=message
        )

    except Exception as e:
        return error_response(
            code="CLEAR_FAILED",
            message=f"Failed to clear cache: {str(e)}"
        )
