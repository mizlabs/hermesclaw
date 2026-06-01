"""Tests for hash-chained immutable audit logs and secret redaction."""

import json
from pathlib import Path

from hermes_openclaw.security.audit import GENESIS_HASH, AuditLogger


def test_audit_record_written(tmp_path: Path):
    log_path = tmp_path / "audit.jsonl"
    audit = AuditLogger(log_path)

    record = audit.record("test_event", details={"action": "create_folder"}, outcome="success")

    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["event"] == "test_event"
    assert parsed["audit_id"] == record.audit_id
    assert parsed["entry_hash"]


def test_secrets_redacted(tmp_path: Path):
    log_path = tmp_path / "audit.jsonl"
    audit = AuditLogger(log_path)

    audit.record(
        "login_attempt",
        details={"api_key": "sk-abcdefghijklmnopqrstuvwxyz1234567890"},
        outcome="failure",
    )

    content = log_path.read_text()
    assert "sk-abc" not in content
    assert "[REDACTED]" in content


def test_hash_chain_links_entries(tmp_path: Path):
    log_path = tmp_path / "audit.jsonl"
    audit = AuditLogger(log_path)

    audit.record("event_one", outcome="ok")
    audit.record("event_two", outcome="ok")

    records = audit.read_all()
    assert records[0]["prev_hash"] == GENESIS_HASH
    assert records[1]["prev_hash"] == records[0]["entry_hash"]


def test_verify_chain_passes(tmp_path: Path):
    log_path = tmp_path / "audit.jsonl"
    audit = AuditLogger(log_path)
    audit.record("a", outcome="ok")
    audit.record("b", outcome="ok")
    valid, msg = audit.verify_chain()
    assert valid is True


def test_tamper_detection(tmp_path: Path):
    log_path = tmp_path / "audit.jsonl"
    audit = AuditLogger(log_path)
    audit.record("original", outcome="ok")

    lines = log_path.read_text().strip().split("\n")
    record = json.loads(lines[0])
    record["outcome"] = "tampered"
    log_path.write_text(json.dumps(record) + "\n")

    audit2 = AuditLogger(log_path)
    valid, msg = audit2.verify_chain()
    assert valid is False
