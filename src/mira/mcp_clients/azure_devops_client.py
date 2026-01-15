"""
Azure DevOps MCP Client for retrieving commits and code changes.

This client wraps the Azure DevOps MCP server tools to provide a scoped interface
for investigating incidents. The client filters all requests to a specific repository.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Commit(BaseModel):
    """Represents a commit from Azure DevOps."""

    commit_id: str
    author: str
    author_email: str
    message: str
    timestamp: str
    changed_files: list[str] = []


class PullRequest(BaseModel):
    """Represents a pull request from Azure DevOps."""

    id: int
    title: str
    description: str
    author: str
    status: str
    created_date: str
    merged_date: str | None = None
    source_branch: str
    target_branch: str


class AzureDevOpsMCPClient:
    """Client for interacting with Azure DevOps via MCP.

    This client provides scoped access to Azure DevOps repositories,
    commits, and pull requests. It's designed to be used by Worker Agents
    during incident investigation.
    """

    def __init__(
        self,
        organization_url: str | None = None,
        organization: str | None = None,
        pat: str | None = None,
        project: str | None = None,
        repo_name: str | None = None,
    ) -> None:
        """Initialize the Azure DevOps MCP client.

        Args:
            organization_url: Azure DevOps organization URL.
            organization: Azure DevOps organization name.
            pat: Personal Access Token for authentication.
            project: Azure DevOps project name.
            repo_name: Repository name to scope queries to.
        """
        self.organization_url = organization_url
        self.organization = organization
        self.pat = pat
        self.project = project
        self.repo_name = repo_name

        logger.info(
            f"Initialized Azure DevOps MCP client for org: {organization or organization_url}"
            + (f", project: {project}" if project else "")
            + (f", repo: {repo_name}" if repo_name else "")
        )

    def with_repo(self, project: str, repo_name: str) -> "AzureDevOpsMCPClient":
        """Create a new client scoped to a specific repository.

        Args:
            project: The Azure DevOps project name.
            repo_name: The repository name.

        Returns:
            A new AzureDevOpsMCPClient instance scoped to the repository.
        """
        return AzureDevOpsMCPClient(
            organization_url=self.organization_url,
            organization=self.organization,
            pat=self.pat,
            project=project,
            repo_name=repo_name,
        )

    async def get_commits(
        self,
        branch: str = "main",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        file_path: str | None = None,
        limit: int = 50,
    ) -> list[Commit]:
        """Retrieve commits from the repository.

        Args:
            branch: Branch to get commits from.
            start_time: Start of the time range. Defaults to 2 hours ago.
            end_time: End of the time range. Defaults to now.
            file_path: Filter commits to those affecting a specific file.
            limit: Maximum number of commits to return.

        Returns:
            List of commits.
        """
        if not self.repo_name:
            raise ValueError("Repository name must be set to get commits")

        if not start_time:
            start_time = datetime.now(UTC) - timedelta(hours=2)
        if not end_time:
            end_time = datetime.now(UTC)

        logger.info(
            f"Fetching commits: repo={self.repo_name}, branch={branch}, "
            f"file={file_path}, from={start_time.isoformat()}"
        )

        # Placeholder implementation
        # In a real implementation, this would call the Azure DevOps MCP server
        return [
            Commit(
                commit_id="placeholder",
                author="Placeholder",
                author_email="placeholder@example.com",
                message=f"[Placeholder] Commits for {self.repo_name}",
                timestamp=datetime.now(UTC).isoformat(),
                changed_files=[],
            )
        ]

    async def get_commits_for_file(
        self,
        file_path: str,
        lookback_hours: int = 2,
        limit: int = 10,
    ) -> list[Commit]:
        """Get commits that modified a specific file.

        This is useful for correlating error stack traces with recent code changes.

        Args:
            file_path: Path to the file to check.
            lookback_hours: How many hours to look back.
            limit: Maximum number of commits to return.

        Returns:
            List of commits that modified the file.
        """
        start_time = datetime.now(UTC) - timedelta(hours=lookback_hours)
        return await self.get_commits(
            file_path=file_path,
            start_time=start_time,
            limit=limit,
        )

    async def get_pull_requests(
        self,
        status: str = "completed",
        start_time: datetime | None = None,
        limit: int = 20,
    ) -> list[PullRequest]:
        """Get pull requests from the repository.

        Args:
            status: Filter by PR status (active, completed, abandoned, all).
            start_time: Get PRs merged after this time.
            limit: Maximum number of PRs to return.

        Returns:
            List of pull requests.
        """
        if not self.repo_name:
            raise ValueError("Repository name must be set to get pull requests")

        logger.info(
            f"Fetching pull requests: repo={self.repo_name}, status={status}"
        )

        # Placeholder implementation
        return []

    async def get_recent_changes(
        self,
        lookback_hours: int = 2,
    ) -> dict[str, Any]:
        """Get a summary of recent changes in the repository.

        This is useful for quick incident correlation.

        Args:
            lookback_hours: How many hours to look back.

        Returns:
            Summary of recent changes including commits and merged PRs.
        """
        start_time = datetime.now(UTC) - timedelta(hours=lookback_hours)

        commits = await self.get_commits(start_time=start_time)
        pull_requests = await self.get_pull_requests(start_time=start_time)

        return {
            "repository": self.repo_name,
            "project": self.project,
            "lookback_hours": lookback_hours,
            "commit_count": len(commits),
            "commits": [c.model_dump() for c in commits],
            "pr_count": len(pull_requests),
            "pull_requests": [pr.model_dump() for pr in pull_requests],
        }

    async def get_commit_details(self, commit_id: str) -> dict[str, Any]:
        """Get detailed information about a specific commit.

        Args:
            commit_id: The commit SHA.

        Returns:
            Detailed commit information including diff.
        """
        if not self.repo_name:
            raise ValueError("Repository name must be set to get commit details")

        logger.info(f"Fetching commit details: {commit_id}")

        # Placeholder implementation
        return {
            "commit_id": commit_id,
            "repository": self.repo_name,
            "changes": [],
        }
