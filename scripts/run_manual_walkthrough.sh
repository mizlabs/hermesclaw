#!/usr/bin/env bash
# Full HermesClaw walkthrough with manual approval (AUTO_APPROVE=false).
# Run from project root in an interactive terminal — you type y/N at each prompt.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .venv/bin/activate ]]; then
  echo "Missing .venv — run: python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

export AUTO_APPROVE=false
export DRY_RUN=false
export HERMES_MOCK_MODE=false

banner() {
  echo ""
  echo "════════════════════════════════════════════════════════════"
  echo "  $1"
  echo "════════════════════════════════════════════════════════════"
  echo ""
}

run_plan() {
  local label="$1"
  local plan_file="$2"
  local real="${3:-false}"
  banner "$label"
  if [[ "$real" == "true" ]]; then
    python -m hermes_openclaw --plan <(jq '.dry_run = false' "$plan_file") || true
  else
    python -m hermes_openclaw --plan "$plan_file" || true
  fi
}

echo "HermesClaw manual-approval walkthrough"
echo "  AUTO_APPROVE=false  DRY_RUN=false  HERMES_MOCK_MODE=false"
echo ""
echo "You will be prompted to approve medium/high-risk plans."
if [[ -t 0 ]]; then
  echo "Press Enter to start..."
  read -r _
else
  echo "(non-interactive stdin — approve with y on each prompt)"
fi

banner "1/8 — Unit tests (pytest)"
pytest -q

banner "2/8 — Example 02: read-only list (no approval needed)"
run_plan "Safe read-only plan" examples/02_open_workspace/plan.json true

banner "3/8 — Example 01: organize files (approval required — type y to proceed)"
run_plan "Organize workspace" examples/01_organize_files/plan.json true

banner "4/8 — Example 03: dangerous action (should reject — no approval)"
python -m hermes_openclaw --plan examples/03_dangerous_action/plan.json || true

banner "5/8 — Example 04: policy rejection (should reject — no approval)"
python -m hermes_openclaw --plan examples/04_policy_rejection/plan.json || true

banner "6/8 — Example 05: high-risk write + launch (approval required — type y or N)"
run_plan "Permission approval demo" examples/05_permission_approval/plan.json true

banner "7/8 — Real Hermes intent (approval required — type y to create folder)"
python -m hermes_openclaw --intent "create a folder named manual_approved inside the workspace" || true

banner "8/8 — Audit log tail"
if [[ -f logs/audit.jsonl ]]; then
  echo "Last 5 audit entries:"
  tail -5 logs/audit.jsonl
else
  echo "(no audit log yet)"
fi

echo ""
echo "Done. Check workspace/:"
ls -la workspace/ 2>/dev/null || true
