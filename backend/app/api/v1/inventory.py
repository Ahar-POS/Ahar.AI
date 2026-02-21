from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from app.models.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse
)
from app.services.inventory_service import inventory_service
from app.utils.response import success_response, error_response, paginated_response
from app.core.dependencies import get_current_user
from app.models.user import UserResponse, UserRole

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("", response_model=dict)
async def create_inventory_item(
    item: InventoryItemCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new inventory item (Admin only)"""
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can create inventory items"
        )

    try:
        created_item = await inventory_service.create_item(item)
        return success_response(
            data=created_item.model_dump(by_alias=True),
            message="Inventory item created successfully"
        )
    except ValueError as e:
        return error_response(
            code="DUPLICATE_MATERIAL_ID",
            message=str(e)
        )
    except Exception as e:
        return error_response(
            code="CREATION_FAILED",
            message=f"Failed to create inventory item: {str(e)}"
        )


@router.get("", response_model=dict)
async def get_all_inventory_items(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    is_perishable: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all inventory items with pagination (Admin only)"""
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can view inventory"
        )

    try:
        items, total = await inventory_service.get_all_items(
            page=page,
            limit=limit,
            category=category,
            is_perishable=is_perishable
        )

        items_data = [item.model_dump(by_alias=True) for item in items]
        return paginated_response(
            data=items_data,
            page=page,
            limit=limit,
            total=total
        )
    except Exception as e:
        return error_response(
            code="FETCH_FAILED",
            message=f"Failed to fetch inventory items: {str(e)}"
        )


@router.get("/low-stock", response_model=dict)
async def get_low_stock_items(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get items that need restocking (Admin only)"""
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can view inventory"
        )

    try:
        items = await inventory_service.get_low_stock_items()
        items_data = [item.model_dump(by_alias=True) for item in items]
        return success_response(
            data=items_data,
            message=f"Found {len(items)} items with low stock"
        )
    except Exception as e:
        return error_response(
            code="FETCH_FAILED",
            message=f"Failed to fetch low stock items: {str(e)}"
        )


@router.get("/{item_id}", response_model=dict)
async def get_inventory_item(
    item_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a specific inventory item (Admin only)"""
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can view inventory"
        )

    try:
        item = await inventory_service.get_item(item_id)
        if not item:
            return error_response(
                code="NOT_FOUND",
                message="Inventory item not found"
            )

        return success_response(
            data=item.model_dump(by_alias=True),
            message="Inventory item retrieved successfully"
        )
    except Exception as e:
        return error_response(
            code="FETCH_FAILED",
            message=f"Failed to fetch inventory item: {str(e)}"
        )


@router.put("/{item_id}", response_model=dict)
async def update_inventory_item(
    item_id: str,
    item_update: InventoryItemUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update an inventory item (Admin only)"""
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can update inventory"
        )

    try:
        updated_item = await inventory_service.update_item(item_id, item_update)
        if not updated_item:
            return error_response(
                code="NOT_FOUND",
                message="Inventory item not found"
            )

        return success_response(
            data=updated_item.model_dump(by_alias=True),
            message="Inventory item updated successfully"
        )
    except Exception as e:
        return error_response(
            code="UPDATE_FAILED",
            message=f"Failed to update inventory item: {str(e)}"
        )


@router.delete("/{item_id}", response_model=dict)
async def delete_inventory_item(
    item_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete an inventory item (Admin only)"""
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can delete inventory items"
        )

    try:
        deleted = await inventory_service.delete_item(item_id)
        if not deleted:
            return error_response(
                code="NOT_FOUND",
                message="Inventory item not found"
            )

        return success_response(
            data={"deleted": True},
            message="Inventory item deleted successfully"
        )
    except Exception as e:
        return error_response(
            code="DELETE_FAILED",
            message=f"Failed to delete inventory item: {str(e)}"
        )
