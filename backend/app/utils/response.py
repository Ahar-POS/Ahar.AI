"""
Standard API response formatters.

Provides consistent response structure as defined in project rules.
"""

from datetime import datetime
from typing import Any, Optional, Dict
from pydantic import BaseModel

from app.utils.timezone import now_ist


class APIResponse(BaseModel):
    """Standard successful API response format."""
    success: bool = True
    data: Any = None
    message: str = ""
    timestamp: str = ""

    def __init__(self, **data):
        if "timestamp" not in data or not data["timestamp"]:
            data["timestamp"] = now_ist().isoformat()
        super().__init__(**data)


class ErrorDetail(BaseModel):
    """Error detail structure."""
    code: str
    message: str
    details: Dict[str, Any] = {}


class APIErrorResponse(BaseModel):
    """Standard error API response format."""
    success: bool = False
    error: ErrorDetail
    timestamp: str = ""

    def __init__(self, **data):
        if "timestamp" not in data or not data["timestamp"]:
            data["timestamp"] = now_ist().isoformat()
        super().__init__(**data)


class PaginationInfo(BaseModel):
    """Pagination metadata."""
    page: int
    limit: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel):
    """Standard paginated API response format."""
    success: bool = True
    data: list = []
    pagination: PaginationInfo
    timestamp: str = ""

    def __init__(self, **data):
        if "timestamp" not in data or not data["timestamp"]:
            data["timestamp"] = now_ist().isoformat()
        super().__init__(**data)


def success_response(
    data: Any = None,
    message: str = "Success"
) -> dict:
    """
    Create a standard success response.
    
    Args:
        data: Response payload
        message: Human-readable message
    
    Returns:
        dict: Formatted response dictionary
    """
    return APIResponse(
        success=True,
        data=data,
        message=message
    ).model_dump()


def error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> dict:
    """
    Create a standard error response.
    
    Args:
        code: Error code (e.g., 'VALIDATION_ERROR')
        message: User-friendly error message
        details: Additional error context
    
    Returns:
        dict: Formatted error response dictionary
    """
    return APIErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details or {}
        )
    ).model_dump()


def paginated_response(
    data: list,
    page: int,
    limit: int,
    total: int
) -> dict:
    """
    Create a standard paginated response.
    
    Args:
        data: List of items for current page
        page: Current page number
        limit: Items per page
        total: Total number of items
    
    Returns:
        dict: Formatted paginated response dictionary
    """
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    
    return PaginatedResponse(
        data=data,
        pagination=PaginationInfo(
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages
        )
    ).model_dump()
