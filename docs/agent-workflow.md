# Investigator Agent Workflow

The `InvestigatorAgent` is the core logic unit of MIRA. This document outlines its lifecycle.

## 1. Initialization
When an alert webhook hits the Dispatcher, `create_investigator_agent` is called with:
- **InvestigationContext**: Details about the alert (Service Name, Alert Title, Timestamp, etc.).
- **Settings**: Global configuration (API keys, Org URLs).

## 2. Tool Discovery (Dynamic Loading)
Before the agent starts "thinking", it connects to the MCP servers to discover available capabilities.

1.  **Azure DevOps Connection**:
    - Launches the Node.js process.
    - Handshakes via MCP protocol.
    - Loads tools like `wit_create_work_item`, `repo_search_commits`.

2.  **Datadog Connection**:
    - Launches the Python `fastmcp` process.
    - Handshakes via MCP protocol.
    - Loads tools like `dd_get_logs`, `dd_get_metrics`.

## 3. The Investigation Loop (Google ADK)
The agent operates within a `Runner` loop managed by the Google Agent Development Kit.

1.  **System Prompt**: The agent is primed with `INVESTIGATOR_SYSTEM_PROMPT`. This prompt contains strict rules:
    - Always filter logs by `service:{service_name}`.
    - Correlate errors with timestamps.
    - Create a Bug ticket only if confidence is high.

2.  **Reasoning Trace**:
    - The agent receives the initial alert message.
    - It decides to call a tool (e.g., `dd_get_logs`).
    - It analyzes the output.
    - It iterates (maybe checking code changes next).

3.  **Action**:
    - If a root cause is found, it calls `wit_create_work_item`.

## 4. Observability (`ddtrace`)
The entire execution is wrapped in `ddtrace` decorators:
- `@workflow`: Tracks the end-to-end investigation time.
- `@agent`: Tracks the specific interaction with the LLM.

This data is sent to **Datadog LLM Observability**, allowing developers to debug the agent's "thought process" and optimize the system prompt.
