"""Deterministic admission for untrusted full-worker evolution candidates."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable

import yaml


_SECRET_NAMES = frozenset({".env", "id_rsa", "id_ed25519"})
_TEXT_SUFFIXES = frozenset({".json", ".md", ".py", ".txt", ".yaml", ".yml"})
_LOCAL_COMPONENT_KEYS = frozenset({
    "middleware", "memory", "routing", "skills", "tools", "validator"
})
_PROTECTED_FIELDS = (
    "type",
    "name",
    "max_context_tokens",
    "system_prompt",
    "system_prompt_type",
    "tool_call_mode",
    "max_iterations",
    "llm_config.model",
    "llm_config.base_url",
    "llm_config.api_key",
    "llm_config.max_tokens",
    "llm_config.temperature",
    "llm_config.stream",
    "llm_config.api_type",
    "llm_config.timeout",
    "tracers",
)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CandidateAdmissionError(ValueError):
    """A candidate is unsafe, invalid, or incompatible with the fixed experiment."""


@dataclass(frozen=True)
class CandidateFile:
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class CandidateAdmissionRecord:
    admitted: bool
    candidate_digest: str
    policy_digest: str
    files: tuple[CandidateFile, ...]
    checks: tuple[str, ...]
    failure: str | None = None


@dataclass(frozen=True)
class AdmissionPolicy:
    allowed_top_level_files: frozenset[str]
    allowed_top_level_directories: frozenset[str]
    protected_fields: tuple[str, ...]
    allowed_import_roots: frozenset[str]
    forbidden_content: tuple[str, ...] = ()
    max_files: int = 2_000
    max_bytes: int = 64 * 1024 * 1024

    @classmethod
    def qfbench_full(
        cls,
        *,
        forbidden_content: Iterable[str] = (),
    ) -> "AdmissionPolicy":
        installed = {
            "nexau",
            "numpy",
            "pandas",
            "pydantic",
            "yaml",
        }
        return cls(
            allowed_top_level_files=frozenset({"agent.yaml", "systemprompt.md"}),
            allowed_top_level_directories=frozenset({
                "memory",
                "middleware",
                "routing",
                "skills",
                "tool_descriptions",
                "tools",
                "validator",
            }),
            protected_fields=_PROTECTED_FIELDS,
            allowed_import_roots=frozenset(set(sys.stdlib_module_names) | installed),
            forbidden_content=tuple(str(item) for item in forbidden_content if str(item)),
        )

    def digest(self) -> str:
        payload = {
            "allowed_top_level_files": sorted(self.allowed_top_level_files),
            "allowed_top_level_directories": sorted(
                self.allowed_top_level_directories
            ),
            "protected_fields": list(self.protected_fields),
            "allowed_import_roots": sorted(self.allowed_import_roots),
            "forbidden_content": list(self.forbidden_content),
            "max_files": self.max_files,
            "max_bytes": self.max_bytes,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def _is_secret_like(path: PurePosixPath) -> bool:
    name = path.name.lower()
    return (
        name in _SECRET_NAMES
        or name.startswith(".env.")
        or name.startswith("credentials")
        or name.startswith("secrets")
        or name.endswith((".key", ".pem"))
    )


def _candidate_files(
    root: Path,
    policy: AdmissionPolicy,
) -> tuple[tuple[CandidateFile, str], ...]:
    if not root.is_dir():
        raise CandidateAdmissionError(f"candidate directory does not exist: {root}")
    collected: list[tuple[CandidateFile, str]] = []
    total_bytes = 0
    for path in sorted(
        root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
    ):
        relative = path.relative_to(root)
        pure = PurePosixPath(relative.as_posix())
        if path.is_symlink():
            raise CandidateAdmissionError(f"symlink is forbidden: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise CandidateAdmissionError(f"non-regular candidate member: {relative}")
        if _is_secret_like(pure):
            raise CandidateAdmissionError(f"secret-like candidate file: {relative}")
        top = pure.parts[0]
        if len(pure.parts) == 1:
            if top not in policy.allowed_top_level_files:
                raise CandidateAdmissionError(
                    f"unknown top-level candidate file: {relative}"
                )
        elif top not in policy.allowed_top_level_directories:
            raise CandidateAdmissionError(
                f"unknown top-level candidate directory: {top}"
            )
        if not path.suffix:
            raise CandidateAdmissionError(
                f"extensionless candidate file is forbidden: {relative}"
            )
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            raise CandidateAdmissionError(
                f"unsupported candidate file type: {relative}"
            )
        payload = path.read_bytes()
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CandidateAdmissionError(
                f"candidate files must be UTF-8 text: {relative}"
            ) from exc
        if "\x00" in text:
            raise CandidateAdmissionError(
                f"candidate files must be UTF-8 text without NUL: {relative}"
            )
        for forbidden in policy.forbidden_content:
            if forbidden in text:
                raise CandidateAdmissionError(
                    f"forbidden content found in candidate file {relative}"
                )
        total_bytes += len(payload)
        if total_bytes > policy.max_bytes:
            raise CandidateAdmissionError(
                f"candidate byte limit exceeded: {total_bytes} > {policy.max_bytes}"
            )
        collected.append((CandidateFile(
            path=pure.as_posix(),
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
        ), text))
        if len(collected) > policy.max_files:
            raise CandidateAdmissionError(
                f"candidate file limit exceeded: {len(collected)} > {policy.max_files}"
            )
    if not collected:
        raise CandidateAdmissionError("candidate directory is empty")
    return tuple(collected)


def _digest_files(files: Iterable[CandidateFile]) -> str:
    digest = hashlib.sha256()
    for item in files:
        path = item.path.encode()
        payload_digest = item.sha256.encode()
        digest.update(len(path).to_bytes(8, "big"))
        digest.update(path)
        digest.update(item.size_bytes.to_bytes(8, "big"))
        digest.update(payload_digest)
    return digest.hexdigest()


def _load_yaml(path: Path, label: str) -> dict:
    try:
        payload = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise CandidateAdmissionError(f"invalid {label} YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise CandidateAdmissionError(f"{label} YAML must be an object")
    return payload


def _dotted(payload: dict, dotted: str):
    current = payload
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise CandidateAdmissionError(f"protected field {dotted} is missing")
        current = current[part]
    return current


def _validate_protected(seed: Path, candidate: Path, policy: AdmissionPolicy) -> dict:
    seed_config = _load_yaml(seed / "agent.yaml", "seed agent")
    candidate_config = _load_yaml(candidate / "agent.yaml", "candidate agent")
    for field in policy.protected_fields:
        if _dotted(seed_config, field) != _dotted(candidate_config, field):
            raise CandidateAdmissionError(f"protected field {field} changed")
    allowed_keys = set(seed_config) | set(_LOCAL_COMPONENT_KEYS)
    extra = set(candidate_config) - allowed_keys
    if extra:
        raise CandidateAdmissionError(
            f"candidate agent has unsupported top-level config: {sorted(extra)}"
        )
    return candidate_config


def _call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
        return f"{call.func.value.id}.{call.func.attr}"
    return ""


def _validate_python(
    root: Path,
    files: Iterable[CandidateFile],
    policy: AdmissionPolicy,
) -> dict[str, ast.Module]:
    trees: dict[str, ast.Module] = {}
    for item in files:
        if not item.path.endswith(".py"):
            continue
        path = root / item.path
        try:
            tree = ast.parse(path.read_text(), filename=item.path)
        except SyntaxError as exc:
            raise CandidateAdmissionError(
                f"Python syntax error in {item.path}: {exc.msg}"
            ) from exc
        trees[item.path] = tree
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports = [node.module.split(".", 1)[0]]
            else:
                imports = []
            for module in imports:
                if module not in policy.allowed_import_roots and module != "tools":
                    raise CandidateAdmissionError(
                        f"undeclared import {module!r} in {item.path}"
                    )
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name in {"eval", "exec"}:
                raise CandidateAdmissionError(
                    f"in-process {name} is forbidden in {item.path}"
                )
            if name == "subprocess.Popen":
                raise CandidateAdmissionError(
                    f"subprocess Popen lacks a coordinator-enforced timeout in {item.path}"
                )
            if name != "subprocess.run":
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
            shell = keywords.get("shell")
            if isinstance(shell, ast.Constant) and shell.value is True:
                raise CandidateAdmissionError(
                    f"subprocess shell=True is forbidden in {item.path}"
                )
            if "timeout" not in keywords:
                raise CandidateAdmissionError(
                    f"subprocess call requires timeout in {item.path}"
                )
    return trees


def _resolve_relative(root: Path, value: str, label: str) -> Path:
    pure = PurePosixPath(value.removeprefix("./"))
    if pure.is_absolute() or not pure.parts or any(
        part in {"", ".", ".."} for part in pure.parts
    ):
        raise CandidateAdmissionError(f"unsafe {label} path {value!r}")
    target = (root / Path(*pure.parts)).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise CandidateAdmissionError(f"{label} path escapes candidate: {value!r}") from exc
    return target


def _validate_local_bindings(
    root: Path,
    config: dict,
    trees: dict[str, ast.Module],
) -> None:
    tools = config.get("tools")
    if not isinstance(tools, list) or not tools:
        raise CandidateAdmissionError("candidate agent tools must be a non-empty list")
    names: set[str] = set()
    for raw in tools:
        if not isinstance(raw, dict):
            raise CandidateAdmissionError("candidate agent tool entry must be an object")
        name = raw.get("name")
        yaml_path = raw.get("yaml_path")
        binding = raw.get("binding")
        if not all(isinstance(item, str) and item for item in (name, yaml_path, binding)):
            raise CandidateAdmissionError("candidate agent tool entry is incomplete")
        if name in names:
            raise CandidateAdmissionError(f"duplicate candidate tool name {name!r}")
        names.add(name)
        description_path = _resolve_relative(root, yaml_path, "tool description")
        description = _load_yaml(description_path, f"tool description {name}")
        if description.get("name") != name:
            raise CandidateAdmissionError(
                f"tool description name mismatch for {name!r}"
            )
        module, separator, function = binding.partition(":")
        if not separator or not _IDENTIFIER_RE.fullmatch(function):
            raise CandidateAdmissionError(f"invalid tool binding {binding!r}")
        if not module.startswith("tools."):
            if not module.startswith("nexau."):
                raise CandidateAdmissionError(
                    f"external tool binding is not allowlisted: {binding!r}"
                )
            continue
        module_path = root / (module.replace(".", "/") + ".py")
        relative = module_path.relative_to(root).as_posix()
        tree = trees.get(relative)
        if tree is None:
            raise CandidateAdmissionError(
                f"local binding module does not exist: {module!r}"
            )
        functions = {
            node.name: node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        function_node = functions.get(function)
        if function_node is None:
            raise CandidateAdmissionError(
                f"binding function {function!r} is missing from {module!r}"
            )
        schema = description.get("input_schema")
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        if not isinstance(properties, dict):
            raise CandidateAdmissionError(
                f"tool description input properties must be an object for {name!r}"
            )
        accepted = {
            argument.arg
            for argument in (*function_node.args.posonlyargs, *function_node.args.args,
                             *function_node.args.kwonlyargs)
        }
        if function_node.args.kwarg is None:
            missing = sorted(set(properties) - accepted)
            if missing:
                raise CandidateAdmissionError(
                    f"binding signature for {name!r} cannot accept {', '.join(missing)}"
                )


def admit_candidate(
    seed_dir: str | Path,
    candidate_dir: str | Path,
    policy: AdmissionPolicy,
    *,
    exact_runtime: Callable[[Path], None] | None = None,
) -> CandidateAdmissionRecord:
    """Validate a candidate before any official task-scoring attempt is created."""

    seed = Path(seed_dir).resolve()
    candidate = Path(candidate_dir).resolve()
    scanned = _candidate_files(candidate, policy)
    files = tuple(item for item, _ in scanned)
    config = _validate_protected(seed, candidate, policy)
    trees = _validate_python(candidate, files, policy)
    _validate_local_bindings(candidate, config, trees)
    checks = [
        "file_manifest",
        "protected_config",
        "python_compile",
        "declared_imports",
        "subprocess_timeouts",
        "local_bindings",
    ]
    if exact_runtime is not None:
        exact_runtime(candidate)
        checks.append("exact_runtime")
    return CandidateAdmissionRecord(
        admitted=True,
        candidate_digest=_digest_files(files),
        policy_digest=policy.digest(),
        files=files,
        checks=tuple(checks),
    )
