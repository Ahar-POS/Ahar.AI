"""
Tables API endpoints.

Handles table management operations for restaurants.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_database
from app.core.dependencies import get_current_user
from app.models.table import (
    TableCreate,
    TableResponse,
    TableStatus,
    TableUpdate,
)
from app.models.user import UserResponse
from app.repositories.table_repository import TableRepository
from app.utils.response import success_response, error_response


class StatusUpdate(BaseModel):
    """Request model for updating table status."""
    status: TableStatus

router = APIRouter(prefix="/tables", tags=["Tables"])


def get_table_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> TableRepository:
    """Dependency to get table repository instance."""
    return TableRepository(db)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_table(
    table: TableCreate,
    current_user = Depends(get_current_user),
    repo: TableRepository = Depends(get_table_repository)
):
    """
    Create a new table.
    
    The created_by_user_id is automatically set from the authenticated user.
    
    Args:
        table: Table creation data.
        current_user: Current authenticated user (auto-injected).
        repo: Table repository instance.
        
    Returns:
        Created table data.
        
    Raises:
        HTTPException: If table number already exists.
    """
    # Set created_by_user_id from authenticated user
    table.created_by_user_id = current_user.id
    
    # Check if table number already exists
    exists = await repo.table_number_exists(table_number=table.table_number)
    
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Table number {table.table_number} already exists"
        )
    
    created_table = await repo.create(table)
    
    return success_response(
        data=TableResponse.model_validate(created_table).model_dump(),
        message="Table created successfully"
    )


@router.get("", response_model=dict)
async def get_tables(
    current_user: UserResponse = Depends(get_current_user),
    include_inactive: bool = Query(False, description="Include inactive tables"),
    repo: TableRepository = Depends(get_table_repository)
):
    """
    Get all tables created by the authenticated user.
    
    Args:
        current_user: Current authenticated user (auto-injected).
        include_inactive: Whether to include inactive tables.
        repo: Table repository instance.
        
    Returns:
        List of tables created by the user.
    """
    tables = await repo.get_all(include_inactive=include_inactive)
    
    # Filter to only tables created by the current user
    user_tables = [t for t in tables if t.created_by_user_id == current_user.id]
    
    return success_response(
        data=[TableResponse.model_validate(t).model_dump() for t in user_tables],
        message=f"Retrieved {len(user_tables)} table(s)"
    )


@router.get("/status/{status}", response_model=dict)
async def get_tables_by_status(
    status: TableStatus = ...,
    current_user: UserResponse = Depends(get_current_user),
    repo: TableRepository = Depends(get_table_repository)
):
    """
    Get all tables with a specific status created by the authenticated user.
    
    Args:
        status: Table status to filter by.
        current_user: Current authenticated user (auto-injected).
        repo: Table repository instance.
        
    Returns:
        List of tables with the specified status created by the user.
    """
    tables = await repo.get_by_status(status=status)
    
    # Filter to only tables created by the current user
    user_tables = [t for t in tables if t.created_by_user_id == current_user.id]
    
    return success_response(
        data=[TableResponse.model_validate(t).model_dump() for t in user_tables],
        message=f"Retrieved {len(user_tables)} {status.value} table(s)"
    )


@router.get("/{table_id}", response_model=dict)
async def get_table(
    table_id: str,
    current_user: UserResponse = Depends(get_current_user),
    repo: TableRepository = Depends(get_table_repository)
):
    """
    Get a specific table by ID.
    
    Only returns the table if it was created by the authenticated user.
    
    Args:
        table_id: Table database ID.
        current_user: Current authenticated user (auto-injected).
        repo: Table repository instance.
        
    Returns:
        Table data.
        
    Raises:
        HTTPException: If table not found or user doesn't have access.
    """
    table = await repo.get_by_id(table_id)
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Authorization check: ensure table was created by the current user
    if table.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this table"
        )
    
    return success_response(
        data=TableResponse.model_validate(table).model_dump(),
        message="Table retrieved successfully"
    )


@router.put("/{table_id}", response_model=dict)
async def update_table(
    table_id: str,
    update_data: TableUpdate,
    current_user: UserResponse = Depends(get_current_user),
    repo: TableRepository = Depends(get_table_repository)
):
    """
    Update table details.
    
    Only allows updating tables that were created by the authenticated user.
    
    Args:
        table_id: Table database ID.
        update_data: Fields to update.
        current_user: Current authenticated user (auto-injected).
        repo: Table repository instance.
        
    Returns:
        Updated table data.
        
    Raises:
        HTTPException: If table not found or user doesn't have access.
    """
    # Check if table exists and was created by the current user
    table = await repo.get_by_id(table_id)
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Authorization check
    if table.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this table"
        )
    
    updated_table = await repo.update(table_id, update_data)
    
    if not updated_table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    return success_response(
        data=TableResponse.model_validate(updated_table).model_dump(),
        message="Table updated successfully"
    )


@router.patch("/{table_id}/status", response_model=dict)
async def update_table_status(
    table_id: str,
    status_update: StatusUpdate,
    current_user: UserResponse = Depends(get_current_user),
    repo: TableRepository = Depends(get_table_repository)
):
    """
    Update table status.
    
    Only allows updating tables that were created by the authenticated user.
    
    Args:
        table_id: Table database ID.
        status_update: Status update request with new status.
        current_user: Current authenticated user (auto-injected).
        repo: Table repository instance.
        
    Returns:
        Updated table data.
        
    Raises:
        HTTPException: If table not found or user doesn't have access.
    """
    # Check if table exists and was created by the current user
    table = await repo.get_by_id(table_id)
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Authorization check
    if table.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this table"
        )
    
    updated_table = await repo.update_status(table_id, status_update.status)
    
    if not updated_table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    return success_response(
        data=TableResponse.model_validate(updated_table).model_dump(),
        message=f"Table status updated to {status_update.status.value}"
    )


@router.delete("/{table_id}", response_model=dict)
async def delete_table(
    table_id: str,
    current_user: UserResponse = Depends(get_current_user),
    repo: TableRepository = Depends(get_table_repository)
):
    """
    Soft delete a table (mark as inactive).
    
    Only allows deleting tables that were created by the authenticated user.
    
    Args:
        table_id: Table database ID.
        current_user: Current authenticated user (auto-injected).
        repo: Table repository instance.
        
    Returns:
        Success message.
        
    Raises:
        HTTPException: If table not found, user doesn't have access, or deletion fails.
    """
    # Check if table exists and was created by the current user
    table = await repo.get_by_id(table_id)
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Authorization check
    if table.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this table"
        )
    
    # Soft delete
    success = await repo.soft_delete(table_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    return success_response(
        data={"id": table_id},
        message="Table deleted successfully"
    )
