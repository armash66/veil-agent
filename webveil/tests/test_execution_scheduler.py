"""
Unit tests for Execution Scheduler.
Verifies separation of browser readiness from security authorization,
immediate zero-delay dispatch on ready states, and target attachment polling.
"""

import unittest
from unittest.mock import MagicMock
from webveil.core.models.schema import BrowserAction, ActionType, DOMNode
from webveil.browser.scheduler import ExecutionScheduler, ReadinessStatus


class TestExecutionScheduler(unittest.TestCase):

    def setUp(self):
        self.scheduler = ExecutionScheduler(default_timeout_ms=300.0, poll_interval_ms=10.0)

    def test_global_actions_ready_immediately(self):
        """Verify global actions (done, wait, keypress, navigate) execute immediately with 0 delay."""
        actions = [
            BrowserAction(action=ActionType.DONE),
            BrowserAction(action=ActionType.WAIT),
            BrowserAction(action=ActionType.KEYPRESS, key="Enter"),
            BrowserAction(action=ActionType.NAVIGATE, url="https://example.com"),
        ]

        for act in actions:
            status = self.scheduler.await_readiness(page=None, action=act)
            self.assertTrue(status.is_ready)
            self.assertEqual(status.retries_used, 0)
            self.assertLess(status.elapsed_ms, 50.0)

    def test_target_ready_when_dom_stable(self):
        """Verify scheduler returns ready when document.readyState is complete and target is visible."""
        mock_page = MagicMock()
        mock_page.evaluate.return_value = "complete"

        mock_locator = MagicMock()
        mock_locator.is_visible.return_value = True
        mock_page.locator.return_value = mock_locator

        action = BrowserAction(action=ActionType.CLICK, node_id=10)
        status = self.scheduler.await_readiness(page=mock_page, action=action)

        self.assertTrue(status.is_ready)
        self.assertEqual(status.retries_used, 0)
        self.assertLess(status.elapsed_ms, 50.0)

    def test_target_not_ready_times_out(self):
        """Verify scheduler times out cleanly if target element is hidden/missing without raising unhandled crash."""
        mock_page = MagicMock()
        mock_page.evaluate.return_value = "complete"

        mock_locator = MagicMock()
        mock_locator.is_visible.return_value = False  # element never appears
        mock_page.locator.return_value = mock_locator

        action = BrowserAction(action=ActionType.CLICK, node_id=99)
        status = self.scheduler.await_readiness(page=mock_page, action=action, max_wait_ms=60.0)

        self.assertFalse(status.is_ready)
        self.assertIn("timeout", status.reason.lower())
        self.assertGreater(status.retries_used, 0)


if __name__ == "__main__":
    unittest.main()
