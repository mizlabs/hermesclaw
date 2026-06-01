"""FastAPI application — localhost-only, validated endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from hermes_openclaw.api.dashboard import create_dashboard_router
from hermes_openclaw.config import Settings
from hermes_openclaw.controller.factory import _build_core
from hermes_openclaw.controller.orchestrator import Orchestrator
from hermes_openclaw.models.execution import ExecutionReport
from hermes_openclaw.security.plan_validator import PlanValidationError


class PlanRequest(BaseModel):
    plan: dict[str, Any]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    audit, _, permission_gateway, openclaw, _, rate_limiter, _ = _build_core(settings)
    orchestrator = Orchestrator(permission_gateway, openclaw, audit)

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
    async def execute_plan(request: PlanRequest) -> ExecutionReport:
        try:
            return orchestrator.process_plan(request.plan)
        except PlanValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app
