"""Provider-neutral artifact archive extraction with a strict file firewall."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path, PurePosixPath


class OutputArchiveError(RuntimeError):
    """An artifact archive is malformed, unsafe, or exceeds declared limits."""


def _unsafe_output_name(name: str) -> bool:
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        return True
    lowered = path.name.lower()
    return (
        lowered == ".env"
        or lowered.startswith(".env.")
        or lowered.startswith("credentials")
        or lowered.startswith("secrets")
        or lowered in {"id_rsa", "id_ed25519"}
        or lowered.endswith((".pem", ".key"))
    )


def extract_output_archive(
    payload: bytes,
    destination: str | Path,
    *,
    max_files: int = 2_000,
    max_bytes: int = 512 * 1024 * 1024,
) -> tuple[Path, ...]:
    """Extract regular files only, without traversal, links, or secret files."""

    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    total_bytes = 0
    seen: set[str] = set()
    try:
        archive = tarfile.open(fileobj=io.BytesIO(payload), mode="r:*")
    except tarfile.TarError as exc:
        raise OutputArchiveError(f"invalid output archive: {exc}") from exc
    with archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            if not member.isfile() or _unsafe_output_name(member.name):
                raise OutputArchiveError(f"unsafe output member {member.name!r}")
            name = PurePosixPath(member.name).as_posix()
            if name in seen:
                raise OutputArchiveError(f"duplicate output member {name!r}")
            seen.add(name)
            if len(seen) > max_files:
                raise OutputArchiveError(
                    f"output file limit exceeded: {len(seen)} > {max_files}"
                )
            total_bytes += member.size
            if total_bytes > max_bytes:
                raise OutputArchiveError(
                    f"output byte limit exceeded: {total_bytes} > {max_bytes}"
                )
            target = (root / Path(*PurePosixPath(name).parts)).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise OutputArchiveError(
                    f"unsafe output member {member.name!r}"
                ) from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise OutputArchiveError(
                    f"cannot read output member {member.name!r}"
                )
            with target.open("wb") as handle:
                handle.write(source.read())
            extracted.append(target)
    return tuple(
        sorted(extracted, key=lambda path: path.relative_to(root).as_posix())
    )


__all__ = ["OutputArchiveError", "extract_output_archive"]
