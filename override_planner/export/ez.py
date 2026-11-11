"""EZ-Template 3.x (PROS) exporter using odometry motions."""
from __future__ import annotations

from ..model.path import Route
from ..model.profile import RobotConfig, build_timeline
from .common import ExportOptions, build_steps, fmt, header


def _spd(const: str, pct: float) -> str:
    return const if pct >= 100 else f"{const} * {fmt(pct, 0)} / 100"


def export(route: Route, robot: RobotConfig, opts: ExportOptions | None = None) -> str:
    opts = opts or ExportOptions()
    tl = build_timeline(route, robot)
    out = header(route, robot, opts, tl, "EZ-Template")
    out.append("// Uses DRIVE_SPEED / TURN_SPEED constants from the EZ-Template example project.")
    out.append(f"void {opts.function_name}() {{")
    for s in build_steps(route, robot, opts, tl):
        d = "rev" if s.reverse else "fwd"
        if s.kind == "set_pose":
            out.append(f"    chassis.odom_xyt_set({fmt(s.x)}_in, {fmt(s.y)}_in, {fmt(s.h)}_deg);")
        elif s.kind == "comment":
            out.append(f"    // {s.text}")
        elif s.kind == "turn_point":
            out.append(f"    chassis.pid_turn_set({{{fmt(s.x)}_in, {fmt(s.y)}_in}}, {d}, TURN_SPEED);")
            out.append("    chassis.pid_wait();")
        elif s.kind == "turn_heading":
            out.append(f"    chassis.pid_turn_set({fmt(s.h)}_deg, TURN_SPEED);")
            out.append("    chassis.pid_wait();")
        elif s.kind == "drive":
            out.append(f"    chassis.pid_odom_set({{{{{fmt(s.x)}_in, {fmt(s.y)}_in}}, {d}, "
                       f"{_spd('DRIVE_SPEED', s.speed)}}}, true);")
            out.append("    chassis.pid_wait();")
        elif s.kind == "curve":
            out.append(f"    chassis.pid_odom_set({{{{{fmt(s.x)}_in, {fmt(s.y)}_in, {fmt(s.h)}_deg}}, {d}, "
                       f"{_spd('DRIVE_SPEED', s.speed)}}}, true);")
            out.append("    chassis.pid_wait();")
        elif s.kind == "action" and s.action is not None:
            code = s.action.snippet()
            if code:
                out.append(f"    {code}")
            if s.timeout_ms > 0:
                out.append(f"    pros::delay({s.timeout_ms});")
    out.append("}")
    return "\n".join(out) + "\n"
