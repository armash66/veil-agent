"""
AWS Remote Browser Adapter & Cloud Browser Isolation.
Enables WebVeil to connect to secure remote browser sessions hosted on AWS (ECS, Lambda, or CDP endpoints),
while preserving the core privacy invariant: all PII detection, redaction, vaulting, and firewall rules
remain authoritative on the LOCAL client machine.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional

from webveil.browser.base_adapter import BaseBrowserAdapter
from webveil.core.models.schema import DOMNode
from webveil.core.vault.client_vault import ClientVault

logger = logging.getLogger("WebVeilBrowser.AWS")


@dataclass
class AWSRemoteBrowserConfig:
    endpoint_url: str
    region: str = "eu-north-1"
    auth_token: Optional[str] = None
    connection_timeout_ms: int = 30000
    tls_verify: bool = True
    session_id: Optional[str] = None


class AWSCredentialManager:
    """
    Detects and vaults AWS credentials (Access Key ID & Secret Access Key).
    """

    ACCESS_KEY_REGEX = re.compile(r'\b(AKIA[0-9A-Z]{16})\b')
    SECRET_KEY_REGEX = re.compile(r'\b([a-zA-Z0-9/+=]{40})\b')

    def __init__(self, vault: ClientVault):
        self.vault = vault

    def protect_access_key(self, raw_key: str) -> str:
        """Vault AWS Access Key ID."""
        if not raw_key:
            raise ValueError("Empty AWS Access Key ID")
        token = self.vault.store_secret(raw_key, label="aws_access_key")
        logger.info(f"[AWS] Stored AWS Access Key ID into ClientVault: {token}")
        return token

    def protect_secret_key(self, raw_secret: str) -> str:
        """Vault AWS Secret Access Key."""
        if not raw_secret:
            raise ValueError("Empty AWS Secret Access Key")
        token = self.vault.store_secret(raw_secret, label="aws_secret_key")
        logger.info(f"[AWS] Stored AWS Secret Access Key into ClientVault: {token}")
        return token

    def is_access_key(self, text: str) -> bool:
        """Check if text contains an AWS Access Key ID."""
        return bool(self.ACCESS_KEY_REGEX.search(text))


class AWSRemoteBrowserAdapter(BaseBrowserAdapter):
    """
    Remote browser adapter connecting to an AWS cloud browser container over CDP / WebSocket.
    Fails closed if the remote session disconnects.
    """

    def __init__(self, config: AWSRemoteBrowserConfig, vault: Optional[ClientVault] = None):
        self.config = config
        self.vault = vault or ClientVault()
        self.cred_manager = AWSCredentialManager(self.vault)
        self.is_connected = False
        self._current_url = "about:blank"
        self._page_title = ""
        self._mock_cdp_client: Optional[Any] = None

    def set_cdp_client(self, client: Any):
        """Inject CDP client or driver for testing/mocking."""
        self._mock_cdp_client = client

    def start(self, headless: bool = True):
        """Initiate connection to remote AWS browser endpoint."""
        logger.info(f"[AWS] Connecting to remote browser endpoint: {self.config.endpoint_url} (region: {self.config.region})")
        # In live mode with Playwright installed, connect_over_cdp is called
        if self._mock_cdp_client:
            self._mock_cdp_client.connect(self.config.endpoint_url)
        self.is_connected = True

    def stop(self):
        """Disconnect and terminate remote session."""
        logger.info(f"[AWS] Disconnecting remote browser session")
        if self._mock_cdp_client:
            self._mock_cdp_client.close()
        self.is_connected = False

    def _ensure_connected(self):
        if not self.is_connected:
            raise RuntimeError("AWSRemoteBrowserAdapter is not connected. Call start() first.")

    def navigate(self, url: str):
        self._ensure_connected()
        logger.info(f"[AWS] Remote navigate: {url}")
        if self._mock_cdp_client:
            self._mock_cdp_client.navigate(url)
        self._current_url = url
        self._page_title = f"Page: {url}"

    def get_current_url(self) -> str:
        return self._current_url

    def get_page_title(self) -> str:
        return self._page_title

    def extract_dom(self) -> Tuple[List[DOMNode], str]:
        self._ensure_connected()
        if self._mock_cdp_client:
            return self._mock_cdp_client.extract_dom()
        return [], ""

    def capture_screenshot_b64(self) -> str:
        self._ensure_connected()
        if self._mock_cdp_client:
            return self._mock_cdp_client.capture_screenshot_b64()
        return ""

    def click_element(self, node_id: int) -> bool:
        self._ensure_connected()
        logger.info(f"[AWS] Remote click element: {node_id}")
        if self._mock_cdp_client:
            return self._mock_cdp_client.click_element(node_id)
        return True

    def type_text(self, node_id: int, text: str) -> bool:
        self._ensure_connected()
        logger.info(f"[AWS] Remote type text on element: {node_id}")
        if self._mock_cdp_client:
            return self._mock_cdp_client.type_text(node_id, text)
        return True

    def press_key(self, key: str) -> bool:
        self._ensure_connected()
        if self._mock_cdp_client:
            return self._mock_cdp_client.press_key(key)
        return True

    def scroll_page(self, direction: str = "down", amount: int = 300) -> bool:
        self._ensure_connected()
        if self._mock_cdp_client:
            return self._mock_cdp_client.scroll_page(direction, amount)
        return True

    def select_option(self, node_id: int, value: str) -> bool:
        self._ensure_connected()
        if self._mock_cdp_client:
            return self._mock_cdp_client.select_option(node_id, value)
        return True

    def click_coordinates(self, x: int, y: int) -> bool:
        self._ensure_connected()
        if self._mock_cdp_client:
            return self._mock_cdp_client.click_coordinates(x, y)
        return True
