"""Playback bar: animates the robot along the profiled route."""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import App

FRAME_MS = 30


class Playback(ttk.Frame):
    def __init__(self, master: tk.Misc, app: "App") -> None:
        super().__init__(master, padding=(6, 2))
        self.app = app
        self.t = 0.0
        self.playing = False
        self._last = 0.0
        self.play_btn = ttk.Button(self, text="▶ Play", width=8, command=self.toggle)
        self.play_btn.pack(side="left")
        ttk.Button(self, text="⏮", width=3, command=self.reset).pack(side="left", padx=2)
        self.t_var = tk.DoubleVar(value=0.0)
        self.slider = ttk.Scale(self, from_=0.0, to=1.0, variable=self.t_var, command=self._on_scrub)
        self.slider.pack(side="left", fill="x", expand=True, padx=6)
        self.speed_var = tk.StringVar(value="1x")
        ttk.Combobox(self, textvariable=self.speed_var, values=["0.25x", "0.5x", "1x", "2x", "4x"],
                     width=5, state="readonly").pack(side="left")
        self.lbl = ttk.Label(self, text="", width=44, font=("TkFixedFont", 9))
        self.lbl.pack(side="left", padx=6)

    @property
    def speed(self) -> float:
        return float(self.speed_var.get().rstrip("x"))

    def toggle(self) -> None:
        if self.playing:
            self.playing = False
            self.play_btn.configure(text="▶ Play")
            return
        if self.t >= self.app.timeline.total - 1e-6:
            self.t = 0.0
        self.playing = True
        self.play_btn.configure(text="⏸ Pause")
        self._last = time.perf_counter()
        self.after(FRAME_MS, self._tick)

    def reset(self) -> None:
        self.playing = False
        self.play_btn.configure(text="▶ Play")
        self.t = 0.0
        self.update_view()

    def _tick(self) -> None:
        if not self.playing:
            return
        now = time.perf_counter()
        self.t += (now - self._last) * self.speed
        self._last = now
        total = self.app.timeline.total
        if self.t >= total:
            self.t = total
            self.playing = False
            self.play_btn.configure(text="▶ Play")
        self.update_view()
        if self.playing:
            self.after(FRAME_MS, self._tick)

    def _on_scrub(self, _v: str) -> None:
        self.t = float(self.t_var.get())
        self.update_view()

    def update_view(self) -> None:
        tl = self.app.timeline
        total = max(tl.total, 0.001)
        self.t = min(self.t, tl.total)
        self.slider.configure(to=total)
        self.t_var.set(self.t)
        canvas = self.app.canvas
        if not tl.phases and not self.app.route.waypoints:
            canvas.ghost_pose = None
            self.lbl.configure(text="")
        else:
            if tl.phases:
                x, y, h, ph = tl.pose_at(self.t)
            else:
                w = self.app.route.waypoints[0]
                x, y, h, ph = w.x, w.y, w.heading or 0.0, None
            canvas.ghost_pose = (x, y, h)
            what = ""
            if ph is not None and ph.t0 <= self.t <= ph.t1:
                what = ph.kind + (f" {ph.action.label}" if ph.action else "") + f" → wp {ph.wp}"
            limit = self.app.inspector.limit
            flag = "  OVER" if self.t > limit else ""
            self.lbl.configure(text=f"t={self.t:5.2f}/{tl.total:5.2f}s{flag}  {what}")
        canvas.redraw()
