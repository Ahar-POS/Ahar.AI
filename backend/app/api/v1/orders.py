"""
Orders API endpoints.

Handles order management operations for waiters and kitchen staff.
"""

import asyncio
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.core.dependencies import get_current_user
from app.models.order import (
    OrderCreate,
    OrderCreateRequest,
    OrderItem,
    OrderResponse,
    OrderStatus,
)
from app.models.user import UserResponse
from app.repositories.menu_repository import MenuRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.table_repository import TableRepository
from app.services.order_service import OrderService, OrderServiceError
from app.utils.response import error_response, success_response

router = APIRouter(prefix="/orders", tags=["Orders"])


def get_order_repository(
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> OrderRepository:
    """Dependency to get order repository instance."""
    return OrderRepository(db)


def get_menu_repository(
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> MenuRepository:
    """Dependency to get menu repository instance."""
    return MenuRepository(db)


def get_table_repository(
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> TableRepository:
    """Dependency to get table repository instance."""
    return TableRepository(db)


def get_order_service(
    order_repo: OrderRepository = Depends(get_order_repository),
    menu_repo: MenuRepository = Depends(get_menu_repository),
    table_repo: TableRepository = Depends(get_table_repository),
) -> OrderService:
    """Dependency to get order service instance."""
    return OrderService(order_repo, menu_repo, table_repo)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_request: OrderCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
):
    """
    Create a new order.
    
    The restaurant_id is automatically set from the authenticated user.
    The order is created in DRAFT status and must be sent to kitchen.
    
    Args:
        order_request: Order creation request from frontend.
        current_user: Current authenticated user (auto-injected).
        order_service: Order service instance.
        
    Returns:
        Created order data.
        
    Raises:
        HTTPException: If creation fails or validation errors.
    """
    # Auto-assign restaurant_id if missing (for existing users who haven't been migrated)
    if not current_user.restaurant_id:
        import uuid
        from app.core.database import get_database
        
        # Auto-assign restaurant_id to user
        db = get_database()
        new_restaurant_id = str(uuid.uuid4())
        
        # Update user in database directly
        try:
            from bson import ObjectId
            result = await db.users.update_one(
                {"_id": ObjectId(current_user.id)},
                {"$set": {"restaurant_id": new_restaurant_id}}
            )
            if result.modified_count > 0:
                # Update current_user object for this request
                current_user.restaurant_id = new_restaurant_id
            else:
                raise Exception("User update failed - no documents modified")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response(
                    code="RESTAURANT_ID_ASSIGNMENT_FAILED",
                    message="Failed to assign restaurant. Please contact support."
                )
            )
    
    try:
        # Convert OrderCreateRequest to OrderCreate format for service
        # The service will handle validation and snapshot creation
        from app.models.order import OrderItem, OrderItemStatus, OrderStatus
        order_items = [
            OrderItem(
                menu_item_id=item.menu_item_id,
                name_snapshot="PLACEHOLDER",  # Will be replaced by service
                price_snapshot=0,  # Will be replaced by service
                quantity=item.quantity,
                notes=item.notes,
                status=OrderItemStatus.PENDING,
            )
            for item in order_request.items
        ]
        
        order_data = OrderCreate(
            restaurant_id=current_user.restaurant_id,
            order_type=order_request.order_type,
            table_id=order_request.table_id,
            status=OrderStatus.DRAFT,
            items=order_items,
            total_amount=0,  # Will be calculated by service
            created_by_user_id=current_user.id,
        )
        
        # Create order
        order = await order_service.create_order(
            order_data,
            current_user.restaurant_id
        )
        
        order_response = await order_service.to_order_response(order)
        return success_response(
            data=order_response.model_dump(),
            message="Order created successfully"
        )
    except OrderServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                code=e.code,
                message=e.message
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(
                code="CREATION_FAILED",
                message=f"Failed to create order: {str(e)}"
            )
        )


@router.post("/{order_id}/send-to-kitchen", response_model=dict)
async def send_order_to_kitchen(
    order_id: str,
    current_user: UserResponse = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
):
    """
    Send order to kitchen (transition DRAFT → SENT_TO_KITCHEN).
    
    Args:
        order_id: Order database ID.
        current_user: Current authenticated user (auto-injected).
        order_service: Order service instance.
        
    Returns:
        Updated order data.
        
    Raises:
        HTTPException: If order not found or invalid transition.
    """
    if not current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                code="NO_RESTAURANT",
                message="User is not associated with a restaurant"
            )
        )
    
    try:
        order = await order_service.send_to_kitchen(
            order_id,
            current_user.restaurant_id
        )
        
        order_response = await order_service.to_order_response(order)
        return success_response(
            data=order_response.model_dump(),
            message="Order sent to kitchen successfully"
        )
    except OrderServiceError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=error_response(
                code=e.code,
                message=e.message
            )
        )


