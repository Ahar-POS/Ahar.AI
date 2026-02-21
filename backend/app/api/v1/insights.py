"""
Insights API endpoints for AI-powered restaurant analysis.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from app.models.insights import InsightsRequest, InsightsResponseWithUsage
from app.models.user import UserResponse, UserRole
from app.core.dependencies import get_current_user
from app.services.insights_service import insights_service
from app.utils.response import success_response, error_response

router = APIRouter(prefix="/insights", tags=["insights"])


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
        # Retrieve from cache
        cached = insights_service._get_cached_insights(cache_key)

        if not cached:
            return error_response(
                code="NOT_FOUND",
                message="Cached insights not found or expired"
            )

        return success_response(
            data=cached.model_dump(by_alias=False),
            message="Cached insights retrieved successfully"
        )

    except Exception as e:
        return error_response(
            code="RETRIEVAL_FAILED",
            message=f"Failed to retrieve cached insights: {str(e)}"
        )
