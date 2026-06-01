"""Security levels — scalable policy tiers for constrained autonomy."""

from __future__ import annotations

from enum import StrEnum

from hermes_openclaw.models.scopes import PermissionScope
from hermes_openclaw.models.tasks import ActionType, RiskLevel


class SecurityLevel(StrEnum):
    SAFE = "safe"  # Read-only
    ELEVATED = "elevated"  # File modifications
    DANGEROUS = "dangerous"  # Desktop control
    CRITICAL = "critical"  # Terminal / network


def classify_plan(
    *,
    risk_level: RiskLevel,
    action_types: set[ActionType],
    scopes: set[PermissionScope],
) -> SecurityLevel:
    """Derive the effective security level from plan content — deterministic, not LLM-driven."""
    if ActionType.EXEC in action_types or PermissionScope.TERMINAL_RESTRICTED in scopes:
        return SecurityLevel.CRITICAL
    if PermissionScope.DESKTOP_CONTROL in scopes:
        return SecurityLevel.DANGEROUS
    if any(
        t in action_types
        for t in (ActionType.MOVE_FILE, ActionType.COPY_FILE, ActionType.CREATE_FOLDER)
    ):
        return SecurityLevel.ELEVATED
    if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        return SecurityLevel.DANGEROUS
    if risk_level == RiskLevel.MEDIUM:
        return SecurityLevel.ELEVATED
    return SecurityLevel.SAFE
