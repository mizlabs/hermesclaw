#!/usr/bin/env bash
set -euo pipefail

echo "=== HermesClaw Dev Setup ==="

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "Created .venv"
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

if [ ! -f ".env" ]; then
  cp config/.env.example .env
  echo "Created .env from template"
fi

mkdir -p workspace data logs

echo ""
echo "Setup complete."
echo ""
echo "  Run tests:     pytest -v"
echo "  Dry-run plan:  python -m hermes_openclaw --plan examples/sample_plan.json --dry-run"
echo "  Start API:     python -m hermes_openclaw --serve"
echo ""
echo "  Security docs: SECURITY.md"
echo "  Architecture:  docs/ARCHITECTURE.md"
