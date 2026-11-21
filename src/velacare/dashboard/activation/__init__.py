"""Optional workspace activation boundary.

The dashboard process is not an always-on activation gateway. The default
provider is deliberately inert; a real external provider belongs in a future
always-reachable, authenticated bootstrap service.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import Lock
from typing import Any, Mapping, Protocol


class ActivationState(StrEnum):
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    READY = "ready"
    AUTH_REQUIRED = "auth_required"
    ERROR = "error"


@dataclass(frozen=True)
class ActivationStatus:
    status: ActivationState
    detail: str
    retry_after: int | None = None
    enabled: bool = True
    simulated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "detail": self.detail,
            "retry_after": self.retry_after,
            "enabled": self.enabled,
            "simulated": self.simulated,
        }


@dataclass(frozen=True)
class ActivationResult:
    accepted: bool
    status: ActivationState
    detail: str
    retry_after: int | None = None
    simulated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "status": self.status.value,
            "detail": self.detail,
            "retry_after": self.retry_after,
            "simulated": self.simulated,
        }


class ActivationProvider(Protocol):
    """Status/start interface for a future, separately hosted activation API."""

    enabled: bool
    simulated: bool

    def get_status(self, context: Mapping[str, Any] | None = None) -> ActivationStatus:
        """Return workspace availability without conflating it with app health."""

    def request_start(
        self,
        context: Mapping[str, Any] | None,
        idempotency_key: str,
    ) -> ActivationResult:
        """Request an authorized, idempotent workspace start."""


class DisabledActivationProvider:
    """Default provider: report unknown and never make network or start calls."""

    enabled = False
    simulated = False

    def get_status(self, context: Mapping[str, Any] | None = None) -> ActivationStatus:
        return ActivationStatus(
            ActivationState.UNKNOWN,
            "External workspace activation is not configured.",
            enabled=False,
        )

    def request_start(
        self,
        context: Mapping[str, Any] | None = None,
        idempotency_key: str = "",
    ) -> ActivationResult:
        return ActivationResult(
            False,
            ActivationState.UNAVAILABLE,
            "No workspace activation provider is configured.",
        )


class MockActivationProvider:
    """Opt-in local state machine for UI and adapter tests; it performs no I/O."""

    enabled = True
    simulated = True
    _SCENARIOS = {"success", "error", "auth_required", "timeout"}

    def __init__(self, scenario: str = "success") -> None:
        if scenario not in self._SCENARIOS:
            raise ValueError(f"Unsupported mock activation scenario: {scenario!r}.")
        self.scenario = scenario
        self._lock = Lock()
        self._started = False
        self._polls = 0
        self._requests: dict[str, ActivationResult] = {}
        self._terminal_status: ActivationState | None = None

    def get_status(self, context: Mapping[str, Any] | None = None) -> ActivationStatus:
        del context
        with self._lock:
            if self._terminal_status is not None:
                detail = (
                    "Simulated authorization is required."
                    if self._terminal_status == ActivationState.AUTH_REQUIRED
                    else "Simulated activation failed."
                )
                return ActivationStatus(self._terminal_status, detail, simulated=True)
            if not self._started:
                return ActivationStatus(
                    ActivationState.STOPPED,
                    "Mock provider reports a stopped workspace.",
                    simulated=True,
                )
            if self.scenario == "timeout":
                self._polls += 1
                if self._polls <= 1:
                    return ActivationStatus(
                        ActivationState.STARTING,
                        "Mock workspace is starting; simulating a delayed response.",
                        retry_after=1,
                        simulated=True,
                    )
                self._terminal_status = ActivationState.ERROR
                return ActivationStatus(
                    ActivationState.ERROR,
                    "Mock activation timed out.",
                    simulated=True,
                )
            self._polls += 1
            state = ActivationState.RUNNING if self._polls == 1 else ActivationState.READY
            detail = (
                "Mock workspace is running; dashboard readiness is checked separately."
                if state == ActivationState.RUNNING
                else "Mock workspace reports ready."
            )
            return ActivationStatus(state, detail, simulated=True)

    def request_start(
        self,
        context: Mapping[str, Any] | None = None,
        idempotency_key: str = "",
    ) -> ActivationResult:
        del context
        if not idempotency_key:
            raise ValueError("An idempotency key is required for mock activation.")
        with self._lock:
            if idempotency_key in self._requests:
                return self._requests[idempotency_key]
            if self.scenario == "auth_required":
                result = ActivationResult(
                    False,
                    ActivationState.AUTH_REQUIRED,
                    "Mock provider requires authorization; no sign-in is simulated.",
                    simulated=True,
                )
                self._terminal_status = ActivationState.AUTH_REQUIRED
            elif self.scenario == "error":
                result = ActivationResult(
                    False,
                    ActivationState.ERROR,
                    "Mock provider simulated an activation error.",
                    simulated=True,
                )
                self._terminal_status = ActivationState.ERROR
            else:
                self._started = True
                self._polls = 0
                result = ActivationResult(
                    True,
                    ActivationState.STARTING,
                    "Mock workspace start accepted (simulated).",
                    retry_after=1,
                    simulated=True,
                )
            self._requests[idempotency_key] = result
            return result


def activation_provider_for_mode(mode: str) -> ActivationProvider:
    """Build the explicitly selected provider; disabled is the safe default."""
    if mode == "disabled":
        return DisabledActivationProvider()
    if mode == "mock":
        return MockActivationProvider()
    raise ValueError("Activation mode must be 'disabled' or 'mock'.")


__all__ = [
    "ActivationProvider",
    "ActivationResult",
    "ActivationState",
    "ActivationStatus",
    "DisabledActivationProvider",
    "MockActivationProvider",
    "activation_provider_for_mode",
]
