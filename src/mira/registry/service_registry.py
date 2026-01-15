"""
Service Registry implementation.

The Service Registry is the "map" between observability (Datadog service names)
and source control (Azure DevOps repositories). It can be backed by:
- A JSON file (default, suitable for development)
- Redis (for production with frequent updates)
- Firestore (for cloud-native deployments)
"""

import json
import logging
from pathlib import Path

from mira.registry.models import ServiceInfo

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """Registry that maps service names to their repository and team information.

    This class provides a lookup mechanism to find the repository associated
    with a service name, which is essential for the incident investigation workflow.

    Example registry data:
    {
        "service-payment-v1": {
            "repo_name": "payment-api-core",
            "project": "Payments",
            "adk_profile": "backend_investigator",
            "owner_team": "team-fintech"
        }
    }
    """

    def __init__(self, registry_path: str | None = None) -> None:
        """Initialize the Service Registry.

        Args:
            registry_path: Path to the JSON file containing the registry.
                          If None, uses an empty registry.
        """
        self._registry: dict[str, ServiceInfo] = {}
        self._registry_path = registry_path

        if registry_path:
            self._load_from_file(registry_path)

    def _load_from_file(self, path: str) -> None:
        """Load registry data from a JSON file.

        Args:
            path: Path to the JSON file.
        """
        file_path = Path(path)
        if not file_path.exists():
            logger.warning(f"Service registry file not found: {path}")
            return

        try:
            with open(file_path) as f:
                data = json.load(f)

            for service_name, service_data in data.items():
                self._registry[service_name] = ServiceInfo(**service_data)

            logger.info(f"Loaded {len(self._registry)} services from registry")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse service registry JSON: {e}")
        except Exception as e:
            logger.error(f"Failed to load service registry: {e}")

    def get_service(self, service_name: str) -> ServiceInfo | None:
        """Get service information by name.

        Args:
            service_name: The name of the service (as it appears in Datadog).

        Returns:
            ServiceInfo if found, None otherwise.
        """
        return self._registry.get(service_name)

    def register_service(self, service_name: str, service_info: ServiceInfo) -> None:
        """Register a new service or update an existing one.

        Args:
            service_name: The name of the service.
            service_info: The service information.
        """
        self._registry[service_name] = service_info
        logger.info(f"Registered service: {service_name}")

    def remove_service(self, service_name: str) -> bool:
        """Remove a service from the registry.

        Args:
            service_name: The name of the service to remove.

        Returns:
            True if the service was removed, False if it wasn't found.
        """
        if service_name in self._registry:
            del self._registry[service_name]
            logger.info(f"Removed service: {service_name}")
            return True
        return False

    def list_services(self) -> list[str]:
        """List all registered service names.

        Returns:
            List of service names.
        """
        return list(self._registry.keys())

    def save_to_file(self, path: str | None = None) -> None:
        """Save the current registry to a JSON file.

        Args:
            path: Path to save to. If None, uses the original path.
        """
        save_path = path or self._registry_path
        if not save_path:
            raise ValueError("No path specified for saving registry")

        file_path = Path(save_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            service_name: service_info.model_dump()
            for service_name, service_info in self._registry.items()
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved registry to {save_path}")

    def __len__(self) -> int:
        """Return the number of registered services."""
        return len(self._registry)

    def __contains__(self, service_name: str) -> bool:
        """Check if a service is registered."""
        return service_name in self._registry
