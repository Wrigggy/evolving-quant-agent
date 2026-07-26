"""Cross-process lease pool shared by all E2B roles in one coordinator host."""

from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator


class E2BLeaseError(RuntimeError):
    """The global E2B lease pool could not grant or maintain a lease."""


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


@dataclass
class E2BLease:
    pool: "E2BLeasePool"
    token: str
    owner: str
    path: Path
    _released: bool = field(default=False, init=False, repr=False)

    def heartbeat(self) -> None:
        if self._released:
            raise E2BLeaseError("cannot heartbeat a released lease")
        self.pool._heartbeat(self)

    def release(self) -> None:
        if self._released:
            return
        self.pool._release(self)
        self._released = True

    def __enter__(self) -> "E2BLease":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()


class E2BLeasePool:
    """A small file-locked semaphore with heartbeats and stale-lease reaping."""

    def __init__(
        self,
        root: str | Path,
        *,
        max_leases: int = 12,
        stale_after_seconds: float = 7_200,
        wall_clock: Callable[[], float] = time.time,
        monotonic_clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_leases < 1:
            raise E2BLeaseError("max_leases must be at least one")
        if stale_after_seconds <= 0:
            raise E2BLeaseError("stale_after_seconds must be positive")
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_leases = max_leases
        self.stale_after_seconds = stale_after_seconds
        self._wall_clock = wall_clock
        self._monotonic_clock = monotonic_clock
        self._sleep = sleep
        self._lock_path = self.root / ".lock"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with self._lock_path.open("a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _active_paths(self) -> list[Path]:
        return sorted(self.root.glob("*.json"))

    def _reap_stale_locked(self, now: float) -> None:
        for path in self._active_paths():
            try:
                payload = json.loads(path.read_text())
                heartbeat = float(payload["heartbeat_at"])
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                path.unlink(missing_ok=True)
                continue
            if now - heartbeat > self.stale_after_seconds:
                path.unlink(missing_ok=True)

    def acquire(
        self,
        owner: str,
        *,
        timeout_seconds: float = 60,
        poll_seconds: float = 0.1,
    ) -> E2BLease:
        if not owner.strip():
            raise E2BLeaseError("lease owner must be non-empty")
        if timeout_seconds < 0:
            raise E2BLeaseError("timeout_seconds must be non-negative")
        deadline = self._monotonic_clock() + timeout_seconds
        while True:
            with self._locked():
                now = self._wall_clock()
                self._reap_stale_locked(now)
                if len(self._active_paths()) < self.max_leases:
                    token = uuid.uuid4().hex
                    path = self.root / f"{token}.json"
                    _atomic_json(path, {
                        "token": token,
                        "owner": owner,
                        "created_at": now,
                        "heartbeat_at": now,
                    })
                    return E2BLease(self, token, owner, path)
            if timeout_seconds == 0 or self._monotonic_clock() >= deadline:
                raise E2BLeaseError(
                    f"E2B lease capacity {self.max_leases} unavailable for {owner}"
                )
            self._sleep(min(poll_seconds, max(0.0, deadline - self._monotonic_clock())))

    def _heartbeat(self, lease: E2BLease) -> None:
        with self._locked():
            if not lease.path.is_file():
                raise E2BLeaseError(f"lease {lease.token} no longer exists")
            payload = json.loads(lease.path.read_text())
            if payload.get("token") != lease.token or payload.get("owner") != lease.owner:
                raise E2BLeaseError(f"lease {lease.token} ownership changed")
            payload["heartbeat_at"] = self._wall_clock()
            _atomic_json(lease.path, payload)

    def _release(self, lease: E2BLease) -> None:
        with self._locked():
            if not lease.path.exists():
                return
            try:
                payload = json.loads(lease.path.read_text())
            except (OSError, json.JSONDecodeError):
                payload = {}
            if payload.get("token") not in {None, lease.token}:
                raise E2BLeaseError(f"refusing to release foreign lease {lease.path}")
            lease.path.unlink(missing_ok=True)
