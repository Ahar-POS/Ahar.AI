"""
Chatbot API endpoints with Skills API integration.

Admin-only. Multi-turn conversation with support for:
- General chat (generic restaurant advisor)
- P&L report generation via Skills API
- File downloads for generated reports

Backend keeps recent history per user and uses local intent detection
to minimize LLM costs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path

from app.core.dependencies import get_admin_user
from app.core.config import get_settings
from app.models.user import UserResponse
from app.services.chatbot_service import get_chatbot_service
from app.utils.response import success_response, error_response

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])

# Max length for a single message to avoid abuse and token overflow
MESSAGE_MAX_LENGTH = 4000


class ChatMessageRequest(BaseModel):
    """Request body for sending a chat message."""

    message: str = Field(..., min_length=1, max_length=MESSAGE_MAX_LENGTH)


@router.post("/message", response_model=dict)
async def post_message(
    body: ChatMessageRequest,
    admin_user: UserResponse = Depends(get_admin_user),
):
    """
    Send a message and receive an assistant reply (admin-only).

    Supports:
    - General chat: Claude answers restaurant operations questions
    - P&L generation: Generates Excel reports for specified date ranges

    Response includes:
    - reply: Assistant's text response
    - download_url: (optional) URL to download generated file
    - filename: (optional) Name of generated file
    - usage: (optional) Token usage statistics for cost tracking
    - needs_clarification: (optional) True if user needs to provide more info

    When CLAUDE_API_KEY is not set, returns "API key not configured" message.
    """
    service = get_chatbot_service()
    result = await service.process_message(admin_user.id, body.message)

    # Build response data
    data = {
        "reply": result.get("reply", "Error processing message")
    }

    # Add optional fields if present
    if "download_url" in result:
        data["download_url"] = result["download_url"]

    if "filename" in result:
        data["filename"] = result["filename"]

    if "usage" in result:
        data["usage"] = result["usage"]

    if "needs_clarification" in result:
        data["needs_clarification"] = result["needs_clarification"]

    return success_response(data=data, message="OK")


@router.get("/download/{filename}")
async def download_file(
    filename: str,
    admin_user: UserResponse = Depends(get_admin_user),
):
    """
    Download a generated report file (admin-only).

    Args:
        filename: Name of the file to download (e.g., "pnl_2024-01-01_2024-01-31.xlsx")

    Returns:
        FileResponse: The requested file

    Raises:
        HTTPException: If file not found or access denied
    """
    settings = get_settings()
    # Resolve reports dir relative to backend root (same as chatbot_service writes to)
    backend_dir = Path(__file__).resolve().parent.parent.parent
    reports_dir = (backend_dir / settings.REPORTS_DIR).resolve()
    file_path = reports_dir / filename

    # Security: Prevent directory traversal
    if not file_path.resolve().is_relative_to(reports_dir):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Check if file exists
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Return file
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
