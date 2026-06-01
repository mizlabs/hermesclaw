"""Signed plan hashing — validator-signed execution tokens prevent tampering."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

from hermes_openclaw.models.signing import ExecutionToken
from hermes_openclaw.models.validation import ValidatedPlan


class PlanSigner:
    """Sign ValidatedPlan after approval; OpenClaw verifies before execute."""

    def __init__(self, secret: str, *, token_ttl_sec: int = 300) -> None:
        if not secret or secret == "CHANGE_ME_IN_PRODUCTION":  # noqa: S105
            import warnings

            warnings.warn(
                "Using default PLAN_SIGNING_SECRET — set a strong secret in production.",
                stacklevel=2,
            )
        self._secret = secret.encode("utf-8")
        self._ttl = token_ttl_sec

    def hash_plan(self, validated: ValidatedPlan) -> str:
        payload = validated.model_dump(mode="json", exclude_none=True, exclude={"execution_token"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def sign(self, validated: ValidatedPlan) -> ExecutionToken:
        plan_hash = self.hash_plan(validated)
        signature = hmac.new(self._secret, plan_hash.encode("utf-8"), hashlib.sha256).hexdigest()
        now = datetime.now(UTC)
        return ExecutionToken(
            plan_hash=plan_hash,
            signature=signature,
            validation_id=validated.validation_id,
            task_id=validated.plan.task_id,
            issued_at=now,
            expires_at=now + timedelta(seconds=self._ttl),
        )

    def verify(self, validated: ValidatedPlan, token: ExecutionToken) -> bool:
        if token.validation_id != validated.validation_id:
            return False
        if token.task_id != validated.plan.task_id:
            return False
        if datetime.now(UTC) > token.expires_at:
            return False
        expected_hash = self.hash_plan(validated)
        if not hmac.compare_digest(token.plan_hash, expected_hash):
            return False
        expected_sig = hmac.new(
            self._secret, expected_hash.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(token.signature, expected_sig)
