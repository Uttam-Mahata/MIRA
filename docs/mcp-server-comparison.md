# MCP Server Implementation Comparison: Azure DevOps vs. Datadog

This document details the technical differences in how MIRA integrates its two Model Context Protocol (MCP) servers. While both are accessed via the **Stdio Transport**, their underlying implementations and invocation strategies differ.

## 1. The Transport Layer: Stdio (Standard Input/Output)

Both servers are integrated using the **Stdio Transport** mechanism. This means MIRA (the host) spawns the MCP server as a **subprocess** and communicates with it by:
- Writing JSON-RPC requests to the subprocess's **Standard Input (stdin)**.
- Reading JSON-RPC responses from the subprocess's **Standard Output (stdout)**.
- **Stderr** is reserved for logs and debugging information, which does not interfere with the protocol.

## 2. Azure DevOps MCP Server (Node.js)

The Azure DevOps integration uses the official Microsoft package `@azure-devops/mcp`.

### Technical Characteristics
*   **Runtime**: Node.js
*   **Library**: Official `@azure-devops/mcp` package (built locally from source in this repo).
*   **Connection Method**: `StdioServerParams` calling the `node` executable.

### Invocation Strategy
MIRA spawns the Node.js process with specific command-line arguments required by the server's CLI interface.

```bash
# Conceptual command line execution
ADO_MCP_AUTH_TOKEN="<PAT>" node azure-devops-mcp/dist/index.js <ORG_NAME> --authentication envvar
```

### Key Configuration Differences
1.  **Positional Arguments**: Requires the Azure DevOps **Organization Name** as the first argument.
2.  **Authentication Flags**: Requires explicit flags `--authentication envvar` to tell the server to look for a token in the environment.
3.  **Specific Env Var**: It strictly looks for `ADO_MCP_AUTH_TOKEN` for the Personal Access Token (PAT).

## 3. Datadog MCP Server (Python)

The Datadog integration is a custom implementation built within MIRA using `fastmcp`.

### Technical Characteristics
*   **Runtime**: Python
*   **Library**: `fastmcp` (Server) + `datadog-api-client` (Logic).
*   **Connection Method**: `StdioServerParams` calling the `python` executable.

### Invocation Strategy
MIRA spawns the Python process. `fastmcp` automatically handles the Stdio protocol when the script is run directly.

```bash
# Conceptual command line execution
DATADOG_API_KEY="..." DATADOG_APP_KEY="..." python src/mira/mcp_clients/datadog_client.py
```

### Key Configuration Differences
1.  **No CLI Args**: The script `datadog_client.py` doesn't require positional arguments for configuration.
2.  **Standard Env Vars**: It reads standard Datadog environment variables (`DATADOG_API_KEY`, `DATADOG_APP_KEY`, `DATADOG_SITE`) directly within the Python code.
3.  **FastMCP Magic**: The `if __name__ == "__main__": mcp.run()` block in the script detects it is being run as a script and starts the Stdio listener.

## Summary Table

| Feature | Azure DevOps MCP | Datadog MCP |
| :--- | :--- | :--- |
| **Language** | Node.js | Python |
| **Base Library** | `@azure-devops/mcp` | `fastmcp` |
| **Process** | Subprocess (`node`) | Subprocess (`python`) |
| **Config Injection** | CLI Arguments + Env Vars | Env Vars Only |
| **Auth Token Var** | `ADO_MCP_AUTH_TOKEN` | `DATADOG_API_KEY` |
| **Initialization** | Requires Organization Name arg | Self-contained |

## Orchestration in MIRA

In `src/mira/worker/agent.py`, MIRA uses `AsyncExitStack` to manage the lifecycles of these two disparate processes simultaneously.

```python
# Pseudo-code visualization of the parallel loading
async with AsyncExitStack() as stack:
    # 1. Spawn Node.js process for ADO
    ado_client = await start_stdio_client("node", ["index.js", "my-org", ...])
    
    # 2. Spawn Python process for Datadog
    dd_client = await start_stdio_client("python", ["datadog_client.py"])
    
    # 3. Aggregate tools
    all_tools = ado_client.tools + dd_client.tools
    
    # 4. Agent runs...
```

This architecture allows MIRA to remain language-agnostic regarding its tools. It doesn't matter if a tool is written in Python, Node.js, or Go, as long as it speaks the MCP JSON-RPC protocol over Stdio.
