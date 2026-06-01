"""Filesystem security — restricted directories, path traversal protection."""

from __future__ import annotations

from pathlib import Path


class PathGuardError(Exception):
    """Raised when a path violates security policy."""


# Paths that must never be touched by automation, regardless of configuration.
# Note: /private is intentionally excluded — on macOS all paths resolve under it.
DEFAULT_DENIED_PATHS: frozenset[str] = frozenset(
    {
        "/etc",
        "/var/log",
        "/usr",
        "/bin",
        "/sbin",
        "/System",
        "/Library",
        "~/.ssh",
        "~/.gnupg",
        "~/.aws",
        "~/.config",
    }
)


class PathGuard:
    """Validates that all filesystem operations stay within allowed boundaries."""

    def __init__(
        self,
        workspace_root: Path,
        allowed_roots: list[Path] | None = None,
        denied_paths: frozenset[str] | None = None,
    ) -> None:
        self._workspace = workspace_root.resolve()
        self._allowed = [p.resolve() for p in (allowed_roots or [self._workspace])]
        self._denied = denied_paths or DEFAULT_DENIED_PATHS

    def resolve(self, raw_path: str) -> Path:
        """Resolve and validate a user/LLM-provided path."""
        expanded = Path(raw_path).expanduser()
        if not expanded.is_absolute():
            expanded = (self._workspace / expanded).resolve()
        else:
            expanded = expanded.resolve()

        self._check_traversal(expanded)
        # Workspace paths take precedence over global denied paths (macOS /private/var/...).
        if self._is_under_allowed(expanded):
            return expanded
        self._check_denied(expanded)
        self._check_allowed(expanded)
        return expanded

    def _is_under_allowed(self, path: Path) -> bool:
        return any(path == root or root in path.parents for root in self._allowed)

    def _check_denied(self, path: Path) -> None:
        home = Path.home()
        for denied in self._denied:
            denied_resolved = Path(denied.replace("~", str(home))).expanduser().resolve()
            if path == denied_resolved or denied_resolved in path.parents:
                raise PathGuardError(f"Access denied to sensitive path: {path}")

    def _check_allowed(self, path: Path) -> None:
        for root in self._allowed:
            if path == root or root in path.parents:
                return
        raise PathGuardError(
            f"Path '{path}' is outside allowed directories: {[str(r) for r in self._allowed]}"
        )

    def _check_traversal(self, path: Path) -> None:
        # After resolve(), '..' components are eliminated — verify resolved path
        # still sits under at least one allowed root (already done in _check_allowed).
        if ".." in path.parts:
            raise PathGuardError(f"Path traversal detected: {path}")
