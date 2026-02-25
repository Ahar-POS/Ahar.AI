"""
Health check endpoints.

Provides endpoints to verify API and database connectivity.
"""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.database import get_database
from app.utils.response import success_response, error_response
from app.services.orchestrator import get_orchestrator
from app.services.event_bus import get_event_bus

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


@router.get("/orchestrator")
async def orchestrator_health():
    """
    Orchestrator and scheduler health check.

    Returns:
        dict: Orchestrator status including scheduler jobs
    """
    try:
        orchestrator = get_orchestrator()

        if not orchestrator._initialized:
            return success_response(
                data={
                    "status": "not_initialized",
                    "message": "Orchestrator will initialize on server startup"
                }
            )

        scheduler_info = orchestrator.get_scheduler_status()

        return success_response(
            data={
                "status": "healthy",
                "scheduler_running": scheduler_info["running"],
                "scheduled_jobs": scheduler_info["jobs"],
                "job_count": len(scheduler_info["jobs"]),
                "registered_agents": list(orchestrator.agents.keys())
            },
            message="Orchestrator is running"
        )
    except Exception as e:
        return error_response(
            code="ORCHESTRATOR_ERROR",
            message="Orchestrator health check failed",
            details={"error": str(e)}
        )


@router.get("/event-bus")
async def event_bus_health():
    """
    Event bus health check.

    Returns:
        dict: Event bus status and recent events
    """
    try:
        event_bus = get_event_bus()

        # Get subscriber counts
        subscribers = {}
        event_types = ['inventory.low_stock', 'inventory.expiring_soon',
                      'revenue.anomaly', 'kitchen.bottleneck']

        for event_type in event_types:
            count = event_bus.get_subscriber_count(event_type)
            if count > 0:
                subscribers[event_type] = count

        return success_response(
            data={
                "status": "healthy",
                "total_subscribers": event_bus.get_subscriber_count(),
                "subscribers_by_event": subscribers,
                "recent_events_count": len(event_bus.get_history(limit=10))
            },
            message="Event bus is operational"
        )
    except Exception as e:
        return error_response(
            code="EVENT_BUS_ERROR",
            message="Event bus health check failed",
            details={"error": str(e)}
        )


@router.post("/trigger-agent/{agent_name}")
async def trigger_agent(agent_name: str):
    """
    Manually trigger an agent for testing or on-demand execution.

    Args:
        agent_name: Name of agent to trigger (inventory, financial, forecaster)

    Returns:
        dict: Agent execution result
    """
    try:
        orchestrator = get_orchestrator()

        if not orchestrator._initialized:
            return error_response(
                code="ORCHESTRATOR_NOT_INITIALIZED",
                message="Orchestrator not initialized yet"
            )

        result = await orchestrator.trigger_agent(agent_name)

        return success_response(
            data=result,
            message=f"Successfully triggered {agent_name} agent"
        )
    except ValueError as e:
        return error_response(
            code="INVALID_AGENT",
            message=str(e)
        )
    except Exception as e:
        return error_response(
            code="TRIGGER_FAILED",
            message=f"Failed to trigger {agent_name} agent",
            details={"error": str(e)}
        )
