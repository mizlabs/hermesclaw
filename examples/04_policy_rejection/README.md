# Scenario 04 — Policy Rejection

Plan requests `bash` with `terminal.unrestricted` scope. Both the command and scope are denied by default policy.

```bash
python -m hermes_openclaw --plan examples/04_policy_rejection/plan.json --dry-run
```

Expected: rejection from policy rules, independent of planner intent.

See `config/policy.yaml` for deny lists.
