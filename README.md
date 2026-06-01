# HermesClaw: A security-first open-source local AI agent framework

HermesClaw separates planning from execution. The [Hermes](https://github.com/NousResearch/hermes-agent) planner produces structured JSON; a security validator checks it; the [OpenClaw](https://github.com/openclaw/openclaw) executor runs only approved, signed plans inside workspace and policy limits.

---

## Why It Exists

LLM output is treated as untrusted input. Plans are validated before anything touches the filesystem or runs a command.

That split exists because planners hallucinate paths, invent action types, and can be steered by injected text. Running their output directly is a design choice we avoid.

More background: [docs/philosophy.md](docs/philosophy.md)

---

## Architecture

```
User intent
  → Hermes (TaskPlan JSON)
  → SecurityValidator
  → PermissionEngine (approve + sign)
  → OpenClaw (execute)
  → FeedbackEngine (retry / replan)
```

Hermes does not emit executable code. OpenClaw accepts only `ValidatedPlan` objects with valid scopes and an execution token.

### Permission scopes

| Scope | Meaning |
|-------|---------|
| `filesystem.read` | Read files under workspace |
| `filesystem.write` | Create/move/copy under workspace |
| `applications.launch` | Launch an application |
| `desktop.control` | GUI input (denied by default) |
| `network.disabled` | No outbound network |
| `terminal.restricted` | Allowlisted commands only |

Details: [docs/security-architecture.md](docs/security-architecture.md)

---

## Security Model

| Control | Where |
|---------|--------|
| Schema + closed action types | `SecurityValidator` |
| Path guard, command allowlist | `PathGuard`, `CommandPolicy` |
| Policy rules | `config/policy.yaml` |
| User approval | `PermissionEngine` |
| Signed plans (SHA256 + HMAC) | `plan_signing.py` |
| Audit log (hash-chained JSONL) | `audit.py` |
| Rate limits | `rate_limiter.py` + policy |
| Adversarial tests | `tests/chaos/` |

Network is disabled by default. Commands use `shell=False` and an allowlist. High-risk actions require confirmation unless you explicitly enable `AUTO_APPROVE` (development only).

Threat model: [docs/threat-model.md](docs/threat-model.md)

---

## Installation

**Requirements:** Python 3.11+. Hermes and OpenClaw for full integration; mock mode works without them.

```bash
git clone https://github.com/YOUR_USERNAME/hermesclaw.git
cd hermesclaw

python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
cp config/.env.example .env
```

---

## Example Usage

Natural language (mock planner):

```bash
python -m hermes_openclaw --intent "organize my project files" --mock-hermes --dry-run
```

From a plan file:

```bash
python -m hermes_openclaw --plan examples/01_organize_files/plan.json --dry-run
```

Blocked plan (hallucinated action type):

```bash
python -m hermes_openclaw --plan examples/03_dangerous_action/plan.json --dry-run
```

More scenarios: [examples/README.md](examples/README.md)

Example plan shape:

```json
{
  "task_id": "123",
  "intent": "organize_downloads",
  "actions": [
    { "type": "create_folder", "destination": "Documents/PDFs" },
    { "type": "list_files", "source": "." }
  ],
  "risk_level": "medium",
  "requires_confirmation": true,
  "dry_run": true
}
```

Allowed action types: `move_file`, `copy_file`, `create_folder`, `list_files`, `launch_app`, `exec` (allowlisted commands only).

API server (localhost):

```bash
python -m hermes_openclaw --serve
# http://127.0.0.1:8000/docs
```

Docker:

```bash
docker compose up --build
```

---

## Development

```bash
./scripts/setup.sh
pytest
ruff check src tests
mypy src/hermes_openclaw
bandit -r src/hermes_openclaw -c pyproject.toml -ll
python scripts/run_benchmarks.py
```

Layout:

```
├── config/policy.yaml       # allow / deny / limits
├── docs/                    # architecture, threat model, philosophy
├── schemas/                 # JSON Schema for wire formats
├── examples/                # runnable demo plans
├── src/hermes_openclaw/
│   ├── hermes/              # planner adapter
│   ├── security/            # validator, policy, audit, signing
│   ├── openclaw/            # executor adapter
│   └── controller/          # pipeline wiring
└── tests/
```

Configuration (safe defaults):

```env
NETWORK_ENABLED=false
AUTO_APPROVE=false
WORKSPACE_ROOT=./workspace
PLAN_SIGNING_SECRET=<set-in-production>
API_HOST=127.0.0.1
```

---

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR. Security-related changes need tests.

Good first areas: [docs/contributor-modules.md](docs/contributor-modules.md)

Security issues: [SECURITY.md](SECURITY.md) — do not file public GitHub issues for vulnerabilities.

---

## License

MIT — see [LICENSE](LICENSE). Hermes and OpenClaw are separate projects with their own licenses.
