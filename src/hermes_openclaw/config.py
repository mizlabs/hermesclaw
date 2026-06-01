"""Application configuration — all secrets via environment variables."""

from __future__ import annotations

from pathlib import Path

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

    # OpenClaw (executor — sandboxed)
    openclaw_gateway_url: str = "http://localhost:18789"
    openclaw_workspace: str = "./workspace"
    openclaw_cli_path: str = "openclaw"

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
    plan_signing_secret: str = Field(default="CHANGE_ME_IN_PRODUCTION")  # noqa: S105
    token_ttl_sec: int = Field(default=300, ge=60, le=3600)
    require_signed_token: bool = True

    # Orchestrator
    log_level: str = "INFO"
    memory_db_path: Path = Path("./data/memory.db")
    audit_log_path: Path = Path("./logs/audit.jsonl")

    # API (binds localhost only by default)
    api_host: str = "127.0.0.1"
    api_port: int = 8000

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
