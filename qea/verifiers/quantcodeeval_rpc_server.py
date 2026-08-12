#!/usr/bin/env python3
"""Run an untrusted QuantCodeEval strategy behind bounded JSON RPC."""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from qea.verifiers.quantcodeeval_rpc import decode_value, encode_value


_MAX_BYTES = 32 * 1024 * 1024


def _load(path: Path):
    spec = importlib.util.spec_from_file_location("candidate_strategy", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot create candidate module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    old_argv = sys.argv
    sys.argv = [str(path), "--data-dir", "/candidate/data"]
    try:
        spec.loader.exec_module(module)
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv
    return module


def _functions(module) -> dict[str, list[dict[str, object]]]:
    output: dict[str, list[dict[str, object]]] = {}
    for name, value in vars(module).items():
        if name.startswith("_") or not inspect.isfunction(value):
            continue
        rows = []
        for parameter in inspect.signature(value).parameters.values():
            rows.append({
                "name": parameter.name,
                "kind": parameter.kind.name,
                "has_default": parameter.default is not inspect.Parameter.empty,
            })
        output[name] = rows
    return output


def _side_effects(strategy_path: Path) -> dict[str, object]:
    path = strategy_path.parent / "trade_log.json"
    if not path.exists():
        return {}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("unsafe trade_log.json side effect")
    payload = json.loads(path.read_text())
    return {"trade_log.json": payload}


class Handler(BaseHTTPRequestHandler):
    module = None
    strategy_path = None

    def log_message(self, format, *args):  # noqa: A003
        return

    def do_POST(self):  # noqa: N802
        if self.path != "/rpc":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if length < 0 or length > _MAX_BYTES:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("request must be an object")
            operation = payload.get("operation")
            if operation == "describe":
                result = {"ok": True, "functions": _functions(self.module)}
            elif operation == "call":
                name = payload.get("function")
                if not isinstance(name, str) or name.startswith("_"):
                    raise ValueError("invalid function name")
                function = getattr(self.module, name, None)
                if not inspect.isfunction(function):
                    raise ValueError("function is not exported")
                args = decode_value(payload.get("args"))
                kwargs = decode_value(payload.get("kwargs"))
                if not isinstance(args, tuple) or not isinstance(kwargs, dict):
                    raise ValueError("invalid call arguments")
                result = {
                    "ok": True,
                    "value": encode_value(function(*args, **kwargs)),
                    "files": _side_effects(self.strategy_path),
                }
            else:
                raise ValueError("invalid operation")
        except Exception as exc:  # noqa: BLE001 - untrusted strategy boundary.
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:4096]}
        raw = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(raw) > _MAX_BYTES:
            raw = json.dumps({"ok": False, "error": "response exceeds byte limit"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", type=Path, default=Path("/candidate/strategy.py"))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    Handler.strategy_path = args.strategy.resolve()
    Handler.module = _load(Handler.strategy_path)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
