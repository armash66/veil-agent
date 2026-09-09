"""
On-Device Client Vault.
Stores sensitive mapping from tokens to raw secrets in ephemeral client memory only.
Enforces strict restoration verification rules using an out-of-DOM node identity registry.
"""

import hashlib
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

    Node identity is tracked via an out-of-DOM fingerprint registry:
    a Python-side dict mapping token → fingerprint_hash, computed from
    immutable node properties at extraction time. The page's own JS
    cannot read or write these fingerprints — they exist only in this
    process's memory.
    """

    def __init__(self, current_origin: str = "http://localhost"):
        self.current_origin = current_origin
        self._entries: Dict[str, VaultEntry] = {}
        # Out-of-DOM identity registry: token → fingerprint hash
        self._node_fingerprints: Dict[str, str] = {}

    def set_origin(self, origin: str):
        self.current_origin = origin

    def clear(self):
        self._entries.clear()
        self._node_fingerprints.clear()

    @staticmethod
    def _compute_node_fingerprint(node: DOMNode, origin: str) -> str:
        """
        Compute a stable fingerprint from immutable node properties.
        This fingerprint is NEVER stored in the DOM — it lives only in Python memory.
        Properties used: origin, tag_name, element_type, element_id, name, node_id.
        """
        parts = [
            origin,
            str(node.node_id),
            node.tag_name or "",
            node.element_type or "",
            node.element_id or "",
            node.name or "",
        ]
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

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
            element_name=node.name if node else None,
            attributes=dict(node.attributes) if node and hasattr(node, "attributes") else {}
        )
        self._entries[match.placeholder] = entry

        # Register out-of-DOM fingerprint
        if node is not None:
            fingerprint = self._compute_node_fingerprint(node, origin)
            self._node_fingerprints[match.placeholder] = fingerprint

        logger.info(f"[Vault] Stored token {match.placeholder} for category {match.category.name} on origin {origin}")
        return match.placeholder

    def restore(self, token: str, target_node: DOMNode, current_origin: str) -> str:
        """
        Restores raw secret for local Playwright execution after strict verification.
        Uses out-of-DOM fingerprint registry as the primary identity check.
        """
        if token not in self._entries:
            logger.error(f"[Vault REJECT] Token {token} not found in vault")
            raise VaultRestorationError(f"Token {token} not found in client vault")

        entry = self._entries[token]

        # 1. Origin verification (stored at creation time, not from live page)
        if entry.origin != current_origin:
            logger.error(f"[Vault REJECT] Origin mismatch for {token}: expected {entry.origin}, got {current_origin}")
            raise VaultRestorationError(f"Origin mismatch: entry origin={entry.origin}, target={current_origin}")

        # 2. Out-of-DOM Fingerprint Identity Verification (PRIMARY CHECK)
        if token in self._node_fingerprints:
            expected_fp = self._node_fingerprints[token]
            actual_fp = self._compute_node_fingerprint(target_node, current_origin)
            if expected_fp != actual_fp:
                logger.error(
                    f"[Vault REJECT] Node fingerprint mismatch for {token}: "
                    f"expected {expected_fp[:16]}..., got {actual_fp[:16]}..."
                )
                raise VaultRestorationError(
                    f"Node identity mismatch: out-of-DOM fingerprint does not match. "
                    f"Target node {target_node.node_id} is not the original extraction node."
                )
        elif entry.source_node_id is not None:
            # Fallback for entries without fingerprint (backward compat)
            if target_node.node_id != entry.source_node_id:
                id_match = entry.element_id and target_node.element_id == entry.element_id
                name_match = entry.element_name and target_node.name == entry.element_name
                if not (id_match or name_match):
                    logger.error(f"[Vault REJECT] Node identity mismatch for {token}")
                    raise VaultRestorationError(f"Target node {target_node.node_id} does not match source vault entry")

        # 3. Element Type Verification
        if entry.category == PIICategory.PASSWORD and target_node.element_type != "password":
            logger.error(f"[Vault REJECT] Security violation: Attempted to inject password token into non-password input type '{target_node.element_type}'")
            raise VaultRestorationError("Password secrets can only be restored into input type='password'")

        # 4. Strict Element Visibility & Exfiltration Prevention Verification
        if not target_node.is_visible:
            logger.error(f"[Vault REJECT] Element node {target_node.node_id} is not visible")
            raise VaultRestorationError("Cannot restore secret into hidden DOM node")

        # Verify zero-size or hidden opacity attribute exfiltration tricks
        opacity = target_node.attributes.get("opacity", "1")
        if opacity in ("0", "0.0", "none"):
            logger.error(f"[Vault REJECT] Element node {target_node.node_id} has zero opacity")
            raise VaultRestorationError("Cannot restore secret into transparent or hidden DOM node")

        if target_node.bounding_box:
            w = target_node.bounding_box.get("width", 0)
            h = target_node.bounding_box.get("height", 0)
            if w <= 1 or h <= 1:
                logger.error(f"[Vault REJECT] Element node {target_node.node_id} has suspicious tiny dimensions ({w}x{h})")
                raise VaultRestorationError("Cannot restore secret into 1px or zero-size exfiltration DOM node")

        logger.info(f"[Vault RESTORE SUCCESS] Verified token {token} for node {target_node.node_id}")
        return entry.secret

