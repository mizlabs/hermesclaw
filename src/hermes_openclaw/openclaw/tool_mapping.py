"""Map HermesClaw validated actions to OpenClaw /tools/invoke calls."""

from __future__ import annotations

import shlex
from pathlib import Path

from hermes_openclaw.models.scopes import PermissionScope
from hermes_openclaw.models.tasks import ActionType
from hermes_openclaw.models.validation import ValidatedAction
from hermes_openclaw.openclaw.gateway_client import GatewayToolCall
from hermes_openclaw.security.command_policy import CommandPolicy, CommandPolicyError
from hermes_openclaw.security.path_guard import PathGuard


def scopes_for_action(validated: ValidatedAction) -> list[str]:
    """HermesClaw scopes to forward as gateway headers (audit / trusted-proxy modes)."""
    scopes = {validated.scope.value}
    scopes.update(scope.value for scope in validated.required_scopes)
    if PermissionScope.NETWORK_DISABLED.value not in scopes:
        scopes.add(PermissionScope.NETWORK_DISABLED.value)
    return sorted(scopes)


def map_action_to_calls(
    validated: ValidatedAction,
    *,
    path_guard: PathGuard,
    command_policy: CommandPolicy,
) -> list[GatewayToolCall]:
    """Translate one validated action into one or more gateway tool invocations."""
    action = validated.action

    if action.type == ActionType.LIST_FILES:
        path = validated.resolved_source or str(path_guard.resolve(action.source or ""))
        return [GatewayToolCall(tool="read", args={"path": path})]

    if action.type == ActionType.CREATE_FOLDER:
        path = validated.resolved_destination or str(path_guard.resolve(action.destination or ""))
        keep_file = str(Path(path) / ".hermesclaw_keep")
        patch = "*** Begin Patch\n" f"*** Add File: {keep_file}\n" "+\n" "*** End Patch\n"
        return [GatewayToolCall(tool="apply_patch", args={"input": patch})]

    if action.type == ActionType.COPY_FILE:
        src = validated.resolved_source or str(path_guard.resolve(action.source or ""))
        dst = validated.resolved_destination or str(path_guard.resolve(action.destination or ""))
        return [
            GatewayToolCall(tool="read", args={"path": src}),
            GatewayToolCall(
                tool="write",
                args={"path": dst, "content": f"__HERMESCLAW_COPY__:{src}"},
            ),
        ]

    if action.type == ActionType.MOVE_FILE:
        src = validated.resolved_source or str(path_guard.resolve(action.source or ""))
        dst = validated.resolved_destination or str(path_guard.resolve(action.destination or ""))
        patch = (
            "*** Begin Patch\n"
            f"*** Update File: {src}\n"
            f"*** Move to: {dst}\n"
            "*** End Patch\n"
        )
        return [GatewayToolCall(tool="apply_patch", args={"input": patch})]

    if action.type == ActionType.EXEC:
        argv = command_policy.validate(action.command or "", action.args)
        command = shlex.join(argv)
        return [GatewayToolCall(tool="exec", args={"command": command})]

    if action.type == ActionType.LAUNCH_APP:
        app = action.app_name or ""
        command = f"open -a {shlex.quote(app)}"
        return [GatewayToolCall(tool="exec", args={"command": command})]

    msg = f"Unhandled action type for gateway mapping: {action.type}"
    raise ValueError(msg)


def format_gateway_result(tool: str, result: object) -> str:
    """Human-readable message from an OpenClaw tool result."""
    if result is None:
        return f"{tool}: ok"
    if isinstance(result, str):
        text = result.strip()
        return text if text else f"{tool}: ok"
    if isinstance(result, dict):
        for key in ("content", "output", "stdout", "message", "text"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return f"{tool}: {result}"
    return f"{tool}: {result!r}"


def resolve_copy_write_args(
    read_result: object,
    pending_write: GatewayToolCall,
) -> GatewayToolCall:
    """
    Replace the COPY_FILE placeholder write args with content from a prior read call.
    """
    marker = pending_write.args.get("content", "")
    if not isinstance(marker, str) or not marker.startswith("__HERMESCLAW_COPY__:"):
        return pending_write

    content = ""
    if isinstance(read_result, str):
        content = read_result
    elif isinstance(read_result, dict):
        for key in ("content", "text", "output"):
            value = read_result.get(key)
            if isinstance(value, str):
                content = value
                break

    return GatewayToolCall(
        tool=pending_write.tool,
        args={"path": pending_write.args["path"], "content": content},
    )


def mapping_precheck(
    validated: ValidatedAction,
    *,
    command_policy: CommandPolicy,
) -> CommandPolicyError | None:
    """Validate exec argv before hitting the gateway."""
    if validated.action.type != ActionType.EXEC:
        return None
    try:
        command_policy.validate(validated.action.command or "", validated.action.args)
    except CommandPolicyError as exc:
        return exc
    return None
