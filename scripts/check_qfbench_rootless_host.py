#!/usr/bin/env python3
"""Read-only readiness checks for the QFBench rootless Docker VM."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence


_TOP_KEYS = frozenset({"schema_version", "fixture_kind", "expected", "observations"})
_EXPECTED_KEYS = frozenset(
    {
        "docker_host",
        "expected_uid",
        "min_cpu_count",
        "min_docker_version",
        "min_free_bytes",
        "min_memory_bytes",
        "runtime_root",
        "secret_file",
        "source_commit",
        "source_root",
        "username",
    }
)
_OBSERVATION_KEYS = frozenset(
    {
        "cgroup_controllers",
        "cgroup_filesystem",
        "cpu_online",
        "docker_info",
        "docker_socket_stat",
        "docker_version",
        "filesystem_free",
        "filesystem_type",
        "fuse_overlayfs_path",
        "git_head",
        "git_status",
        "kernel_release",
        "linger",
        "max_user_namespaces",
        "meminfo",
        "newgidmap_path",
        "newgidmap_stat",
        "newuidmap_path",
        "newuidmap_stat",
        "runtime_stat",
        "secret_stat",
        "subgid",
        "subuid",
        "systemd_user",
        "uid",
        "username",
    }
)
_OBSERVATION_FIELDS = frozenset({"exit_code", "stdout", "stderr"})
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")


class HostCheckError(ValueError):
    """Host-check input is malformed or cannot be collected safely."""


def _observation(exit_code: int, stdout: str = "", stderr: str = "") -> dict[str, object]:
    return {
        "exit_code": int(exit_code),
        "stdout": str(stdout),
        "stderr": str(stderr),
    }


def _run(argv: Sequence[str], *, timeout: int = 30) -> dict[str, object]:
    try:
        result = subprocess.run(
            tuple(argv),
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _observation(127, stderr=f"{type(exc).__name__}: {exc}")
    return _observation(result.returncode, result.stdout, result.stderr)


def _read(path: Path) -> dict[str, object]:
    try:
        return _observation(0, path.read_text())
    except OSError as exc:
        return _observation(1, stderr=f"{type(exc).__name__}: {exc}")


def _which(name: str) -> dict[str, object]:
    path = shutil.which(name)
    return _observation(0, path + "\n") if path else _observation(1)


def _stat_record(path: Path) -> dict[str, object]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        return _observation(1, stderr=f"{type(exc).__name__}: {exc}")
    if stat.S_ISSOCK(metadata.st_mode):
        kind = "socket"
    elif stat.S_ISREG(metadata.st_mode):
        kind = "regular file"
    elif stat.S_ISDIR(metadata.st_mode):
        kind = "directory"
    else:
        kind = "other"
    return _observation(
        0,
        f"{stat.S_IMODE(metadata.st_mode):o}:{metadata.st_uid}:{kind}\n",
    )


def _matching_subids(path: Path, username: str, uid: int) -> dict[str, object]:
    observed = _read(path)
    if observed["exit_code"] != 0:
        return observed
    lines = [
        line
        for line in str(observed["stdout"]).splitlines()
        if line.split(":", 1)[0] in {username, str(uid)}
    ]
    return _observation(0, "\n".join(lines) + ("\n" if lines else ""))


def collect_live(expected: Mapping[str, object]) -> dict[str, object]:
    """Collect fixed, read-only observations on the current Linux host."""

    normalized = _validate_expected(expected)
    uid = normalized["expected_uid"]
    username = normalized["username"]
    source = Path(normalized["source_root"])
    runtime = Path(normalized["runtime_root"])
    secret = Path(normalized["secret_file"])
    socket_path = Path(f"/run/user/{uid}/docker.sock")
    docker_host = normalized["docker_host"]
    newuid = shutil.which("newuidmap")
    newgid = shutil.which("newgidmap")
    observations = {
        "uid": _run(("id", "-u")),
        "username": _run(("id", "-un")),
        "newuidmap_path": _which("newuidmap"),
        "newuidmap_stat": _stat_record(Path(newuid)) if newuid else _observation(1),
        "newgidmap_path": _which("newgidmap"),
        "newgidmap_stat": _stat_record(Path(newgid)) if newgid else _observation(1),
        "subuid": _matching_subids(Path("/etc/subuid"), username, uid),
        "subgid": _matching_subids(Path("/etc/subgid"), username, uid),
        "max_user_namespaces": _read(Path("/proc/sys/user/max_user_namespaces")),
        "cgroup_filesystem": _run(("stat", "-f", "-c", "%T", "/sys/fs/cgroup")),
        "cgroup_controllers": _read(Path("/sys/fs/cgroup/cgroup.controllers")),
        "systemd_user": _run(("systemctl", "--user", "is-system-running")),
        "linger": _run(("loginctl", "show-user", username, "-p", "Linger", "--value")),
        "docker_socket_stat": _stat_record(socket_path),
        "docker_version": _run(
            ("docker", "--host", docker_host, "version", "--format", "{{json .}}")
        ),
        "docker_info": _run(
            ("docker", "--host", docker_host, "info", "--format", "{{json .}}")
        ),
        "filesystem_free": _run(("df", "-Pk", str(runtime))),
        "filesystem_type": _run(("stat", "-f", "-c", "%T", str(runtime))),
        "kernel_release": _run(("uname", "-r")),
        "meminfo": _read(Path("/proc/meminfo")),
        "cpu_online": _run(("getconf", "_NPROCESSORS_ONLN")),
        "git_head": _run(("git", "-C", str(source), "rev-parse", "HEAD")),
        "git_status": _run(
            ("git", "-C", str(source), "status", "--porcelain", "--untracked-files=no")
        ),
        "runtime_stat": _stat_record(runtime),
        "secret_stat": _stat_record(secret),
        "fuse_overlayfs_path": _which("fuse-overlayfs"),
    }
    return {
        "schema_version": 1,
        "fixture_kind": "live-read-only",
        "expected": normalized,
        "observations": observations,
    }


def _validate_expected(raw: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(raw, Mapping) or set(raw) != _EXPECTED_KEYS:
        raise HostCheckError("expected host contract has missing or unknown fields")
    values = dict(raw)
    integer_fields = (
        "expected_uid",
        "min_cpu_count",
        "min_free_bytes",
        "min_memory_bytes",
    )
    if any(type(values[name]) is not int or values[name] <= 0 for name in integer_fields):
        raise HostCheckError("host numeric requirements must be positive integers")
    for name in _EXPECTED_KEYS - set(integer_fields):
        if not isinstance(values[name], str) or not values[name]:
            raise HostCheckError(f"expected {name} must be a non-empty string")
    uid = values["expected_uid"]
    if uid == 0 or values["docker_host"] != f"unix:///run/user/{uid}/docker.sock":
        raise HostCheckError("Docker host must be the exact non-root user socket")
    if _COMMIT.fullmatch(values["source_commit"]) is None:
        raise HostCheckError("source_commit must be a full lowercase SHA")
    for name in ("source_root", "runtime_root", "secret_file"):
        if not Path(values[name]).is_absolute():
            raise HostCheckError(f"expected {name} must be absolute")
    return values


def _validate_fixture(payload: object) -> tuple[dict[str, object], dict[str, dict[str, object]], str]:
    if not isinstance(payload, dict) or set(payload) != _TOP_KEYS:
        raise HostCheckError("host fixture has missing or unknown top-level fields")
    if payload.get("schema_version") != 1:
        raise HostCheckError("unsupported host fixture schema")
    kind = payload.get("fixture_kind")
    if not isinstance(kind, str) or not kind:
        raise HostCheckError("fixture_kind must be a non-empty string")
    expected = _validate_expected(payload.get("expected"))
    raw = payload.get("observations")
    if not isinstance(raw, dict) or set(raw) != _OBSERVATION_KEYS:
        raise HostCheckError("host observations have missing or unknown fields")
    observations: dict[str, dict[str, object]] = {}
    for name, value in raw.items():
        if not isinstance(value, dict) or set(value) != _OBSERVATION_FIELDS:
            raise HostCheckError(f"malformed observation {name}")
        if type(value["exit_code"]) is not int:
            raise HostCheckError(f"observation {name} exit_code is not an integer")
        if not isinstance(value["stdout"], str) or not isinstance(value["stderr"], str):
            raise HostCheckError(f"observation {name} output is not text")
        observations[name] = dict(value)
    return expected, observations, kind


def _text(observations: Mapping[str, Mapping[str, object]], name: str) -> str:
    item = observations[name]
    return str(item["stdout"]).strip() if item["exit_code"] == 0 else ""


def _integer(value: str) -> int | None:
    try:
        result = int(value.strip())
    except (TypeError, ValueError):
        return None
    return result


def _subid_size(value: str, username: str, uid: int) -> int:
    total = 0
    for line in value.splitlines():
        fields = line.split(":")
        if len(fields) != 3 or fields[0] not in {username, str(uid)}:
            continue
        try:
            start, size = int(fields[1]), int(fields[2])
        except ValueError:
            return 0
        if start <= 0 or size <= 0:
            return 0
        total += size
    return total


def _mode(value: str) -> tuple[str, int, str] | None:
    fields = value.split(":", 2)
    if len(fields) != 3:
        return None
    try:
        uid = int(fields[1])
    except ValueError:
        return None
    return fields[0], uid, fields[2]


def _version(value: object) -> tuple[int, ...] | None:
    if not isinstance(value, str) or not value:
        return None
    match = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", value)
    if match is None:
        return None
    return tuple(int(part or 0) for part in match.groups(default="0"))


def _json_observation(observations, name: str) -> dict[str, object] | None:
    raw = _text(observations, name)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def evaluate_fixture(payload: object) -> dict[str, object]:
    """Evaluate raw read-only observations against one strict host contract."""

    expected, observations, kind = _validate_fixture(payload)
    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, detail: str, *, required: bool = True) -> None:
        checks.append(
            {
                "name": name,
                "required": required,
                "status": "pass" if passed else "fail",
                "detail": detail,
            }
        )

    uid = expected["expected_uid"]
    username = expected["username"]
    actual_uid = _integer(_text(observations, "uid"))
    add("uid", actual_uid == uid and uid != 0, f"observed={actual_uid} expected={uid}")
    add(
        "username",
        _text(observations, "username") == username,
        f"expected={username}",
    )
    for tool in ("newuidmap", "newgidmap"):
        path = _text(observations, f"{tool}_path")
        metadata = _mode(_text(observations, f"{tool}_stat"))
        ok = bool(path.startswith("/")) and metadata == ("4755", 0, "regular file")
        add(tool, ok, "absolute setuid-root helper required")
    add(
        "subuid",
        _subid_size(_text(observations, "subuid"), username, uid) >= 65_536,
        "at least 65536 subordinate UIDs required",
    )
    add(
        "subgid",
        _subid_size(_text(observations, "subgid"), username, uid) >= 65_536,
        "at least 65536 subordinate GIDs required",
    )
    namespace_count = _integer(_text(observations, "max_user_namespaces"))
    add(
        "user_namespaces",
        namespace_count is not None and namespace_count > 0,
        f"max_user_namespaces={namespace_count}",
    )
    add(
        "cgroup_v2",
        _text(observations, "cgroup_filesystem") in {"cgroup2", "cgroup2fs"},
        "unified cgroup2 required",
    )
    controllers = set(_text(observations, "cgroup_controllers").split())
    add(
        "cgroup_controllers",
        {"cpu", "memory", "pids"}.issubset(controllers),
        "cpu, memory, and pids controllers required",
    )
    add(
        "user_systemd",
        _text(observations, "systemd_user") in {"running", "degraded"},
        "user systemd manager must be reachable",
    )
    add("linger", _text(observations, "linger") == "yes", "linger=yes required")
    socket_metadata = _mode(_text(observations, "docker_socket_stat"))
    endpoint_ok = (
        expected["docker_host"] == f"unix:///run/user/{uid}/docker.sock"
        and socket_metadata is not None
        and socket_metadata[1:] == (uid, "socket")
        and socket_metadata[0] in {"600", "660", "1600", "1660"}
    )
    add("docker_endpoint", endpoint_ok, str(expected["docker_host"]))

    docker_version = _json_observation(observations, "docker_version")
    minimum_version = _version(expected["min_docker_version"])
    client = _version(
        docker_version.get("Client", {}).get("Version") if docker_version else None
    )
    server = _version(
        docker_version.get("Server", {}).get("Version") if docker_version else None
    )
    version_ok = bool(
        minimum_version and client and server and client >= minimum_version and server >= minimum_version
    )
    add("docker_version", version_ok, f"client={client} server={server} minimum={minimum_version}")

    docker_info = _json_observation(observations, "docker_info")
    security = docker_info.get("SecurityOptions", []) if docker_info else []
    docker_root = docker_info.get("DockerRootDir") if docker_info else None
    rootless_ok = (
        isinstance(security, list)
        and "name=rootless" in security
        and isinstance(docker_root, str)
        and docker_root.startswith(f"/home/{username}/")
        and docker_root != "/var/lib/docker"
    )
    add("rootless_security", rootless_ok, "rootless security option and user-owned data root required")
    driver_status = docker_info.get("DriverStatus", []) if docker_info else []
    backing = " ".join(
        str(value)
        for pair in driver_status
        if isinstance(pair, list)
        for value in pair
    ).lower()
    filesystem = _text(observations, "filesystem_type")
    storage_ok = bool(
        docker_info
        and docker_info.get("Driver") in {"overlay2", "overlayfs"}
        and (
            "extfs" in backing
            or "ext4" in backing
            or filesystem in {"ext2/ext3", "ext4"}
        )
    )
    add(
        "docker_storage",
        storage_ok,
        "native overlay2/overlayfs on the observed ext4 filesystem required",
    )

    df_lines = _text(observations, "filesystem_free").splitlines()
    available_bytes = None
    if df_lines:
        fields = df_lines[-1].split()
        if len(fields) >= 4:
            available_kib = _integer(fields[3])
            available_bytes = available_kib * 1024 if available_kib is not None else None
    add(
        "filesystem_space",
        available_bytes is not None and available_bytes >= expected["min_free_bytes"],
        f"available_bytes={available_bytes} minimum={expected['min_free_bytes']}",
    )
    mem_match = re.search(r"^MemTotal:\s+(\d+)\s+kB$", _text(observations, "meminfo"), re.MULTILINE)
    memory_bytes = int(mem_match.group(1)) * 1024 if mem_match else None
    add(
        "memory",
        memory_bytes is not None and memory_bytes >= expected["min_memory_bytes"],
        f"memory_bytes={memory_bytes} minimum={expected['min_memory_bytes']}",
    )
    cpu = _integer(_text(observations, "cpu_online"))
    add(
        "cpu",
        cpu is not None and cpu >= expected["min_cpu_count"],
        f"online={cpu} minimum={expected['min_cpu_count']}",
    )
    kernel = _version(_text(observations, "kernel_release"))
    add("kernel", kernel is not None and kernel >= (5, 11, 0), f"kernel={kernel}")
    add(
        "git_commit",
        _text(observations, "git_head") == expected["source_commit"],
        f"expected={expected['source_commit']}",
    )
    add("git_clean", _text(observations, "git_status") == "", "tracked worktree must be clean")
    runtime_mode = _mode(_text(observations, "runtime_stat"))
    add(
        "runtime_mode",
        runtime_mode == ("700", uid, "directory"),
        "runtime root must be mode 700 and user-owned",
    )
    secret_mode = _mode(_text(observations, "secret_stat"))
    add(
        "secret_mode",
        secret_mode == ("600", uid, "regular file"),
        "secret file must be regular, mode 600, and user-owned",
    )

    fuse_present = bool(_text(observations, "fuse_overlayfs_path"))
    fuse_unnecessary = not fuse_present and filesystem in {"ext2/ext3", "ext4"} and storage_ok
    checks.append(
        {
            "name": "fuse_overlayfs",
            "required": False,
            "status": "pass" if fuse_present else ("unnecessary" if fuse_unnecessary else "fail"),
            "detail": (
                "optional with native overlay2/overlayfs on the observed "
                "modern kernel/ext4 host"
            ),
        }
    )

    required = [item for item in checks if item["required"]]
    failed = sum(item["status"] != "pass" for item in required)
    return {
        "schema_version": 1,
        "mode": "read-only",
        "fixture_kind": kind,
        "ready": failed == 0,
        "required_passed": len(required) - failed,
        "required_failed": failed,
        "optional_unnecessary": sum(item["status"] == "unnecessary" for item in checks),
        "checks": checks,
    }


def _load_json(path: str | Path) -> object:
    try:
        return json.loads(Path(path).expanduser().read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HostCheckError(f"cannot load host fixture: {exc}") from exc


def _human_summary(report: Mapping[str, object]) -> str:
    state = "READY" if report["ready"] else "NOT READY"
    failures = [
        item["name"]
        for item in report["checks"]
        if item["required"] and item["status"] != "pass"
    ]
    suffix = "" if not failures else "; failed=" + ",".join(failures)
    return (
        f"{state}: read-only rootless host check; "
        f"required={report['required_passed']} passed/{report['required_failed']} failed"
        f"{suffix}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture")
    parser.add_argument("--expected-uid", type=int)
    parser.add_argument("--username")
    parser.add_argument("--docker-host")
    parser.add_argument("--source-root")
    parser.add_argument("--source-commit")
    parser.add_argument("--runtime-root")
    parser.add_argument("--secret-file")
    parser.add_argument("--min-cpu-count", type=int, default=32)
    parser.add_argument("--min-memory-bytes", type=int, default=96 * 1024**3)
    parser.add_argument("--min-free-bytes", type=int, default=50 * 1024**3)
    parser.add_argument("--min-docker-version", default="29.0.0")
    return parser


def _expected_from_args(args: argparse.Namespace) -> dict[str, object]:
    required = {
        "expected_uid": args.expected_uid,
        "username": args.username,
        "source_root": args.source_root,
        "source_commit": args.source_commit,
        "runtime_root": args.runtime_root,
        "secret_file": args.secret_file,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise HostCheckError("live mode is missing arguments: " + ", ".join(missing))
    docker_host = args.docker_host or f"unix:///run/user/{args.expected_uid}/docker.sock"
    return {
        **required,
        "docker_host": docker_host,
        "min_cpu_count": args.min_cpu_count,
        "min_memory_bytes": args.min_memory_bytes,
        "min_free_bytes": args.min_free_bytes,
        "min_docker_version": args.min_docker_version,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.fixture:
            payload = _load_json(args.fixture)
        else:
            payload = collect_live(_expected_from_args(args))
        report = evaluate_fixture(payload)
    except HostCheckError as exc:
        print(json.dumps({"schema_version": 1, "mode": "read-only", "ready": False, "error": str(exc)}, sort_keys=True, indent=2))
        print(f"NOT READY: read-only rootless host check input error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    print(_human_summary(report), file=sys.stderr)
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
