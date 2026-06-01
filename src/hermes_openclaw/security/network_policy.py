"""Network security — offline-first, outbound disabled by default."""

from __future__ import annotations

from urllib.parse import urlparse


class NetworkPolicyError(Exception):
    """Raised when a network request violates policy."""


# Local-only endpoints permitted when network is enabled for LLM inference.
LOCAL_HOSTS: frozenset[str] = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
    }
)


class NetworkPolicy:
    """Controls outbound network access — disabled by default."""

    def __init__(
        self,
        network_enabled: bool = False,
        allowed_hosts: frozenset[str] | None = None,
    ) -> None:
        self._enabled = network_enabled
        self._allowed = allowed_hosts or LOCAL_HOSTS

    @property
    def network_enabled(self) -> bool:
        return self._enabled

    def check_url(self, url: str) -> None:
        """Validate a URL against network policy. Raises on violation."""
        if not self._enabled:
            raise NetworkPolicyError(
                "Outbound network access is disabled. " "Set NETWORK_ENABLED=true to opt in."
            )

        parsed = urlparse(url)
        host = parsed.hostname
        if host is None:
            raise NetworkPolicyError(f"Invalid URL: {url}")

        if host not in self._allowed:
            raise NetworkPolicyError(
                f"Host '{host}' is not in the allowed list: {sorted(self._allowed)}"
            )

    def assert_offline(self) -> None:
        """Fail fast if any network call is attempted while offline mode is active."""
        if not self._enabled:
            raise NetworkPolicyError("Network access blocked — offline-first mode active")
