# Contributor Modules

Ideas for modules that fit the existing pipeline without turning the project into an unrestricted agent.

Read [philosophy.md](philosophy.md) first.

---

## Required Pattern

Every executor or adapter must:

1. Take `ValidatedPlan` + valid `ExecutionToken` — not raw planner JSON
2. Declare permission scopes
3. Honor `config/policy.yaml`
4. Write audit events via `AuditLogger`
5. Ship tests, including adversarial cases

```
Hermes → Validator → Permission → your module → Feedback
```

Do not add a path that skips the validator.

---

## Suggested Modules

### Browser executor

Scopes: `browser.navigate`, `browser.read_dom` (read-only by default)

| Action | Default |
|--------|---------|
| Navigate to URL | Denied |
| Read page text | Allowed with scope |
| Click / submit | Requires confirmation |
| Download | Denied |

Clear scope boundaries; useful for research on constrained web automation.

Hook: add a dispatch branch in `src/hermes_openclaw/openclaw/adapter.py`.

### Voice adapter

Scopes: `voice.listen`, `voice.speak`

| Action | Default |
|--------|---------|
| TTS status messages | Allowed |
| STT for intent | Allowed |
| Voice-triggered execution | Requires confirmation |

Voice as input/output, not as a bypass around approval.

### macOS executor

Scopes: `applications.launch`, `desktop.control` (denied by default)

Platform backend (AppleScript / Accessibility API) with allowlists. Same validator and token flow as the rest of the system.

### Windows executor

Same scope model as macOS. Prefer restricted PowerShell patterns; avoid open `cmd.exe` access.

### Linux sandbox backend

Scopes: `terminal.restricted`, `filesystem.read`, `filesystem.write`

Possible backends: namespaces, `bubblewrap`, or `firejail`. Good fit if you care about sandbox isolation research.

### Vision plugin

Scope: `vision.analyze` (read-only)

Screenshot → structured description JSON. No click coordinates or GUI control unless policy and scopes explicitly allow it.

---

## Layout

```
src/hermes_openclaw/plugins/<name>/
  __init__.py
  adapter.py
  scopes.py
  tests/
    test_<name>.py
    test_adversarial_<name>.py
```

Register scopes in `models/scopes.py` and rules in `config/policy.yaml`.

---

## Will Not Merge

- Validator bypasses
- Arbitrary shell
- Cloud-first features without opt-in
- Telemetry
- Modes that remove signing or approval

---

## Getting Started

1. Open an issue with the module name, scopes, and default policy
2. Read [CONTRIBUTING.md](../CONTRIBUTING.md) and [security-architecture.md](security-architecture.md)
3. Write tests first (`tests/chaos/` patterns are a good reference)
4. Open a PR with a short doc update

Security reports: [SECURITY.md](../SECURITY.md), not GitHub Issues.
