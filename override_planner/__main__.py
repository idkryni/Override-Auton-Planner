"""Entry point: python -m override_planner [route.json]"""
from __future__ import annotations

import sys


def main() -> None:
    try:
        import tkinter as tk
    except ImportError:
        sys.exit("Tkinter is required. On Linux install it with: sudo apt install python3-tk")
    from .ui.app import App

    root = tk.Tk()
    try:
        from tkinter import ttk
        style = ttk.Style(root)
        if "clam" in style.theme_names() and sys.platform.startswith("linux"):
            style.theme_use("clam")
    except tk.TclError:
        pass
    App(root, sys.argv[1] if len(sys.argv) > 1 else None)
    root.mainloop()


if __name__ == "__main__":
    main()
