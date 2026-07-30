import hashlib
import http.client
import json
import os
import signal
import socket
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

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
                {
                    "ok": True,
                    "chunks": ["one", "two", "three"],
                    "usage": {
                        "prompt_tokens": 11,
                        "completion_tokens": 7,
                        "total_tokens": 18,
                        "cost": 0.00125,
                    },
                },
                sort_keys=True,
            ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header(
            "X-Request-Id",
            (
                f"provider-{REAL_TOKEN}"
                if self.path.endswith("/echo-token-header")
                else "provider-request-fixture-001"
            ),
        )
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
        "allowed_model": "fixture",
        "token_file": _token_file(tmp_path),
        "audit_file": tmp_path / "proxy-audit.jsonl",
        "max_request_bytes": 512,
        "max_response_bytes": 256,
        "connect_timeout_seconds": 2.0,
        "read_timeout_seconds": 2.0,
    }
    values.update(changes)
    server = create_proxy_server(ModelProxyConfig(**values))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _request(
    proxy,
    method="POST",
    path="/v1/chat/completions",
    body=b'{"model":"fixture"}',
    headers=None,
):
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


def _finalize(proxy):
    connection = http.client.HTTPConnection(
        "127.0.0.1", proxy.server_address[1], timeout=3
    )
    connection.request(
        "POST",
        "/__qea_private/finalize",
        body=b"",
        headers={"Content-Length": "0"},
    )
    response = connection.getresponse()
    payload = response.read()
    result = response.status, payload
    connection.close()
    return result


def _stop(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
    assert not thread.is_alive()


def _read_audit(tmp_path):
    path = tmp_path / "proxy-audit.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def _start_disconnect_upstream():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    captured = []

    def receive_then_disconnect():
        connection, _ = listener.accept()
        with connection:
            payload = b""
            while b"\r\n\r\n" not in payload:
                payload += connection.recv(4096)
            headers, body = payload.split(b"\r\n\r\n", 1)
            length = 0
            for line in headers.split(b"\r\n")[1:]:
                name, value = line.split(b":", 1)
                if name.lower() == b"content-length":
                    length = int(value.strip())
            while len(body) < length:
                body += connection.recv(4096)
            captured.append(headers + b"\r\n\r\n" + body)
        listener.close()

    thread = threading.Thread(target=receive_then_disconnect, daemon=True)
    thread.start()
    return SimpleServerAddress(listener.getsockname()), captured, thread


def _start_short_body_upstream():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    captured = []

    def receive_then_truncate_response():
        connection, _ = listener.accept()
        with connection:
            payload = b""
            while b"\r\n\r\n" not in payload:
                payload += connection.recv(4096)
            headers, body = payload.split(b"\r\n\r\n", 1)
            length = 0
            for line in headers.split(b"\r\n")[1:]:
                name, value = line.split(b":", 1)
                if name.lower() == b"content-length":
                    length = int(value.strip())
            while len(body) < length:
                body += connection.recv(4096)
            captured.append(headers + b"\r\n\r\n" + body)
            connection.sendall(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 64\r\n"
                b"Connection: close\r\n\r\n"
                b'{"truncated":true}'
            )
        listener.close()

    thread = threading.Thread(target=receive_then_truncate_response, daemon=True)
    thread.start()
    return SimpleServerAddress(listener.getsockname()), captured, thread


class BlockingUpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.captured.append(body)
        self.server.request_started.set()
        assert self.server.release_response.wait(timeout=3)
        payload = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        return


def _start_blocking_upstream():
    server = ThreadingHTTPServer(("127.0.0.1", 0), BlockingUpstreamHandler)
    server.captured = []
    server.request_started = threading.Event()
    server.release_response = threading.Event()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


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
        assert json.loads(payload) == {
            "chunks": ["one", "two", "three"],
            "ok": True,
            "usage": {
                "completion_tokens": 7,
                "cost": 0.00125,
                "prompt_tokens": 11,
                "total_tokens": 18,
            },
        }
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
    ("body", "expected_code"),
    [
        (b"{}", "model_required"),
        (b'{"model":"other"}', "model_not_allowed"),
        (b'{"model":', "invalid_json"),
    ],
)
def test_proxy_rejects_missing_wrong_or_malformed_model_before_forwarding(
    tmp_path, body, expected_code
):
    upstream, upstream_thread = _start_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    try:
        status, _, payload = _request(proxy, body=body)
        assert status == 400
        assert json.loads(payload)["error"]["code"] == expected_code
        assert upstream.captured == []
        [audit] = _read_audit(tmp_path)
        assert audit["request_state"] == "not_accepted"
        assert audit["failure_class"] == "policy_rejection"
        assert audit["model"] is None
        assert body not in (tmp_path / "proxy-audit.jsonl").read_bytes()
    finally:
        _stop(proxy, proxy_thread)
        _stop(upstream, upstream_thread)


