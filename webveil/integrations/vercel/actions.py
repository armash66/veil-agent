"""
Vercel Browser Agent Actions & Navigation Plans.
Defines high-level validated navigation flows for Vercel workflows (deployments, env vars, domains).
"""

from dataclasses import dataclass
from typing import Optional, List
from webveil.core.models.schema import BrowserAction, ActionType


@dataclass
class VercelEnvVarSpec:
    key: str
    value: str
    target_environments: List[str]  # e.g. ["production", "preview", "development"]


@dataclass
class VercelDeploymentSpec:
    project: str
    team: Optional[str] = None
    deployment_id: Optional[str] = None


class VercelActionPlanBuilder:
    """
    Builds structured browser action sequences for Vercel automation,
    ensuring all secrets (API tokens, environment variable values) are bound to vault tokens.
    """

    VERCEL_BASE_URL = "https://vercel.com"

    @classmethod
    def plan_navigate_dashboard(cls) -> BrowserAction:
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"{cls.VERCEL_BASE_URL}/dashboard"
        )

    @classmethod
    def plan_navigate_project(cls, project: str, team: Optional[str] = None) -> BrowserAction:
        path = f"{team}/{project}" if team else project
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"{cls.VERCEL_BASE_URL}/{path}"
        )

    @classmethod
    def plan_navigate_deployments(cls, project: str, team: Optional[str] = None) -> BrowserAction:
        path = f"{team}/{project}" if team else project
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"{cls.VERCEL_BASE_URL}/{path}/deployments"
        )

    @classmethod
    def plan_navigate_env_vars(cls, project: str, team: Optional[str] = None) -> BrowserAction:
        path = f"{team}/{project}" if team else project
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"{cls.VERCEL_BASE_URL}/{path}/settings/environment-variables"
        )
