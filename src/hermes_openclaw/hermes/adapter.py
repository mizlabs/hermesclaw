"""Hermes planner adapter — produces structured JSON only, never raw executable code."""

from __future__ import annotations

import json
import re
import subprocess
from abc import ABC, abstractmethod
from typing import Any

import structlog

logger = structlog.get_logger()

# System prompt enforced on every Hermes planning request.
HERMES_PLANNER_PROMPT = """You are a planning agent. You MUST output ONLY a valid JSON task plan.
You must NEVER output executable code, shell scripts, Python, bash, or free-form instructions.

Required JSON schema:
{
  "intent": "<short description>",
  "actions": [
    {
      "type": "<move_file|copy_file|create_folder|list_files|launch_app|exec>",
      "source": "<path if needed — NOT for create_folder>",
      "destination": "<path if needed — REQUIRED for create_folder>",
      "command": "<allowlisted command if exec>",
      "args": [],
      "app_name": "<app if launch_app>",
      "scope": "<filesystem.read|filesystem.write|applications.launch|terminal.restricted>"
    }
  ],
  "risk_level": "<low|medium|high|critical>",
  "requires_confirmation": true,
  "dry_run": false
}

Rules:
- Output JSON only. No markdown, no code fences, no explanations.
- Never include shell, script, eval, or raw_command fields.
- Use only the allowed action types listed above.
- All paths must be relative to the workspace (e.g. "output/demo", not absolute paths).
- Classify risk accurately: file operations (create_folder, copy_file, move_file,
  list_files) must use risk_level "medium" or higher; exec actions must use "medium" or higher.
"""

# Patterns that indicate Hermes emitted raw executable content — must be rejected.
_EXECUTABLE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"```(?:python|bash|sh|shell|javascript|js|zsh)\b", re.I),
    re.compile(r"^\s*(?:import\s+\w+|from\s+\w+\s+import|def\s+\w+|class\s+\w+)", re.M),
    re.compile(r"^\s*(?:sudo|rm\s+-rf|chmod|chown|curl|wget|eval|exec)\s", re.M | re.I),
    re.compile(r"subprocess\.|os\.system|os\.popen", re.I),
]

# Forbidden top-level keys if Hermes tries to bypass the schema.
_FORBIDDEN_PLAN_KEYS = frozenset(
    {"shell", "script", "raw_command", "eval", "exec_raw", "code", "python", "bash"}
)


class HermesAdapterError(Exception):
    """Raised when Hermes output is invalid or contains executable content."""


def reject_executable_content(text: str) -> None:
    """Fail closed if the planner response contains raw executable code."""
    for pattern in _EXECUTABLE_PATTERNS:
        if pattern.search(text):
            raise HermesAdapterError(
                "Hermes output contains raw executable content — rejected by policy"
            )


def extract_json_from_response(text: str) -> dict[str, Any]:
    """
    Extract a JSON object from Hermes response text.

    Strips markdown fences if present, then parses JSON.
    Rejects any response containing executable code patterns.
    """
    reject_executable_content(text)

    cleaned = text.strip()

    # Strip optional markdown code fence (JSON inside is still OK).
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    else:
        # Find first { ... } block.
        brace_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if brace_match:
            cleaned = brace_match.group(0)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HermesAdapterError(f"Hermes did not return valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise HermesAdapterError("Hermes output must be a JSON object")

    forbidden = _FORBIDDEN_PLAN_KEYS & data.keys()
    if forbidden:
        raise HermesAdapterError(f"Hermes output contains forbidden fields: {forbidden}")

    return data


class HermesAdapter(ABC):
    """Planner Adapter API — planning only, no execution."""

    @abstractmethod
    async def generate_plan(self, user_input: str, context: dict | None = None) -> dict[str, Any]:
        """Convert natural language intent into a structured task plan dict."""

    def plan(self, user_intent: str, *, context: str = "") -> dict[str, Any]:
        """Sync wrapper for CLI and pipeline usage."""
        import asyncio

        ctx = {"replan_context": context} if context else {}
        coro = self.generate_plan(user_intent, ctx)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        # Called from an async context — run in a dedicated thread to avoid nested loops.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()


class MockHermesAdapter(HermesAdapter):
    """Deterministic planner for tests and offline development — no Hermes CLI required."""

    async def generate_plan(self, user_input: str, context: dict | None = None) -> dict[str, Any]:
        logger.info("mock_hermes_plan", intent=user_input)
        return {
            "intent": user_input,
            "actions": [
                {
                    "type": "create_folder",
                    "destination": "output",
                    "scope": "filesystem.write",
                },
                {"type": "list_files", "source": ".", "scope": "filesystem.read"},
            ],
            "risk_level": "medium",
            "requires_confirmation": True,
            "dry_run": True,
        }


class CliHermesAdapter(HermesAdapter):
    """
    Invokes Hermes CLI in one-shot mode.

    Hermes is instructed to output JSON only. Raw code in the response is rejected.
    """

    def __init__(
        self,
        cli_path: str = "hermes",
        timeout_sec: int = 120,
        *,
        workspace_root: str | None = None,
    ) -> None:
        self._cli_path = cli_path
        self._timeout = timeout_sec
        self._workspace_root = workspace_root

    async def generate_plan(self, user_input: str, context: dict | None = None) -> dict[str, Any]:
        prompt = HERMES_PLANNER_PROMPT
        if self._workspace_root:
            prompt += f"\n- Workspace root (all paths must stay inside): {self._workspace_root}"
        replan = (context or {}).get("replan_context", "")
        if replan:
            prompt += f"\n\nPrevious failure context:\n{replan}"

        full_prompt = f"{prompt}\n\nUser intent: {user_input}"

        logger.info("hermes_plan_request", intent=user_input)

        try:
            result = subprocess.run(  # noqa: S603 — Hermes CLI only, shell=False
                [self._cli_path, "-z", full_prompt],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise HermesAdapterError(
                f"Hermes CLI not found at '{self._cli_path}'. Install Hermes or use mock mode."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise HermesAdapterError("Hermes planner timed out") from exc

        if result.returncode != 0:
            raise HermesAdapterError(
                f"Hermes planner failed (exit {result.returncode}): {result.stderr.strip()}"
            )

        output = result.stdout.strip()
        if not output:
            raise HermesAdapterError("Hermes returned empty response")

        plan_dict = extract_json_from_response(output)
        logger.info("hermes_plan_received", intent=plan_dict.get("intent"))
        return plan_dict
