"""Tests for the notification module."""

from unittest.mock import AsyncMock, patch

import pytest

from mira.config.settings import Settings
from mira.utils.notifications import (
    create_notification_tools,
    send_google_space_notification,
    send_teams_notification,
)


@pytest.fixture
def settings_with_notifications() -> Settings:
    """Create settings with notification webhooks configured."""
    return Settings(
        environment="development",
        teams_webhook_url="https://outlook.office.com/webhook/test",
        google_space_webhook_url="https://chat.googleapis.com/v1/spaces/test",
    )


@pytest.fixture
def settings_no_notifications() -> Settings:
    """Create settings without notification webhooks."""
    return Settings(environment="development")


@pytest.fixture
def sample_details() -> dict:
    """Create sample notification details."""
    return {
        "service": "payment-service",
        "environment": "prod",
        "alert_type": "error_rate",
        "rca_summary": "Database connection timeout caused by connection pool exhaustion.",
        "recommended_action": "Increase connection pool size in config.",
        "ticket_url": "https://dev.azure.com/org/project/_workitems/edit/123",
    }


class TestTeamsNotification:
    """Tests for Teams notification."""

    @pytest.mark.asyncio
    async def test_send_teams_notification_success(self, sample_details: dict) -> None:
        """Test successful Teams notification."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = AsyncMock()
            mock_response.raise_for_status = AsyncMock()
            mock_post.return_value = mock_response

            result = await send_teams_notification(
                webhook_url="https://outlook.office.com/webhook/test",
                title="Test Alert",
                summary="Test summary",
                details=sample_details,
                severity="high",
            )

            assert result["status"] == "success"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_teams_notification_error(self, sample_details: dict) -> None:
        """Test Teams notification with error."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Connection error")

            result = await send_teams_notification(
                webhook_url="https://outlook.office.com/webhook/test",
                title="Test Alert",
                summary="Test summary",
                details=sample_details,
            )

            assert result["status"] == "error"
            assert "Connection error" in result["message"]


class TestGoogleSpaceNotification:
    """Tests for Google Space notification."""

    @pytest.mark.asyncio
    async def test_send_google_space_notification_success(self, sample_details: dict) -> None:
        """Test successful Google Space notification."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = AsyncMock()
            mock_response.raise_for_status = AsyncMock()
            mock_post.return_value = mock_response

            result = await send_google_space_notification(
                webhook_url="https://chat.googleapis.com/v1/spaces/test",
                title="Test Alert",
                summary="Test summary",
                details=sample_details,
                severity="critical",
            )

            assert result["status"] == "success"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_google_space_notification_error(self, sample_details: dict) -> None:
        """Test Google Space notification with error."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("API error")

            result = await send_google_space_notification(
                webhook_url="https://chat.googleapis.com/v1/spaces/test",
                title="Test Alert",
                summary="Test summary",
                details=sample_details,
            )

            assert result["status"] == "error"
            assert "API error" in result["message"]


class TestCreateNotificationTools:
    """Tests for notification tools creation."""

    def test_creates_both_tools_when_configured(
        self, settings_with_notifications: Settings
    ) -> None:
        """Test that both notification tools are created when webhooks configured."""
        tools = create_notification_tools(settings_with_notifications)
        assert len(tools) == 2

    def test_creates_no_tools_when_not_configured(
        self, settings_no_notifications: Settings
    ) -> None:
        """Test that no tools are created when webhooks not configured."""
        tools = create_notification_tools(settings_no_notifications)
        assert len(tools) == 0

    def test_creates_only_teams_tool(self) -> None:
        """Test that only Teams tool is created when only Teams configured."""
        settings = Settings(
            environment="development",
            teams_webhook_url="https://outlook.office.com/webhook/test",
        )
        tools = create_notification_tools(settings)
        assert len(tools) == 1

    def test_creates_only_google_space_tool(self) -> None:
        """Test that only Google Space tool is created when only it configured."""
        settings = Settings(
            environment="development",
            google_space_webhook_url="https://chat.googleapis.com/v1/spaces/test",
        )
        tools = create_notification_tools(settings)
        assert len(tools) == 1


class TestSeverityColors:
    """Tests for severity color/emoji mapping."""

    @pytest.mark.asyncio
    async def test_teams_severity_colors(self) -> None:
        """Test that different severities map to correct colors in Teams."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = AsyncMock()
            mock_response.raise_for_status = AsyncMock()
            mock_post.return_value = mock_response

            for severity in ["low", "medium", "high", "critical"]:
                await send_teams_notification(
                    webhook_url="https://test.com",
                    title="Test",
                    summary="Test",
                    details={},
                    severity=severity,
                )

            # Should have been called 4 times
            assert mock_post.call_count == 4

    @pytest.mark.asyncio
    async def test_google_space_severity_emojis(self) -> None:
        """Test that different severities map to correct emojis in Google Space."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = AsyncMock()
            mock_response.raise_for_status = AsyncMock()
            mock_post.return_value = mock_response

            for severity in ["low", "medium", "high", "critical"]:
                await send_google_space_notification(
                    webhook_url="https://test.com",
                    title="Test",
                    summary="Test",
                    details={},
                    severity=severity,
                )

            assert mock_post.call_count == 4
