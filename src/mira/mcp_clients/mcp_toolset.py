"""
MCP Toolset integration for connecting Google ADK agents to external MCP servers.

This module provides a unified interface for connecting to MCP servers using
various transport methods (stdio, HTTP, SSE) and exposes their tools to
Google ADK agents.

Supported MCP Server Connection Types:
1. StdioConnectionParams - For subprocess-based MCP servers (e.g., azure-devops-mcp)
2. StreamableHTTPConnectionParams - For HTTP-based MCP servers
3. SseConnectionParams - For SSE (Server-Sent Events) based MCP servers
"""

import logging
import os
from typing import Any

from mcp import StdioServerParameters

from mira.config.settings import Settings

logger = logging.getLogger(__name__)


def get_azure_devops_mcp_toolset(
    settings: Settings,
    organization: str | None = None,
) -> Any:
    """Create an MCPToolset for Azure DevOps MCP server.

    The Azure DevOps MCP server runs as a Node.js subprocess and communicates
    via stdio. This function creates a toolset that connects to the server
    and exposes its tools to the Google ADK agent.

    Args:
        settings: Application settings containing Azure DevOps credentials.
        organization: Azure DevOps organization name. If not provided,
                     uses the value from settings.

    Returns:
        MCPToolset configured for Azure DevOps, or None if not configured.
    """
    try:
        from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
    except ImportError:
        logger.warning(
            "google.adk.tools.mcp_tool not available. "
            "Install google-adk with MCP support to use McpToolset."
        )
        return None

    org = organization or settings.azure_devops_organization

    if not org:
        logger.warning(
            "Azure DevOps organization not configured. "
            "Set AZURE_DEVOPS_ORGANIZATION environment variable."
        )
        return None

    # The Azure DevOps MCP server is a Node.js application
    # that can be run via npx or as a local npm package
    server_params = StdioServerParameters(
        command="npx",
        args=[
            "-y",
            "@anthropic/azure-devops-mcp",
            org,
            "--authentication",
            "env",
        ],
        env={
            "AZURE_DEVOPS_PAT": settings.azure_devops_pat or "",
            "PATH": os.environ.get("PATH", ""),
        },
    )

    try:
        toolset = McpToolset(
            connection_params=StdioConnectionParams(server_params=server_params),
            tool_filter=[
                # Repository tools
                "repo_list_repos_by_project",
                "repo_list_pull_requests_by_repo_or_project",
                "repo_get_pull_request_by_id",
                "repo_search_commits",
                "repo_list_branches_by_repo",
                # Work item tools
                "work_create_work_item",
                "work_get_work_item",
                "work_search_work_items",
                "work_update_work_item",
                # Pipeline tools
                "pipelines_list_pipelines",
                "pipelines_get_pipeline",
                "pipelines_list_runs",
            ],
        )
        logger.info(f"Created Azure DevOps McpToolset for organization: {org}")
        return toolset
    except Exception as e:
        logger.error(f"Failed to create Azure DevOps McpToolset: {e}")
        return None


def get_datadog_mcp_toolset(
    settings: Settings,
    service_name: str | None = None,
) -> Any:
    """Create an McpToolset for Datadog MCP server.

    Datadog MCP server can be accessed via HTTP using the
    StreamableHTTPConnectionParams transport.

    Args:
        settings: Application settings containing Datadog credentials.
        service_name: Service name to scope queries to.

    Returns:
        McpToolset configured for Datadog, or None if not configured.
    """
    try:
        from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
    except ImportError:
        logger.warning(
            "google.adk.tools.mcp_tool not available. "
            "Install google-adk with MCP support to use McpToolset."
        )
        return None

    if not settings.datadog_api_key or not settings.datadog_app_key:
        logger.warning(
            "Datadog credentials not configured. "
            "Set DATADOG_API_KEY and DATADOG_APP_KEY environment variables."
        )
        return None

    # Datadog MCP server URL - can be configured via environment
    mcp_server_url = os.getenv("DATADOG_MCP_SERVER_URL", "http://localhost:3001/mcp")

    try:
        toolset = McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=mcp_server_url,
                headers={
                    "DD-API-KEY": settings.datadog_api_key,
                    "DD-APPLICATION-KEY": settings.datadog_app_key,
                },
            ),
            tool_filter=[
                "search_logs",
                "get_logs",
                "query_metrics",
                "list_monitors",
                "get_monitor",
            ],
        )
        logger.info(
            f"Created Datadog McpToolset for site: {settings.datadog_site}"
            + (f", service: {service_name}" if service_name else "")
        )
        return toolset
    except Exception as e:
        logger.error(f"Failed to create Datadog McpToolset: {e}")
        return None


def get_github_mcp_toolset(
    repo_filter: str | None = None,
) -> Any:
    """Create an McpToolset for GitHub MCP server (via Copilot).

    This connects to GitHub's Copilot MCP server for code-related queries.

    Args:
        repo_filter: Optional repository filter (e.g., "owner/repo").

    Returns:
        McpToolset configured for GitHub, or None if not configured.
    """
    try:
        from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
    except ImportError:
        logger.warning(
            "google.adk.tools.mcp_tool not available. "
            "Install google-adk with MCP support to use McpToolset."
        )
        return None

    github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")

    if not github_token:
        logger.warning(
            "GitHub personal access token not configured. "
            "Set GITHUB_PERSONAL_ACCESS_TOKEN environment variable."
        )
        return None

    try:
        toolset = McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="https://api.githubcopilot.com/mcp/",
                headers={
                    "Authorization": f"Bearer {github_token}",
                },
            ),
            tool_filter=[
                "search_repositories",
                "search_issues",
                "list_issues",
                "get_issue",
                "list_pull_requests",
                "get_pull_request",
                "search_code",
            ],
        )
        logger.info(
            "Created GitHub McpToolset" + (f" for repo: {repo_filter}" if repo_filter else "")
        )
        return toolset
    except Exception as e:
        logger.error(f"Failed to create GitHub McpToolset: {e}")
        return None


def get_investigation_mcp_tools(
    settings: Settings,
    organization: str | None = None,
    service_name: str | None = None,
) -> list[Any]:
    """Get all MCP toolsets needed for incident investigation.

    This function creates MCPToolsets for all configured external services
    and returns them as a list that can be passed to a Google ADK agent.

    Args:
        settings: Application settings.
        organization: Azure DevOps organization name.
        service_name: Service name to scope Datadog queries to.

    Returns:
        List of MCPToolset instances for configured services.
    """
    tools = []

    # Add Azure DevOps toolset
    azure_toolset = get_azure_devops_mcp_toolset(settings, organization)
    if azure_toolset:
        tools.append(azure_toolset)

    # Add Datadog toolset
    datadog_toolset = get_datadog_mcp_toolset(settings, service_name)
    if datadog_toolset:
        tools.append(datadog_toolset)

    # Add GitHub toolset (optional, for code search)
    github_toolset = get_github_mcp_toolset()
    if github_toolset:
        tools.append(github_toolset)

    logger.info(f"Loaded {len(tools)} MCP toolsets for investigation")
    return tools
