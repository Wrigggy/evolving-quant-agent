"""Entrypoint uploaded to an isolated full-harness evolver sandbox."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import tarfile
import time
from collections import Counter
from pathlib import Path
from typing import Any


_MAX_TRACE_BYTES = 4 * 1024 * 1024
_MAX_FINAL_BYTES = 512 * 1024


def _redact(text: str) -> str:
    scrubbed = text
    for name, value in os.environ.items():
        if value and any(marker in name.upper() for marker in ("KEY", "TOKEN", "SECRET")):
            scrubbed = scrubbed.replace(value, "[REDACTED]")
    return scrubbed


def _message_text(message) -> str:
    try:
        return message.get_text_content()
    except Exception:  # noqa: BLE001
        return str(getattr(message, "content", "") or "")


def _role_name(message) -> str:
    raw = getattr(message, "role", "")
    value = getattr(raw, "value", raw)
    role = str(value).casefold()
    if "." in role:
        role = role.rsplit(".", 1)[-1]
    return role


def _json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _usage(item) -> dict[str, Any] | None:
    for attribute in ("usage", "usage_metadata"):
        value = getattr(item, attribute, None)
        if value is None:
            continue
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if isinstance(value, dict):
            return value
    return None


def _archive_candidate(candidate_dir: Path, output_path: Path) -> tuple[str, ...]:
    members: list[str] = []
    with tarfile.open(output_path, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(
            candidate_dir.rglob("*"),
            key=lambda item: item.relative_to(candidate_dir).as_posix(),
        ):
            relative = path.relative_to(candidate_dir)
            if path.is_symlink():
                raise ValueError(f"candidate symlink is forbidden: {relative}")
            if not path.is_file():
                continue
            payload = path.read_bytes()
            name = relative.as_posix()
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            archive.addfile(info, fileobj=io.BytesIO(payload))
            members.append(name)
    return tuple(members)


def _access_summary(path: Path, evidence_dir: Path) -> dict[str, Any]:
    operations: Counter[str] = Counter()
    bytes_by_source: Counter[str] = Counter()
    evidence_paths: set[str] = set()
    records = 0
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            records += 1
            operations[str(record.get("operation", "unknown"))] += 1
            source = str(record.get("source", "unknown"))
            returned = record.get("bytes_returned", 0)
            if isinstance(returned, int) and returned >= 0:
                bytes_by_source[source] += returned
            if record.get("source") == "evidence":
                evidence_paths.add(str(record.get("relative_path", "")))
    evidence_members = sorted(
        path.relative_to(evidence_dir).as_posix()
        for path in evidence_dir.rglob("*")
        if path.is_file() and not path.is_symlink()
    )
    exact_paths = sorted(set(evidence_members) & evidence_paths)
    return {
        "records": records,
        "operations": dict(sorted(operations.items())),
        "bytes_returned_by_source": dict(sorted(bytes_by_source.items())),
        "evidence_paths": sorted(evidence_paths),
        "evidence_member_count": len(evidence_members),
        "exact_evidence_paths": exact_paths,
        "exact_evidence_access_ratio": (
            len(exact_paths) / len(evidence_members) if evidence_members else None
        ),
    }


def run(
    *,
    candidate_dir: Path,
    evidence_dir: Path,
    evolver_dir: Path,
    result_dir: Path,
    diagnosis: str,
    iteration: int,
) -> int:
    from nexau import Agent, AgentConfig

    started = time.time()
    result_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir = candidate_dir.resolve(strict=True)
    evidence_dir = evidence_dir.resolve(strict=True)
    evolver_dir = evolver_dir.resolve(strict=True)
    reference_dir = (evolver_dir / "reference").resolve(strict=True)
    runtime_root = Path(__file__).resolve(strict=True).parent
    if str(evolver_dir) not in sys.path:
        sys.path.insert(0, str(evolver_dir))
    access_log = result_dir / "access_log.jsonl"
    access_log.touch()
    os.environ["QEA_CANDIDATE_ROOT"] = str(candidate_dir)
    os.environ["QEA_EVIDENCE_ROOT"] = str(evidence_dir)
    os.environ["QEA_REFERENCE_ROOT"] = str(reference_dir)
    os.environ["QEA_RUNTIME_ROOT"] = str(runtime_root)
    os.environ["QEA_ACCESS_LOG"] = str(access_log)
    config = AgentConfig.from_yaml(config_path=evolver_dir / "agent.yaml")
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        os.environ.pop(name, None)

    agent = Agent(config=config)
    message = (
        f"Evolution iteration: {iteration}\n"
        "Coordinator diagnosis (non-authoritative; verify against evidence):\n"
        f"{diagnosis}\n\n"
        "Inspect the authorized evidence and candidate, then make one coherent "
        "full-harness improvement."
    )
    context = {
        "date": os.environ.get("QEA_EVAL_DATE", "2026-07-27"),
        "username": "qea-evolver",
        "working_directory": str(candidate_dir),
    }
    context["env_content"] = dict(context)
    response = agent.run(message=message, context=context)
    final = response if isinstance(response, str) else (response[0] if response else "")
    final_text = _redact(str(final))
    final_payload = final_text.encode("utf-8")[:_MAX_FINAL_BYTES]
    (result_dir / "final.txt").write_bytes(final_payload)

    trace_bytes = 0
    turns = tool_calls = tool_errors = 0
    usages: list[dict[str, Any]] = []
    trace_path = result_dir / "raw_trace.jsonl"
    with trace_path.open("w", encoding="utf-8") as trace:
        for item in agent.full_trace or ():
            role = _role_name(item)
            content = _redact(_message_text(item))
            record = json.dumps(
                {"role": role, "content": content}, ensure_ascii=False
            ) + "\n"
            encoded = record.encode("utf-8")
            if trace_bytes + len(encoded) > _MAX_TRACE_BYTES:
                break
            trace.write(record)
            trace_bytes += len(encoded)
            if role == "assistant":
                turns += 1
            elif role not in {"", "user"}:
                tool_calls += 1
                if any(word in content.lower() for word in ("error", "failed", "traceback")):
                    tool_errors += 1
            usage = _usage(item)
            if usage is not None:
                usages.append(usage)

    prediction = _json_object(final_text)
    if prediction is None:
        prediction = {
            "parse_error": "final response did not contain a JSON object",
            "final_sha256": hashlib.sha256(final_payload).hexdigest(),
        }
    (result_dir / "prediction.json").write_text(
        json.dumps(prediction, sort_keys=True, indent=2) + "\n"
    )
    access_summary = _access_summary(access_log, evidence_dir)
    (result_dir / "access-summary.json").write_text(
        json.dumps(access_summary, sort_keys=True, indent=2) + "\n"
    )
    members = _archive_candidate(candidate_dir, result_dir / "candidate.tar")
    discovery_state_path = result_dir / "discovery-hypothesis.json"
    discovery_state = None
    if discovery_state_path.is_file():
        try:
            discovery_state = json.loads(discovery_state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            discovery_state = {"parse_error": "invalid discovery hypothesis JSON"}
    try:
        from evolver_discovery import measure_discovery_quality
    except ModuleNotFoundError:  # Local repository tests; sandbox uses /qea module.
        from qea.evolver_discovery import measure_discovery_quality

    evidence_members = tuple(
        path.relative_to(evidence_dir).as_posix()
        for path in evidence_dir.rglob("*")
        if path.is_file() and not path.is_symlink()
    )
    discovery_quality = measure_discovery_quality(
        prediction=prediction,
        access_summary=access_summary,
        discovery_state=discovery_state,
        evidence_members=evidence_members,
    )
    (result_dir / "discovery-quality.json").write_text(
        json.dumps(discovery_quality, sort_keys=True, indent=2) + "\n"
    )
    summary = {
        "turns": turns,
        "tool_calls": tool_calls,
        "tool_errors": tool_errors,
        "candidate_files": len(members),
        "candidate_members": list(members),
        "trace_bytes": trace_bytes,
        "final_truncated": len(final_text.encode("utf-8")) > len(final_payload),
        "secs": round(time.time() - started, 3),
        "model_usage": usages or None,
        "model_usage_reason": None if usages else "not exposed by NexAU tracer",
        "discovery": discovery_quality,
        "discovery_hypothesis": discovery_state,
    }
    (result_dir / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--evolver-dir", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--diagnosis-file", type=Path, required=True)
    parser.add_argument("--iteration", type=int, required=True)
    args = parser.parse_args(argv)
    return run(
        candidate_dir=args.candidate_dir,
        evidence_dir=args.evidence_dir,
        evolver_dir=args.evolver_dir,
        result_dir=args.result_dir,
        diagnosis=args.diagnosis_file.read_text(encoding="utf-8"),
        iteration=args.iteration,
    )


if __name__ == "__main__":
    raise SystemExit(main())
