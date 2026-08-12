"""Deterministic pre-submission validator for quant strategy modules.

Scope
-----
Audits a worker-submitted ``strategy.py``-style module for mechanical
compliance that is independent of any benchmark answer:

* parse health and required top-level function presence/signature
  (parameter names are read statically from the AST, exactly matching the
  interface contract "argument names should match the input column names");
* synthetic single-DataFrame execution: when the spec lists functions in
  pipeline order, each single-DataFrame function runs on the accumulated
  synthetic frame, so downstream steps can consume upstream output columns;
* output-column completeness, finite values, NaN/lag placement
  (first/last non-null positions, look-ahead ``shift(-1)``), near-constant
  output, and output-vs-input magnitude ratio >100x (percent-vs-decimal
  scale hazard);
* percent-like module numeric constants with no explicit decimal conversion
  (``/100``, ``*0.01``, ``*1e-2`` anywhere in the module);
* forbidden-file access scan (checker/reference/property/verdict/paper
  text), and an output-directory delivery audit that removes bytecode
  caches and reports missing/extra files.

Delivery safety
---------------
The module is NEVER imported from the deliverable directory.  It is copied to
a temporary file outside the output directory and loaded with
``sys.dont_write_bytecode = True``, so no ``__pycache__`` or ``*.pyc`` files
can appear next to the submitted module.  If an ``output_dir`` is supplied,
the audit removes any existing bytecode caches there and verifies the
required deliverable files exist.

The function is intentionally conservative: anything it cannot verify with
certainty is reported as a warning, never as a hard error.  ``errors`` mean
the module cannot even be mechanically compliant (syntax/import failure,
missing required function, wrong signature, call exception, missing output
column, non-finite output, missing required deliverable).  Warnings must be
resolved against the task instruction (e.g., a percent-form constant may be
legitimate if converted before use).
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

_SCHEMA_VERSION = 2
_LOOKAHEAD_RE = re.compile(r"shift\s*\(\s*-1\s*\)")
_FORBIDDEN_READ_RE = re.compile(
    r"(paper_text\.md|verdict|checker|property|reference|solution)",
    re.IGNORECASE,
)
_READ_CALL_RE = re.compile(
    r"\b(open|read_csv|read_excel|read_parquet|read_json|read_pickle)\s*\(",
    re.IGNORECASE,
)
_SCALE_RE = re.compile(r"[*/]\s*100(?:\.0)?\b")
# Explicit conversions from percent-form to decimal-form arithmetic.
_DECIMAL_CONVERT_RE = re.compile(
    r"/\s*100(?:\.0)?\b|\*\s*0\.01\b|\*\s*1e-2\b", re.IGNORECASE
)


def _month_ends(periods: int) -> pd.DatetimeIndex:
    try:
        return pd.date_range("2010-01-31", periods=periods, freq="ME")
    except ValueError:  # older pandas without 'ME'
        return pd.date_range("2010-01-31", periods=periods, freq="M")


def _synthetic_df(columns: List[str], periods: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed=0)
    data: Dict[str, Any] = {}
    for col in columns:
        if col.strip().lower() == "date":
            data[col] = _month_ends(periods)
        elif "rf" in col.lower():
            data[col] = rng.normal(0.002, 0.01, periods)
        elif col.lower().startswith(("mkt", "ret", "excess")):
            data[col] = rng.normal(0.01, 0.05, periods)
        else:
            data[col] = rng.normal(0.0, 0.1, periods)
    df = pd.DataFrame(data)
    if "date" in df.columns:
        df = df.sort_values("date").reset_index(drop=True)
    return df


def _top_level_function_sigs(source: str) -> Dict[str, List[str]]:
    """Static AST scan of top-level function names and positional params.

    This mirrors the interface contract (argument names must match input
    column names) without importing the module, so it cannot trigger module
    side effects or bytecode writes.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    sigs: Dict[str, List[str]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            positional = [
                a.arg for a in node.args.args if a.arg not in ("self", "cls")
            ]
            sigs[node.name] = positional
    return sigs


def _collect_module_constants(source: str) -> List[Dict[str, Any]]:
    """Module-level numeric constant assignments, with percent-like flags."""
    found: List[Dict[str, Any]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return found
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                val = node.value.value
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    found.append(
                        {
                            "name": target.id,
                            "value": val,
                            "line": node.lineno,
                            # Percent-form values live roughly in [1, 10000]:
                            # after /100 they become plausible decimal-space
                            # magnitudes (0.01 .. 100).
                            "percent_like": 1.0 <= abs(val) <= 10000.0,
                        }
                    )
    return found


def _audit_source(source: str) -> Dict[str, Any]:
    warnings: List[str] = []
    info: List[str] = []

    try:
        tree = ast.parse(source)
        info.append("parse: valid")
    except SyntaxError as exc:
        return {
            "warnings": [],
            "info": [],
            "syntax_error": f"line {exc.lineno}: {exc.msg}",
        }

    for lineno, line in enumerate(source.splitlines(), 1):
        if _LOOKAHEAD_RE.search(line):
            warnings.append(
                f"line {lineno}: look-ahead shift(-1) detected - verify this is "
                "intended (lag direction should point into the past, shift(+1))"
            )
        if _READ_CALL_RE.search(line) and _FORBIDDEN_READ_RE.search(line):
            warnings.append(
                f"line {lineno}: file access pattern touches forbidden material "
                "(checker/reference/property/verdict/paper_text) - remove it"
            )
        for match in _SCALE_RE.finditer(line):
            info.append(
                f"line {lineno}: explicit scaling expression '{match.group(0)}' "
                "- verify percent/decimal consistency with the instruction"
            )

    percent_consts = _collect_module_constants(source)
    for const in percent_consts:
        if const["percent_like"]:
            warnings.append(
                f"line {const['line']}: module constant {const['name']} = "
                f"{const['value']} is percent/basis-point-like in magnitude - "
                "verify it is converted to the task's declared units (usually "
                "decimal, /100) before being used in arithmetic"
            )
        else:
            info.append(
                f"line {const['line']}: module constant {const['name']} = "
                f"{const['value']}"
            )

    if percent_consts and not _DECIMAL_CONVERT_RE.search(source):
        names = ", ".join(
            f"{c['name']}={c['value']}" for c in percent_consts if c["percent_like"]
        )
        if names:
            warnings.append(
                f"percent-like module constant(s) {names} present but no explicit "
                "decimal conversion (e.g. /100, *0.01, *1e-2) was found anywhere "
                "in the module - if these are percent-form values they will scale "
                "decimal-space outputs by ~100x; divide by 100 before use"
            )
    return {"warnings": warnings, "info": info, "syntax_error": None}


def _load_module_no_bytecode(source: str, module_path: str) -> Any:
    """Load the module from a temp copy with bytecode writing disabled.

    The submitted file itself is never imported, so no ``__pycache__`` or
    ``*.pyc`` can be created in the deliverable directory.
    """
    digest = hashlib.sha256(str(module_path).encode("utf-8")).hexdigest()[:12]
    name = f"_qea_strategy_check_{digest}"
    fd, tmp = tempfile.mkstemp(suffix=".py", prefix="qea_strategy_")
    os.close(fd)
    try:
        Path(tmp).write_text(source, encoding="utf-8")
        old_flag = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec = importlib.util.spec_from_file_location(name, tmp)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot build import spec for {module_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            try:
                spec.loader.exec_module(module)
            finally:
                sys.modules.pop(name, None)
            return module
        finally:
            sys.dont_write_bytecode = old_flag
    finally:
        try:
            Path(tmp).unlink()
        except OSError:
            pass


def _parse_signature(func) -> Dict[str, Any]:
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return {"positional": [], "kind": "unknown"}
    positional = [
        p.name
        for p in sig.parameters.values()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    return {"positional": positional, "kind": "function"}


def _top_level_functions(module) -> Dict[str, Any]:
    funcs: Dict[str, Any] = {}
    for member_name, member in inspect.getmembers(module, inspect.isfunction):
        if getattr(member, "__module__", None) == module.__name__:
            funcs[member_name] = member
    return funcs


def _audit_delivery(
    output_dir: str,
    required_deliverables: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Audit the output directory and remove bytecode caches.

    Bytecode caches are removed automatically (they are never a deliverable).
    Missing required deliverables are errors.  Extra files beyond the required
    set are warnings: some task interfaces legitimately request additional
    artifacts (e.g. a trade log), so extras are the worker's call.
    """
    errors: List[str] = []
    warnings: List[str] = []
    info: List[str] = []
    removed: List[str] = []
    root = Path(output_dir).resolve()

    if not root.exists():
        errors.append(f"output directory not found: {output_dir}")
        return {"errors": errors, "warnings": warnings, "info": info, "files": [], "removed_caches": removed}

    # Remove bytecode caches recursively (never a deliverable).
    if root.is_dir():
        for cache in sorted(root.rglob("__pycache__")):
            try:
                shutil_rmtree(cache)
                removed.append(str(cache.relative_to(root)))
            except OSError as exc:
                warnings.append(f"could not remove bytecode cache {cache}: {exc}")
        for pyc in sorted(root.rglob("*.pyc")):
            try:
                pyc.unlink()
                removed.append(str(pyc.relative_to(root)))
            except OSError as exc:
                warnings.append(f"could not remove bytecode file {pyc}: {exc}")

    files = sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )
    info.append(f"output directory files after cache removal: {files}")

    required = [r for r in (required_deliverables or []) if r]
    if required:
        for req in required:
            req_path = (root / req).resolve()
            if not req_path.exists() or not req_path.is_file():
                errors.append(f"required deliverable missing: {req}")
    if files:
        required_set = set(required)
        extras = [f for f in files if f not in required_set]
        if extras:
            warnings.append(
                f"files beyond required deliverables present: {extras} - keep "
                "only the artifacts the task interface actually requires"
            )
    if removed:
        info.append(f"removed bytecode cache files: {removed}")
    return {
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "files": files,
        "removed_caches": removed,
    }


def shutil_rmtree(path: Path) -> None:
    import shutil

    shutil.rmtree(path)


def validate_strategy_module(
    module_path: str,
    required_functions: Optional[Dict[str, Dict[str, Any]]] = None,
    sample_rows: int = 120,
    output_dir: Optional[str] = None,
    required_deliverables: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Validate a submitted strategy module.

    Args:
        module_path: absolute path to the strategy module (e.g.
            ``/app/output/strategy.py``) or the path used by the harness.
        required_functions: mapping of function name to an interface spec::

            {
              "compute_demeaned_signal": {
                "input_columns": ["date", "mkt", "mkt_rf", "rf"],
                "output_columns": ["is_newsy", "sum_4_newsy",
                                   "expanding_mean", "raw_signal",
                                   "demeaned_signal"]
              }
            }

            A list of plain names (instead of a dict) performs a static
            presence/signature check only.  Single-DataFrame functions whose
            spec has exactly one positional parameter are also executed on
            fixed-seed synthetic data derived from ``input_columns``.
        sample_rows: number of synthetic rows used for runtime checks
            (capped at 400).
        output_dir: optional output directory to audit for delivery
            (bytecode caches removed, required deliverables checked).
        required_deliverables: file names (relative to ``output_dir``) that
            must exist after the module is saved.

    Returns:
        JSON-serializable report with ``ok`` (bool), ``errors``, ``warnings``,
        and ``info``.  ``ok`` is True only when there are no errors; warnings
        must be resolved against the task instruction.
    """
    sample_rows = max(8, min(int(sample_rows), 400))
    errors: List[str] = []
    warnings: List[str] = []
    info: List[str] = []

    path = Path(module_path).resolve()
    if not path.exists():
        errors.append(f"module file not found: {module_path}")
        return _report(module_path, errors, warnings, info)

    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read module: {exc}")
        return _report(module_path, errors, warnings, info)

    ast_audit = _audit_source(source)
    if ast_audit["syntax_error"]:
        errors.append(f"syntax error: {ast_audit['syntax_error']}")
        return _report(module_path, errors, warnings, info)
    warnings.extend(ast_audit["warnings"])
    info.extend(ast_audit["info"])

    static_sigs = _top_level_function_sigs(source)
    info.append(f"static top-level functions: {sorted(static_sigs)}")

    if required_functions:
        if isinstance(required_functions, dict):
            specs = {name: spec for name, spec in required_functions.items()}
        else:
            specs = {name: {} for name in required_functions}
    else:
        specs = {}

    # Static presence/signature checks (always run; no import side effects).
    for name, spec in specs.items():
        if name not in static_sigs:
            errors.append(f"required function missing: {name}")
        elif isinstance(spec, dict) and spec.get("expected_params"):
            expected = list(spec["expected_params"])
            actual = static_sigs[name]
            if expected != actual:
                errors.append(
                    f"function {name} parameter names {actual} do not match "
                    f"expected {expected} - argument names should match input "
                    "column names (or use the _df suffix as instructed)"
                )

    # Runtime synthetic checks (only for single-DataFrame functions).
    try:
        module = _load_module_no_bytecode(source, str(path))
    except Exception as exc:  # noqa: BLE001 - report any import failure
        errors.append(f"module import failed: {type(exc).__name__}: {exc}")
        return _report(module_path, errors, warnings, info)

    funcs = _top_level_functions(module)
    info.append(f"import: ok; top-level functions: {sorted(funcs)}")

    all_input_cols: List[str] = []
    for spec in specs.values():
        if isinstance(spec, dict):
            for col in spec.get("input_columns", []) or []:
                if col not in all_input_cols:
                    all_input_cols.append(col)
    base_cols = all_input_cols or ["date"]
    for extra in ("mkt", "mkt_rf", "rf"):
        if extra not in base_cols:
            base_cols.append(extra)
    synthetic = _synthetic_df(base_cols, sample_rows)

    for name, spec in specs.items():
        if name not in funcs:
            continue  # already reported as missing
        sig = _parse_signature(funcs[name])
        info.append(f"function {name}: positional params {sig['positional']}")
        output_cols = list(spec.get("output_columns", [])) if isinstance(spec, dict) else []
        input_cols = list(spec.get("input_columns", [])) if isinstance(spec, dict) else []
        if not output_cols:
            continue

        positional = [p for p in sig["positional"] if p not in ("data_dir", "data_path")]
        if len(positional) == 1:
            # Chain-aware: run on the accumulated frame, which carries both the
            # declared input columns and every output column produced so far.
            try:
                out = funcs[name](synthetic.copy())
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    f"function {name} raised on synthetic input "
                    f"({type(exc).__name__}: {exc})"
                )
                continue
            if not isinstance(out, pd.DataFrame):
                errors.append(
                    f"function {name} returned {type(out).__name__}, expected DataFrame"
                )
                continue
            missing = [c for c in output_cols if c not in out.columns]
            if missing:
                errors.append(f"function {name} output missing columns: {missing}")
                continue
            for col in output_cols:
                series = pd.to_numeric(out[col], errors="coerce")
                non_null = int(series.notna().sum())
                first_nn = int(series.first_valid_index()) if non_null else None
                last_nn = int(series.last_valid_index()) if non_null else None
                if non_null == 0:
                    errors.append(
                        f"function {name} output column '{col}' is entirely NaN"
                    )
                    continue
                info.append(
                    f"function {name} output '{col}': non-null {non_null}/{len(series)}, "
                    f"first index {first_nn}, last index {last_nn}"
                )
                if last_nn == len(series) - 1 and first_nn == 0:
                    pass  # fully populated column: fine
                elif last_nn is not None and last_nn == len(series) - 1:
                    info.append(
                        f"function {name} output '{col}': leading NaN pattern "
                        "(consistent with a shift(+1)/causal lag)"
                    )
                elif (
                    first_nn is not None
                    and first_nn == 0
                    and last_nn is not None
                    and last_nn < len(series) - 1
                ):
                    warnings.append(
                        f"function {name} output '{col}': trailing NaN at the END of "
                        "the series - a lag shifted the wrong direction (look-ahead) "
                        "or the final value was lost"
                    )
                finite = bool(np.isfinite(series.dropna()).all())
                if not finite:
                    errors.append(f"function {name} output column '{col}' has non-finite values")
                if non_null >= 2 and float(series.std()) < 1e-12:
                    warnings.append(
                        f"function {name} output column '{col}' is (near-)constant - "
                        "check unit scale or construction"
                    )
            if input_cols:
                input_max = 0.0
                for col in input_cols:
                    if col.strip().lower() == "date":
                        continue
                    numeric = pd.to_numeric(synthetic[col], errors="coerce")
                    if numeric.notna().any():
                        input_max = max(input_max, float(numeric.abs().max()))
                out_max = 0.0
                for col in output_cols:
                    numeric = pd.to_numeric(out[col], errors="coerce")
                    if numeric.notna().any():
                        out_max = max(out_max, float(numeric.abs().max()))
                if input_max > 0 and out_max > 0 and out_max / input_max > 100.0:
                    warnings.append(
                        f"function {name}: max |output| ({out_max:.3g}) exceeds max "
                        f"|input| ({input_max:.3g}) by >100x - possible "
                        "percent-vs-decimal unit-scale error"
                    )
            for col in output_cols:
                if col not in synthetic.columns:
                    synthetic[col] = out[col].reset_index(drop=True)
        else:
            info.append(f"function {name}: multi-arg signature - static check only")

    report = _report(module_path, errors, warnings, info)
    if output_dir:
        delivery = _audit_delivery(output_dir, required_deliverables)
        report["delivery"] = delivery
        report["errors"].extend(delivery["errors"])
        report["warnings"].extend(delivery["warnings"])
        report["info"].extend(delivery["info"])
        report["ok"] = not report["errors"]
    return report


def _report(
    module_path: str,
    errors: List[str],
    warnings: List[str],
    info: List[str],
) -> Dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "module_path": module_path,
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "info": info,
    }


def main() -> None:
    """CLI convenience: python -m tools.strategy_validate <module_path> [spec.json]."""
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "errors": ["usage: module_path [spec.json]"]}))
        return
    spec = None
    if len(sys.argv) >= 3:
        spec_path = Path(sys.argv[2])
        if spec_path.exists():
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
    report = validate_strategy_module(sys.argv[1], spec)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
