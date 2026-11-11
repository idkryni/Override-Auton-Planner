"""Geometry helpers. Field frame: inches, +Y toward far wall, heading 0 = +Y, clockwise positive."""
from __future__ import annotations

import math
from typing import Iterable, Sequence

Point = tuple[float, float]


def norm_heading(h: float) -> float:
    """Normalize to [0, 360)."""
    h = math.fmod(h, 360.0)
    return h + 360.0 if h < 0 else (0.0 if h == 360.0 else h)


def angle_diff(target: float, current: float) -> float:
    """Shortest signed turn from current to target, in (-180, 180]."""
    d = math.fmod(target - current, 360.0)
    if d > 180.0:
        d -= 360.0
    elif d <= -180.0:
        d += 360.0
    return d


def heading_to(a: Point, b: Point) -> float:
    """Compass heading of the vector a->b."""
    return norm_heading(math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])))


def heading_vec(h: float, length: float = 1.0) -> Point:
    r = math.radians(h)
    return (math.sin(r) * length, math.cos(r) * length)


def dist(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def lerp(a: Point, b: Point, t: float) -> Point:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def bezier(p0: Point, p1: Point, p2: Point, p3: Point, t: float) -> Point:
    u = 1.0 - t
    b0, b1, b2, b3 = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (
        b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0],
        b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1],
    )


def sample_bezier(p0: Point, p1: Point, p2: Point, p3: Point, step: float = 0.5) -> list[Point]:
    """Sample a cubic bezier at roughly `step` inch spacing (endpoints included)."""
    approx = dist(p0, p1) + dist(p1, p2) + dist(p2, p3)
    n = max(8, int(math.ceil(approx / step)))
    return [bezier(p0, p1, p2, p3, i / n) for i in range(n + 1)]


def polyline_length(pts: Sequence[Point]) -> float:
    return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def cumulative_lengths(pts: Sequence[Point]) -> list[float]:
    out = [0.0]
    for i in range(len(pts) - 1):
        out.append(out[-1] + dist(pts[i], pts[i + 1]))
    return out


def point_at_length(pts: Sequence[Point], cum: Sequence[float], s: float) -> tuple[Point, float]:
    """Point and travel heading at arc length s along a polyline."""
    if len(pts) == 1:
        return pts[0], 0.0
    s = max(0.0, min(s, cum[-1]))
    lo, hi = 0, len(cum) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if cum[mid] <= s:
            lo = mid
        else:
            hi = mid
    seg = cum[hi] - cum[lo]
    t = 0.0 if seg <= 1e-9 else (s - cum[lo]) / seg
    return lerp(pts[lo], pts[hi], t), heading_to(pts[lo], pts[hi])


def rotated_rect(cx: float, cy: float, heading: float, width: float, length: float) -> list[Point]:
    """Corners of a robot footprint centered at (cx, cy) facing `heading`."""
    fx, fy = heading_vec(heading, length / 2)
    rx, ry = heading_vec(heading + 90, width / 2)
    return [
        (cx + fx + rx, cy + fy + ry),
        (cx + fx - rx, cy + fy - ry),
        (cx - fx - rx, cy - fy - ry),
        (cx - fx + rx, cy - fy + ry),
    ]


def point_seg_distance(p: Point, a: Point, b: Point) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    l2 = vx * vx + vy * vy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / l2))
    return dist(p, (a[0] + vx * t, a[1] + vy * t))


def point_in_polygon(p: Point, poly: Sequence[Point]) -> bool:
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > p[1]) != (yj > p[1]) and p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def circle_hits_polygon(c: Point, r: float, poly: Sequence[Point]) -> bool:
    if point_in_polygon(c, poly):
        return True
    return any(point_seg_distance(c, poly[i], poly[(i + 1) % len(poly)]) < r for i in range(len(poly)))


def bounds(pts: Iterable[Point]) -> tuple[float, float, float, float]:
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)
