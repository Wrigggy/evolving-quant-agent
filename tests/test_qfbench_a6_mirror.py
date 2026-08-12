from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
R3_ROOT = REPO / "output/qfbench-supervisor/a6-ad26fe36d9539273-r3"
R4_ROOT = REPO / "output/qfbench-supervisor/a6-1a83fc76757b73bf-r4"
R5_ROOT = REPO / "output/qfbench-supervisor/a6-881ee7f14a1b2c46-r5"
R6_ROOT = REPO / "output/qfbench-supervisor/a6-4d5fd85f47525255-r6"
R7_ROOT = REPO / "output/qfbench-supervisor/a6-7a57e32dcfa60aea-r7"
R8_ROOT = REPO / "output/qfbench-supervisor/a6-7704a05305551d96-r8"
R3_SCRIPT = R3_ROOT / "qea-qfbench-a6-r3-result-sync.sh"
R4_SCRIPT = R4_ROOT / "qea-qfbench-a6-r4-result-sync.sh"
R5_SCRIPT = R5_ROOT / "qea-qfbench-a6-r5-result-sync.sh"
R6_SCRIPT = R6_ROOT / "qea-qfbench-a6-r6-result-sync.sh"
R7_SCRIPT = R7_ROOT / "qea-qfbench-a6-r7-result-sync.sh"
R8_SCRIPT = R8_ROOT / "qea-qfbench-a6-r8-result-sync.sh"


def _write_executable(path: Path, payload: str) -> None:
    path.write_text(payload, encoding="utf-8")
    path.chmod(0o700)


def _testable_script(
    tmp_path: Path, *, run_ids: list[str], source_script: Path = R3_SCRIPT
) -> tuple[Path, Path, Path, Path]:
    runs = tmp_path / "runs.txt"
    runs.write_text("\n".join(run_ids) + "\n", encoding="utf-8")
    destination = tmp_path / "mirror"
    ssh_log = tmp_path / "ssh.log"
    rsync_log = tmp_path / "rsync.log"
    fake_ssh = tmp_path / "ssh"
    fake_rsync = tmp_path / "rsync"
    _write_executable(
        fake_ssh,
        """#!/bin/sh
/usr/bin/cat >/dev/null
printf '%s\\n' "$*" >> "$QEA_TEST_SSH_LOG"
case "$*" in
  *missing-run*) exit 1 ;;
  *ssh-error*) exit 42 ;;
esac
exit 0
""",
    )
    _write_executable(
        fake_rsync,
        """#!/bin/sh
/usr/bin/cat >/dev/null
for argument in "$@"; do
  case "$argument" in
    bc:/home/julius/qea/runs/*/)
      run_id=${argument#bc:/home/julius/qea/runs/}
      run_id=${run_id%/}
      printf '%s\\n' "$run_id" >> "$QEA_TEST_RSYNC_LOG"
      ;;
  esac
done
exit 0
""",
    )
    payload = source_script.read_text(encoding="utf-8")
    payload = re.sub(
        r'^runs_file="[^"]+/qfbench-result-sync-runs\.txt"$',
        f'runs_file="{runs}"',
        payload,
        count=1,
        flags=re.MULTILINE,
    )
    payload = payload.replace(
        'destination_root="/Users/kevinwu/Coding/evolving-quant-agent/'
        'results/bc-mirror"',
        f'destination_root="{destination}"',
    )
    payload = payload.replace("/usr/bin/ssh", str(fake_ssh))
    payload = payload.replace("/usr/bin/rsync", str(fake_rsync))
    executable = tmp_path / "mirror.sh"
    _write_executable(executable, payload)
    return executable, destination, ssh_log, rsync_log


