# Investigator Agent Workflow

The `InvestigatorAgent` is the core logic unit of MIRA. This document outlines its lifecycle, decision-making process, and tool usage.

## 1. The Trigger (Webhook)
**Important:** The Agent does **NOT** poll Datadog continuously. It is **event-driven**.

1.  **Observability Detection:** Datadog (or another monitoring tool) detects a spike in errors or latency and fires an alert.
2.  **Dispatcher Action:** The MIRA Dispatcher receives the webhook, verifies it, and spawns a new `InvestigatorAgent` specific to that service.
3.  **Context Injection:** The Agent starts with full context: "I am investigating the 'Payment-Service' because 'High Error Rate' was detected at 10:45 AM."

## 2. Tool Discovery
Before the agent starts "thinking", it connects to the MCP servers to discover available capabilities.

1.  **Azure DevOps Connection**: Loads tools like `wit_create_work_item`, `repo_search_commits`.
2.  **Datadog Connection**: Loads tools like `dd_get_logs`, `dd_get_metrics`.

## 3. The Investigation Loop (Reasoning & Action)
The agent operates within a loop managed by the Google Agent Development Kit. This is where the "Brain" (Gemini) makes decisions.

### Step A: Evidence Gathering (Datadog)
*   **Agent Thought:** "I need to see what actually broke. I will check the logs around the alert time."
*   **Tool Call:** `dd_get_logs(service="payment-service", status="error", lookback_minutes=15)`
*   **Observation:** The Agent receives a list of raw logs, e.g., `ConnectionRefusedError: Database at 10.0.0.5 is unreachable`.

### Step B: Correlation (Azure DevOps)
*   **Agent Thought:** "This looks like a database connection issue. Was configuration changed recently?"
*   **Tool Call:** `repo_search_commits(repo="payment-repo", query="database config")`
*   **Observation:** The Agent sees a commit merged 10 minutes ago: `feat: update db connection string`.

### Step C: The Decision (Gemini Brain)
The LLM analyzes the gathered evidence against the `INVESTIGATOR_SYSTEM_PROMPT`.

*   **Scenario 1: High Confidence (Root Cause Found)**
    *   *Reasoning:* "The error log matches the timestamp of the config change commit exactly. This is definitely a bug."
    *   *Action:* `wit_create_work_item(title="[RCA] Database Config Error", type="Bug")`

*   **Scenario 2: Low Confidence (Ambiguous)**
    *   *Reasoning:* "I see errors, but no recent code changes match. It might be a cloud provider outage."
    *   *Action:* The Agent reports its findings but **does NOT** create a ticket to avoid spamming the team.

## 4. Final Output (RCA Report)
Regardless of whether a ticket was created, the Agent generates a Markdown Root Cause Analysis (RCA) report summarizing:
*   **What happened:** (The Alert)
*   **What was found:** (The Logs & Commits)
*   **The Verdict:** (Bug Created ID #1234 OR "Further manual investigation required")

## 5. Observability (`ddtrace`)
The entire execution is wrapped in `ddtrace` decorators (`@workflow`, `@agent`). This data is sent to **Datadog LLM Observability**, allowing developers to review why the agent made a specific decision.
