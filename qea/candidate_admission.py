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
_LOCAL_CONFIG_KEYS = frozenset({"middlewares", "skills"})
_LOCAL_PYTHON_ROOTS = frozenset({
    "memory", "middleware", "routing", "skills", "tools", "validator"
})
_PROTECTED_FIELDS = (
    "type",
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
            "runtime_bridge",
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
    allowed_keys = set(seed_config) | set(_LOCAL_CONFIG_KEYS)
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
                if (
                    module not in policy.allowed_import_roots
                    and module not in _LOCAL_PYTHON_ROOTS
                ):
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
) -> set[str]:
    tools = config.get("tools")
    if not isinstance(tools, list) or not tools:
        raise CandidateAdmissionError("candidate agent tools must be a non-empty list")
    names: set[str] = set()
    local_modules: set[str] = set()
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
        local_modules.add(module)
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
    return local_modules


def _validate_skills(root: Path, config: dict) -> None:
    raw_skills = config.get("skills", [])
    if not isinstance(raw_skills, list):
        raise CandidateAdmissionError("candidate agent skills must be a list")
    names: set[str] = set()
    for raw in raw_skills:
        if not isinstance(raw, str) or not raw:
            raise CandidateAdmissionError("candidate skill path must be a non-empty string")
        folder = _resolve_relative(root, raw, "skill")
        try:
            relative = folder.relative_to(root.resolve())
        except ValueError as exc:  # pragma: no cover - guarded by _resolve_relative
            raise CandidateAdmissionError(f"skill path escapes candidate: {raw!r}") from exc
        if not relative.parts or relative.parts[0] != "skills":
            raise CandidateAdmissionError(
                f"candidate skill must live below skills/: {raw!r}"
            )
        skill_path = folder / "SKILL.md"
        if not skill_path.is_file():
            raise CandidateAdmissionError(f"candidate skill has no SKILL.md: {raw!r}")
        text = skill_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            raise CandidateAdmissionError(
                f"candidate skill frontmatter is missing: {raw!r}"
            )
        try:
            closing = next(
                index for index, line in enumerate(lines[1:], start=1)
                if line.strip() == "---"
            )
        except StopIteration as exc:
            raise CandidateAdmissionError(
                f"candidate skill frontmatter is unterminated: {raw!r}"
            ) from exc
        try:
            metadata = yaml.safe_load("\n".join(lines[1:closing]))
        except yaml.YAMLError as exc:
            raise CandidateAdmissionError(
                f"invalid candidate skill frontmatter {raw!r}: {exc}"
            ) from exc
        if not isinstance(metadata, dict):
            raise CandidateAdmissionError(
                f"candidate skill frontmatter must be an object: {raw!r}"
            )
        name = metadata.get("name")
        description = metadata.get("description")
        if not isinstance(name, str) or not name.strip():
            raise CandidateAdmissionError(f"candidate skill name is missing: {raw!r}")
        if not isinstance(description, str) or not description.strip():
            raise CandidateAdmissionError(
                f"candidate skill description is missing: {raw!r}"
            )
        if name in names:
            raise CandidateAdmissionError(f"duplicate candidate skill name {name!r}")
        names.add(name)


def _middleware_binding(raw: object, *, index: int) -> str:
    if isinstance(raw, str) and raw:
        return raw
    if not isinstance(raw, dict):
        raise CandidateAdmissionError(
            f"candidate middleware {index} must be a string or object"
        )
    extra = set(raw) - {"import", "params"}
    if extra:
        raise CandidateAdmissionError(
            f"candidate middleware {index} has unsupported fields: {sorted(extra)}"
        )
    binding = raw.get("import")
    params = raw.get("params")
    if not isinstance(binding, str) or not binding:
        raise CandidateAdmissionError(
            f"candidate middleware {index} import is missing"
        )
    if params is not None and not isinstance(params, dict):
        raise CandidateAdmissionError(
            f"candidate middleware {index} params must be an object"
        )
    return binding


