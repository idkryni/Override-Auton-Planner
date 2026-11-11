"""JAR-Template (VEXcode V5 C++) exporter."""
from __future__ import annotations

from ..model.path import Route
from ..model.profile import RobotConfig, build_timeline
from .common import ExportOptions, build_steps, fmt, header


def export(route: Route, robot: RobotConfig, opts: ExportOptions | None = None) -> str:
    opts = opts or ExportOptions()
    tl = build_timeline(route, robot)
    out = header(route, robot, opts, tl, "JAR-Template")
    out.append("// Reverse moves use turn_to_point(x, y, 180) + drive_distance(-d).")
    out.append(f"void {opts.function_name}() {{")
    speed = 100.0
    for s in build_steps(route, robot, opts, tl):
        if s.kind in ("drive", "curve") and s.speed != speed:
            out.append(f"    chassis.drive_max_voltage = {fmt(12 * s.speed / 100, 2)};")
            speed = s.speed
        if s.kind == "set_pose":
            out.append(f"    chassis.set_coordinates({fmt(s.x)}, {fmt(s.y)}, {fmt(s.h)});")
        elif s.kind == "comment":
            out.append(f"    // {s.text}")
        elif s.kind == "turn_point":
            extra = ", 180" if s.reverse else ""
            out.append(f"    chassis.turn_to_point({fmt(s.x)}, {fmt(s.y)}{extra});")
        elif s.kind == "turn_heading":
            out.append(f"    chassis.turn_to_angle({fmt(s.h)});")
        elif s.kind == "drive":
            if s.reverse:
                out.append(f"    chassis.drive_distance({fmt(-s.distance)});")
            else:
                out.append(f"    chassis.drive_to_point({fmt(s.x)}, {fmt(s.y)});")
        elif s.kind == "curve":
            if s.reverse:
                out.append("    // reverse curve: approximated as a straight reverse move")
                out.append(f"    chassis.turn_to_point({fmt(s.x)}, {fmt(s.y)}, 180);")
                out.append(f"    chassis.drive_distance({fmt(-s.distance)});")
                out.append(f"    chassis.turn_to_angle({fmt(s.h)});")
            else:
                out.append(f"    chassis.drive_to_pose({fmt(s.x)}, {fmt(s.y)}, {fmt(s.h)});")
        elif s.kind == "action" and s.action is not None:
            code = s.action.snippet()
            if code:
                out.append(f"    {code}")
            if s.timeout_ms > 0:
                out.append(f"    wait({s.timeout_ms}, msec);")
    if speed != 100.0:
        out.append("    chassis.drive_max_voltage = 12;")
    out.append("}")
    return "\n".join(out) + "\n"
