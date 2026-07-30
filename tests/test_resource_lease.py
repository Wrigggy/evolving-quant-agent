from __future__ import annotations

import math
import threading
from dataclasses import FrozenInstanceError

import pytest

import qea.resource_lease as resource_lease
from qea.resource_lease import (
    HostHeadroomPolicy,
    HostHealthSnapshot,
    HostResourceLeasePool,
    ResourceCapacity,
    ResourceLeaseError,
    ResourceLeaseTimeout,
    ResourceRequest,
)


HEALTHY = HostHealthSnapshot(
    load_1m=1.5,
    available_memory_mb=16_000,
    free_disk_mb=80_000,
    free_inodes=1_000_000,
)
POLICY = HostHeadroomPolicy(
    max_load_1m=8.0,
    min_available_memory_mb=8_000,
    min_free_disk_mb=40_000,
    min_free_inodes=500_000,
)


def _capacity(value: int = 4) -> ResourceCapacity:
    return ResourceCapacity(
        cpu_count=value,
        memory_mb=value,
        pids_limit=value,
        tmpfs_mb=value,
        sandboxes=value,
    )


def _request(value: int = 1, **overrides: int) -> ResourceRequest:
    values = {
        "cpu_count": value,
        "memory_mb": value,
        "pids_limit": value,
        "tmpfs_mb": value,
        "sandboxes": value,
    }
    values.update(overrides)
    return ResourceRequest(**values)


def _pool(
    capacity: ResourceCapacity | None = None,
    probe=lambda: HEALTHY,
    policy: HostHeadroomPolicy = POLICY,
) -> HostResourceLeasePool:
    return HostResourceLeasePool(capacity or _capacity(), policy, probe)


@pytest.mark.parametrize(
    "resource_type",
    [ResourceRequest, ResourceCapacity],
)
@pytest.mark.parametrize(
    "field",
    ["cpu_count", "memory_mb", "pids_limit", "tmpfs_mb", "sandboxes"],
)
def test_resource_dimensions_must_be_positive_integers(resource_type, field):
    values = {
        "cpu_count": 1,
        "memory_mb": 1,
        "pids_limit": 1,
        "tmpfs_mb": 1,
        "sandboxes": 1,
    }
    values[field] = 0

    with pytest.raises(ValueError, match=field):
        resource_type(**values)


@pytest.mark.parametrize("invalid", [True, 1.0, "1"])
def test_resource_dimensions_reject_non_integer_values(invalid):
    with pytest.raises(ValueError, match="cpu_count"):
        _request(cpu_count=invalid)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("load_1m", -0.1),
        ("load_1m", math.inf),
        ("load_1m", math.nan),
        ("available_memory_mb", -1),
        ("free_disk_mb", -1),
        ("free_inodes", -1),
    ],
)
def test_host_health_snapshot_rejects_invalid_measurements(field, invalid):
    values = {
        "load_1m": 0.0,
        "available_memory_mb": 0,
        "free_disk_mb": 0,
        "free_inodes": 0,
    }
    values[field] = invalid

    with pytest.raises(ValueError, match=field):
        HostHealthSnapshot(**values)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("max_load_1m", -0.1),
        ("max_load_1m", math.inf),
        ("max_load_1m", math.nan),
        ("min_available_memory_mb", -1),
        ("min_free_disk_mb", -1),
        ("min_free_inodes", -1),
    ],
)
def test_host_headroom_policy_rejects_invalid_limits(field, invalid):
    values = {
        "max_load_1m": 0.0,
        "min_available_memory_mb": 0,
        "min_free_disk_mb": 0,
        "min_free_inodes": 0,
    }
    values[field] = invalid

    with pytest.raises(ValueError, match=field):
        HostHeadroomPolicy(**values)


@pytest.mark.parametrize(
    "value",
    [
        _request(),
        _capacity(),
        HEALTHY,
        POLICY,
    ],
)
def test_resource_contract_values_are_immutable(value):
    field = next(iter(value.__dataclass_fields__))

    with pytest.raises(FrozenInstanceError):
        setattr(value, field, 999)


