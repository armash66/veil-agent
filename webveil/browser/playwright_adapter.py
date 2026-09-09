"""
Playwright Browser Adapter for WebVeil V1.
Provides local browser control via Playwright sync Chromium API.
V1: Added wait_for_stable, get_accessibility_tree, select_option, get_page_text.
"""

import base64
import logging
import time
from typing import List, Tuple, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page
from webveil.browser.base_adapter import BaseBrowserAdapter
from webveil.core.models.schema import DOMNode

logger = logging.getLogger("WebVeilPlaywright")


class PlaywrightAdapter(BaseBrowserAdapter):
    """
    Playwright driver implementation of BaseBrowserAdapter.
    Disables tracing and video recording by default to prevent secret leaks.
    """

    def __init__(self, viewport_size: Dict[str, int] = None):
        self.viewport_size = viewport_size or {"width": 1280, "height": 800}
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._node_map: Dict[int, Any] = {}  # node_id -> Playwright ElementHandle / Selector
        from webveil.browser.pointer import RealisticPointer
        self.pointer = RealisticPointer()
        self.realistic_simulation = False

    def start(self, headless: bool = True):
        logger.info("[Playwright] Starting browser engine...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        # Explicitly disable video/tracing record to prevent local secret exfiltration
        self.context = self.browser.new_context(
            viewport=self.viewport_size,
            record_video_dir=None,
            device_scale_factor=1.0
        )
        self.page = self.context.new_page()

    def stop(self):
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("[Playwright] Browser engine stopped.")

    def navigate(self, url: str):
        if not self.page:
            raise RuntimeError("Browser not started")
        logger.info(f"[Playwright] Navigating to {url}")
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            self.wait_for_stable()
        except Exception as e:
            logger.warning(f"[Playwright] Navigation warning: {e}")

    def wait_for_stable(self, timeout_ms: int = 3000):
        """Wait for page to stabilize after navigation or action."""
        if not self.page:
            return
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass  # Timeout is acceptable — some pages never reach networkidle
        # Small additional wait for JS rendering
        time.sleep(0.3)

    def get_current_url(self) -> str:
        return self.page.url if self.page else ""

    def get_page_title(self) -> str:
        return self.page.title() if self.page else ""

    def get_page_text(self) -> str:
        """Extract visible text from the page body."""
        if not self.page:
            return ""
        try:
            return self.page.inner_text("body")
        except Exception:
            return ""

    def get_accessibility_tree(self) -> Optional[Dict[str, Any]]:
        """Get the accessibility tree snapshot."""
        if not self.page:
            return None
        try:
            return self.page.accessibility.snapshot(interesting_only=True)
        except Exception as e:
            logger.warning(f"[Playwright] A11y snapshot failed: {e}")
            return None

    def extract_dom(self) -> Tuple[List[DOMNode], str]:
        """
        Extracts DOM nodes, prunes non-interactive structural noise, and assigns numeric node IDs.
        """
        if not self.page:
            return [], ""

        self._node_map.clear()
        
        # Client-side script extracting interactive & content elements
        extraction_js = """
        () => {
            const elements = Array.from(document.querySelectorAll('input, button, a, textarea, select, label, h1, h2, h3, p, span, form'));
            return elements.map((el, idx) => {
                const rect = el.getBoundingClientRect();
                const isInteractive = ['INPUT', 'BUTTON', 'A', 'TEXTAREA', 'SELECT'].includes(el.tagName);
                return {
                    node_id: idx,
                    tag_name: el.tagName.toLowerCase(),
                    element_type: el.getAttribute('type') || (el.tagName === 'INPUT' ? 'text' : ''),
                    element_id: el.id || '',
                    name: el.getAttribute('name') || '',
                    text_content: el.innerText || el.textContent || '',
                    value: el.value || '',
                    is_interactive: isInteractive,
                    is_visible: rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden',
                    bounding_box: {
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    },
                    attributes: {
                        type: el.getAttribute('type') || '',
                        placeholder: el.getAttribute('placeholder') || '',
                        name: el.getAttribute('name') || '',
                        autocomplete: el.getAttribute('autocomplete') || '',
                        'aria-label': el.getAttribute('aria-label') || ''
                    }
                };
            }).filter(e => e.is_visible);
        }
        """

        try:
            raw_nodes_data = self.page.evaluate(extraction_js)
        except Exception as e:
            logger.warning(f"[Playwright] DOM extraction failed: {e}")
            return [], ""

        dom_nodes: List[DOMNode] = []
        formatted_lines: List[str] = []

        for data in raw_nodes_data:
            node = DOMNode(
                node_id=data["node_id"],
                tag_name=data["tag_name"],
                element_type=data["element_type"],
                element_id=data["element_id"],
                name=data["name"],
                text_content=data["text_content"].strip(),
                value=data["value"],
                is_interactive=data["is_interactive"],
                is_visible=data["is_visible"],
                bounding_box=data["bounding_box"],
                attributes=data["attributes"]
            )
            dom_nodes.append(node)
            self._node_map[node.node_id] = node

            # Formatted text string representation
            if node.is_interactive:
                line = f"[{node.node_id}] <{node.tag_name} type='{node.element_type}' name='{node.name}' placeholder='{node.attributes.get('placeholder', '')}' value='{node.value}'>{node.text_content}</{node.tag_name}>"
                formatted_lines.append(line)

        formatted_dom = "\n".join(formatted_lines)
        return dom_nodes, formatted_dom

    def capture_screenshot_b64(self) -> str:
        if not self.page:
            return ""
        try:
            bytes_data = self.page.screenshot(type="png", full_page=False)
            return base64.b64encode(bytes_data).decode("utf-8")
        except Exception as e:
            logger.warning(f"[Playwright] Screenshot failed: {e}")
            return ""

    def click_element(self, node_id: int) -> bool:
        if not self.page or node_id not in self._node_map:
            return False

        node: DOMNode = self._node_map[node_id]
        selector = f"#{node.element_id}" if node.element_id else f"[name='{node.name}']" if node.name else None
        
        try:
            if selector and self.page.query_selector(selector):
                if self.realistic_simulation and node.bounding_box:
                    x = node.bounding_box["x"] + node.bounding_box["width"] / 2
                    y = node.bounding_box["y"] + node.bounding_box["height"] / 2
                    self.pointer.move_to(self.page, x, y)
                self.page.click(selector, timeout=5000)
            elif node.bounding_box:
                x = node.bounding_box["x"] + node.bounding_box["width"] / 2
                y = node.bounding_box["y"] + node.bounding_box["height"] / 2
                if self.realistic_simulation:
                    self.pointer.move_to(self.page, x, y)
                self.page.mouse.click(x, y)
            else:
                return False
            self.wait_for_stable(timeout_ms=2000)
            return True
        except Exception as e:
            logger.error(f"[Playwright Click Failed] Node {node_id}: {e}")
            return False

    def type_text(self, node_id: int, text: str) -> bool:
        if not self.page or node_id not in self._node_map:
            return False

        node: DOMNode = self._node_map[node_id]
        selector = f"#{node.element_id}" if node.element_id else f"[name='{node.name}']" if node.name else None

        try:
            if selector and self.page.query_selector(selector):
                if self.realistic_simulation:
                    from webveil.browser.pointer import HumanizedTyping
                    self.page.click(selector)
                    HumanizedTyping.type_with_cadence(self.page, text, simulate_realistic_delay=False)
                else:
                    self.page.fill(selector, text)
            elif node.bounding_box:
                x = node.bounding_box["x"] + node.bounding_box["width"] / 2
                y = node.bounding_box["y"] + node.bounding_box["height"] / 2
                if self.realistic_simulation:
                    from webveil.browser.pointer import HumanizedTyping
                    self.pointer.move_to(self.page, x, y)
                    self.page.mouse.click(x, y)
                    HumanizedTyping.type_with_cadence(self.page, text, simulate_realistic_delay=False)
                else:
                    self.page.mouse.click(x, y)
                    self.page.keyboard.type(text)
            else:
                return False
            return True
        except Exception as e:
            logger.error(f"[Playwright Type Failed] Node {node_id}: {e}")
            return False

    def select_option(self, node_id: int, value: str) -> bool:
        """Select an option from a <select> dropdown."""
        if not self.page or node_id not in self._node_map:
            return False

        node: DOMNode = self._node_map[node_id]
        selector = f"#{node.element_id}" if node.element_id else f"[name='{node.name}']" if node.name else None

        try:
            if selector:
                self.page.select_option(selector, value=value)
                return True
            return False
        except Exception as e:
            logger.error(f"[Playwright Select Failed] Node {node_id}: {e}")
            return False

    def press_key(self, key: str) -> bool:
        if not self.page:
            return False
        try:
            self.page.keyboard.press(key)
            self.wait_for_stable(timeout_ms=2000)
            return True
        except Exception as e:
            logger.error(f"[Playwright Keypress Failed] {key}: {e}")
            return False

    def scroll_page(self, direction: str = "down", amount: int = 300) -> bool:
        if not self.page:
            return False
        delta_y = amount if direction == "down" else -amount
        self.page.evaluate(f"window.scrollBy(0, {delta_y});")
        return True

    def click_coordinates(self, x: int, y: int) -> bool:
        """Click at specific page coordinates (for visual/canvas interactions)."""
        if not self.page:
            return False
        try:
            self.page.mouse.click(x, y)
            self.wait_for_stable(timeout_ms=1000)
            return True
        except Exception as e:
            logger.error(f"[Playwright Coordinate Click Failed] ({x}, {y}): {e}")
            return False
