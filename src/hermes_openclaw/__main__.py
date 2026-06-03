"""Entry point for HermesClaw."""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings

from hermes_openclaw.config import Settings
from hermes_openclaw.controller.factory import build_orchestrator, build_pipeline
from hermes_openclaw.logging_setup import configure_logging


def main() -> None:
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
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use the fast heuristic planner for common intents",
    )
    parser.add_argument(
        "--check-gateway",
        action="store_true",
        help="Verify OpenClaw gateway connectivity and configuration",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a concise human-readable summary instead of raw JSON",
    )
    parser.add_argument(
        "--brainstorm",
        action="store_true",
        help="Alias for a non-executing, human-readable planning run",
    )
    args = parser.parse_args()

    quiet_mode = args.summary or args.brainstorm or os.getenv("HERMESCLAW_QUIET", "").strip() == "1"
    if quiet_mode:
        warnings.filterwarnings("ignore", message="AUTO_APPROVE is enabled.*")

    settings = Settings()
    updates: dict = {}
    if args.dry_run:
        updates["dry_run"] = True
    if args.brainstorm:
        updates["dry_run"] = True
    if args.mock_hermes:
        updates["hermes_mock_mode"] = True
    if args.fast:
        updates["hermes_fast_mode"] = True
    if updates:
        settings = settings.model_copy(update=updates)

    if quiet_mode:
        settings = settings.model_copy(update={"log_level": "ERROR"})

    configure_logging(settings.log_level)

    if args.check_gateway:
        from hermes_openclaw.openclaw.gateway_client import OpenClawGatewayClient

        client = OpenClawGatewayClient(
            settings.openclaw_gateway_url,
            token=settings.openclaw_gateway_token,
            session_key=settings.openclaw_gateway_session_key,
            timeout_sec=float(settings.openclaw_gateway_timeout_sec),
        )
        gateway_report = {
            "gateway_url": settings.openclaw_gateway_url,
            "execution_mode": settings.openclaw_execution_mode,
            "token_configured": bool(settings.openclaw_gateway_token),
            "openclaw_cli": settings.openclaw_cli_path,
            "agent_fallback": settings.openclaw_agent_execution,
            "ping_ok": client.ping(),
        }
        print(json.dumps(gateway_report, indent=2))
        sys.exit(0 if gateway_report["ping_ok"] else 1)

    if args.serve:
        import uvicorn

        from hermes_openclaw.api.app import create_app

        app = create_app(settings)
        uvicorn.run(app, host=settings.api_host, port=settings.api_port)
        return

    if args.intent:
        pipeline = build_pipeline(settings)
        result = pipeline.run(args.intent)
        if quiet_mode:
            print(f"Intent: {result.intent}")
            print(f"Success: {result.success}")
            if getattr(result, "message", None):
                print(f"Message: {result.message}")
            execution_report = getattr(result, "execution_report", None)
            if execution_report is not None:
                print(f"Status: {execution_report.status.value}")
                for action_result in execution_report.results:
                    print(
                        "- "
                        + action_result.action_type
                        + ": "
                        + action_result.status.value
                        + " -> "
                        + action_result.message
                    )
        else:
            print(json.dumps(result.model_dump(mode="json"), indent=2))
        sys.exit(0 if result.success else 1)

    if args.plan:
        orchestrator = build_orchestrator(settings)
        with open(args.plan, encoding="utf-8") as f:
            raw_plan = json.load(f)
        report = orchestrator.process_plan(raw_plan)
        if quiet_mode:
            print(f"Task: {report.task_id}")
            print(f"Status: {report.status.value}")
            if getattr(report, "reason", None):
                print(f"Reason: {report.reason}")
            for action_result in report.results:
                print(
                    "- "
                    + action_result.action_type
                    + ": "
                    + action_result.status.value
                    + " -> "
                    + action_result.message
                )
        else:
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
    print('  python -m hermes_openclaw --intent "play music" --brainstorm')
    print("  python -m hermes_openclaw --plan examples/sample_plan.json --dry-run")
    print("  python -m hermes_openclaw --serve")


def run() -> None:
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    run()
