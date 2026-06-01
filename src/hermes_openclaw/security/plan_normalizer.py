"""Normalize Hermes plan JSON into the internal schema."""

from __future__ import annotations

from typing import Any

# Hermes may use plural action names — map to internal ActionType values.
ACTION_ALIASES: dict[str, str] = {
    "move_files": "move_file",
    "move_file": "move_file",
    "copy_files": "copy_file",
    "copy_file": "copy_file",
    "create_folders": "create_folder",
    "create_folder": "create_folder",
    "list_files": "list_files",
    "launch_app": "launch_app",
    "exec": "exec",
}


def normalize_plan_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Accept Hermes output in either format:
    - { "actions": [{ "type": "move_file", ... }] }
    - { "tasks": [{ "action": "move_files", ... }] }
    """
    normalized = dict(data)

    raw_items = normalized.pop("tasks", None) or normalized.get("actions", [])
    actions: list[dict[str, Any]] = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        action = dict(item)
        raw_type = action.pop("action", None) or action.get("type", "")
        if isinstance(raw_type, str):
            action["type"] = ACTION_ALIASES.get(raw_type, raw_type)
        actions.append(action)

    normalized["actions"] = actions
    return normalized
