"""Safe JSON RPC codec and client proxy for isolated strategy execution.

The trusted checker imports this client, while untrusted ``strategy.py`` runs
in a separate container that has no checker, expected-value, or golden files.
Only a bounded, explicitly tagged JSON value language crosses the boundary.
"""

from __future__ import annotations

import inspect
import io
import json
import math
import os
import time
import urllib.request
from types import ModuleType
from typing import Any
from pathlib import Path

import numpy as np
import pandas as pd


_MAX_RPC_BYTES = 32 * 1024 * 1024


class QuantCodeEvalRPCError(RuntimeError):
    """The isolated strategy service returned an unsafe or invalid response."""


def encode_value(value: Any) -> Any:
    """Encode supported numerical/pandas values without Python object loading."""

    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if math.isnan(number):
            return {"__qce_type__": "float", "value": "nan"}
        if math.isinf(number):
            return {"__qce_type__": "float", "value": "inf" if number > 0 else "-inf"}
        return number
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, pd.DataFrame):
        return {
            "__qce_type__": "dataframe",
            "table": value.to_json(
                orient="table", date_format="iso", double_precision=15, index=True
            ),
            "attrs": encode_value(dict(value.attrs)),
        }
    if isinstance(value, pd.Series):
        return {
            "__qce_type__": "series",
            "name": encode_value(value.name),
            "frame": encode_value(value.to_frame(name="__qce_series_value__")),
        }
    if isinstance(value, np.ndarray):
        if value.dtype.kind not in "biufcMmOSU":
            raise QuantCodeEvalRPCError(f"unsupported ndarray dtype {value.dtype}")
        return {
            "__qce_type__": "ndarray",
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "values": encode_value(value.tolist()),
        }
    if isinstance(value, tuple):
        return {"__qce_type__": "tuple", "items": [encode_value(item) for item in value]}
    if isinstance(value, list):
        return [encode_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise QuantCodeEvalRPCError("only string-keyed mappings are supported")
        return {key: encode_value(item) for key, item in value.items()}
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return {"__qce_type__": "timestamp", "value": str(value)}
    raise QuantCodeEvalRPCError(f"unsupported RPC value {type(value).__name__}")


def decode_value(value: Any) -> Any:
    """Decode only values produced by :func:`encode_value`."""

    if value is None or isinstance(value, (bool, str, int, float)):
        return value
    if isinstance(value, list):
        return [decode_value(item) for item in value]
    if not isinstance(value, dict):
        raise QuantCodeEvalRPCError("invalid RPC JSON value")
    kind = value.get("__qce_type__")
    if kind is None:
        return {str(key): decode_value(item) for key, item in value.items()}
    if kind == "float":
        mapping = {"nan": float("nan"), "inf": float("inf"), "-inf": float("-inf")}
        if value.get("value") not in mapping:
            raise QuantCodeEvalRPCError("invalid special float")
        return mapping[value["value"]]
    if kind == "timestamp":
        return pd.Timestamp(value.get("value"))
    if kind == "tuple":
        items = value.get("items")
        if not isinstance(items, list):
            raise QuantCodeEvalRPCError("invalid tuple")
        return tuple(decode_value(item) for item in items)
    if kind == "dataframe":
        table = value.get("table")
        if not isinstance(table, str) or len(table.encode("utf-8")) > _MAX_RPC_BYTES:
            raise QuantCodeEvalRPCError("invalid dataframe table")
        frame = pd.read_json(io.StringIO(table), orient="table")
        attrs = decode_value(value.get("attrs", {}))
        if not isinstance(attrs, dict):
            raise QuantCodeEvalRPCError("invalid dataframe attrs")
        frame.attrs.update(attrs)
        return frame
    if kind == "series":
        frame = decode_value(value.get("frame"))
        if not isinstance(frame, pd.DataFrame) or list(frame.columns) != ["__qce_series_value__"]:
            raise QuantCodeEvalRPCError("invalid series frame")
        series = frame.iloc[:, 0]
        series.name = decode_value(value.get("name"))
        return series
    if kind == "ndarray":
        dtype = value.get("dtype")
        shape = value.get("shape")
        if not isinstance(dtype, str) or not isinstance(shape, list):
            raise QuantCodeEvalRPCError("invalid ndarray descriptor")
        array = np.asarray(decode_value(value.get("values")), dtype=np.dtype(dtype))
        if array.size > 10_000_000:
            raise QuantCodeEvalRPCError("ndarray exceeds element limit")
        return array.reshape(tuple(int(item) for item in shape))
    raise QuantCodeEvalRPCError(f"unknown RPC tag {kind!r}")


def _rpc(payload: dict[str, Any]) -> dict[str, Any]:
    url = os.environ.get("QEA_STRATEGY_RPC_URL", "")
    if not url.startswith("http://") or not url.endswith("/rpc"):
        raise QuantCodeEvalRPCError("isolated strategy RPC URL is missing")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(raw) > _MAX_RPC_BYTES:
        raise QuantCodeEvalRPCError("RPC request exceeds byte limit")
    request = urllib.request.Request(
        url,
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_error: Exception | None = None
    body: bytes | None = None
    for attempt in range(30):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read(_MAX_RPC_BYTES + 1)
            break
        except Exception as exc:  # noqa: BLE001 - normalized trusted boundary.
            last_error = exc
            if attempt < 29:
                time.sleep(0.1)
    if body is None:
        assert last_error is not None
        raise QuantCodeEvalRPCError(
            f"strategy RPC failed: {type(last_error).__name__}: {last_error}"
        ) from last_error
    if len(body) > _MAX_RPC_BYTES:
        raise QuantCodeEvalRPCError("RPC response exceeds byte limit")
    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise QuantCodeEvalRPCError("strategy RPC returned invalid JSON") from exc
    if not isinstance(result, dict) or set(result) - {
        "ok", "value", "error", "functions", "files"
    }:
        raise QuantCodeEvalRPCError("strategy RPC returned invalid envelope")
    if result.get("ok") is not True:
        raise QuantCodeEvalRPCError(str(result.get("error", "strategy call failed"))[:4096])
    return result


def _rewrite_public_paths(value: Any) -> Any:
    if isinstance(value, str):
        if value == "/tests/data":
            return "/candidate/data"
        if value.startswith("/tests/data/"):
            return "/candidate/data/" + value.removeprefix("/tests/data/")
        return value
    if isinstance(value, tuple):
        return tuple(_rewrite_public_paths(item) for item in value)
    if isinstance(value, list):
        return [_rewrite_public_paths(item) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_public_paths(item) for key, item in value.items()}
    return value


def _sync_side_effects(result: dict[str, Any]) -> None:
    files = result.get("files", {})
    if not isinstance(files, dict) or set(files) - {"trade_log.json"}:
        raise QuantCodeEvalRPCError("invalid strategy side-effect set")
    if "trade_log.json" not in files:
        return
    payload = files["trade_log.json"]
    encoded = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
    if len(encoded) > 8 * 1024 * 1024:
        raise QuantCodeEvalRPCError("strategy trade log exceeds byte limit")
    output_root = Path(os.environ.get("QEA_STRATEGY_SIDE_EFFECT_DIR", "/app/output"))
    if output_root.as_posix() != "/app/output":
        raise QuantCodeEvalRPCError("invalid strategy side-effect directory")
    (output_root / "trade_log.json").write_bytes(encoded + b"\n")


class RemoteFunction:
    def __init__(self, name: str, parameters: list[dict[str, Any]]) -> None:
        self.__name__ = name
        built: list[inspect.Parameter] = []
        kinds = {
            name: kind for name, kind in inspect._ParameterKind.__members__.items()
        }
        for row in parameters:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str):
                raise QuantCodeEvalRPCError("invalid remote signature")
            kind_name = row.get("kind")
            if kind_name not in kinds:
                raise QuantCodeEvalRPCError("invalid remote parameter kind")
            default = None if row.get("has_default") else inspect.Parameter.empty
            built.append(inspect.Parameter(row["name"], kinds[kind_name], default=default))
        self.__signature__ = inspect.Signature(built)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        args = _rewrite_public_paths(args)
        kwargs = _rewrite_public_paths(kwargs)
        result = _rpc({
            "operation": "call",
            "function": self.__name__,
            "args": encode_value(args),
            "kwargs": encode_value(kwargs),
        })
        _sync_side_effects(result)
        return decode_value(result.get("value"))


class RemoteModule(ModuleType):
    def __init__(self, module_name: str = "isolated_strategy") -> None:
        super().__init__(module_name)
        response = _rpc({"operation": "describe"})
        functions = response.get("functions")
        if not isinstance(functions, dict):
            raise QuantCodeEvalRPCError("strategy description has no functions")
        self._functions = {
            name: RemoteFunction(name, rows)
            for name, rows in functions.items()
            if isinstance(name, str) and isinstance(rows, list)
        }

    def __getattr__(self, name: str) -> Any:
        try:
            return self._functions[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def load_module(code_path: str, module_name: str = "isolated_strategy") -> ModuleType:
    del code_path
    return RemoteModule(module_name)


def get_function(
    module: ModuleType,
    func_name: str,
    aliases: list[str] | None = None,
):
    function = getattr(module, func_name, None)
    if callable(function):
        return function
    for alias in aliases or []:
        function = getattr(module, alias, None)
        if callable(function):
            return function
    return None


def get_si_function(code_path: str, function_name: str):
    try:
        function = get_function(load_module(code_path), function_name)
    except Exception as exc:  # noqa: BLE001 - checker expects an error string.
        return None, f"Failed to connect to isolated strategy: {exc}"
    if function is None:
        return None, f"required task function `{function_name}` not found in module"
    return function, None
