"""
Datadog MCP Client for retrieving logs and metrics.

This client wraps the Datadog MCP server tools to provide a scoped interface
for investigating incidents. The client filters all requests to a specific service.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LogEntry(BaseModel):
    """Represents a single log entry from Datadog."""

    timestamp: str
    message: str
    service: str
    status: str
    host: str | None = None
    attributes: dict[str, Any] = {}


class DatadogMCPClient:
    """Client for interacting with Datadog via MCP.

    This client provides scoped access to Datadog logs and metrics,
    filtered by service name. It's designed to be used by Worker Agents
    during incident investigation.
    """

    def __init__(
        self,
        api_key: str,
        app_key: str,
        site: str = "datadoghq.com",
        service_name: str | None = None,
    ) -> None:
        """Initialize the Datadog MCP client.

        Args:
            api_key: Datadog API key.
            app_key: Datadog Application key.
            site: Datadog site (e.g., datadoghq.com, datadoghq.eu).
            service_name: Optional service name to scope all queries to.
        """
        self.api_key = api_key
        self.app_key = app_key
        self.site = site
        self.service_name = service_name
        self._base_url = f"https://api.{site}"

        logger.info(
            f"Initialized Datadog MCP client for site: {site}"
            + (f", service: {service_name}" if service_name else "")
        )

    def with_service(self, service_name: str) -> "DatadogMCPClient":
        """Create a new client scoped to a specific service.

        Args:
            service_name: The service name to scope queries to.

        Returns:
            A new DatadogMCPClient instance scoped to the service.
        """
        return DatadogMCPClient(
            api_key=self.api_key,
            app_key=self.app_key,
            site=self.site,
            service_name=service_name,
        )

    async def get_logs(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        status: str | None = None,
        query: str | None = None,
        limit: int = 100,
    ) -> list[LogEntry]:
        """Retrieve logs from Datadog.

        Args:
            start_time: Start of the time range. Defaults to 1 hour ago.
            end_time: End of the time range. Defaults to now.
            status: Filter by log status (e.g., 'error', 'warn', 'info').
            query: Additional search query.
            limit: Maximum number of logs to return.

        Returns:
            List of log entries.
        """
        if not start_time:
            start_time = datetime.now(UTC) - timedelta(hours=1)
        if not end_time:
            end_time = datetime.now(UTC)

        # Build the query
        query_parts = []

        if self.service_name:
            query_parts.append(f"service:{self.service_name}")

        if status:
            query_parts.append(f"status:{status}")

        if query:
            query_parts.append(query)

        full_query = " ".join(query_parts) if query_parts else "*"

        logger.info(
            f"Fetching logs: query='{full_query}', "
            f"from={start_time.isoformat()}, to={end_time.isoformat()}"
        )

        # In a real implementation, this would call the Datadog MCP server
        # For now, return a placeholder that shows the query structure
        return [
            LogEntry(
                timestamp=datetime.now(UTC).isoformat(),
                message=f"[Placeholder] Query executed: {full_query}",
                service=self.service_name or "unknown",
                status="info",
            )
        ]

    async def get_error_logs(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
    ) -> list[LogEntry]:
        """Convenience method to get only error logs.

        Args:
            start_time: Start of the time range.
            end_time: End of the time range.
            limit: Maximum number of logs to return.

        Returns:
            List of error log entries.
        """
        return await self.get_logs(
            start_time=start_time,
            end_time=end_time,
            status="error",
            limit=limit,
        )

    async def get_metrics(
        self,
        metric_name: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        aggregation: str = "avg",
    ) -> dict[str, Any]:
        """Query metrics from Datadog.

        Args:
            metric_name: Name of the metric to query.
            start_time: Start of the time range.
            end_time: End of the time range.
            aggregation: Aggregation method (avg, sum, min, max, count).

        Returns:
            Metric data with timestamps and values.
        """
        if not start_time:
            start_time = datetime.now(UTC) - timedelta(hours=1)
        if not end_time:
            end_time = datetime.now(UTC)

        filters = {}
        if self.service_name:
            filters["service"] = self.service_name

        logger.info(
            f"Fetching metric: {metric_name}, aggregation={aggregation}, "
            f"filters={filters}"
        )

        # Placeholder implementation
        return {
            "metric": metric_name,
            "aggregation": aggregation,
            "service": self.service_name,
            "from": start_time.isoformat(),
            "to": end_time.isoformat(),
            "data": [],
        }

    async def get_monitors(
        self,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get Datadog monitors, optionally filtered by status.

        Args:
            status: Filter by monitor status (e.g., 'Alert', 'OK', 'Warn').

        Returns:
            List of monitors.
        """
        tags = f"service:{self.service_name}" if self.service_name else ""

        logger.info(f"Fetching monitors with tags: {tags}, status: {status}")

        # Placeholder implementation
        return []
