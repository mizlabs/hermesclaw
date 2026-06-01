"""Policy engine — configurable enterprise-grade security rules."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog
import yaml
from pydantic import BaseModel

from hermes_openclaw.models.scopes import PermissionScope
from hermes_openclaw.models.tasks import ActionType
from hermes_openclaw.security.rate_limiter import RateLimitConfig

logger = structlog.get_logger()


class PolicyAction(StrEnum):
    DENY = "deny"
    ALLOW = "allow"
    REQUIRE_CONFIRMATION = "require_confirmation"


class PolicyRule(BaseModel):
    action: PolicyAction
    scope: str
    reason: str = ""


class PolicyDecision(BaseModel):
    allowed: bool
    requires_confirmation: bool = False
    reason: str = ""
    matched_rule: str = ""


# Built-in defaults used when no policy file is present.
DEFAULT_RULES: list[PolicyRule] = [
    PolicyRule(
        action=PolicyAction.DENY,
        scope="filesystem.delete",
        reason="File deletion is not permitted by policy",
    ),
    PolicyRule(
        action=PolicyAction.DENY,
        scope="filesystem.delete.system",
        reason="System path access is forbidden",
    ),
    PolicyRule(
        action=PolicyAction.DENY,
        scope="desktop.control",
        reason="Desktop control requires explicit opt-in",
    ),
    PolicyRule(
        action=PolicyAction.DENY,
        scope="network.enabled",
        reason="Network access is disabled by default",
    ),
    PolicyRule(
        action=PolicyAction.REQUIRE_CONFIRMATION,
        scope="terminal.restricted",
        reason="Terminal commands require user approval",
    ),
    PolicyRule(
        action=PolicyAction.REQUIRE_CONFIRMATION,
        scope="filesystem.write",
        reason="Filesystem writes require confirmation",
    ),
    PolicyRule(
        action=PolicyAction.ALLOW,
        scope="filesystem.read",
        reason="Read within workspace is permitted",
    ),
]


class PolicyEngine:
    """
    Evaluates permission scopes against configurable policy rules.

    Example policy:
        deny: filesystem.delete.system
        require_confirmation: terminal.execute
        allow: filesystem.read.workspace
    """

    def __init__(self, rules: list[PolicyRule] | None = None) -> None:
        self._rules = rules or list(DEFAULT_RULES)

    @classmethod
    def from_yaml(cls, path: Path) -> PolicyEngine:
        if not path.exists():
            logger.warning("policy_file_missing", path=str(path))
            return cls()
        with path.open(encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        rules = cls._parse_rules(data.get("rules", []))
        return cls(rules)

    @staticmethod
    def load_rate_limits(path: Path) -> RateLimitConfig:
        if not path.exists():
            return RateLimitConfig()
        with path.open(encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        limits = data.get("limits", {}) or {}
        return RateLimitConfig(
            max_actions_per_minute=int(limits.get("max_actions_per_minute", 20)),
            max_parallel_tasks=int(limits.get("max_parallel_tasks", 3)),
        )

    @staticmethod
    def _parse_rules(raw: Any) -> list[PolicyRule]:
        """Support list format and grouped deny/require_confirmation/allow format."""
        if isinstance(raw, dict):
            rules: list[PolicyRule] = []
            for scope in raw.get("deny", []) or []:
                rules.append(
                    PolicyRule(
                        action=PolicyAction.DENY,
                        scope=str(scope),
                        reason=f"Denied by policy: {scope}",
                    )
                )
            for scope in raw.get("require_confirmation", []) or []:
                rules.append(
                    PolicyRule(
                        action=PolicyAction.REQUIRE_CONFIRMATION,
                        scope=str(scope),
                        reason=f"Confirmation required: {scope}",
                    )
                )
            for scope in raw.get("allow", []) or []:
                rules.append(
                    PolicyRule(
                        action=PolicyAction.ALLOW,
                        scope=str(scope),
                        reason=f"Allowed: {scope}",
                    )
                )
            return rules or list(DEFAULT_RULES)

        if isinstance(raw, list):
            return [PolicyRule.model_validate(r) for r in raw]

        return list(DEFAULT_RULES)

    def evaluate_scope(self, scope: PermissionScope) -> PolicyDecision:
        """Evaluate a single scope against policy rules (first match wins)."""
        scope_str = scope.value
        for rule in self._rules:
            if self._rule_matches(rule.scope, scope_str):
                return self._apply_rule(rule)
        # Default: allow if not explicitly denied
        return PolicyDecision(allowed=True, reason="No matching deny rule")

    def evaluate_action(
        self,
        action_type: ActionType,
        scopes: frozenset[PermissionScope],
        *,
        is_system_path: bool = False,
    ) -> PolicyDecision:
        """Evaluate all scopes required by an action."""
        if is_system_path:
            for rule in self._rules:
                if rule.action == PolicyAction.DENY and "filesystem.delete.system" in rule.scope:
                    return PolicyDecision(
                        allowed=False,
                        reason=rule.reason or "System path access forbidden",
                        matched_rule=rule.scope,
                    )

        requires_confirmation = False
        for scope in scopes:
            decision = self.evaluate_scope(scope)
            if not decision.allowed:
                return decision
            if decision.requires_confirmation:
                requires_confirmation = True

        # Block delete-like action types regardless of scope string
        if action_type.value in ("delete_file", "delete_folder"):
            return PolicyDecision(
                allowed=False,
                reason="Delete operations are forbidden",
                matched_rule="filesystem.delete",
            )

        return PolicyDecision(
            allowed=True,
            requires_confirmation=requires_confirmation,
            reason="Policy checks passed",
        )

    def _rule_matches(self, rule_scope: str, scope: str) -> bool:
        return scope == rule_scope or scope.startswith(rule_scope + ".")

    def _apply_rule(self, rule: PolicyRule) -> PolicyDecision:
        if rule.action == PolicyAction.DENY:
            return PolicyDecision(
                allowed=False,
                reason=rule.reason,
                matched_rule=rule.scope,
            )
        if rule.action == PolicyAction.REQUIRE_CONFIRMATION:
            return PolicyDecision(
                allowed=True,
                requires_confirmation=True,
                reason=rule.reason,
                matched_rule=rule.scope,
            )
        return PolicyDecision(
            allowed=True,
            reason=rule.reason,
            matched_rule=rule.scope,
        )
