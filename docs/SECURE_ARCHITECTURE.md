# Secure Multi-Agent Architecture

How Hermes, the validator, and OpenClaw divide responsibility.

## Planner — Hermes

Hermes produces structured JSON plans. It does not execute commands or touch the filesystem.

**It handles:**

- Parsing user intent
- Breaking work into steps
- Replanning after structured failure feedback

**It does not:**

- Run shell commands
- Call system APIs directly
- Control the desktop
- Emit executable code

Plans with raw code blocks or fields like `shell`, `bash`, `script`, `exec`, or `subprocess` are rejected at validation.

**Example:**

```json
{
  "intent": "workspace_setup",
  "risk_level": "medium",
  "tasks": [
    {
      "action": "move_files",
      "source": "~/Downloads/*.pdf",
      "destination": "~/Documents/PDFs"
    }
  ]
}
```

---

## Security Validator

Mandatory gate between Hermes and OpenClaw. LLM output is untrusted; this layer checks it before anything runs.

**Checks:**

- Schema and required fields
- Path resolution and workspace bounds
- Permission scopes
- Unknown or hallucinated action types
- Policy rules from `config/policy.yaml`
- Security level and confirmation flags

**Typical rejections:**

- Shell or subprocess fields in the plan JSON
- Paths outside the workspace or under denied dirs (`/etc`, `~/.ssh`, etc.)
- Action types not in the allowlist
- Commands not on the allowlist

Output is a `ValidatedPlan` or a structured rejection — never raw planner JSON passed through.

**Code:** `src/hermes_openclaw/security/security_validator.py`

---

## Policy Engine

Configurable runtime security rules at `config/policy.yaml`.

**Capabilities:** allow rules, deny rules, confirmation requirements, execution constraints, workspace restrictions.

**Example:**

```yaml
rules:
  deny:
    - filesystem.delete.system
    - terminal.unrestricted
  require_confirmation:
    - filesystem.write
    - applications.launch
  allow:
    - filesystem.read.workspace
```

Policies are deterministic and enforced independently from the LLM.

**Implementation:** `src/hermes_openclaw/security/policy_engine.py`

---

## Permission Engine

Handles user authorization before execution. High-risk operations require explicit user approval.

**Examples:** filesystem writes, application launching, desktop control, network access, terminal execution.

**Implementation:** `src/hermes_openclaw/security/permission_engine.py`

---

## Execution Layer — OpenClaw

OpenClaw acts as a restricted execution gateway. It NEVER receives raw LLM output.

OpenClaw accepts ONLY `ValidatedPlan` objects with typed, allowlisted actions.

**Implementation:** `src/hermes_openclaw/openclaw/adapter.py`

---

## Execution Security Model

| Category | Rule |
|----------|------|
| Commands | Allowlisted (`ls`, `cp`, `mv`); blocked (`rm`, `bash`, `curl \| sh`) |
| Filesystem | Workspace-only; sensitive paths blocked globally |
| Network | Disabled by default; permission-gated; logged |
| Sandboxing | Docker, temp workspaces, timeouts (see `Dockerfile`) |

---

## Audit Logging

Every action is audit-logged with timestamp, task ID, scope, result, and failure reason. Secrets (API keys, tokens, passwords) are redacted automatically.

**Implementation:** `src/hermes_openclaw/security/audit.py`

---

## Feedback Engine

Execution results flow back to Hermes. Outcomes: success, retry, replan, request user clarification.

**Implementation:** `src/hermes_openclaw/feedback/engine.py`

---

## Safety Principles

1. LLMs are untrusted by default
2. Execution is always constrained
3. Policies are deterministic
4. User approval overrides automation
5. Every action is auditable
6. Offline-first operation is preferred
7. Security is prioritized over convenience

---

## Architectural Principle

**HermesClaw:** plan → validate → execute.

No single component is trusted with full autonomy.
