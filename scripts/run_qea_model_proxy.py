#!/usr/bin/env python3
"""Run QEA's fixed-upstream model proxy from an owner-only token file."""

from __future__ import annotations

import argparse
import signal
import threading

from qea.model_proxy import ModelProxyConfig, ModelProxyError, create_proxy_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, required=True)
    parser.add_argument("--upstream-base-url", required=True)
    parser.add_argument("--allowed-path-prefix", default="/v1")
    parser.add_argument("--allowed-model", required=True)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--audit-file", required=True)
    parser.add_argument(
        "--denied-request-identity-sha256", action="append", default=[]
    )
    parser.add_argument("--max-request-bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--max-response-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--connect-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--read-timeout-seconds", type=float, default=300.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        server = create_proxy_server(
            ModelProxyConfig(
                listen_host=args.listen_host,
                listen_port=args.listen_port,
                upstream_base_url=args.upstream_base_url,
                allowed_path_prefix=args.allowed_path_prefix,
                allowed_model=args.allowed_model,
                token_file=args.token_file,
                audit_file=args.audit_file,
                denied_request_identities_sha256=tuple(
                    args.denied_request_identity_sha256
                ),
                max_request_bytes=args.max_request_bytes,
                max_response_bytes=args.max_response_bytes,
                connect_timeout_seconds=args.connect_timeout_seconds,
                read_timeout_seconds=args.read_timeout_seconds,
            )
        )
    except ModelProxyError:
        return 2

    stopped = threading.Event()

    def stop(_signum, _frame) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    server.timeout = 0.25
    try:
        while not stopped.is_set():
            server.handle_request()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
