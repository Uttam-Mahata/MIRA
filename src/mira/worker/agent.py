"""
Worker Agent implementation using Google Agent Development Kit (ADK).

The Worker Agent is the intelligent investigator that analyzes incidents.
It is ephemeral and lives only for the duration of the analysis.
"""

import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from ddtrace.llmobs.decorators import agent, workflow
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StdioServerParameters,
)
from google.genai import types as genai_types

from mira.config.settings import Settings
from mira.registry.models import InvestigationContext

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
Your goal is to identify the root cause of this incident by correlating logs from Datadog and code changes from Azure DevOps.
If you find a confirmed root cause, you must create a Bug ticket in Azure DevOps.

## Investigation Guidelines

1. **Start with logs (Datadog)**:
   - Use `dd_get_logs` to find error logs around the alert time.
   - **CRITICAL**: You MUST ALWAYS filter by `service:{service_name}`. Never query logs without this filter.
   - Look for stack traces, exception messages, and error patterns.

2. **Correlate with code (Azure DevOps)**:
   - Once you have a suspect file or error message, use the Azure DevOps tools to find recent changes.
   - Filter commits by the file paths seen in the stack traces.
   - Look for commits merged shortly before the alert timestamp.

3. **Take Action (Azure DevOps)**:
   - If you identify the root cause with **High Confidence**:
     - Use `wit_create_work_item` to create a "Bug" in project "{project}".
     - **Title**: "[RCA] {alert_title} - Root Cause Identified"
     - **Description**: Provide a detailed summary of the findings, including the specific error logs and the commit that caused it. Tag the owner team: {owner_team}.
     - **Fields**: Set `System.AreaPath` if known, otherwise leave default.

## Important Rules
- **Multi-Tenant Safety**: You are running in a shared environment. NEVER query data without `service:{service_name}` or `repo:{repo_name}` filters.
- **Fact-Based**: Do not guess. If you can't find the root cause, state "Root Cause Unknown".
- **Tool Usage**: Use the provided MCP tools. Do not hallucinate tool names.

