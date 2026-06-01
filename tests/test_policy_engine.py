"""Tests for the configurable policy engine."""

from hermes_openclaw.models.scopes import PermissionScope
from hermes_openclaw.models.tasks import ActionType
from hermes_openclaw.security.policy_engine import PolicyAction, PolicyEngine, PolicyRule


def test_deny_filesystem_delete():
    engine = PolicyEngine()
    decision = engine.evaluate_scope(PermissionScope.FILESYSTEM_DELETE)
    assert decision.allowed is False


def test_allow_filesystem_read():
    engine = PolicyEngine()
    decision = engine.evaluate_scope(PermissionScope.FILESYSTEM_READ)
    assert decision.allowed is True


def test_require_confirmation_for_terminal():
    engine = PolicyEngine()
    decision = engine.evaluate_scope(PermissionScope.TERMINAL_RESTRICTED)
    assert decision.allowed is True
    assert decision.requires_confirmation is True


def test_grouped_yaml_format():
    rules = PolicyEngine._parse_rules(
        {
            "deny": ["filesystem.delete.system"],
            "require_confirmation": ["filesystem.write"],
            "allow": ["filesystem.read.workspace"],
        }
    )
    assert any(r.action == PolicyAction.DENY for r in rules)
    assert any(r.action == PolicyAction.REQUIRE_CONFIRMATION for r in rules)


def test_custom_deny_rule():
    engine = PolicyEngine(
        rules=[
            PolicyRule(
                action=PolicyAction.DENY,
                scope="applications.launch",
                reason="Apps disabled",
            )
        ]
    )
    decision = engine.evaluate_action(
        ActionType.LAUNCH_APP, frozenset({PermissionScope.APPLICATIONS_LAUNCH})
    )
    assert decision.allowed is False
