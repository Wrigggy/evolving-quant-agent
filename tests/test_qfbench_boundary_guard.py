import hashlib
import json
import os
import signal
from dataclasses import replace

import pytest


def _epochs():
    from qea.qfbench_scheduler_epochs import SchedulerEpoch

    return (
        SchedulerEpoch(1, 1, 4, 3, "5" * 64, "4" * 64),
        SchedulerEpoch(2, 5, 12, 3, "6" * 64, "7" * 64),
    )


def _write_boundary(run_dir):
    run_dir.mkdir(parents=True)
    (run_dir / "resume.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "formal-run",
                "benchmark_commit": "0" * 40,
                "total_repetitions": 5,
                "identity": {
                    "model_identity": "model",
                    "task_manifest_digest": "1" * 64,
                    "runtime_identity_digest": "4" * 64,
                    "scheduler_identity_digest": "5" * 64,
                    "template_identity_digest": "2" * 64,
                    "worker_concurrency": 4,
                    "verifier_concurrency": 3,
                    "seed_worker_digest": "3" * 64,
                    "primary_tasks": [],
                    "diagnostic_tasks": [],
                },
                "phase": "primary",
                "next_repetition": 2,
                "pending_primary": None,
                "completed": [
                    {"repetition": 1, "primary": {}, "diagnostic": {}}
                ],
            }
        )
    )


def _write_proc(proc_root, *, state="S", uid=None, pgid=456, start=789):
    pid = 123
    root = proc_root / str(pid)
    root.mkdir(parents=True, exist_ok=True)
    tail = [state, "1", str(pgid)] + ["0"] * 16 + [str(start)] + ["0"] * 5
    (root / "stat").write_text(f"{pid} (python worker) " + " ".join(tail))
    (root / "status").write_text(f"Name:\tpython\nUid:\t{os.getuid() if uid is None else uid}\t0\t0\t0\n")
    argv = (
        b"python\x00run.py\x00--run-id\x00formal-run\x00"
        + b"--source-commit\x00"
        + b"0" * 40
        + b"\x00"
    )
    (root / "cmdline").write_bytes(argv)
    return pid, argv


def _config(run_dir, process):
    from qea.qfbench_boundary import BoundaryGuardConfig

    return BoundaryGuardConfig(
        run_id="formal-run",
        source_commit="0" * 40,
        run_dir=run_dir,
        expected_uid=os.getuid(),
        command_token="run.py",
        process=process,
        scheduler_epochs=_epochs(),
        expected_scores=0,
        wait_timeout_seconds=1,
    )


def test_proc_identity_validates_command_run_commit_uid_pgid_and_start_ticks(
    tmp_path,
):
    from qea.qfbench_boundary import (
        BoundaryError,
        ProcessIdentity,
        read_process_snapshot,
        validate_process_snapshot,
    )

    proc_root = tmp_path / "proc"
    pid, argv = _write_proc(proc_root)
    expected = ProcessIdentity(
        pid=pid,
        process_group_id=456,
        uid=os.getuid(),
        start_ticks=789,
        command_sha256=hashlib.sha256(argv).hexdigest(),
    )
    snapshot = read_process_snapshot(pid, proc_root=proc_root)
    assert snapshot.identity == expected
    assert snapshot.state == "S"
    validate_process_snapshot(
        snapshot,
        expected=expected,
        command_token="run.py",
        run_id="formal-run",
        source_commit="0" * 40,
        expected_uid=os.getuid(),
    )

    variants = (
        (replace(expected, process_group_id=999), "process group"),
        (replace(expected, uid=expected.uid + 1), "UID"),
        (replace(expected, start_ticks=790), "start ticks"),
        (replace(expected, command_sha256="a" * 64), "command"),
    )
    for changed, message in variants:
        with pytest.raises(BoundaryError, match=message):
            validate_process_snapshot(
                snapshot,
                expected=changed,
                command_token="run.py",
                run_id="formal-run",
                source_commit="0" * 40,
                expected_uid=os.getuid(),
            )

    with pytest.raises(BoundaryError, match="token"):
        validate_process_snapshot(
            snapshot,
            expected=expected,
            command_token="other.py",
            run_id="formal-run",
            source_commit="0" * 40,
            expected_uid=os.getuid(),
        )
    for changed, message in (
        ({"run_id": "other-run"}, "run ID"),
        ({"source_commit": "f" * 40}, "source commit"),
        ({"expected_uid": os.getuid() + 1}, "guard UID"),
    ):
        values = {
            "expected": expected,
            "command_token": "run.py",
            "run_id": "formal-run",
            "source_commit": "0" * 40,
            "expected_uid": os.getuid(),
            **changed,
        }
        with pytest.raises(BoundaryError, match=message):
            validate_process_snapshot(snapshot, **values)


def _inventory(*, clean=True):
    from qea.qfbench_boundary import BoundaryInventory

    return BoundaryInventory(
        clean=clean,
        repetition_one_score_count=0,
        repetition_two_evidence=() if clean else ("attempts/rep2",),
        active_resource_ids=(),
        evidence_sha256="a" * 64,
        evidence_manifest=(),
    )


def _guard_fixture(tmp_path, *, initial_state="S"):
    from qea.qfbench_boundary import ProcessIdentity, ProcessSnapshot

    run_dir = tmp_path / "formal-run"
    _write_boundary(run_dir)
    argv = (
        "python",
        "run.py",
        "--run-id",
        "formal-run",
        "--source-commit",
        "0" * 40,
    )
    command = "\x00".join(argv).encode() + b"\x00"
    identity = ProcessIdentity(
        pid=123,
        process_group_id=456,
        uid=os.getuid(),
        start_ticks=789,
        command_sha256=hashlib.sha256(command).hexdigest(),
    )
    return run_dir, _config(run_dir, identity), ProcessSnapshot(
        identity=identity,
        state=initial_state,
        argv=argv,
    )


