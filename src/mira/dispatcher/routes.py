"""
FastAPI routes for the MIRA Dispatcher service.

Includes the webhook endpoint for Datadog alerts and management endpoints.
"""

import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from pydantic import BaseModel

from mira.config.settings import Settings
from mira.registry.models import AlertPayload, InvestigationContext, ServiceInfo
from mira.registry.service_registry import ServiceRegistry
from mira.worker.agent import create_investigator_agent

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    environment: str
    services_registered: int


class InvestigationResponse(BaseModel):
    """Response after accepting an investigation request."""

    status: str
    investigation_id: str
    service: str
    message: str


class InvestigationResult(BaseModel):
    """Result of an investigation."""

    status: str
    service: str
    alert_type: str
    rca: dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Health check endpoint.

    Returns the current status of the dispatcher service.
    """
    settings: Settings = request.app.state.settings
    registry: ServiceRegistry = request.app.state.service_registry

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        environment=settings.environment,
        services_registered=len(registry),
    )


@router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with service information."""
    return {
        "service": "MIRA - Microservice Incident Response Agent",
        "version": "0.1.0",
        "docs": "/docs",
    }


def verify_webhook_signature(
    payload: bytes,
    signature: str | None,
    secret: str | None,
) -> bool:
    """Verify the webhook signature from Datadog.

    Args:
        payload: Raw request body.
        signature: Signature header from the request.
        secret: Webhook secret.

    Returns:
        True if signature is valid or verification is disabled.
    """
    if not secret:
        # Signature verification disabled
        return True

    if not signature:
        return False

    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


async def run_investigation(
    context: InvestigationContext,
    settings: Settings,
) -> InvestigationResult:
    """Run the investigation in the background.

    Args:
        context: Investigation context.
        settings: Application settings.

    Returns:
        Investigation result.
    """
    logger.info(f"Running investigation for service: {context.service_name}")

    try:
        agent = create_investigator_agent(context, settings)
        result = await agent.investigate()

        logger.info(f"Investigation completed for service: {context.service_name}")

        return InvestigationResult(
            status=result.get("status", "completed"),
            service=context.service_name,
            alert_type=context.alert_type,
            rca=result.get("rca", {}),
        )

    except Exception as e:
        logger.error(f"Investigation failed for {context.service_name}: {e}")
        return InvestigationResult(
            status="failed",
            service=context.service_name,
            alert_type=context.alert_type,
            rca={
                "summary": f"Investigation failed: {e!s}",
                "confidence": "N/A",
                "error": str(e),
            },
        )


@router.post("/webhook/datadog", response_model=InvestigationResponse)
async def receive_datadog_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_datadog_signature: str | None = Header(None),
) -> InvestigationResponse:
    """Receive and process a Datadog alert webhook.

    This is the main entry point for incident detection. When Datadog
    triggers an alert, it sends a webhook to this endpoint.

    The dispatcher:
    1. Validates the webhook signature
    2. Extracts service name and alert details
    3. Looks up the service in the registry
    4. Spawns a Worker Agent to investigate

    Args:
        request: FastAPI request object.
        background_tasks: Background task manager.
        x_datadog_signature: Webhook signature header.

    Returns:
        Response indicating the investigation has been queued.

    Raises:
        HTTPException: If validation fails or service is not found.
    """
    settings: Settings = request.app.state.settings
    registry: ServiceRegistry = request.app.state.service_registry

    # Get raw body for signature verification
    body = await request.body()

    # Verify webhook signature
    if not verify_webhook_signature(body, x_datadog_signature, settings.webhook_secret):
        logger.warning("Invalid webhook signature received")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Parse the alert payload
    try:
        payload_data = await request.json()
        alert = AlertPayload(**payload_data)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}") from e

    # Look up the service in the registry
    service_info: ServiceInfo | None = registry.get_service(alert.service)

    if not service_info:
        logger.warning(f"Service not found in registry: {alert.service}")
        raise HTTPException(
            status_code=404,
            detail=f"Service '{alert.service}' not found in registry",
        )

    # Create investigation context
    investigation_id = f"inv-{alert.service}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

    context = InvestigationContext(
        service_name=alert.service,
        repo_name=service_info.repo_name,
        project=service_info.project or settings.azure_devops_organization or "",
        alert_timestamp=alert.timestamp,
        environment=alert.environment,
        alert_type=alert.alert_type,
        alert_title=alert.alert_title,
        owner_team=service_info.owner_team,
        alert_channel=service_info.alert_channel,
    )

    logger.info(
        f"Received alert for service: {alert.service}, "
        f"type: {alert.alert_type}, "
        f"repo: {service_info.repo_name}"
    )

    # Queue the investigation in the background
    background_tasks.add_task(run_investigation, context, settings)

    return InvestigationResponse(
        status="accepted",
        investigation_id=investigation_id,
        service=alert.service,
        message=f"Investigation queued for {alert.service}",
    )


@router.post("/investigate", response_model=InvestigationResult)
async def investigate_service(
    request: Request,
    alert: AlertPayload,
) -> InvestigationResult:
    """Manually trigger an investigation for a service.

    This endpoint allows manual triggering of investigations without
    waiting for a Datadog webhook. Useful for testing and debugging.

    Args:
        request: FastAPI request object.
        alert: Alert payload with service and alert details.

    Returns:
        Investigation result with RCA.

    Raises:
        HTTPException: If service is not found.
    """
    settings: Settings = request.app.state.settings
    registry: ServiceRegistry = request.app.state.service_registry

    # Look up the service
    service_info: ServiceInfo | None = registry.get_service(alert.service)

    if not service_info:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{alert.service}' not found in registry",
        )

    # Create investigation context
    context = InvestigationContext(
        service_name=alert.service,
        repo_name=service_info.repo_name,
        project=service_info.project or settings.azure_devops_organization or "",
        alert_timestamp=alert.timestamp,
        environment=alert.environment,
        alert_type=alert.alert_type,
        alert_title=alert.alert_title,
        owner_team=service_info.owner_team,
        alert_channel=service_info.alert_channel,
    )

    # Run investigation synchronously
    return await run_investigation(context, settings)


@router.get("/services")
async def list_services(request: Request) -> dict[str, Any]:
    """List all registered services.

    Returns a list of all services in the registry.
    """
    registry: ServiceRegistry = request.app.state.service_registry

    return {
        "count": len(registry),
        "services": registry.list_services(),
    }


@router.post("/services/{service_name}")
async def register_service(
    request: Request,
    service_name: str,
    service_info: ServiceInfo,
) -> dict[str, str]:
    """Register a new service in the registry.

    Args:
        request: FastAPI request object.
        service_name: Name of the service.
        service_info: Service registration details.

    Returns:
        Confirmation message.
    """
    registry: ServiceRegistry = request.app.state.service_registry

    registry.register_service(service_name, service_info)

    return {"message": f"Service '{service_name}' registered successfully"}


@router.delete("/services/{service_name}")
async def remove_service(
    request: Request,
    service_name: str,
) -> dict[str, str]:
    """Remove a service from the registry.

    Args:
        request: FastAPI request object.
        service_name: Name of the service to remove.

    Returns:
        Confirmation message.

    Raises:
        HTTPException: If service is not found.
    """
    registry: ServiceRegistry = request.app.state.service_registry

    if not registry.remove_service(service_name):
        raise HTTPException(
            status_code=404,
            detail=f"Service '{service_name}' not found",
        )

    return {"message": f"Service '{service_name}' removed successfully"}
