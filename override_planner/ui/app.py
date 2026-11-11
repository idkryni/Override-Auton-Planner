"""Main application window."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional

from ..export import FORMATS
from ..model import io
from ..model.actions import Action
from ..model.collision import find_collisions
from ..model.path import FIELD_SIZE, Route
from ..model.profile import build_timeline
from .dialogs import ExportDialog, RobotDialog
from .field_canvas import FieldCanvas
from .inspector import Inspector
from .playback import Playback

UNDO_LIMIT = 200


class App:
    def __init__(self, root: tk.Tk, route_file: Optional[str] = None) -> None:
        self.root = root
        self.layout = io.load_layout()
        self.elements = io.load_elements()
        self.robot = io.load_robot()
        self.route = Route()
        self.selected: Optional[int] = None
        self.path: Optional[Path] = None
        self.dirty = False
        self.undo_stack: list[Route] = []
        self.redo_stack: list[Route] = []
        self.export_origin = "center"
        self.timeline = build_timeline(self.route, self.robot)
        self.collisions: list = []

        self.mode = tk.StringVar(value="add")
        self.show_objects = tk.BooleanVar(value=True)
        self.show_footprints = tk.BooleanVar(value=True)
        self.check_collisions = tk.BooleanVar(value=True)
        self.snap_enabled = tk.BooleanVar(value=True)
        self.snap_size = tk.DoubleVar(value=0.5)

        root.title("Override Auton Planner")
        self._build_menu()
        self._build_layout()
        self._bind_keys()
        if route_file:
            self._open_path(Path(route_file))
        self.changed(mark_dirty=False)

    # ---- layout ----------------------------------------------------------------
    def _build_layout(self) -> None:
        root = self.root
        toolbar = ttk.Frame(root, padding=(6, 4))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Mode:").pack(side="left")
        ttk.Radiobutton(toolbar, text="Add points (A)", value="add", variable=self.mode).pack(side="left")
        ttk.Radiobutton(toolbar, text="Select / move (S)", value="select", variable=self.mode).pack(side="left")
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Checkbutton(toolbar, text="Snap", variable=self.snap_enabled).pack(side="left")
        ttk.Combobox(toolbar, textvariable=self.snap_size, values=[0.25, 0.5, 1, 2, 3, 6], width=4,
                     state="readonly").pack(side="left")
        ttk.Label(toolbar, text="in").pack(side="left")
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(toolbar, text="Mirror red↔blue", command=self.mirror).pack(side="left")
        ttk.Button(toolbar, text="Export…", command=lambda: self.export(next(iter(FORMATS)))).pack(side="left", padx=4)
        ttk.Label(toolbar, text="Shift-drag a point to set heading · right-click for options",
                  foreground="#666").pack(side="right")

        body = ttk.Frame(root)
        body.pack(fill="both", expand=True)
        size = max(520, min(820, root.winfo_screenheight() - 200))
        self.canvas = FieldCanvas(body, self, size)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inspector = Inspector(body, self)
        self.inspector.pack(side="right", fill="y")
        self.playback = Playback(root, self)
        self.playback.pack(fill="x")
        self.status = ttk.Label(root, text="", anchor="w", padding=(6, 2), font=("TkFixedFont", 9))
        self.status.pack(fill="x")

    def _build_menu(self) -> None:
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="New", accelerator="Ctrl+N", command=self.new)
        f.add_command(label="Open…", accelerator="Ctrl+O", command=self.open)
        f.add_command(label="Save", accelerator="Ctrl+S", command=self.save)
        f.add_command(label="Save As…", command=self.save_as)
        f.add_separator()
        f.add_command(label="Quit", command=self.quit)
        m.add_cascade(label="File", menu=f)
        e = tk.Menu(m, tearoff=0)
        e.add_command(label="Undo", accelerator="Ctrl+Z", command=self.undo)
        e.add_command(label="Redo", accelerator="Ctrl+Y", command=self.redo)
        e.add_separator()
        e.add_command(label="Delete waypoint", accelerator="Del", command=lambda: self.delete_waypoint(self.selected))
        e.add_command(label="Mirror red ↔ blue", command=self.mirror)
        e.add_command(label="Clear route", command=self.clear)
        starts = tk.Menu(e, tearoff=0)
        half = self.robot.length / 2
        for label, x, y, h in (
            ("Red – left wall, near", half, 35.1, 90), ("Red – left wall, far", half, 105.3, 90),
            ("Blue – right wall, near", FIELD_SIZE - half, 35.1, 270),
            ("Blue – right wall, far", FIELD_SIZE - half, 105.3, 270),
        ):
            starts.add_command(label=label, command=lambda x=x, y=y, h=h: self.set_start(x, y, h))
        e.add_cascade(label="Set start pose", menu=starts)
        m.add_cascade(label="Edit", menu=e)
        v = tk.Menu(m, tearoff=0)
        v.add_checkbutton(label="Scoring objects (H2H layout)", variable=self.show_objects, command=self.redraw)
        v.add_checkbutton(label="Robot footprints", variable=self.show_footprints, command=self.redraw)
        v.add_checkbutton(label="Collision warnings", variable=self.check_collisions, command=self.changed)
        m.add_cascade(label="View", menu=v)
        r = tk.Menu(m, tearoff=0)
        r.add_command(label="Robot settings…", command=lambda: RobotDialog(self))
        m.add_cascade(label="Robot", menu=r)
        x = tk.Menu(m, tearoff=0)
        for name in FORMATS:
            x.add_command(label=name + "…", command=lambda n=name: self.export(n))
        m.add_cascade(label="Export", menu=x)
        self.root.config(menu=m)

    def _bind_keys(self) -> None:
        r = self.root
        r.bind("<Control-z>", lambda _e: self.undo())
        r.bind("<Control-y>", lambda _e: self.redo())
        r.bind("<Control-Z>", lambda _e: self.redo())
        r.bind("<Control-s>", lambda _e: self.save())
        r.bind("<Control-o>", lambda _e: self.open())
        r.bind("<Control-n>", lambda _e: self.new())
        c = self.canvas
        c.bind("<Delete>", lambda _e: self.delete_waypoint(self.selected))
        c.bind("<BackSpace>", lambda _e: self.delete_waypoint(self.selected))
        c.bind("a", lambda _e: self.mode.set("add"))
        c.bind("s", lambda _e: self.mode.set("select"))
        c.bind("<space>", lambda _e: self.playback.toggle())
        for key, (dx, dy) in {"<Left>": (-1, 0), "<Right>": (1, 0), "<Up>": (0, 1), "<Down>": (0, -1)}.items():
            c.bind(key, lambda _e, dx=dx, dy=dy: self.nudge(dx, dy))
        r.protocol("WM_DELETE_WINDOW", self.quit)

    # ---- state ------------------------------------------------------------------
    def snap(self, x: float, y: float) -> tuple[float, float]:
        if not self.snap_enabled.get():
            return x, y
        s = float(self.snap_size.get()) or 0.5
        return round(x / s) * s, round(y / s) * s

    def snapshot(self) -> None:
        self.undo_stack.append(self.route.clone())
        del self.undo_stack[:-UNDO_LIMIT]
        self.redo_stack.clear()

    def changed(self, light: bool = False, mark_dirty: bool = True) -> None:
        if self.selected is not None and self.selected >= len(self.route.waypoints):
            self.selected = len(self.route.waypoints) - 1 if self.route.waypoints else None
        self.timeline = build_timeline(self.route, self.robot)
        if not light:
            self.collisions = (find_collisions(self.timeline, self.layout, self.robot)
                               if self.check_collisions.get() else [])
        if mark_dirty:
            self.dirty = True
        self._update_title()
        self.inspector.refresh()
        self.playback.update_view()  # redraws canvas

    def redraw(self) -> None:
        self.canvas.redraw()

    def select(self, i: Optional[int]) -> None:
        self.selected = i
        self.inspector.refresh()
        self.canvas.redraw()

    def set_status(self, msg: str) -> None:
        self.status.configure(text=msg)

    def _update_title(self) -> None:
        name = self.path.name if self.path else "untitled"
        self.root.title(f"Override Auton Planner — {name}{' *' if self.dirty else ''}")

    # ---- edit operations ------------------------------------------------------
    def add_at(self, x: float, y: float) -> None:
        self.snapshot()
        self.selected = self.route.add(x, y)
        self.changed()

    def insert_after(self, i: Optional[int]) -> None:
        wps = self.route.waypoints
        if i is None or not wps:
            return
        if i + 1 < len(wps):
            x, y = (wps[i].x + wps[i + 1].x) / 2, (wps[i].y + wps[i + 1].y) / 2
        else:
            x, y = min(FIELD_SIZE, wps[i].x + 12), wps[i].y
        self.snapshot()
        self.selected = self.route.add(x, y, i + 1)
        self.changed()

    def delete_waypoint(self, i: Optional[int]) -> None:
        if i is None or i >= len(self.route.waypoints):
            return
        self.snapshot()
        self.route.remove(i)
        self.selected = min(i, len(self.route.waypoints) - 1) if self.route.waypoints else None
        self.changed()

    def reorder(self, d: int) -> None:
        i = self.selected
        wps = self.route.waypoints
        if i is None or not (0 <= i + d < len(wps)):
            return
        self.snapshot()
        wps[i], wps[i + d] = wps[i + d], wps[i]
        w0 = wps[0]
        w0.curve, w0.reverse, w0.c1, w0.c2 = False, False, None, None
        if w0.heading is None:
            w0.heading = 0.0
        self.selected = i + d
        self.changed()

    def nudge(self, dx: float, dy: float) -> None:
        if self.selected is None:
            return
        step = float(self.snap_size.get()) if self.snap_enabled.get() else 0.5
        wp = self.route.waypoints[self.selected]
        self.snapshot()
        self.route.move(self.selected, wp.x + dx * step, wp.y + dy * step)
        self.changed()

    def toggle_flag(self, i: int, name: str) -> None:
        if i <= 0:
            return
        self.snapshot()
        wp = self.route.waypoints[i]
        if name == "curve":
            self.route.set_curve(i, not wp.curve)
        elif name == "reverse":
            wp.reverse = not wp.reverse
            if wp.curve:
                wp.c1, wp.c2 = self.route.default_controls(i)
        self.changed()

    def reset_handles(self, i: Optional[int]) -> None:
        if i is None or i == 0 or not self.route.waypoints[i].curve:
            return
        self.snapshot()
        wp = self.route.waypoints[i]
        wp.c1, wp.c2 = self.route.default_controls(i)
        self.changed()

    def set_heading(self, i: int, h: Optional[float]) -> None:
        if i == 0 and h is None:
            h = 0.0
        self.snapshot()
        self.route.set_heading(i, h)
        self.changed()

    def ask_heading(self, i: int) -> None:
        cur = self.route.heading_at(i) or 0.0
        h = simpledialog.askfloat("Heading", "Heading in degrees (0 = far wall, 90 = right):",
                                  initialvalue=round(cur, 1), parent=self.root)
        if h is not None:
            self.set_heading(i, h)

    def add_action(self, i: int, key: str) -> None:
        self.snapshot()
        self.route.waypoints[i].actions.append(Action.make(key))
        self.changed()

    def set_start(self, x: float, y: float, h: float) -> None:
        self.snapshot()
        if not self.route.waypoints:
            self.route.add(x, y)
        else:
            self.route.move(0, x, y)
        self.route.waypoints[0].heading = h
        self.selected = 0
        self.changed()

    def mirror(self) -> None:
        self.snapshot()
        self.route.mirror(FIELD_SIZE)
        self.changed()

    def clear(self) -> None:
        if self.route.waypoints and messagebox.askyesno("Clear route", "Remove all waypoints?", parent=self.root):
            self.snapshot()
            self.route.waypoints.clear()
            self.selected = None
            self.changed()

    def undo(self) -> None:
        if self.undo_stack:
            self.redo_stack.append(self.route.clone())
            self.route = self.undo_stack.pop()
            self.changed()

    def redo(self) -> None:
        if self.redo_stack:
            self.undo_stack.append(self.route.clone())
            self.route = self.redo_stack.pop()
            self.changed()

    # ---- files -------------------------------------------------------------------
    def _confirm_discard(self) -> bool:
        if not self.dirty or not self.route.waypoints:
            return True
        ans = messagebox.askyesnocancel("Unsaved changes", "Save changes first?", parent=self.root)
        if ans is None:
            return False
        if ans:
            return self.save()
        return True

    def new(self) -> None:
        if not self._confirm_discard():
            return
        self.route = Route()
        self.path = None
        self.selected = None
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.changed(mark_dirty=False)
        self.dirty = False
        self._update_title()

    def open(self) -> None:
        if not self._confirm_discard():
            return
        p = filedialog.askopenfilename(parent=self.root, filetypes=[("Route", "*.json"), ("All", "*")])
        if p:
            self._open_path(Path(p))

    def _open_path(self, p: Path) -> None:
        try:
            route, robot = io.load_route(p)
        except Exception as exc:  # noqa: BLE001 - show any parse error to the user
            messagebox.showerror("Open route", f"Could not open {p}:\n{exc}", parent=self.root)
            return
        self.route = route
        if robot is not None:
            self.robot = robot
        self.path = p
        self.selected = None
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.changed(mark_dirty=False)
        self.dirty = False
        self._update_title()

    def save(self) -> bool:
        if self.path is None:
            return self.save_as()
        io.save_route(self.route, self.robot, self.path)
        self.dirty = False
        self._update_title()
        self.set_status(f"Saved {self.path}")
        return True

    def save_as(self) -> bool:
        p = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json",
                                         initialfile=f"{self.route.name}.json",
                                         filetypes=[("Route", "*.json")])
        if not p:
            return False
        self.path = Path(p)
        return self.save()

    def export(self, fmt: str) -> None:
        ExportDialog(self, fmt)

    def quit(self) -> None:
        if self._confirm_discard():
            self.root.destroy()
