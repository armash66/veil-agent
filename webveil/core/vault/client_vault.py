"""
On-Device Client Vault.
Stores sensitive mapping from tokens to raw secrets in ephemeral client memory only.
Enforces strict restoration verification rules.
"""

import logging
from typing import Dict, Optional
from webveil.core.models.schema import VaultEntry, DOMNode, PIIMatch, PIICategory

logger = logging.getLogger("WebVeilVault")


class VaultRestorationError(Exception):
    """Raised when vault restoration verification fails."""
    pass


class ClientVault:
    """
    Ephemeral memory store for PII tokens.
    Secrets NEVER escape client memory or appear in logs.
    """

    def __init__(self, current_origin: str = "http://localhost"):
        self.current_origin = current_origin
        self._entries: Dict[str, VaultEntry] = {}

    def set_origin(self, origin: str):
        self.current_origin = origin

    def clear(self):
        self._entries.clear()

    def store_match(self, match: PIIMatch, origin: str, node: Optional[DOMNode] = None) -> str:
        """
        Store a detected PII match in the vault and return its token placeholder.
        """
        entry = VaultEntry(
            token=match.placeholder,
            secret=match.raw_value,
            origin=origin,
            category=match.category,
            source_node_id=match.source_node_id,
            element_type=node.element_type if node else "text",
            element_id=node.element_id if node else None,
            element_name=node.name if node else None
        )
        self._entries[match.placeholder] = entry
        logger.info(f"[Vault] Stored token {match.placeholder} for category {match.category.name} on origin {origin}")
        return match.placeholder

    def restore(self, token: str, target_node: DOMNode, current_origin: str) -> str:
        """
        Restores raw secret for local Playwright execution after strict verification.
        """
        if token not in self._entries:
            logger.error(f"[Vault REJECT] Token {token} not found in vault")
            raise VaultRestorationError(f"Token {token} not found in client vault")

        entry = self._entries[token]

        # 1. Origin verification
        if entry.origin != current_origin:
            logger.error(f"[Vault REJECT] Origin mismatch for {token}: expected {entry.origin}, got {current_origin}")
            raise VaultRestorationError(f"Origin mismatch: entry origin={entry.origin}, target={current_origin}")

        # 2. Node Freshness / Identity Verification
        if entry.source_node_id is not None and target_node.node_id != entry.source_node_id:
            # Check if fallback element_id or name matches
            id_match = entry.element_id and target_node.element_id == entry.element_id
            name_match = entry.element_name and target_node.name == entry.element_name
            if not (id_match or name_match):
                logger.error(f"[Vault REJECT] Node identity mismatch for {token}: source node={entry.source_node_id}, target node={target_node.node_id}")
                raise VaultRestorationError(f"Target node {target_node.node_id} does not match source vault entry")

        # 3. Element Type Verification
        if entry.category == PIICategory.PASSWORD and target_node.element_type != "password":
            logger.error(f"[Vault REJECT] Security violation: Attempted to inject password token into non-password input type '{target_node.element_type}'")
            raise VaultRestorationError("Password secrets can only be restored into input type='password'")

        # 4. Element Visibility Verification
        if not target_node.is_visible:
            logger.error(f"[Vault REJECT] Element node {target_node.node_id} is not visible")
            raise VaultRestorationError("Cannot restore secret into hidden DOM node")

        logger.info(f"[Vault RESTORE SUCCESS] Verified token {token} for node {target_node.node_id}")
        return entry.secret
