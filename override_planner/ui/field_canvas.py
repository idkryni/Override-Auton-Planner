"""Field drawing + mouse interaction."""
from __future__ import annotations

import math
import tkinter as tk
from typing import TYPE_CHECKING, Optional

from ..model.actions import ACTION_TYPES, SHORT
from ..model.geometry import dist, heading_to, heading_vec, rotated_rect
from ..model.path import FIELD_SIZE
from .theme import FIELD

if TYPE_CHECKING:
    from .app import App

WP_R = 8       # waypoint radius px
HANDLE_R = 5


class FieldCanvas(tk.Canvas):
    def __init__(self, master: tk.Misc, app: "App") -> None:
        super().__init__(master, width=760, height=760, bg=app.theme.c["stage"], highlightthickness=0, bd=0)
        self.app = app
        self.margin = 28
        self.ox = self.oy = float(self.margin)
        self.scale = (760 - 2 * self.margin) / FIELD_SIZE
        self._drag: Optional[tuple[str, int]] = None  # (kind, index) kind: wp | c1 | c2 | heading
        self._drag_snapshotted = False
        self._hover: Optional[tuple[str, int]] = None
        self.ghost_pose: Optional[tuple[float, float, float]] = None
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<Shift-ButtonPress-1>", lambda e: self._on_press(e, shift=True))
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<ButtonPress-3>", self._on_context)
        self.bind("<ButtonPress-2>", self._on_context)  # macOS right click
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda _e: self.app.set_status(""))
        self.bind("<Configure>", self._on_resize)

    # ---- coordinate transforms ---------------------------------------------
    def to_px(self, x: float, y: float) -> tuple[float, float]:
        return self.ox + x * self.scale, self.oy + (FIELD_SIZE - y) * self.scale

    def to_field(self, px: float, py: float) -> tuple[float, float]:
        return (px - self.ox) / self.scale, FIELD_SIZE - (py - self.oy) / self.scale

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
        side = FIELD_SIZE * self.scale
        self.ox = (e.width - side) / 2
        self.oy = (e.height - side) / 2
        self.redraw()

    # ---- drawing -------------------------------------------------------------
    def redraw(self) -> None:
        self.configure(bg=self.app.theme.c["stage"])
        self.delete("all")
        self._draw_field()
        self._draw_route()
        self._draw_ghost()
        self._draw_empty_state()

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
        wall = 1.6 * s
        self.create_rectangle(x0 - wall, y0 - wall, x1 + wall, y1 + wall, fill=FIELD["wall"],
                              outline=FIELD["wall_edge"])
        self.create_rectangle(x0, y0, x1, y1, fill=FIELD["tile"], outline=FIELD["wall_edge"])
        for v in lay.get("tile_lines", []):
            self.create_line(*self._pts([(v, 0), (v, FIELD_SIZE)]), fill=FIELD["seam"])
            self.create_line(*self._pts([(0, v), (FIELD_SIZE, v)]), fill=FIELD["seam"])
        for t in lay.get("tape", []):
            col = FIELD.get(t.get("color", "white"), t.get("color", "white"))
            pts = t["points"]
            if t.get("double"):
                (ax, ay), (bx, by) = pts[0], pts[-1]
                ox, oy = heading_vec(heading_to((ax, ay), (bx, by)) + 90, 1.25)
                for sg in (1, -1):
                    self.create_line(*self._pts([(ax + sg * ox, ay + sg * oy), (bx + sg * ox, by + sg * oy)]),
                                     fill=col, width=max(1, 0.9 * s))
            else:
                self.create_line(*self._pts(pts), fill=col, width=max(1, 1.6 * s), capstyle="projecting",
                                 joinstyle="miter")
        tg = el["toggle"]
        for t in lay.get("toggles", []):
            L, P = tg["length"], tg["profile"]
            if t["orientation"] == "horizontal":
                a, b = (t["x"] - L / 2, t["y"] - P / 2), (t["x"] + L / 2, t["y"] + P / 2)
            else:
                a, b = (t["x"] - P / 2, t["y"] - L / 2), (t["x"] + P / 2, t["y"] + L / 2)
            self.create_rectangle(*self._pts([a, b]), fill=FIELD["yellow"], outline=FIELD["ink"])
        ld = el["loader"]
        for l in lay.get("loaders", []):
            depth, w = ld["depth"], ld["base_width"]
            if l["wall"] == "left":
                a, b, cx = (0, l["y"] - w / 2), (depth, l["y"] + w / 2), depth / 2
            else:
                a, b, cx = (FIELD_SIZE - depth, l["y"] - w / 2), (FIELD_SIZE, l["y"] + w / 2), FIELD_SIZE - depth / 2
            col = FIELD.get(l["color"], "#999")
            self.create_rectangle(*self._pts([a, b]), fill=FIELD["neutral"], outline=col, width=2)
            self._circle(cx, l["y"], ld["tube_diameter"] / 2, outline=col)
        g = el["goal"]
        hw, ch = g["base_width"] / 2, 1.15
        for goal in lay.get("goals", []):
            gx, gy = goal["x"], goal["y"]
            octo = [(gx - hw + ch, gy + hw), (gx + hw - ch, gy + hw), (gx + hw, gy + hw - ch), (gx + hw, gy - hw + ch),
                    (gx + hw - ch, gy - hw), (gx - hw + ch, gy - hw), (gx - hw, gy - hw + ch), (gx - hw, gy + hw - ch)]
            self.create_polygon(*self._pts(octo), fill=FIELD.get(goal["color"], FIELD["neutral"]),
                                outline=FIELD["ink"])
            self._circle(gx, gy, g["hole_diameter"] / 2, fill="#4a4e53", outline=FIELD["ink"])
            if goal.get("type") == "tall":
                self._circle(gx, gy, g["hole_diameter"] / 2 + 0.6, outline="#b9bcc0")
            if goal.get("preload") and self.app.show_objects.get():
                self._circle(gx, gy, 0.8, fill=FIELD.get(goal["preload"], "#ff0"), outline=FIELD["ink"])
        if self.app.show_objects.get():
            self._draw_objects()

    def _pin(self, x: float, y: float, color: str) -> None:
        pin = self.app.elements["pin"]
        self._circle(x, y, pin["base_diameter"] / 2, fill=FIELD.get(color, color), outline=FIELD["ink"])
        self._circle(x, y, pin["top_diameter"] / 2, fill="#fbf3c2" if color == "yellow" else "#f3f4f5", outline="")

    def _lying_pin(self, x: float, y: float, heading: float, color: str) -> None:
        pin = self.app.elements["pin"]
        poly = rotated_rect(x, y, heading, pin["mid_diameter"], pin["height"])
        self.create_polygon(*self._pts(poly), fill=FIELD.get(color, color), outline=FIELD["ink"])

    def _draw_objects(self) -> None:
        lay = self.app.layout
        cup = self.app.elements["cup"]
        for o in lay.get("objects", []):
            if o["kind"] == "cup":
                self._circle(o["x"], o["y"], cup["rim_diameter"] / 2, fill=FIELD["cup"], outline=FIELD["ink"], width=2)
                self._circle(o["x"], o["y"], cup["waist_diameter"] / 2 * 0.6, outline="#6d7177")
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

    def _robot_poly(self, x: float, y: float, h: float, outline: str, **kw) -> None:
        r = self.app.robot
        poly = rotated_rect(x, y, h, r.width, r.length)
        self.create_polygon(*self._pts(poly), outline=outline, **kw)
        fx, fy = heading_vec(h, r.length / 2)
        rx, ry = heading_vec(h + 90, r.width / 2)
        self.create_line(*self._pts([(x + fx + rx, y + fy + ry), (x + fx - rx, y + fy - ry)]), fill=outline, width=3)

    def _line(self, pts, color: str, width: int = 3, **kw) -> None:
        coords = self._pts(pts)
        self.create_line(*coords, fill=FIELD["underlay"], width=width + 3, capstyle="round", joinstyle="round")
        self.create_line(*coords, fill=color, width=width, capstyle="round", joinstyle="round", **kw)

    def _pill(self, px: float, py: float, text: str, anchor: str = "sw") -> None:
        c = self.app.theme.c
        tid = self.create_text(px, py, text=text, anchor=anchor, font=self.app.theme.f["mono_b"], fill=c["text"])
        bb = self.bbox(tid)
        rid = self.create_rectangle(bb[0] - 4, bb[1] - 2, bb[2] + 4, bb[3] + 2, fill=c["surface"],
                                    outline=c["border_strong"])
        self.tag_lower(rid, tid)

    def _draw_route(self) -> None:
        app = self.app
        accent = FIELD["path"]
        route = app.route
        wps = route.waypoints
        sel = app.selected
        if app.show_footprints.get():
            for i in range(len(wps)):
                if i == sel:
                    continue
                self._robot_poly(wps[i].x, wps[i].y, route.heading_at(i) or 0.0, FIELD["foot"], fill="",
                                 dash=(3, 4), width=1)
        if sel is not None and sel < len(wps):
            self._robot_poly(wps[sel].x, wps[sel].y, route.heading_at(sel) or 0.0, accent, fill="", width=2)
        for i in range(1, len(wps)):
            wp = wps[i]
            pts = route.segment_points(i, 1.0)
            col = FIELD["path_rev"] if wp.reverse else accent
            self._line(pts, col, 3, dash=(8, 5) if wp.reverse else ())
            mid = len(pts) // 2 if len(pts) > 2 else None
            if mid is not None:
                a, b = pts[mid - 1], pts[mid]
            else:
                a = (pts[0][0] + (pts[1][0] - pts[0][0]) * 0.47, pts[0][1] + (pts[1][1] - pts[0][1]) * 0.47)
                b = (pts[0][0] + (pts[1][0] - pts[0][0]) * 0.53, pts[0][1] + (pts[1][1] - pts[0][1]) * 0.53)
            if dist(a, b) > 1e-6:
                self.create_line(*self._pts([a, b]), fill=col, width=3, arrow="last", arrowshape=(12, 14, 6))
            if wp.curve and wp.c1 is not None and wp.c2 is not None:
                for anchor, c in ((wps[i - 1].pos, wp.c1), (wp.pos, wp.c2)):
                    self.create_line(*self._pts([anchor, c]), fill=FIELD["marker"], dash=(2, 3))
                    px, py = self.to_px(*c)
                    self.create_rectangle(px - HANDLE_R, py - HANDLE_R, px + HANDLE_R, py + HANDLE_R,
                                          fill=FIELD["marker"], outline=FIELD["ink"], width=2)
        if app.check_collisions.get():
            for _, x, y, _what in app.collisions:
                px, py = self.to_px(x, y)
                for d in (1, -1):
                    self.create_line(px - 6, py - 6 * d, px + 6, py + 6 * d, fill=FIELD["ink"], width=5)
                    self.create_line(px - 6, py - 6 * d, px + 6, py + 6 * d, fill=FIELD["hit"], width=3)
        for i, wp in enumerate(wps):
            px, py = self.to_px(wp.x, wp.y)
            h = route.heading_at(i) or 0.0
            hx, hy = heading_vec(h, 8)
            explicit = wp.heading is not None or i == 0
            self.create_line(*self._pts([wp.pos, (wp.x + hx, wp.y + hy)]), fill=FIELD["ink"], width=4, arrow="last")
            self.create_line(*self._pts([wp.pos, (wp.x + hx, wp.y + hy)]),
                             fill=FIELD["marker"] if explicit else "#c5c8cc", width=2, arrow="last",
                             dash=() if explicit else (2, 2))
            is_sel = i == sel
            hover = self._hover is not None and self._hover == ("wp", i)
            r = WP_R + (2 if is_sel or hover else 0)
            if is_sel:
                self.create_oval(px - r - 4, py - r - 4, px + r + 4, py + r + 4, outline=accent, width=2)
            fill = accent if i == 0 or is_sel else FIELD["marker"]
            self.create_oval(px - r, py - r, px + r, py + r, fill=fill, outline=FIELD["ink"], width=2)
            self.create_text(px, py, text=str(i), font=self.app.theme.f["mono_b"], fill=FIELD["ink"])
            if wp.actions:
                self._pill(px + r + 4, py - r - 2, " ".join(SHORT.get(a.type, "?") for a in wp.actions))

    def _draw_ghost(self) -> None:
        if self.ghost_pose is None:
            return
        x, y, h = self.ghost_pose
        self._robot_poly(x, y, h, FIELD["path"], fill=FIELD["path"], stipple="gray25", width=2)

    def _draw_empty_state(self) -> None:
        if self.app.route.waypoints:
            return
        c = self.app.theme.c
        cx, cy = self.to_px(FIELD_SIZE / 2, FIELD_SIZE / 2)
        lines = ("Click the field to place the start pose",
                 "Shift-drag a point to aim it. Right-click for actions.")
        t1 = self.create_text(cx, cy - 10, text=lines[0], font=self.app.theme.f["title"], fill=c["text"])
        t2 = self.create_text(cx, cy + 14, text=lines[1], font=self.app.theme.f["body"], fill=c["muted"])
        b1, b2 = self.bbox(t1), self.bbox(t2)
        rid = self.create_rectangle(min(b1[0], b2[0]) - 18, b1[1] - 14, max(b1[2], b2[2]) + 18, b2[3] + 14,
                                    fill=c["surface"], outline=c["border_strong"])
        self.tag_lower(rid, t1)

    # ---- hit testing ------------------------------------------------------------
    def hit(self, px: float, py: float) -> Optional[tuple[str, int]]:
        wps = self.app.route.waypoints
        for i in range(len(wps) - 1, 0, -1):
            wp = wps[i]
            if wp.curve:
                for kind, c in (("c2", wp.c2), ("c1", wp.c1)):
                    if c is not None:
                        cx, cy = self.to_px(*c)
                        if abs(cx - px) <= HANDLE_R + 3 and abs(cy - py) <= HANDLE_R + 3:
                            return kind, i
        for i in range(len(wps) - 1, -1, -1):
            cx, cy = self.to_px(wps[i].x, wps[i].y)
            if math.hypot(cx - px, cy - py) <= WP_R + 4:
                return "wp", i
        return None

    # ---- mouse --------------------------------------------------------------------
    def _on_press(self, e: tk.Event, shift: bool = False) -> None:
        self.focus_set()
        app = self.app
        h = self.hit(e.x, e.y)
        self._drag_snapshotted = False
        if h is None:
            x, y = self.to_field(e.x, e.y)
            inside = 0 <= x <= FIELD_SIZE and 0 <= y <= FIELD_SIZE
            if app.mode.get() == "add" and inside:
                x, y = app.snap(x, y)
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
        app.select(i)
        self._drag = ("heading", i) if (shift and kind == "wp") else (kind, i)

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
            app.route.move(i, max(0.0, min(FIELD_SIZE, x)), max(0.0, min(FIELD_SIZE, y)))
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
            wp.heading = app.route.curve_end_heading(i)
        app.changed(light=True)

    def _on_release(self, _e: tk.Event) -> None:
        if self._drag is not None and self._drag_snapshotted:
            self.app.changed()
        self._drag = None

    def _on_motion(self, e: tk.Event) -> None:
        hv = self.hit(e.x, e.y)
        if hv != self._hover:
            self._hover = hv
            self.configure(cursor="hand2" if hv else ("crosshair" if self.app.mode.get() == "add" else ""))
            self.redraw()
        x, y = self.to_field(e.x, e.y)
        if not (0 <= x <= FIELD_SIZE and 0 <= y <= FIELD_SIZE):
            self.app.set_status("")
            return
        c = FIELD_SIZE / 2
        msg = f"x {x:6.2f}  y {y:6.2f} in    from center  x {x - c:6.2f}  y {y - c:6.2f}"
        for gi, g in enumerate(self.app.layout.get("goals", [])):
            if dist((x, y), (g["x"], g["y"])) < 3.5:
                ht = self.app.elements["goal"]["heights"].get(g.get("type", ""), "?")
                msg += f"    goal {gi + 1}: {g['color']} {g.get('type', '')}, {ht} in tall"
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
                self._menu_vars = [tk.BooleanVar(value=wp.curve), tk.BooleanVar(value=wp.reverse)]
                menu.add_checkbutton(label="Curved segment", variable=self._menu_vars[0],
                                     command=lambda: app.toggle_flag(i, "curve"))
                menu.add_checkbutton(label="Drive in reverse", variable=self._menu_vars[1],
                                     command=lambda: app.toggle_flag(i, "reverse"))
                menu.add_command(label="Clear end heading", command=lambda: app.set_heading(i, None))
            menu.add_command(label="Set heading...", command=lambda: app.ask_heading(i))
            sub = tk.Menu(menu, tearoff=0)
            for key, (label, _, _) in ACTION_TYPES.items():
                sub.add_command(label=label, command=lambda k=key: app.add_action(i, k))
            menu.add_cascade(label="Add action", menu=sub)
            menu.add_separator()
            menu.add_command(label="Insert point after", command=lambda: app.insert_after(i))
            menu.add_command(label="Delete point", command=lambda: app.delete_waypoint(i))
        else:
            x, y = app.snap(*self.to_field(e.x, e.y))
            menu.add_command(label=f"Add point at {x:.1f}, {y:.1f}", command=lambda: app.add_at(x, y))
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()
