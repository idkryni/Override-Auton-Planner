"""Export and robot-settings dialogs."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from ..export import FORMATS, ExportOptions

if TYPE_CHECKING:
    from .app import App


class ExportDialog(tk.Toplevel):
    def __init__(self, app: "App", fmt: str) -> None:
        super().__init__(app.root)
        self.app = app
        self.title("Export auton")
        self.geometry("820x620")
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="Format").pack(side="left")
        self.fmt = tk.StringVar(value=fmt)
        cb = ttk.Combobox(bar, textvariable=self.fmt, values=list(FORMATS), state="readonly", width=22)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.render())
        ttk.Label(bar, text="Origin").pack(side="left", padx=(10, 0))
        self.origin = tk.StringVar(value=app.export_origin)
        for val, lbl in (("center", "field center"), ("bottom_left", "bottom-left")):
            ttk.Radiobutton(bar, text=lbl, value=val, variable=self.origin, command=self.render).pack(side="left")
        ttk.Label(bar, text="Function").pack(side="left", padx=(10, 0))
        self.fn = tk.StringVar(value=app.route.name.replace(" ", "_") or "autonRoute")
        en = ttk.Entry(bar, textvariable=self.fn, width=16)
        en.pack(side="left", padx=4)
        en.bind("<Return>", lambda _e: self.render())
        self.text = tk.Text(self, wrap="none", font=("TkFixedFont", 10), undo=False)
        ys = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        self.text.pack(fill="both", expand=True)
        btns = ttk.Frame(self, padding=6)
        btns.pack(fill="x", side="bottom")
        ttk.Button(btns, text="Copy to clipboard", command=self.copy).pack(side="left")
        ttk.Button(btns, text="Save…", command=self.save).pack(side="left", padx=4)
        ttk.Button(btns, text="Close", command=self.destroy).pack(side="right")
        self.render()

    def content(self) -> str:
        fn, _ = FORMATS[self.fmt.get()]
        name = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in self.fn.get()) or "autonRoute"
        self.app.export_origin = self.origin.get()
        return fn(self.app.route, self.app.robot, ExportOptions(origin=self.origin.get(), function_name=name))

    def render(self) -> None:
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.content())

    def copy(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end-1c"))
        self.app.set_status("Export copied to clipboard")

    def save(self) -> None:
        _, ext = FORMATS[self.fmt.get()]
        path = filedialog.asksaveasfilename(parent=self, defaultextension=ext,
                                            initialfile=f"{self.app.route.name}{ext}")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text.get("1.0", "end-1c"))
            self.app.set_status(f"Exported {path}")


class RobotDialog(tk.Toplevel):
    FIELDS = [
        ("width", "Width (in, side to side)"),
        ("length", "Length (in, front to back)"),
        ("max_velocity", "Max velocity (in/s)"),
        ("max_acceleration", "Max acceleration (in/s²)"),
        ("max_angular_velocity", "Max turn rate (°/s)"),
        ("max_angular_acceleration", "Max turn accel (°/s²)"),
        ("turn_threshold_deg", "Ignore turns smaller than (°)"),
    ]

    def __init__(self, app: "App") -> None:
        super().__init__(app.root)
        self.app = app
        self.title("Robot settings")
        self.resizable(False, False)
        frm = ttk.Frame(self, padding=10)
        frm.pack()
        self.vars: dict[str, tk.StringVar] = {}
        for r, (key, label) in enumerate(self.FIELDS):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=f"{getattr(app.robot, key):g}")
            ttk.Entry(frm, textvariable=v, width=10).grid(row=r, column=1, padx=6)
            self.vars[key] = v
        b = ttk.Frame(frm)
        b.grid(row=len(self.FIELDS), column=0, columnspan=2, pady=(8, 0))
        ttk.Button(b, text="Apply", command=self.apply).pack(side="left")
        ttk.Button(b, text="Close", command=self.destroy).pack(side="left", padx=4)

    def apply(self) -> None:
        try:
            vals = {k: float(v.get()) for k, v in self.vars.items()}
        except ValueError:
            messagebox.showerror("Robot settings", "All values must be numbers.", parent=self)
            return
        if any(vals[k] <= 0 for k in vals if k != "turn_threshold_deg"):
            messagebox.showerror("Robot settings", "Values must be positive.", parent=self)
            return
        for k, v in vals.items():
            setattr(self.app.robot, k, v)
        self.app.changed()
