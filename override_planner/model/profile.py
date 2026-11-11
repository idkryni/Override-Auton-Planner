"""Trapezoidal motion profile -> timeline used for time estimates, playback and exports."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .actions import Action
from .geometry import Point, angle_diff, cumulative_lengths, heading_to, norm_heading, point_at_length
from .path import Route


@dataclass
class RobotConfig:
    width: float = 15.0
    length: float = 15.0
    max_velocity: float = 60.0              # in/s
    max_acceleration: float = 120.0         # in/s^2
    max_angular_velocity: float = 360.0     # deg/s
    max_angular_acceleration: float = 900.0 # deg/s^2
    turn_threshold_deg: float = 3.0

    @classmethod
    def from_dict(cls, d: dict) -> "RobotConfig":
        names = cls.__dataclass_fields__.keys()
        return cls(**{k: float(v) for k, v in d.items() if k in names})

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def trapezoid_time(d: float, vmax: float, amax: float) -> float:
    """Time to travel distance d from rest to rest."""
    d = abs(d)
    if d <= 0 or vmax <= 0 or amax <= 0:
        return 0.0
    d_acc = vmax * vmax / amax  # accel + decel distance at full speed
    if d <= d_acc:
        return 2.0 * math.sqrt(d / amax)
    return d / vmax + vmax / amax


def trapezoid_pos(t: float, d: float, vmax: float, amax: float) -> float:
    """Distance travelled at time t along a rest-to-rest profile of length d."""
    d = abs(d)
    total = trapezoid_time(d, vmax, amax)
    if total <= 0:
        return d
    t = max(0.0, min(t, total))
    if d <= vmax * vmax / amax:  # triangular
        th = total / 2
        if t <= th:
            return 0.5 * amax * t * t
        r = total - t
        return d - 0.5 * amax * r * r
    ta = vmax / amax
    if t <= ta:
        return 0.5 * amax * t * t
    if t <= total - ta:
        return 0.5 * vmax * ta + vmax * (t - ta)
    r = total - t
    return d - 0.5 * amax * r * r


@dataclass
class Phase:
    kind: str                       # "turn" | "drive" | "action"
    t0: float
    t1: float
    wp: int                         # waypoint index this phase belongs to
    x: float = 0.0                  # start position
    y: float = 0.0
    h0: float = 0.0                 # start heading
    h1: float = 0.0                 # end heading (for turns: h0 + signed delta)
    reverse: bool = False
    curve: bool = False
    speed: float = 100.0
    face_point: Optional[Point] = None   # turn is a "turn to face point" before driving
    pts: list[Point] = field(default_factory=list)
    cum: list[float] = field(default_factory=list)
    vmax: float = 0.0
    amax: float = 0.0
    action: Optional[Action] = None

    @property
    def duration(self) -> float:
        return self.t1 - self.t0

    @property
    def length(self) -> float:
        return self.cum[-1] if self.cum else 0.0

    @property
    def end(self) -> Point:
        return self.pts[-1] if self.pts else (self.x, self.y)


@dataclass
class Timeline:
    phases: list[Phase]
    total: float
    arrival: list[float]  # time each waypoint is reached (index-aligned with route.waypoints)
    finish: list[float]   # time each waypoint's actions finish

    def pose_at(self, t: float) -> tuple[float, float, float, Optional[Phase]]:
        if not self.phases:
            return 0.0, 0.0, 0.0, None
        ph = self.phases[-1]
        for p in self.phases:
            if t <= p.t1:
                ph = p
                break
        local = max(0.0, min(t - ph.t0, ph.duration))
        if ph.kind == "turn":
            d = ph.h1 - ph.h0
            s = trapezoid_pos(local, abs(d), ph.vmax, ph.amax)
            h = ph.h0 + math.copysign(s, d)
            return ph.x, ph.y, norm_heading(h), ph
        if ph.kind == "drive" and ph.pts:
            s = trapezoid_pos(local, ph.length, ph.vmax, ph.amax)
            (px, py), travel = point_at_length(ph.pts, ph.cum, s)
            if ph.length <= 1e-6:
                return px, py, ph.h0, ph
            if ph.curve:
                h = norm_heading(travel + 180) if ph.reverse else travel
            else:
                h = ph.h1
            return px, py, h, ph
        return ph.x, ph.y, norm_heading(ph.h0), ph


def build_timeline(route: Route, robot: RobotConfig) -> Timeline:
    phases: list[Phase] = []
    wps = route.waypoints
    arrival: list[float] = []
    finish: list[float] = []
    if not wps:
        return Timeline([], 0.0, [], [])
    t = 0.0
    x, y = wps[0].x, wps[0].y
    h = wps[0].heading if wps[0].heading is not None else 0.0
    va, aa = robot.max_angular_velocity, robot.max_angular_acceleration

    def turn(target: float, wp_i: int, face: Optional[Point] = None) -> None:
        nonlocal t, h
        d = angle_diff(target, h)
        if abs(d) < robot.turn_threshold_deg:
            h = norm_heading(target)
            return
        dur = trapezoid_time(abs(d), va, aa)
        phases.append(Phase("turn", t, t + dur, wp_i, x, y, h, h + d, face_point=face, vmax=va, amax=aa))
        t += dur
        h = norm_heading(target)

    def do_actions(wp_i: int) -> None:
        nonlocal t
        for a in wps[wp_i].actions:
            dur = max(0.0, a.duration)
            phases.append(Phase("action", t, t + dur, wp_i, x, y, h, h, action=a))
            t += dur

    arrival.append(0.0)
    do_actions(0)
    finish.append(t)

    for i in range(1, len(wps)):
        wp = wps[i]
        speed = max(1.0, min(100.0, wp.speed))
        vmax = robot.max_velocity * speed / 100.0
        amax = robot.max_acceleration
        pts = route.segment_points(i)
        cum = cumulative_lengths(pts)
        if wp.curve and len(pts) > 2:
            dur = trapezoid_time(cum[-1], vmax, amax)
            end_h = route.curve_end_heading(i)
            phases.append(Phase("drive", t, t + dur, i, x, y, h, end_h, reverse=wp.reverse, curve=True,
                                speed=speed, pts=pts, cum=cum, vmax=vmax, amax=amax))
            t += dur
            x, y, h = wp.x, wp.y, end_h
        elif cum[-1] > 1e-6:
            travel = heading_to(pts[0], pts[-1])
            face = norm_heading(travel + 180) if wp.reverse else travel
            turn(face, i, wp.pos)
            dur = trapezoid_time(cum[-1], vmax, amax)
            phases.append(Phase("drive", t, t + dur, i, x, y, h, h, reverse=wp.reverse, speed=speed,
                                pts=pts, cum=cum, vmax=vmax, amax=amax))
            t += dur
            x, y = wp.x, wp.y
        if wp.heading is not None and not wp.curve:
            turn(wp.heading, i)
        arrival.append(t)
        do_actions(i)
        finish.append(t)
    return Timeline(phases, t, arrival, finish)
