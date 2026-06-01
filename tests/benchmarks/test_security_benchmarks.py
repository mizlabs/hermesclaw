"""Performance checks for validator, signing, audit, and rate limits.

Run: pytest tests/benchmarks/ -v -s
     python scripts/run_benchmarks.py
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import pytest

from hermes_openclaw.models.scopes import PermissionScope
from hermes_openclaw.models.tasks import TaskAction, TaskPlan
from hermes_openclaw.models.validation import ValidatedAction, ValidatedPlan
from hermes_openclaw.security.audit import AuditLogger
from hermes_openclaw.security.command_policy import CommandPolicy
from hermes_openclaw.security.path_guard import PathGuard
from hermes_openclaw.security.plan_signing import PlanSigner
from hermes_openclaw.security.policy_engine import PolicyEngine
from hermes_openclaw.security.rate_limiter import (
    ExecutionRateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
)
from hermes_openclaw.security.security_validator import SecurityValidator

ITERATIONS = 100
# Generous ceilings for CI variance — benchmarks assert upper bounds, not exact timing.
MAX_VALIDATOR_MS = 50.0
MAX_SIGN_MS = 5.0
MAX_AUDIT_RECORD_MS = 10.0
MAX_CHAIN_VERIFY_MS = 100.0


def _percentile_ms(samples: list[float], p: float) -> float:
    ordered = sorted(samples)
    idx = int(len(ordered) * p / 100)
    return ordered[min(idx, len(ordered) - 1)]


def _bench(fn, iterations: int = ITERATIONS) -> dict[str, float]:
    samples: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return {
        "mean_ms": statistics.mean(samples),
        "p50_ms": _percentile_ms(samples, 50),
        "p95_ms": _percentile_ms(samples, 95),
        "max_ms": max(samples),
    }


@pytest.fixture
def validator(tmp_path: Path) -> SecurityValidator:
    guard = PathGuard(workspace_root=tmp_path)
    return SecurityValidator(guard, CommandPolicy(), PolicyEngine())


def _sample_plan_dict() -> dict:
    return {
        "intent": "organize workspace files into folders",
        "actions": [
            {"type": "create_folder", "destination": "docs", "scope": "filesystem.write"},
            {"type": "list_files", "source": ".", "scope": "filesystem.read"},
            {
                "type": "move_file",
                "source": "a.txt",
                "destination": "docs/a.txt",
                "scope": "filesystem.write",
            },
        ],
        "risk_level": "medium",
    }


def _validated_plan() -> ValidatedPlan:
    action = TaskAction(type="list_files", source=".", scope="filesystem.read")
    return ValidatedPlan(
        plan=TaskPlan(intent="bench", actions=[action], dry_run=True),
        actions=[ValidatedAction(action=action, scope=PermissionScope.FILESYSTEM_READ)],
    )


class TestSecurityBenchmarks:
    """Upper-bound latency checks for security-critical paths."""

    def test_validator_latency(self, validator: SecurityValidator, capsys: pytest.CaptureFixture):
        plan = _sample_plan_dict()
        stats = _bench(lambda: validator.validate_sync(plan))
        print(f"\n[BENCH] validator_latency: {json.dumps(stats)}")
        p95 = stats["p95_ms"]
        assert p95 < MAX_VALIDATOR_MS, f"p95 {p95:.2f}ms exceeds {MAX_VALIDATOR_MS}ms"

    def test_signing_overhead(self, capsys: pytest.CaptureFixture):
        signer = PlanSigner("benchmark-secret-key")
        plan = _validated_plan()

        def sign_verify():
            token = signer.sign(plan)
            signed = plan.model_copy(update={"execution_token": token})
            assert signer.verify(signed, token)

        stats = _bench(sign_verify)
        print(f"\n[BENCH] signing_overhead: {json.dumps(stats)}")
        assert stats["p95_ms"] < MAX_SIGN_MS

    def test_audit_chain_performance(self, tmp_path: Path, capsys: pytest.CaptureFixture):
        log_path = tmp_path / "bench_audit.jsonl"
        audit = AuditLogger(log_path)

        def record():
            audit.record("bench_event", details={"i": 1}, outcome="ok")

        stats = _bench(record, iterations=50)
        print(f"\n[BENCH] audit_record: {json.dumps(stats)}")
        assert stats["p95_ms"] < MAX_AUDIT_RECORD_MS

        # Append 200 entries then verify chain
        for i in range(200):
            audit.record("chain", details={"seq": i}, outcome="ok")

        start = time.perf_counter()
        valid, _ = audit.verify_chain()
        verify_ms = (time.perf_counter() - start) * 1000
        print(f'\n[BENCH] audit_chain_verify_200: {{"verify_ms": {verify_ms:.3f}}}')
        assert valid is True
        assert verify_ms < MAX_CHAIN_VERIFY_MS

    def test_rate_limit_effectiveness(self, capsys: pytest.CaptureFixture):
        config = RateLimitConfig(max_actions_per_minute=10, max_parallel_tasks=2)
        limiter = ExecutionRateLimiter(config)

        allowed = 0
        blocked = 0
        for _ in range(15):
            try:
                limiter.record_action()
                allowed += 1
            except RateLimitExceeded:
                blocked += 1

        print(f"\n[BENCH] rate_limit: allowed={allowed}, blocked={blocked}")
        assert allowed == 10
        assert blocked == 5

        # Parallel task slots
        limiter.check_and_acquire_task_slot()
        limiter.check_and_acquire_task_slot()
        with pytest.raises(RateLimitExceeded):
            limiter.check_and_acquire_task_slot()
        limiter.release_task_slot()

    def test_retry_replan_stability(
        self, validator: SecurityValidator, capsys: pytest.CaptureFixture
    ):
        """Repeated validation of same plan should be deterministic and fast."""
        plan = _sample_plan_dict()
        results: list[bool] = []
        stats = _bench(
            lambda: results.append(validator.validate_sync(plan).valid) or True,
            iterations=50,
        )
        print(f"\n[BENCH] retry_replan_stability: {json.dumps(stats)}, all_valid={all(results)}")
        assert all(results)
        assert stats["p95_ms"] < MAX_VALIDATOR_MS
