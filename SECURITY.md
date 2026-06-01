# Security Policy

## Reporting

Do not open public GitHub issues for security vulnerabilities.

Email: **mizlabs99@proton.me** 

### What to include

1. Short description of the issue
2. Your severity estimate (Critical / High / Medium / Low)
3. Affected component (Validator, OpenClaw, Permission Engine, API, etc.)
4. Steps to reproduce or a minimal test case
5. Likely impact
6. Suggested fix, if you have one
7. Contact for follow-up

### Timeline

| When | What |
|------|------|
| 48 hours | Acknowledgment |
| 7 days | Triage and severity confirmation |
| 30 days | Target fix for Critical/High (may slip by agreement) |
| 90 days | Coordinated public disclosure if reporter agrees |

Advisories use the ID format `HCL-YYYY-NNN`.

---

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |
| < 0.1   | No        |

Security fixes land on the current 0.1.x release.

---

## Disclosure Process

```
Day 0   Report received
Day 1   Acknowledgment, internal triage
Day 3   Severity set, fix branch opened
Day 7   Patch for Critical/High (target)
Day 30  Public advisory (with reporter consent)
        - HCL-YYYY-NNN
        - Affected versions
        - Severity (CVSS-style, best effort)
        - Mitigation
        - Credit (unless anonymous)
```

### Severity (rough guide)

| Level | Examples |
|-------|----------|
| Critical | Validator bypass, unsigned plan execution, RCE through OpenClaw |
| High | Policy bypass, forged audit chain, token replay without expiry check |
| Medium | Path guard bypass, rate limit bypass, sensitive data in logs |
| Low | DoS, incomplete redaction |

---

## Architecture (summary)

```
User intent
  → Hermes CLI (hermes -z) — JSON only
  → Plan normalizer
  → SecurityValidator
  → PermissionEngine (approve + sign)
  → OpenClaw gateway / agent (constrained)
  → Audit log
```

LLM output is not executed directly. HermesClaw never calls an LLM API itself for planning — it delegates to the Hermes agent CLI, which has its own credentials in `~/.hermes/.env`.

| Control | Implementation |
|---------|----------------|
| Schema validation | Pydantic + published JSON Schema |
| Planner output cleanup | `plan_normalizer.py` |
| Paths | PathGuard |
| Commands | CommandPolicy allowlist |
| Policy | `config/policy.yaml` |
| User approval | `PermissionEngine` / `ApprovalGate` |
| Execution auth | SHA256 + HMAC tokens |
| OpenClaw access | Gateway bearer token (operator credential) |
| Audit | Hash-chained JSONL |
| Flooding | ExecutionRateLimiter |

Full detail: [docs/security-architecture.md](docs/security-architecture.md)

---

## Production Configuration

Copy `config/.env.example` to `.env` at the project root. **Never commit `.env`.**

```env
NETWORK_ENABLED=false
SAFETY_CONFIRM_DESTRUCTIVE=true
AUTO_APPROVE=false
DRY_RUN=false
WORKSPACE_ROOT=./workspace
API_HOST=127.0.0.1
REQUIRE_SIGNED_TOKEN=true
OPENCLAW_EXECUTION_MODE=gateway
OPENCLAW_AGENT_EXECUTION=true
OPENCLAW_GATEWAY_TOKEN=<set locally — operator secret>
PLAN_SIGNING_SECRET=<generate locally — see below>
```

Generate a signing secret locally:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Before `git push`, run `./scripts/pre_push_check.sh` — it verifies `.env` is not tracked and that this template has no pre-filled secrets.

### Credential separation

| Secret | Location | Notes |
|--------|----------|-------|
| `PLAN_SIGNING_SECRET` | HermesClaw `.env` | Signs approved plans; leak allows forged execution tokens |
| `OPENCLAW_GATEWAY_TOKEN` | HermesClaw `.env` | Gateway operator access; treat like a root password on localhost |
| LLM API keys | `~/.hermes/.env` | Hermes agent only; not in this repository |
| OpenClaw auth | `~/.openclaw/openclaw.json` | Separate from HermesClaw git tree |

This reduces risk. It does not make the host immune to a compromised OS or a leaked signing secret.

---

## Dependencies

- Versions pinned in `pyproject.toml`
- CI runs `pip-audit` on push and PR
- Dependabot for pip and GitHub Actions
- New dependencies need a short security review; no telemetry libraries

---

## Development

Contributors working on security-sensitive code should:

- Avoid logging secrets
- Not skip validation in production paths
- Not use `shell=True`
- Add tests for security behavior
- Run `ruff`, `mypy`, `bandit`, `pytest` locally

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Acknowledgments

| Advisory ID | Researcher | Date |
|-------------|------------|------|
| — | — | — |

---

## Safe Harbor

Good-faith research on installations you own or have permission to test is welcome. Do not test systems you do not control.

---

## Related

- [docs/security-architecture.md](docs/security-architecture.md)
- [docs/threat-model.md](docs/threat-model.md)
- [docs/philosophy.md](docs/philosophy.md)
