"""Simple collision checks of the robot footprint against walls and goals."""
from __future__ import annotations

from .geometry import circle_hits_polygon, rotated_rect
from .profile import RobotConfig, Timeline

GOAL_RADIUS = 2.8  # ~ half of the 5.61 in goal base


def find_collisions(tl: Timeline, layout: dict, robot: RobotConfig, dt: float = 0.05) -> list[tuple[float, float, float, str]]:
    """Return (t, x, y, what) at the start of each collision interval."""
    size = layout["field_size"]
    goals = layout.get("goals", [])
    hits: list[tuple[float, float, float, str]] = []
    active: set[str] = set()
    n = int(tl.total / dt) + 1
    for k in range(n + 1):
        t = min(k * dt, tl.total)
        x, y, h, _ = tl.pose_at(t)
        poly = rotated_rect(x, y, h, robot.width, robot.length)
        now: set[str] = set()
        if any(px < -0.01 or py < -0.01 or px > size + 0.01 or py > size + 0.01 for px, py in poly):
            now.add("wall")
        for gi, g in enumerate(goals):
            if circle_hits_polygon((g["x"], g["y"]), GOAL_RADIUS, poly):
                now.add(f"goal {gi + 1} ({g['color']})")
        for what in now - active:
            hits.append((t, x, y, what))
        active = now
    return hits
