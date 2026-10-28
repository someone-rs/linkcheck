# linkcheck

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org)

**Find broken links in your Markdown docs before your readers do.**

`linkcheck` scans Markdown files and verifies every link it finds:

- **External URLs** — probed over HTTP(S), with a GET fallback for servers
  that refuse `HEAD`, and plain-language failure reasons (DNS, refused,
  timeout, TLS, redirect loop).
- **Local files** — relative links resolved against the file that contains
  them, including `%20`-style URL encoding.
- **Anchors** — `#fragment` links validated against the target file's
  headings, using GitHub-style slugs (including `-1`, `-2` duplicates).
- **Skipped, not faked** — `mailto:`/`tel:` links and anything you
  `--exclude` are reported as skipped, never silently passed.

Links inside fenced code blocks and inline code spans are ignored, so your
examples never trigger false positives. Exit codes are CI-friendly:
`0` = all clean, `1` = broken links found, `2` = usage error.

## Install

```bash
pip install linkcheck
```

Requires Python 3.9+. Zero dependencies — it only uses the standard library.

Or run it from source:

```bash
git clone https://github.com/someone-rs/linkcheck
cd linkcheck
python -m linkcheck docs/
```

## Quickstart

```bash
# Check a whole docs tree (directories are scanned recursively)
linkcheck docs/

# Check one file, local links and anchors only
linkcheck README.md --no-external

# Machine-readable output for CI
linkcheck docs/ --json

# Ignore a whole domain, show only broken links
linkcheck docs/ --exclude 'example\.com' --quiet
```

## Example output

Running it on the included `demo/` folder:

```
$ linkcheck demo/
✓ demo/sample.md:3  guide.md  [ok]
✓ demo/sample.md:4  #sample-doc  [ok]
✗ demo/sample.md:4  missing.md  [broken] file does not exist
✗ demo/sample.md:5  #nope  [broken] no heading with anchor #nope
✓ demo/sample.md:7  https://www.python.org  [ok] HTTP 200
✗ demo/sample.md:8  https://www.python.org/this-page-does-not-exist  [broken] HTTP 404
– demo/sample.md:10  mailto:hello@example.com  [skipped] mailto: link
7 link(s) checked: 3 ok, 3 broken, 1 skipped
```

## Options

| Flag | Meaning |
| --- | --- |
| `--no-external` | Skip http(s) links; only check local files and anchors |
| `--timeout SECONDS` | Per-link timeout for external checks (default: 10) |
| `--jobs N` | Concurrent external checks (default: 8) |
| `--exclude REGEX` | Skip links whose target matches (repeatable) |
| `--json` | Print results as JSON instead of a table |
| `-q, --quiet` | Only print broken links (and the summary) |

## Use it in CI

```yaml
# .github/workflows/docs.yml
- name: Check Markdown links
  run: pip install linkcheck && linkcheck docs/
```

A broken link fails the build with exit code 1.

## Link styles supported

Inline `[text](url)` and images `![alt](url)`, reference-style
`[text][ref]` plus `[ref]: url`, shortcut references `[ref]`, and
autolinks `<https://example.com>`.

## License

MIT — see [LICENSE](LICENSE).