## Output Format
Provide your final response as a structured Root Cause Analysis (RCA) report:
1. **Summary**: One-sentence description.
2. **Evidence**: Logs and commits (IDs/timestamps).
3. **Root Cause**: The specific commit or config change.
4. **Ticket Created**: The ID/Link of the Azure DevOps Bug created (or "None").
5. **Recommended Action**: Revert commit, rollback, etc.
"""


class InvestigatorAgent:
    """Agent that investigates incidents using Datadog and Azure DevOps data.

    This agent is ephemeral - it is created for each incident investigation
    and disposed of after generating the RCA report.
    """

    def __init__(
        self,
        context: InvestigationContext,
        settings: Settings,
    ) -> None:
        """Initialize the investigator agent.

        Args:
            context: The investigation context containing service and alert info.
            settings: Application settings.
        """
        self.context = context
        self.settings = settings

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

    async def _get_mcp_tools(self, exit_stack: AsyncExitStack) -> list:
        """Fetch tools dynamically from MCP servers.

        Args:
            exit_stack: AsyncExitStack to manage server connections.

        Returns:
            List of tools from all connected MCP servers.
        """
        all_tools = []

        # 1. Connect to Azure DevOps (Stdio/Node)
        try:
            mcp_path = os.path.abspath(self.settings.azure_mcp_path)
            logger.info(f"Connecting to Azure DevOps MCP via Stdio: {mcp_path}")

            # azure-devops-mcp expects: node index.js <org> --authentication envvar
            # and the token in ADO_MCP_AUTH_TOKEN env var
            azure_tools, azure_stack = await MCPToolset.from_server(
                connection_params=StdioServerParams(
                    command="node",
                    args=[
                        mcp_path,
                        self.settings.azure_devops_organization or "",
                        "--authentication",
                        "envvar",
                    ],
                    env={
                        "ADO_MCP_AUTH_TOKEN": self.settings.azure_devops_pat or "",
                    },
                )
            )
            await exit_stack.enter_async_context(azure_stack)
            all_tools.extend(azure_tools)
            logger.info(f"Loaded {len(azure_tools)} tools from Azure DevOps MCP")
        except Exception as e:
            logger.error(f"Failed to load Azure DevOps MCP tools: {e}")

        # 2. Connect to Datadog (Stdio/Python)
        # Using the local Python MCP server we just implemented
        try:
            dd_mcp_path = os.path.abspath("src/mira/mcp_clients/datadog_client.py")
            logger.info(f"Connecting to Datadog MCP via Stdio: {dd_mcp_path}")
            
            datadog_tools, datadog_stack = await MCPToolset.from_server(
                connection_params=StdioServerParams(
                    command=sys.executable,
                    args=[dd_mcp_path],
                    env={
                        "DATADOG_API_KEY": self.settings.datadog_api_key or "",
                        "DATADOG_APP_KEY": self.settings.datadog_app_key or "",
                        "DATADOG_SITE": self.settings.datadog_site,
                    }
                )
            )
            await exit_stack.enter_async_context(datadog_stack)
            all_tools.extend(datadog_tools)
            logger.info(f"Loaded {len(datadog_tools)} tools from Datadog MCP")
        except Exception as e:
            logger.error(f"Failed to load Datadog MCP tools: {e}")

        return all_tools

    @workflow(name="investigate_incident")
    async def investigate(self) -> dict[str, Any]:
        """Run the investigation and return the RCA report.

        Returns:
            Dictionary containing the investigation results and RCA.
        """
        logger.info(
            f"Starting investigation for {self.context.service_name} "
            f"(alert: {self.context.alert_title})"
        )

        async with AsyncExitStack() as exit_stack:
            # Fetch tools dynamically
            tools = await self._get_mcp_tools(exit_stack)

            if not tools:
                logger.warning("No tools loaded from MCP servers. Investigation may be limited.")

            # Create the ADK Agent
            agent_obj = Agent(
                name=f"investigator_{self.context.service_name}",
                model=self.settings.llm_model,
                instruction=self._build_system_prompt(),
                description=f"SRE investigator for {self.context.service_name}",
                tools=tools,
            )

            # Setup Runner and Session
            session_service = InMemorySessionService()
            session_id = f"investigation_{self.context.service_name}_{int(os.getpid())}"
            await session_service.create_session(
                app_name="MIRA",
                user_id="system",
                session_id=session_id,
            )

            runner = Runner(
                agent=agent_obj,
                app_name="MIRA",
                session_service=session_service,
            )

            # Kick off the investigation
            initial_message = f"""An alert has been triggered for service {self.context.service_name}.

Alert Details:
- Type: {self.context.alert_type}
- Title: {self.context.alert_title}
- Time: {self.context.alert_timestamp}
- Environment: {self.context.environment}

Please investigate this incident and provide a Root Cause Analysis (RCA) report.
Start by getting the error logs from around the alert time.
"""

            final_response = ""
            
            # Trace the agent execution
            @agent(name="adk_agent_run")
            async def run_agent_loop():
                response_text = ""
                async for event in runner.run_async(
                    user_id="system",
                    session_id=session_id,
                    new_message=genai_types.Content(
                        role="user",
                        parts=[genai_types.Part.from_text(text=initial_message)],
                    ),
                ):
                    if event.is_final_response():
                        response_text = event.content.parts[0].text
                return response_text

            final_response = await run_agent_loop()

            logger.info("Investigation complete")

            return {
                "status": "completed",
                "service": self.context.service_name,
                "alert_type": self.context.alert_type,
                "rca_report": final_response,
                "session_id": session_id,
            }


def create_investigator_agent(
    context: InvestigationContext,
    settings: Settings,
) -> InvestigatorAgent:
    """Factory function to create an investigator agent.

    Args:
        context: The investigation context.
        settings: Application settings.

    Returns:
        Configured InvestigatorAgent instance.
    """
    return InvestigatorAgent(context=context, settings=settings)
