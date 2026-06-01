# Security Policy

## Reporting

Do not open public GitHub issues for security vulnerabilities.

Email: **security@YOUR_DOMAIN** (replace before publishing)

Optional: publish a PGP key at `https://YOUR_DOMAIN/.well-known/security.txt`

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
Untrusted (Hermes / LLM) → Validator → Permission + signing → OpenClaw (constrained)
```

LLM output is not executed directly.

| Control | Implementation |
|---------|----------------|
| Schema validation | Pydantic + published JSON Schema |
| Paths | PathGuard |
| Commands | CommandPolicy allowlist |
| Policy | `config/policy.yaml` |
| Execution auth | SHA256 + HMAC tokens |
| Audit | Hash-chained JSONL |
| Flooding | ExecutionRateLimiter |

Full detail: [docs/security-architecture.md](docs/security-architecture.md)

---

## Production Configuration

```env
NETWORK_ENABLED=false
SAFETY_CONFIRM_DESTRUCTIVE=true
AUTO_APPROVE=false
WORKSPACE_ROOT=./workspace
API_HOST=127.0.0.1
PLAN_SIGNING_SECRET=<strong-random-secret>
REQUIRE_SIGNED_TOKEN=true
```

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
