"""
Abstract Browser Adapter Base Interface.
Decouples core WebVeil agent & privacy logic from specific browser automation drivers.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
from webveil.core.models.schema import DOMNode


class BaseBrowserAdapter(ABC):
    """
    Abstract interface for browser automation.
    Implemented by PlaywrightAdapter for V0, and future ChromeExtensionAdapter / FirefoxExtensionAdapter.
    """

    @abstractmethod
    def start(self, headless: bool = True):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def navigate(self, url: str):
        pass

    @abstractmethod
    def get_current_url(self) -> str:
        pass

    @abstractmethod
    def get_page_title(self) -> str:
        pass

    @abstractmethod
    def extract_dom(self) -> Tuple[List[DOMNode], str]:
        pass

    @abstractmethod
    def capture_screenshot_b64(self) -> str:
        pass

    @abstractmethod
    def click_element(self, node_id: int) -> bool:
        pass

    @abstractmethod
    def type_text(self, node_id: int, text: str) -> bool:
        pass

    @abstractmethod
    def press_key(self, key: str) -> bool:
        pass

    @abstractmethod
    def scroll_page(self, direction: str = "down", amount: int = 300) -> bool:
        pass

    @abstractmethod
    def select_option(self, node_id: int, value: str) -> bool:
        pass

    @abstractmethod
    def click_coordinates(self, x: int, y: int) -> bool:
        pass