def test_proxy_audit_has_only_safe_completed_request_fields(tmp_path):
    upstream, upstream_thread = _start_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    prompt = "private-prompt-must-not-enter-audit"
    body = json.dumps(
        {"model": "fixture", "messages": [{"content": prompt}]},
        separators=(",", ":"),
    ).encode()
    try:
        status, _, _ = _request(proxy, body=body)
        assert status == 200
        [audit] = _read_audit(tmp_path)
        assert set(audit) == {
            "schema_version",
            "request_identity_sha256",
            "model",
            "started_at",
            "finished_at",
            "latency_ms",
            "request_state",
            "upstream_status_code",
            "provider_request_id",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "provider_cost_usd",
            "failure_class",
        }
        assert audit["schema_version"] == 1
        assert len(audit["request_identity_sha256"]) == 64
        assert audit["model"] == "fixture"
        assert audit["latency_ms"] >= 0
        assert audit["request_state"] == "completed"
        assert audit["upstream_status_code"] == 200
        assert audit["provider_request_id"] == "provider-request-fixture-001"
        assert audit["input_tokens"] == 11
        assert audit["output_tokens"] == 7
        assert audit["total_tokens"] == 18
        assert audit["provider_cost_usd"] == 0.00125
        assert audit["failure_class"] is None
        encoded = (tmp_path / "proxy-audit.jsonl").read_text()
        assert prompt not in encoded
        assert REAL_TOKEN not in encoded
        assert "authorization" not in encoded.lower()
        assert (tmp_path / "proxy-audit.jsonl").stat().st_mode & 0o777 == 0o600
    finally:
        _stop(proxy, proxy_thread)
        _stop(upstream, upstream_thread)


def test_proxy_audit_drops_provider_request_id_that_contains_token(tmp_path):
    upstream, upstream_thread = _start_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    try:
        status, _, _ = _request(proxy, path="/v1/echo-token-header")
        assert status == 502
        [audit] = _read_audit(tmp_path)
        assert audit["provider_request_id"] is None
        assert REAL_TOKEN not in (tmp_path / "proxy-audit.jsonl").read_text()
    finally:
        _stop(proxy, proxy_thread)
        _stop(upstream, upstream_thread)


def test_proxy_classifies_connect_failure_before_request_as_not_accepted(tmp_path):
    unused = socket.socket()
    unused.bind(("127.0.0.1", 0))
    port = unused.getsockname()[1]
    unused.close()
    proxy, proxy_thread = _start_proxy(
        tmp_path, SimpleServerAddress(("127.0.0.1", port))
    )
    try:
        status, _, _ = _request(proxy)
        assert status == 502
        [audit] = _read_audit(tmp_path)
        assert audit["request_state"] == "not_accepted"
        assert audit["failure_class"] == "pre_accept_transport"
        assert audit["upstream_status_code"] is None
        assert audit["provider_request_id"] is None
        assert audit["input_tokens"] is None
        assert audit["output_tokens"] is None
        assert audit["total_tokens"] is None
        assert audit["provider_cost_usd"] is None
    finally:
        _stop(proxy, proxy_thread)


def test_proxy_quarantines_disconnect_after_request_bytes_are_received(tmp_path):
    upstream, captured, upstream_thread = _start_disconnect_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    try:
        status, _, _ = _request(proxy)
        assert status == 502
        upstream_thread.join(timeout=3)
        assert not upstream_thread.is_alive()
        assert captured and b'{"model":"fixture"}' in captured[0]
        [audit] = _read_audit(tmp_path)
        assert audit["request_state"] == "quarantined"
        assert audit["failure_class"] == "post_accept_transport"
        assert audit["upstream_status_code"] is None
    finally:
        _stop(proxy, proxy_thread)


