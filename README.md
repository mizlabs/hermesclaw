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
git clone https://github.com/mizlabs/hermesclaw.git
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

Shell wrapper:

```bash
hermesclaw "open youtube and play kun anta"
hermesclaw --safe "open youtube and play kun anta"
```

Use the direct form for normal workspace-scoped tasks. Use `--safe` when you want the wrapper to show a preview and ask for approval first.

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

Configuration (copy from `config/.env.example`):

```bash
cp config/.env.example .env
# Edit .env locally — set PLAN_SIGNING_SECRET (generate per comment in that file)
# NEVER commit .env — only config/.env.example belongs in git
./scripts/pre_push_check.sh   # run before git push
```

Hermes **model/API** is configured in `~/.hermes/` (`hermes model`, `hermes config show`), not via `HERMES_MODEL_*` in HermesClaw `.env`. See [plan.md](plan.md) for the full workflow.

Key defaults:

```env
NETWORK_ENABLED=false
AUTO_APPROVE=false
WORKSPACE_ROOT=./workspace
OPENCLAW_EXECUTION_MODE=auto
OPENCLAW_GATEWAY_URL=http://localhost:18789
API_HOST=127.0.0.1
```

### OpenClaw gateway bridge

HermesClaw can execute signed plans through a running [OpenClaw gateway](https://docs.openclaw.ai/gateway) instead of the built-in local dispatcher.

1. Start OpenClaw gateway (default port `18789`).
2. Copy your gateway token into `.env`:

```env
OPENCLAW_GATEWAY_TOKEN=<from openclaw config get gateway.auth.token>
OPENCLAW_EXECUTION_MODE=auto   # auto | local | gateway
```

Execution modes:

| Mode | Behavior |
|------|----------|
| `auto` | Use gateway when reachable; fall back to local execution |
| `local` | Always execute in-process (no HTTP) |
| `gateway` | Require gateway; fail if unreachable |

HermesClaw maps validated actions to OpenClaw `POST /tools/invoke` when coding tools are exposed over HTTP. On OpenClaw 2026.5.x, file tools often require the **agent fallback** (`openclaw agent --json`) which HermesClaw enables automatically when HTTP returns 404.

```bash
./scripts/setup_openclaw.sh          # install + configure OpenClaw
openclaw gateway run --port 18789    # start gateway (separate terminal)
python -m hermes_openclaw --check-gateway
```

Set in `.env`:

```env
OPENCLAW_GATEWAY_TOKEN=<from openclaw config get gateway.auth.token>
OPENCLAW_EXECUTION_MODE=gateway
OPENCLAW_AGENT_EXECUTION=true
```

Security note: gateway bearer tokens are operator credentials. HermesClaw still validates, approves, and signs every plan before anything reaches OpenClaw.

---

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR. Security-related changes need tests.

Good first areas: [docs/contributor-modules.md](docs/contributor-modules.md)

Security issues: [SECURITY.md](SECURITY.md) — do not file public GitHub issues for vulnerabilities.

---

## License

MIT — see [LICENSE](LICENSE). Hermes and OpenClaw are separate projects with their own licenses.
