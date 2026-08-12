"""Content-addressed QuantCodeEval T16/T24 engineering-canary image plan."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .benchmarks.quantcodeeval import verify_quantcodeeval_role_root
from .rootless_images import (
    RootlessContextFile,
    RootlessImageBuildPlan,
    RootlessImageError,
)


PANDAS_223_CP311_X86_64_SHA256 = (
    "c124333816c3a9b03fbeef3a9f230ba9a737e9e5bb4060aa2107a86cc0a497fc"
)


def _identity(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def prepare_quantcodeeval_canary_image_plan(
    *,
    public_root: str | Path,
    trusted_root: str | Path,
    base_image_ref: str,
    cpu_count: int = 4,
    memory_mb: int = 8192,
    build_timeout_seconds: int = 1800,
) -> RootlessImageBuildPlan:
    """Prepare one shared checker/strategy image for the two-task canary.

    This deliberately records a canary runtime deviation instead of pretending
    to be the official full ``uv.lock`` environment: the parent already pins
    Python 3.11.15 and the official scientific stack versions, and this layer
    replaces only pandas with the official 2.2.3 wheel after checking its hash.
    Golden parity remains the release gate.
    """

    public = verify_quantcodeeval_role_root(public_root, "public")
    trusted = verify_quantcodeeval_role_root(trusted_root, "trusted-verifier")
    if public.commit != trusted.commit or public.task_ids != trusted.task_ids:
        raise RootlessImageError("QuantCodeEval public/trusted identities differ")
    if public.task_ids != ("T16", "T24"):
        raise RootlessImageError("canary image requires exact T16/T24 task panel")
    if not base_image_ref.startswith("sha256:") or len(base_image_ref) != 71:
        raise RootlessImageError("canary image requires an immutable local image ID")
    if any(
        type(value) is not int or value <= 0
        for value in (cpu_count, memory_mb, build_timeout_seconds)
    ):
        raise RootlessImageError("image resources must be positive integers")

    package_root = Path(__file__).resolve().parent
    minimal_package_init = b'"""Minimal isolated QuantCodeEval RPC package."""\n'
    minimal_verifier_init = b'"""Minimal isolated QuantCodeEval verifier package."""\n'
    base_tag = f"qea-local-base:{base_image_ref.removeprefix('sha256:')}"
    dockerfile = f"""FROM {base_tag}

USER root
RUN rm -f /app/prices.csv \\
 && mkdir -p /tmp/qce-wheel \\
 && python3 -m pip download --disable-pip-version-check --no-deps \\
      --only-binary=:all: --dest /tmp/qce-wheel pandas==2.2.3 \\
 && test "$(find /tmp/qce-wheel -maxdepth 1 -type f | wc -l)" = "1" \\
 && echo "{PANDAS_223_CP311_X86_64_SHA256}  /tmp/qce-wheel/$(basename /tmp/qce-wheel/*)" | sha256sum -c - \\
 && python3 -m pip install --disable-pip-version-check --no-deps /tmp/qce-wheel/* \\
 && rm -rf /tmp/qce-wheel \\
 && python3 -c "import sys,numpy,pandas; assert sys.version_info[:3] == (3,11,15); assert numpy.__version__ == '2.4.6'; assert pandas.__version__ == '2.2.3'"
RUN mkdir -p /opt/qea-qce/qea/verifiers /opt/qea/uv-cache-seed /opt/qea/uv-cache /opt/qea/uv-tools /opt/qea/uv-bin
COPY qea/__init__.py /opt/qea-qce/qea/__init__.py
COPY qea/verifiers/__init__.py /opt/qea-qce/qea/verifiers/__init__.py
COPY qea/verifiers/quantcodeeval_rpc.py /opt/qea-qce/qea/verifiers/quantcodeeval_rpc.py
COPY qea/verifiers/quantcodeeval_rpc_server.py /opt/qea-qce/qea/verifiers/quantcodeeval_rpc_server.py
RUN python3 -m pip freeze | LC_ALL=C sort > /opt/qea/verifier-requirements.lock
LABEL org.qea.quantcodeeval.role="shared-verifier-strategy"
LABEL org.qea.quantcodeeval.protocol="T16-T24-engineering-canary"
""".encode()
    raw_files = (
        ("Dockerfile", dockerfile, 0o644),
        ("qea/__init__.py", minimal_package_init, 0o644),
        (
            "qea/verifiers/__init__.py",
            minimal_verifier_init,
            0o644,
        ),
        (
            "qea/verifiers/quantcodeeval_rpc.py",
            (package_root / "verifiers" / "quantcodeeval_rpc.py").read_bytes(),
            0o644,
        ),
        (
            "qea/verifiers/quantcodeeval_rpc_server.py",
            (package_root / "verifiers" / "quantcodeeval_rpc_server.py").read_bytes(),
            0o555,
        ),
    )
    context_files = tuple(
        RootlessContextFile.from_payload(path, content, mode=mode)
        for path, content, mode in raw_files
    )
    source_identity = _identity({
        "public_manifest_sha256": public.manifest_sha256,
        "trusted_manifest_sha256": trusted.manifest_sha256,
    })
    test_identity = _identity({
        task_id: hashlib.sha256(
            (trusted.root / "tasks" / task_id / "tests" / "test.sh").read_bytes()
        ).hexdigest()
        for task_id in trusted.task_ids
    })
    identity_payload = {
        "role": "verifier",
        "task_id": "T16-T24",
        "benchmark_commit": public.commit,
        "base_image_ref": base_image_ref,
        "source_manifest_sha256": source_identity,
        "verifier_test_script_sha256": test_identity,
        "context_files": [item.manifest_record() for item in context_files],
        "cpu_count": cpu_count,
        "memory_mb": memory_mb,
        "build_timeout_seconds": build_timeout_seconds,
        "build_network": "default",
        "protocol": "quantcodeeval-engineering-canary-v1",
    }
    return RootlessImageBuildPlan(
        role="verifier",
        task_id="T16-T24",
        benchmark_commit=public.commit,
        base_image_ref=base_image_ref,
        source_manifest_sha256=source_identity,
        verifier_test_script_sha256=test_identity,
        context_files=context_files,
        dockerfile_bytes=dockerfile,
        cpu_count=cpu_count,
        memory_mb=memory_mb,
        build_timeout_seconds=build_timeout_seconds,
        build_network="default",
        nexau_runtime_image_ref=None,
        identity_sha256=_identity(identity_payload),
    )
