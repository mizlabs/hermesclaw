"""Structured task schemas — the only format Hermes may produce and OpenClaw may consume."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

# Hermes must never emit action types outside this closed set.
ALLOWED_ACTION_TYPES: frozenset[str] = frozenset(
    {
        "move_file",
        "copy_file",
        "create_folder",
        "list_files",
        "launch_app",
        "exec",
    }
)

# Reject shell metacharacters in paths and arguments — defense in depth.
_UNSAFE_PATH_PATTERN = re.compile(r"[;|`$&<>]")
_UNSAFE_ARG_PATTERN = re.compile(r"[;|`$&<>]")


class ActionType(StrEnum):
    MOVE_FILE = "move_file"
    COPY_FILE = "copy_file"
    CREATE_FOLDER = "create_folder"
    LIST_FILES = "list_files"
    LAUNCH_APP = "launch_app"
    EXEC = "exec"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskAction(BaseModel):
    """A single validated action — no free-form shell strings."""

    type: ActionType
    source: str | None = None
    destination: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    app_name: str | None = None
    scope: str | None = None  # Permission scope e.g. "applications.launch"
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type", mode="before")
    @classmethod
    def reject_unknown_action_types(cls, value: str) -> str:
        if value not in ALLOWED_ACTION_TYPES:
            msg = f"Unknown action type '{value}'. Allowed: {sorted(ALLOWED_ACTION_TYPES)}"
            raise ValueError(msg)
        return value

    @field_validator("source", "destination", "command", "app_name", mode="before")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None or not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped if stripped else None

    @field_validator("source", "destination", "command", "app_name")
    @classmethod
    def reject_shell_metacharacters(cls, value: str | None) -> str | None:
        if value is not None and _UNSAFE_PATH_PATTERN.search(value):
            raise ValueError("Path or string contains forbidden shell metacharacters")
        return value

    @field_validator("args")
    @classmethod
    def sanitize_args(cls, value: list[str]) -> list[str]:
        for arg in value:
            if _UNSAFE_ARG_PATTERN.search(arg):
                raise ValueError(f"Argument contains forbidden characters: {arg!r}")
        return value

    @model_validator(mode="after")
    def validate_required_fields(self) -> TaskAction:
        required: dict[ActionType, tuple[str, ...]] = {
            ActionType.MOVE_FILE: ("source", "destination"),
            ActionType.COPY_FILE: ("source", "destination"),
            ActionType.CREATE_FOLDER: ("destination",),
            ActionType.LIST_FILES: ("source",),
            ActionType.LAUNCH_APP: ("app_name",),
            ActionType.EXEC: ("command",),
        }
        for field_name in required[self.type]:
            if getattr(self, field_name) is None:
                raise ValueError(f"Action type '{self.type}' requires '{field_name}'")
        return self


class TaskPlan(BaseModel):
    """Hermes output schema — structured JSON only, never raw instructions."""

    task_id: str = Field(default_factory=lambda: str(uuid4()))
    intent: str = Field(min_length=1, max_length=2000)
    actions: list[TaskAction] = Field(min_length=1, max_length=50)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    dry_run: bool = False

    @field_validator("intent")
    @classmethod
    def sanitize_intent(cls, value: str) -> str:
        # Strip control characters that could confuse downstream parsers.
        cleaned = "".join(ch for ch in value.strip() if ch.isprintable())
        if not cleaned:
            raise ValueError("Intent must contain printable characters")
        return cleaned

    @model_validator(mode="after")
    def align_confirmation_with_risk(self) -> TaskPlan:
        # High/critical risk always requires confirmation regardless of LLM output.
        if self.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            object.__setattr__(self, "requires_confirmation", True)
        if any(action.type == ActionType.EXEC for action in self.actions):
            object.__setattr__(self, "requires_confirmation", True)
        return self
