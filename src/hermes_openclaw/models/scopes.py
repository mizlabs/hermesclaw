"""Permission scopes — OpenClaw behaves as a restricted OS API layer."""

from __future__ import annotations

from enum import StrEnum

from hermes_openclaw.models.tasks import ActionType


class PermissionScope(StrEnum):
    """Scoped capabilities granted to the execution layer."""

    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    FILESYSTEM_DELETE = "filesystem.delete"
    APPLICATIONS_LAUNCH = "applications.launch"
    DESKTOP_CONTROL = "desktop.control"
    NETWORK_DISABLED = "network.disabled"
    TERMINAL_RESTRICTED = "terminal.restricted"


# Each action type requires exactly these scopes to execute.
ACTION_REQUIRED_SCOPES: dict[ActionType, frozenset[PermissionScope]] = {
    ActionType.LIST_FILES: frozenset({PermissionScope.FILESYSTEM_READ}),
    ActionType.CREATE_FOLDER: frozenset({PermissionScope.FILESYSTEM_WRITE}),
    ActionType.COPY_FILE: frozenset(
        {PermissionScope.FILESYSTEM_READ, PermissionScope.FILESYSTEM_WRITE}
    ),
    ActionType.MOVE_FILE: frozenset(
        {PermissionScope.FILESYSTEM_READ, PermissionScope.FILESYSTEM_WRITE}
    ),
    ActionType.LAUNCH_APP: frozenset({PermissionScope.APPLICATIONS_LAUNCH}),
    ActionType.EXEC: frozenset({PermissionScope.TERMINAL_RESTRICTED}),
}

# Actions Hermes may hallucinate — always blocked at the validator.
BLOCKED_ACTION_TYPES: frozenset[str] = frozenset(
    {
        "delete_file",
        "delete_folder",
        "remove_file",
        "rm",
        "format_disk",
        "shutdown",
        "reboot",
        "kill_process",
        "network_request",
        "download",
        "upload",
    }
)

# Default scopes granted to the execution gateway (network always disabled).
DEFAULT_GRANTED_SCOPES: frozenset[PermissionScope] = frozenset(
    {
        PermissionScope.FILESYSTEM_READ,
        PermissionScope.FILESYSTEM_WRITE,
        PermissionScope.APPLICATIONS_LAUNCH,
        PermissionScope.TERMINAL_RESTRICTED,
        PermissionScope.NETWORK_DISABLED,
    }
)
