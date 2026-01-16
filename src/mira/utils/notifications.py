"""
Notification tools for sending alerts to Teams and Google Space.

This module provides tools for notifying teams about incident analysis results
through Microsoft Teams webhooks and Google Chat (Space) webhooks.
"""

import logging
from typing import Any

import httpx

from mira.config.settings import Settings

logger = logging.getLogger(__name__)


async def send_teams_notification(
    webhook_url: str,
    title: str,
    summary: str,
    details: dict[str, Any],
    severity: str = "high",
) -> dict[str, Any]:
    """Send a notification to Microsoft Teams via webhook.

    Args:
        webhook_url: The Teams incoming webhook URL.
        title: Notification title.
        summary: Brief summary of the incident.
        details: Detailed information including RCA.
        severity: Severity level (low, medium, high, critical).

    Returns:
        Response status from Teams.
    """
    # Map severity to Teams colors
    color_map = {
        "low": "00FF00",  # Green
        "medium": "FFFF00",  # Yellow
        "high": "FFA500",  # Orange
        "critical": "FF0000",  # Red
    }

    color = color_map.get(severity.lower(), "FFA500")

    # Build the adaptive card for Teams
    card = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": color,
        "summary": summary,
        "sections": [
            {
                "activityTitle": title,
                "facts": [
                    {"name": "Service", "value": details.get("service", "Unknown")},
                    {"name": "Environment", "value": details.get("environment", "Unknown")},
                    {"name": "Alert Type", "value": details.get("alert_type", "Unknown")},
                    {"name": "Severity", "value": severity.upper()},
                ],
                "markdown": True,
            },
            {
                "activityTitle": "Root Cause Analysis",
                "text": details.get("rca_summary", "Analysis pending..."),
                "markdown": True,
            },
        ],
    }

    # Add recommended action if available
    if details.get("recommended_action"):
        card["sections"].append(
            {
                "activityTitle": "Recommended Action",
                "text": details.get("recommended_action"),
                "markdown": True,
            }
        )

    # Add link to ticket if created
    if details.get("ticket_url"):
        card["potentialAction"] = [
            {
                "@type": "OpenUri",
                "name": "View Ticket",
                "targets": [{"os": "default", "uri": details.get("ticket_url")}],
            }
        ]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=card,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            response.raise_for_status()

        logger.info(f"Teams notification sent successfully for: {title}")
        return {"status": "success", "message": "Teams notification sent"}

    except Exception as e:
        logger.error(f"Failed to send Teams notification: {e}")
        return {"status": "error", "message": str(e)}