def _run(
    executable: Path, *, ssh_log: Path, rsync_log: Path
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.update(
        QEA_TEST_SSH_LOG=str(ssh_log),
        QEA_TEST_RSYNC_LOG=str(rsync_log),
    )
    return subprocess.run(
        ["/bin/sh", str(executable)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=10,
    )


@pytest.mark.parametrize(
    ("root", "source_script"),
    (
        (R3_ROOT, R3_SCRIPT),
        (R4_ROOT, R4_SCRIPT),
        (R5_ROOT, R5_SCRIPT),
        (R6_ROOT, R6_SCRIPT),
        (R7_ROOT, R7_SCRIPT),
        (R8_ROOT, R8_SCRIPT),
    ),
)
def test_mirror_visits_every_registered_id_when_children_consume_stdin(
    tmp_path: Path, root: Path, source_script: Path,
) -> None:
    run_ids = [
        line
        for line in (root / "qfbench-result-sync-runs.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line and not line.startswith("#")
    ]
    executable, destination, ssh_log, rsync_log = _testable_script(
        tmp_path, run_ids=run_ids, source_script=source_script
    )

    completed = _run(executable, ssh_log=ssh_log, rsync_log=rsync_log)

    assert completed.returncode == 0, completed.stderr
    visited = [
        re.search(r"/runs/([^ ]+)", line).group(1)
        for line in ssh_log.read_text(encoding="utf-8").splitlines()
    ]
    assert visited == run_ids
    mirrored = rsync_log.read_text(encoding="utf-8").splitlines()
    assert mirrored == run_ids
    assert all((destination / item).is_dir() for item in run_ids)
    assert all((destination / item).stat().st_mode & 0o777 == 0o700 for item in run_ids)


def test_mirror_skips_one_missing_id_and_continues(tmp_path: Path) -> None:
    run_ids = ["exact-run-before", "missing-run", "exact-run-after"]
    executable, _, ssh_log, rsync_log = _testable_script(
        tmp_path, run_ids=run_ids
    )

    completed = _run(executable, ssh_log=ssh_log, rsync_log=rsync_log)

    assert completed.returncode == 0, completed.stderr
    visited = [
        re.search(r"/runs/([^ ]+)", line).group(1)
        for line in ssh_log.read_text(encoding="utf-8").splitlines()
    ]
    assert visited == run_ids
    assert rsync_log.read_text(encoding="utf-8").splitlines() == [
        "exact-run-before",
        "exact-run-after",
    ]
    assert "sync-skip run=missing-run status=not-available" in completed.stdout


def test_mirror_fails_closed_on_ssh_error_without_visiting_later_ids(
    tmp_path: Path,
) -> None:
    run_ids = ["exact-run-first", "ssh-error", "exact-run-never"]
    executable, _, ssh_log, rsync_log = _testable_script(
        tmp_path, run_ids=run_ids
    )

    completed = _run(executable, ssh_log=ssh_log, rsync_log=rsync_log)

    assert completed.returncode == 42
    assert "sync-failed run=ssh-error status=ssh-error exit=42" in completed.stderr
    visited = ssh_log.read_text(encoding="utf-8")
    assert "exact-run-first" in visited
    assert "ssh-error" in visited
    assert "exact-run-never" not in visited
    assert rsync_log.read_text(encoding="utf-8").splitlines() == [
        "exact-run-first"
    ]


@pytest.mark.parametrize(
    "source_script",
    (R3_SCRIPT, R4_SCRIPT, R5_SCRIPT, R6_SCRIPT, R7_SCRIPT, R8_SCRIPT),
)
def test_mirror_preserves_additive_security_and_mode_contract(
    source_script: Path,
) -> None:
    payload = source_script.read_text(encoding="utf-8")

    assert "exec 3< \"${runs_file}\"" in payload
    assert "read -r run_id <&3" in payload
    assert payload.count("3<&-") >= 3
    assert re.search(r"/usr/bin/ssh \\\n\s+-n \\", payload)
    assert "3<&- </dev/null" in payload
    assert "--delete" not in payload
    for exclusion in (
        "worker-input.tar",
        "verifier-input.tar",
        "input.tar",
        ".e2b-leases",
        ".env",
        "*credential*",
        "*token*",
        "*criteria*",
        "trusted-verifier/***",
        "trusted/***",
    ):
        assert f"--exclude={exclusion}" in payload or f"--exclude='{exclusion}'" in payload
    assert "--chmod=Du=rwx,Dgo=,Fu=rw,Fgo=" in payload
    assert "umask 077" in payload
    assert '/bin/mkdir -p -m 700 "${destination}"' in payload
    assert '/bin/chmod 700 "${destination}"' in payload


def test_r3_registry_is_additive_unique_and_exact_ids_are_fresh() -> None:
    registry = [
        line
        for line in (R3_ROOT / "qfbench-result-sync-runs.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line and not line.startswith("#")
    ]
    exact = (R3_ROOT / "r3-exact-run-ids.txt").read_text(encoding="utf-8").splitlines()

    assert len(registry) == 28
    assert len(registry) == len(set(registry))
    assert len(exact) == 7
    assert all(item.endswith("-20260809-r3") for item in exact)
    assert registry[-7:] == exact
    assert "qfbench-a6-seed-evidence-flash-20260809-r2" in registry


def test_r4_registry_is_additive_unique_and_exact_ids_are_fresh() -> None:
    registry = [
        line
        for line in (R4_ROOT / "qfbench-result-sync-runs.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line and not line.startswith("#")
    ]
    exact = (R4_ROOT / "r4-exact-run-ids.txt").read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(registry) == 35
    assert len(registry) == len(set(registry))
    assert len(exact) == 7
    assert all(item.endswith("-20260810-r4") for item in exact)
    assert registry[-7:] == exact
    assert "qfbench-a6-seed-evidence-flash-20260809-r3" in registry


def test_r5_registry_is_additive_unique_and_exact_ids_are_fresh() -> None:
    registry = [
        line
        for line in (R5_ROOT / "qfbench-result-sync-runs.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line and not line.startswith("#")
    ]
    exact = (R5_ROOT / "r5-exact-run-ids.txt").read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(registry) == 42
    assert len(registry) == len(set(registry))
    assert len(exact) == 7
    assert all(item.endswith("-20260810-r5") for item in exact)
    assert registry[-7:] == exact
    assert "qfbench-a6-seed-evidence-flash-20260810-r4" in registry


def test_r6_registry_is_additive_unique_and_exact_ids_are_fresh() -> None:
    registry = [
        line
        for line in (R6_ROOT / "qfbench-result-sync-runs.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line and not line.startswith("#")
    ]
    exact = (R6_ROOT / "r6-exact-run-ids.txt").read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(registry) == 49
    assert len(registry) == len(set(registry))
    assert len(exact) == 7
    assert all(item.endswith("-20260810-r6") for item in exact)
    assert registry[-7:] == exact
    assert "qfbench-a6-seed-evidence-flash-20260810-r5" in registry


def test_r7_registry_is_additive_unique_and_exact_ids_are_fresh() -> None:
    registry = [
        line
        for line in (R7_ROOT / "qfbench-result-sync-runs.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line and not line.startswith("#")
    ]
    exact = (R7_ROOT / "r7-exact-run-ids.txt").read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(registry) == 56
    assert len(registry) == len(set(registry))
    assert len(exact) == 7
    assert all(item.endswith("-20260810-r7") for item in exact)
    assert registry[-7:] == exact
    assert "qfbench-a6-seed-evidence-flash-20260810-r6" in registry


def test_r8_registry_is_additive_unique_and_exact_ids_are_fresh() -> None:
    registry = [
        line
        for line in (R8_ROOT / "qfbench-result-sync-runs.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line and not line.startswith("#")
    ]
    exact = (R8_ROOT / "r8-exact-run-ids.txt").read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(registry) == 63
    assert len(registry) == len(set(registry))
    assert len(exact) == 7
    assert all(item.endswith("-20260810-r8") for item in exact)
    assert registry[-7:] == exact
    assert "qfbench-a6-seed-evidence-flash-20260810-r7" in registry


def test_r5_mirror_excludes_materialized_private_input_tree() -> None:
    payload = R5_SCRIPT.read_text(encoding="utf-8")

    assert "--exclude='inputs/***'" in payload


def test_r6_mirror_excludes_materialized_private_input_tree() -> None:
    payload = R6_SCRIPT.read_text(encoding="utf-8")

    assert "--exclude='inputs/***'" in payload


def test_r7_mirror_excludes_materialized_private_input_tree() -> None:
    payload = R7_SCRIPT.read_text(encoding="utf-8")

    assert "--exclude='inputs/***'" in payload


def test_r8_mirror_excludes_materialized_private_input_tree() -> None:
    payload = R8_SCRIPT.read_text(encoding="utf-8")

    assert "--exclude='inputs/***'" in payload
