---
name: Security vulnerability
about: Report a security issue (do not disclose publicly)
title: "[Security] "
labels: security
---

**Do NOT include exploit details in this issue if the repository is public.**

For sensitive reports, email **mizlabs99@proton.me** instead.

## Summary

<!-- Brief description of the vulnerability -->

## Severity

- [ ] Critical — remote code execution, data exfiltration
- [ ] High — privilege escalation, bypass of approval gates
- [ ] Medium — path traversal, command injection in edge cases
- [ ] Low — information disclosure, denial of service

## Component

- [ ] PlanValidator / task schemas
- [ ] Plan normalizer
- [ ] PathGuard (filesystem)
- [ ] CommandPolicy (exec)
- [ ] ApprovalGate / PermissionEngine
- [ ] Plan signing (HMAC tokens)
- [ ] OpenClaw gateway client
- [ ] OpenClaw agent bridge
- [ ] AuditLogger
- [ ] NetworkPolicy
- [ ] Orchestrator
- [ ] API endpoints
- [ ] Docker configuration
- [ ] Other

## Steps to reproduce

1.
2.
3.

## Impact

<!-- What could an attacker achieve? -->

## Suggested fix

<!-- Optional -->