def test_proxy_quarantines_response_shorter_than_declared_content_length(tmp_path):
    upstream, captured, upstream_thread = _start_short_body_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    try:
        status, _, payload = _request(proxy)
        assert status == 502
        assert b"incomplete_upstream_response" in payload
        upstream_thread.join(timeout=3)
        assert not upstream_thread.is_alive()
        assert len(captured) == 1
        [audit] = _read_audit(tmp_path)
        assert audit["request_state"] == "quarantined"
        assert audit["failure_class"] == "post_accept_transport"
        assert audit["upstream_status_code"] == 200
    finally:
        _stop(proxy, proxy_thread)


@pytest.mark.parametrize(
    "body",
    [
        b'{"model":"other","model":"fixture"}',
        b'{"model":"fixture","messages":{"role":"user","role":"system"}}',
    ],
)
def test_proxy_rejects_duplicate_json_keys_before_upstream_forwarding(tmp_path, body):
    upstream, upstream_thread = _start_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    try:
        status, _, payload = _request(proxy, body=body)
        assert status == 400
        assert json.loads(payload)["error"]["code"] == "duplicate_json_key"
        assert upstream.captured == []
        [audit] = _read_audit(tmp_path)
        assert audit["request_state"] == "not_accepted"
        assert audit["failure_class"] == "policy_rejection"
    finally:
        _stop(proxy, proxy_thread)
        _stop(upstream, upstream_thread)


def test_new_proxy_attempt_rejects_prior_request_hash_before_second_upstream_call(
    tmp_path,
):
    upstream, upstream_thread = _start_upstream()
    first_dir = tmp_path / "attempt-a"
    second_dir = tmp_path / "attempt-b"
    first_dir.mkdir()
    second_dir.mkdir()
    first_proxy, first_thread = _start_proxy(first_dir, upstream)
    try:
        status, _, _ = _request(first_proxy)
        assert status == 200
        [first_audit] = _read_audit(first_dir)
    finally:
        _stop(first_proxy, first_thread)

    second_proxy, second_thread = _start_proxy(
        second_dir,
        upstream,
        denied_request_identities_sha256=(
            first_audit["request_identity_sha256"],
        ),
    )
    try:
        status, _, payload = _request(second_proxy)
        assert status == 409
        assert json.loads(payload)["error"]["code"] == "request_replay_forbidden"
        assert len(upstream.captured) == 1
        [second_audit] = _read_audit(second_dir)
        assert second_audit["request_identity_sha256"] == (
            first_audit["request_identity_sha256"]
        )
        assert second_audit["request_state"] == "quarantined"
        assert second_audit["failure_class"] == "replay_denied"
    finally:
        _stop(second_proxy, second_thread)
        _stop(upstream, upstream_thread)


def test_finalize_waits_for_inflight_request_then_seals_exact_audit(tmp_path):
    upstream, upstream_thread = _start_blocking_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    request_result = []
    finalize_result = []
    request_done = threading.Event()
    finalize_done = threading.Event()

    def make_request():
        try:
            request_result.append(_request(proxy))
        finally:
            request_done.set()

    def finalize():
        try:
            finalize_result.append(_finalize(proxy))
        finally:
            finalize_done.set()

    request_thread = threading.Thread(target=make_request)
    finalize_thread = threading.Thread(target=finalize)
    try:
        request_thread.start()
        assert upstream.request_started.wait(timeout=3)
        finalize_thread.start()
        assert proxy.finalize_started.wait(timeout=3)
        assert not finalize_done.is_set()
        upstream.release_response.set()
        request_thread.join(timeout=3)
        finalize_thread.join(timeout=3)
        assert request_done.is_set()
        assert finalize_done.is_set()
        assert request_result[0][0] == 200
        status, payload = finalize_result[0]
        assert status == 200
        seal = json.loads(payload)
        audit_bytes = (tmp_path / "proxy-audit.jsonl").read_bytes()
        assert seal == {
            "audit_sha256": hashlib.sha256(audit_bytes).hexdigest(),
            "record_count": 1,
            "schema_version": 1,
        }
    finally:
        upstream.release_response.set()
        request_thread.join(timeout=3)
        finalize_thread.join(timeout=3)
        _stop(proxy, proxy_thread)
        _stop(upstream, upstream_thread)