def test_clean_guard_stops_then_kills_exact_group_and_migrates(tmp_path):
    from qea.qfbench_boundary import run_boundary_guard

    run_dir, config, running = _guard_fixture(tmp_path)
    stopped = replace(running, state="T")
    alive = [running]
    signals = []

    def send_group(pgid, requested_signal):
        assert pgid == 456
        signals.append(requested_signal)
        if requested_signal == signal.SIGSTOP:
            alive[0] = stopped
        elif requested_signal == signal.SIGKILL:
            alive.clear()

    def read_process(pid):
        if not alive:
            raise ProcessLookupError(pid)
        return alive[0]

    result = run_boundary_guard(
        config,
        boundary_waiter=lambda current: None,
        process_reader=read_process,
        signal_group=send_group,
        inventory_reader=lambda current: _inventory(),
        sleep=lambda seconds: None,
    )

    assert result.status == "migrated"
    assert signals == [signal.SIGSTOP, signal.SIGKILL]
    assert json.loads((run_dir / "resume.json").read_text())["schema_version"] == 2
    assert (run_dir / "boundary-manifest.json").is_file()


def test_post_stop_rep2_evidence_leaves_group_stopped_and_records_hard_stop(
    tmp_path,
):
    from qea.qfbench_boundary import run_boundary_guard

    run_dir, config, running = _guard_fixture(tmp_path)
    stopped = replace(running, state="T")
    current = [running]
    signals = []

    def send_group(pgid, requested_signal):
        signals.append(requested_signal)
        current[0] = stopped

    result = run_boundary_guard(
        config,
        boundary_waiter=lambda current: None,
        process_reader=lambda pid: current[0],
        signal_group=send_group,
        inventory_reader=lambda current: _inventory(clean=False),
        sleep=lambda seconds: None,
    )

    assert result.status == "hard_stop"
    assert signals == [signal.SIGSTOP]
    assert json.loads((run_dir / "resume.json").read_text())["schema_version"] == 1
    assert (run_dir / "boundary-hard-stop.json").is_file()


def test_already_stopped_process_is_not_stopped_twice(tmp_path):
    from qea.qfbench_boundary import run_boundary_guard

    _, config, stopped = _guard_fixture(tmp_path, initial_state="T")
    alive = [stopped]
    signals = []

    def send_group(pgid, requested_signal):
        signals.append(requested_signal)
        if requested_signal == signal.SIGKILL:
            alive.clear()

    result = run_boundary_guard(
        config,
        boundary_waiter=lambda current: None,
        process_reader=lambda pid: (
            alive[0] if alive else (_ for _ in ()).throw(ProcessLookupError(pid))
        ),
        signal_group=send_group,
        inventory_reader=lambda current: _inventory(),
        sleep=lambda seconds: None,
    )

    assert result.status == "migrated"
    assert signals == [signal.SIGKILL]


def test_duplicate_guard_claim_and_stale_pid_reuse_fail_closed(tmp_path):
    from qea.qfbench_boundary import BoundaryError, run_boundary_guard

    run_dir, config, running = _guard_fixture(tmp_path)
    (run_dir / "boundary-guard-claim.json").write_text("{}")
    with pytest.raises(BoundaryError, match="already claimed"):
        run_boundary_guard(
            config,
            boundary_waiter=lambda current: None,
            process_reader=lambda pid: running,
            inventory_reader=lambda current: _inventory(),
        )

    (run_dir / "boundary-guard-claim.json").unlink()
    stale = replace(
        running,
        identity=replace(running.identity, start_ticks=999),
        state="T",
    )
    snapshots = iter((running, running, stale))
    signals = []
    result = run_boundary_guard(
        config,
        boundary_waiter=lambda current: None,
        process_reader=lambda pid: next(snapshots),
        signal_group=lambda pgid, requested: signals.append(requested),
        inventory_reader=lambda current: _inventory(),
        sleep=lambda seconds: None,
    )
    assert result.status == "hard_stop"
    assert signals == [signal.SIGSTOP]
    assert (run_dir / "boundary-hard-stop.json").is_file()


def test_guard_config_loader_requires_owner_mode_600_regular_file(tmp_path):
    from qea.qfbench_boundary import (
        BoundaryError,
        ProcessIdentity,
        load_boundary_guard_config,
    )

    run_dir = tmp_path / "formal-run"
    run_dir.mkdir()
    process = ProcessIdentity(123, 456, os.getuid(), 789, "a" * 64)
    payload = {
        "schema_version": 1,
        "run_id": "formal-run",
        "source_commit": "0" * 40,
        "run_dir": str(run_dir),
        "expected_uid": os.getuid(),
        "command_token": "run.py",
        "process": process.to_dict(),
        "scheduler_epochs": [epoch.to_dict() for epoch in _epochs()],
        "expected_scores": 85,
        "wait_timeout_seconds": 60,
    }
    path = tmp_path / "guard.json"
    path.write_text(json.dumps(payload))
    path.chmod(0o600)
    assert load_boundary_guard_config(path).process == process

    path.chmod(0o644)
    with pytest.raises(BoundaryError, match="mode 600"):
        load_boundary_guard_config(path)

    target = tmp_path / "target.json"
    target.write_text(json.dumps(payload))
    target.chmod(0o600)
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(BoundaryError, match="symlink|regular"):
        load_boundary_guard_config(path)
