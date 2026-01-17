# MCP Client Integrations

MIRA uses two distinct MCP servers to provide tools to the Agent.

## 1. Datadog MCP Client
**Technology**: Python (`fastmcp` + `datadog-api-client`)  
**Location**: `src/mira/mcp_clients/datadog_client.py`

This client is built in-house to expose Datadog's API as MCP tools.

### Why `datadog-api-client`?
We use the official [datadog-api-client-python](https://github.com/DataDog/datadog-api-client-python) because the agent needs to **query** the Datadog API to fetch:
- Logs (`dd_get_logs`)
- Metrics (`dd_get_metrics`)
- Monitors (`dd_list_monitors`)

### Integration Architecture
The Agent spawns this client as a subprocess using `StdioServerParams`.
```python
# src/mira/worker/agent.py
datadog_tools = await MCPToolset.from_server(
    connection_params=StdioServerParams(
        command=sys.executable,
        args=["src/mira/mcp_clients/datadog_client.py"],
        env={...}
    )
)
```

---

## 2. Azure DevOps MCP Client
**Technology**: Node.js (`@azure-devops/mcp`)  
**Location**: `azure-devops-mcp/` (Submodule/Local Package)

We leverage the official Microsoft MCP server implementation for Azure DevOps.

### Configuration Details
Unlike the Python client, this Node.js server requires specific command-line arguments to function via stdio:

1.  **Organization Name**: Passed as a positional argument.
2.  **Authentication Mode**: Must be set to `envvar` to use environment variables.
3.  **Token Variable**: The Personal Access Token (PAT) must be in `ADO_MCP_AUTH_TOKEN`.

### Integration Architecture
```python
# src/mira/worker/agent.py
azure_tools = await MCPToolset.from_server(
    connection_params=StdioServerParams(
        command="node",
        args=[
            "azure-devops-mcp/dist/index.js",
            "MY_ORG_NAME",          # Positional Arg 1: Organization
            "--authentication",     # Flag: Auth Type
            "envvar"                # Value: envvar
        ],
        env={
            "ADO_MCP_AUTH_TOKEN": "..." # The actual PAT
        }
    )
)
```

## Comparison: `ddtrace` vs `datadog-api-client`

| Component | Library Used | Purpose |
|-----------|--------------|---------|
| **The Tools** | `datadog-api-client` | Allows the *Agent* to see external data (logs, metrics) to investigate incidents. |
| **The Agent** | `ddtrace` | Allows *You* to see the Agent's internal performance, prompts, and token usage (LLM Observability). |
