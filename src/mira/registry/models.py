"""Data models for the Service Registry."""

from pydantic import BaseModel, Field


class ServiceInfo(BaseModel):
    """Information about a service in the registry.

    This model maps a service (as identified in observability systems like Datadog)
    to its source code repository and team ownership in Azure DevOps.
    """

    repo_name: str = Field(
        ...,
        description="The name of the repository in Azure DevOps containing the service code",
    )
    project: str = Field(
        default="",
        description="Azure DevOps project name. If empty, uses the default project.",
    )
    adk_profile: str = Field(
        default="backend_investigator",
        description="The ADK agent profile to use for investigating this service",
    )
    owner_team: str = Field(
        default="",
        description="The team that owns this service (for notification routing)",
    )
    description: str = Field(
        default="",
        description="Optional description of the service",
    )
    alert_channel: str = Field(
        default="",
        description="Slack/Teams channel for alerts related to this service",
    )


class AlertPayload(BaseModel):
    """Incoming alert payload from Datadog webhook.

    This represents the payload structure sent by Datadog when a monitor triggers.
    """

    service: str = Field(
        ...,
        description="The name of the service that triggered the alert",
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp of when the alert occurred",
    )
    environment: str = Field(
        default="prod",
        description="Environment where the alert was triggered (e.g., prod, staging)",
    )
    alert_type: str = Field(
        default="error_rate",
        description="Type of alert (e.g., error_rate, latency, cpu_usage)",
    )
    alert_title: str = Field(
        default="",
        description="Title of the alert from Datadog",
    )
    alert_id: str = Field(
        default="",
        description="Unique identifier for the alert",
    )
    severity: str = Field(
        default="high",
        description="Severity level of the alert (low, medium, high, critical)",
    )
    tags: dict[str, str] = Field(
        default_factory=dict,
        description="Additional tags from Datadog",
    )


class InvestigationContext(BaseModel):
    """Context passed to the Worker Agent for investigation.

    Contains all the information needed by the agent to investigate an incident.
    """

    service_name: str = Field(
        ...,
        description="Name of the service to investigate",
    )
    repo_name: str = Field(
        ...,
        description="Name of the repository to check for commits",
    )
    project: str = Field(
        ...,
        description="Azure DevOps project name",
    )
    alert_timestamp: str = Field(
        ...,
        description="Timestamp of the alert",
    )
    environment: str = Field(
        ...,
        description="Environment (prod, staging, etc.)",
    )
    alert_type: str = Field(
        ...,
        description="Type of alert that was triggered",
    )
    alert_title: str = Field(
        default="",
        description="Title of the alert",
    )
    owner_team: str = Field(
        default="",
        description="Team that owns this service",
    )
    alert_channel: str = Field(
        default="",
        description="Channel for notifications",
    )
    lookback_hours: int = Field(
        default=2,
        description="How many hours to look back for commits",
    )
