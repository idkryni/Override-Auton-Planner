"""Design tokens, fonts and ttk styles. One accent, zinc neutrals, dark + light."""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

DARK = {
    "bg": "#0e1012", "surface": "#15181b", "raised": "#1c2024", "hover": "#23282d",
    "border": "#262b30", "border_strong": "#363c43",
    "text": "#e6e8eb", "muted": "#959ca5", "faint": "#646c75",
    "accent": "#3ecf8e", "accent_hover": "#5ad9a0", "accent_text": "#06140d", "accent_soft": "#173a2b",
    "warn": "#f2a33a", "danger": "#f26464", "stage": "#0b0d0f",
}
LIGHT = {
    "bg": "#eef0f2", "surface": "#ffffff", "raised": "#f5f6f7", "hover": "#e9ecef",
    "border": "#e0e3e7", "border_strong": "#c9ced4",
    "text": "#16191d", "muted": "#545c65", "faint": "#858d96",
    "accent": "#0f8a5a", "accent_hover": "#0c774d", "accent_text": "#ffffff", "accent_soft": "#d7efe4",
    "warn": "#a35f00", "danger": "#c62828", "stage": "#e3e6e9",
}

# Field colors are game colors and stay identical in both themes.
FIELD = {
    "tile": "#8b8e92", "seam": "#7a7d81", "wall": "#c8cbcf", "wall_edge": "#55595e",
    "red": "#d64545", "blue": "#3576d9", "yellow": "#f0cf2a", "white": "#f3f4f5",
    "neutral": "#202326", "cup": "#3b3f44",
    "path": "#3ecf8e", "path_rev": "#f2a33a", "underlay": "#111315",
    "marker": "#f4f5f6", "ink": "#111315", "foot": "#dfe2e5", "hit": "#ff4d4d",
}

SANS = ["Geist", "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", ".AppleSystemUIFont", "Helvetica Neue",
        "Inter", "Cantarell", "DejaVu Sans"]
MONO = ["Geist Mono", "JetBrains Mono", "Cascadia Mono", "SF Mono", "Menlo", "Consolas", "DejaVu Sans Mono"]


