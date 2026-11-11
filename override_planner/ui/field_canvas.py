"""Field drawing + mouse interaction."""
from __future__ import annotations

import math
import tkinter as tk
from typing import TYPE_CHECKING, Optional

from ..model.actions import SHORT
from ..model.geometry import dist, heading_to, heading_vec, rotated_rect
from ..model.path import FIELD_SIZE

if TYPE_CHECKING:
    from .app import App

COLORS = {
    "field": "#8f8f8f", "seam": "#7a7a7a", "wall": "#cfcfcf",
    "red": "#d0262f", "blue": "#1f6fd1", "yellow": "#f4d21f", "white": "#f4f4f4",
    "neutral": "#1d1d1d", "cup": "#3a3a3a",
    "path_fwd": "#2ee86a", "path_rev": "#ff9a1f", "wp": "#ffffff", "start": "#2ee86a",
    "sel": "#ffe600", "handle": "#d07bff", "ghost": "#00e5ff", "foot": "#e8e8e8", "hit": "#ff2d2d",
}
WP_R = 7       # waypoint radius px
HANDLE_R = 5


class FieldCanvas(tk.Canvas):
    def __init__(self, master: tk.Misc, app: "App", size_px: int = 760) -> None:
        super().__init__(master, width=size_px, height=size_px, bg="#2b2b2b", highlightthickness=0)
        self.app = app
        self.size_px = size_px
        self.margin = 18
        self.scale = (size_px - 2 * self.margin) / FIELD_SIZE
        self._drag: Optional[tuple[str, int]] = None  # (kind, index) kind: wp | c1 | c2 | heading
        self._drag_snapshotted = False
        self.ghost_pose: Optional[tuple[float, float, float]] = None
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<Shift-ButtonPress-1>", lambda e: self._on_press(e, shift=True))
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<ButtonPress-3>", self._on_context)
        self.bind("<ButtonPress-2>", self._on_context)  # macOS right click
        self.bind("<Motion>", self._on_motion)
        self.bind("<Configure>", self._on_resize)

    # ---- coordinate transforms ---------------------------------------------
    def to_px(self, x: float, y: float) -> tuple[float, float]:
        return self.margin + x * self.scale, self.margin + (FIELD_SIZE - y) * self.scale

    def to_field(self, px: float, py: float) -> tuple[float, float]:
        return (px - self.margin) / self.scale, FIELD_SIZE - (py - self.margin) / self.scale

    def _pts(self, pts) -> list[float]:
        out: list[float] = []
        for x, y in pts:
            out.extend(self.to_px(x, y))
        return out

    def _on_resize(self, e: tk.Event) -> None:
        s = min(e.width, e.height)
        if s < 200:
            return
        self.scale = (s - 2 * self.margin) / FIELD_SIZE
        self.redraw()

    # ---- drawing -------------------------------------------------------------
    def redraw(self) -> None:
        self.delete("all")
        self._draw_field()
        self._draw_route()
        self._draw_ghost()

    def _circle(self, x: float, y: float, r_in: float, **kw) -> None:
        px, py = self.to_px(x, y)
        r = r_in * self.scale
        self.create_oval(px - r, py - r, px + r, py + r, **kw)

    def _draw_field(self) -> None:
        lay = self.app.layout
        el = self.app.elements
        s = self.scale
        x0, y0 = self.to_px(0, FIELD_SIZE)
        x1, y1 = self.to_px(FIELD_SIZE, 0)
        wall = 1.5 * s
        self.create_rectangle(x0 - wall, y0 - wall, x1 + wall, y1 + wall, fill=COLORS["wall"], outline="")
        self.create_rectangle(x0, y0, x1, y1, fill=COLORS["field"], outline="#555")
        for v in lay.get("tile_lines", []):
            self.create_line(*self._pts([(v, 0), (v, FIELD_SIZE)]), fill=COLORS["seam"], width=1)
            self.create_line(*self._pts([(0, v), (FIELD_SIZE, v)]), fill=COLORS["seam"], width=1)
        # tape
        for t in lay.get("tape", []):
            col = COLORS.get(t.get("color", "white"), t.get("color", "white"))
            pts = t["points"]
            if t.get("double"):
                (ax, ay), (bx, by) = pts[0], pts[-1]
                h = heading_to((ax, ay), (bx, by))
                ox, oy = heading_vec(h + 90, 1.25)
                for sg in (1, -1):
                    self.create_line(*self._pts([(ax + sg * ox, ay + sg * oy), (bx + sg * ox, by + sg * oy)]),
                                     fill=col, width=max(1, 0.9 * s))
            else:
                self.create_line(*self._pts(pts), fill=col, width=max(1, 1.6 * s), capstyle="projecting",
                                 joinstyle="miter")
        # toggles
        tg = el["toggle"]
        for t in lay.get("toggles", []):
            L, P = tg["length"], tg["profile"]
            if t["orientation"] == "horizontal":
                a, b = (t["x"] - L / 2, t["y"] - P / 2), (t["x"] + L / 2, t["y"] + P / 2)
            else:
                a, b = (t["x"] - P / 2, t["y"] - L / 2), (t["x"] + P / 2, t["y"] + L / 2)
            self.create_rectangle(*self._pts([a, b]), fill=COLORS["yellow"], outline="#7a6a00", width=1)
        # loaders
        ld = el["loader"]
        for l in lay.get("loaders", []):
            depth, w = ld["depth"], ld["base_width"]
            if l["wall"] == "left":
                a, b, cx = (0, l["y"] - w / 2), (depth, l["y"] + w / 2), depth / 2
            else:
                a, b, cx = (FIELD_SIZE - depth, l["y"] - w / 2), (FIELD_SIZE, l["y"] + w / 2), FIELD_SIZE - depth / 2
            col = COLORS.get(l["color"], "#999")
            self.create_rectangle(*self._pts([a, b]), fill="#2a2a2a", outline=col, width=2)
            self._circle(cx, l["y"], ld["tube_diameter"] / 2, outline=col, width=1)
        # goals
        g = el["goal"]
        hw, ch = g["base_width"] / 2, 1.15
        for goal in lay.get("goals", []):
            gx, gy = goal["x"], goal["y"]
            octo = [(gx - hw + ch, gy + hw), (gx + hw - ch, gy + hw), (gx + hw, gy + hw - ch), (gx + hw, gy - hw + ch),
                    (gx + hw - ch, gy - hw), (gx - hw + ch, gy - hw), (gx - hw, gy - hw + ch), (gx - hw, gy + hw - ch)]
            col = COLORS.get(goal["color"], COLORS["neutral"])
            self.create_polygon(*self._pts(octo), fill=col, outline="#000", width=1)
            self._circle(gx, gy, g["hole_diameter"] / 2, fill="#555", outline="#000")
            if goal.get("type") == "tall":
                self._circle(gx, gy, g["hole_diameter"] / 2 + 0.6, outline="#bbb", width=1)
            if goal.get("preload") and self.app.show_objects.get():
                self._circle(gx, gy, 0.8, fill=COLORS.get(goal["preload"], "#ff0"), outline="#000")
        if self.app.show_objects.get():
            self._draw_objects()

    def _pin(self, x: float, y: float, color: str) -> None:
        pin = self.app.elements["pin"]
        self._circle(x, y, pin["base_diameter"] / 2, fill=COLORS.get(color, color), outline="#111")
        self._circle(x, y, pin["top_diameter"] / 2, fill="#ffffff" if color != "yellow" else "#fff6b0", outline="")

    def _lying_pin(self, x: float, y: float, heading: float, color: str) -> None:
        pin = self.app.elements["pin"]
        poly = rotated_rect(x, y, heading, pin["mid_diameter"], pin["height"])
        self.create_polygon(*self._pts(poly), fill=COLORS.get(color, color), outline="#111")

    def _draw_objects(self) -> None:
        lay = self.app.layout
        cup = self.app.elements["cup"]
        for o in lay.get("objects", []):
            if o["kind"] == "cup":
                self._circle(o["x"], o["y"], cup["rim_diameter"] / 2, fill=COLORS["cup"], outline="#000", width=2)
                self._circle(o["x"], o["y"], cup["waist_diameter"] / 2 * 0.6, outline="#777")
            elif o["kind"] == "pin":
                self._pin(o["x"], o["y"], o.get("color", "yellow"))
            elif o["kind"] == "pin_lying":
                self._lying_pin(o["x"], o["y"], o.get("angle", 0), o.get("color", "yellow"))
        cl = lay.get("pin_cross_layout", {"offset": 4.6, "center": "yellow"})
        off = cl.get("offset", 4.6)
        for c in lay.get("pin_crosses", []):
            for d, hd in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
                vx, vy = heading_vec(hd, off)
                self._lying_pin(c["x"] + vx, c["y"] + vy, hd, cl.get(d, "yellow"))
            self._pin(c["x"], c["y"], cl.get("center", "yellow"))

    def _robot_poly(self, x: float, y: float, h: float, **kw) -> None:
        r = self.app.robot
        poly = rotated_rect(x, y, h, r.width, r.length)
        self.create_polygon(*self._pts(poly), **kw)
        fx, fy = heading_vec(h, r.length / 2)
        rx, ry = heading_vec(h + 90, r.width / 2)
        self.create_line(*self._pts([(x + fx + rx, y + fy + ry), (x + fx - rx, y + fy - ry)]),
                         fill=kw.get("outline", "#fff"), width=4)

    def _draw_route(self) -> None:
        app = self.app
        route = app.route
        wps = route.waypoints
        sel = app.selected
        # robot footprints
        if app.show_footprints.get():
            for i in range(len(wps)):
                h = route.heading_at(i) or 0.0
                self._robot_poly(wps[i].x, wps[i].y, h, outline=COLORS["sel"] if i == sel else COLORS["foot"],
                                 fill="", dash=() if i == sel else (3, 3), width=1)
        # segments
        for i in range(1, len(wps)):
            wp = wps[i]
            pts = route.segment_points(i, 1.0)
            col = COLORS["path_rev"] if wp.reverse else COLORS["path_fwd"]
            self.create_line(*self._pts(pts), fill=col, width=3, smooth=False)
            # direction arrow at middle
            mid = len(pts) // 2 if len(pts) > 2 else None
            if mid is not None:
                a, b = pts[mid - 1], pts[mid]
            else:
                a = (pts[0][0] + (pts[1][0] - pts[0][0]) * 0.48, pts[0][1] + (pts[1][1] - pts[0][1]) * 0.48)
                b = (pts[0][0] + (pts[1][0] - pts[0][0]) * 0.52, pts[0][1] + (pts[1][1] - pts[0][1]) * 0.52)
            if dist(a, b) > 1e-6:
                self.create_line(*self._pts([a, b]), fill=col, width=3, arrow="last", arrowshape=(12, 14, 6))
            if wp.curve and wp.c1 is not None and wp.c2 is not None:
                for anchor, c, kind in ((wps[i - 1].pos, wp.c1, "c1"), (wp.pos, wp.c2, "c2")):
                    self.create_line(*self._pts([anchor, c]), fill=COLORS["handle"], dash=(4, 3))
                    px, py = self.to_px(*c)
                    self.create_rectangle(px - HANDLE_R, py - HANDLE_R, px + HANDLE_R, py + HANDLE_R,
                                          fill=COLORS["handle"], outline="#000")
        # collision markers
        if app.check_collisions.get():
            for _, x, y, what in app.collisions:
                px, py = self.to_px(x, y)
                self.create_line(px - 6, py - 6, px + 6, py + 6, fill=COLORS["hit"], width=3)
                self.create_line(px - 6, py + 6, px + 6, py - 6, fill=COLORS["hit"], width=3)
        # waypoints
        for i, wp in enumerate(wps):
            px, py = self.to_px(wp.x, wp.y)
            h = route.heading_at(i) or 0.0
            hx, hy = heading_vec(h, 7)
            explicit = wp.heading is not None or i == 0
            self.create_line(*self._pts([wp.pos, (wp.x + hx, wp.y + hy)]), fill="#ffffff" if explicit else "#bbbbbb",
                             width=2 if explicit else 1, arrow="last", dash=() if explicit else (2, 2))
            fill = COLORS["start"] if i == 0 else COLORS["wp"]
            self.create_oval(px - WP_R, py - WP_R, px + WP_R, py + WP_R, fill=fill,
                             outline=COLORS["sel"] if i == sel else "#000", width=3 if i == sel else 1)
            self.create_text(px, py, text=str(i), font=("TkDefaultFont", 7, "bold"), fill="#000")
            if wp.actions:
                label = " ".join(SHORT.get(a.type, "?") for a in wp.actions)
                tid = self.create_text(px + WP_R + 4, py - WP_R - 4, text=label, anchor="sw",
                                       font=("TkDefaultFont", 8, "bold"), fill="#000")
                bb = self.bbox(tid)
                rid = self.create_rectangle(bb[0] - 2, bb[1] - 1, bb[2] + 2, bb[3] + 1, fill="#ffe680", outline="#000")
                self.tag_lower(rid, tid)

    def _draw_ghost(self) -> None:
        if self.ghost_pose is None:
            return
        x, y, h = self.ghost_pose
        self._robot_poly(x, y, h, outline=COLORS["ghost"], fill=COLORS["ghost"], stipple="gray25", width=2)

    # ---- hit testing ------------------------------------------------------------
    def hit(self, px: float, py: float) -> Optional[tuple[str, int]]:
        wps = self.app.route.waypoints
        for i in range(len(wps) - 1, 0, -1):
            wp = wps[i]
            if wp.curve:
                for kind, c in (("c2", wp.c2), ("c1", wp.c1)):
                    if c is not None:
                        cx, cy = self.to_px(*c)
                        if abs(cx - px) <= HANDLE_R + 2 and abs(cy - py) <= HANDLE_R + 2:
                            return kind, i
        for i in range(len(wps) - 1, -1, -1):
            cx, cy = self.to_px(wps[i].x, wps[i].y)
            if math.hypot(cx - px, cy - py) <= WP_R + 3:
                return "wp", i
        return None

    # ---- mouse --------------------------------------------------------------------
    def _on_press(self, e: tk.Event, shift: bool = False) -> None:
        self.focus_set()
        app = self.app
        h = self.hit(e.x, e.y)
        self._drag_snapshotted = False
        if h is None:
            if app.mode.get() == "add":
                x, y = app.snap(*self.to_field(e.x, e.y))
                app.snapshot()
                idx = app.route.add(x, y)
                app.select(idx)
                app.changed()
                self._drag = ("wp", idx)
                self._drag_snapshotted = True
            else:
                app.select(None)
                self._drag = None
            return
        kind, i = h
        if kind == "wp":
            app.select(i)
            self._drag = ("heading", i) if shift else ("wp", i)
        else:
            app.select(i)
            self._drag = (kind, i)

    def _on_drag(self, e: tk.Event) -> None:
        if self._drag is None:
            return
        app = self.app
        kind, i = self._drag
        if not self._drag_snapshotted:
            app.snapshot()
            self._drag_snapshotted = True
        x, y = self.to_field(e.x, e.y)
        wp = app.route.waypoints[i]
        if kind == "wp":
            x, y = app.snap(x, y)
            x = max(0.0, min(FIELD_SIZE, x))
            y = max(0.0, min(FIELD_SIZE, y))
            app.route.move(i, x, y)
        elif kind == "heading":
            if dist((x, y), wp.pos) > 0.5:
                hd = heading_to(wp.pos, (x, y))
                if app.snap_enabled.get():
                    hd = round(hd / 5.0) * 5.0 % 360
                app.route.set_heading(i, hd)
        elif kind == "c1":
            wp.c1 = (x, y)
        elif kind == "c2":
            wp.c2 = (x, y)
            # pose heading follows the end tangent of the curve
            wp.heading = app.route.curve_end_heading(i)
        app.changed(light=True)

    def _on_release(self, _e: tk.Event) -> None:
        if self._drag is not None and self._drag_snapshotted:
            self.app.changed()
        self._drag = None

    def _on_motion(self, e: tk.Event) -> None:
        x, y = self.to_field(e.x, e.y)
        if not (0 <= x <= FIELD_SIZE and 0 <= y <= FIELD_SIZE):
            self.app.set_status("")
            return
        c = FIELD_SIZE / 2
        msg = f"field ({x:6.2f}, {y:6.2f}) in   center-origin ({x - c:6.2f}, {y - c:6.2f})"
        for gi, g in enumerate(self.app.layout.get("goals", [])):
            if dist((x, y), (g["x"], g["y"])) < 3.5:
                ht = self.app.elements["goal"]["heights"].get(g.get("type", ""), "?")
                msg += f"   | goal {gi + 1}: {g['color']} {g.get('type', '')} ({ht} in tall)"
        self.app.set_status(msg)

    def _on_context(self, e: tk.Event) -> None:
        h = self.hit(e.x, e.y)
        app = self.app
        menu = tk.Menu(self, tearoff=0)
        if h is not None:
            i = h[1]
            app.select(i)
            wp = app.route.waypoints[i]
            if i > 0:
                menu.add_command(label="Curve (bezier)" + ("  ✓" if wp.curve else ""),
                                 command=lambda: app.toggle_flag(i, "curve"))
                menu.add_command(label="Reverse into point" + ("  ✓" if wp.reverse else ""),
                                 command=lambda: app.toggle_flag(i, "reverse"))
                menu.add_command(label="Clear end heading", command=lambda: app.set_heading(i, None))
            menu.add_command(label="Set heading…", command=lambda: app.ask_heading(i))
            sub = tk.Menu(menu, tearoff=0)
            from ..model.actions import ACTION_TYPES
            for key, (label, _, _) in ACTION_TYPES.items():
                sub.add_command(label=label, command=lambda k=key: app.add_action(i, k))
            menu.add_cascade(label="Add action", menu=sub)
            menu.add_separator()
            menu.add_command(label="Insert waypoint after", command=lambda: app.insert_after(i))
            menu.add_command(label="Delete waypoint", command=lambda: app.delete_waypoint(i))
        else:
            x, y = app.snap(*self.to_field(e.x, e.y))
            menu.add_command(label=f"Add waypoint here ({x:.1f}, {y:.1f})", command=lambda: app.add_at(x, y))
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()
