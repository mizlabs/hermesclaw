"""Command execution security — allowlisted commands only, no arbitrary shell."""

from __future__ import annotations

import shlex


class CommandPolicyError(Exception):
    """Raised when a command violates execution policy."""


# Only these base commands may be invoked. No shell interpreters.
DEFAULT_ALLOWED_COMMANDS: frozenset[str] = frozenset(
    {
        "ls",
        "cp",
        "mv",
        "mkdir",
        "cat",
        "echo",
        "find",
        "grep",
        "head",
        "tail",
        "wc",
        "sort",
        "open",  # macOS app launcher
        "xdg-open",  # Linux app launcher
    }
)

# Commands that are always blocked even if allowlisted.
BLOCKED_COMMANDS: frozenset[str] = frozenset(
    {
        "rm",
        "rmdir",
        "sudo",
        "su",
        "chmod",
        "chown",
        "kill",
        "pkill",
        "curl",
        "wget",
        "ssh",
        "scp",
        "bash",
        "sh",
        "zsh",
        "python",
        "python3",
        "node",
        "eval",
        "exec",
    }
)


class CommandPolicy:
    """Enforces allowlisted, argument-sanitized command execution."""

    def __init__(
        self,
        allowed_commands: frozenset[str] | None = None,
        blocked_commands: frozenset[str] | None = None,
    ) -> None:
        self._allowed = allowed_commands or DEFAULT_ALLOWED_COMMANDS
        self._blocked = blocked_commands or BLOCKED_COMMANDS

    def validate(self, command: str, args: list[str] | None = None) -> list[str]:
        """
        Validate and return a safe argv list for subprocess execution.

        Never passes through a shell — caller must use subprocess with shell=False.
        """
        try:
            tokens = shlex.split(command)
        except ValueError as exc:
            raise CommandPolicyError(f"Malformed command: {exc}") from exc

        if args:
            tokens.extend(args)

        if not tokens:
            raise CommandPolicyError("Empty command")

        base = tokens[0]
        if base in self._blocked:
            raise CommandPolicyError(f"Command '{base}' is explicitly blocked")

        if base not in self._allowed:
            raise CommandPolicyError(
                f"Command '{base}' is not in the allowlist. " f"Allowed: {sorted(self._allowed)}"
            )

        return tokens
