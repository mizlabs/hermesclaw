"""Structured rejection explanations — every blocked task is explainable."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class RejectionCategory(StrEnum):
    SCHEMA = "schema_validation"
    BLOCKED_ACTION = "action_not_allowlisted"
    PATH = "path_outside_workspace"
    SCOPE = "permission_scope_denied"
    POLICY = "policy_rule_violation"
    COMMAND = "command_not_allowlisted"
    RATE_LIMIT = "rate_limit_exceeded"
    FORBIDDEN_FIELD = "forbidden_field_in_plan"
    SECURITY_LEVEL = "security_level_exceeded"
    SIGNATURE = "invalid_execution_token"
    HALLUCINATION = "hallucinated_action"


class RejectionExplanation(BaseModel):
    """Human-readable explanation for every rejected plan or action."""

    rejected: bool = True
    category: RejectionCategory
    reasons: list[str] = Field(default_factory=list)
    human_readable: str = ""
    blocked_action: str | None = None
    policy_rule: str | None = None

    @classmethod
    def build(
        cls,
        category: RejectionCategory,
        *,
        reasons: list[str] | None = None,
        blocked_action: str | None = None,
        policy_rule: str | None = None,
    ) -> RejectionExplanation:
        reason_list = reasons or []
        lines = ["Rejected because:"]
        for r in reason_list:
            lines.append(f"- {r}")
        if not reason_list:
            lines.append(f"- {category.value.replace('_', ' ')}")
        return cls(
            category=category,
            reasons=reason_list,
            human_readable="\n".join(lines),
            blocked_action=blocked_action,
            policy_rule=policy_rule,
        )
