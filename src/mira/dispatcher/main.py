"""
FastAPI Dispatcher Service main entry point.

The Dispatcher is the entry point (API Gateway) for the MIRA system.
It receives webhooks from Datadog, looks up service metadata in the
Service Registry, and instantiates Worker Agents for investigation.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mira.config.settings import get_settings
from mira.dispatcher.routes import router
from mira.registry.service_registry import ServiceRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    settings = get_settings()

    # Initialize the service registry
    logger.info(f"Loading service registry from: {settings.service_registry_path}")
    app.state.service_registry = ServiceRegistry(settings.service_registry_path)
    app.state.settings = settings

    logger.info(
        f"MIRA Dispatcher starting in {settings.environment} mode"
        f" (services registered: {len(app.state.service_registry)})"
    )

    yield

    # Cleanup on shutdown
    logger.info("MIRA Dispatcher shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="MIRA - Microservice Incident Response Agent",
        description=(
            "Automated incident investigation system designed to reduce MTTR. "
            "Receives alerts from Datadog and investigates root causes using "
            "Google ADK agents with access to logs and Azure DevOps commits."
        ),
        version="0.1.0",
        docs_url="/docs" if settings.debug or settings.environment == "development" else None,
        redoc_url="/redoc" if settings.debug or settings.environment == "development" else None,
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.environment == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(router)

    return app


# Create the application instance
app = create_app()


def run() -> None:
    """Run the application using uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "mira.dispatcher.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
