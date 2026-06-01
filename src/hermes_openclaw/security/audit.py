"""Immutable audit logging — append-only, hash-chained, tamper-detectable."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(api[_-]?key|token|secret|password|credential)\s*[:=]\s*\S+", re.I),
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
]

GENESIS_HASH = "0" * 64


@dataclass
class AuditRecord:
    audit_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    event: str = ""
    task_id: str | None = None
    actor: str = "system"
    details: dict[str, Any] = field(default_factory=dict)
    outcome: str = "pending"
    prev_hash: str = GENESIS_HASH
    entry_hash: str = ""


class AuditLogger:
    """Append-only audit trail with hash chaining for tamper detection."""

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = self._load_last_hash()

    def record(
        self,
        event: str,
        *,
        task_id: str | None = None,
        actor: str = "system",
        details: dict[str, Any] | None = None,
        outcome: str = "pending",
    ) -> AuditRecord:
        entry = AuditRecord(
            event=event,
            task_id=task_id,
            actor=actor,
            details=self._redact(details or {}),
            outcome=outcome,
            prev_hash=self._last_hash,
        )
        entry.entry_hash = self._compute_hash(entry)
        self._append(entry)
        self._last_hash = entry.entry_hash
        return entry

    def read_all(self) -> list[dict[str, Any]]:
        if not self._log_path.exists():
            return []
        records = []
        for line in self._log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records

    def verify_chain(self) -> tuple[bool, str]:
        """Verify hash chain integrity — returns (valid, message)."""
        records = self.read_all()
        prev = GENESIS_HASH
        for i, rec in enumerate(records):
            if rec.get("prev_hash") != prev:
                return False, f"Chain broken at entry {i}: prev_hash mismatch"
            expected = self._compute_hash_from_dict(rec, prev)
            if rec.get("entry_hash") != expected:
                return False, f"Tamper detected at entry {i}: entry_hash invalid"
            prev = rec["entry_hash"]
        return True, f"Chain valid ({len(records)} entries)"

    def _load_last_hash(self) -> str:
        records = self.read_all()
        if not records:
            return GENESIS_HASH
        return str(records[-1].get("entry_hash", GENESIS_HASH))

    def _compute_hash(self, entry: AuditRecord) -> str:
        return self._compute_hash_from_dict(asdict(entry), entry.prev_hash)

    def _compute_hash_from_dict(self, data: dict[str, Any], prev_hash: str) -> str:
        payload = {k: v for k, v in data.items() if k != "entry_hash"}
        payload["prev_hash"] = prev_hash
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _redact(self, data: dict[str, Any]) -> dict[str, Any]:
        serialized = json.dumps(data, default=str)
        for pattern in _SECRET_PATTERNS:
            serialized = pattern.sub("[REDACTED]", serialized)
        return cast(dict[str, Any], json.loads(serialized))

    def _append(self, entry: AuditRecord) -> None:
        line = json.dumps(asdict(entry), default=str)
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
