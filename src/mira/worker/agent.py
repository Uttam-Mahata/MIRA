"""
Worker Agent implementation using Google Agent Development Kit (ADK).

The Worker Agent is the intelligent investigator that analyzes incidents.
It is ephemeral and lives only for the duration of the analysis.

This module supports two modes of operation:
1. Direct MCP Integration - Uses MCPToolset from Google ADK to connect
   directly to external MCP servers (Azure DevOps, Datadog, GitHub).
2. Fallback Mode - Uses local tool implementations when MCP servers
   are not available or MCP toolset is not configured.

The agent workflow:
1. Retrieves logs, traces, and metrics from Datadog for the affected service
2. Analyzes the data using Gemini model to identify root cause
3. Creates a ticket in Azure DevOps if configured
4. Notifies the team via Teams or Google Space
"""

import logging
from typing import Any

from google.adk.agents import Agent

from mira.config.settings import Settings
from mira.mcp_clients.azure_devops_client import AzureDevOpsMCPClient
from mira.mcp_clients.datadog_client import DatadogMCPClient
from mira.mcp_clients.mcp_toolset import get_investigation_mcp_tools
from mira.registry.models import InvestigationContext
from mira.utils.notifications import create_notification_tools
from mira.worker.tools import get_investigation_tools

logger = logging.getLogger(__name__)


# System prompt template for the investigator agent
INVESTIGATOR_SYSTEM_PROMPT = """You are an expert SRE investigator agent. You have been summoned to investigate an alert for service "{service_name}".

## Context
- **Service**: {service_name}
- **Repository**: {repo_name}
- **Project**: {project}
- **Alert Type**: {alert_type}
- **Alert Title**: {alert_title}
- **Environment**: {environment}
- **Alert Timestamp**: {alert_timestamp}
- **Owner Team**: {owner_team}

## Your Mission
Your goal is to:
1. Identify the root cause of this incident by analyzing observability data
2. Create a ticket in Azure DevOps with your findings (if enabled)
3. Notify the team about the incident and your analysis

## Investigation Guidelines

### Step 1: Gather Observability Data from Datadog
Use the available Datadog tools to collect:
- **Error Logs**: Search for error logs around the alert time using search_logs or get_logs
- **APM Traces**: Look for failed traces using search_traces to understand request flow
- **Metrics**: Query relevant metrics (error rate, latency, CPU, memory) using query_metrics
- **Monitor State**: Check the monitor that triggered the alert using get_monitor

### Step 2: Correlate with Code Changes
Once you identify suspicious errors:
- Use repo_search_commits to find recent commits to affected files
- Look for commits that occurred shortly before errors started
- Check repo_list_pull_requests_by_repo_or_project for recently merged PRs

### Step 3: Analyze and Determine Root Cause
Based on the collected data:
- Correlate error timestamps with deployment or commit times
- Identify the specific code change that likely caused the issue
- Assess the severity and impact of the incident

### Step 4: Create Ticket (if auto_create_tickets is enabled)
Use work_create_work_item to create a ticket with:
- Title: Clear description of the incident
- Description: Include RCA summary, evidence, and recommended action
- Assign to the owner team

### Step 5: Notify the Team
Use the notification tools (notify_teams or notify_google_space) to:
- Alert the team about the incident
- Share the root cause analysis
- Include link to the created ticket

## Important Rules
- Focus on service: {service_name} but consider related services if needed
- Check code changes in repository: {repo_name}
- Do not hallucinate data - only report what you find in the tools
- Be precise about timestamps and commit IDs
- If you cannot determine the root cause, say so clearly and still create a ticket

## Output Format
Provide your findings in a structured Root Cause Analysis (RCA) report with:
1. **Summary**: One-sentence description of the root cause
2. **Evidence**: The specific logs, traces, and commits that support your conclusion
3. **Root Cause**: Detailed explanation with commit ID if identified
4. **Confidence Level**: High, Medium, or Low (with reasoning)
5. **Recommended Action**: What should be done to resolve the issue
"""