def test_pool_and_acquire_arguments_are_validated():
    with pytest.raises(ValueError, match="capacity"):
        HostResourceLeasePool(_request(), POLICY, lambda: HEALTHY)
    with pytest.raises(ValueError, match="headroom_policy"):
        HostResourceLeasePool(_capacity(), object(), lambda: HEALTHY)
    with pytest.raises(ValueError, match="health_probe"):
        HostResourceLeasePool(_capacity(), POLICY, None)

    pool = _pool()
    with pytest.raises(ValueError, match="key"):
        pool.acquire(" ", _request(), timeout_seconds=0)
    with pytest.raises(ValueError, match="request"):
        pool.acquire("bad-request", _capacity(), timeout_seconds=0)
    for invalid_timeout in (-0.1, True, math.inf, math.nan):
        with pytest.raises(ValueError, match="timeout_seconds"):
            pool.acquire("bad-timeout", _request(), timeout_seconds=invalid_timeout)


def test_acquire_immediately_reserves_all_five_dimensions_when_they_fit():
    pool = _pool(_capacity(4))
    first = pool.acquire("first", _request(2), timeout_seconds=0)
    second = pool.acquire("second", _request(2), timeout_seconds=0)

    with pytest.raises(ResourceLeaseTimeout):
        pool.acquire("full", _request(), timeout_seconds=0)

    first.release()
    second.release()


@pytest.mark.parametrize(
    "exhausted_field",
    ["cpu_count", "memory_mb", "pids_limit", "tmpfs_mb", "sandboxes"],
)
def test_each_exhausted_dimension_blocks_admission(exhausted_field):
    pool = _pool(_capacity(2))
    holder = pool.acquire(
        "holder",
        _request(**{exhausted_field: 2}),
        timeout_seconds=0,
    )

    with pytest.raises(ResourceLeaseTimeout):
        pool.acquire("blocked", _request(), timeout_seconds=0)

    holder.release()


def test_fifo_head_request_is_not_bypassed_by_a_smaller_request():
    large_waiter_is_head = threading.Event()
    large_acquired = threading.Event()
    release_large = threading.Event()
    failures: list[BaseException] = []

    def probe() -> HostHealthSnapshot:
        if threading.current_thread().name == "large-waiter":
            large_waiter_is_head.set()
        return HEALTHY

    pool = _pool(_capacity(2), probe=probe)
    holder = pool.acquire("holder", _request(), timeout_seconds=0)

    def acquire_large() -> None:
        try:
            with pool.acquire("large", _request(2), timeout_seconds=1):
                large_acquired.set()
                if not release_large.wait(1):
                    raise AssertionError("large waiter was not released by the test")
        except BaseException as exc:  # recorded and asserted in the main thread
            failures.append(exc)

    thread = threading.Thread(target=acquire_large, name="large-waiter")
    thread.start()
    assert large_waiter_is_head.wait(1)

    with pytest.raises(ResourceLeaseTimeout):
        pool.acquire("small", _request(), timeout_seconds=0)

    holder.release()
    assert large_acquired.wait(1)
    release_large.set()
    thread.join(1)
    assert not thread.is_alive()
    assert failures == []


def test_combined_requests_overlap_only_when_exact_accounting_allows_it():
    capacity = ResourceCapacity(8, 32_000, 2_000, 8_000, 4)
    pool = _pool(capacity)
    worker = ResourceRequest(4, 16_000, 1_000, 4_000, 2)
    verifier = ResourceRequest(2, 8_000, 500, 2_000, 1)

    worker_lease = pool.acquire("worker", worker, timeout_seconds=0)
    verifier_lease = pool.acquire("verifier", verifier, timeout_seconds=0)
    final_lease = pool.acquire("final", verifier, timeout_seconds=0)
    with pytest.raises(ResourceLeaseTimeout):
        pool.acquire("one-too-many", _request(), timeout_seconds=0)

    final_lease.release()
    verifier_lease.release()
    worker_lease.release()


def test_duplicate_live_lease_key_is_rejected_without_changing_accounting():
    pool = _pool(_capacity(1))
    first = pool.acquire("same-key", _request(), timeout_seconds=0)

    with pytest.raises(ResourceLeaseError, match="duplicate live lease key"):
        pool.acquire("same-key", _request(), timeout_seconds=0)

    first.release()
    replacement = pool.acquire("same-key", _request(), timeout_seconds=0)
    replacement.release()


