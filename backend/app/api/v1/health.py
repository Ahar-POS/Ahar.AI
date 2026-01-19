"""
Health check endpoints.

Provides endpoints to verify API and database connectivity.
"""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.database import get_database
from app.utils.response import success_response, error_response

router = APIRouter()


@router.get("")
async def health_check():
    """
    Basic health check endpoint.
    
    Returns:
        dict: Health status response
    """
    settings = get_settings()
    return success_response(
        data={
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION
        },
        message="Service is running"
    )


@router.get("/db")
async def database_health_check():
    """
    Database connectivity health check.
    
    Returns:
        dict: Database health status response
    """
    try:
        db: AsyncIOMotorDatabase = get_database()
        # Ping the database
        await db.command("ping")
        return success_response(
            data={
                "status": "healthy",
                "database": "connected"
            },
            message="Database connection is healthy"
        )
    except Exception as e:
        return error_response(
            code="DATABASE_ERROR",
            message="Database connection failed",
            details={"error": str(e)}
        )
