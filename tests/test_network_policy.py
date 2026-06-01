"""Tests for network security policy."""

import pytest

from hermes_openclaw.security.network_policy import NetworkPolicy, NetworkPolicyError


def test_blocks_by_default():
    policy = NetworkPolicy(network_enabled=False)
    with pytest.raises(NetworkPolicyError, match="disabled"):
        policy.check_url("http://example.com")


def test_allows_localhost_when_enabled():
    policy = NetworkPolicy(network_enabled=True)
    policy.check_url("http://localhost:11434/v1")


def test_blocks_external_when_enabled():
    policy = NetworkPolicy(network_enabled=True)
    with pytest.raises(NetworkPolicyError, match="not in the allowed"):
        policy.check_url("https://api.openai.com/v1")
