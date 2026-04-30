from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.models.user import UserResponse
from app.services.notification_service import get_notification_service
from app.utils.response import success_response, error_response, paginated_response

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _fmt(n: dict) -> dict:
    """Serialise a raw MongoDB notification dict for API responses."""
    return {
        "notification_id": n.get("notification_id"),
        "type": n.get("type"),
        "title": n.get("title"),
        "message": n.get("message"),
        "severity": n.get("severity", "info"),
        "target_roles": n.get("target_roles", []),
        "metadata": n.get("metadata", {}),
        "is_read": n.get("is_read", False),
        "read_at": n["read_at"].isoformat() if n.get("read_at") else None,
        "created_at": n["created_at"].isoformat() if n.get("created_at") else None,
    }


@router.get("", response_model=dict)
async def list_notifications(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    unread_only: bool = Query(default=False),
    current_user: UserResponse = Depends(get_current_user),
):
    """Return paginated notifications for the caller's role."""
    svc = get_notification_service()
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    items, total = await svc.get_notifications(role, page, limit, unread_only)
    return paginated_response([_fmt(n) for n in items], page, limit, total)


@router.get("/unread-count", response_model=dict)
async def unread_count(
    current_user: UserResponse = Depends(get_current_user),
):
    """Return unread notification count for the caller's role."""
    svc = get_notification_service()
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    count = await svc.get_unread_count(role)
    return success_response({"count": count}, "Unread count fetched")


@router.put("/{notification_id}/read", response_model=dict)
async def mark_read(
    notification_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Mark a single notification as read."""
    svc = get_notification_service()
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    updated = await svc.mark_read(notification_id, role)
    if not updated:
        return error_response("NOT_FOUND", "Notification not found or already read")
    return success_response({"notification_id": notification_id}, "Marked as read")


@router.put("/mark-all-read", response_model=dict)
async def mark_all_read(
    current_user: UserResponse = Depends(get_current_user),
):
    """Mark all notifications as read for the caller's role."""
    svc = get_notification_service()
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    count = await svc.mark_all_read(role)
    return success_response({"marked": count}, f"{count} notifications marked as read")
