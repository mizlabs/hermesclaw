"""Tests for filesystem path security."""

from pathlib import Path

import pytest

from hermes_openclaw.security.path_guard import PathGuard, PathGuardError


@pytest.fixture
def guard(tmp_path: Path) -> PathGuard:
    return PathGuard(workspace_root=tmp_path)


def test_allows_workspace_path(guard: PathGuard, tmp_path: Path):
    resolved = guard.resolve(str(tmp_path / "docs"))
    assert resolved == (tmp_path / "docs").resolve()


def test_allows_relative_path(guard: PathGuard, tmp_path: Path):
    resolved = guard.resolve("subdir/file.txt")
    assert tmp_path.resolve() in resolved.parents or resolved.parent == tmp_path.resolve()


def test_blocks_sensitive_paths(guard: PathGuard):
    with pytest.raises(PathGuardError, match="sensitive"):
        guard.resolve("/etc/passwd")


def test_blocks_outside_workspace(guard: PathGuard):
    with pytest.raises(PathGuardError, match="outside allowed"):
        guard.resolve("/opt/outside")
