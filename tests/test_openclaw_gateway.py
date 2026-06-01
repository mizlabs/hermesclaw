"""Tests for OpenClaw gateway bridge."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from hermes_openclaw.models.execution import ExecutionStatus, FailureReason
from hermes_openclaw.models.scopes import PermissionScope
from hermes_openclaw.models.tasks import TaskAction, TaskPlan
from hermes_openclaw.models.validation import ValidatedAction, ValidatedPlan
from hermes_openclaw.openclaw.adapter import OpenClawAdapter
from hermes_openclaw.openclaw.gateway_client import (
    GatewayToolCall,
    OpenClawGatewayClient,
)
from hermes_openclaw.openclaw.tool_mapping import map_action_to_calls, resolve_copy_write_args
from hermes_openclaw.security.audit import AuditLogger
from hermes_openclaw.security.command_policy import CommandPolicy
from hermes_openclaw.security.path_guard import PathGuard
from hermes_openclaw.security.plan_signing import PlanSigner
from hermes_openclaw.security.rate_limiter import ExecutionRateLimiter, RateLimitConfig


def _gateway_response(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content.decode())
    tool = body.get("tool")
    if tool == "sessions_list":
        return httpx.Response(200, json={"ok": True, "result": {"sessions": []}})
    if tool == "read":
        return httpx.Response(200, json={"ok": True, "result": {"content": "hello"}})
    if tool == "write":
        return httpx.Response(200, json={"ok": True, "result": {"path": body["args"]["path"]}})
    if tool == "apply_patch":
        return httpx.Response(200, json={"ok": True, "result": "patched"})
    return httpx.Response(404, json={"ok": False, "error": {"message": f"unknown tool {tool}"}})


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    root.mkdir()
    return root


@pytest.fixture
def adapter(workspace: Path) -> OpenClawAdapter:
    transport = httpx.MockTransport(_gateway_response)
    client = OpenClawGatewayClient(
        "http://127.0.0.1:18789",
        token="test-token",
    )

    def mock_post(url: str, *, json: dict, headers: dict) -> httpx.Response:  # noqa: A002
        request = httpx.Request("POST", url, json=json, headers=headers)
        return transport.handle_request(request)

    client.invoke = lambda call, **kwargs: _invoke_via_mock(client, call, mock_post)  # type: ignore[method-assign]
    return OpenClawAdapter(
        path_guard=PathGuard(workspace),
        command_policy=CommandPolicy(),
        audit_logger=AuditLogger(workspace.parent / "audit.jsonl"),
        plan_signer=PlanSigner("test-secret"),
        rate_limiter=ExecutionRateLimiter(RateLimitConfig()),
        execution_mode="gateway",
        gateway_client=client,
    )


def _invoke_via_mock(
    client: OpenClawGatewayClient,
    call,
    mock_post,
):
    url = f"{client._base_url}/tools/invoke"
    payload = {
        "tool": call.tool,
        "args": call.args,
        "sessionKey": client._session_key,
        "dryRun": False,
    }
    headers = {"Content-Type": "application/json"}
    if client._token:
        headers["Authorization"] = f"Bearer {client._token}"
    response = mock_post(url, json=payload, headers=headers)
    return client._parse_response(response, call.tool)


def _signed_plan(
    workspace: Path,
    action: TaskAction,
    *,
    signer: PlanSigner | None = None,
    scope: PermissionScope = PermissionScope.FILESYSTEM_WRITE,
    resolved_source: str | None = None,
    resolved_destination: str | None = None,
) -> ValidatedPlan:
    signer = signer or PlanSigner("test-secret")
    plan = TaskPlan(intent="gateway test", actions=[action])
    validated = ValidatedPlan(
        plan=plan,
        actions=[
            ValidatedAction(
                action=action,
                scope=scope,
                resolved_destination=resolved_destination
                or (str(workspace / action.destination) if action.destination else None),
                resolved_source=resolved_source
                or (str(workspace / action.source) if action.source else None),
            )
        ],
        granted_scopes=[scope],
    )
    validated.execution_token = signer.sign(validated)
    return validated


def test_map_create_folder_to_apply_patch(workspace: Path):
    action = ValidatedAction(
        action=TaskAction(type="create_folder", destination="demo"),
        scope=PermissionScope.FILESYSTEM_WRITE,
        resolved_destination=str(workspace / "demo"),
    )
    calls = map_action_to_calls(
        action,
        path_guard=PathGuard(workspace),
        command_policy=CommandPolicy(),
    )
    assert len(calls) == 1
    assert calls[0].tool == "apply_patch"
    assert ".hermesclaw_keep" in calls[0].args["input"]


def test_resolve_copy_write_args():
    pending = resolve_copy_write_args(
        {"content": "file body"},
        GatewayToolCall(
            tool="write",
            args={"path": "/dst", "content": "__HERMESCLAW_COPY__:/src"},
        ),
    )
    assert pending.args["content"] == "file body"


def test_gateway_create_folder(adapter: OpenClawAdapter, workspace: Path):
    plan = _signed_plan(workspace, TaskAction(type="create_folder", destination="demo"))
    report = adapter.execute_sync(plan)
    assert report.status == ExecutionStatus.SUCCESS
    assert report.results[0].action_type == "create_folder"


def test_gateway_list_files(adapter: OpenClawAdapter, workspace: Path):
    plan = _signed_plan(
        workspace,
        TaskAction(type="list_files", source="."),
        scope=PermissionScope.FILESYSTEM_READ,
        resolved_source=str(workspace),
    )
    report = adapter.execute_sync(plan)
    assert report.status == ExecutionStatus.SUCCESS


def test_gateway_auth_failure(workspace: Path):
    def unauthorized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "error": {"message": "unauthorized"}})

    transport = httpx.MockTransport(unauthorized)
    client = OpenClawGatewayClient("http://127.0.0.1:18789", token="bad")

    def invoke(call, **kwargs):
        request = httpx.Request(
            "POST",
            f"{client._base_url}/tools/invoke",
            json={"tool": call.tool, "args": call.args},
        )
        return client._parse_response(transport.handle_request(request), call.tool)

    client.invoke = invoke  # type: ignore[method-assign]
    adapter = OpenClawAdapter(
        path_guard=PathGuard(workspace),
        command_policy=CommandPolicy(),
        audit_logger=AuditLogger(workspace.parent / "audit.jsonl"),
        plan_signer=PlanSigner("test-secret"),
        rate_limiter=ExecutionRateLimiter(RateLimitConfig()),
        execution_mode="gateway",
        gateway_client=client,
    )
    plan = _signed_plan(
        workspace,
        TaskAction(type="list_files", source="."),
        scope=PermissionScope.FILESYSTEM_READ,
        resolved_source=str(workspace),
    )
    report = adapter.execute_sync(plan)
    assert report.status == ExecutionStatus.FAILURE
    assert report.results[0].reason == FailureReason.PERMISSION_DENIED


def test_auto_mode_falls_back_to_local(workspace: Path):
    def unreachable(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=httpx.Request("GET", "http://x"))

    client = OpenClawGatewayClient("http://127.0.0.1:1", token="test")
    client.ping = lambda: False  # type: ignore[method-assign]
    adapter = OpenClawAdapter(
        path_guard=PathGuard(workspace),
        command_policy=CommandPolicy(),
        audit_logger=AuditLogger(workspace.parent / "audit.jsonl"),
        plan_signer=PlanSigner("test-secret"),
        rate_limiter=ExecutionRateLimiter(RateLimitConfig()),
        execution_mode="auto",
        gateway_client=client,
    )
    plan = _signed_plan(workspace, TaskAction(type="create_folder", destination="local_only"))
    report = adapter.execute_sync(plan)
    assert report.status == ExecutionStatus.SUCCESS
    assert (workspace / "local_only").is_dir()
