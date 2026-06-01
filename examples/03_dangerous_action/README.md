# Scenario 03 — Dangerous Action Blocked

Plan uses `delete_file`, which is not in the action allowlist. This simulates a common hallucination pattern.

```bash
python -m hermes_openclaw --plan examples/03_dangerous_action/plan.json --dry-run
```

Expected: validator rejects the plan before OpenClaw runs. Output will mention the blocked action type.

The plan never reaches the executor.
