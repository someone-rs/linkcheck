"""End-to-end tests for the linkcheck CLI."""

import json

import pytest

from linkcheck.cli import EXIT_BROKEN, EXIT_ERROR, EXIT_OK, main


def run_cli(args, capsys):
    code = main(args)
    return code, capsys.readouterr().out


def test_cli_ok_file_exits_zero(tmp_path, capsys):
    doc = tmp_path / "a.md"
    doc.write_text("[self](#title)\n\n# Title\n")
    code, out = run_cli([str(doc), "--no-external"], capsys)
    assert code == EXIT_OK
    assert "0 broken" in out


def test_cli_broken_file_exits_one(tmp_path, capsys):
    doc = tmp_path / "a.md"
    doc.write_text("[gone](missing.md)\n")
    code, out = run_cli([str(doc), "--no-external"], capsys)
    assert code == EXIT_BROKEN
    assert "1 broken" in out
    assert "missing.md" in out


def test_cli_directory_scan_and_json(tmp_path, capsys):
    (tmp_path / "a.md").write_text("[gone](missing.md)\n")
    (tmp_path / "b.md").write_text("[ok](a.md)\n")
    code, out = run_cli([str(tmp_path), "--no-external", "--json"], capsys)
    assert code == EXIT_BROKEN
    data = json.loads(out[: out.rindex("]") + 1])
    by_target = {item["target"]: item["status"] for item in data}
    assert by_target["missing.md"] == "broken"
    assert by_target["a.md"] == "ok"


def test_cli_missing_path_exits_two(tmp_path, capsys):
    code, _ = run_cli([str(tmp_path / "nope.md")], capsys)
    assert code == EXIT_ERROR


def test_cli_quiet_hides_ok_lines(tmp_path, capsys):
    doc = tmp_path / "a.md"
    doc.write_text("[ok](a.md) [gone](missing.md)\n")
    code, out = run_cli([str(doc), "--no-external", "--quiet"], capsys)
    assert code == EXIT_BROKEN
    assert "missing.md" in out
    assert "[ok]" not in out


def test_cli_invalid_exclude_regex(tmp_path, capsys):
    doc = tmp_path / "a.md"
    doc.write_text("hi\n")
    code, _ = run_cli([str(doc), "--exclude", "([invalid"], capsys)
    assert code == EXIT_ERROR
