"""
Investigation tools for the Worker Agent.

These tools are used by the Google ADK agent to investigate incidents.
Each tool is scoped to a specific service and repository.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from mira.mcp_clients.azure_devops_client import AzureDevOpsMCPClient
from mira.mcp_clients.datadog_client import DatadogMCPClient
from mira.registry.models import InvestigationContext

logger = logging.getLogger(__name__)


def create_get_logs_tool(datadog_client: DatadogMCPClient, context: InvestigationContext):
    """Create a scoped get_logs tool for the agent.

    Args:
        datadog_client: Datadog client scoped to the service.
        context: Investigation context.

    Returns:
        A callable tool function.
    """

    async def get_logs(
        status: str = "error",
        lookback_minutes: int = 30,
        query: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve logs from Datadog for the service being investigated.

        Use this tool to get error logs and stack traces from the service.

        Args:
            status: Log status to filter by (error, warn, info, debug).
                   Default is "error" to focus on errors.
            lookback_minutes: How many minutes before the alert to look for logs.
                            Default is 30 minutes.
            query: Additional search query to narrow down logs.

        Returns:
            Dictionary containing log entries and metadata.
        """
        # Parse the alert timestamp
        try:
            alert_time = datetime.fromisoformat(context.alert_timestamp.replace("Z", "+00:00"))
        except ValueError:
            alert_time = datetime.now(UTC)

        start_time = alert_time - timedelta(minutes=lookback_minutes)
        end_time = alert_time + timedelta(minutes=5)  # Include a few minutes after

        logger.info(
            f"Agent getting logs: service={context.service_name}, "
            f"status={status}, from={start_time}"
        )

        logs = await datadog_client.get_logs(
            start_time=start_time,
            end_time=end_time,
            status=status,
            query=query,
        )

        return {
            "service": context.service_name,
            "status_filter": status,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "log_count": len(logs),
            "logs": [log.model_dump() for log in logs],
        }

    return get_logs


def create_get_commits_tool(azure_client: AzureDevOpsMCPClient, context: InvestigationContext):
    """Create a scoped get_commits tool for the agent.

    Args:
        azure_client: Azure DevOps client scoped to the repository.
        context: Investigation context.

    Returns:
        A callable tool function.
    """

    async def get_commits(
        file_path: str | None = None,
        lookback_hours: int | None = None,
    ) -> dict[str, Any]:
        """Retrieve recent commits from Azure DevOps for the service repository.

        Use this tool to find recent code changes that might have caused the incident.

        Args:
            file_path: Optional file path to filter commits.
                      Use this when you've identified a specific file from error logs.
            lookback_hours: How many hours before the alert to look for commits.
                          Defaults to the context's lookback_hours setting.

        Returns:
            Dictionary containing commits and metadata.
        """
        hours = lookback_hours or context.lookback_hours

        # Parse the alert timestamp
        try:
            alert_time = datetime.fromisoformat(context.alert_timestamp.replace("Z", "+00:00"))
        except ValueError:
            alert_time = datetime.now(UTC)

        start_time = alert_time - timedelta(hours=hours)

        logger.info(
            f"Agent getting commits: repo={context.repo_name}, file={file_path}, lookback={hours}h"
        )

        commits = await azure_client.get_commits(
            start_time=start_time,
            end_time=alert_time,
            file_path=file_path,
        )

        return {
            "repository": context.repo_name,
            "project": context.project,
            "file_filter": file_path,
            "time_range": {
                "start": start_time.isoformat(),
                "end": alert_time.isoformat(),
            },
            "commit_count": len(commits),
            "commits": [c.model_dump() for c in commits],
        }

    return get_commits


def create_get_commit_details_tool(
    azure_client: AzureDevOpsMCPClient, context: InvestigationContext
):
    """Create a tool to get detailed information about a specific commit.

    Args:
        azure_client: Azure DevOps client scoped to the repository.
        context: Investigation context.

    Returns:
        A callable tool function.
    """

    async def get_commit_details(commit_id: str) -> dict[str, Any]:
        """Get detailed information about a specific commit including the diff.

        Use this tool when you've identified a suspicious commit and want to
        see exactly what changes were made.

        Args:
            commit_id: The commit SHA to get details for.

        Returns:
            Dictionary containing detailed commit information and changes.
        """
        logger.info(f"Agent getting commit details: {commit_id}")

        return await azure_client.get_commit_details(commit_id)

    return get_commit_details


def create_get_metrics_tool(datadog_client: DatadogMCPClient, context: InvestigationContext):
    """Create a scoped get_metrics tool for the agent.

    Args:
        datadog_client: Datadog client scoped to the service.
        context: Investigation context.

    Returns:
        A callable tool function.
    """

    async def get_metrics(
        metric_name: str,
        lookback_minutes: int = 60,
        aggregation: str = "avg",
    ) -> dict[str, Any]:
        """Query metrics from Datadog for the service being investigated.

        Use this tool to understand the behavior of the service around the incident time.

        Args:
            metric_name: Name of the metric to query (e.g., 'http.request.duration',
                        'error.rate', 'cpu.usage').
            lookback_minutes: How many minutes of data to retrieve.
            aggregation: Aggregation method (avg, sum, min, max, count).

        Returns:
            Dictionary containing metric data and timestamps.
        """
        # Parse the alert timestamp
        try:
            alert_time = datetime.fromisoformat(context.alert_timestamp.replace("Z", "+00:00"))
        except ValueError:
            alert_time = datetime.now(UTC)

        start_time = alert_time - timedelta(minutes=lookback_minutes)

        logger.info(f"Agent getting metrics: {metric_name}, aggregation={aggregation}")

        return await datadog_client.get_metrics(
            metric_name=metric_name,
            start_time=start_time,
            end_time=alert_time,
            aggregation=aggregation,
        )

    return get_metrics


def get_investigation_tools(
    datadog_client: DatadogMCPClient,
    azure_client: AzureDevOpsMCPClient,
    context: InvestigationContext,
) -> list:
    """Get all investigation tools for the worker agent.

    Args:
        datadog_client: Datadog client scoped to the service.
        azure_client: Azure DevOps client scoped to the repository.
        context: Investigation context.

    Returns:
        List of tool functions for the agent.
    """
    return [
        create_get_logs_tool(datadog_client, context),
        create_get_commits_tool(azure_client, context),
        create_get_commit_details_tool(azure_client, context),
        create_get_metrics_tool(datadog_client, context),
    ]
