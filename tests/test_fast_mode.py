"""Tests for the fast heuristic Hermes planner."""

from __future__ import annotations

from pathlib import Path

from hermes_openclaw.config import Settings
from hermes_openclaw.controller.factory import build_hermes_adapter
from hermes_openclaw.hermes.adapter import FastHermesAdapter


def _settings(tmp_path: Path, **overrides) -> Settings:
    base = {
        "workspace_root": tmp_path / "workspace",
        "audit_log_path": tmp_path / "logs" / "audit.jsonl",
        "memory_db_path": tmp_path / "data" / "memory.db",
        "policy_file": Path("config/policy.yaml"),
        "hermes_mock_mode": False,
        "hermes_fast_mode": True,
        "dry_run": True,
        "network_enabled": True,
        "plan_signing_secret": "test-secret",
    }
    base.update(overrides)
    return Settings(**base)


def test_build_hermes_adapter_uses_fast_mode(tmp_path: Path):
    settings = _settings(tmp_path)
    adapter = build_hermes_adapter(settings)

    assert isinstance(adapter, FastHermesAdapter)


def test_fast_adapter_shortcuts_youtube_search():
    plan = FastHermesAdapter()._plan_for_intent("open youtube and play lo-fi beats")

    assert plan is not None
    assert plan["intent"] == "open youtube and play lo-fi beats"
    assert plan["actions"][0]["command"] == "open"
    assert "youtube.com" in plan["actions"][0]["args"][0]
