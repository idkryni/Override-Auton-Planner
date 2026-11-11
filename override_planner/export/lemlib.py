"""LemLib (PROS) exporter. Targets LemLib 0.5.x (async motions, waitUntilDone)."""
from __future__ import annotations

from ..model.path import Route
from ..model.profile import RobotConfig, build_timeline
from .common import ExportOptions, build_steps, fmt, header, speed127


def _params(forwards: bool, speed: float, extra: str = "") -> str:
    parts = []
    if not forwards:
        parts.append(".forwards = false")
    if speed < 100:
        parts.append(f".maxSpeed = {speed127(speed)}")
    if extra:
        parts.append(extra)
    return ", {" + ", ".join(parts) + "}" if parts else ""


def export(route: Route, robot: RobotConfig, opts: ExportOptions | None = None) -> str:
    opts = opts or ExportOptions()
    tl = build_timeline(route, robot)
    out = header(route, robot, opts, tl, "LemLib")
    out.append(f"void {opts.function_name}() {{")
    moving = False  # a motion was queued since the last waitUntilDone

    def wait() -> None:
        nonlocal moving
        if moving:
            out.append("    chassis.waitUntilDone();")
            moving = False

    for s in build_steps(route, robot, opts, tl):
        if s.kind == "set_pose":
            out.append(f"    chassis.setPose({fmt(s.x)}, {fmt(s.y)}, {fmt(s.h)});")
        elif s.kind == "comment":
            out.append(f"    // {s.text}")
        elif s.kind == "turn_point":
            out.append(f"    chassis.turnToPoint({fmt(s.x)}, {fmt(s.y)}, {s.timeout_ms}{_params(not s.reverse, 100)});")
            moving = True
        elif s.kind == "turn_heading":
            out.append(f"    chassis.turnToHeading({fmt(s.h)}, {s.timeout_ms});")
            moving = True
        elif s.kind == "drive":
            out.append(f"    chassis.moveToPoint({fmt(s.x)}, {fmt(s.y)}, {s.timeout_ms}{_params(not s.reverse, s.speed)});")
            moving = True
        elif s.kind == "curve":
            out.append(f"    chassis.moveToPose({fmt(s.x)}, {fmt(s.y)}, {fmt(s.h)}, {s.timeout_ms}"
                       f"{_params(not s.reverse, s.speed)});")
            moving = True
        elif s.kind == "action" and s.action is not None:
            wait()
            code = s.action.snippet()
            if code:
                out.append(f"    {code}")
            if s.timeout_ms > 0:
                out.append(f"    pros::delay({s.timeout_ms});")
    wait()
    out.append("}")
    return "\n".join(out) + "\n"
