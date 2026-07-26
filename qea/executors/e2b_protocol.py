"""Narrow E2B SDK surface used by the QFBench executor and its test fakes."""

from __future__ import annotations

from typing import Protocol


class E2BFiles(Protocol):
    def write(self, path: str, data, **kwargs): ...
    def read(self, path: str, format: str = "text", **kwargs): ...


class E2BCommands(Protocol):
    def run(self, command: str, **kwargs): ...


class E2BSandbox(Protocol):
    sandbox_id: str
    files: E2BFiles
    commands: E2BCommands

    def kill(self): ...


class E2BSandboxFactory(Protocol):
    def create(self, **kwargs) -> E2BSandbox: ...


class SDKSandboxFactory:
    """Import E2B lazily so dependency-light tests still import the package."""

    def create(self, **kwargs) -> E2BSandbox:
        from e2b import Sandbox

        return Sandbox.create(**kwargs)
