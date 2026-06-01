"""Entry point for HermesClaw."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from hermes_openclaw.config import Settings
from hermes_openclaw.controller.factory import build_orchestrator, build_pipeline
from hermes_openclaw.logging_setup import configure_logging


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="HermesClaw: A security-first open-source local AI agent framework"
    )
    parser.add_argument("--plan", type=str, help="JSON task plan file to validate and execute")
    parser.add_argument(
        "--intent",
        type=str,
        help="Natural language intent — runs full Hermes → OpenClaw pipeline",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulate without executing")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI server")
    parser.add_argument(
        "--mock-hermes",
        action="store_true",
        help="Use mock Hermes planner (no CLI required)",
    )
    args = parser.parse_args()

    settings = Settings()
    updates: dict = {}
    if args.dry_run:
        updates["dry_run"] = True
    if args.mock_hermes:
        updates["hermes_mock_mode"] = True
    if updates:
        settings = settings.model_copy(update=updates)

    configure_logging(settings.log_level)

    if args.serve:
        import uvicorn

        from hermes_openclaw.api.app import create_app

        app = create_app(settings)
        uvicorn.run(app, host=settings.api_host, port=settings.api_port)
        return

    if args.intent:
        pipeline = build_pipeline(settings)
        result = pipeline.run(args.intent)
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        sys.exit(0 if result.success else 1)

    if args.plan:
        orchestrator = build_orchestrator(settings)
        with open(args.plan, encoding="utf-8") as f:
            raw_plan = json.load(f)
        report = orchestrator.process_plan(raw_plan)
        print(json.dumps(report.model_dump(mode="json"), indent=2))
        sys.exit(0 if report.status.value in ("success", "dry_run") else 1)

    print("HermesClaw: A security-first open-source local AI agent framework")
    print(f"  Workspace:  {settings.workspace_root.resolve()}")
    print(f"  Network:    {'enabled' if settings.network_enabled else 'disabled (offline-first)'}")
    print(f"  Hermes:     {'mock' if settings.hermes_mock_mode else 'CLI'}")
    print()
    print("Pipeline (HermesClaw):")
    print("  plan → validate → approve → execute → feedback")
    print()
    print("Usage:")
    print('  python -m hermes_openclaw --intent "organize my project files" --mock-hermes')
    print("  python -m hermes_openclaw --plan examples/sample_plan.json --dry-run")
    print("  python -m hermes_openclaw --serve")


def run() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    run()
