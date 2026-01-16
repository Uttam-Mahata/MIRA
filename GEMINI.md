# MIRA - Microservice Incident Response Agent

## Project Overview
MIRA is an automated incident investigation system designed to reduce Mean Time To Recovery (MTTR) for microservices ecosystems. It uses the Google Agent Development Kit (ADK) to spawn ephemeral agents that investigate alerts by correlating Datadog logs with Azure DevOps code changes via the Model Context Protocol (MCP).

## Technical Architecture
*   **Dispatcher (FastAPI):** Acts as the entry point, receiving webhooks from observability tools (Datadog). It looks up service metadata and spawns a worker agent.
    *   Location: `src/mira/dispatcher/`
*   **Worker Agent (Google ADK):** An ephemeral intelligent agent scoped to a specific service. It uses MCP clients to query logs and commits to find the root cause of incidents.
    *   Location: `src/mira/worker/`
*   **Service Registry:** Maps service names from alerts to their respective repositories and metadata.
    *   Location: `src/mira/registry/`
    *   Config: `config/service_registry.json`
*   **MCP Clients:** specialized clients that wrap MCP server tools for Datadog and Azure DevOps to provide a scoped interface for agents.
    *   Location: `src/mira/mcp_clients/`
    *   **Note:** The Azure DevOps client currently contains placeholder implementations.

## Key Files & Directories
*   `src/mira/dispatcher/main.py`: Application entry point.
*   `src/mira/config/settings.py`: Configuration management using Pydantic Settings.
*   `src/mira/mcp_clients/`: Integration logic for external services (Datadog, Azure DevOps).
*   `docker-compose.yml`: Defines the `mira` service for local development.
*   `pyproject.toml`: Dependency and build configuration.

## Development & Usage

### Prerequisite
Ensure you have the following environment variables set (see `.env.example`):
*   `DATADOG_API_KEY` & `DATADOG_APP_KEY`
*   `AZURE_DEVOPS_PAT`, `AZURE_DEVOPS_ORGANIZATION_URL`
*   `GOOGLE_API_KEY` (for Gemini models)

### Installation
```bash
pip install -e ".[dev]"
```

### Running the Service
**Local:**
```bash
mira
```
**Docker:**
```bash
docker-compose up -d
```

### Testing & Quality
*   **Run Tests:** `pytest`
*   **Coverage:** `pytest --cov=mira`
*   **Linting:** `ruff check src tests`
*   **Type Checking:** `mypy src`

## Submodules
*   `adk-samples/`: Contains reference implementations and examples for Google ADK.
*   `azure-devops-mcp/`: Likely a reference or implementation of the Azure DevOps MCP server.
