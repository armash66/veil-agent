"""
AWS Console Action Plans and Navigation Routes.
Defines structured URL patterns for navigating AWS services (EC2, S3, IAM, CloudWatch, Lambda).
"""

from typing import Optional
from webveil.core.models.schema import BrowserAction, ActionType


class AWSActionPlanBuilder:
    """
    Builds structured navigation actions for AWS Console services.
    """

    AWS_CONSOLE_BASE = "https://console.aws.amazon.com"

    @classmethod
    def plan_navigate_console(cls, region: str = "eu-north-1") -> BrowserAction:
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"https://{region}.console.aws.amazon.com/console/home?region={region}"
        )

    @classmethod
    def plan_navigate_ec2(cls, region: str = "eu-north-1") -> BrowserAction:
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"https://{region}.console.aws.amazon.com/ec2/home?region={region}#Instances:"
        )

    @classmethod
    def plan_navigate_s3(cls) -> BrowserAction:
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"{cls.AWS_CONSOLE_BASE}/s3/buckets"
        )

    @classmethod
    def plan_navigate_lambda(cls, region: str = "eu-north-1") -> BrowserAction:
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"https://{region}.console.aws.amazon.com/lambda/home?region={region}#/functions"
        )

    @classmethod
    def plan_navigate_iam(cls) -> BrowserAction:
        return BrowserAction(
            action=ActionType.NAVIGATE,
            url=f"{cls.AWS_CONSOLE_BASE}/iam/home#/users"
        )
