"""A small, dependency-free circuit breaker for calls to services we don't
control (Meta's Graph API, Gemini/ADK). No new pip package on purpose — this
is ~60 lines and every line is auditable, which matters more than reuse here.

States:
    CLOSED    — calls go through normally. Consecutive failures are counted.
    OPEN      — calls fail immediately (CircuitOpenError) without touching
                the dependency, for `reset_timeout_s` after the last failure.
                This is the point: once a dependency is clearly down, stop
                making the user wait through N more full timeouts.
    HALF_OPEN — after the timeout, the next call is allowed through as a
                probe. Success -> CLOSED. Failure -> back to OPEN.

Every state transition is logged at WARNING so it shows up in whatever log
pipeline you already have, and can be turned into a log-based metric for
alerting (see ops/alerts/) without any code change here.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger("vendorscoutai.circuit_breaker")

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised instead of calling through when the breaker is open."""


class CircuitBreaker:
    def __init__(self, name: str, fail_max: int = 3, reset_timeout_s: float = 30.0) -> None:
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout_s = reset_timeout_s
        self._lock = threading.Lock()
        self._failures = 0
        self._state = "closed"
        self._opened_at = 0.0

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def _check_and_maybe_probe(self) -> None:
        """Raise if open; flip to half_open if the cooldown has elapsed."""
        with self._lock:
            if self._state == "open":
                if time.time() - self._opened_at < self.reset_timeout_s:
                    raise CircuitOpenError(
                        f"{self.name}: circuit open, {self.fail_max} consecutive "
                        f"failures — retrying in "
                        f"{self.reset_timeout_s - (time.time() - self._opened_at):.0f}s"
                    )
                self._state = "half_open"
                logger.warning("circuit_breaker name=%s state=half_open (probe attempt)", self.name)

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        self._check_and_maybe_probe()
        try:
            result = func(*args, **kwargs)
        except Exception:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result

    async def acall(self, coro_func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Async counterpart of `call` — for coroutine dependencies (e.g. the
        ADK Runner talking to Gemini). Same state machine, same semantics."""
        self._check_and_maybe_probe()
        try:
            result = await coro_func(*args, **kwargs)
        except Exception:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result

    def _on_success(self) -> None:
        with self._lock:
            if self._state != "closed":
                logger.warning("circuit_breaker name=%s state=closed (recovered)", self.name)
            self._failures = 0
            self._state = "closed"

    def _on_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state == "half_open" or self._failures >= self.fail_max:
                self._state = "open"
                self._opened_at = time.time()
                logger.warning(
                    "circuit_breaker name=%s state=open failures=%d",
                    self.name, self._failures,
                )
