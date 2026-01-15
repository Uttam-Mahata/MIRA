"""Tests for the Worker Agent and tools."""


import pytest

from mira.config.settings import Settings
from mira.registry.models import InvestigationContext
from mira.worker.agent import InvestigatorAgent, create_investigator_agent


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
def investigation_context() -> InvestigationContext:
    """Create a test investigation context."""
    return InvestigationContext(
        service_name="test-service",
        repo_name="test-repo",
        project="TestProject",
        alert_timestamp="2024-01-15T10:00:00Z",
        environment="prod",
        alert_type="error_rate",
        alert_title="High Error Rate Alert",
        owner_team="team-test",
    )


class TestInvestigatorAgent:
    """Tests for the InvestigatorAgent class."""

    def test_create_agent(
        self, settings: Settings, investigation_context: InvestigationContext
    ) -> None:
        """Test creating an investigator agent."""
        agent = create_investigator_agent(investigation_context, settings)

        assert isinstance(agent, InvestigatorAgent)
        assert agent.context == investigation_context
        assert agent.settings == settings

    def test_agent_clients_initialized(
        self, settings: Settings, investigation_context: InvestigationContext
    ) -> None:
        """Test that MCP clients are properly initialized."""
        agent = create_investigator_agent(investigation_context, settings)

        # Check Datadog client
        assert agent.datadog_client is not None
        assert agent.datadog_client.service_name == "test-service"

        # Check Azure DevOps client
        assert agent.azure_client is not None
        assert agent.azure_client.repo_name == "test-repo"
        assert agent.azure_client.project == "TestProject"

    def test_system_prompt_contains_context(
        self, settings: Settings, investigation_context: InvestigationContext
    ) -> None:
        """Test that the system prompt includes context information."""
        agent = create_investigator_agent(investigation_context, settings)
        prompt = agent._build_system_prompt()

        assert "test-service" in prompt
        assert "test-repo" in prompt
        assert "TestProject" in prompt
        assert "error_rate" in prompt
        assert "High Error Rate Alert" in prompt
        assert "prod" in prompt

    @pytest.mark.asyncio
    async def test_investigate_returns_result(
        self, settings: Settings, investigation_context: InvestigationContext
    ) -> None:
        """Test that investigate returns a result structure."""
        agent = create_investigator_agent(investigation_context, settings)
        result = await agent.investigate()

        assert "status" in result
        assert "service" in result
        assert result["service"] == "test-service"
        assert "rca" in result


class TestInvestigationContext:
    """Tests for the InvestigationContext model."""

    def test_minimal_context(self) -> None:
        """Test creating context with minimal required fields."""
        context = InvestigationContext(
            service_name="my-service",
            repo_name="my-repo",
            project="MyProject",
            alert_timestamp="2024-01-15T10:00:00Z",
            environment="prod",
            alert_type="error_rate",
        )

        assert context.service_name == "my-service"
        assert context.repo_name == "my-repo"
        assert context.lookback_hours == 2  # default

    def test_full_context(self) -> None:
        """Test creating context with all fields."""
        context = InvestigationContext(
            service_name="payment-service",
            repo_name="payment-api",
            project="Payments",
            alert_timestamp="2024-01-15T10:00:00Z",
            environment="prod",
            alert_type="latency",
            alert_title="High Latency",
            owner_team="team-payments",
            alert_channel="#payments-alerts",
            lookback_hours=4,
        )

        assert context.service_name == "payment-service"
        assert context.lookback_hours == 4
        assert context.alert_channel == "#payments-alerts"
