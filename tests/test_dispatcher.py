"""Tests for the FastAPI Dispatcher routes."""

import pytest
from fastapi.testclient import TestClient

from mira.config.settings import Settings
from mira.dispatcher.main import create_app
from mira.registry.models import ServiceInfo
from mira.registry.service_registry import ServiceRegistry


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    app = create_app()

    # Manually set up the state for testing (normally done in lifespan)
    app.state.settings = Settings()
    app.state.service_registry = ServiceRegistry()

    return TestClient(app)


@pytest.fixture
def client_with_services() -> TestClient:
    """Create a test client with pre-registered services."""
    app = create_app()

    # Set up settings
    app.state.settings = Settings()

    # Manually set up the registry for testing
    registry = ServiceRegistry()
    registry.register_service(
        "test-service",
        ServiceInfo(
            repo_name="test-repo",
            project="TestProject",
            owner_team="team-test",
        ),
    )
    registry.register_service(
        "payment-service",
        ServiceInfo(
            repo_name="payment-api",
            project="Payments",
            owner_team="team-fintech",
        ),
    )

    app.state.service_registry = registry

    return TestClient(app)


class TestHealthEndpoints:
    """Tests for health and root endpoints."""

    def test_root_endpoint(self, client: TestClient) -> None:
        """Test the root endpoint returns service info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "MIRA" in data["service"]
        assert data["version"] == "0.1.0"

    def test_health_endpoint(self, client: TestClient) -> None:
        """Test the health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data


class TestServiceEndpoints:
    """Tests for service management endpoints."""

    def test_list_services_empty(self, client: TestClient) -> None:
        """Test listing services when registry is empty."""
        response = client.get("/services")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["services"] == []

    def test_list_services_with_data(self, client_with_services: TestClient) -> None:
        """Test listing services with registered services."""
        response = client_with_services.get("/services")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert "test-service" in data["services"]
        assert "payment-service" in data["services"]

    def test_register_service(self, client: TestClient) -> None:
        """Test registering a new service."""
        service_data = {
            "repo_name": "new-repo",
            "project": "NewProject",
            "owner_team": "team-new",
        }

        response = client.post("/services/new-service", json=service_data)

        assert response.status_code == 200
        assert "registered successfully" in response.json()["message"]

        # Verify it was registered
        response = client.get("/services")
        assert "new-service" in response.json()["services"]

    def test_remove_service(self, client_with_services: TestClient) -> None:
        """Test removing a service."""
        response = client_with_services.delete("/services/test-service")

        assert response.status_code == 200
        assert "removed successfully" in response.json()["message"]

        # Verify it was removed
        response = client_with_services.get("/services")
        assert "test-service" not in response.json()["services"]

    def test_remove_nonexistent_service(self, client: TestClient) -> None:
        """Test removing a nonexistent service."""
        response = client.delete("/services/nonexistent")

        assert response.status_code == 404


class TestWebhookEndpoint:
    """Tests for the Datadog webhook endpoint."""

    def test_webhook_service_not_found(self, client: TestClient) -> None:
        """Test webhook with unknown service."""
        payload = {
            "service": "unknown-service",
            "timestamp": "2024-01-15T10:00:00Z",
            "environment": "prod",
            "alert_type": "error_rate",
        }

        response = client.post("/webhook/datadog", json=payload)

        assert response.status_code == 404
        assert "not found in registry" in response.json()["detail"]

    def test_webhook_success(self, client_with_services: TestClient) -> None:
        """Test successful webhook processing."""
        payload = {
            "service": "test-service",
            "timestamp": "2024-01-15T10:00:00Z",
            "environment": "prod",
            "alert_type": "error_rate",
            "alert_title": "High Error Rate",
        }

        response = client_with_services.post("/webhook/datadog", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["service"] == "test-service"
        assert "investigation_id" in data

    def test_webhook_invalid_payload(self, client: TestClient) -> None:
        """Test webhook with invalid payload."""
        response = client.post(
            "/webhook/datadog",
            json={"invalid": "payload"},
        )

        assert response.status_code == 400


class TestInvestigateEndpoint:
    """Tests for the manual investigation endpoint."""

    def test_investigate_service_not_found(self, client: TestClient) -> None:
        """Test investigation with unknown service."""
        payload = {
            "service": "unknown-service",
            "timestamp": "2024-01-15T10:00:00Z",
        }

        response = client.post("/investigate", json=payload)

        assert response.status_code == 404

    def test_investigate_success(self, client_with_services: TestClient) -> None:
        """Test successful investigation request."""
        payload = {
            "service": "test-service",
            "timestamp": "2024-01-15T10:00:00Z",
            "environment": "prod",
            "alert_type": "error_rate",
            "alert_title": "Test Alert",
        }

        response = client_with_services.post("/investigate", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "test-service"
        assert data["alert_type"] == "error_rate"
        assert "rca" in data
