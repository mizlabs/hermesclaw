# Security Architecture

How security is structured in HermesClaw.

Pipeline: Hermes produces plans → Validator checks them → Permission signs approved plans → OpenClaw executes under constraints.

Related docs: [philosophy.md](philosophy.md) · [threat-model.md](threat-model.md) · [SECURE_ARCHITECTURE.md](SECURE_ARCHITECTURE.md)

---

## Trust Boundaries

```
┌──────────────────────────────────────────────────────────────────┐
│ Untrusted input                                                  │
│ User text · Hermes / LLM output · injected context               │
└───────────────────────────────┬──────────────────────────────────┘
                                │  boundary 1
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Security Validator                                               │
│ Schema · paths · scopes · policy · security level                │
│ Output: ValidatedPlan (unsigned)                                 │
└───────────────────────────────┬──────────────────────────────────┘
                                │  boundary 2
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Permission Engine                                                │
│ User approval · plan hash · HMAC execution token                 │
│ Output: ValidatedPlan + ExecutionToken                           │
└───────────────────────────────┬──────────────────────────────────┘
                                │  boundary 3
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ OpenClaw Executor                                                │
│ Token check · rate limits · allowlisted commands · workspace FS  │
│ Output: ExecutionReport → Feedback                               │
└──────────────────────────────────────────────────────────────────┘
```

| Component | Executes? | Role |
|-----------|-----------|------|
| Hermes | No | Planner; output is untrusted |
| Security Validator | No | Mandatory gate before any action |
| Permission Engine | No | Approval and signing |
| OpenClaw | Yes, constrained | Only signed, validated plans |

---

## Threat Model (short)

Full write-up: [threat-model.md](threat-model.md)

| Scenario | Mitigation |
|----------|------------|
| Malicious or injected prompts | Schema checks, forbidden top-level fields |
| Hallucinated actions (`delete_file`) | Closed action-type enum |
| Path traversal | PathGuard, resolved paths, denied system dirs |
| Plan changed after validation | SHA256 plan hash + HMAC signature |
| Replay of old tokens | Expiry, `validation_id` and `task_id` binding |
| Runaway retries | Rate limits, max retry count in pipeline |
| Audit log edits | Hash-chained append-only JSONL |

**Not in scope:** compromised host OS, leaked `PLAN_SIGNING_SECRET`.

---

## Execution Flow

```
User intent
    → Hermes (TaskPlan JSON)
    → SecurityValidator.validate()
    → PermissionGateway (approve + sign)
    → OpenClaw (verify token, execute)
    → FeedbackEngine (retry / replan / done)
```

Code: `controller/pipeline.py`

---

## What the Validator Checks

When `SecurityValidator.validate()` returns `valid: true`:

1. Plan matches `TaskPlan` / `schemas/task_plan.schema.json`
2. No forbidden plan fields (`shell`, `bash`, etc.)
3. Action types are in the allowlist (no invented types)
4. Paths resolve inside the workspace; sensitive paths are blocked
5. Each action has the required permission scopes
6. `config/policy.yaml` rules pass
7. `exec` actions use allowlisted commands only
8. A security level is assigned (Safe → Critical)
9. Failures return structured explanations

The validator does not execute anything. It either produces `ValidatedPlan` or rejects with reasons.

Code: `security/security_validator.py`

---

## Plan Signing

After validation and approval:

```
ValidatedPlan (unsigned)
    → canonical JSON (sorted keys, no execution_token field)
    → SHA256 → plan_hash
    → HMAC-SHA256(plan_hash, PLAN_SIGNING_SECRET) → signature
    → ExecutionToken attached to plan
```

OpenClaw checks before running:

1. `validation_id` and `task_id` match the plan
2. Token is not expired
3. Recomputed hash matches `plan_hash`
4. HMAC verifies

Changing any signed field invalidates the token.

Code: `security/plan_signing.py` · Schema: `schemas/execution_token.schema.json`

---

## Replay Protection

| Control | Behavior |
|---------|----------|
| Token TTL | Default 300 seconds; expired tokens rejected |
| `validation_id` | Bound to one validation run |
| `task_id` | Bound to one plan instance |
| Plan hash | Any content change breaks the signature |
| Rate limits | Caps actions per minute and parallel tasks |

---

## Audit Log

Append-only JSONL with hash chaining:

```
Entry N:
  prev_hash  = previous entry_hash (GENESIS for first entry)
  entry_hash = SHA256(canonical entry without entry_hash)
```

- New entries only; existing lines are not rewritten
- Editing an entry breaks `verify_chain()`
- Secrets are redacted before write

Code: `security/audit.py`

---

## Rate Limits

From `config/policy.yaml`:

```yaml
limits:
  max_actions_per_minute: 20
  max_parallel_tasks: 3
```

Enforced in the OpenClaw gateway to limit runaway loops.

Code: `security/rate_limiter.py`

---

## JSON Schemas

Wire formats for tools and integrations:

| File | Use |
|------|-----|
| `schemas/task_plan.schema.json` | Hermes output |
| `schemas/validated_plan.schema.json` | Post-validation plan |
| `schemas/execution_token.schema.json` | Signed token |
| `schemas/validation_result.schema.json` | Validator response |
| `schemas/rejection_explanation.schema.json` | Rejection detail |

Regenerate from Pydantic: `python scripts/export_schemas.py`

---

## Security Levels

| Level | Typical actions |
|-------|-----------------|
| Safe | `list_files` |
| Elevated | `create_folder`, `move_file`, `copy_file` |
| Dangerous | Desktop control (denied by default) |
| Critical | `exec` (allowlisted commands only) |

Higher levels map to stricter policy and confirmation requirements.

Code: `models/security_levels.py`

---

## Non-Goals

This project is not:

- An unrestricted autonomous agent
- A desktop chat companion with shell access
- Shell-first automation
- A system that executes planner output without validation

The intended model is policy-constrained local execution with an explicit audit trail.