@pytest.mark.parametrize(
    "oversized_field",
    ["cpu_count", "memory_mb", "pids_limit", "tmpfs_mb", "sandboxes"],
)
def test_each_oversized_dimension_is_rejected_instead_of_queued(oversized_field):
    probe_called = threading.Event()
    finished = threading.Event()
    failures: list[BaseException] = []
    pool = _pool(_capacity(1), probe=lambda: probe_called.set() or HEALTHY)

    def acquire_oversized() -> None:
        try:
            pool.acquire(
                "oversized",
                _request(**{oversized_field: 2}),
                timeout_seconds=60,
            )
        except BaseException as exc:  # recorded and asserted in the main thread
            failures.append(exc)
        finally:
            finished.set()

    thread = threading.Thread(target=acquire_oversized, daemon=True)
    thread.start()
    assert finished.wait(1)
    thread.join(1)
    assert len(failures) == 1
    assert isinstance(failures[0], ResourceLeaseError)
    assert "exceeds capacity" in str(failures[0])
    assert not probe_called.is_set()


@pytest.mark.parametrize(
    ("unhealthy", "reason"),
    [
        (HostHealthSnapshot(8.1, 16_000, 80_000, 1_000_000), "load_1m"),
        (HostHealthSnapshot(1.5, 7_999, 80_000, 1_000_000), "available_memory_mb"),
        (HostHealthSnapshot(1.5, 16_000, 39_999, 1_000_000), "free_disk_mb"),
        (HostHealthSnapshot(1.5, 16_000, 80_000, 499_999), "free_inodes"),
    ],
)
def test_each_host_headroom_failure_stops_admission_without_reserving(unhealthy, reason):
    current = [unhealthy]
    pool = _pool(_capacity(1), probe=lambda: current[0])

    with pytest.raises(ResourceLeaseTimeout, match=reason):
        pool.acquire("unhealthy", _request(), timeout_seconds=0)

    current[0] = HEALTHY
    lease = pool.acquire("healthy", _request(), timeout_seconds=0)
    lease.release()


def test_headroom_threshold_values_are_admitted():
    at_threshold = HostHealthSnapshot(8.0, 8_000, 40_000, 500_000)
    pool = _pool(_capacity(1), probe=lambda: at_threshold)

    lease = pool.acquire("threshold", _request(), timeout_seconds=0)
    lease.release()


def test_timeout_reports_requested_and_currently_available_capacity():
    capacity = ResourceCapacity(4, 800, 80, 160, 3)
    pool = _pool(capacity)
    holder = pool.acquire(
        "holder",
        ResourceRequest(3, 600, 60, 120, 2),
        timeout_seconds=0,
    )

    requested = ResourceRequest(2, 300, 30, 60, 2)
    with pytest.raises(ResourceLeaseTimeout) as raised:
        pool.acquire("blocked", requested, timeout_seconds=0)

    message = str(raised.value)
    assert (
        "requested=ResourceRequest(cpu_count=2, memory_mb=300, pids_limit=30, "
        "tmpfs_mb=60, sandboxes=2)" in message
    )
    assert (
        "available=ResourceCapacity(cpu_count=1, memory_mb=200, pids_limit=20, "
        "tmpfs_mb=40, sandboxes=1)" in message
    )
    holder.release()


def test_expired_monotonic_deadline_cannot_admit_after_health_probe(monkeypatch):
    now = [100.0]
    first_probe = [True]

    def probe() -> HostHealthSnapshot:
        if first_probe[0]:
            first_probe[0] = False
            now[0] = 101.1
        return HEALTHY

    monkeypatch.setattr(resource_lease.time, "monotonic", lambda: now[0])
    pool = _pool(_capacity(1), probe=probe)

    with pytest.raises(ResourceLeaseTimeout):
        pool.acquire("expired", _request(), timeout_seconds=1.0)

    replacement = pool.acquire("replacement", _request(), timeout_seconds=0)
    replacement.release()


def test_release_is_idempotent_without_overcrediting_capacity():
    pool = _pool(_capacity(1))
    first = pool.acquire("first", _request(), timeout_seconds=0)
    first.release()
    first.release()

    second = pool.acquire("second", _request(), timeout_seconds=0)
    with pytest.raises(ResourceLeaseTimeout):
        pool.acquire("third", _request(), timeout_seconds=0)
    second.release()


def test_context_manager_returns_lease_and_releases_after_exception_once():
    pool = _pool(_capacity(1))
    lease = pool.acquire("exception", _request(), timeout_seconds=0)

    with pytest.raises(RuntimeError, match="worker failed"):
        with lease as entered:
            assert entered is lease
            lease.release()
            raise RuntimeError("worker failed")

    replacement = pool.acquire("replacement", _request(), timeout_seconds=0)
    with pytest.raises(ResourceLeaseTimeout):
        pool.acquire("overcredited", _request(), timeout_seconds=0)
    replacement.release()
