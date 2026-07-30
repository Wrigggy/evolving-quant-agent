"""Process-local weighted leases for one self-hosted sandbox coordinator."""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable


_RESOURCE_FIELDS = (
    "cpu_count",
    "memory_mb",
    "pids_limit",
    "tmpfs_mb",
    "sandboxes",
)
_HEALTH_RECHECK_SECONDS = 0.1


class ResourceLeaseError(RuntimeError):
    """A weighted host resource lease could not be granted or maintained."""


class ResourceLeaseTimeout(ResourceLeaseError):
    """A resource request was not admitted before its monotonic deadline."""


def _require_positive_integer(name: str, value: object) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _require_nonnegative_integer(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _require_nonnegative_finite_number(name: str, value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{name} must be a non-negative finite number")
    return float(value)


@dataclass(frozen=True)
class ResourceRequest:
    """Resources reserved for one or more concurrently live sandboxes."""

    cpu_count: int
    memory_mb: int
    pids_limit: int
    tmpfs_mb: int
    sandboxes: int = 1

    def __post_init__(self) -> None:
        for name in _RESOURCE_FIELDS:
            _require_positive_integer(name, getattr(self, name))


@dataclass(frozen=True)
class ResourceCapacity:
    """Usable host capacity after coordinator and runtime headroom."""

    cpu_count: int
    memory_mb: int
    pids_limit: int
    tmpfs_mb: int
    sandboxes: int

    def __post_init__(self) -> None:
        for name in _RESOURCE_FIELDS:
            _require_positive_integer(name, getattr(self, name))


@dataclass(frozen=True)
class HostHealthSnapshot:
    """Admission-sensitive host measurements captured by a trusted probe."""

    load_1m: float
    available_memory_mb: int
    free_disk_mb: int
    free_inodes: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "load_1m",
            _require_nonnegative_finite_number("load_1m", self.load_1m),
        )
        for name in ("available_memory_mb", "free_disk_mb", "free_inodes"):
            _require_nonnegative_integer(name, getattr(self, name))


@dataclass(frozen=True)
class HostHeadroomPolicy:
    """Minimum live host headroom required before granting a lease."""

    max_load_1m: float
    min_available_memory_mb: int
    min_free_disk_mb: int
    min_free_inodes: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_load_1m",
            _require_nonnegative_finite_number("max_load_1m", self.max_load_1m),
        )
        for name in (
            "min_available_memory_mb",
            "min_free_disk_mb",
            "min_free_inodes",
        ):
            _require_nonnegative_integer(name, getattr(self, name))


@dataclass(frozen=True)
class _Waiter:
    ticket: int
    key: str
    request: ResourceRequest


@dataclass(frozen=True)
class _LiveLease:
    ticket: int
    request: ResourceRequest


@dataclass(frozen=True)
class _AvailableResources:
    cpu_count: int
    memory_mb: int
    pids_limit: int
    tmpfs_mb: int
    sandboxes: int

    def __post_init__(self) -> None:
        for name in _RESOURCE_FIELDS:
            _require_nonnegative_integer(name, getattr(self, name))


class ResourceLease:
    """One idempotently releasable reservation from a host resource pool."""

    def __init__(
        self,
        pool: "HostResourceLeasePool",
        key: str,
        request: ResourceRequest,
        ticket: int,
    ) -> None:
        self._pool = pool
        self.key = key
        self.request = request
        self._ticket = ticket

    def release(self) -> None:
        """Return this reservation once; repeated or concurrent calls are safe."""

        self._pool._release(self)

    def __enter__(self) -> "ResourceLease":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()


