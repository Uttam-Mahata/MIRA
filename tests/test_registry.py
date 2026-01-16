"""Tests for the Service Registry."""

import json
import tempfile
from pathlib import Path

from mira.registry.models import ServiceInfo
from mira.registry.service_registry import ServiceRegistry


class TestServiceRegistry:
    """Tests for ServiceRegistry class."""

    def test_empty_registry(self) -> None:
        """Test creating an empty registry."""
        registry = ServiceRegistry()

        assert len(registry) == 0
        assert registry.list_services() == []
        assert registry.get_service("nonexistent") is None

    def test_register_service(self) -> None:
        """Test registering a service."""
        registry = ServiceRegistry()

        service_info = ServiceInfo(
            repo_name="test-repo",
            project="TestProject",
            adk_profile="backend_investigator",
            owner_team="team-test",
        )

        registry.register_service("test-service", service_info)

        assert len(registry) == 1
        assert "test-service" in registry
        assert registry.get_service("test-service") == service_info

    def test_remove_service(self) -> None:
        """Test removing a service."""
        registry = ServiceRegistry()

        service_info = ServiceInfo(repo_name="test-repo")
        registry.register_service("test-service", service_info)

        assert registry.remove_service("test-service") is True
        assert len(registry) == 0
        assert registry.remove_service("nonexistent") is False

    def test_list_services(self) -> None:
        """Test listing all services."""
        registry = ServiceRegistry()

        registry.register_service("service-a", ServiceInfo(repo_name="repo-a"))
        registry.register_service("service-b", ServiceInfo(repo_name="repo-b"))
        registry.register_service("service-c", ServiceInfo(repo_name="repo-c"))

        services = registry.list_services()
        assert len(services) == 3
        assert set(services) == {"service-a", "service-b", "service-c"}

    def test_load_from_file(self) -> None:
        """Test loading registry from a JSON file."""
        data = {
            "service-payment": {
                "repo_name": "payment-api",
                "project": "Payments",
                "owner_team": "team-fintech",
            },
            "service-auth": {
                "repo_name": "auth-service",
                "project": "Platform",
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            registry = ServiceRegistry(temp_path)

            assert len(registry) == 2
            assert "service-payment" in registry
            assert "service-auth" in registry

            payment = registry.get_service("service-payment")
            assert payment is not None
            assert payment.repo_name == "payment-api"
            assert payment.project == "Payments"
            assert payment.owner_team == "team-fintech"
        finally:
            Path(temp_path).unlink()

    def test_load_nonexistent_file(self) -> None:
        """Test loading from a nonexistent file."""
        registry = ServiceRegistry("/nonexistent/path/registry.json")

        assert len(registry) == 0

    def test_save_to_file(self) -> None:
        """Test saving registry to a JSON file."""
        registry = ServiceRegistry()

        registry.register_service(
            "test-service",
            ServiceInfo(
                repo_name="test-repo",
                project="TestProject",
                owner_team="team-test",
            ),
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            registry.save_to_file(temp_path)

            with open(temp_path) as f:
                data = json.load(f)

            assert "test-service" in data
            assert data["test-service"]["repo_name"] == "test-repo"
            assert data["test-service"]["project"] == "TestProject"
        finally:
            Path(temp_path).unlink()


class TestServiceInfo:
    """Tests for ServiceInfo model."""

    def test_minimal_service_info(self) -> None:
        """Test creating ServiceInfo with minimal fields."""
        info = ServiceInfo(repo_name="my-repo")

        assert info.repo_name == "my-repo"
        assert info.project == ""
        assert info.adk_profile == "backend_investigator"
        assert info.owner_team == ""

    def test_full_service_info(self) -> None:
        """Test creating ServiceInfo with all fields."""
        info = ServiceInfo(
            repo_name="payment-api",
            project="Payments",
            adk_profile="custom_profile",
            owner_team="team-fintech",
            description="Payment service",
            alert_channel="#payments",
        )

        assert info.repo_name == "payment-api"
        assert info.project == "Payments"
        assert info.adk_profile == "custom_profile"
        assert info.owner_team == "team-fintech"
        assert info.description == "Payment service"
        assert info.alert_channel == "#payments"
