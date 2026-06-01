#!/usr/bin/env bash
# Install and configure OpenClaw for HermesClaw gateway execution.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== HermesClaw OpenClaw setup ==="

# Node 22+ required by OpenClaw 2026.5+
if command -v brew >/dev/null && ! node --version 2>/dev/null | grep -qE '^v22\.(1[9-9]|[2-9][0-9])'; then
  echo "Installing Node 22 via Homebrew..."
  brew install node@22
fi
export PATH="/opt/homebrew/opt/node@22/bin:${HOME}/.local/bin:${PATH}"

if ! command -v openclaw >/dev/null; then
  echo "Installing OpenClaw to ~/.local ..."
  npm install -g openclaw@latest --prefix "${HOME}/.local"
fi

openclaw --version

WORKSPACE="$(cd "$ROOT/workspace" && pwd)"
echo "Workspace: $WORKSPACE"

# Reuse Hermes NVIDIA key when available
if [[ -f "${HOME}/.hermes/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${HOME}/.hermes/.env"
  set +a
fi

AUTH_ARGS=(--auth-choice skip)
if [[ -n "${NVIDIA_API_KEY:-}" ]]; then
  AUTH_ARGS=(--auth-choice nvidia-api-key --nvidia-api-key "$NVIDIA_API_KEY")
  echo "Using NVIDIA API key from ~/.hermes/.env"
fi

openclaw onboard --non-interactive --accept-risk --flow quickstart \
  "${AUTH_ARGS[@]}" \
  --gateway-auth token \
  --gateway-bind loopback \
  --gateway-port 18789 \
  --workspace "$WORKSPACE" \
  --skip-health

TOKEN="$(openclaw config get gateway.auth.token 2>/dev/null || true)"
if [[ -z "$TOKEN" || "$TOKEN" == "__OPENCLAW_REDACTED__" ]]; then
  TOKEN="$(python3 - <<'PY'
import json, pathlib
cfg = pathlib.Path.home() / ".openclaw/openclaw.json"
print(json.loads(cfg.read_text())["gateway"]["auth"]["token"])
PY
)"
fi

openclaw config set tools.profile coding
openclaw config set gateway.tools.allow '["read","write","apply_patch","exec"]'

echo ""
echo "Add these to your .env:"
echo "OPENCLAW_GATEWAY_URL=http://localhost:18789"
echo "OPENCLAW_GATEWAY_TOKEN=${TOKEN}"
echo "OPENCLAW_EXECUTION_MODE=gateway"
echo "OPENCLAW_CLI_PATH=${HOME}/.local/bin/openclaw"
echo ""
echo "Start gateway (separate terminal):"
echo "  export PATH=\"/opt/homebrew/opt/node@22/bin:\$HOME/.local/bin:\$PATH\""
echo "  openclaw gateway run --port 18789"
echo ""
echo "Verify:"
echo "  python -m hermes_openclaw --check-gateway"
