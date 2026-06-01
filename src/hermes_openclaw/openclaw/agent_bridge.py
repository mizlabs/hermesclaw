"""OpenClaw agent CLI bridge — fallback when /tools/invoke lacks coding tools."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

import structlog

from hermes_openclaw.models.execution import FailureReason
from hermes_openclaw.models.validation import ValidatedAction
from hermes_openclaw.openclaw.gateway_client import GatewayInvokeError

logger = structlog.get_logger()

EXECUTE_PREFIX = "HERMESCLAW_EXECUTE_v1"


class OpenClawAgentBridge:
    """
    Run a single validated action through `openclaw agent --json`.

    OpenClaw 2026.5.x does not expose read/write/apply_patch on POST /tools/invoke
    (see openclaw/openclaw#54391). The agent path uses OpenClaw's coding tool surface
    with a constrained one-shot message derived from the signed ValidatedAction.
    """

    def __init__(
        self,
        cli_path: str = "openclaw",
        *,
        session_key: str = "main",
        gateway_token: str = "",
        timeout_sec: int = 120,
        workspace_root: str | None = None,
    ) -> None:
        self._cli_path = cli_path
        self._session_key = session_key
        self._gateway_token = gateway_token
        self._timeout = timeout_sec
        self._workspace_root = workspace_root

    def execute(self, validated: ValidatedAction, *, task_id: str | None = None) -> tuple[str, str]:
        message = self._build_message(validated, task_id=task_id)
        env = os.environ.copy()
        if self._gateway_token:
            env["OPENCLAW_GATEWAY_TOKEN"] = self._gateway_token

        try:
            result = subprocess.run(  # noqa: S603
                [
                    self._cli_path,
                    "agent",
                    "--json",
                    "--session-key",
                    self._session_key,
                    "--message",
                    message,
                ],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
                shell=False,
                env=env,
            )
        except FileNotFoundError as exc:
            raise GatewayInvokeError(
                f"OpenClaw CLI not found at '{self._cli_path}'",
                reason=FailureReason.UNKNOWN,
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise GatewayInvokeError(
                "OpenClaw agent execution timed out",
                reason=FailureReason.TIMEOUT,
            ) from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise GatewayInvokeError(
                f"OpenClaw agent failed (exit {result.returncode}): {detail[:500]}",
                reason=FailureReason.UNKNOWN,
            )

        return self._parse_agent_output(result.stdout)

    def _build_message(self, validated: ValidatedAction, *, task_id: str | None) -> str:
        action = validated.action.model_dump(mode="json")
        payload = {
            "prefix": EXECUTE_PREFIX,
            "task_id": task_id,
            "scope": validated.scope.value,
            "action": action,
            "resolved_source": validated.resolved_source,
            "resolved_destination": validated.resolved_destination,
            "workspace_root": self._workspace_root,
        }
        return (
            f"{EXECUTE_PREFIX}\n"
            "Execute exactly ONE validated action using OpenClaw file tools. "
            "Do not run any other commands or modify unrelated paths.\n"
            f"{json.dumps(payload, indent=2)}\n"
            'Reply with JSON only: {"status":"success"|"failure","message":"..."}'
        )

    def _parse_agent_output(self, stdout: str) -> tuple[str, str]:
        text = stdout.strip()
        if not text:
            raise GatewayInvokeError(
                "OpenClaw agent returned empty output",
                reason=FailureReason.UNKNOWN,
            )

        # openclaw agent --json may wrap payloads; find last JSON object in output.
        for candidate in reversed(self._json_candidates(text)):
            status = candidate.get("status")
            message = candidate.get("message")
            if status in ("success", "failure", "ok") and isinstance(message, str):
                if status in ("success", "ok"):
                    return message, text
                raise GatewayInvokeError(message, reason=FailureReason.UNKNOWN)

            nested = candidate.get("result")
            if isinstance(nested, dict):
                payloads = nested.get("payloads")
                if isinstance(payloads, list):
                    for item in payloads:
                        if not isinstance(item, dict):
                            continue
                        payload_text = item.get("text")
                        if not isinstance(payload_text, str):
                            continue
                        try:
                            inner = json.loads(payload_text)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(inner, dict):
                            inner_status = inner.get("status")
                            inner_message = inner.get("message")
                            if inner_status in ("success", "ok") and isinstance(inner_message, str):
                                return inner_message, text
                            if inner_status == "failure" and isinstance(inner_message, str):
                                raise GatewayInvokeError(
                                    inner_message, reason=FailureReason.UNKNOWN
                                )

        # Fall back to raw agent text if structured status missing.
        logger.warning("openclaw_agent_unstructured_response")
        return text[:500], text

    def _json_candidates(self, text: str) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                candidates.append(data)
                nested = data.get("result") or data.get("payload")
                if isinstance(nested, dict):
                    candidates.append(nested)
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                candidates.append(data)
        except json.JSONDecodeError:
            pass
        return candidates
