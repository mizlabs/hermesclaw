# Threat Model

Assumptions, boundaries, and known limits for HermesClaw.

## System Overview

Four main stages:

- **Hermes** — produces JSON plans; does not execute
- **Security Validator** — trust boundary; schema, paths, policy
- **Permission Engine** — user approval and signed tokens
- **OpenClaw** — executes allowlisted actions inside workspace limits

No component should have both open-ended planning and unconstrained execution.

---

## Attacker Assumptions

We assume an attacker may:

| Threat | Description |
|--------|-------------|
| Malicious prompts | User or third party tries to steer the planner |
| Prompt injection | Hidden instructions in files, URLs, or context |
| LLM hallucination | Invented actions (`delete_file`) or bad paths |
| Plan tampering | Modified JSON between validation and execution |
| Replay | Re-submitting an old approved plan or token |
| Path traversal | `../../etc/passwd` and similar |
| Runaway loops | Retries that flood the executor |
| Forged approval | Attempts to skip human confirmation |
| Audit tampering | Editing logs after the fact |

We do not assume attackers can:

- Break SHA-256 or HMAC without `PLAN_SIGNING_SECRET`
- Compromise the host kernel (out of scope)
- Read `.env` or signing secrets from disk (out of scope)

---

## Trust Boundaries

```
Untrusted: user input, Hermes output, external context
    ↓  boundary 1
Security Validator
    ↓  boundary 2
Permission Engine (approval + signing)
    ↓  boundary 3
OpenClaw (constrained execution)
```

---

## Risks and Mitigations

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| LLM emits shell code | Critical | Schema, forbidden fields, no code blocks | Implemented |
| Hallucinated delete ops | Critical | Closed action enum, policy deny | Implemented |
| Path traversal | High | PathGuard, resolved paths | Implemented |
| Plan tampering | High | Plan hash + HMAC token | Implemented |
| Replay | High | Token expiry, id binding | Implemented |
| Runaway agent | High | Rate limits | Implemented |
| Audit tampering | Medium | Hash-chained log | Implemented |
| Unauthorized exec | Critical | Command allowlist, `shell=False` | Implemented |
| Network exfiltration | High | Network off by default | Implemented |
| Missing consent | High | Permission approval gates | Implemented |
| Validator bypass | Critical | OpenClaw rejects unsigned plans | Implemented |

---

## Security Levels

| Level | Example actions |
|-------|-----------------|
| Safe | `list_files` |
| Elevated | `create_folder`, `move_file` |
| Dangerous | GUI automation (denied by default) |
| Critical | `exec`, outbound network if enabled |

Higher levels require stronger confirmation in policy.

---

## Guarantees and Limits

**When configured as documented**, the system intends that:

1. OpenClaw does not receive raw LLM output
2. Executed plans passed schema, path, and policy checks
3. Executed plans carry a time-limited signed token
4. Actions are logged in a hash-chained audit file
5. Rejected plans include structured reasons
6. Network stays off unless enabled
7. Commands go through an allowlist, not an open shell

**We do not claim protection against:**

- A compromised host OS
- Leaked `PLAN_SIGNING_SECRET` or `.env`
- Physical access to the machine
- Every possible novel hallucination format (layers reduce risk; they do not eliminate it)

---

## Non-Goals

- Unrestricted autonomous agent
- Shell-first automation
- Cloud-dependent operation
- Executing planner output without validation

---

## Reporting

See [SECURITY.md](../SECURITY.md).
