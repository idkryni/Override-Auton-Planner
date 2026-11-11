"""Generic JSON / CSV exports for custom parsers."""
from __future__ import annotations

import csv
import io
import json

from ..model.path import Route
from ..model.profile import RobotConfig, build_timeline
from .common import ExportOptions, build_steps, to_out


def export_json(route: Route, robot: RobotConfig, opts: ExportOptions | None = None) -> str:
    opts = opts or ExportOptions()
    tl = build_timeline(route, robot)
    wps = []
    for i, w in enumerate(route.waypoints):
        x, y = to_out(w.x, w.y, opts)
        d = w.to_dict()
        d.update({"index": i, "x": round(x, 3), "y": round(y, 3),
                  "robot_heading": round(route.heading_at(i) or 0.0, 2),
                  "arrival_time": round(tl.arrival[i], 3), "finish_time": round(tl.finish[i], 3)})
        if w.c1 is not None:
            d["c1"] = [round(v, 3) for v in to_out(*w.c1, opts)]
        if w.c2 is not None:
            d["c2"] = [round(v, 3) for v in to_out(*w.c2, opts)]
        if i > 0:
            d["path"] = [[round(v, 3) for v in to_out(px, py, opts)] for px, py in route.segment_points(i, 2.0)]
        wps.append(d)
    steps = []
    for s in build_steps(route, robot, opts, tl):
        if s.kind == "comment":
            continue
        e = {"kind": s.kind, "waypoint": s.wp}
        if s.kind in ("set_pose", "turn_point", "drive", "curve"):
            e.update(x=round(s.x, 3), y=round(s.y, 3))
        if s.kind in ("set_pose", "turn_heading", "curve", "turn_point"):
            e["heading"] = round(s.h, 2)
        if s.kind in ("turn_point", "drive", "curve"):
            e["reverse"] = s.reverse
        if s.kind in ("drive", "curve"):
            e["speed"] = s.speed
            e["distance"] = round(s.distance, 3)
        if s.kind == "action" and s.action is not None:
            e["action"] = s.action.to_dict()
        if s.kind != "set_pose":
            e["timeout_ms"] = s.timeout_ms
        steps.append(e)
    doc = {
        "name": route.name, "notes": route.notes,
        "units": "in", "origin": opts.origin, "heading": "0 = far wall, clockwise positive",
        "estimated_time": round(tl.total, 3), "robot": robot.to_dict(),
        "waypoints": wps, "steps": steps,
    }
    return json.dumps(doc, indent=2) + "\n"


def export_csv(route: Route, robot: RobotConfig, opts: ExportOptions | None = None) -> str:
    opts = opts or ExportOptions()
    tl = build_timeline(route, robot)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["index", "x", "y", "heading", "reverse", "curve", "c1x", "c1y", "c2x", "c2y",
                "speed", "arrival_time", "actions"])
    for i, wp in enumerate(route.waypoints):
        x, y = to_out(wp.x, wp.y, opts)
        c1 = to_out(*wp.c1, opts) if wp.c1 is not None and wp.curve else ("", "")
        c2 = to_out(*wp.c2, opts) if wp.c2 is not None and wp.curve else ("", "")
        r = lambda v: round(v, 3) if isinstance(v, float) else v  # noqa: E731
        w.writerow([i, r(x), r(y), round(route.heading_at(i) or 0.0, 2), int(wp.reverse), int(wp.curve),
                    r(c1[0]), r(c1[1]), r(c2[0]), r(c2[1]), wp.speed, round(tl.arrival[i], 3),
                    ";".join(f"{a.type}:{a.duration:g}" for a in wp.actions)])
    return buf.getvalue()
