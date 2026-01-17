"""
Datadog MCP Server and Client for retrieving logs and metrics.

This module implements:
1. An MCP server using FastMCP and the official Datadog API client.
2. A specialized client class (DatadogMCPClient) that wraps the API for agents.
"""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.api.metrics_api import MetricsApi
from datadog_api_client.v2.api.monitors_api import MonitorsApi
from datadog_api_client.v2.model.logs_list_request import LogsListRequest
from datadog_api_client.v2.model.logs_list_request_page import LogsListRequestPage
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_sort import LogsSort
from fastmcp import FastMCP
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Initialize FastMCP
mcp = FastMCP("datadog")


class LogEntry(BaseModel):
    """Represents a log entry from Datadog."""

    timestamp: str | None
    message: str | None
    status: str | None
    service: str | None
    host: str | None


class DatadogMCPClient:
    """Specialized client for Datadog that provides a scoped interface for agents.

    This client wraps the official Datadog API client to provide high-level
    methods for logs, metrics, and monitors.
    """

    def __init__(
        self,
        api_key: str | None = None,
        app_key: str | None = None,
        site: str = "datadoghq.com",
        service_name: str | None = None,
    ) -> None:
        """Initialize the Datadog client.

        Args:
            api_key: Datadog API key.
            app_key: Datadog App key.
            site: Datadog site (e.g., datadoghq.com).
            service_name: Default service name to filter by.
        """
        self.configuration = Configuration()
        self.configuration.api_key["apiKeyAuth"] = api_key or os.getenv("DATADOG_API_KEY")
        self.configuration.api_key["appKeyAuth"] = app_key or os.getenv("DATADOG_APP_KEY")
        self.configuration.server_variables["site"] = site or os.getenv(
            "DATADOG_SITE", "datadoghq.com"
        )
        self.service_name = service_name

    def with_service(self, service_name: str) -> "DatadogMCPClient":
        """Create a new client scoped to a specific service.

        Args:
            service_name: The service name.

        Returns:
            A new DatadogMCPClient instance scoped to the service.
        """
        return DatadogMCPClient(
            api_key=self.configuration.api_key["apiKeyAuth"],
            app_key=self.configuration.api_key["appKeyAuth"],
            site=self.configuration.server_variables["site"],
            service_name=service_name,
        )

    async def get_logs(
        self,
        query: str | None = None,
        status: str = "error",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
    ) -> list[LogEntry]:
        """Retrieve logs from Datadog.

        Args:
            query: Additional search query.
            status: Filter by log status (error, warn, info).
            start_time: Start of the time range.
            end_time: End of the time range.
            limit: Maximum number of logs to return.

        Returns:
            List of log entries.
        """
        if not self.service_name:
            raise ValueError("Service name must be set to get logs")

        filter_parts = [f"service:{self.service_name}"]
        if status:
            filter_parts.append(f"status:{status}")
        if query:
            filter_parts.append(query)

        full_query = " ".join(filter_parts)

        if not start_time:
            start_time = datetime.now(UTC) - timedelta(minutes=30)
        if not end_time:
            end_time = datetime.now(UTC)

        with ApiClient(self.configuration) as api_client:
            api_instance = LogsApi(api_client)
            body = LogsListRequest(
                filter=LogsQueryFilter(
                    query=full_query,
                    _from=start_time.isoformat(),
                    to=end_time.isoformat(),
                ),
                sort=LogsSort.TIMESTAMP_DESCENDING,
                page=LogsListRequestPage(limit=limit),
            )

            try:
                response = api_instance.list_logs(body=body)
                logs = []
                for log in response.data:
                    attr = log.attributes
                    logs.append(
                        LogEntry(
                            timestamp=attr.timestamp.isoformat() if attr.timestamp else None,
                            message=attr.message,
                            status=attr.status,
                            service=attr.service,
                            host=attr.host,
                        )
                    )
                return logs
            except Exception as e:
                logger.error(f"Error fetching logs from Datadog: {e}")
                return []

    async def get_metrics(
        self,
        metric_name: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        aggregation: str = "avg",
    ) -> dict[str, Any]:
        """Query metrics from Datadog.

        Args:
            metric_name: The name of the metric.
            start_time: Start of the time range.
            end_time: End of the time range.
            aggregation: Aggregation method.

        Returns:
            Metric data.
        """
        if not self.service_name:
            raise ValueError("Service name must be set to get metrics")

        if not start_time:
            start_time = datetime.now(UTC) - timedelta(minutes=60)
        if not end_time:
            end_time = datetime.now(UTC)

        query = f"{metric_name}{{service:{self.service_name}}}.{aggregation}()"

        with ApiClient(self.configuration) as api_client:
            api_instance = MetricsApi(api_client)
            try:
                # Simplified for the wrapper
                response = api_instance.query_scalar_data(
                    _from=int(start_time.timestamp()),
                    to=int(end_time.timestamp()),
                    query=query,
                )
                return {"metric": metric_name, "query": query, "data": str(response.data)}
            except Exception as e:
                logger.error(f"Error fetching metrics from Datadog: {e}")
                return {"error": str(e)}


