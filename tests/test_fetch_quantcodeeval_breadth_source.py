import io
import json
import sys

import pytest

from scripts import fetch_quantcodeeval_breadth_source as fetcher


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


def test_fetches_allowlisted_files_and_records_setup_without_hashes(
    tmp_path, monkeypatch, capsys
):
    destination = tmp_path / "source"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fetch",
            "--destination",
            str(destination),
            "--workers",
            "2",
        ],
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO("tasks/T26/sample_instruction.md\ntasks/T27/paper_text.md\n"),
    )
    monkeypatch.setattr(
        fetcher,
        "urlopen",
        lambda request, timeout: _Response(request.full_url.encode("utf-8")),
    )

    assert fetcher.main() == 0
    result = json.loads(capsys.readouterr().out)
    setup = json.loads((destination / "SETUP.json").read_text())

    assert result["file_count"] == 2
    assert setup["file_count"] == 2
    assert setup["task_ids"] == ["T26", "T27"]
    assert [row["path"] for row in setup["files"]] == [
        "tasks/T26/sample_instruction.md",
        "tasks/T27/paper_text.md",
    ]
    assert "sha256" not in json.dumps(setup).casefold()
    assert not (destination / "FETCH-INCOMPLETE").exists()


def test_rejects_path_outside_the_allowlisted_source(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["fetch", "--destination", str(tmp_path / "source")],
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("../golden_ref.py\n"))

    with pytest.raises(ValueError, match="unsafe source path"):
        fetcher.main()
