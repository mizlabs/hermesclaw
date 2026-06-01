"""Tests for command execution policy."""

import pytest

from hermes_openclaw.security.command_policy import CommandPolicy, CommandPolicyError


@pytest.fixture
def policy() -> CommandPolicy:
    return CommandPolicy()


def test_allows_listed_command(policy: CommandPolicy):
    argv = policy.validate("ls -la")
    assert argv == ["ls", "-la"]


def test_blocks_rm(policy: CommandPolicy):
    with pytest.raises(CommandPolicyError, match="blocked"):
        policy.validate("rm -rf /")


def test_blocks_shell_interpreter(policy: CommandPolicy):
    with pytest.raises(CommandPolicyError, match="blocked"):
        policy.validate("bash -c 'echo pwned'")


def test_blocks_unlisted_command(policy: CommandPolicy):
    with pytest.raises(CommandPolicyError, match="not in the allowlist"):
        policy.validate("unzip archive.zip")


def test_validates_with_extra_args(policy: CommandPolicy):
    argv = policy.validate("ls", ["-la", "/tmp"])
    assert argv == ["ls", "-la", "/tmp"]
