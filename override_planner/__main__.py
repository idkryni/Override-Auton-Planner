"""Entry point: python -m override_planner [route.json] [--light]"""
from __future__ import annotations

import sys


def main() -> None:
    try:
        import tkinter as tk
    except ImportError:
        sys.exit("Tkinter is required. On Linux install it with: sudo apt install python3-tk")
    from .ui.app import App

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = tk.Tk()
    root.geometry("1440x920")
    App(root, args[0] if args else None, theme="light" if "--light" in sys.argv else "dark")
    root.mainloop()


if __name__ == "__main__":
    main()
