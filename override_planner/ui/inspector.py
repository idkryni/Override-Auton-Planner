"""Sidebar: time budget, path table, selected point, actions."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Callable

from ..model.actions import ACTION_TYPES, SHORT, Action

if TYPE_CHECKING:
    from .app import App

LIMITS = {"Match (15 s)": 15.0, "Skills (60 s)": 60.0, "Custom (30 s)": 30.0}
PAD = 16


class Scrollable(ttk.Frame):
    """Vertical scroll container for the sidebar body."""

    def __init__(self, master: tk.Misc, app: "App") -> None:
        super().__init__(master, style="Side.TFrame")
        self.app = app
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=app.theme.c["surface"])
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas, style="Side.TFrame")
        self._win = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y")
        self.body.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        for w in (self.canvas, self.body):
            w.bind("<Enter>", lambda _e: self._wheel(True))
            w.bind("<Leave>", lambda _e: self._wheel(False))

    def _scroll(self, e: tk.Event) -> None:
        step = -1 if e.delta > 0 else 1
        self.canvas.yview_scroll(step * (3 if abs(e.delta) >= 120 else 1), "units")

    def _wheel(self, on: bool) -> None:
        if on:
            self.bind_all("<MouseWheel>", self._scroll)
            self.bind_all("<Button-4>", lambda _e: self.canvas.yview_scroll(-3, "units"))
            self.bind_all("<Button-5>", lambda _e: self.canvas.yview_scroll(3, "units"))
        else:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.unbind_all(seq)

    def retheme(self) -> None:
        self.canvas.configure(bg=self.app.theme.c["surface"])


def field(parent: tk.Misc, label: str, var: tk.StringVar, on_commit: Callable[[], None], width: int = 8,
          mono: bool = True) -> ttk.Frame:
    """Label above input; commits on Enter or focus out."""
    f = ttk.Frame(parent, style="Side.TFrame")
    ttk.Label(f, text=label, style="Field.TLabel").pack(anchor="w", pady=(0, 3))
    e = ttk.Entry(f, textvariable=var, width=width, style="Mono.TEntry" if mono else "TEntry")
    e.pack(fill="x")
    e.bind("<Return>", lambda _e: on_commit())
    e.bind("<FocusOut>", lambda _e: on_commit())
    return f


class Inspector(ttk.Frame):
    def __init__(self, master: tk.Misc, app: "App") -> None:
        super().__init__(master, style="Side.TFrame", width=372)
        self.pack_propagate(False)
        self.app = app
        self._loading = False

        # ---- time budget (fixed at top) -------------------------------------
        top = ttk.Frame(self, style="Side.TFrame", padding=(PAD, PAD, PAD, 12))
        top.pack(fill="x")
        row = ttk.Frame(top, style="Side.TFrame")
        row.pack(fill="x")
        ttk.Label(row, text="Estimated time", style="Muted.TLabel").pack(side="left")
        self.limit_var = tk.StringVar(value=next(iter(LIMITS)))
        lc = ttk.Combobox(row, textvariable=self.limit_var, values=list(LIMITS), state="readonly", width=13)
        lc.pack(side="right")
        lc.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        trow = ttk.Frame(top, style="Side.TFrame")
        trow.pack(fill="x", pady=(4, 0))
        self.time_lbl = ttk.Label(trow, text="0.00 s", style="BigOk.TLabel")
        self.time_lbl.pack(side="left")
        self.left_lbl = ttk.Label(trow, text="", style="Mono.TLabel")
        self.left_lbl.pack(side="left", padx=(10, 0), pady=(10, 0))
        self.seg_lbl = ttk.Label(top, text="", style="Mono.TLabel")
        self.seg_lbl.pack(anchor="w", pady=(2, 0))
        self.warn_lbl = ttk.Label(top, text="", style="Warn.TLabel", justify="left", wraplength=330)
        ttk.Separator(self).pack(fill="x")

        self.scroll = Scrollable(self, app)
        self.scroll.pack(fill="both", expand=True)
        body = self.scroll.body

        # ---- path -------------------------------------------------------------
        sec = ttk.Frame(body, style="Side.TFrame", padding=(PAD, 14, PAD, 4))
        sec.pack(fill="x")
        head = ttk.Frame(sec, style="Side.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="Path", style="Section.TLabel").pack(side="left")
        self.count_lbl = ttk.Label(head, text="", style="Muted.TLabel")
        self.count_lbl.pack(side="left", padx=8)
        ttk.Label(sec, text="Route name", style="Field.TLabel").pack(anchor="w", pady=(10, 3))
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(sec, textvariable=self.name_var)
        self.name_entry.pack(fill="x")
        self.name_entry.bind("<Return>", lambda _e: self._apply_name())
        self.name_entry.bind("<FocusOut>", lambda _e: self._apply_name())

        cols = ("i", "x", "y", "h", "t", "act")
        self.tree = ttk.Treeview(sec, columns=cols, show="headings", height=7, selectmode="browse")
        for cid, txt, w, anc in (("i", "#", 30, "e"), ("x", "X", 52, "e"), ("y", "Y", 52, "e"),
                                 ("h", "HDG", 44, "e"), ("t", "ARRIVE", 58, "e"), ("act", "DO", 80, "w")):
            self.tree.heading(cid, text=txt, anchor=anc)
            self.tree.column(cid, width=w, minwidth=w, anchor=anc, stretch=cid == "act")
        self.tree.pack(fill="x", pady=(12, 0))
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree_empty = ttk.Label(sec, text="No points yet. Click the field to add the start pose.",
                                    style="Muted.TLabel", wraplength=320)
        tb = self.path_toolbar = ttk.Frame(sec, style="Side.TFrame")
        tb.pack(fill="x", pady=(6, 0))
        self.path_btns = []
        for txt, cmd in (("Up", lambda: app.reorder(-1)), ("Down", lambda: app.reorder(1)),
                         ("Insert after", lambda: app.insert_after(app.selected)),
                         ("Delete", lambda: app.delete_waypoint(app.selected))):
            b = ttk.Button(tb, text=txt, style="Ghost.TButton", command=cmd)
            b.pack(side="left")
            self.path_btns.append(b)

        ttk.Separator(body).pack(fill="x", padx=PAD, pady=(10, 0))

        # ---- selected point -------------------------------------------------------
        sec = ttk.Frame(body, style="Side.TFrame", padding=(PAD, 14, PAD, 4))
        sec.pack(fill="x")
        phead = ttk.Frame(sec, style="Side.TFrame")
        phead.pack(fill="x")
        self.point_title = ttk.Label(phead, text="Point", style="Section.TLabel")
        self.point_title.pack(side="left")
        self.reset_btn = ttk.Button(phead, text="Reset curve", style="Ghost.TButton",
                                    command=lambda: app.reset_handles(app.selected))
        self.point_empty = ttk.Label(sec, text="Select a point on the field or in the table to edit it.",
                                     style="Muted.TLabel", wraplength=320)
        self.point_body = ttk.Frame(sec, style="Side.TFrame")
        pb = self.point_body
        self.x_var, self.y_var, self.h_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        grid = ttk.Frame(pb, style="Side.TFrame")
        grid.pack(fill="x", pady=(10, 0))
        for col, (lbl, var, cb) in enumerate((("X (in)", self.x_var, self._apply_xy),
                                              ("Y (in)", self.y_var, self._apply_xy),
                                              ("Heading (deg)", self.h_var, self._apply_heading))):
            field(grid, lbl, var, cb).grid(row=0, column=col, sticky="we", padx=(0 if col == 0 else 8, 0))
            grid.columnconfigure(col, weight=1)
        self.h_set, self.rev_var, self.curve_var = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
        chips = ttk.Frame(pb, style="Side.TFrame")
        chips.pack(fill="x", pady=(12, 0))
        self.h_chk = ttk.Checkbutton(chips, text="Turn to heading", variable=self.h_set, style="Chip.Toolbutton",
                                     command=self._apply_heading)
        self.rev_chk = ttk.Checkbutton(chips, text="Reverse", variable=self.rev_var, style="Chip.Toolbutton",
                                       command=lambda: self._apply_flag("reverse", self.rev_var))
        self.curve_chk = ttk.Checkbutton(chips, text="Curve", variable=self.curve_var, style="Chip.Toolbutton",
                                         command=lambda: self._apply_flag("curve", self.curve_var))
        for i, w in enumerate((self.h_chk, self.rev_chk, self.curve_chk)):
            w.pack(side="left", padx=(0 if i == 0 else 6, 0))
        sp = ttk.Frame(pb, style="Side.TFrame")
        sp.pack(fill="x", pady=(14, 0))
        top_row = ttk.Frame(sp, style="Side.TFrame")
        top_row.pack(fill="x")
        ttk.Label(top_row, text="Max speed into this point", style="Field.TLabel").pack(side="left")
        self.speed_lbl = ttk.Label(top_row, text="100%", style="Mono.TLabel")
        self.speed_lbl.pack(side="right")
        self.speed_var = tk.DoubleVar(value=100)
        self.speed_scale = ttk.Scale(sp, from_=10, to=100, variable=self.speed_var, style="Side.Horizontal.TScale",
                                     command=self._on_speed_drag)
        self.speed_scale.pack(fill="x", pady=(6, 0))
        self.speed_scale.bind("<ButtonRelease-1>", lambda _e: self._apply_speed())

        ttk.Separator(body).pack(fill="x", padx=PAD, pady=(14, 0))

        # ---- actions ------------------------------------------------------------------
        sec = ttk.Frame(body, style="Side.TFrame", padding=(PAD, 14, PAD, PAD))
        sec.pack(fill="x")
        ttk.Label(sec, text="Actions", style="Section.TLabel").pack(anchor="w")
        ttk.Label(sec, text="Run in order after the robot arrives.", style="Muted.TLabel").pack(anchor="w", pady=(2, 0))
        self.act_body = ttk.Frame(sec, style="Side.TFrame")
        sec = self.act_body
        self.acts = ttk.Treeview(sec, columns=("a", "d", "c"), show="headings", height=4, selectmode="browse")
        for cid, txt, w, anc in (("a", "ACTION", 120, "w"), ("d", "SEC", 44, "e"), ("c", "CODE", 120, "w")):
            self.acts.heading(cid, text=txt, anchor=anc)
            self.acts.column(cid, width=w, minwidth=w, anchor=anc, stretch=cid == "c")
        self.acts.pack(fill="x", pady=(10, 0))
        self.acts.bind("<<TreeviewSelect>>", self._on_action_select)
        form = ttk.Frame(sec, style="Side.TFrame")
        form.pack(fill="x", pady=(10, 0))
        self._label_to_key = {v[0]: k for k, v in ACTION_TYPES.items()}
        self.act_type = tk.StringVar(value=ACTION_TYPES["intake_on"][0])
        tf = ttk.Frame(form, style="Side.TFrame")
        tf.grid(row=0, column=0, sticky="we")
        ttk.Label(tf, text="Type", style="Field.TLabel").pack(anchor="w", pady=(0, 3))
        cb = ttk.Combobox(tf, textvariable=self.act_type, values=[v[0] for v in ACTION_TYPES.values()],
                          state="readonly")
        cb.pack(fill="x")
        cb.bind("<<ComboboxSelected>>", self._on_type_change)
        self.act_dur = tk.StringVar(value="0")
        field(form, "Seconds", self.act_dur, lambda: None, width=6).grid(row=0, column=1, sticky="we", padx=(8, 0))
        form.columnconfigure(0, weight=1)
        self.act_code = tk.StringVar(value=ACTION_TYPES["intake_on"][2])
        field(sec, "Code", self.act_code, lambda: None).pack(fill="x", pady=(8, 0))
        ab = ttk.Frame(sec, style="Side.TFrame")
        ab.pack(fill="x", pady=(10, 0))
        self.act_btns = [ttk.Button(ab, text="Add action", command=self._add_action)]
        self.act_btns[0].pack(side="left")
        for txt, cmd in (("Update", self._update_action), ("Remove", self._remove_action),
                         ("Up", lambda: self._move_action(-1)), ("Down", lambda: self._move_action(1))):
            b = ttk.Button(ab, text=txt, style="Ghost.TButton", command=cmd)
            b.pack(side="left", padx=(4, 0))
            self.act_btns.append(b)

    # ---- refresh -------------------------------------------------------------
    @property
    def limit(self) -> float:
        return LIMITS.get(self.limit_var.get(), 15.0)

    def retheme(self) -> None:
        self.scroll.retheme()

    def refresh(self) -> None:
        app = self.app
        route = app.route
        sel = app.selected
        self._loading = True
        try:
            if self.focus_get() is not self.name_entry:
                self.name_var.set(route.name)
            self._refresh_time()
            self._refresh_table(sel)
            self._refresh_point(sel)
        finally:
            self._loading = False

    def _refresh_time(self) -> None:
        app = self.app
        tl = app.timeline
        over = tl.total > self.limit
        self.time_lbl.configure(text=f"{tl.total:.2f} s", style="BigWarn.TLabel" if over else "BigOk.TLabel")
        spare = self.limit - tl.total
        self.left_lbl.configure(text=f"{abs(spare):.2f} s {'over' if over else 'spare'} of {self.limit:.0f} s")
        drive = sum(p.duration for p in tl.phases if p.kind == "drive")
        turn = sum(p.duration for p in tl.phases if p.kind == "turn")
        act = sum(p.duration for p in tl.phases if p.kind == "action")
        dist_total = sum(p.length for p in tl.phases if p.kind == "drive")
        self.seg_lbl.configure(text=f"drive {drive:.2f}  turn {turn:.2f}  act {act:.2f}  {dist_total:.0f} in")
        if app.check_collisions.get() and app.collisions:
            lines = [f"Contact with {what} at {t:.2f} s" for t, _x, _y, what in app.collisions[:3]]
            if len(app.collisions) > 3:
                lines.append(f"{len(app.collisions) - 3} more contacts")
            self.warn_lbl.configure(text="\n".join(lines))
            self.warn_lbl.pack(anchor="w", pady=(6, 0))
        else:
            self.warn_lbl.pack_forget()

    def _refresh_table(self, sel: int | None) -> None:
        route, tl = self.app.route, self.app.timeline
        n = len(route.waypoints)
        self.count_lbl.configure(text=f"{n} point{'s' if n != 1 else ''}")
        self.tree.delete(*self.tree.get_children())
        for i, wp in enumerate(route.waypoints):
            h = route.heading_at(i) or 0.0
            t = tl.arrival[i] if i < len(tl.arrival) else 0.0
            tags = ("R " if wp.reverse else "") + ("C " if wp.curve else "")
            acts = tags + " ".join(SHORT.get(a.type, "?") for a in wp.actions)
            self.tree.insert("", "end", iid=str(i), values=(i, f"{wp.x:.1f}", f"{wp.y:.1f}", f"{h:.0f}",
                                                            f"{t:.2f}", acts))
        if n == 0:
            self.tree.pack_forget()
            self.tree_empty.pack(anchor="w", pady=(12, 0), before=self.path_toolbar)
        else:
            self.tree_empty.pack_forget()
            self.tree.pack(fill="x", pady=(12, 0), before=self.path_toolbar)
        if sel is not None and sel < n:
            self.tree.selection_set(str(sel))
            self.tree.see(str(sel))
        for b in self.path_btns:
            b.state(["!disabled"] if sel is not None else ["disabled"])

    def _refresh_point(self, sel: int | None) -> None:
        route = self.app.route
        if sel is None or sel >= len(route.waypoints):
            self.point_title.configure(text="Point")
            self.reset_btn.pack_forget()
            self.point_body.pack_forget()
            self.point_empty.pack(anchor="w", pady=(6, 0))
            self.act_body.pack_forget()
            return
        self.point_empty.pack_forget()
        self.point_body.pack(fill="x")
        self.act_body.pack(fill="x")
        wp = route.waypoints[sel]
        first = sel == 0
        self.point_title.configure(text="Start pose" if first else f"Point {sel}")
        self.x_var.set(f"{wp.x:.2f}")
        self.y_var.set(f"{wp.y:.2f}")
        self.h_var.set(f"{route.heading_at(sel) or 0.0:.1f}")
        self.h_set.set(wp.heading is not None or first or wp.curve)
        self.rev_var.set(wp.reverse)
        self.curve_var.set(wp.curve)
        self.speed_var.set(wp.speed)
        self.speed_lbl.configure(text=f"{wp.speed:.0f}%")
        for w in (self.rev_chk, self.curve_chk):
            w.state(["disabled"] if first else ["!disabled"])
        self.h_chk.state(["disabled"] if first or wp.curve else ["!disabled"])
        if wp.curve:
            self.reset_btn.pack(side="right")
        else:
            self.reset_btn.pack_forget()
        self.speed_scale.state(["disabled"] if first else ["!disabled"])
        self.acts.delete(*self.acts.get_children())
        for k, a in enumerate(wp.actions):
            self.acts.insert("", "end", iid=str(k), values=(a.label, f"{a.duration:g}", a.snippet()))
        for b in self.act_btns:
            b.state(["!disabled"])

    # ---- apply edits -----------------------------------------------------------
    def _apply_name(self) -> None:
        name = self.name_var.get().strip() or "auton"
        if name != self.app.route.name:
            self.app.snapshot()
            self.app.route.name = name
            self.app.changed()

    def _on_tree_select(self, _e: tk.Event) -> None:
        cur = self.tree.selection()
        if cur and not self._loading and int(cur[0]) != self.app.selected:
            self.app.select(int(cur[0]))

    def _apply_xy(self) -> None:
        app = self.app
        if self._loading or app.selected is None:
            return
        try:
            x, y = float(self.x_var.get()), float(self.y_var.get())
        except ValueError:
            return
        wp = app.route.waypoints[app.selected]
        if abs(x - wp.x) < 1e-6 and abs(y - wp.y) < 1e-6:
            return
        app.snapshot()
        app.route.move(app.selected, x, y)
        app.changed()

    def _apply_heading(self) -> None:
        app = self.app
        if self._loading or app.selected is None:
            return
        i = app.selected
        wp = app.route.waypoints[i]
        explicit = self.h_set.get() or i == 0 or wp.curve
        try:
            h = float(self.h_var.get())
        except ValueError:
            return
        if not explicit and wp.heading is None:
            return
        if explicit and wp.heading is not None and abs(h - wp.heading) < 1e-6:
            return
        app.set_heading(i, h if explicit else None)

    def _apply_flag(self, name: str, var: tk.BooleanVar) -> None:
        app = self.app
        if self._loading or app.selected is None:
            return
        if bool(getattr(app.route.waypoints[app.selected], name)) != var.get():
            app.toggle_flag(app.selected, name)

    def _on_speed_drag(self, _v: str) -> None:
        v = round(float(self.speed_var.get()) / 5) * 5
        self.speed_lbl.configure(text=f"{v:.0f}%")

    def _apply_speed(self) -> None:
        app = self.app
        if self._loading or app.selected is None:
            return
        wp = app.route.waypoints[app.selected]
        v = float(round(float(self.speed_var.get()) / 5) * 5)
        if v != wp.speed:
            app.snapshot()
            wp.speed = v
            app.changed()

    # ---- actions ------------------------------------------------------------------
    def _on_type_change(self, _e: tk.Event) -> None:
        key = self._label_to_key[self.act_type.get()]
        _, dur, code = ACTION_TYPES[key]
        self.act_dur.set(f"{dur:g}")
        self.act_code.set(code)

    def _form_action(self) -> Action | None:
        key = self._label_to_key.get(self.act_type.get())
        if key is None:
            return None
        try:
            dur = max(0.0, float(self.act_dur.get() or 0))
        except ValueError:
            dur = ACTION_TYPES[key][1]
        return Action(key, dur, self.act_code.get().strip())

    def _sel_action(self) -> int | None:
        cur = self.acts.selection()
        return int(cur[0]) if cur else None

    def _on_action_select(self, _e: tk.Event) -> None:
        app = self.app
        k = self._sel_action()
        if k is None or app.selected is None or self._loading:
            return
        a = app.route.waypoints[app.selected].actions[k]
        self.act_type.set(a.label)
        self.act_dur.set(f"{a.duration:g}")
        self.act_code.set(a.snippet())

    def _add_action(self) -> None:
        app = self.app
        a = self._form_action()
        if app.selected is None or a is None:
            return
        app.snapshot()
        app.route.waypoints[app.selected].actions.append(a)
        app.changed()

    def _update_action(self) -> None:
        app = self.app
        k, a = self._sel_action(), self._form_action()
        if app.selected is None or k is None or a is None:
            return
        app.snapshot()
        app.route.waypoints[app.selected].actions[k] = a
        app.changed()
        self.acts.selection_set(str(k))

    def _remove_action(self) -> None:
        app = self.app
        k = self._sel_action()
        if app.selected is None or k is None:
            return
        app.snapshot()
        del app.route.waypoints[app.selected].actions[k]
        app.changed()

    def _move_action(self, d: int) -> None:
        app = self.app
        k = self._sel_action()
        if app.selected is None or k is None:
            return
        acts = app.route.waypoints[app.selected].actions
        j = k + d
        if 0 <= j < len(acts):
            app.snapshot()
            acts[k], acts[j] = acts[j], acts[k]
            app.changed()
            self.acts.selection_set(str(j))
