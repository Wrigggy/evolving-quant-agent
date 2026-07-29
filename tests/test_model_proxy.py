import http.client
import json
import os
import socket
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


REAL_TOKEN = "sk-fixture-real-token-never-leak"


class UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _respond(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.captured.append(
            {
                "method": self.command,
                "path": self.path,
                "headers": {key.lower(): value for key, value in self.headers.items()},
                "body": body,
            }
        )
        if self.path.endswith("/echo-token"):
            payload = f'{{"authorization":"Bearer {REAL_TOKEN}"}}'.encode()
        elif self.path.endswith("/large"):
            payload = b"x" * 128
        else:
            payload = json.dumps(
                {"ok": True, "chunks": ["one", "two", "three"]},
                sort_keys=True,
            ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Connection", "keep-alive, X-Upstream-Remove")
        self.send_header("X-Upstream-Remove", "secret-hop")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        midpoint = len(payload) // 2
        self.wfile.write(payload[:midpoint])
        self.wfile.flush()
        self.wfile.write(payload[midpoint:])

    do_GET = _respond
    do_POST = _respond

    def log_message(self, format, *args):
        return


def _start_upstream():
    server = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
    server.captured = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _token_file(tmp_path):
    path = tmp_path / "model-token"
    path.write_text(REAL_TOKEN + "\n")
    path.chmod(0o600)
    return path


def _start_proxy(tmp_path, upstream, **changes):
    from qea.model_proxy import ModelProxyConfig, create_proxy_server

    values = {
        "listen_host": "127.0.0.1",
        "listen_port": 0,
        "upstream_base_url": (
            f"http://127.0.0.1:{upstream.server_address[1]}/api/v1"
        ),
        "allowed_path_prefix": "/v1",
        "token_file": _token_file(tmp_path),
        "max_request_bytes": 64,
        "max_response_bytes": 256,
        "connect_timeout_seconds": 2.0,
        "read_timeout_seconds": 2.0,
    }
    values.update(changes)
    server = create_proxy_server(ModelProxyConfig(**values))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _request(proxy, method="POST", path="/v1/chat/completions", body=b"{}", headers=None):
    connection = http.client.HTTPConnection(
        "127.0.0.1", proxy.server_address[1], timeout=3
    )
    request_headers = {
        "Authorization": "Bearer qea-proxy-placeholder",
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    }
    request_headers.update(headers or {})
    connection.request(method, path, body=body, headers=request_headers)
    response = connection.getresponse()
    payload = response.read()
    result = response.status, dict(response.getheaders()), payload
    connection.close()
    return result


def _stop(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
    assert not thread.is_alive()


def test_proxy_routes_fixed_path_injects_token_and_strips_hop_headers(tmp_path):
    upstream, upstream_thread = _start_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    try:
        status, response_headers, payload = _request(
            proxy,
            body=b'{"model":"fixture"}',
            headers={
                "Connection": "keep-alive, X-Remove-Me",
                "X-Remove-Me": "do-not-forward",
                "Proxy-Authorization": "also-do-not-forward",
            },
        )
        assert status == 200
        assert json.loads(payload) == {"chunks": ["one", "two", "three"], "ok": True}
        captured = upstream.captured[-1]
        assert captured["method"] == "POST"
        assert captured["path"] == "/api/v1/chat/completions"
        assert captured["headers"]["authorization"] == f"Bearer {REAL_TOKEN}"
        assert captured["headers"]["host"] == f"127.0.0.1:{upstream.server_address[1]}"
        assert "proxy-authorization" not in captured["headers"]
        assert "x-remove-me" not in captured["headers"]
        assert "connection" not in captured["headers"]
        assert "connection" not in {name.lower() for name in response_headers}
        assert "x-upstream-remove" not in {
            name.lower() for name in response_headers
        }
        assert REAL_TOKEN.encode() not in payload
    finally:
        _stop(proxy, proxy_thread)
        _stop(upstream, upstream_thread)


@pytest.mark.parametrize(
    ("method", "path", "headers", "expected"),
    [
        ("POST", "http://evil.example/v1/chat/completions", {}, 400),
        ("POST", "/other/chat/completions", {}, 404),
        ("CONNECT", "evil.example:443", {}, 405),
        ("POST", "/v1/../admin", {}, 400),
        ("POST", "/v1/chat/completions", {"Upgrade": "websocket"}, 400),
    ],
)
def test_proxy_rejects_alternate_routes_tunnels_and_upgrades(
    tmp_path, method, path, headers, expected
):
    upstream, upstream_thread = _start_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    try:
        status, _, payload = _request(
            proxy, method=method, path=path, headers=headers
        )
        assert status == expected
        assert REAL_TOKEN.encode() not in payload
        assert upstream.captured == []
    finally:
        _stop(proxy, proxy_thread)
        _stop(upstream, upstream_thread)


def test_proxy_bounds_request_and_response_bodies(tmp_path):
    upstream, upstream_thread = _start_upstream()
    proxy, proxy_thread = _start_proxy(
        tmp_path,
        upstream,
        max_request_bytes=8,
        max_response_bytes=64,
    )
    try:
        status, _, payload = _request(proxy, body=b"x" * 9)
        assert status == 413
        assert upstream.captured == []
        status, _, payload = _request(proxy, method="GET", path="/v1/large", body=b"")
        assert status == 502
        assert b"response_limit" in payload
        assert REAL_TOKEN.encode() not in payload
    finally:
        _stop(proxy, proxy_thread)
        _stop(upstream, upstream_thread)


def test_proxy_blocks_an_upstream_response_that_echoes_the_real_token(tmp_path):
    upstream, upstream_thread = _start_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    try:
        status, _, payload = _request(
            proxy, method="GET", path="/v1/echo-token", body=b""
        )
        assert status == 502
        assert b"credential_echo" in payload
        assert REAL_TOKEN.encode() not in payload
    finally:
        _stop(proxy, proxy_thread)
        _stop(upstream, upstream_thread)


def test_proxy_sanitizes_upstream_failures_and_emits_no_access_log(tmp_path, capsys):
    unused = socket.socket()
    unused.bind(("127.0.0.1", 0))
    port = unused.getsockname()[1]
    unused.close()
    upstream = SimpleServerAddress(("127.0.0.1", port))
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    try:
        status, _, payload = _request(proxy)
        assert status == 502
        assert b"upstream_failure" in payload
        assert REAL_TOKEN.encode() not in payload
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""
        assert REAL_TOKEN not in captured.out + captured.err
    finally:
        _stop(proxy, proxy_thread)


class SimpleServerAddress:
    def __init__(self, address):
        self.server_address = address


@pytest.mark.parametrize("mode", [0o644, 0o400, 0o666])
def test_token_file_requires_exact_mode_600(tmp_path, mode):
    from qea.model_proxy import ModelProxyConfig, ModelProxyError

    token = _token_file(tmp_path)
    token.chmod(mode)
    with pytest.raises(ModelProxyError, match="mode 600"):
        ModelProxyConfig(
            listen_host="127.0.0.1",
            listen_port=0,
            upstream_base_url="https://model.example/v1",
            allowed_path_prefix="/v1",
            token_file=token,
        )


def test_token_file_rejects_symlink_and_oversized_value(tmp_path):
    from qea.model_proxy import ModelProxyConfig, ModelProxyError

    real = _token_file(tmp_path)
    link = tmp_path / "linked-token"
    link.symlink_to(real)
    with pytest.raises(ModelProxyError, match="regular non-symlink"):
        ModelProxyConfig(
            listen_host="127.0.0.1",
            listen_port=0,
            upstream_base_url="https://model.example/v1",
            allowed_path_prefix="/v1",
            token_file=link,
        )
    real.write_bytes(b"x" * 16_385)
    real.chmod(0o600)
    with pytest.raises(ModelProxyError, match="token file is too large"):
        ModelProxyConfig(
            listen_host="127.0.0.1",
            listen_port=0,
            upstream_base_url="https://model.example/v1",
            allowed_path_prefix="/v1",
            token_file=real,
        )


def test_proxy_sandbox_plan_contains_no_token_and_uses_secret_tmpfs(tmp_path):
    from qea.model_proxy import build_model_proxy_sandbox_plan

    plan = build_model_proxy_sandbox_plan(
        run_id="run-001",
        attempt_id="proxy-001",
        image_ref="sha256:" + "c" * 64,
        upstream_base_url="https://openrouter.ai/api/v1",
        allowed_path_prefix="/v1",
        listen_port=8080,
        cpu_count=1,
        memory_mb=512,
        pids_limit=64,
        timeout_seconds=3600,
    )
    encoded = json.dumps(plan.public_payload(), sort_keys=True)
    assert plan.spec.role == "proxy"
    assert plan.spec.network_policy == "proxy-outbound"
    assert dict(plan.spec.environment) == {}
    assert plan.spec.writable_tmpfs_mb["/run/qea-secrets"] == 1
    assert plan.token_path == "/run/qea-secrets/model-token"
    assert "--token-file" in plan.start_argv
    assert REAL_TOKEN not in encoded
    assert REAL_TOKEN not in " ".join(plan.start_argv)


def test_proxy_sandbox_plan_rejects_origin_without_absolute_path():
    from qea.model_proxy import ModelProxyError, build_model_proxy_sandbox_plan

    with pytest.raises(ModelProxyError, match="absolute path"):
        build_model_proxy_sandbox_plan(
            run_id="run-origin-root",
            attempt_id="proxy-origin-root",
            image_ref="sha256:" + "c" * 64,
            upstream_base_url="https://example.com",
            allowed_path_prefix="/v1",
            listen_port=8080,
            cpu_count=1,
            memory_mb=512,
            pids_limit=64,
            timeout_seconds=300,
        )


def test_proxy_controller_persists_before_start_and_uploads_token_last(tmp_path):
    from qea.model_proxy import (
        build_model_proxy_sandbox_plan,
        start_model_proxy_sandbox,
    )
    from qea.sandbox_backend import KillResult, SandboxHandle

    plan = build_model_proxy_sandbox_plan(
        run_id="run-001",
        attempt_id="proxy-001",
        image_ref="sha256:" + "c" * 64,
        upstream_base_url="https://openrouter.ai/api/v1",
        allowed_path_prefix="/v1",
        listen_port=8080,
        cpu_count=1,
        memory_mb=512,
        pids_limit=64,
        timeout_seconds=3600,
    )
    lifecycle = tmp_path / "proxy-sandbox-lifecycle-v2.json"

    class Backend:
        backend_name = "fake"

        def __init__(self):
            self.events = []

        def create(self, spec):
            self.events.append("create")
            return SandboxHandle(
                backend="fake",
                native_id="proxy-native-id",
                immutable_image_ref=spec.image_ref,
                spec_sha256=spec.spec_sha256,
            )

        def start(self, handle):
            self.events.append(f"start:lifecycle={lifecycle.is_file()}")

        def put_bytes(self, handle, path, payload):
            self.events.append(("upload", path, payload))

        def kill(self, native_id):
            self.events.append(("kill", native_id))
            return KillResult(native_id=native_id, outcome="killed")

    backend = Backend()
    handle = start_model_proxy_sandbox(
        backend=backend,
        plan=plan,
        token=REAL_TOKEN.encode(),
        lifecycle_path=lifecycle,
        clock=lambda: datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert handle.native_id == "proxy-native-id"
    assert backend.events[0:2] == ["create", "start:lifecycle=True"]
    assert backend.events[2][0:2] == (
        "upload",
        "/run/qea-secrets/proxy-config.json",
    )
    assert backend.events[3] == (
        "upload",
        "/run/qea-secrets/model-token",
        REAL_TOKEN.encode(),
    )
    assert REAL_TOKEN not in lifecycle.read_text()


def test_recursive_secret_scan_checks_files_and_memory_surfaces(tmp_path):
    from qea.model_proxy import ModelProxyError, scan_secret_exposure

    clean_root = tmp_path / "clean"
    clean_root.mkdir()
    (clean_root / "inspect.json").write_text('{"Env":["LLM_API_KEY=qea-proxy-placeholder"]}')
    report = scan_secret_exposure(
        REAL_TOKEN.encode(),
        {
            "worker-filesystem": clean_root,
            "worker-log": b"request completed",
            "proxy-argv": "--token-file /run/qea-secrets/model-token",
        },
    )
    assert report.scanned_surfaces == 3
    assert report.scanned_files == 1
    assert report.exposed_surfaces == ()

    (clean_root / "leak.txt").write_text(f"Bearer {REAL_TOKEN}")
    with pytest.raises(ModelProxyError, match="worker-filesystem/leak.txt") as raised:
        scan_secret_exposure(REAL_TOKEN.encode(), {"worker-filesystem": clean_root})
    assert REAL_TOKEN not in str(raised.value)


def test_cli_accepts_token_file_only_and_graceful_shutdown_joins(tmp_path):
    from scripts.run_qea_model_proxy import build_parser

    parser = build_parser()
    actions = {option for action in parser._actions for option in action.option_strings}
    assert "--token-file" in actions
    assert "--token" not in actions
    assert "--api-key" not in actions

    upstream, upstream_thread = _start_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    _stop(proxy, proxy_thread)
    _stop(upstream, upstream_thread)
    assert not proxy_thread.is_alive()
