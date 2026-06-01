"""Execution rate limits — prevents runaway agents."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitConfig:
    max_actions_per_minute: int = 20
    max_parallel_tasks: int = 3


class RateLimitExceeded(Exception):
    """Raised when an agent exceeds configured execution rate limits."""


class ExecutionRateLimiter:
    """
    Sliding-window rate limiter for action execution.

    Protects against runaway agents retrying or flooding the executor.
    """

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self._config = config or RateLimitConfig()
        self._action_timestamps: deque[float] = deque()
        self._active_tasks = 0
        self._lock = threading.Lock()

    @property
    def config(self) -> RateLimitConfig:
        return self._config

    @property
    def active_tasks(self) -> int:
        return self._active_tasks

    @property
    def actions_last_minute(self) -> int:
        self._prune()
        return len(self._action_timestamps)

    def check_and_acquire_task_slot(self) -> None:
        with self._lock:
            if self._active_tasks >= self._config.max_parallel_tasks:
                raise RateLimitExceeded(
                    f"Max parallel tasks ({self._config.max_parallel_tasks}) exceeded"
                )
            self._active_tasks += 1

    def release_task_slot(self) -> None:
        with self._lock:
            self._active_tasks = max(0, self._active_tasks - 1)

    def record_action(self) -> None:
        with self._lock:
            self._prune()
            if len(self._action_timestamps) >= self._config.max_actions_per_minute:
                raise RateLimitExceeded(
                    f"Max actions per minute ({self._config.max_actions_per_minute}) exceeded"
                )
            self._action_timestamps.append(time.monotonic())

    def _prune(self) -> None:
        cutoff = time.monotonic() - 60.0
        while self._action_timestamps and self._action_timestamps[0] < cutoff:
            self._action_timestamps.popleft()