@router.post("/{order_id}/start-cooking", response_model=dict)
async def start_cooking_order(
    order_id: str,
    current_user: UserResponse = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
):
    """
    Start cooking order (transition SENT_TO_KITCHEN → IN_PROGRESS).
    
    Args:
        order_id: Order database ID.
        current_user: Current authenticated user (auto-injected).
        order_service: Order service instance.
        
    Returns:
        Updated order data.
        
    Raises:
        HTTPException: If order not found or invalid transition.
    """
    if not current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                code="NO_RESTAURANT",
                message="User is not associated with a restaurant"
            )
        )
    
    try:
        order = await order_service.start_cooking(
            order_id,
            current_user.restaurant_id
        )
        
        order_response = await order_service.to_order_response(order)
        return success_response(
            data=order_response.model_dump(),
            message="Order started cooking successfully"
        )
    except OrderServiceError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=error_response(
                code=e.code,
                message=e.message
            )
        )


@router.post("/{order_id}/mark-complete", response_model=dict)
async def mark_order_complete(
    order_id: str,
    current_user: UserResponse = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
):
    """
    Mark order as complete (transition IN_PROGRESS → COMPLETED).
    
    Args:
        order_id: Order database ID.
        current_user: Current authenticated user (auto-injected).
        order_service: Order service instance.
        
    Returns:
        Updated order data.
        
    Raises:
        HTTPException: If order not found or invalid transition.
    """
    if not current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                code="NO_RESTAURANT",
                message="User is not associated with a restaurant"
            )
        )
    
    try:
        order = await order_service.mark_complete(
            order_id,
            current_user.restaurant_id
        )
        
        order_response = await order_service.to_order_response(order)
        return success_response(
            data=order_response.model_dump(),
            message="Order marked as complete successfully"
        )
    except OrderServiceError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=error_response(
                code=e.code,
                message=e.message
            )
        )


@router.post("/{order_id}/move-to-waiting", response_model=dict)
async def move_order_to_waiting(
    order_id: str,
    current_user: UserResponse = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
):
    """
    Move order back to waiting (transition IN_PROGRESS → SENT_TO_KITCHEN).
    
    Args:
        order_id: Order database ID.
        current_user: Current authenticated user (auto-injected).
        order_service: Order service instance.
        
    Returns:
        Updated order data.
        
    Raises:
        HTTPException: If order not found or invalid transition.
    """
    if not current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                code="NO_RESTAURANT",
                message="User is not associated with a restaurant"
            )
        )
    
    try:
        order = await order_service.move_to_waiting(
            order_id,
            current_user.restaurant_id
        )
        
        order_response = await order_service.to_order_response(order)
        return success_response(
            data=order_response.model_dump(),
            message="Order moved to waiting successfully"
        )
    except OrderServiceError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=error_response(
                code=e.code,
                message=e.message
            )
        )


@router.get("/kitchen", response_model=dict)
async def get_kitchen_orders(
    current_user: UserResponse = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
):
    """
    Get orders for kitchen view, grouped by status.
    
    Returns orders in SENT_TO_KITCHEN (Waiting) and IN_PROGRESS (Next Up) statuses.
    Includes calculated wait times.
    
    Args:
        current_user: Current authenticated user (auto-injected).
        order_service: Order service instance.
        
    Returns:
        Dictionary with 'waiting' and 'next_up' order lists.
    """
    if not current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                code="NO_RESTAURANT",
                message="User is not associated with a restaurant"
            )
        )
    
    try:
        waiting, next_up = await order_service.get_kitchen_orders(
            current_user.restaurant_id
        )
        
        # Convert orders to responses with table information (parallel processing)
        waiting_responses = await asyncio.gather(
            *[order_service.to_order_response(order) for order in waiting]
        )
        next_up_responses = await asyncio.gather(
            *[order_service.to_order_response(order) for order in next_up]
        )
        
        return success_response(
            data={
                "waiting": [resp.model_dump() for resp in waiting_responses],
                "next_up": [resp.model_dump() for resp in next_up_responses],
            },
            message=f"Retrieved {len(waiting)} waiting and {len(next_up)} in progress order(s)"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(
                code="FETCH_FAILED",
                message=f"Failed to fetch kitchen orders: {str(e)}"
            )
        )


@router.get("/{order_id}", response_model=dict)
async def get_order(
    order_id: str,
    current_user: UserResponse = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
):
    """
    Get a specific order by ID.
    
    Args:
        order_id: Order database ID.
        current_user: Current authenticated user (auto-injected).
        order_service: Order service instance.
        
    Returns:
        Order data.
        
    Raises:
        HTTPException: If order not found or unauthorized.
    """
    if not current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                code="NO_RESTAURANT",
                message="User is not associated with a restaurant"
            )
        )
    
    try:
        order_repo = OrderRepository(order_service.order_repo.db)
        order = await order_repo.get_by_id(order_id)
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response(
                    code="NOT_FOUND",
                    message="Order not found"
                )
            )
        
        if order.restaurant_id != current_user.restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_response(
                    code="UNAUTHORIZED",
                    message="You do not have access to this order"
                )
            )
        
        order_response = await order_service.to_order_response(order)
        return success_response(
            data=order_response.model_dump(),
            message="Order retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(
                code="FETCH_FAILED",
                message=f"Failed to fetch order: {str(e)}"
            )
        )