class InvestigatorAgent:
    """Agent that investigates incidents using Datadog and Azure DevOps data.

    This agent is ephemeral - it is created for each incident investigation
    and disposed of after generating the RCA report.

    The agent supports two modes:
    1. MCP Mode - Connects directly to external MCP servers using MCPToolset
    2. Fallback Mode - Uses local tool implementations when MCP is unavailable
    """

    def __init__(
        self,
        context: InvestigationContext,
        settings: Settings,
        use_mcp_toolset: bool = True,
    ) -> None:
        """Initialize the investigator agent.

        Args:
            context: The investigation context containing service and alert info.
            settings: Application settings.
            use_mcp_toolset: Whether to use MCPToolset for direct MCP server
                           integration. If False or if MCP servers are not
                           available, falls back to local tool implementations.
        """
        self.context = context
        self.settings = settings
        self.use_mcp_toolset = use_mcp_toolset
        self._agent: Agent | None = None
        # MCP tools list - populated by get_investigation_mcp_tools which handles dynamic imports
        self._mcp_tools: list[Any] = []

        # Try to load MCP toolsets if enabled
        if use_mcp_toolset:
            self._mcp_tools = get_investigation_mcp_tools(
                settings=settings,
                organization=settings.azure_devops_organization,
                service_name=context.service_name,
            )

        # Create scoped MCP clients for fallback mode
        self.datadog_client = DatadogMCPClient(
            api_key=settings.datadog_api_key or "",
            app_key=settings.datadog_app_key or "",
            site=settings.datadog_site,
            service_name=context.service_name,
        )

        self.azure_client = AzureDevOpsMCPClient(
            organization_url=settings.azure_devops_organization_url,
            organization=settings.azure_devops_organization,
            pat=settings.azure_devops_pat,
            project=context.project,
            repo_name=context.repo_name,
        )

    def _build_system_prompt(self) -> str:
        """Build the system prompt with context substitution."""
        return INVESTIGATOR_SYSTEM_PROMPT.format(
            service_name=self.context.service_name,
            repo_name=self.context.repo_name,
            project=self.context.project,
            alert_type=self.context.alert_type,
            alert_title=self.context.alert_title,
            environment=self.context.environment,
            alert_timestamp=self.context.alert_timestamp,
            owner_team=self.context.owner_team,
        )

    def _create_agent(self) -> Agent:
        """Create the Google ADK agent with tools.

        Returns:
            Configured Agent instance.
        """
        # Determine which tools to use
        if self._mcp_tools:
            # Use MCP toolsets for direct server integration
            tools: list[Any] = list(self._mcp_tools)
            logger.info(
                f"Using {len(tools)} MCP toolsets for investigation "
                f"(service: {self.context.service_name})"
            )
        else:
            # Fallback to local tool implementations
            tools = get_investigation_tools(
                datadog_client=self.datadog_client,
                azure_client=self.azure_client,
                context=self.context,
            )
            logger.info(
                f"Using fallback tools for investigation (service: {self.context.service_name})"
            )

        # Add notification tools if configured
        notification_tools = create_notification_tools(self.settings)
        if notification_tools:
            tools.extend(notification_tools)
            logger.info(f"Added {len(notification_tools)} notification tools")

        agent = Agent(
            name=f"investigator_{self.context.service_name}",
            model=self.settings.llm_model,
            instruction=self._build_system_prompt(),
            description=f"SRE investigator for {self.context.service_name}",
            tools=tools,
        )

        logger.info(f"Created investigator agent for service: {self.context.service_name}")

        return agent

    @property
    def agent(self) -> Agent:
        """Get or create the agent instance."""
        if self._agent is None:
            self._agent = self._create_agent()
        return self._agent

    async def investigate(self) -> dict[str, Any]:
        """Run the investigation and return the RCA report.

        Returns:
            Dictionary containing the investigation results and RCA.
        """
        logger.info(
            f"Starting investigation for {self.context.service_name} "
            f"(alert: {self.context.alert_title})"
        )

        # The initial prompt to kick off the investigation
        initial_prompt = f"""An alert has been triggered for service {self.context.service_name}.

Alert Details:
- Type: {self.context.alert_type}
- Title: {self.context.alert_title}
- Time: {self.context.alert_timestamp}
- Environment: {self.context.environment}

Please investigate this incident and provide a Root Cause Analysis (RCA) report.
Start by getting the error logs from around the alert time.
"""

        # In a full implementation, we would run the agent here
        # For now, return a placeholder response
        logger.info("Investigation complete (placeholder)")

        return {
            "status": "completed",
            "service": self.context.service_name,
            "alert_type": self.context.alert_type,
            "rca": {
                "summary": "Investigation placeholder - agent framework initialized",
                "evidence": [],
                "root_cause": "Pending actual agent execution",
                "confidence": "N/A",
                "recommended_action": "Deploy with actual API credentials to run investigations",
            },
            "investigation_prompt": initial_prompt,
        }


def create_investigator_agent(
    context: InvestigationContext,
    settings: Settings,
    use_mcp_toolset: bool = True,
) -> InvestigatorAgent:
    """Factory function to create an investigator agent.

    Args:
        context: The investigation context.
        settings: Application settings.
        use_mcp_toolset: Whether to use MCPToolset for direct MCP server
                        integration. Defaults to True.

    Returns:
        Configured InvestigatorAgent instance.
    """
    return InvestigatorAgent(
        context=context,
        settings=settings,
        use_mcp_toolset=use_mcp_toolset,
    )
