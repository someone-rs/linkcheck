"""Tests for link checking: local files, anchors, external URLs."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from linkcheck.check import check_external, check_file


@pytest.fixture()
def docs(tmp_path: Path):
    (tmp_path / "guide.md").write_text("# Guide\n\n## Getting Started\n")
    (tmp_path / "sub").mkdir()
    return tmp_path


def write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def statuses(path: Path, **kwargs):
    return {r.target: r.status for r in check_file(path, **kwargs)}


def test_local_file_ok_and_missing(docs):
    path = write(docs / "index.md", "[ok](guide.md) [gone](nope.md)\n")
    result = statuses(path, check_externals=False)
    assert result == {"guide.md": "ok", "nope.md": "broken"}


def test_anchor_ok_and_missing(docs):
    path = write(
        docs / "index.md",
        "## Getting Started\n\n[ok](#getting-started) [bad](#no-such-heading) "
        "[file](guide.md#getting-started)\n",
    )
    result = statuses(path, check_externals=False)
    assert result["#getting-started"] == "ok"
    assert result["#no-such-heading"] == "broken"
    assert result["guide.md#getting-started"] == "ok"


def test_anchor_to_missing_file_is_file_error(docs):
    path = write(docs / "index.md", "[x](nope.md#anchor)\n")
    result = statuses(path, check_externals=False)
    assert result["nope.md#anchor"] == "broken"


def test_percent_encoded_local_path(docs):
    (docs / "my file.md").write_text("# Hi\n")
    path = write(docs / "index.md", "[x](my%20file.md)\n")
    assert statuses(path, check_externals=False)["my%20file.md"] == "ok"


def test_mailto_and_tel_skipped(docs):
    path = write(docs / "index.md", "[m](mailto:a@b.c) [t](tel:+123)\n")
    result = statuses(path, check_externals=False)
    assert result == {"mailto:a@b.c": "skipped", "tel:+123": "skipped"}


def test_no_external_mode_skips_http(docs):
    path = write(docs / "index.md", "[x](https://example.com)\n")
    assert statuses(path, check_externals=False)["https://example.com"] == "skipped"


def test_exclude_regex(docs):
    import re

    path = write(docs / "index.md", "[a](guide.md) [b](other.md)\n")
    result = statuses(path, check_externals=False, exclude=[re.compile("other")])
    assert result["other.md"] == "skipped"
    assert result["guide.md"] == "ok"


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self._respond()

    def do_GET(self):
        self._respond()

    def _respond(self):
        if self.path == "/ok":
            self.send_response(200)
        elif self.path == "/gone":
            self.send_response(404)
        elif self.path == "/head-refused":
            if self.command == "HEAD":
                self.send_response(405)
            else:
                self.send_response(200)
        elif self.path == "/redirect":
            self.send_response(301)
            self.send_header("Location", "/ok")
        else:
            self.send_response(500)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_external_ok_404_redirect_and_head_fallback(server):
    assert check_external(f"{server}/ok", 5)[0] == "ok"
    assert check_external(f"{server}/gone", 5)[0] == "broken"
    assert check_external(f"{server}/redirect", 5)[0] == "ok"
    # HEAD refused (405) but GET works -> still ok.
    assert check_external(f"{server}/head-refused", 5)[0] == "ok"


def test_external_connection_refused_is_broken():
    status, detail = check_external("http://127.0.0.1:1/", 2)
    assert status == "broken"
    assert "refused" in detail


def test_external_check_through_check_file(server, docs):
    path = write(
        docs / "index.md",
        f"[ok]({server}/ok) [gone]({server}/gone)\n",
    )
    result = statuses(path, timeout=5)
    assert result[f"{server}/ok"] == "ok"
    assert result[f"{server}/gone"] == "broken"