def _validate_middlewares(
    root: Path,
    config: dict,
    trees: dict[str, ast.Module],
) -> set[str]:
    raw_middlewares = config.get("middlewares", [])
    if not isinstance(raw_middlewares, list):
        raise CandidateAdmissionError("candidate agent middlewares must be a list")
    local_modules: set[str] = set()
    for index, raw in enumerate(raw_middlewares):
        binding = _middleware_binding(raw, index=index)
        module, separator, symbol = binding.partition(":")
        if not separator or not _IDENTIFIER_RE.fullmatch(symbol):
            raise CandidateAdmissionError(f"invalid middleware import {binding!r}")
        if module.startswith("nexau."):
            continue
        if not module.startswith("middleware."):
            raise CandidateAdmissionError(
                f"local middleware import must be below middleware/: {binding!r}"
            )
        module_path = root / (module.replace(".", "/") + ".py")
        relative = module_path.relative_to(root).as_posix()
        tree = trees.get(relative)
        if tree is None:
            raise CandidateAdmissionError(
                f"local middleware module does not exist: {module!r}"
            )
        symbols = {
            node.name
            for node in tree.body
            if isinstance(
                node,
                (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            )
        }
        if symbol not in symbols:
            raise CandidateAdmissionError(
                f"middleware symbol {symbol!r} is missing from {module!r}"
            )
        local_modules.add(module)
    return local_modules


def _module_name(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imported_local_modules(
    module: str,
    path: str,
    tree: ast.Module,
    known: set[str],
) -> set[str]:
    imported: set[str] = set()
    pure = PurePosixPath(path)
    package = module if pure.stem == "__init__" else module.rpartition(".")[0]
    for node in ast.walk(tree):
        candidates: list[str] = []
        if isinstance(node, ast.Import):
            candidates.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                package_parts = package.split(".") if package else []
                trim = node.level - 1
                if trim > len(package_parts):
                    continue
                base_parts = package_parts[: len(package_parts) - trim]
                if node.module:
                    base_parts.extend(node.module.split("."))
                base = ".".join(base_parts)
            else:
                base = node.module or ""
            if base:
                candidates.append(base)
                candidates.extend(f"{base}.{alias.name}" for alias in node.names)
        for candidate in candidates:
            if candidate in known:
                imported.add(candidate)
    return imported


def _validate_component_reachability(
    trees: dict[str, ast.Module],
    entrypoints: set[str],
) -> None:
    modules = {
        _module_name(path): (path, tree)
        for path, tree in trees.items()
        if _module_name(path)
    }
    known = set(modules)
    edges = {
        module: _imported_local_modules(module, path, tree, known)
        for module, (path, tree) in modules.items()
    }
    reachable: set[str] = set()
    pending = list(entrypoints)
    while pending:
        module = pending.pop()
        if module in reachable:
            continue
        reachable.add(module)
        pending.extend(edges.get(module, ()))
        parts = module.split(".")
        reachable.update(".".join(parts[:index]) for index in range(1, len(parts)))
    checked_roots = {"memory", "middleware", "routing", "tools", "validator"}
    unreachable = sorted(
        module
        for module in known
        if module.split(".", 1)[0] in checked_roots and module not in reachable
    )
    if unreachable:
        raise CandidateAdmissionError(
            "candidate Python modules are not reachable from a declared tool or "
            f"middleware: {unreachable}"
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
    tool_modules = _validate_local_bindings(candidate, config, trees)
    _validate_skills(candidate, config)
    middleware_modules = _validate_middlewares(candidate, config, trees)
    _validate_component_reachability(
        trees,
        tool_modules | middleware_modules,
    )
    checks = [
        "file_manifest",
        "protected_config",
        "python_compile",
        "declared_imports",
        "subprocess_timeouts",
        "local_bindings",
        "local_skills",
        "local_middlewares",
        "component_reachability",
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
