"""Check one link: classify it, probe it, and report a verdict."""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .extract import extract_links, heading_slugs

SKIPPED_SCHEMES = {"mailto", "tel", "data", "javascript"}
_SLUG_CACHE: dict[str, set[str]] = {}


@dataclass
class Result:
    """The verdict for a single link."""

    source: Path
    line: int
    target: str
    status: str  # "ok" | "broken" | "skipped"
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "source": str(self.source),
            "line": self.line,
            "target": self.target,
            "status": self.status,
            "detail": self.detail,
        }


def _heading_slugs_cached(path: Path) -> set[str]:
    key = str(path)
    if key not in _SLUG_CACHE:
        try:
            _SLUG_CACHE[key] = heading_slugs(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            _SLUG_CACHE[key] = set()
    return _SLUG_CACHE[key]


def _check_anchor(path: Path, anchor: str) -> Result | None:
    """Return a broken Result if *anchor* is not a heading slug, else None."""
    if anchor in _heading_slugs_cached(path):
        return None
    return Result(path, 0, "", "broken", f"no heading with anchor #{anchor}")


def check_local(source: Path, target: str, line: int) -> Result:
    """Check a relative file link, optionally with a #anchor."""
    path_part, _, anchor = target.partition("#")
    # URL-decode so "my%20file.md" resolves like a browser would.
    path_part = urllib.parse.unquote(path_part)
    if not path_part:
        # Anchor-only link: validate against the source file itself.
        if not anchor:
            return Result(source, line, target, "ok")
        bad = _check_anchor(source, anchor)
        if bad is not None:
            return Result(source, line, target, "broken", bad.detail)
        return Result(source, line, target, "ok")
    resolved = (source.parent / path_part).resolve()
    if not resolved.exists():
        return Result(source, line, target, "broken", "file does not exist")
    if anchor and resolved.suffix.lower() in {".md", ".markdown"}:
        bad = _check_anchor(resolved, anchor)
        if bad is not None:
            return Result(source, line, target, "broken", bad.detail)
    return Result(source, line, target, "ok")


def check_external(target: str, timeout: float) -> tuple[str, str]:
    """Probe an http(s) URL. Returns (status, detail)."""
    request = urllib.request.Request(
        target, method="HEAD", headers={"User-Agent": "linkcheck/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return "ok", f"HTTP {response.status}"
    except urllib.error.HTTPError as err:
        if err.code in (405, 501) or err.code == 403:
            # Some servers refuse HEAD; retry with GET before giving up.
            try:
                get = urllib.request.Request(
                    target, headers={"User-Agent": "linkcheck/1.0"}
                )
                with urllib.request.urlopen(get, timeout=timeout) as response:
                    return "ok", f"HTTP {response.status}"
            except urllib.error.HTTPError as get_err:
                return "broken", f"HTTP {get_err.code}"
            except (urllib.error.URLError, TimeoutError, OSError) as get_err:
                return "broken", _url_error_detail(get_err)
        return "broken", f"HTTP {err.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        return "broken", _url_error_detail(err)


def _url_error_detail(err: Exception) -> str:
    reason = getattr(err, "reason", err)
    text = str(reason)
    if "Name or service not known" in text or "nodename nor servname" in text:
        return "DNS lookup failed"
    if "Connection refused" in text:
        return "connection refused"
    if isinstance(err, TimeoutError) or "timed out" in text:
        return "timed out"
    if "CERTIFICATE_VERIFY_FAILED" in text or "certificate" in text.lower():
        return "TLS certificate error"
    if "Too many redirects" in text or "redirect" in text.lower():
        return "redirect loop"
    return text or err.__class__.__name__


def check_file(
    path: Path,
    *,
    check_externals: bool = True,
    timeout: float = 10.0,
    exclude: list[re.Pattern] | None = None,
    executor: ThreadPoolExecutor | None = None,
) -> list[Result]:
    """Check every link in one Markdown file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        return [Result(path, 0, "", "broken", f"cannot read file: {err}")]
    results: list[Result] = []
    external_futures: list[tuple[Result, object]] = []
    for link in extract_links(text):
        if exclude and any(p.search(link.target) for p in exclude):
            results.append(Result(path, link.line, link.target, "skipped", "excluded"))
            continue
        scheme = urllib.parse.urlparse(link.target).scheme.lower()
        if scheme in SKIPPED_SCHEMES:
            results.append(Result(path, link.line, link.target, "skipped", f"{scheme}: link"))
            continue
        if scheme in ("http", "https"):
            if not check_externals:
                results.append(Result(path, link.line, link.target, "skipped", "external checks off"))
                continue
            if executor is not None:
                placeholder = Result(path, link.line, link.target, "ok")
                future = executor.submit(check_external, link.target, timeout)
                external_futures.append((placeholder, future))
            else:
                status, detail = check_external(link.target, timeout)
                results.append(Result(path, link.line, link.target, status, detail))
            continue
        if scheme:
            results.append(Result(path, link.line, link.target, "skipped", f"unsupported scheme: {scheme}"))
            continue
        results.append(check_local(path, link.target, link.line))
    for placeholder, future in external_futures:
        status, detail = future.result()
        results.append(Result(placeholder.source, placeholder.line, placeholder.target, status, detail))
    results.sort(key=lambda r: (r.line, r.target))
    return results


def collect_markdown_files(paths: list[Path]) -> list[Path]:
    """Expand files and directories into a sorted list of Markdown files."""
    found: list[Path] = []
    for path in paths:
        if path.is_file():
            found.append(path)
        elif path.is_dir():
            found.extend(sorted(path.rglob("*.md")))
            found.extend(sorted(path.rglob("*.markdown")))
        else:
            raise FileNotFoundError(f"no such file or directory: {path}")
    # Deduplicate while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in found:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique
