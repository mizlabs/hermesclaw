"""Security Validator — the trust boundary between Hermes and OpenClaw."""

from __future__ import annotations

import json
from typing import Any

import structlog
from pydantic import ValidationError

from hermes_openclaw.models.explainability import RejectionCategory, RejectionExplanation
from hermes_openclaw.models.scopes import (
    ACTION_REQUIRED_SCOPES,
    BLOCKED_ACTION_TYPES,
    DEFAULT_GRANTED_SCOPES,
    PermissionScope,
)
from hermes_openclaw.models.security_levels import classify_plan
from hermes_openclaw.models.tasks import ActionType, RiskLevel, TaskAction, TaskPlan
from hermes_openclaw.models.validation import ValidatedAction, ValidatedPlan, ValidationResult
from hermes_openclaw.security.command_policy import CommandPolicy, CommandPolicyError
from hermes_openclaw.security.path_guard import PathGuard, PathGuardError
from hermes_openclaw.security.plan_normalizer import normalize_plan_dict
from hermes_openclaw.security.plan_validator import PlanValidationError
from hermes_openclaw.security.policy_engine import PolicyEngine

logger = structlog.get_logger()

_FORBIDDEN_PLAN_KEYS = frozenset(
    {
        "shell",
        "script",
        "raw_command",
        "eval",
        "exec_raw",
        "code",
        "python",
        "bash",
        "exec",
        "subprocess",
    }
)


class SecurityValidator:
    """
    Trust boundary between Hermes and OpenClaw.

    Checks schema, paths, scopes, and policy. Does not execute actions.
    Output is ValidatedPlan or a structured rejection.
    """

    def __init__(
        self,
        path_guard: PathGuard,
        command_policy: CommandPolicy,
        policy_engine: PolicyEngine,
        granted_scopes: frozenset[PermissionScope] | None = None,
        max_actions: int = 50,
    ) -> None:
        self._path_guard = path_guard
        self._command_policy = command_policy
        self._policy = policy_engine
        self._granted_scopes = granted_scopes or DEFAULT_GRANTED_SCOPES
        self._max_actions = max_actions

    async def validate(self, raw: str | dict[str, Any] | TaskPlan) -> ValidationResult:
        """Async validation API — primary entry point."""
        return self.validate_sync(raw)

    def validate_sync(self, raw: str | dict[str, Any] | TaskPlan) -> ValidationResult:
        """Synchronous validation for CLI and tests."""
        try:
            plan = self._parse_raw(raw)
        except PlanValidationError as exc:
            msg = str(exc)
            blocked: str | None = None
            category = RejectionCategory.SCHEMA
            if msg.startswith("Blocked action type:"):
                blocked = msg.split(":", 1)[1].strip()
                category = RejectionCategory.HALLUCINATION
            elif "Forbidden fields" in msg:
                category = RejectionCategory.FORBIDDEN_FIELD
            return self._reject(category, msg, blocked_action=blocked)

        blocked = self._check_blocked_actions(plan)
        if blocked:
            return self._reject(
                RejectionCategory.HALLUCINATION,
                f"Action '{blocked}' is forbidden — Hermes may have hallucinated",
                blocked_action=blocked,
                reasons=[f"action not allowlisted: {blocked}"],
            )

        if len(plan.actions) > self._max_actions:
            return self._reject(
                RejectionCategory.SCHEMA,
                f"Plan exceeds maximum action count ({self._max_actions})",
                reasons=["too many actions in plan"],
            )

        validated_actions: list[ValidatedAction] = []
        policy_requires_confirmation = False

        for action in plan.actions:
            action_result = self._validate_action(action)
            if not action_result.valid or action_result.validated_plan is None:
                return action_result

            validated_action = action_result.validated_plan.actions[0]
            validated_actions.append(validated_action)

            scopes = frozenset(validated_action.required_scopes)
            is_system = self._touches_system_path(validated_action)
            policy_decision = self._policy.evaluate_action(
                action.type, scopes, is_system_path=is_system
            )
            if not policy_decision.allowed:
                return self._reject(
                    RejectionCategory.POLICY,
                    policy_decision.reason,
                    blocked_action=action.type.value,
                    reasons=["policy rule violation", policy_decision.reason],
                    policy_rule=policy_decision.matched_rule,
                )
            if policy_decision.requires_confirmation:
                policy_requires_confirmation = True

        if policy_requires_confirmation:
            object.__setattr__(plan, "requires_confirmation", True)

        action_types = {a.action.type for a in validated_actions}
        plan_scopes = {a.scope for a in validated_actions}
        level = classify_plan(
            risk_level=plan.risk_level,
            action_types=action_types,
            scopes=plan_scopes,
        )

        validated_plan = ValidatedPlan(
            plan=plan,
            actions=validated_actions,
            granted_scopes=sorted(self._granted_scopes, key=lambda s: s.value),
            security_level=level,
        )

        logger.info(
            "security_validation_passed",
            task_id=plan.task_id,
            actions=len(validated_actions),
        )

        return ValidationResult(valid=True, validated_plan=validated_plan, reason="Validated")

    def _parse_raw(self, raw: str | dict[str, Any] | TaskPlan) -> TaskPlan:
        if isinstance(raw, TaskPlan):
            return raw

        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise PlanValidationError(f"Invalid JSON from planner: {exc}") from exc
        else:
            data = raw

        if not isinstance(data, dict):
            raise PlanValidationError("Plan must be a JSON object")

        forbidden = _FORBIDDEN_PLAN_KEYS & data.keys()
        if forbidden:
            raise PlanValidationError(f"Forbidden fields in plan: {forbidden}")

        data = normalize_plan_dict(data)

        for item in data.get("actions", []):
            if isinstance(item, dict):
                action_type = item.get("type") or item.get("action", "")
                if action_type in BLOCKED_ACTION_TYPES:
                    raise PlanValidationError(f"Blocked action type: {action_type}")

        try:
            plan = TaskPlan.model_validate(data)
        except ValidationError as exc:
            raise PlanValidationError(f"Schema validation failed: {exc}") from exc

        self._validate_risk_consistency(plan)
        return plan

    def _check_blocked_actions(self, plan: TaskPlan) -> str | None:
        for action in plan.actions:
            if action.type.value in BLOCKED_ACTION_TYPES:
                return action.type.value
        return None

    def _validate_action(self, action: TaskAction) -> ValidationResult:
        required = ACTION_REQUIRED_SCOPES.get(action.type, frozenset())
        scope = self._resolve_scope(action)

        missing = required - self._granted_scopes
        if missing:
            return self._reject(
                RejectionCategory.SCOPE,
                f"Missing scopes: {', '.join(s.value for s in missing)}",
                blocked_action=action.type.value,
                reasons=[f"permission scope denied: {s.value}" for s in missing],
            )

        resolved_source: str | None = None
        resolved_destination: str | None = None

        try:
            if action.source:
                resolved_source = str(self._path_guard.resolve(action.source))
            if action.destination:
                resolved_destination = str(self._path_guard.resolve(action.destination))
        except PathGuardError as exc:
            return self._reject(
                RejectionCategory.PATH,
                str(exc),
                blocked_action=action.type.value,
                reasons=["path outside workspace or sensitive path blocked"],
            )

        if action.type == ActionType.EXEC and action.command:
            try:
                self._command_policy.validate(action.command, action.args)
            except CommandPolicyError as exc:
                return self._reject(
                    RejectionCategory.COMMAND,
                    str(exc),
                    blocked_action=action.type.value,
                    reasons=["command not allowlisted"],
                )

        validated = ValidatedAction(
            action=action,
            scope=scope,
            required_scopes=sorted(required, key=lambda s: s.value),
            resolved_source=resolved_source,
            resolved_destination=resolved_destination,
        )
        stub_plan = ValidatedPlan(plan=TaskPlan(intent="_", actions=[action]), actions=[validated])
        return ValidationResult(valid=True, validated_plan=stub_plan)

    def _resolve_scope(self, action: TaskAction) -> PermissionScope:
        if action.scope:
            try:
                return PermissionScope(action.scope)
            except ValueError as exc:
                raise PlanValidationError(f"Unknown permission scope: {action.scope}") from exc
        required = ACTION_REQUIRED_SCOPES.get(action.type, frozenset())
        if len(required) == 1:
            return next(iter(required))
        # Multi-scope actions use primary write scope
        if PermissionScope.FILESYSTEM_WRITE in required:
            return PermissionScope.FILESYSTEM_WRITE
        return next(iter(required)) if required else PermissionScope.FILESYSTEM_READ

    def _touches_system_path(self, validated: ValidatedAction) -> bool:
        system_prefixes = ("/etc", "/usr", "/bin", "/sbin", "/System", "/Library")
        for path in (validated.resolved_source, validated.resolved_destination):
            if path and any(path.startswith(p) for p in system_prefixes):
                return True
        return False

    def _reject(
        self,
        category: RejectionCategory,
        reason: str,
        *,
        blocked_action: str | None = None,
        reasons: list[str] | None = None,
        policy_rule: str | None = None,
    ) -> ValidationResult:
        explanation = RejectionExplanation.build(
            category,
            reasons=reasons or [reason],
            blocked_action=blocked_action,
            policy_rule=policy_rule,
        )
        return ValidationResult(
            valid=False,
            errors=reasons or [reason],
            blocked_action=blocked_action,
            reason=reason,
            explanation=explanation,
        )

    def _validate_risk_consistency(self, plan: TaskPlan) -> None:
        has_exec = any(a.type == ActionType.EXEC for a in plan.actions)
        has_file_ops = any(
            a.type in (ActionType.MOVE_FILE, ActionType.COPY_FILE, ActionType.CREATE_FOLDER)
            for a in plan.actions
        )
        if has_exec and plan.risk_level == RiskLevel.LOW:
            raise PlanValidationError("Plans with exec actions cannot be classified as low risk")
        if has_file_ops and plan.risk_level == RiskLevel.LOW:
            raise PlanValidationError("Plans with file operations cannot be classified as low risk")