class HostResourceLeasePool:
    """Grant FIFO leases with exact accounting across five host dimensions.

    The pool intentionally coordinates only threads in this process. The
    rootless runtime separately owns the exclusive run-root coordinator lock;
    lifecycle records and the reaper remain responsible for crash recovery.
    """

    def __init__(
        self,
        capacity: ResourceCapacity,
        headroom_policy: HostHeadroomPolicy,
        health_probe: Callable[[], HostHealthSnapshot],
    ) -> None:
        if not isinstance(capacity, ResourceCapacity):
            raise ValueError("capacity must be a ResourceCapacity")
        if not isinstance(headroom_policy, HostHeadroomPolicy):
            raise ValueError("headroom_policy must be a HostHeadroomPolicy")
        if not callable(health_probe):
            raise ValueError("health_probe must be callable")
        self.capacity = capacity
        self.headroom_policy = headroom_policy
        self._health_probe = health_probe
        self._available = _AvailableResources(
            **{name: getattr(capacity, name) for name in _RESOURCE_FIELDS}
        )
        self._condition = threading.Condition()
        self._waiters: deque[_Waiter] = deque()
        self._live: dict[str, _LiveLease] = {}
        self._next_ticket = 0

    @staticmethod
    def _fits(
        request: ResourceRequest,
        available: ResourceCapacity | _AvailableResources,
    ) -> bool:
        return all(
            getattr(request, name) <= getattr(available, name)
            for name in _RESOURCE_FIELDS
        )

    def _exceeds_capacity(self, request: ResourceRequest) -> bool:
        return not self._fits(request, self.capacity)

    @staticmethod
    def _subtract(
        available: _AvailableResources, request: ResourceRequest
    ) -> _AvailableResources:
        return _AvailableResources(
            **{
                name: getattr(available, name) - getattr(request, name)
                for name in _RESOURCE_FIELDS
            }
        )

    @staticmethod
    def _add(
        available: _AvailableResources, request: ResourceRequest
    ) -> _AvailableResources:
        return _AvailableResources(
            **{
                name: getattr(available, name) + getattr(request, name)
                for name in _RESOURCE_FIELDS
            }
        )

    def _headroom_failures(self, snapshot: HostHealthSnapshot) -> tuple[str, ...]:
        policy = self.headroom_policy
        failures: list[str] = []
        if snapshot.load_1m > policy.max_load_1m:
            failures.append(
                f"load_1m={snapshot.load_1m} exceeds "
                f"max_load_1m={policy.max_load_1m}"
            )
        if snapshot.available_memory_mb < policy.min_available_memory_mb:
            failures.append(
                f"available_memory_mb={snapshot.available_memory_mb} is below "
                f"min_available_memory_mb={policy.min_available_memory_mb}"
            )
        if snapshot.free_disk_mb < policy.min_free_disk_mb:
            failures.append(
                f"free_disk_mb={snapshot.free_disk_mb} is below "
                f"min_free_disk_mb={policy.min_free_disk_mb}"
            )
        if snapshot.free_inodes < policy.min_free_inodes:
            failures.append(
                f"free_inodes={snapshot.free_inodes} is below "
                f"min_free_inodes={policy.min_free_inodes}"
            )
        return tuple(failures)

    def _drop_waiter(self, waiter: _Waiter) -> None:
        try:
            self._waiters.remove(waiter)
        except ValueError:
            return
        self._condition.notify_all()

    def _timeout_error(
        self,
        key: str,
        request: ResourceRequest,
        health_failures: tuple[str, ...],
    ) -> ResourceLeaseTimeout:
        health = "; ".join(health_failures) if health_failures else "healthy"
        available = ", ".join(
            f"{name}={getattr(self._available, name)}" for name in _RESOURCE_FIELDS
        )
        return ResourceLeaseTimeout(
            f"resource lease deadline expired for key={key!r}; "
            f"requested={request}; available=ResourceCapacity({available}); "
            f"health={health}"
        )

    def acquire(
        self,
        key: str,
        request: ResourceRequest,
        *,
        timeout_seconds: float = 120.0,
    ) -> ResourceLease:
        """Wait in FIFO order for capacity and healthy host headroom."""

        if not isinstance(key, str) or not key.strip():
            raise ValueError("lease key must be a non-empty string")
        if not isinstance(request, ResourceRequest):
            raise ValueError("request must be a ResourceRequest")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds < 0
        ):
            raise ValueError("timeout_seconds must be a non-negative finite number")

        deadline = time.monotonic() + float(timeout_seconds)
        with self._condition:
            if key in self._live:
                raise ResourceLeaseError(f"duplicate live lease key: {key!r}")
            if self._exceeds_capacity(request):
                raise ResourceLeaseError(
                    f"resource request exceeds capacity for key={key!r}; "
                    f"requested={request}; capacity={self.capacity}"
                )

            waiter = _Waiter(self._next_ticket, key, request)
            self._next_ticket += 1
            self._waiters.append(waiter)
            health_failures: tuple[str, ...] = ()

            while True:
                if key in self._live:
                    self._drop_waiter(waiter)
                    raise ResourceLeaseError(f"duplicate live lease key: {key!r}")

                is_head = bool(self._waiters) and self._waiters[0] is waiter
                if is_head:
                    try:
                        snapshot = self._health_probe()
                    except Exception as exc:
                        self._drop_waiter(waiter)
                        raise ResourceLeaseError("host health probe failed") from exc
                    if not isinstance(snapshot, HostHealthSnapshot):
                        self._drop_waiter(waiter)
                        raise ResourceLeaseError(
                            "health_probe must return a HostHealthSnapshot"
                        )
                    health_failures = self._headroom_failures(snapshot)
                    if timeout_seconds > 0 and time.monotonic() >= deadline:
                        self._drop_waiter(waiter)
                        raise self._timeout_error(key, request, health_failures)
                    if not health_failures and self._fits(request, self._available):
                        self._available = self._subtract(self._available, request)
                        self._waiters.popleft()
                        self._live[key] = _LiveLease(waiter.ticket, request)
                        self._condition.notify_all()
                        return ResourceLease(self, key, request, waiter.ticket)

                remaining = deadline - time.monotonic()
                if timeout_seconds == 0 or remaining <= 0:
                    self._drop_waiter(waiter)
                    raise self._timeout_error(key, request, health_failures)

                wait_seconds = remaining
                if is_head and health_failures:
                    wait_seconds = min(wait_seconds, _HEALTH_RECHECK_SECONDS)
                self._condition.wait(timeout=wait_seconds)

    def _release(self, lease: ResourceLease) -> None:
        with self._condition:
            live = self._live.get(lease.key)
            if live is None or live.ticket != lease._ticket:
                return
            del self._live[lease.key]
            self._available = self._add(self._available, live.request)
            self._condition.notify_all()
