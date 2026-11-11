"""Side panel: route list, waypoint properties, actions, timing."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ..model.actions import ACTION_TYPES, SHORT, Action

if TYPE_CHECKING:
    from .app import App

LIMITS = {"Match auton (15 s)": 15.0, "Skills auton (60 s)": 60.0, "Custom (30 s)": 30.0}


class Inspector(ttk.Frame):
    def __init__(self, master: tk.Misc, app: "App") -> None:
        super().__init__(master, padding=6)
        self.app = app
        self._loading = False

        # route
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Route").pack(side="left")
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(top, textvariable=self.name_var, width=22)
        self.name_entry.pack(side="left", padx=4, fill="x", expand=True)
        self.name_entry.bind("<Return>", lambda _e: self._apply_name())
        self.name_entry.bind("<FocusOut>", lambda _e: self._apply_name())

        # waypoint list
        lf = ttk.LabelFrame(self, text="Waypoints", padding=4)
        lf.pack(fill="both", expand=True, pady=(6, 0))
        self.wp_list = tk.Listbox(lf, height=9, exportselection=False, font=("TkFixedFont", 9))
        self.wp_list.pack(fill="both", expand=True)
        self.wp_list.bind("<<ListboxSelect>>", self._on_list_select)
        bf = ttk.Frame(lf)
        bf.pack(fill="x", pady=(4, 0))
        for txt, cmd in (("▲", lambda: app.reorder(-1)), ("▼", lambda: app.reorder(1)),
                         ("Insert after", lambda: app.insert_after(app.selected)),
                         ("Delete", lambda: app.delete_waypoint(app.selected))):
            ttk.Button(bf, text=txt, command=cmd, width=len(txt) + 2).pack(side="left", padx=1)

        # properties
        pf = ttk.LabelFrame(self, text="Selected waypoint", padding=4)
        pf.pack(fill="x", pady=(6, 0))
        self.x_var, self.y_var, self.h_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.h_set = tk.BooleanVar()
        self.rev_var, self.curve_var = tk.BooleanVar(), tk.BooleanVar()
        self.speed_var = tk.DoubleVar(value=100)
        r = 0
        for lbl, var in (("X (in)", self.x_var), ("Y (in)", self.y_var)):
            ttk.Label(pf, text=lbl).grid(row=r, column=0, sticky="w")
            en = ttk.Entry(pf, textvariable=var, width=9)
            en.grid(row=r, column=1, sticky="w")
            en.bind("<Return>", lambda _e: self._apply_xy())
            en.bind("<FocusOut>", lambda _e: self._apply_xy())
            r += 1
        ttk.Label(pf, text="Heading °").grid(row=r, column=0, sticky="w")
        he = ttk.Entry(pf, textvariable=self.h_var, width=9)
        he.grid(row=r, column=1, sticky="w")
        he.bind("<Return>", lambda _e: self._apply_heading())
        he.bind("<FocusOut>", lambda _e: self._apply_heading())
        self.h_chk = ttk.Checkbutton(pf, text="turn to heading", variable=self.h_set, command=self._apply_heading)
        self.h_chk.grid(row=r, column=2, sticky="w")
        r += 1
        self.rev_chk = ttk.Checkbutton(pf, text="Reverse (drive backward)", variable=self.rev_var,
                                       command=lambda: self._apply_flag("reverse", self.rev_var))
        self.rev_chk.grid(row=r, column=0, columnspan=3, sticky="w")
        r += 1
        self.curve_chk = ttk.Checkbutton(pf, text="Curved segment (bezier / boomerang)", variable=self.curve_var,
                                         command=lambda: self._apply_flag("curve", self.curve_var))
        self.curve_chk.grid(row=r, column=0, columnspan=2, sticky="w")
        self.reset_btn = ttk.Button(pf, text="Reset handles", command=lambda: app.reset_handles(app.selected))
        self.reset_btn.grid(row=r, column=2, sticky="w")
        r += 1
        ttk.Label(pf, text="Max speed %").grid(row=r, column=0, sticky="w")
        self.speed_scale = tk.Scale(pf, from_=10, to=100, resolution=5, orient="horizontal",
                                    variable=self.speed_var, showvalue=True, length=160,
                                    command=lambda _v: self._apply_speed())
        self.speed_scale.grid(row=r, column=1, columnspan=2, sticky="we")

        # actions
        af = ttk.LabelFrame(self, text="Actions at waypoint (run in order after arriving)", padding=4)
        af.pack(fill="x", pady=(6, 0))
        self.act_list = tk.Listbox(af, height=4, exportselection=False)
        self.act_list.pack(fill="x")
        self.act_list.bind("<<ListboxSelect>>", self._on_action_select)
        row = ttk.Frame(af)
        row.pack(fill="x", pady=(4, 0))
        self.act_type = tk.StringVar(value=ACTION_TYPES["intake_on"][0])
        self._label_to_key = {v[0]: k for k, v in ACTION_TYPES.items()}
        cb = ttk.Combobox(row, textvariable=self.act_type, values=[v[0] for v in ACTION_TYPES.values()],
                          state="readonly", width=16)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", self._on_type_change)
        ttk.Label(row, text="s").pack(side="right")
        self.act_dur = tk.StringVar(value="0")
        ttk.Entry(row, textvariable=self.act_dur, width=5).pack(side="right")
        row2 = ttk.Frame(af)
        row2.pack(fill="x", pady=(2, 0))
        ttk.Label(row2, text="Code").pack(side="left")
        self.act_code = tk.StringVar(value=ACTION_TYPES["intake_on"][2])
        ttk.Entry(row2, textvariable=self.act_code).pack(side="left", fill="x", expand=True, padx=4)
        row3 = ttk.Frame(af)
        row3.pack(fill="x", pady=(2, 0))
        ttk.Button(row3, text="Add", command=self._add_action).pack(side="left")
        ttk.Button(row3, text="Update", command=self._update_action).pack(side="left", padx=2)
        ttk.Button(row3, text="Remove", command=self._remove_action).pack(side="left")
        ttk.Button(row3, text="▲", width=3, command=lambda: self._move_action(-1)).pack(side="left", padx=(6, 0))
        ttk.Button(row3, text="▼", width=3, command=lambda: self._move_action(1)).pack(side="left")

        # timing
        tf = ttk.LabelFrame(self, text="Timing", padding=4)
        tf.pack(fill="x", pady=(6, 0))
        self.limit_var = tk.StringVar(value=next(iter(LIMITS)))
        lc = ttk.Combobox(tf, textvariable=self.limit_var, values=list(LIMITS), state="readonly", width=20)
        lc.pack(anchor="w")
        lc.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.time_lbl = tk.Label(tf, text="", font=("TkDefaultFont", 12, "bold"), anchor="w")
        self.time_lbl.pack(fill="x")
        self.seg_lbl = ttk.Label(tf, text="", justify="left", wraplength=330)
        self.seg_lbl.pack(fill="x")
        self.warn_lbl = tk.Label(tf, text="", fg="#c00", justify="left", anchor="w", wraplength=330)
        self.warn_lbl.pack(fill="x")

    # ---- refresh -------------------------------------------------------------
    @property
    def limit(self) -> float:
        return LIMITS.get(self.limit_var.get(), 15.0)

    def refresh(self) -> None:
        app = self.app
        self._loading = True
        try:
            if self.focus_get() is not self.name_entry:
                self.name_var.set(app.route.name)
            route = app.route
            self.wp_list.delete(0, "end")
            for i, wp in enumerate(route.waypoints):
                flags = ("R" if wp.reverse else " ") + ("~" if wp.curve else " ")
                h = route.heading_at(i) or 0.0
                acts = " ".join(SHORT.get(a.type, "?") for a in wp.actions)
                t = app.timeline.arrival[i] if i < len(app.timeline.arrival) else 0.0
                self.wp_list.insert("end", f"{i:>2} {flags} ({wp.x:6.1f},{wp.y:6.1f}) h{h:5.1f} {t:5.2f}s {acts}")
            sel = app.selected
            state = "normal" if sel is not None else "disabled"
            for w in (self.h_chk, self.rev_chk, self.curve_chk, self.reset_btn):
                w.configure(state=state)
            if sel is not None:
                self.wp_list.selection_set(sel)
                self.wp_list.see(sel)
                wp = route.waypoints[sel]
                self.x_var.set(f"{wp.x:.2f}")
                self.y_var.set(f"{wp.y:.2f}")
                h = route.heading_at(sel) or 0.0
                self.h_var.set(f"{h:.1f}")
                self.h_set.set(wp.heading is not None or sel == 0 or wp.curve)
                self.rev_var.set(wp.reverse)
                self.curve_var.set(wp.curve)
                self.speed_var.set(wp.speed)
                if sel == 0:
                    self.rev_chk.configure(state="disabled")
                    self.curve_chk.configure(state="disabled")
                    self.h_chk.configure(state="disabled")
                if not wp.curve:
                    self.reset_btn.configure(state="disabled")
                self.act_list.delete(0, "end")
                for a in wp.actions:
                    self.act_list.insert("end", a.describe())
            else:
                for v in (self.x_var, self.y_var, self.h_var):
                    v.set("")
                self.act_list.delete(0, "end")
            # timing
            tl = app.timeline
            over = tl.total > self.limit
            self.time_lbl.configure(text=f"Estimated: {tl.total:.2f} s / {self.limit:.0f} s",
                                    fg="#c00" if over else "#1a7f37")
            drive = sum(p.duration for p in tl.phases if p.kind == "drive")
            turn = sum(p.duration for p in tl.phases if p.kind == "turn")
            act = sum(p.duration for p in tl.phases if p.kind == "action")
            dist_total = sum(p.length for p in tl.phases if p.kind == "drive")
            self.seg_lbl.configure(text=f"drive {drive:.2f}s · turn {turn:.2f}s · actions {act:.2f}s · "
                                        f"distance {dist_total:.0f} in")
            if app.check_collisions.get() and app.collisions:
                lines = [f"⚠ {what} at t={t:.2f}s ({x:.0f},{y:.0f})" for t, x, y, what in app.collisions[:6]]
                if len(app.collisions) > 6:
                    lines.append(f"… {len(app.collisions) - 6} more")
                self.warn_lbl.configure(text="\n".join(lines))
            else:
                self.warn_lbl.configure(text="")
        finally:
            self._loading = False

    # ---- apply edits -----------------------------------------------------------
    def _apply_name(self) -> None:
        name = self.name_var.get().strip() or "auton"
        if name != self.app.route.name:
            self.app.snapshot()
            self.app.route.name = name
            self.app.changed()

    def _on_list_select(self, _e: tk.Event) -> None:
        cur = self.wp_list.curselection()
        if cur and not self._loading:
            self.app.select(cur[0])

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

    def _apply_speed(self) -> None:
        app = self.app
        if self._loading or app.selected is None:
            return
        wp = app.route.waypoints[app.selected]
        v = float(self.speed_var.get())
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

    def _on_action_select(self, _e: tk.Event) -> None:
        app = self.app
        cur = self.act_list.curselection()
        if not cur or app.selected is None:
            return
        a = app.route.waypoints[app.selected].actions[cur[0]]
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
        cur = self.act_list.curselection()
        a = self._form_action()
        if app.selected is None or not cur or a is None:
            return
        app.snapshot()
        app.route.waypoints[app.selected].actions[cur[0]] = a
        app.changed()
        self.act_list.selection_set(cur[0])

    def _remove_action(self) -> None:
        app = self.app
        cur = self.act_list.curselection()
        if app.selected is None or not cur:
            return
        app.snapshot()
        del app.route.waypoints[app.selected].actions[cur[0]]
        app.changed()

    def _move_action(self, d: int) -> None:
        app = self.app
        cur = self.act_list.curselection()
        if app.selected is None or not cur:
            return
        acts = app.route.waypoints[app.selected].actions
        i, j = cur[0], cur[0] + d
        if 0 <= j < len(acts):
            app.snapshot()
            acts[i], acts[j] = acts[j], acts[i]
            app.changed()
            self.act_list.selection_set(j)
