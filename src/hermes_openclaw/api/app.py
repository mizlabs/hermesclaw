"""FastAPI application with authenticated execution and integration webhooks."""

from __future__ import annotations

from typing import Annotated, Any

import httpx
import structlog
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from hermes_openclaw.api.dashboard import create_dashboard_router
from hermes_openclaw.config import Settings
from hermes_openclaw.controller.factory import _build_core, build_pipeline
from hermes_openclaw.controller.orchestrator import Orchestrator
from hermes_openclaw.models.execution import ExecutionReport
from hermes_openclaw.models.feedback import PipelineResult
from hermes_openclaw.security.plan_validator import PlanValidationError

logger = structlog.get_logger()


class PlanRequest(BaseModel):
    plan: dict[str, Any]


class IntentRequest(BaseModel):
    intent: str = Field(min_length=1, max_length=2000)
    safe_mode: bool = False
    dry_run: bool = False


def _format_result_for_chat(result: PipelineResult, safe_mode: bool) -> str:
    lines = [
        f"Intent: {result.intent}",
        f"Safe mode: {'on' if safe_mode else 'off'}",
        f"Success: {result.success}",
    ]
    if result.message:
        lines.append(f"Message: {result.message}")
    report = result.execution_report
    if report is not None:
        lines.append(f"Status: {report.status.value}")
        for action_result in report.results:
            lines.append(
                f"- {action_result.action_type}: {action_result.status.value} -> {action_result.message}"
            )
    return "\n".join(lines)


def _send_telegram_message(bot_token: str, chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
    response.raise_for_status()


def _extract_telegram_message(update: dict[str, Any]) -> tuple[int | None, str]:
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return None, ""
    chat = message.get("chat")
    if not isinstance(chat, dict):
        return None, ""
    chat_id = chat.get("id")
    text = message.get("text")
    if not isinstance(chat_id, int) or not isinstance(text, str):
        return None, ""
    return chat_id, text.strip()


def _parse_telegram_command(text: str) -> tuple[str, bool]:
    if not text:
        return "", True
    if text == "/start":
        return "", True
    if text.startswith("/safe "):
        return text[6:].strip(), True
    if text.startswith("/run "):
        return text[5:].strip(), False
    return text, True


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    audit, _, permission_gateway, openclaw, _, rate_limiter, _ = _build_core(settings)
    orchestrator = Orchestrator(permission_gateway, openclaw, audit)
    pipeline = build_pipeline(settings)
    safe_pipeline = build_pipeline(settings.model_copy(update={"dry_run": True}))

    expected_token = settings.api_bearer_token.strip()

    async def require_api_auth(
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
        x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    ) -> None:
        if not expected_token:
            return
        if x_api_key and x_api_key.strip() == expected_token:
            return
        if authorization and authorization.startswith("Bearer "):
            supplied = authorization[7:].strip()
            if supplied == expected_token:
                return
        raise HTTPException(status_code=401, detail="Unauthorized")

    app = FastAPI(
        title="HermesClaw",
        description="A security-first open-source local AI agent framework",
        version="0.2.0",
        docs_url="/docs" if settings.api_host == "127.0.0.1" else None,
    )

    app.include_router(create_dashboard_router(audit, rate_limiter))

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "service": "HermesClaw",
            "dashboard": "/dashboard",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        valid, msg = audit.verify_chain()
        return {
            "status": "ok",
            "network_enabled": str(settings.network_enabled),
            "audit_chain": msg if valid else f"INVALID: {msg}",
        }

    @app.post("/plans/execute", response_model=ExecutionReport)
    async def execute_plan(
        request: PlanRequest,
        _: None = Depends(require_api_auth),
    ) -> ExecutionReport:
        try:
            return orchestrator.process_plan(request.plan)
        except PlanValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/intents/execute", response_model=PipelineResult)
    async def execute_intent(
        request: IntentRequest,
        _: None = Depends(require_api_auth),
    ) -> PipelineResult:
        use_safe = request.safe_mode or request.dry_run
        runner = safe_pipeline if use_safe else pipeline
        return runner.run(request.intent)

    @app.post("/integrations/telegram/webhook")
    async def telegram_webhook(
        update: dict[str, Any],
        x_telegram_secret: Annotated[
            str | None,
            Header(alias="X-Telegram-Bot-Api-Secret-Token"),
        ] = None,
    ) -> dict[str, Any]:
        if not settings.telegram_bot_token:
            raise HTTPException(status_code=503, detail="Telegram integration is not configured")
        if settings.telegram_webhook_secret and x_telegram_secret != settings.telegram_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")
        if not settings.network_enabled:
            raise HTTPException(
                status_code=503,
                detail="Network is disabled; Telegram integration requires NETWORK_ENABLED=true",
            )

        chat_id, text = _extract_telegram_message(update)
        if chat_id is None:
            return {"ok": True, "ignored": "unsupported_update"}

        allowed_chat_ids = set(settings.telegram_allowed_chat_ids)
        if allowed_chat_ids and chat_id not in allowed_chat_ids:
            logger.warning("telegram_chat_denied", chat_id=chat_id)
            return {"ok": True, "ignored": "chat_not_allowed"}

        intent, safe_mode = _parse_telegram_command(text)
        if not intent:
            help_text = (
                "HermesClaw bot ready.\n"
                "Use /safe <intent> (default) for dry-run safety.\n"
                "Use /run <intent> for direct execution."
            )
            _send_telegram_message(settings.telegram_bot_token, chat_id, help_text)
            return {"ok": True, "status": "help_sent"}

        runner = safe_pipeline if safe_mode else pipeline
        result = runner.run(intent)
        message = _format_result_for_chat(result, safe_mode=safe_mode)

        try:
            _send_telegram_message(settings.telegram_bot_token, chat_id, message)
        except httpx.HTTPError as exc:
            logger.exception("telegram_send_failed", chat_id=chat_id, error=str(exc))
            raise HTTPException(status_code=502, detail="Failed to send Telegram response") from exc

        return {"ok": True, "status": "processed", "safe_mode": safe_mode}

    return app
