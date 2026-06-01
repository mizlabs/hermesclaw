# Scenario 05 — Permission Approval

Plan creates a folder and launches VS Code. Marked `requires_confirmation: true` and high risk.

```bash
python -m hermes_openclaw --plan examples/05_permission_approval/plan.json --dry-run
python -m hermes_openclaw --plan examples/05_permission_approval/plan.json
```

Flow:

1. Validator checks schema, paths, scopes
2. Permission engine prompts for approval (unless `AUTO_APPROVE=true`)
3. On approval, plan is signed
4. OpenClaw verifies the token before acting

Use `AUTO_APPROVE=true` only in local development.
