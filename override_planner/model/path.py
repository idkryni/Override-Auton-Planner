"""Route model: ordered waypoints joined by straight or cubic-bezier segments."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from .actions import Action
from .geometry import Point, dist, heading_to, heading_vec, norm_heading, sample_bezier

FIELD_SIZE = 140.41


@dataclass
class Waypoint:
    x: float
    y: float
    heading: Optional[float] = None  # final robot heading (None = keep travel heading)
    reverse: bool = False            # drive backwards INTO this waypoint
    curve: bool = False              # segment INTO this waypoint is a cubic bezier
    c1: Optional[Point] = None       # bezier control near previous waypoint
    c2: Optional[Point] = None       # bezier control near this waypoint
    speed: float = 100.0             # max speed percent for the segment into this waypoint
    actions: list[Action] = field(default_factory=list)

    @property
    def pos(self) -> Point:
        return (self.x, self.y)

    def to_dict(self) -> dict:
        return {
            "x": round(self.x, 3), "y": round(self.y, 3),
            "heading": None if self.heading is None else round(self.heading, 2),
            "reverse": self.reverse, "curve": self.curve,
            "c1": None if self.c1 is None else [round(self.c1[0], 3), round(self.c1[1], 3)],
            "c2": None if self.c2 is None else [round(self.c2[0], 3), round(self.c2[1], 3)],
            "speed": self.speed,
            "actions": [a.to_dict() for a in self.actions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Waypoint":
        return cls(
            x=float(d["x"]), y=float(d["y"]),
            heading=None if d.get("heading") is None else float(d["heading"]),
            reverse=bool(d.get("reverse", False)), curve=bool(d.get("curve", False)),
            c1=None if d.get("c1") is None else (float(d["c1"][0]), float(d["c1"][1])),
            c2=None if d.get("c2") is None else (float(d["c2"][0]), float(d["c2"][1])),
            speed=float(d.get("speed", 100.0)),
            actions=[Action.from_dict(a) for a in d.get("actions", [])],
        )


@dataclass
class Route:
    name: str = "auton"
    waypoints: list[Waypoint] = field(default_factory=list)
    notes: str = ""

    # ---- editing -------------------------------------------------------------
    def add(self, x: float, y: float, index: Optional[int] = None) -> int:
        wp = Waypoint(x, y)
        if not self.waypoints:
            wp.heading = 0.0
        if index is None or index >= len(self.waypoints):
            self.waypoints.append(wp)
            return len(self.waypoints) - 1
        self.waypoints.insert(index, wp)
        return index

    def remove(self, i: int) -> None:
        del self.waypoints[i]
        if self.waypoints:
            w0 = self.waypoints[0]
            w0.curve, w0.reverse, w0.c1, w0.c2 = False, False, None, None
            if w0.heading is None:
                w0.heading = 0.0

    def move(self, i: int, x: float, y: float) -> None:
        """Move a waypoint, dragging attached bezier controls along with it."""
        wp = self.waypoints[i]
        dx, dy = x - wp.x, y - wp.y
        wp.x, wp.y = x, y
        if wp.curve and wp.c2 is not None:
            wp.c2 = (wp.c2[0] + dx, wp.c2[1] + dy)
        if i + 1 < len(self.waypoints):
            nxt = self.waypoints[i + 1]
            if nxt.curve and nxt.c1 is not None:
                nxt.c1 = (nxt.c1[0] + dx, nxt.c1[1] + dy)

    def set_curve(self, i: int, on: bool) -> None:
        if i <= 0:
            return
        wp = self.waypoints[i]
        wp.curve = on
        if on and (wp.c1 is None or wp.c2 is None):
            wp.c1, wp.c2 = self.default_controls(i)

    def default_controls(self, i: int) -> tuple[Point, Point]:
        prev, wp = self.waypoints[i - 1], self.waypoints[i]
        d = max(dist(prev.pos, wp.pos), 1.0) / 3.0
        travel = heading_to(prev.pos, wp.pos)
        start_h = self.heading_at(i - 1)
        if start_h is None:
            start_h = travel
        # Direction the robot travels leaving prev (opposite of facing when reversing).
        out_h = start_h + (180 if wp.reverse else 0)
        end_h = travel if wp.heading is None else wp.heading + (180 if wp.reverse else 0)
        v1 = heading_vec(out_h, d)
        v2 = heading_vec(end_h, d)
        return (prev.x + v1[0], prev.y + v1[1]), (wp.x - v2[0], wp.y - v2[1])

    def set_heading(self, i: int, h: Optional[float]) -> None:
        wp = self.waypoints[i]
        wp.heading = None if h is None else norm_heading(h)
        if wp.curve and wp.c2 is not None and h is not None:
            # Keep bezier end tangent consistent with the requested pose heading.
            d = max(dist(wp.c2, wp.pos), 1.0)
            travel_h = h + (180 if wp.reverse else 0)
            v = heading_vec(travel_h, d)
            wp.c2 = (wp.x - v[0], wp.y - v[1])

    def mirror(self, field_size: float = FIELD_SIZE) -> None:
        """Mirror left<->right (red <-> blue side)."""
        for wp in self.waypoints:
            wp.x = field_size - wp.x
            if wp.heading is not None:
                wp.heading = norm_heading(-wp.heading)
            if wp.c1 is not None:
                wp.c1 = (field_size - wp.c1[0], wp.c1[1])
            if wp.c2 is not None:
                wp.c2 = (field_size - wp.c2[0], wp.c2[1])

    # ---- queries -------------------------------------------------------------
    def segment_points(self, i: int, step: float = 0.5) -> list[Point]:
        """Polyline the robot center follows from waypoint i-1 to waypoint i."""
        prev, wp = self.waypoints[i - 1], self.waypoints[i]
        if wp.curve and wp.c1 is not None and wp.c2 is not None:
            return sample_bezier(prev.pos, wp.c1, wp.c2, wp.pos, step)
        return [prev.pos, wp.pos]

    def curve_end_heading(self, i: int) -> float:
        """Robot heading at the end of a curved segment (from bezier tangent)."""
        wp = self.waypoints[i]
        pts = self.segment_points(i)
        a = pts[-2] if len(pts) >= 2 else self.waypoints[i - 1].pos
        if wp.c2 is not None and dist(wp.c2, wp.pos) > 1e-6:
            a = wp.c2
        h = heading_to(a, wp.pos)
        return norm_heading(h + 180) if wp.reverse else h

    def heading_at(self, i: int) -> Optional[float]:
        """Robot heading after arriving at waypoint i (before its actions)."""
        if not self.waypoints:
            return None
        wp = self.waypoints[i]
        if i == 0:
            return wp.heading if wp.heading is not None else 0.0
        if wp.curve:
            return self.curve_end_heading(i)
        if wp.heading is not None:
            return wp.heading
        travel = heading_to(self.waypoints[i - 1].pos, wp.pos)
        if dist(self.waypoints[i - 1].pos, wp.pos) < 1e-6:
            return self.heading_at(i - 1)
        return norm_heading(travel + 180) if wp.reverse else travel

    # ---- serialization -------------------------------------------------------
    def to_dict(self) -> dict:
        return {"name": self.name, "notes": self.notes, "units": "in",
                "frame": "origin bottom-left (audience view), heading 0 = far wall, CW+",
                "waypoints": [w.to_dict() for w in self.waypoints]}

    @classmethod
    def from_dict(cls, d: dict) -> "Route":
        return cls(name=d.get("name", "auton"), notes=d.get("notes", ""),
                   waypoints=[Waypoint.from_dict(w) for w in d.get("waypoints", [])])

    def clone(self) -> "Route":
        return copy.deepcopy(self)
