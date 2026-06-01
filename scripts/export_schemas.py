#!/usr/bin/env python3
"""Export Pydantic models to JSON Schema files in schemas/."""

from __future__ import annotations

import json
from pathlib import Path

from hermes_openclaw.models.explainability import RejectionExplanation
from hermes_openclaw.models.signing import ExecutionToken
from hermes_openclaw.models.tasks import TaskPlan
from hermes_openclaw.models.validation import ValidatedPlan, ValidationResult

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

EXPORTS: list[tuple[str, type]] = [
    ("task_plan.schema.json", TaskPlan),
    ("validated_plan.schema.json", ValidatedPlan),
    ("execution_token.schema.json", ExecutionToken),
    ("validation_result.schema.json", ValidationResult),
    ("rejection_explanation.schema.json", RejectionExplanation),
]


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, model in EXPORTS:
        schema = model.model_json_schema(mode="serialization")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://hermesclaw.dev/schemas/{filename}"
        path = SCHEMA_DIR / filename
        path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
