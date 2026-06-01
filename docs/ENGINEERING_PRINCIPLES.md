# Engineering Principles

These principles govern all design and implementation decisions in this project.
**Security always comes first.**

---

## Priority Order

1. Security
2. Reliability
3. Transparency
4. Maintainability
5. Extensibility
6. Performance
7. Features

Never sacrifice security for convenience.

---

## Core Rules

### Security First

- Local execution, sandboxing, least privilege
- User approval for dangerous actions
- Full audit trail, secrets redacted
- Never trust LLM outputs — validate everything

### Open Source Friendly

- Modular, readable, testable, documented
- Clean interfaces, typed APIs
- No hidden automation or magic abstractions

### Local-First

- Fully offline by default
- No telemetry, no hidden network calls
- Internet features require explicit opt-in

### Agent Safety Model

| Agent | Can Execute? | Can Plan? |
|-------|-------------|-----------|
| Hermes | **No** | Yes (JSON only) |
| OpenClaw | Yes (validated) | No |

### Code Standards

- Python type hints + Pydantic models
- FastAPI, structlog, pytest, ruff, black
- SOLID principles, dependency injection
- Tests required for security-sensitive code

---

## What This Project Is NOT

- A toy AI assistant
- An unsafe autonomous agent
- A cloud surveillance platform

## What This Project IS

- A secure local AI framework
- A privacy-preserving automation system
- A modular multi-agent architecture
- An open-source developer platform

---

See also: [SECURITY.md](../SECURITY.md) | [CONTRIBUTING.md](../CONTRIBUTING.md) | [ROADMAP.md](../ROADMAP.md)
