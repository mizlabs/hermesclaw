"""Tests for application configuration."""

from pathlib import Path

from hermes_openclaw.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.hermes_model_endpoint == "http://localhost:11434/v1"
    assert settings.network_enabled is False
    assert settings.safety_confirm_destructive is True
    assert settings.auto_approve is False
    assert isinstance(settings.workspace_root, Path)
