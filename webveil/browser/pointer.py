"""
Realistic Humanized Pointer & Keyboard Simulation Engine.
Provides cubic Bezier mouse trajectories, natural Gaussian typing delays,
and pointer trail coordinates for visual auditing.
"""

import time
import math
import random
import logging
from typing import List, Tuple, Dict, Any, Optional

logger = logging.getLogger("WebVeilBrowser.Pointer")


class RealisticPointer:
    """
    Simulates human-like pointer motion using randomized cubic Bezier curves
    with velocity curvature and micro-jitter.
    """

    def __init__(self, current_pos: Tuple[float, float] = (0.0, 0.0)):
        self.current_pos = current_pos
        self.trail_history: List[Tuple[float, float, float]] = []

    @staticmethod
    def generate_bezier_path(
        start: Tuple[float, float],
        end: Tuple[float, float],
        steps: int = 20,
        jitter_amount: float = 3.0,
    ) -> List[Tuple[float, float]]:
        """
        Generate cubic Bezier curve points between start and end.
        P(t) = (1-t)^3 * P0 + 3(1-t)^2 * t * P1 + 3(1-t) * t^2 * P2 + t^3 * P3
        """
        x0, y0 = start
        x3, y3 = end

        # Distance
        dx = x3 - x0
        dy = y3 - y0
        dist = math.hypot(dx, dy)

        if dist < 1.0 or steps <= 1:
            return [start, end]

        # Randomized control points with perpendicular deviation
        dev = dist * random.uniform(0.15, 0.35)
        angle = math.atan2(dy, dx)
        perp_angle = angle + (math.pi / 2.0) * random.choice([1, -1])

        p1_dist = dist * random.uniform(0.25, 0.45)
        x1 = x0 + math.cos(angle) * p1_dist + math.cos(perp_angle) * dev
        y1 = y0 + math.sin(angle) * p1_dist + math.sin(perp_angle) * dev

        p2_dist = dist * random.uniform(0.55, 0.85)
        x2 = x0 + math.cos(angle) * p2_dist + math.cos(perp_angle) * (dev * 0.6)
        y2 = y0 + math.sin(angle) * p2_dist + math.sin(perp_angle) * (dev * 0.6)

        points: List[Tuple[float, float]] = []

        for step in range(steps + 1):
            t = step / float(steps)

            # Ease-in-out profile
            # Smoothstep: t * t * (3 - 2 * t)
            t_ease = t * t * (3.0 - 2.0 * t)

            u = 1.0 - t_ease
            tt = t_ease * t_ease
            uu = u * u
            uuu = uu * u
            ttt = tt * t_ease

            px = uuu * x0 + 3 * uu * t_ease * x1 + 3 * u * tt * x2 + ttt * x3
            py = uuu * y0 + 3 * uu * t_ease * y1 + 3 * u * tt * y2 + ttt * y3

            # Apply subtle micro-jitter for non-endpoints
            if 0 < step < steps:
                px += random.uniform(-jitter_amount, jitter_amount)
                py += random.uniform(-jitter_amount, jitter_amount)

            points.append((round(px, 1), round(py, 1)))

        return points

    def move_to(
        self,
        page,
        target_x: float,
        target_y: float,
        steps: int = 15,
        speed_factor: float = 1.0,
    ) -> List[Tuple[float, float]]:
        """
        Move mouse smoothly from current position to target coordinates via Bezier curve.
        """
        start = self.current_pos
        end = (target_x, target_y)

        path = self.generate_bezier_path(start, end, steps=steps)

        for pt in path:
            x, y = pt
            if page and hasattr(page, "mouse"):
                try:
                    page.mouse.move(x, y)
                except Exception:
                    pass
            self.trail_history.append((x, y, time.time()))

        self.current_pos = end
        return path


class HumanizedTyping:
    """
    Simulates human typing rhythm with natural Gaussian delay distribution.
    """

    @staticmethod
    def get_keystroke_delay(char: str, mean_ms: float = 65.0, std_ms: float = 25.0) -> float:
        """
        Compute Gaussian delay in seconds for a single keystroke.
        Adds pause after punctuation or space.
        """
        base_delay_ms = random.gauss(mean_ms, std_ms)
        clamped_ms = max(20.0, min(200.0, base_delay_ms))

        # Human pauses after punctuation or space
        if char in " .,?!;:\n":
            clamped_ms += random.uniform(50.0, 140.0)

        return clamped_ms / 1000.0

    @staticmethod
    def type_with_cadence(
        page,
        text: str,
        simulate_realistic_delay: bool = True,
    ):
        """
        Type string character by character with realistic human latency.
        """
        if not page or not hasattr(page, "keyboard"):
            return

        for char in text:
            page.keyboard.type(char)
            if simulate_realistic_delay:
                delay = HumanizedTyping.get_keystroke_delay(char)
                time.sleep(delay)


def draw_pointer_trail_on_image(
    image,
    trail: List[Tuple[float, float, float]],
    cursor_pos: Optional[Tuple[float, float]] = None,
):
    """
    Draw smooth pointer trail and cursor circle on a PIL Image for auditing.
    """
    from PIL import ImageDraw
    draw = ImageDraw.Draw(image)

    # Draw trail line segments with fading alpha
    if len(trail) > 1:
        for i in range(1, len(trail)):
            x1, y1, _ = trail[i - 1]
            x2, y2, _ = trail[i]
            draw.line([(x1, y1), (x2, y2)], fill=(0, 200, 255), width=2)

    # Draw target cursor circle
    if cursor_pos:
        cx, cy = cursor_pos
        r = 6
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 50, 50), outline=(255, 255, 255), width=2)
