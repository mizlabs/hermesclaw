"""Application configuration — all secrets via environment variables."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Hermes (planner — no execution privileges)
    hermes_model_endpoint: str = "http://localhost:11434/v1"
    hermes_model_name: str = "llama3.2"
    hermes_cli_path: str = "hermes"
    hermes_fast_mode: bool = False

    # OpenClaw (executor — sandboxed)
    openclaw_gateway_url: str = "http://localhost:18789"
    openclaw_gateway_token: str = ""
    openclaw_gateway_session_key: str = "main"
    openclaw_gateway_timeout_sec: int = Field(default=30, ge=1, le=300)
    openclaw_execution_mode: Literal["auto", "local", "gateway"] = "auto"
    openclaw_workspace: str = "./workspace"
    openclaw_cli_path: str = "openclaw"
    openclaw_agent_execution: bool = True

    # Security
    workspace_root: Path = Path("./workspace")
    network_enabled: bool = False
    safety_confirm_destructive: bool = True
    dry_run: bool = False
    execution_timeout_sec: int = Field(default=300, ge=1, le=3600)
    auto_approve: bool = False  # NEVER enable in production
    max_retry_attempts: int = Field(default=3, ge=0, le=10)
    hermes_mock_mode: bool = True
    policy_file: Path = Path("./config/policy.yaml")
    plan_signing_secret: str = Field(default="")
    token_ttl_sec: int = Field(default=300, ge=60, le=3600)
    require_signed_token: bool = True

    # Orchestrator
    log_level: str = "INFO"
    memory_db_path: Path = Path("./data/memory.db")
    audit_log_path: Path = Path("./logs/audit.jsonl")

    # API (binds localhost only by default)
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_bearer_token: str = ""

    # Integrations
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_allowed_chat_ids: list[int] = Field(default_factory=list)

    @field_validator(
        "workspace_root", "memory_db_path", "audit_log_path", "policy_file", mode="before"
    )
    @classmethod
    def coerce_path(cls, value: str | Path) -> Path:
        return Path(value)

    @field_validator("auto_approve")
    @classmethod
    def warn_auto_approve(cls, value: bool) -> bool:
        if value:
            import warnings

            warnings.warn(
                "AUTO_APPROVE is enabled — approval gates are bypassed. "
                "Use only in test environments.",
                stacklevel=2,
            )
        return value

    @field_validator("hermes_cli_path", mode="after")
    @classmethod
    def resolve_hermes_cli(cls, value: str) -> str:
        candidate = Path(value).expanduser()
        if candidate.is_file():
            return str(candidate)
        found = shutil.which(value)
        if found:
            return found
        default = Path.home() / ".local/bin/hermes"
        if default.is_file():
            return str(default)
        return value

    @field_validator("openclaw_cli_path", mode="after")
    @classmethod
    def resolve_openclaw_cli(cls, value: str) -> str:
        candidate = Path(value).expanduser()
        if candidate.is_file():
            return str(candidate)
        found = shutil.which(value)
        if found:
            return found
        default = Path.home() / ".local/bin/openclaw"
        if default.is_file():
            return str(default)
        return value

    @field_validator("openclaw_execution_mode")
    @classmethod
    def validate_execution_mode(cls, value: str) -> str:
        allowed = {"auto", "local", "gateway"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"OPENCLAW_EXECUTION_MODE must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("telegram_allowed_chat_ids", mode="before")
    @classmethod
    def parse_telegram_allowed_chat_ids(cls, value: Any) -> list[int]:
        if value is None:
            return []
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            return [int(part.strip()) for part in raw.split(",") if part.strip()]
        if isinstance(value, list):
            return [int(item) for item in value]
        raise ValueError("TELEGRAM_ALLOWED_CHAT_IDS must be a comma-separated string or list")
