"""Action markers attached to waypoints (run after the robot arrives)."""
from __future__ import annotations

from dataclasses import dataclass

# type -> (label, default duration seconds, C++ snippet emitted in code exports)
ACTION_TYPES: dict[str, tuple[str, float, str]] = {
    "intake_on": ("Intake on", 0.0, "intakeOn();"),
    "intake_off": ("Intake off", 0.0, "intakeOff();"),
    "outtake": ("Outtake", 0.3, "outtake();"),
    "score_goal": ("Score in goal", 0.6, "scoreGoal();"),
    "grab_pin": ("Grab pin", 0.3, "grabPin();"),
    "grab_cup": ("Grab cup", 0.3, "grabCup();"),
    "flip_toggle": ("Flip toggle", 0.4, "flipToggle();"),
    "load": ("Take from loader", 1.0, "loadFromLoader();"),
    "clamp": ("Clamp / mech toggle", 0.2, "clampToggle();"),
    "wait": ("Wait", 0.5, ""),
    "custom": ("Custom code", 0.0, ""),
}

SHORT = {
    "intake_on": "I+", "intake_off": "I-", "outtake": "O", "score_goal": "S", "grab_pin": "P",
    "grab_cup": "C", "flip_toggle": "T", "load": "L", "clamp": "K", "wait": "W", "custom": "*",
}


@dataclass
class Action:
    type: str
    duration: float = 0.0
    code: str = ""  # custom code / override of the default snippet

    @classmethod
    def make(cls, type_: str) -> "Action":
        label, dur, snippet = ACTION_TYPES[type_]
        return cls(type_, dur, snippet)

    @property
    def label(self) -> str:
        return ACTION_TYPES.get(self.type, (self.type, 0, ""))[0]

    def snippet(self) -> str:
        if self.code:
            return self.code
        return ACTION_TYPES.get(self.type, ("", 0, ""))[2]

    def describe(self) -> str:
        s = self.label
        if self.duration:
            s += f" ({self.duration:g}s)"
        if self.code and self.code != ACTION_TYPES.get(self.type, ("", 0, ""))[2]:
            s += f" [{self.code}]"
        return s

    def to_dict(self) -> dict:
        return {"type": self.type, "duration": self.duration, "code": self.code}

    @classmethod
    def from_dict(cls, d: dict) -> "Action":
        return cls(d["type"], float(d.get("duration", 0.0)), d.get("code", ""))
