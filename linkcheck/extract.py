"""Extract links from Markdown text.

Handles inline links/images, reference-style links, and autolinks.
Fenced code blocks and inline code spans are stripped first so that
example links inside code are not reported as real links.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_INLINE_RE = re.compile(
    r"!?\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)"
)
_REF_USE_RE = re.compile(r"!?\[([^\]]+)\]\[([^\]]*)\]")
_REF_DEF_RE = re.compile(
    r"(?m)^[ ]{0,3}\[([^\]]+)\]:\s*(\S+)(?:\s+\"[^\"]*\")?\s*$"
)
_AUTOLINK_RE = re.compile(r"<(https?://[^>\s]+)>")
_HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE_RE = re.compile(r"(?ms)^```.*?^```|^~~~.*?^~~~")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


@dataclass(frozen=True)
class Link:
    """One link found in a Markdown file."""

    target: str
    line: int
    text: str = ""

    @property
    def is_image(self) -> bool:
        return self.text.startswith("!")


def strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code spans.

    Newlines are preserved so reported line numbers stay correct.
    """
    def _blank_fence(match: re.Match) -> str:
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))

    text = _FENCE_RE.sub(_blank_fence, text)
    text = _INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), text)
    return text


def extract_links(text: str) -> list[Link]:
    """Return every link in *text* with its 1-based line number."""
    clean = strip_code(text)
    links: list[Link] = []
    seen_spans: set[tuple[int, int]] = set()

    def _line_no(pos: int) -> int:
        return clean.count("\n", 0, pos) + 1

    for match in _INLINE_RE.finditer(clean):
        span = match.span()
        if span in seen_spans:
            continue
        seen_spans.add(span)
        links.append(Link(match.group(2), _line_no(match.start()), match.group(1)))

    # Reference definitions: [label]: url
    definitions: dict[str, str] = {}
    for match in _REF_DEF_RE.finditer(clean):
        definitions[match.group(1).strip().lower()] = match.group(2)

    for match in _REF_USE_RE.finditer(clean):
        seen_spans.add(match.span())
        label = (match.group(2) or match.group(1)).strip().lower()
        target = definitions.get(label)
        if target is not None:
            links.append(Link(target, _line_no(match.start()), match.group(1)))

    # Shortcut reference links: [label] on its own, when a definition exists.
    for match in re.finditer(r"\[([^\]]+)\]", clean):
        start, end = match.span()
        if any(s <= start < e for s, e in seen_spans):
            continue
        if clean[end:end + 1] == ":":
            continue  # this is the definition line itself, not a use
        label = match.group(1).strip().lower()
        target = definitions.get(label)
        if target is not None:
            links.append(Link(target, _line_no(start), match.group(1)))

    for match in _AUTOLINK_RE.finditer(clean):
        links.append(Link(match.group(1), _line_no(match.start())))

    links.sort(key=lambda link: link.line)
    return links


def heading_slugs(text: str) -> set[str]:
    """Return the set of GitHub-style anchor slugs for all headings."""
    slugs: set[str] = set()
    counts: dict[str, int] = {}
    for match in _HEADING_RE.finditer(strip_code(text)):
        slug = slugify(match.group(2))
        if not slug:
            continue
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        slugs.add(slug if count == 0 else f"{slug}-{count}")
    return slugs


def slugify(heading: str) -> str:
    """GitHub-style anchor slug for a heading."""
    heading = heading.strip().lower()
    heading = re.sub(r"`", "", heading)
    heading = re.sub(r"[^\w\s-]", "", heading, flags=re.UNICODE)
    heading = re.sub(r"\s+", "-", heading)
    return heading.strip("-")
