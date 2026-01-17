"""
Datadog MCP Server for retrieving logs and metrics.

This module implements an MCP server using FastMCP and the official Datadog API client.
It provides tools for Worker Agents to investigate microservices.
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

logger = logging.getLogger(__name__)

# Initialize FastMCP
mcp = FastMCP("datadog")


def get_datadog_client() -> ApiClient:
    """Create and configure the Datadog API client."""
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
            filter=LogsListRequestFilter(
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
                logs.append({
                    "timestamp": attr.timestamp.isoformat() if attr.timestamp else None,
                    "message": attr.message,
                    "status": attr.status,
                    "service": attr.service,
                    "host": attr.host,
                })
            
            return {
                "status": "success",
                "query": full_query,
                "count": len(logs),
                "logs": logs
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
            # Note: Metrics query API might differ slightly in implementation details
            # depending on whether it's V1 or V2. V2 uses query_scalar_data or similar.
            # This is a simplified representation.
            response = api_instance.query_scalar_data(
                _from=start_time,
                to=end_time,
                query=query
            )
            return {
                "status": "success",
                "metric": metric_name,
                "query": query,
                "data": str(response.data) if hasattr(response, 'data') else "No data returned"
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
            # Monitors API is typically V1 in the official client for listing
            # But we'll try to use the configured instance
            monitors = api_instance.list_monitors(monitor_tags=tags)
            
            result = []
            for m in monitors:
                if status and m.overall_state != status:
                    continue
                result.append({
                    "id": m.id,
                    "name": m.name,
                    "state": m.overall_state,
                    "type": m.type,
                })
            
            return {
                "status": "success",
                "service": service,
                "count": len(result),
                "monitors": result
            }
        except Exception as e:
            logger.error(f"Error listing monitors: {e}")
            return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    # Start the MCP server
    mcp.run()