class Theme:
    def __init__(self, root: tk.Tk, mode: str = "dark") -> None:
        self.root = root
        self.mode = mode
        fams = set(tkfont.families(root))
        self.sans = next((f for f in SANS if f in fams), "TkDefaultFont")
        self.mono = next((f for f in MONO if f in fams), "TkFixedFont")
        self.f = {
            "body": (self.sans, 10), "small": (self.sans, 9), "label": (self.sans, 9),
            "strong": (self.sans, 10, "bold"), "title": (self.sans, 12, "bold"), "section": (self.sans, 10, "bold"),
            "mono": (self.mono, 9), "mono_sm": (self.mono, 8), "mono_b": (self.mono, 8, "bold"),
            "big": (self.mono, 22, "bold"),
        }
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.apply(mode)

    @property
    def c(self) -> dict:
        return DARK if self.mode == "dark" else LIGHT

    def apply(self, mode: str) -> None:
        self.mode = mode
        c, f, s = self.c, self.f, self.style
        r = self.root
        r.configure(bg=c["bg"])
        # Named defaults (not the option DB: "*Font" would override every ttk style font).
        for name, spec in (("TkDefaultFont", f["body"]), ("TkTextFont", f["body"]), ("TkMenuFont", f["body"]),
                           ("TkHeadingFont", f["small"]), ("TkFixedFont", f["mono"])):
            fam, size = spec[0], spec[1]
            try:
                tkfont.nametofont(name, root=r).configure(family=fam, size=size)
            except tk.TclError:
                pass
        for opt, val in (("*Menu.background", c["surface"]), ("*Menu.foreground", c["text"]),
                         ("*Menu.activeBackground", c["hover"]), ("*Menu.activeForeground", c["text"]),
                         ("*Menu.relief", "flat"), ("*Menu.borderWidth", 1),
                         ("*TCombobox*Listbox.background", c["surface"]),
                         ("*TCombobox*Listbox.foreground", c["text"]),
                         ("*TCombobox*Listbox.selectBackground", c["accent_soft"]),
                         ("*TCombobox*Listbox.selectForeground", c["text"]),
                         ("*TCombobox*Listbox.font", f["body"])):
            r.option_add(opt, val)

        s.configure(".", background=c["bg"], foreground=c["text"], fieldbackground=c["raised"],
                    bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"],
                    troughcolor=c["raised"], focuscolor=c["accent"], selectbackground=c["accent_soft"],
                    selectforeground=c["text"], insertcolor=c["text"], font=f["body"], relief="flat")
        s.configure("TFrame", background=c["bg"])
        s.configure("Bar.TFrame", background=c["surface"])
        s.configure("Side.TFrame", background=c["surface"])
        s.configure("Stage.TFrame", background=c["stage"])
        for name, bg in (("TLabel", c["bg"]), ("Bar.TLabel", c["surface"]), ("Side.TLabel", c["surface"])):
            s.configure(name, background=bg, foreground=c["text"], font=f["body"])
        s.configure("Brand.TLabel", background=c["surface"], foreground=c["text"], font=f["title"])
        s.configure("Muted.TLabel", background=c["surface"], foreground=c["muted"], font=f["small"])
        s.configure("Field.TLabel", background=c["surface"], foreground=c["muted"], font=f["label"])
        s.configure("Section.TLabel", background=c["surface"], foreground=c["text"], font=f["section"])
        s.configure("Big.TLabel", background=c["surface"], foreground=c["text"], font=f["big"])
        s.configure("BigOk.TLabel", background=c["surface"], foreground=c["accent"], font=f["big"])
        s.configure("BigWarn.TLabel", background=c["surface"], foreground=c["danger"], font=f["big"])
        s.configure("Mono.TLabel", background=c["surface"], foreground=c["muted"], font=f["mono"])
        s.configure("Warn.TLabel", background=c["surface"], foreground=c["danger"], font=f["small"])
        s.configure("Status.TLabel", background=c["bg"], foreground=c["muted"], font=f["mono"])
        s.configure("TSeparator", background=c["border"])
        s.configure("Bar.TSeparator", background=c["border"])

        # Shape system: Tk cannot round corners, so every control is flat and square-edged.
        btn = dict(padding=(12, 6), borderwidth=1, focusthickness=0, font=f["body"], width=-3)
        s.configure("TButton", background=c["raised"], foreground=c["text"], bordercolor=c["border_strong"],
                    lightcolor=c["raised"], darkcolor=c["raised"], **btn)
        s.map("TButton", background=[("disabled", c["surface"]), ("pressed", c["border"]), ("active", c["hover"])],
              foreground=[("disabled", c["faint"])], lightcolor=[("active", c["hover"])],
              darkcolor=[("active", c["hover"])])
        s.configure("Accent.TButton", background=c["accent"], foreground=c["accent_text"], bordercolor=c["accent"],
                    lightcolor=c["accent"], darkcolor=c["accent"], **{**btn, "font": f["strong"]})
        s.map("Accent.TButton", background=[("pressed", c["accent_hover"]), ("active", c["accent_hover"])],
              lightcolor=[("active", c["accent_hover"])], darkcolor=[("active", c["accent_hover"])],
              bordercolor=[("active", c["accent_hover"])])
        s.configure("Ghost.TButton", background=c["surface"], foreground=c["muted"], bordercolor=c["surface"],
                    lightcolor=c["surface"], darkcolor=c["surface"], padding=(8, 4), width=-2)
        s.map("Ghost.TButton", background=[("disabled", c["surface"]), ("active", c["hover"])],
              foreground=[("disabled", c["faint"]), ("active", c["text"])],
              bordercolor=[("active", c["hover"])], lightcolor=[("active", c["hover"])],
              darkcolor=[("active", c["hover"])])

        # Segmented controls and toggle chips (Radiobutton / Checkbutton drawn as buttons).
        seg = dict(padding=(12, 5), borderwidth=1, font=f["body"], anchor="center", width=-2)
        for name in ("Seg.Toolbutton", "Chip.Toolbutton"):
            s.configure(name, background=c["raised"], foreground=c["muted"], bordercolor=c["border_strong"],
                        lightcolor=c["raised"], darkcolor=c["raised"], **seg)
            s.map(name,
                  background=[("disabled", c["surface"]), ("selected", c["accent_soft"]), ("active", c["hover"])],
                  foreground=[("disabled", c["faint"]), ("selected", c["accent"] if self.mode == "dark" else c["accent_hover"]),
                              ("active", c["text"])],
                  bordercolor=[("selected", c["accent"])],
                  lightcolor=[("selected", c["accent_soft"]), ("active", c["hover"])],
                  darkcolor=[("selected", c["accent_soft"]), ("active", c["hover"])])
        s.configure("Chip.Toolbutton", padding=(10, 4), font=f["small"])

        s.configure("TCheckbutton", background=c["surface"], foreground=c["text"], indicatorbackground=c["raised"],
                    indicatorforeground=c["accent_text"], upperbordercolor=c["border_strong"],
                    lowerbordercolor=c["border_strong"], font=f["body"])
        s.map("TCheckbutton", indicatorbackground=[("selected", c["accent"])],
              background=[("active", c["surface"])])

        s.configure("TEntry", fieldbackground=c["raised"], foreground=c["text"], bordercolor=c["border_strong"],
                    lightcolor=c["raised"], darkcolor=c["raised"], padding=(8, 5), insertcolor=c["text"])
        s.map("TEntry", bordercolor=[("focus", c["accent"])], lightcolor=[("focus", c["accent"])],
              fieldbackground=[("disabled", c["surface"])], foreground=[("disabled", c["faint"])])
        s.configure("Mono.TEntry", font=f["mono"])
        s.configure("TCombobox", fieldbackground=c["raised"], background=c["raised"], foreground=c["text"],
                    arrowcolor=c["muted"], bordercolor=c["border_strong"], lightcolor=c["raised"],
                    darkcolor=c["raised"], padding=(8, 4))
        s.map("TCombobox", fieldbackground=[("readonly", c["raised"])], foreground=[("readonly", c["text"])],
              background=[("active", c["hover"])], bordercolor=[("focus", c["accent"])],
              selectbackground=[("readonly", c["raised"])], selectforeground=[("readonly", c["text"])])

        s.configure("Treeview", background=c["surface"], fieldbackground=c["surface"], foreground=c["text"],
                    bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["surface"],
                    rowheight=26, font=f["mono"])
        s.map("Treeview", background=[("selected", c["accent_soft"])],
              foreground=[("selected", c["accent"] if self.mode == "dark" else c["accent_hover"])])
        s.configure("Treeview.Heading", background=c["surface"], foreground=c["faint"], font=f["small"],
                    bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["surface"], relief="flat",
                    padding=(4, 4))
        s.map("Treeview.Heading", background=[("active", c["surface"])])
        s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        s.configure("Horizontal.TScale", background=c["accent"], troughcolor=c["border"], bordercolor=c["bg"],
                    lightcolor=c["accent"], darkcolor=c["accent"], sliderlength=14, sliderthickness=14,
                    gripcount=0)
        s.map("Horizontal.TScale", background=[("active", c["accent_hover"])])
        s.configure("Side.Horizontal.TScale", bordercolor=c["surface"])
        s.configure("Vertical.TScrollbar", background=c["raised"], troughcolor=c["surface"],
                    bordercolor=c["surface"], lightcolor=c["raised"], darkcolor=c["raised"],
                    arrowcolor=c["faint"], gripcount=0, arrowsize=10)
        s.map("Vertical.TScrollbar", background=[("active", c["hover"])])
        s.configure("TRadiobutton", background=c["surface"], foreground=c["text"])
