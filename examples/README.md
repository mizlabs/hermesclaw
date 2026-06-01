# Demo Scenarios

Small, runnable plans that show how validation and policy behave.

Each folder has a `plan.json` and a short README.

## Setup

```bash
./scripts/setup.sh
export PLAN_SIGNING_SECRET="dev-secret-change-me"
```

## Scenarios

| Folder | What it shows | Result |
|--------|---------------|--------|
| [01_organize_files](01_organize_files/) | Create folders, list files | Validates; dry-run OK |
| [02_open_workspace](02_open_workspace/) | Read-only listing | Safe level; no confirmation |
| [03_dangerous_action](03_dangerous_action/) | `delete_file` action type | Validator rejects |
| [04_policy_rejection](04_policy_rejection/) | `bash` + unrestricted scope | Policy rejects |
| [05_permission_approval](05_permission_approval/) | Write + app launch | Needs confirmation |

## Run

```bash
python -m hermes_openclaw --plan examples/01_organize_files/plan.json --dry-run
python -m hermes_openclaw --plan examples/03_dangerous_action/plan.json --dry-run
python -m hermes_openclaw --intent "organize my downloads" --mock-hermes --dry-run
```

`--dry-run` avoids filesystem changes. Use it while exploring.

Plans should match [schemas/task_plan.schema.json](../schemas/task_plan.schema.json).

Background: [docs/philosophy.md](../docs/philosophy.md)
