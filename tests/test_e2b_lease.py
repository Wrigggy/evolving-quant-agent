import json

import pytest


def test_global_lease_enforces_cap_and_release(tmp_path):
    from qea.e2b_lease import E2BLeaseError, E2BLeasePool

    pool = E2BLeasePool(tmp_path / "leases", max_leases=1, stale_after_seconds=60)
    first = pool.acquire("attempt-a", timeout_seconds=0)
    assert first.path.is_file()

    with pytest.raises(E2BLeaseError, match="capacity"):
        pool.acquire("attempt-b", timeout_seconds=0)

    first.release()
    second = pool.acquire("attempt-b", timeout_seconds=0)
    assert second.path.is_file()
    second.release()


def test_global_lease_reaps_stale_heartbeat(tmp_path):
    from qea.e2b_lease import E2BLeasePool

    lease_root = tmp_path / "leases"
    lease_root.mkdir()
    stale = lease_root / "stale.json"
    stale.write_text(json.dumps({
        "token": "stale",
        "owner": "dead-attempt",
        "created_at": 1.0,
        "heartbeat_at": 1.0,
    }))

    pool = E2BLeasePool(
        lease_root,
        max_leases=1,
        stale_after_seconds=10,
        wall_clock=lambda: 100.0,
    )
    current = pool.acquire("live-attempt", timeout_seconds=0)

    assert not stale.exists()
    payload = json.loads(current.path.read_text())
    assert payload["owner"] == "live-attempt"
    current.heartbeat()
    assert json.loads(current.path.read_text())["heartbeat_at"] == 100.0
    current.release()
