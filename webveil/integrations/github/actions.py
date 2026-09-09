"""
GitHub Browser Agent Actions & Navigation Plans.
Defines high-level validated navigation flows for GitHub workflows (issues, PRs, actions, search).
"""

from dataclasses import dataclass
from typing import Optional, List
from webveil.core.models.schema import BrowserAction, ActionType


@dataclass
class GitHubIssueSpec:
    repo: str
    title: str
    body: str
    labels: Optional[List[str]] = None


@dataclass
class GitHubPRSpec:
    repo: str
    branch: str
    base: str = "main"
    title: str = ""
    body: str = ""


class GitHubActionPlanBuilder:
    """
    Builds structured browser action sequences for GitHub automation,
    ensuring all secrets (e.g. PAT tokens, private keys) are bound to vault tokens.
    """

    GITHUB_BASE_URL = "https://github.com"

    @classmethod
    def plan_navigate_repo(cls, repo: str) -> BrowserAction:
        clean_repo = repo.strip("/")
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"{cls.GITHUB_BASE_URL}/{clean_repo}"
        )

    @classmethod
    def plan_navigate_issues(cls, repo: str) -> BrowserAction:
        clean_repo = repo.strip("/")
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"{cls.GITHUB_BASE_URL}/{clean_repo}/issues"
        )

    @classmethod
    def plan_navigate_new_issue(cls, repo: str) -> BrowserAction:
        clean_repo = repo.strip("/")
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"{cls.GITHUB_BASE_URL}/{clean_repo}/issues/new"
        )

    @classmethod
    def plan_navigate_pull_request(cls, repo: str, pr_number: int) -> BrowserAction:
        clean_repo = repo.strip("/")
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"{cls.GITHUB_BASE_URL}/{clean_repo}/pull/{pr_number}"
        )

    @classmethod
    def plan_navigate_actions(cls, repo: str) -> BrowserAction:
        clean_repo = repo.strip("/")
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"{cls.GITHUB_BASE_URL}/{clean_repo}/actions"
        )
