# Contributing

Thanks for looking at this project. Security-sensitive changes get extra review time — that is intentional.

## Before You Start

1. [SECURITY.md](SECURITY.md) — reporting and baseline expectations
2. [docs/security-architecture.md](docs/security-architecture.md) — trust boundaries
3. [docs/philosophy.md](docs/philosophy.md) — what we are and are not building
4. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — component layout
5. [docs/contributor-modules.md](docs/contributor-modules.md) — module ideas
6. [ROADMAP.md](ROADMAP.md) — current priorities

## Setup

```bash
git clone https://github.com/mizlabs/hermesclaw.git
cd hermesclaw
./scripts/setup.sh
```

## Rules (non-negotiable)

- LLM output goes through the validator — no shortcuts
- No `shell=True` in subprocess calls
- No bypassing approval in production code paths
- No logging secrets (use `AuditLogger`; it redacts common patterns)
- Network access goes through `NetworkPolicy`
- New dependencies should not phone home or collect telemetry
- Security changes need tests

## Code Standards

- Python 3.11+, type hints where practical
- Pydantic for structured data
- `ruff` + `black` for style
- `pytest` for tests

```bash
ruff check src tests
black src tests
mypy src/hermes_openclaw
bandit -r src/hermes_openclaw -c pyproject.toml -ll
pytest -v
python scripts/run_benchmarks.py
```

## Before You Push

```bash
cp config/.env.example .env   # first time only — edit locally, never commit .env
./scripts/pre_push_check.sh   # secrets scan + full CI toolchain locally
```

The pre-push script checks that `.env` is not tracked, `config/.env.example` has no pre-filled signing secret, and pytest/ruff/mypy/bandit/pip-audit pass.

## Pull Requests

1. Branch from `main`
2. Add tests for security-related changes
3. Make sure CI passes
4. Update docs if behavior or config changed
5. Describe what changed and why

## What We Usually Accept

- Validator, policy, or audit improvements (with tests)
- Bug fixes
- Documentation fixes
- Hermes / OpenClaw integration work
- Sandboxed plugins that respect scopes and policy

## What We Usually Decline

- Validator bypasses
- Arbitrary shell execution
- Cloud dependencies without explicit opt-in
- Telemetry
- Undocumented behavior

## Questions

GitHub Issues or Discussions: [mizlabs/hermesclaw](https://github.com/mizlabs/hermesclaw/issues)

For vulnerabilities, use [SECURITY.md](SECURITY.md) — not a public issue.
