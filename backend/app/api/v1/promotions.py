"""
Promotions API endpoints.

Handles promotional campaign management operations.
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.models.user import UserResponse
from app.services.promotion_service import get_promotion_service
from app.utils.response import success_response

router = APIRouter(prefix="/promotions", tags=["Promotions"])


@router.get("/active", response_model=dict)
async def get_active_promotions(
    current_user: UserResponse = Depends(get_current_user),
    promotion_service=Depends(get_promotion_service)
):
    """
    Get all active promotions for the current user's restaurant.

    Args:
        current_user: Current authenticated user (auto-injected).
        promotion_service: Promotion service instance.

    Returns:
        List of active promotions matching today's date range.
    """
    promos = await promotion_service.get_active_promotions(current_user.restaurant_id)
    return success_response(data=promos, message="Active promotions")