def test_finalize_reports_prior_record_plus_later_audit_append_loss(
    tmp_path, monkeypatch
):
    import qea.model_proxy as model_proxy

    upstream, upstream_thread = _start_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    original_append = model_proxy._append_audit
    append_calls = 0

    def fail_second_append(*args, **kwargs):
        nonlocal append_calls
        append_calls += 1
        if append_calls == 2:
            raise model_proxy.ModelProxyError("synthetic audit append loss")
        return original_append(*args, **kwargs)

    monkeypatch.setattr(model_proxy, "_append_audit", fail_second_append)
    try:
        status, _, _ = _request(proxy, body=b"{}")
        assert status == 400
        with pytest.raises((http.client.RemoteDisconnected, ConnectionResetError)):
            _request(proxy)
        assert len(upstream.captured) == 1
        [earlier_record] = _read_audit(tmp_path)
        assert earlier_record["request_state"] == "not_accepted"
        status, payload = _finalize(proxy)
        assert status == 409
        assert json.loads(payload)["error"]["code"] == "audit_append_failed"
    finally:
        _stop(proxy, proxy_thread)
        _stop(upstream, upstream_thread)


def test_finalize_rejects_counted_handler_without_terminal_audit_record(tmp_path):
    upstream, upstream_thread = _start_upstream()
    proxy, proxy_thread = _start_proxy(tmp_path, upstream)
    try:
        status, _, _ = _request(proxy, body=b"{}")
        assert status == 400
        status, _, _ = _request(proxy, path="/outside-allowlist")
        assert status == 404
        [earlier_record] = _read_audit(tmp_path)
        assert earlier_record["request_state"] == "not_accepted"

        status, payload = _finalize(proxy)
        assert status == 409
        assert json.loads(payload)["error"]["code"] == (
            "audit_stream_incomplete"
        )
    finally:
        _stop(proxy, proxy_thread)
        _stop(upstream, upstream_thread)


def test_non_loopback_client_cannot_invoke_private_finalize():
    from qea.model_proxy import _ModelProxyHandler

    finalized = []
    rejected = []
    handler = object.__new__(_ModelProxyHandler)
    handler.client_address = ("172.20.0.9", 43100)
    handler.server = SimpleNamespace(
        finalize_audit=lambda: finalized.append(True)
    )
    handler._reject = lambda status, code: rejected.append((status, code))

    handler._finalize()

    assert finalized == []
    assert rejected == [(403, "finalize_loopback_only")]


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
        max_request_bytes=64,
        max_response_bytes=64,
    )
    try:
        status, _, payload = _request(proxy, body=b"x" * 65)
        assert status == 413
        assert upstream.captured == []
        status, _, payload = _request(proxy, path="/v1/large")
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
            proxy, path="/v1/echo-token"
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


@pytest.mark.parametrize("mode", [0o604, 0o640, 0o644, 0o666])
def test_token_file_rejects_any_group_or_other_permission_bits(tmp_path, mode):
    from qea.model_proxy import ModelProxyConfig, ModelProxyError

    token = _token_file(tmp_path)
    token.chmod(mode)
    with pytest.raises(ModelProxyError, match="group or other"):
        ModelProxyConfig(
            listen_host="127.0.0.1",
            listen_port=0,
            upstream_base_url="https://model.example/v1",
            allowed_path_prefix="/v1",
            allowed_model="fixture",
            token_file=token,
            audit_file=tmp_path / "audit.jsonl",
        )


