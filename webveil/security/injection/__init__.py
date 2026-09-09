"""
WebVeil Prompt Injection Defense Subsystem.
Provides detection, classification, taint provenance tracking,
and firewall blocking against indirect prompt injection attacks in web content.
"""

from webveil.security.injection.classifier import PromptInjectionClassifier, InjectionRiskAssessment
from webveil.security.injection.taint_tracker import TaintTracker
from webveil.security.injection.firewall_rule import PromptInjectionFirewallRule

__all__ = [
    "PromptInjectionClassifier",
    "InjectionRiskAssessment",
    "TaintTracker",
    "PromptInjectionFirewallRule",
]
