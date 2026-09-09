"""
WebVeil GitHub Integration Package.
"""

from webveil.integrations.github.actions import (
    GitHubIssueSpec,
    GitHubPRSpec,
    GitHubActionPlanBuilder,
)
from webveil.integrations.github.client import (
    GitHubCredentialManager,
    GitHubWorkflowNavigator,
)

__all__ = [
    "GitHubIssueSpec",
    "GitHubPRSpec",
    "GitHubActionPlanBuilder",
    "GitHubCredentialManager",
    "GitHubWorkflowNavigator",
]
