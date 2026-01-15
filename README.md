# MIRA
Microservice Incident Response Agent
Technical Design Document: Automated MTTR Reduction Agent System



1. Executive Summary

This document outlines the architecture for an automated incident investigation system designed to reduce Mean Time To Recovery (MTTR) for a microservices ecosystem comprising 100+ services. The system utilizes Google Agent Development Kit (ADK) as the agent framework and integrates with Datadog and Azure DevOps via the Model Context Protocol (MCP).

The core objective is to automate the "Triage" phase of incident response: detecting an anomaly, identifying the corresponding code changes, and correlating them to find the root cause without human intervention.

2. High-Level Architecture

2.1 The Challenge of Scale

A traditional "polling" agent architecture (where an agent asks "Is anything wrong?" every minute) fails at 100+ services due to:

API Rate Limits: 100 services * 1 call/min = Instant throttling by Datadog/Azure.

Noise: Agents get distracted by non-critical logs.

Cost: Continuous LLM inference on healthy services is wasteful.

2.2 The Solution: Event-Driven Dispatcher Pattern

The proposed solution uses a Dispatcher-Worker pattern triggered by webhooks. The system remains dormant until an alert fires.

System Diagram Description:

Trigger: Datadog Monitor fires a Webhook to the Dispatcher Service.

Routing: Dispatcher looks up metadata in the Service Registry.

Instantiation: Dispatcher spins up an ephemeral Worker Agent (Google ADK) scoped strictly to the impacting service.

Investigation: Worker Agent connects to Datadog MCP (for logs) and Azure DevOps MCP (for commits).

Resolution: Worker Agent generates a Root Cause Analysis (RCA) report and posts it to the Incident Channel/Ticket.

3. Component Design

3.1 The Dispatcher Service

Role: The entry point (API Gateway). It is "dumb" and fast.

Tech Stack: Python (FastAPI/Flask) running on Serverless (e.g., Google Cloud Run).

Responsibilities:

Validate incoming Webhook signature (security).

Extract service_name, timestamp, and alert_type from the payload.

Query the Service Registry to find the repo associated with the service.

Initialize the Worker Agent with this specific context.

3.2 The Service Registry

Role: The "Map" between observability and source control.

Storage: A simple JSON file, Redis, or Firestore.

Schema:

{
  "service-payment-v1": {
    "repo_name": "payment-api-core",
    "adk_profile": "backend_investigator",
    "owner_team": "team-fintech"
  },
  "service-frontend-web": {
    "repo_name": "web-portal-react",
    "adk_profile": "frontend_investigator",
    "owner_team": "team-ux"
  }
}


3.3 The Worker Agent (Google ADK)

Role: The intelligent investigator. Ephemeral (lives only for the duration of the analysis).

Framework: Google ADK (Python SDK).

System Prompt Strategy:

"You are an expert SRE investigator. You have been summoned to investigate an alert for service {SERVICE_NAME}. You must ONLY query logs for this service and ONLY check code changes in the {REPO_NAME} repository. Do not hallucinate data from other services."

Tool Integration:

Datadog MCP Client: configured with filter="service:{SERVICE_NAME}".

Azure DevOps MCP Client: configured with project="{PROJECT}" and repo="{REPO_NAME}".

4. Detailed Data Flow

Phase 1: Detection

Datadog Monitor [High Error Rate: PaymentService] triggers.

Webhook POST sent to https://api.internal/auto-triage.

Payload: { "service": "payment-svc", "time": "10:05", "env": "prod" }.

Phase 2: Orchestration

Dispatcher receives payload.

Dispatcher calls Registry: get_repo("payment-svc") -> returns payment-backend-core.

Dispatcher initializes Google ADK Agent with a Scoped Toolset:

Tool: get_logs(service="payment-svc") (Hardcoded filter)

Tool: get_commits(repo="payment-backend-core") (Hardcoded filter)

Phase 3: Investigation (The Loop)

The Agent executes the following reasoning loop:

Thought: "I need to see the error stack trace."

Action: Calls Datadog MCP -> get_logs(start_time="10:00", end_time="10:05", status="error").

Observation: Receives NullReferenceException at PaymentController.cs:45.

Thought: "I need to see who touched PaymentController.cs recently."

Action: Calls Azure DevOps MCP -> get_commits(file="PaymentController.cs", lookback="2 hours").

Observation: Commit abc1234 by developer@company.com: "Refactored null checks".

Phase 4: Reporting

Agent correlates the timestamp of Commit abc1234 with the start of the error spike.

Agent posts to Slack/Azure Boards:

Root Cause: Commit abc1234.

Confidence: High (Stack trace line matches diff).

Action: Revert immediately.

5. Scalability Strategy

5.1 Concurrency Handling

Serverless Runtime: The Dispatcher and Agents should run on a platform like Cloud Run or Azure Container Apps.

Scaling Behavior:

0 alerts = 0 containers running (Cost: ~$0).

1 alert = 1 container.

50 simultaneous alerts (major outage) = 50 containers spin up instantly.

MCP Server Scaling: The MCP Servers (Datadog/Azure) should be deployed as stateless microservices that can accept connections from multiple Agent containers.

5.2 Rate Limit Protection

Caching: Implement a simplified caching layer for the Azure DevOps MCP server. If 5 agents request the "latest commit" for the same repo within 1 second, serve from cache.

Backoff: Implement exponential backoff in the ADK agent's tool definition if MCP returns HTTP 429.

6. Security Considerations

Secrets Management: API Keys for Datadog and PATs (Personal Access Tokens) for Azure DevOps must be stored in a Secret Manager (e.g., Azure Key Vault or Google Secret Manager) and injected into the Agent container at runtime.

Read-Only Access: The Azure DevOps MCP token used by the agent should have Read-Only permissions to code and Write permissions only to Comments/Work Items. It should never have permission to push code or delete pipelines.

7. Implementation Roadmap

POC: Build a single script connecting Google ADK to Datadog MCP (local test).

Phase 1: Implement the "Dispatcher" and "Service Registry" with hardcoded maps.

Phase 2: Containerize the solution and deploy to Serverless environment.

Phase 3: Enable "Auto-Comment" on Azure DevOps Pull Requests.
