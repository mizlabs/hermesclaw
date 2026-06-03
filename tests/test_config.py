"""Tests for application configuration."""

from pathlib import Path

from hermes_openclaw.config import Settings


def test_default_settings():
    settings = Settings(auto_approve=False)
    assert settings.hermes_model_endpoint == "http://localhost:11434/v1"
    assert settings.network_enabled is False
    assert settings.safety_confirm_destructive is True
    assert settings.auto_approve is False
    assert isinstance(settings.workspace_root, Path)


def test_parse_telegram_allowed_chat_ids_from_csv():
    settings = Settings(telegram_allowed_chat_ids="123, -456")
    assert settings.telegram_allowed_chat_ids == [123, -456]


def test_parse_telegram_allowed_chat_ids_from_list():
    settings = Settings(telegram_allowed_chat_ids=["123", 456])
    assert settings.telegram_allowed_chat_ids == [123, 456]
