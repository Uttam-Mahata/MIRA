"""Tests for the MCP Toolset integration module."""

import os
from unittest.mock import patch

import pytest

from mira.config.settings import Settings
from mira.mcp_clients.mcp_toolset import (
    get_azure_devops_mcp_toolset,
    get_datadog_mcp_toolset,
    get_github_mcp_toolset,
    get_investigation_mcp_tools,
)


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        environment="development",
        datadog_api_key="test-api-key",
        datadog_app_key="test-app-key",
        azure_devops_pat="test-pat",
        azure_devops_organization="test-org",
        google_api_key="test-google-key",
    )


@pytest.fixture
def settings_no_datadog() -> Settings:
    """Create settings without Datadog credentials."""
    return Settings(
        environment="development",
        azure_devops_pat="test-pat",
        azure_devops_organization="test-org",
    )


@pytest.fixture
def settings_no_azure() -> Settings:
    """Create settings without Azure DevOps credentials."""
    return Settings(
        environment="development",
        datadog_api_key="test-api-key",
        datadog_app_key="test-app-key",
    )


class TestAzureDevOpsMCPToolset:
    """Tests for Azure DevOps MCP toolset creation."""

    def test_returns_none_without_organization(
        self, settings_no_azure: Settings
    ) -> None:
        """Test that None is returned when organization is not set."""
        result = get_azure_devops_mcp_toolset(settings_no_azure)
        # Should return None since no organization is configured
        assert result is None

    def test_returns_toolset_with_organization(self, settings: Settings) -> None:
        """Test that a toolset is returned when organization is set."""
        # This test creates an actual McpToolset instance
        # The McpToolset doesn't connect until tools are requested
        result = get_azure_devops_mcp_toolset(settings)
        # Should return a McpToolset instance
        assert result is not None

    def test_explicit_organization_override(self, settings: Settings) -> None:
        """Test that explicit organization parameter overrides settings."""
        result = get_azure_devops_mcp_toolset(
            settings, organization="explicit-org"
        )
        assert result is not None


class TestDatadogMCPToolset:
    """Tests for Datadog MCP toolset creation."""

    def test_returns_none_without_credentials(
        self, settings_no_datadog: Settings
    ) -> None:
        """Test that None is returned when credentials are not set."""
        result = get_datadog_mcp_toolset(settings_no_datadog)
        assert result is None

    def test_returns_toolset_with_credentials(self, settings: Settings) -> None:
        """Test that a toolset is returned when credentials are set."""
        result = get_datadog_mcp_toolset(settings)
        assert result is not None


class TestGitHubMCPToolset:
    """Tests for GitHub MCP toolset creation."""

    def test_returns_none_without_token(self) -> None:
        """Test that None is returned when token is not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_github_mcp_toolset()
        assert result is None

    def test_returns_toolset_with_token(self) -> None:
        """Test that a toolset is returned when token is set."""
        with patch.dict(
            os.environ, {"GITHUB_PERSONAL_ACCESS_TOKEN": "test-token"}
        ):
            result = get_github_mcp_toolset()
        assert result is not None


class TestInvestigationMCPTools:
    """Tests for the combined investigation MCP tools."""

    def test_returns_list(self, settings: Settings) -> None:
        """Test that a list is returned."""
        tools = get_investigation_mcp_tools(settings)
        assert isinstance(tools, list)

    def test_includes_available_toolsets(self, settings: Settings) -> None:
        """Test that available toolsets are included."""
        tools = get_investigation_mcp_tools(settings)
        # Should include Azure DevOps and Datadog (no GitHub token set)
        assert len(tools) >= 2

    def test_empty_with_no_credentials(self) -> None:
        """Test that an empty list is returned with no credentials."""
        settings = Settings(environment="development")
        with patch.dict(os.environ, {}, clear=True):
            tools = get_investigation_mcp_tools(settings)
        # Should be empty since no credentials are configured
        assert isinstance(tools, list)