async def send_google_space_notification(
    webhook_url: str,
    title: str,
    summary: str,
    details: dict[str, Any],
    severity: str = "high",
) -> dict[str, Any]:
    """Send a notification to Google Chat Space via webhook.

    Args:
        webhook_url: The Google Chat Space webhook URL.
        title: Notification title.
        summary: Brief summary of the incident.
        details: Detailed information including RCA.
        severity: Severity level (low, medium, high, critical).

    Returns:
        Response status from Google Chat.
    """
    # Map severity to emojis for visual indication
    emoji_map = {
        "low": "🟢",
        "medium": "🟡",
        "high": "🟠",
        "critical": "🔴",
    }

    emoji = emoji_map.get(severity.lower(), "🟠")

    # Build the Google Chat card message
    message = {
        "cards": [
            {
                "header": {
                    "title": f"{emoji} {title}",
                    "subtitle": summary,
                },
                "sections": [
                    {
                        "header": "Incident Details",
                        "widgets": [
                            {
                                "keyValue": {
                                    "topLabel": "Service",
                                    "content": details.get("service", "Unknown"),
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Environment",
                                    "content": details.get("environment", "Unknown"),
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Alert Type",
                                    "content": details.get("alert_type", "Unknown"),
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Severity",
                                    "content": severity.upper(),
                                }
                            },
                        ],
                    },
                    {
                        "header": "Root Cause Analysis",
                        "widgets": [
                            {
                                "textParagraph": {
                                    "text": details.get("rca_summary", "Analysis pending...")
                                }
                            }
                        ],
                    },
                ],
            }
        ]
    }

    # Add recommended action if available
    if details.get("recommended_action"):
        message["cards"][0]["sections"].append(
            {
                "header": "Recommended Action",
                "widgets": [{"textParagraph": {"text": details.get("recommended_action")}}],
            }
        )

    # Add button to ticket if created
    if details.get("ticket_url"):
        message["cards"][0]["sections"].append(
            {
                "widgets": [
                    {
                        "buttons": [
                            {
                                "textButton": {
                                    "text": "VIEW TICKET",
                                    "onClick": {"openLink": {"url": details.get("ticket_url")}},
                                }
                            }
                        ]
                    }
                ]
            }
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            response.raise_for_status()

        logger.info(f"Google Space notification sent successfully for: {title}")
        return {"status": "success", "message": "Google Space notification sent"}

    except Exception as e:
        logger.error(f"Failed to send Google Space notification: {e}")
        return {"status": "error", "message": str(e)}


def create_notification_tools(settings: Settings) -> list:
    """Create notification tool functions for the agent.

    These tools allow the agent to notify teams about investigation results.

    Args:
        settings: Application settings containing webhook URLs.

    Returns:
        List of notification tool functions.
    """
    tools = []

    # Create Teams notification tool if configured
    teams_webhook_url = settings.teams_webhook_url
    if teams_webhook_url:

        async def notify_teams(
            title: str,
            summary: str,
            service: str,
            environment: str,
            alert_type: str,
            rca_summary: str,
            severity: str = "high",
            recommended_action: str | None = None,
            ticket_url: str | None = None,
        ) -> dict[str, Any]:
            """Send notification to Microsoft Teams about incident analysis.

            Use this tool to notify the team about investigation results,
            especially when a root cause has been identified or action is needed.

            Args:
                title: Notification title (e.g., "Incident Alert: Payment Service").
                summary: Brief one-line summary of the incident.
                service: Name of the affected service.
                environment: Environment (prod, staging, etc.).
                alert_type: Type of alert (error_rate, latency, etc.).
                rca_summary: Summary of the root cause analysis.
                severity: Severity level (low, medium, high, critical).
                recommended_action: Recommended action to resolve the issue.
                ticket_url: URL to the created ticket (if any).

            Returns:
                Status of the notification.
            """
            details = {
                "service": service,
                "environment": environment,
                "alert_type": alert_type,
                "rca_summary": rca_summary,
                "recommended_action": recommended_action,
                "ticket_url": ticket_url,
            }
            return await send_teams_notification(
                teams_webhook_url, title, summary, details, severity
            )

        tools.append(notify_teams)
        logger.info("Teams notification tool enabled")

    # Create Google Space notification tool if configured
    google_space_webhook_url = settings.google_space_webhook_url
    if google_space_webhook_url:

        async def notify_google_space(
            title: str,
            summary: str,
            service: str,
            environment: str,
            alert_type: str,
            rca_summary: str,
            severity: str = "high",
            recommended_action: str | None = None,
            ticket_url: str | None = None,
        ) -> dict[str, Any]:
            """Send notification to Google Chat Space about incident analysis.

            Use this tool to notify the team about investigation results,
            especially when a root cause has been identified or action is needed.

            Args:
                title: Notification title (e.g., "Incident Alert: Payment Service").
                summary: Brief one-line summary of the incident.
                service: Name of the affected service.
                environment: Environment (prod, staging, etc.).
                alert_type: Type of alert (error_rate, latency, etc.).
                rca_summary: Summary of the root cause analysis.
                severity: Severity level (low, medium, high, critical).
                recommended_action: Recommended action to resolve the issue.
                ticket_url: URL to the created ticket (if any).

            Returns:
                Status of the notification.
            """
            details = {
                "service": service,
                "environment": environment,
                "alert_type": alert_type,
                "rca_summary": rca_summary,
                "recommended_action": recommended_action,
                "ticket_url": ticket_url,
            }
            return await send_google_space_notification(
                google_space_webhook_url, title, summary, details, severity
            )

        tools.append(notify_google_space)
        logger.info("Google Space notification tool enabled")

    return tools
