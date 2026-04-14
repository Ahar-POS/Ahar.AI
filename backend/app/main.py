"""
FastAPI application entry point.

Initializes the application with middleware, routers, and lifecycle events.
"""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import connect_to_database, close_database_connection
from app.api.v1 import router as api_v1_router
from app.services.orchestrator import get_orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    settings = get_settings()

    # Startup - Try to connect to database but don't fail if it's not available yet
    try:
        await connect_to_database()
    except Exception as e:
        print(f"Warning: Could not connect to database during startup: {e}")
        print("Application will start anyway. Database connection will be retried on first request.")

    # Initialize orchestrator (autonomous agents)
    if settings.ORCHESTRATOR_ENABLED:
        try:
            orchestrator = get_orchestrator()
            await orchestrator.initialize()
        except Exception as e:
            print(f"Warning: Could not initialize orchestrator: {e}")

    yield

    # Shutdown
    if settings.ORCHESTRATOR_ENABLED:
        try:
            orchestrator = get_orchestrator()
            await orchestrator.shutdown()
        except:
            pass

    await close_database_connection()


def create_application() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        FastAPI: Configured application instance.
    """
    settings = get_settings()

    # Ensure application logs (logger.info/...) are visible under Uvicorn.
    # Uvicorn configures its own loggers, but doesn't necessarily raise the root
    # level for application modules.
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(level=level)
    else:
        root_logger.setLevel(level)
        # Uvicorn often configures only its own loggers/handlers. Ensure the root
        # logger has a StreamHandler so `logging.getLogger(__name__)` in app
        # modules actually emits to the terminal.
        if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
            handler = logging.StreamHandler()
            handler.setLevel(level)
            handler.setFormatter(
                logging.Formatter("%(levelname)s %(name)s: %(message)s")
            )
            root_logger.addHandler(handler)
    logging.getLogger("app").setLevel(level)
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-powered Restaurant POS System",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Configure CORS: allow FRONTEND_URL and, when it uses localhost, also 127.0.0.1
    # so the app works whether opened as http://localhost:3000 or http://127.0.0.1:3000 (e.g. Docker)
    origins = [settings.FRONTEND_URL]
    if "localhost" in settings.FRONTEND_URL:
        origins.append(settings.FRONTEND_URL.replace("localhost", "127.0.0.1"))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(api_v1_router, prefix=settings.API_PREFIX)

    return app


app = create_application()


@app.get("/")
async def root():
    """Root endpoint - API information."""
    settings = get_settings()
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
