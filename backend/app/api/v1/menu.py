"""
Menu API endpoints.

Handles menu item management operations.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.core.dependencies import get_current_user
from app.models.menu_item import (
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
)
from app.models.user import UserResponse
from app.repositories.menu_repository import MenuRepository
from app.utils.response import success_response, error_response

router = APIRouter(prefix="/menu/items", tags=["Menu"])


def get_menu_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> MenuRepository:
    """Dependency to get menu repository instance."""
    return MenuRepository(db)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
    menu_item: MenuItemCreate,
    current_user: UserResponse = Depends(get_current_user),
    repo: MenuRepository = Depends(get_menu_repository)
):
    """
    Create a new menu item.
    
    Args:
        menu_item: Menu item creation data.
        current_user: Current authenticated user (auto-injected).
        repo: Menu repository instance.
        
    Returns:
        Created menu item data.
        
    Raises:
        HTTPException: If creation fails.
    """
    try:
        created_item = await repo.create(menu_item)
        
        return success_response(
            data=MenuItemResponse.model_validate(created_item).model_dump(),
            message="Menu item created successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(
                code="CREATION_FAILED",
                message=f"Failed to create menu item: {str(e)}"
            )
        )


@router.get("", response_model=dict)
async def get_menu_items(
    include_inactive: bool = Query(False, description="Include inactive menu items"),
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: UserResponse = Depends(get_current_user),
    repo: MenuRepository = Depends(get_menu_repository)
):
    """
    Get all menu items.
    
    Args:
        include_inactive: Whether to include inactive items.
        category: Optional category filter.
        repo: Menu repository instance.
        
    Returns:
        List of menu items.
    """
    items = await repo.get_all(include_inactive=include_inactive, category=category)
    
    return success_response(
        data=[MenuItemResponse.model_validate(item).model_dump() for item in items],
        message=f"Retrieved {len(items)} menu item(s)"
    )


@router.get("/categories", response_model=dict)
async def get_categories(
    current_user: UserResponse = Depends(get_current_user),
    repo: MenuRepository = Depends(get_menu_repository)
):
    """
    Get all unique menu categories.
    
    Args:
        repo: Menu repository instance.
        
    Returns:
        List of category names.
    """
    categories = await repo.get_categories()
    
    return success_response(
        data=categories,
        message=f"Retrieved {len(categories)} category(ies)"
    )


@router.get("/{item_id}", response_model=dict)
async def get_menu_item(
    item_id: str,
    current_user: UserResponse = Depends(get_current_user),
    repo: MenuRepository = Depends(get_menu_repository)
):
    """
    Get a specific menu item by ID.
    
    Args:
        item_id: Menu item database ID.
        repo: Menu repository instance.
        
    Returns:
        Menu item data.
        
    Raises:
        HTTPException: If menu item not found.
    """
    item = await repo.get_by_id(item_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(
                code="NOT_FOUND",
                message="Menu item not found"
            )
        )
    
    return success_response(
        data=MenuItemResponse.model_validate(item).model_dump(),
        message="Menu item retrieved successfully"
    )


@router.put("/{item_id}", response_model=dict)
async def update_menu_item(
    item_id: str,
    update_data: MenuItemUpdate,
    current_user: UserResponse = Depends(get_current_user),
    repo: MenuRepository = Depends(get_menu_repository)
):
    """
    Update menu item details.
    
    Args:
        item_id: Menu item database ID.
        update_data: Fields to update.
        current_user: Current authenticated user (auto-injected).
        repo: Menu repository instance.
        
    Returns:
        Updated menu item data.
        
    Raises:
        HTTPException: If menu item not found.
    """
    updated_item = await repo.update(item_id, update_data)
    
    if not updated_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(
                code="NOT_FOUND",
                message="Menu item not found"
            )
        )
    
    return success_response(
        data=MenuItemResponse.model_validate(updated_item).model_dump(),
        message="Menu item updated successfully"
    )


@router.delete("/{item_id}", response_model=dict)
async def delete_menu_item(
    item_id: str,
    current_user: UserResponse = Depends(get_current_user),
    repo: MenuRepository = Depends(get_menu_repository)
):
    """
    Soft delete a menu item (mark as inactive).
    
    Args:
        item_id: Menu item database ID.
        current_user: Current authenticated user (auto-injected).
        repo: Menu repository instance.
        
    Returns:
        Success message.
        
    Raises:
        HTTPException: If menu item not found or deletion fails.
    """
    success = await repo.soft_delete(item_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(
                code="NOT_FOUND",
                message="Menu item not found"
            )
        )
    
    return success_response(
        data={"id": item_id},
        message="Menu item deleted successfully"
    )
