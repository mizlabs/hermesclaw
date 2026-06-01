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
        actions.append(normalize_action_dict(action))

    normalized["actions"] = actions
    return normalized


def _blank_to_none(value: object) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    return stripped if stripped else None


def normalize_action_dict(action: dict[str, Any]) -> dict[str, Any]:
    """Fix common Hermes planner mistakes before schema validation."""
    normalized = dict(action)
    for key in ("source", "destination", "command", "app_name"):
        if key in normalized:
            normalized[key] = _blank_to_none(normalized.get(key))

    action_type = normalized.get("type")
    if action_type == "create_folder":
        destination = normalized.get("destination")
        source = normalized.get("source")
        if not destination and source:
            normalized["destination"] = source
            normalized["source"] = None

    return normalized
