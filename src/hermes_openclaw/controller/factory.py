"""Factory for wiring pipeline components with security dependencies."""

from __future__ import annotations

from pathlib import Path

from hermes_openclaw.config import Settings
from hermes_openclaw.controller.orchestrator import Orchestrator
from hermes_openclaw.controller.pipeline import AgentPipeline
from hermes_openclaw.feedback.engine import FeedbackEngine
from hermes_openclaw.hermes.adapter import CliHermesAdapter, HermesAdapter, MockHermesAdapter
from hermes_openclaw.openclaw.adapter import OpenClawAdapter
from hermes_openclaw.security.approval_gate import ApprovalGate
from hermes_openclaw.security.audit import AuditLogger
from hermes_openclaw.security.command_policy import CommandPolicy
from hermes_openclaw.security.network_policy import NetworkPolicy
from hermes_openclaw.security.path_guard import PathGuard
from hermes_openclaw.security.permission_engine import PermissionEngine
from hermes_openclaw.security.permission_gateway import PermissionGateway
from hermes_openclaw.security.plan_signing import PlanSigner
from hermes_openclaw.security.policy_engine import PolicyEngine
from hermes_openclaw.security.rate_limiter import ExecutionRateLimiter
from hermes_openclaw.security.security_validator import SecurityValidator


def _build_core(
    settings: Settings,
) -> tuple[
    AuditLogger,
    PermissionEngine,
    PermissionGateway,
    OpenClawAdapter,
    FeedbackEngine,
    ExecutionRateLimiter,
    PlanSigner,
]:
    workspace = settings.workspace_root.resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    path_guard = PathGuard(workspace_root=workspace)
    audit = AuditLogger(settings.audit_log_path)
    policy_path = Path(settings.policy_file)
    policy_engine = PolicyEngine.from_yaml(policy_path)
    rate_limits = PolicyEngine.load_rate_limits(policy_path)
    rate_limiter = ExecutionRateLimiter(rate_limits)
    plan_signer = PlanSigner(settings.plan_signing_secret, token_ttl_sec=settings.token_ttl_sec)

    security_validator = SecurityValidator(
        path_guard=path_guard,
        command_policy=CommandPolicy(),
        policy_engine=policy_engine,
    )
    approval = ApprovalGate(auto_approve=settings.auto_approve or settings.dry_run)
    permission_engine = PermissionEngine(security_validator, approval, audit, plan_signer)
    permission_gateway = PermissionGateway(permission_engine)
    openclaw = OpenClawAdapter(
        path_guard=path_guard,
        command_policy=CommandPolicy(),
        audit_logger=audit,
        plan_signer=plan_signer,
        rate_limiter=rate_limiter,
        dry_run=settings.dry_run,
        execution_timeout_sec=settings.execution_timeout_sec,
        gateway_url=settings.openclaw_gateway_url,
        gateway_token=settings.openclaw_gateway_token,
        gateway_session_key=settings.openclaw_gateway_session_key,
        gateway_timeout_sec=settings.openclaw_gateway_timeout_sec,
        execution_mode=settings.openclaw_execution_mode,
        require_signed_token=settings.require_signed_token,
        openclaw_cli_path=settings.openclaw_cli_path,
        openclaw_agent_execution=settings.openclaw_agent_execution,
        workspace_root=workspace,
    )
    feedback = FeedbackEngine(audit, max_retries=settings.max_retry_attempts)
    return (
        audit,
        permission_engine,
        permission_gateway,
        openclaw,
        feedback,
        rate_limiter,
        plan_signer,
    )


def build_hermes_adapter(settings: Settings) -> HermesAdapter:
    if settings.hermes_mock_mode:
        return MockHermesAdapter()
    return CliHermesAdapter(
        cli_path=settings.hermes_cli_path,
        workspace_root=str(settings.workspace_root.resolve()),
    )


def build_orchestrator(settings: Settings) -> Orchestrator:
    audit, _, permission_gateway, openclaw, _, _, _ = _build_core(settings)
    return Orchestrator(permission_gateway, openclaw, audit)


def build_pipeline(settings: Settings) -> AgentPipeline:
    audit, _, permission_gateway, openclaw, feedback, _, _ = _build_core(settings)
    hermes = build_hermes_adapter(settings)
    return AgentPipeline(hermes, permission_gateway, openclaw, feedback, audit)


def build_network_policy(settings: Settings) -> NetworkPolicy:
    return NetworkPolicy(network_enabled=settings.network_enabled)
