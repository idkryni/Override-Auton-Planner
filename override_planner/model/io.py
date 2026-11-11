"""Load configs and save/load route files."""
from __future__ import annotations

import json
from pathlib import Path

from .path import Route
from .profile import RobotConfig

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def load_json(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def load_layout() -> dict:
    return load_json("field_layout.json")


def load_elements() -> dict:
    return load_json("elements.json")


def load_robot() -> RobotConfig:
    return RobotConfig.from_dict(load_json("robot.json"))


def save_route(route: Route, robot: RobotConfig, path: str | Path) -> None:
    data = route.to_dict()
    data["robot"] = robot.to_dict()
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_route(path: str | Path) -> tuple[Route, RobotConfig | None]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    robot = RobotConfig.from_dict(data["robot"]) if "robot" in data else None
    return Route.from_dict(data), robot
