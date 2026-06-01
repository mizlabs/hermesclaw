# Why This Project Exists

HermesClaw is a security-first open-source local AI agent framework. Planning and execution are separate steps, with a validator in between.

Most automation tools treat LLM output as instructions and run them. We treat it as untrusted input and check it first.

---

## The Problem

A common pattern in agent tooling:

```
User prompt → LLM decides → system executes
```

That works until it does not. Typical failures:

- The planner picks the wrong path and deletes or moves the wrong files
- Injected text in a file or URL changes what the planner outputs
- The model invents action types (`delete_file`) that the runtime should never support
- A retry loop keeps spawning actions until something breaks

These are not edge cases. They are predictable outcomes when execution has no fixed boundary.

---

## What We Do Instead

```
Hermes (plan) → Validator (check) → Permission (approve + sign) → OpenClaw (execute)
```

Hermes produces structured JSON. It does not run commands.

The validator checks schema, paths, scopes, and policy rules. OpenClaw only sees a `ValidatedPlan` with a valid execution token.

No single component gets full control of the machine.

---

## Design Principles

### LLM output is untrusted

Models are useful for planning. They also hallucinate, misread context, and follow injected instructions.

We do not execute planner output directly. Every plan goes through `SecurityValidator` first.

### Policy is code, not prompting

Asking the model to "be safe" is not a security control. Rules in `config/policy.yaml` apply the same way regardless of what Hermes returns.

### Execution is constrained

OpenClaw is a restricted executor: workspace-scoped filesystem access, allowlisted commands, rate limits, signed tokens.

It is not a general-purpose shell wrapper.

### Local-first by default

Network access is off unless you turn it on. There is no telemetry in the core path. Your plans and audit logs stay on your machine.

### Rejections should be readable

When a plan is blocked, the response includes structured reasons — not a generic error. Executed actions go into a hash-chained audit log.

### Humans approve high-risk work

Writes, app launches, and terminal commands can require explicit confirmation. The model does not approve its own plan.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| Policy-driven local automation | Unrestricted autonomous agents |
| Validated, signed execution plans | Raw LLM → shell pipelines |
| Explainable rejections and audit logs | Opaque black-box automation |
| Offline-first operation | Cloud-dependent control planes |

---

## Who Might Use This

- Researchers studying multi-agent security and sandbox boundaries
- Developers who want local automation with explicit constraints
- Contributors adding platform-specific executors (browser, voice, OS backends)

---

## Contributing Without Changing the Model

Useful extensions fit the same pipeline:

- Sandboxed browser or vision modules with declared scopes
- macOS / Windows / Linux executors behind the same validator
- Voice input/output with confirmation gates on anything that executes

Changes we will not accept:

- Skipping the validator for convenience
- Arbitrary shell execution
- Cloud-only features without opt-in
- Modes that remove approval or signing

See [contributor-modules.md](contributor-modules.md) for concrete module ideas.

---

## Summary

Hermes plans. Policy and the validator decide what is allowed. OpenClaw executes only what passed both checks and carries a valid token.

That separation is the point of the project.
