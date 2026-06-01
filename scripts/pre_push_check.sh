#!/usr/bin/env bash
# Pre-push security and CI checks — run before git push.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== HermesClaw pre-push check ==="
echo ""

fail() { echo "FAIL: $1" >&2; exit 1; }

# 1. No real .env in git
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  fail ".env is tracked by git — remove it before pushing"
fi
if git ls-files | grep -qx '\.env'; then
  fail "root .env found in index"
fi
echo "OK  .env not tracked (only config/.env.example allowed)"

# 2. No accidental secret files
for f in credentials.json secrets.json *.pem; do
  if git ls-files | grep -q "$f"; then
    fail "sensitive file tracked: $f"
  fi
done
echo "OK  no credentials.json / *.pem in index"

# 3. .env.example must not ship pre-filled secrets (check working tree)
ENV_EXAMPLE="$ROOT/config/.env.example"
[[ -f "$ENV_EXAMPLE" ]] || fail "missing config/.env.example"
if grep -qE '^PLAN_SIGNING_SECRET=.+|^OPENCLAW_GATEWAY_TOKEN=.+|^NVIDIA_API_KEY=|^OPENROUTER_API_KEY=' "$ENV_EXAMPLE"; then
  fail "config/.env.example must leave secrets empty (PLAN_SIGNING_SECRET, tokens, API keys)"
fi
echo "OK  config/.env.example has no pre-filled secrets"

# 4. CI toolchain
command -v pytest >/dev/null || fail "pytest not found — activate .venv"
pytest -q
ruff check src tests
black --check src tests
mypy src/hermes_openclaw
bandit -r src/hermes_openclaw -c pyproject.toml -ll
pip-audit

echo ""
echo "=== All pre-push checks passed ==="
echo "Safe to: git push -u origin main"
