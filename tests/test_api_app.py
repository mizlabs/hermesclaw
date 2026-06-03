"""API tests for authenticated execution and Telegram webhook handling."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import hermes_openclaw.api.app as app_module
from hermes_openclaw.api.app import create_app
from hermes_openclaw.config import Settings


def _settings(tmp_path: Path, **overrides) -> Settings:
    base = {
        "workspace_root": tmp_path / "workspace",
        "audit_log_path": tmp_path / "logs" / "audit.jsonl",
        "memory_db_path": tmp_path / "data" / "memory.db",
        "policy_file": Path("config/policy.yaml"),
        "hermes_mock_mode": True,
        "dry_run": True,
        "network_enabled": True,
        "plan_signing_secret": "test-secret",
    }
    base.update(overrides)
    return Settings(**base)


def test_intent_endpoint_requires_auth_when_token_set(tmp_path: Path):
    settings = _settings(tmp_path, api_bearer_token="top-secret")
    client = TestClient(create_app(settings))

    denied = client.post("/intents/execute", json={"intent": "organize files"})
    assert denied.status_code == 401

    allowed = client.post(
        "/intents/execute",
        headers={"Authorization": "Bearer top-secret"},
        json={"intent": "organize files", "safe_mode": True},
    )
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["intent"] == "organize files"
    assert "success" in body


def test_telegram_webhook_runs_safe_mode_by_default(tmp_path: Path, monkeypatch):
    sent: list[tuple[int, str]] = []

    def _fake_send(bot_token: str, chat_id: int, text: str) -> None:
        assert bot_token == "bot-token"  # noqa: S105
        sent.append((chat_id, text))

    monkeypatch.setattr(app_module, "_send_telegram_message", _fake_send)

    settings = _settings(
        tmp_path,
        telegram_bot_token="bot-token",
        telegram_webhook_secret="hook-secret",
        telegram_allowed_chat_ids=[12345],
    )
    client = TestClient(create_app(settings))

    response = client.post(
        "/integrations/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "hook-secret"},
        json={
            "message": {
                "chat": {"id": 12345},
                "text": "organize my project files",
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["safe_mode"] is True
    assert sent
    _, message = sent[0]
    assert "Safe mode: on" in message


def test_telegram_webhook_rejects_invalid_secret(tmp_path: Path):
    settings = _settings(
        tmp_path,
        telegram_bot_token="bot-token",
        telegram_webhook_secret="hook-secret",
    )
    client = TestClient(create_app(settings))

    response = client.post(
        "/integrations/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        json={"message": {"chat": {"id": 1}, "text": "hello"}},
    )

    assert response.status_code == 401
