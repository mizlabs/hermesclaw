# JSON Schemas

Published JSON Schema files for the main data contracts. They mirror the Pydantic models in `src/hermes_openclaw/models/`.

Use them to validate plans in editors, CI, or external tools without importing Python.

## Files

| File | Model | Description |
|------|-------|-------------|
| `task_plan.schema.json` | `TaskPlan` | Planner output |
| `validated_plan.schema.json` | `ValidatedPlan` | After validation |
| `execution_token.schema.json` | `ExecutionToken` | Signed token |
| `validation_result.schema.json` | `ValidationResult` | Validator result |
| `rejection_explanation.schema.json` | `RejectionExplanation` | Why a plan was rejected |

## Regenerate

After model changes:

```bash
python scripts/export_schemas.py
```

Commit both the Python models and the updated schema files.

## Validate in Python

```bash
python -c "
from hermes_openclaw.models.tasks import TaskPlan
plan = TaskPlan.model_validate_json(open('examples/01_organize_files/plan.json').read())
print(plan.task_id)
"
```

## Versioning

Schema `$id` values use `https://hermesclaw.dev/schemas/`. Breaking wire-format changes should be noted in release notes.
