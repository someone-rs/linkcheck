"""Command-line interface for linkcheck."""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import __version__
from .check import Result, check_file, collect_markdown_files

EXIT_OK = 0
EXIT_BROKEN = 1
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="linkcheck",
        description="Find broken links in Markdown files: external URLs, "
        "local files, and #anchors.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Markdown file(s) or directorie(s) to scan (directories are scanned recursively)",
    )
    parser.add_argument(
        "--no-external",
        action="store_true",
        help="skip http(s) links; only check local files and anchors",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="seconds to wait for each external link (default: 10)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=8,
        help="concurrent external checks (default: 8)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="REGEX",
        help="skip links whose target matches this regex (repeatable)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print results as JSON instead of a table",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="only print broken links (and the summary)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def render_table(results: list[Result], *, quiet: bool) -> str:
    lines: list[str] = []
    for result in results:
        if quiet and result.status != "broken":
            continue
        marker = {"ok": "✓", "broken": "✗", "skipped": "–"}[result.status]
        lines.append(
            f"{marker} {result.source}:{result.line}  {result.target}  "
            f"[{result.status}] {result.detail}"
        )
    return "\n".join(lines)


def render_summary(results: list[Result]) -> str:
    counts = {"ok": 0, "broken": 0, "skipped": 0}
    for result in results:
        counts[result.status] += 1
    total = len(results)
    return (
        f"{total} link(s) checked: {counts['ok']} ok, "
        f"{counts['broken']} broken, {counts['skipped']} skipped"
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        exclude = [re.compile(pattern) for pattern in args.exclude]
    except re.error as err:
        print(f"linkcheck: invalid --exclude regex: {err}", file=sys.stderr)
        return EXIT_ERROR
    try:
        files = collect_markdown_files(args.paths)
    except FileNotFoundError as err:
        print(f"linkcheck: {err}", file=sys.stderr)
        return EXIT_ERROR
    if not files:
        print("linkcheck: no Markdown files found", file=sys.stderr)
        return EXIT_ERROR

    results: list[Result] = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        for path in files:
            results.extend(
                check_file(
                    path,
                    check_externals=not args.no_external,
                    timeout=args.timeout,
                    exclude=exclude,
                    executor=executor,
                )
            )

    if args.json:
        print(json.dumps([r.as_dict() for r in results], indent=2))
    else:
        table = render_table(results, quiet=args.quiet)
        if table:
            print(table)
    print(render_summary(results))
    broken = any(r.status == "broken" for r in results)
    return EXIT_BROKEN if broken else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
