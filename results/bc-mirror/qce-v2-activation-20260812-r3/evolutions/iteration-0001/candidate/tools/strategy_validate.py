"""Deterministic pre-submission validator for quant strategy modules.

Scope
-----
Audits a worker-submitted ``strategy.py``-style module for mechanical
compliance that is independent of any benchmark answer:

* parse/import health and required top-level function presence;
* synthetic single-DataFrame execution for interface functions whose spec is
  provided (input columns -> required output columns);
* output-column completeness, finite values, and lag/NaN placement audit
  (all-NaN column, first/last non-null positions, look-ahead ``shift(-1)``);
* input-preservation audit when the spec marks the transform as "augment"
  (the instruction says the input DataFrame is augmented with new columns);
* percent-vs-decimal unit-scale hazard scan of module numeric constants and
  scaling expressions (``* 100``, ``/ 100``, percent-like constants used
  without an explicit ``/ 100`` conversion);
* forbidden-file access scan (checker/reference/property/verdict/paper text).

It never inspects evaluator, reference, property, verdict, or held-out files
and encodes no task-specific numeric answer.  Synthetic data uses a fixed
seed so results are reproducible.

The function is intentionally conservative: anything it cannot verify with
certainty is reported as a warning, never as a hard error.  ``errors`` mean
the module cannot even be mechanically compliant (syntax/import failure,
missing required function, call exception, missing output column,
non-finite output, dropped input column under an explicit augment contract).
Warnings must be resolved against the task instruction (e.g., a percent-form
constant may be legitimate if converted before use).
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

_SCHEMA_VERSION = 2
_LOOKAHEAD_RE = re.compile(r"shift\s*\(\s*-1\s*\)|\.shift\(-1\)")
_FORBIDDEN_READ_RE = re.compile(
    r"(paper_text\.md|verdict|checker|property|reference)",
    re.IGNORECASE,
)
_READ_CALL_RE = re.compile(
    r"\b(open|read_csv|read_excel|read_parquet|read_json|read_pickle)\s*\(",
    re.IGNORECASE,
)
_SCALE_RE = re.compile(r"([*/])\s*100(?:\.0)?\b")
_SCALE_CONVERSION_RE = re.compile(r"[/*]\s*(100|0\.01)\b")


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


def _percent_like(val: float) -> bool:
    """A non-integer magnitude in 0.05..10000 is likely a raw percent anchor.

    Small integers such as 12 (months), 60, 22, or 252 (annualization) are
    counts/factors, not percent quotes; decimal anchors from papers (0.75,
    4.86, 5.34) are non-integer and sit in this range.
    """
    return 0.05 <= abs(val) <= 10000.0 and not float(val).is_integer()


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
                            "percent_like": _percent_like(float(val)),
                        }
                    )
    return found


def _audit_scaling_constants(source: str) -> List[str]:
    """Warn when a percent-like constant is used without any /100 conversion.

    A percent-form paper anchor (e.g. 5.34 meaning 5.34%) must be divided by
    100 before arithmetic on decimal returns.  If every expression that
    references the constant contains an explicit ``/ 100`` or ``* 0.01``, the
    module is treating it correctly; otherwise flag it for review.
    """
    warnings: List[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return warnings
    lines = source.splitlines()
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Name) and isinstance(node.value, ast.Constant)):
            continue
        val = node.value.value
        if not (isinstance(val, (int, float)) and not isinstance(val, bool)):
            continue
        if not _percent_like(float(val)):
            continue
        name = target.id
        name_re = re.compile(r"\b" + re.escape(name) + r"\b")
        use_lines = [
            (lineno, line)
            for lineno, line in enumerate(lines, 1)
            if lineno != node.lineno and name_re.search(line)
        ]
        if not use_lines:
            continue
        converted = any(_SCALE_CONVERSION_RE.search(line) for _, line in use_lines)
        if converted:
            continue
        warnings.append(
            f"line {node.lineno}: percent-form module constant {name} = {val} "
            f"is referenced in {len(use_lines)} expression(s) with no explicit "
            "/100 (or *0.01) conversion on those lines - verify it is not "
            "applied in raw percent form to decimal data"
        )
    return warnings


def _audit_source(source: str, module_path: str) -> Dict[str, List[str]]:
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

    for const in _collect_module_constants(source):
        if const["percent_like"]:
            warnings.append(
                f"line {const['line']}: module constant {const['name']} = "
                f"{const['value']} is percent-like in magnitude - verify it is "
                "converted to the task's declared units (usually decimal, /100) "
                "before being used in arithmetic"
            )
        else:
            info.append(
                f"line {const['line']}: module constant {const['name']} = "
                f"{const['value']}"
            )
    warnings.extend(_audit_scaling_constants(source))
    return {"warnings": warnings, "info": info, "syntax_error": None}


def _load_module(module_path: str) -> Any:
    path = Path(module_path).resolve()
    name = "_qea_strategy_smoke_%d" % (abs(hash(str(path))) % (10**6))
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _top_level_functions(module) -> Dict[str, Any]:
    funcs: Dict[str, Any] = {}
    for member_name, member in inspect.getmembers(module, inspect.isfunction):
        if getattr(member, "__module__", None) == module.__name__:
            funcs[member_name] = member
    return funcs


def validate_strategy_module(
    module_path: str,
    required_functions: Optional[Dict[str, Dict[str, Any]]] = None,
    sample_rows: int = 120,
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
                                   "demeaned_signal"],
                "augment": true
              }
            }

            A list of plain names (instead of a dict) performs a static
            presence check only.  Single-DataFrame functions whose spec has
            exactly one positional parameter are also executed on synthetic
            data derived from ``input_columns``.  ``augment: true`` (the
            instruction says the input DataFrame is *augmented* with the new
            columns) additionally requires every input column to survive in
            the output.
        sample_rows: number of synthetic rows used for runtime checks
            (capped at 400).

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

    ast_audit = _audit_source(source, str(path))
    if ast_audit["syntax_error"]:
        errors.append(f"syntax error: {ast_audit['syntax_error']}")
        return _report(module_path, errors, warnings, info)
    warnings.extend(ast_audit["warnings"])
    info.extend(ast_audit["info"])

    try:
        module = _load_module(str(path))
    except Exception as exc:  # noqa: BLE001 - report any import failure
        errors.append(f"module import failed: {type(exc).__name__}: {exc}")
        return _report(module_path, errors, warnings, info)

    funcs = _top_level_functions(module)
    info.append(f"import: ok; top-level functions: {sorted(funcs)}")

    if required_functions:
        if isinstance(required_functions, dict):
            specs = {name: spec for name, spec in required_functions.items()}
        else:
            specs = {name: {} for name in required_functions}
    else:
        specs = {}

    for name, spec in specs.items():
        if name not in funcs:
            errors.append(f"required function missing: {name}")
            continue
        sig = _parse_signature(funcs[name])
        info.append(f"function {name}: positional params {sig['positional']}")
        output_cols = list(spec.get("output_columns", [])) if isinstance(spec, dict) else []
        input_cols = list(spec.get("input_columns", [])) if isinstance(spec, dict) else []
        augment = bool(spec.get("augment", False)) if isinstance(spec, dict) else False
        if not output_cols:
            continue

        positional = [p for p in sig["positional"] if p not in ("data_dir", "data_path")]
        if len(positional) == 1:
            synthetic = _synthetic_df(input_cols or ["date"], sample_rows)
            try:
                out = funcs[name](synthetic.copy())
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    f"function {name} raised on synthetic input "
                    f"({type(exc).__name__}: {exc})"
                )
                continue
            if not isinstance(out, pd.DataFrame):
                errors.append(f"function {name} returned {type(out).__name__}, expected DataFrame")
                continue
            missing = [c for c in output_cols if c not in out.columns]
            if missing:
                errors.append(f"function {name} output missing columns: {missing}")
                continue
            if augment:
                dropped = [c for c in input_cols if c not in out.columns]
                if dropped:
                    errors.append(
                        f"function {name} dropped required input columns under "
                        f"an augment contract: {dropped}"
                    )
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
                if last_nn is not None and last_nn == len(series) - 1:
                    if first_nn == 0:
                        pass  # fully populated column: fine
                    else:
                        info.append(
                            f"function {name} output '{col}': leading NaN pattern "
                            "(consistent with a shift(+1)/causal lag)"
                        )
                elif first_nn is not None and first_nn == 0 and last_nn is not None and last_nn < len(series) - 1:
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
        else:
            info.append(f"function {name}: multi-arg signature - static check only")

    return _report(module_path, errors, warnings, info)


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
