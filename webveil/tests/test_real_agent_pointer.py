"""
Unit tests for Phase 8: Real Agent Pointer.
Verifies Bezier curve generation, pointer motion simulation,
Gaussian humanized typing delays, and visual pointer trail rendering.
"""

import io
import unittest
from unittest.mock import MagicMock
from PIL import Image

from webveil.browser.pointer import (
    RealisticPointer, HumanizedTyping, draw_pointer_trail_on_image
)


class TestRealAgentPointer(unittest.TestCase):

    def test_bezier_path_generation(self):
        """Verify cubic Bezier path generation smoothly bridges start and end."""
        start = (100.0, 100.0)
        end = (500.0, 400.0)
        steps = 20

        points = RealisticPointer.generate_bezier_path(start, end, steps=steps, jitter_amount=2.0)

        self.assertEqual(len(points), steps + 1)
        self.assertEqual(points[0], start)
        self.assertEqual(points[-1], end)

        # Ensure no NaNs or infinities
        for pt in points:
            self.assertFalse(any(isinstance(v, complex) for v in pt))
            self.assertGreaterEqual(pt[0], 0)
            self.assertGreaterEqual(pt[1], 0)

    def test_realistic_pointer_move_to(self):
        """Verify pointer tracks position and maintains trail history."""
        pointer = RealisticPointer(current_pos=(50.0, 50.0))
        mock_page = MagicMock()

        path = pointer.move_to(mock_page, target_x=300.0, target_y=200.0, steps=10)

        self.assertEqual(pointer.current_pos, (300.0, 200.0))
        self.assertEqual(len(pointer.trail_history), 11)
        self.assertEqual(mock_page.mouse.move.call_count, 11)

    def test_humanized_typing_cadence(self):
        """Verify Gaussian delay distribution for realistic typing."""
        # Standard alphanumeric character delay
        delays = [HumanizedTyping.get_keystroke_delay('a') for _ in range(50)]
        for d in delays:
            self.assertGreaterEqual(d, 0.020)  # Min 20ms
            self.assertLessEqual(d, 0.200)     # Max 200ms

        # Space or punctuation should include pause
        delay_space = HumanizedTyping.get_keystroke_delay(' ')
        self.assertGreaterEqual(delay_space, 0.050)

        # Mock typing simulation
        mock_page = MagicMock()
        HumanizedTyping.type_with_cadence(mock_page, "Search", simulate_realistic_delay=False)
        self.assertEqual(mock_page.keyboard.type.call_count, 6)

    def test_pointer_trail_drawing_on_image(self):
        """Verify visual trail and cursor circle rendering on screenshot."""
        img = Image.new("RGB", (300, 200), color=(255, 255, 255))
        trail = [(10.0, 10.0, 1.0), (50.0, 60.0, 2.0), (100.0, 120.0, 3.0)]

        draw_pointer_trail_on_image(img, trail, cursor_pos=(100.0, 120.0))

        # Check that target cursor was drawn (red center at (100, 120))
        pixel = img.getpixel((100, 120))
        self.assertEqual(pixel[0], 255)  # Red channel active
        self.assertLess(pixel[1], 100)   # Green channel suppressed


if __name__ == "__main__":
    unittest.main()
