"""Export and robot-settings dialogs."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

from ..export import FORMATS, ExportOptions

if TYPE_CHECKING:
    from .app import App

SHORT_NAMES = {"LemLib (PROS)": "LemLib", "JAR-Template (VEXcode)": "JAR", "EZ-Template (PROS)": "EZ",
               "JSON": "JSON", "CSV": "CSV"}


class ExportDialog(tk.Toplevel):
    def __init__(self, app: "App", fmt: str) -> None:
        super().__init__(app.root)
        self.app = app
        c, f = app.theme.c, app.theme.f
        self.title("Export")
        self.configure(bg=c["surface"])
        self.geometry("900x660")
        self.transient(app.root)
        head = ttk.Frame(self, style="Side.TFrame", padding=(20, 18, 20, 12))
        head.pack(fill="x")
        ttk.Label(head, text="Export route", style="Brand.TLabel").pack(anchor="w")
        ttk.Label(head, text="Code for your robot project. Heading 0 faces the far wall, clockwise positive.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 0))
        opts = ttk.Frame(self, style="Side.TFrame", padding=(20, 0, 20, 12))
        opts.pack(fill="x")
        self.fmt = tk.StringVar(value=fmt)
        self.origin = tk.StringVar(value=app.export_origin)
        self.fn = tk.StringVar(value="".join(ch if ch.isalnum() else "_" for ch in app.route.name) or "autonRoute")
        g1 = ttk.Frame(opts, style="Side.TFrame")
        g1.pack(side="left")
        ttk.Label(g1, text="Format", style="Field.TLabel").pack(anchor="w", pady=(0, 3))
        segs = ttk.Frame(g1, style="Side.TFrame")
        segs.pack(anchor="w")
        for name in FORMATS:
            ttk.Radiobutton(segs, text=SHORT_NAMES.get(name, name), value=name, variable=self.fmt,
                            style="Seg.Toolbutton", command=self.render).pack(side="left")
        g2 = ttk.Frame(opts, style="Side.TFrame")
        g2.pack(side="left", padx=(20, 0))
        ttk.Label(g2, text="Origin", style="Field.TLabel").pack(anchor="w", pady=(0, 3))
        segs = ttk.Frame(g2, style="Side.TFrame")
        segs.pack(anchor="w")
        for val, lbl in (("center", "Field center"), ("bottom_left", "Bottom left")):
            ttk.Radiobutton(segs, text=lbl, value=val, variable=self.origin, style="Seg.Toolbutton",
                            command=self.render).pack(side="left")
        g3 = ttk.Frame(opts, style="Side.TFrame")
        g3.pack(side="left", padx=(20, 0), fill="x", expand=True)
        ttk.Label(g3, text="Function name", style="Field.TLabel").pack(anchor="w", pady=(0, 3))
        en = ttk.Entry(g3, textvariable=self.fn, style="Mono.TEntry")
        en.pack(fill="x")
        en.bind("<Return>", lambda _e: self.render())
        en.bind("<FocusOut>", lambda _e: self.render())

        foot = ttk.Frame(self, style="Side.TFrame", padding=(20, 12))
        foot.pack(fill="x", side="bottom")
        ttk.Button(foot, text="Copy code", style="Accent.TButton", command=self.copy).pack(side="right")
        ttk.Button(foot, text="Save file", command=self.save).pack(side="right", padx=(0, 8))
        ttk.Button(foot, text="Close", style="Ghost.TButton", command=self.destroy).pack(side="left")
        self.note = ttk.Label(foot, text="", style="Muted.TLabel")
        self.note.pack(side="left", padx=12)

        box = tk.Frame(self, bg=c["border"], padx=1, pady=1)
        box.pack(fill="both", expand=True, padx=20)
        self.text = tk.Text(box, wrap="none", font=f["mono"], bg=c["bg"], fg=c["text"], insertbackground=c["text"],
                            selectbackground=c["accent_soft"], relief="flat", padx=14, pady=12, bd=0,
                            highlightthickness=0)
        ys = ttk.Scrollbar(box, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("comment", foreground=c["faint"])
        self.render()

    def content(self) -> str:
        fn, _ = FORMATS[self.fmt.get()]
        name = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in self.fn.get()) or "autonRoute"
        self.app.export_origin = self.origin.get()
        return fn(self.app.route, self.app.robot, ExportOptions(origin=self.origin.get(), function_name=name))

    def render(self) -> None:
        txt = self.content()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for line in txt.splitlines(keepends=True):
            self.text.insert("end", line, ("comment",) if line.lstrip().startswith("//") else ())
        self.text.configure(state="disabled")
        self.note.configure(text=f"{len(txt.splitlines())} lines")

    def copy(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end-1c"))
        self.note.configure(text="Copied to clipboard")

    def save(self) -> None:
        _, ext = FORMATS[self.fmt.get()]
        path = filedialog.asksaveasfilename(parent=self, defaultextension=ext,
                                            initialfile=f"{self.app.route.name}{ext}")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.text.get("1.0", "end-1c"))
            self.note.configure(text=f"Saved {path}")


class RobotDialog(tk.Toplevel):
    FIELDS = [
        ("width", "Width (in)"), ("length", "Length (in)"),
        ("max_velocity", "Max speed (in/s)"), ("max_acceleration", "Max accel (in/s²)"),
        ("max_angular_velocity", "Max turn rate (deg/s)"), ("max_angular_acceleration", "Max turn accel (deg/s²)"),
        ("turn_threshold_deg", "Skip turns under (deg)"),
    ]

    def __init__(self, app: "App") -> None:
        super().__init__(app.root)
        self.app = app
        self.title("Robot")
        self.configure(bg=app.theme.c["surface"])
        self.resizable(False, False)
        self.transient(app.root)
        frm = ttk.Frame(self, style="Side.TFrame", padding=20)
        frm.pack()
        ttk.Label(frm, text="Robot model", style="Brand.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(frm, text="Used for footprints, contact checks and time estimates.",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 12))
        self.vars: dict[str, tk.StringVar] = {}
        for k, (key, label) in enumerate(self.FIELDS):
            r, col = 2 + (k // 2) * 2, k % 2
            ttk.Label(frm, text=label, style="Field.TLabel").grid(row=r, column=col, sticky="w",
                                                                  padx=(0 if col == 0 else 12, 0), pady=(6, 3))
            v = tk.StringVar(value=f"{getattr(app.robot, key):g}")
            ttk.Entry(frm, textvariable=v, width=14, style="Mono.TEntry").grid(
                row=r + 1, column=col, sticky="we", padx=(0 if col == 0 else 12, 0))
            self.vars[key] = v
        self.err = ttk.Label(frm, text="", style="Warn.TLabel")
        self.err.grid(row=20, column=0, columnspan=2, sticky="w", pady=(10, 0))
        b = ttk.Frame(frm, style="Side.TFrame")
        b.grid(row=21, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(b, text="Close", style="Ghost.TButton", command=self.destroy).pack(side="left")
        ttk.Button(b, text="Apply", style="Accent.TButton", command=self.apply).pack(side="left", padx=(8, 0))

    def apply(self) -> None:
        try:
            vals = {k: float(v.get()) for k, v in self.vars.items()}
        except ValueError:
            self.err.configure(text="Every value must be a number.")
            return
        if any(vals[k] <= 0 for k in vals if k != "turn_threshold_deg"):
            self.err.configure(text="Sizes and limits must be greater than zero.")
            return
        self.err.configure(text="")
        for k, v in vals.items():
            setattr(self.app.robot, k, v)
        self.app.changed()