def get_datadog_client() -> ApiClient:
    """Create and configure the Datadog API client for the MCP server."""
    configuration = Configuration()
    configuration.api_key["apiKeyAuth"] = os.getenv("DATADOG_API_KEY")
    configuration.api_key["appKeyAuth"] = os.getenv("DATADOG_APP_KEY")
    configuration.server_variables["site"] = os.getenv("DATADOG_SITE", "datadoghq.com")
    return ApiClient(configuration)


@mcp.tool()
async def dd_get_logs(
    service: str,
    query: str = "",
    status: str = "error",
    lookback_minutes: int = 30,
    limit: int = 50,
) -> dict[str, Any]:
    """Retrieve logs from Datadog for a specific service.

    Args:
        service: The service name to filter by.
        query: Additional search query.
        status: Filter by log status (error, warn, info).
        lookback_minutes: How many minutes to look back.
        limit: Maximum number of logs to return.
    """
    with get_datadog_client() as api_client:
        api_instance = LogsApi(api_client)

        # Build query
        filter_parts = [f"service:{service}"]
        if status:
            filter_parts.append(f"status:{status}")
        if query:
            filter_parts.append(query)

        full_query = " ".join(filter_parts)

        start_time = datetime.now(UTC) - timedelta(minutes=lookback_minutes)

        body = LogsListRequest(
            filter=LogsQueryFilter(
                query=full_query,
                _from=start_time.isoformat(),
                to=datetime.now(UTC).isoformat(),
            ),
            sort=LogsSort.TIMESTAMP_DESCENDING,
            page=LogsListRequestPage(limit=limit),
        )

        try:
            response = api_instance.list_logs(body=body)
            logs = []
            for log in response.data:
                attr = log.attributes
                logs.append(
                    {
                        "timestamp": attr.timestamp.isoformat() if attr.timestamp else None,
                        "message": attr.message,
                        "status": attr.status,
                        "service": attr.service,
                        "host": attr.host,
                    }
                )

            return {
                "status": "success",
                "query": full_query,
                "count": len(logs),
                "logs": logs,
            }
        except Exception as e:
            logger.error(f"Error fetching logs: {e}")
            return {"status": "error", "message": str(e)}


@mcp.tool()
async def dd_get_metrics(
    metric_name: str,
    service: str,
    lookback_minutes: int = 60,
) -> dict[str, Any]:
    """Query metrics from Datadog for a specific service.

    Args:
        metric_name: The name of the metric (e.g. system.cpu.user).
        service: The service name to filter by.
        lookback_minutes: How many minutes of data to retrieve.
    """
    with get_datadog_client() as api_client:
        api_instance = MetricsApi(api_client)

        start_time = int((datetime.now(UTC) - timedelta(minutes=lookback_minutes)).timestamp())
        end_time = int(datetime.now(UTC).timestamp())

        query = f"{metric_name}{{service:{service}}}.avg()"

        try:
            response = api_instance.query_scalar_data(_from=start_time, to=end_time, query=query)
            return {
                "status": "success",
                "metric": metric_name,
                "query": query,
                "data": str(response.data) if hasattr(response, "data") else "No data returned",
            }
        except Exception as e:
            logger.error(f"Error fetching metrics: {e}")
            return {"status": "error", "message": str(e)}


@mcp.tool()
async def dd_list_monitors(
    service: str,
    status: str | None = None,
) -> dict[str, Any]:
    """List Datadog monitors filtered by service.

    Args:
        service: The service name to filter by (via tags).
        status: Optional monitor status (Alert, OK, Warn).
    """
    with get_datadog_client() as api_client:
        api_instance = MonitorsApi(api_client)

        tags = f"service:{service}"

        try:
            monitors = api_instance.list_monitors(monitor_tags=tags)

            result = []
            for m in monitors:
                if status and m.overall_state != status:
                    continue
                result.append(
                    {
                        "id": m.id,
                        "name": m.name,
                        "state": m.overall_state,
                        "type": m.type,
                    }
                )

            return {"status": "success", "service": service, "count": len(result), "monitors": result}
        except Exception as e:
            logger.error(f"Error listing monitors: {e}")
            return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    # Start the MCP server
    mcp.run()
