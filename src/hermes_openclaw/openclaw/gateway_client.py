"""HTTP client for the OpenClaw Gateway /tools/invoke API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from hermes_openclaw.models.execution import FailureReason

logger = structlog.get_logger()


class GatewayInvokeError(Exception):
    """OpenClaw gateway rejected or failed a tool invocation."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        reason: FailureReason = FailureReason.UNKNOWN,
        tool: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason
        self.tool = tool


@dataclass(frozen=True)
class GatewayToolCall:
    """A single OpenClaw /tools/invoke request."""

    tool: str
    args: dict[str, Any]


class OpenClawGatewayClient:
    """
    Thin wrapper around POST /tools/invoke.

    See: https://docs.openclaw.ai/gateway/tools-invoke-http-api
    """

    def __init__(
        self,
        base_url: str,
        *,
        token: str = "",
        session_key: str = "main",
        timeout_sec: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._session_key = session_key
        self._timeout = timeout_sec

    @property
    def configured(self) -> bool:
        return bool(self._base_url)

    def ping(self) -> bool:
        """Return True when the gateway accepts authenticated tool calls."""
        try:
            self.invoke(GatewayToolCall(tool="sessions_list", args={"action": "json"}))
            return True
        except GatewayInvokeError as exc:
            logger.warning("openclaw_gateway_ping_failed", error=str(exc))
            return False

    def invoke(
        self,
        call: GatewayToolCall,
        *,
        scopes: list[str] | None = None,
        task_id: str | None = None,
        validation_id: str | None = None,
    ) -> Any:
        url = f"{self._base_url}/tools/invoke"
        payload: dict[str, Any] = {
            "tool": call.tool,
            "args": call.args,
            "sessionKey": self._session_key,
            "dryRun": False,
        }
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if scopes:
            headers["x-openclaw-scopes"] = ",".join(scopes)
            headers["x-hermesclaw-scopes"] = ",".join(scopes)
        if task_id:
            headers["x-hermesclaw-task-id"] = task_id
        if validation_id:
            headers["x-hermesclaw-validation-id"] = validation_id

        try:
            with httpx.Client(timeout=self._timeout, trust_env=False) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.RequestError as exc:
            raise GatewayInvokeError(
                f"Gateway unreachable at {self._base_url}: {exc}",
                reason=FailureReason.UNKNOWN,
                tool=call.tool,
            ) from exc

        return self._parse_response(response, call.tool)

    def _parse_response(self, response: httpx.Response, tool: str) -> Any:
        if response.status_code == 401:
            raise GatewayInvokeError(
                "Gateway authentication failed — check OPENCLAW_GATEWAY_TOKEN",
                status_code=401,
                reason=FailureReason.PERMISSION_DENIED,
                tool=tool,
            )
        if response.status_code == 404:
            raise GatewayInvokeError(
                f"Tool not available over HTTP: {tool}. "
                "Configure gateway.tools.allow in OpenClaw for coding tools.",
                status_code=404,
                reason=FailureReason.POLICY_DENIED,
                tool=tool,
            )
        if response.status_code == 429:
            raise GatewayInvokeError(
                "Gateway auth rate-limited",
                status_code=429,
                reason=FailureReason.PERMISSION_DENIED,
                tool=tool,
            )

        body: dict[str, Any]
        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise GatewayInvokeError(
                f"Invalid JSON from gateway ({response.status_code})",
                status_code=response.status_code,
                tool=tool,
            ) from exc

        if response.status_code >= 400 or not body.get("ok", False):
            error = body.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else str(error)
            if not message:
                message = f"Gateway error ({response.status_code})"
            reason = (
                FailureReason.POLICY_DENIED
                if response.status_code == 400
                else FailureReason.UNKNOWN
            )
            raise GatewayInvokeError(
                message,
                status_code=response.status_code,
                reason=reason,
                tool=tool,
            )

        return body.get("result")