@pytest.mark.parametrize("mode", [0o400, 0o600, 0o700])
def test_token_file_accepts_owner_only_modes(tmp_path, mode):
    from qea.model_proxy import ModelProxyConfig

    token = _token_file(tmp_path)
    token.chmod(mode)
    config = ModelProxyConfig(
        listen_host="127.0.0.1",
        listen_port=0,
        upstream_base_url="https://model.example/v1",
        allowed_path_prefix="/v1",
        allowed_model="fixture",
        token_file=token,
        audit_file=tmp_path / "audit.jsonl",
    )

    assert config.token_file == token


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
            allowed_model="fixture",
            token_file=link,
            audit_file=tmp_path / "audit.jsonl",
        )
    real.write_bytes(b"x" * 16_385)
    real.chmod(0o600)
    with pytest.raises(ModelProxyError, match="token file is too large"):
        ModelProxyConfig(
            listen_host="127.0.0.1",
            listen_port=0,
            upstream_base_url="https://model.example/v1",
            allowed_path_prefix="/v1",
            allowed_model="fixture",
            token_file=real,
            audit_file=tmp_path / "audit.jsonl",
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


def test_proxy_sandbox_plan_binds_scope_model_and_private_audit_config():
    from qea.model_proxy import build_model_proxy_sandbox_plan

    plan = build_model_proxy_sandbox_plan(
        run_id="run-001",
        attempt_id="attempt-001",
        task_id="historical-var-data-prep",
        image_ref="sha256:" + "c" * 64,
        upstream_base_url="https://openrouter.ai/api/v1",
        allowed_path_prefix="/v1",
        allowed_model="openai/gpt-5",
        audit_path="/run/qea-secrets/proxy-audit.jsonl",
        network_scope="attempt-001",
        listen_port=8080,
        cpu_count=1,
        memory_mb=512,
        pids_limit=64,
        timeout_seconds=3600,
    )

    assert plan.spec.task_id == "historical-var-data-prep"
    assert plan.spec.network_scope == "attempt-001"
    assert plan.allowed_model == "openai/gpt-5"
    assert plan.audit_path == "/run/qea-secrets/proxy-audit.jsonl"
    assert plan.config_payload()["allowed_model"] == "openai/gpt-5"


def test_proxy_public_plan_identity_includes_safe_denied_request_hashes():
    from qea.model_proxy import build_model_proxy_sandbox_plan

    denied = ("1" * 64, "2" * 64)
    plan = build_model_proxy_sandbox_plan(
        run_id="run-001",
        attempt_id="attempt-001",
        task_id="historical-var-data-prep",
        image_ref="sha256:" + "c" * 64,
        upstream_base_url="https://openrouter.ai/api/v1",
        allowed_path_prefix="/v1",
        allowed_model="openai/gpt-5",
        audit_path="/run/qea-secrets/proxy-audit.jsonl",
        network_scope="attempt-001",
        denied_request_identities_sha256=denied,
        listen_port=8080,
        cpu_count=1,
        memory_mb=512,
        pids_limit=64,
        timeout_seconds=300,
    )

    assert plan.public_payload()["denied_request_identities_sha256"] == list(
        denied
    )
    assert plan.config_payload()["audit_file"] == (
        "/run/qea-secrets/proxy-audit.jsonl"
    )
    assert "openai/gpt-5" not in " ".join(plan.start_argv)


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


def test_cli_requires_and_forwards_model_and_audit_policy(tmp_path, monkeypatch):
    import scripts.run_qea_model_proxy as cli

    token = _token_file(tmp_path)
    audit = tmp_path / "cli-audit.jsonl"
    captured = {}
    handlers = {}

    class Server:
        timeout = None

        def handle_request(self):
            handlers[signal.SIGTERM](signal.SIGTERM, None)

        def server_close(self):
            captured["closed"] = True

    def config_factory(**values):
        captured["config"] = values
        return object()

    monkeypatch.setattr(cli, "ModelProxyConfig", config_factory)
    monkeypatch.setattr(cli, "create_proxy_server", lambda config: Server())
    monkeypatch.setattr(
        cli.signal,
        "signal",
        lambda signum, handler: handlers.__setitem__(signum, handler),
    )

    assert cli.main(
        [
            "--listen-port",
            "8080",
            "--upstream-base-url",
            "https://openrouter.ai/api/v1",
            "--allowed-path-prefix",
            "/v1",
            "--allowed-model",
            "openai/gpt-5",
            "--token-file",
            str(token),
            "--audit-file",
            str(audit),
        ]
    ) == 0
    assert captured["config"]["allowed_model"] == "openai/gpt-5"
    assert captured["config"]["audit_file"] == str(audit)
    assert captured["closed"] is True
