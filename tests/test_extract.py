"""Tests for Markdown link extraction."""

from linkcheck.extract import extract_links, heading_slugs, slugify


def targets(text):
    return [(link.target, link.line) for link in extract_links(text)]


def test_inline_link_and_image():
    text = "[docs](guide.md) and ![logo](img/logo.png)\n"
    assert targets(text) == [("guide.md", 1), ("img/logo.png", 1)]


def test_link_with_title():
    assert targets('[a](page.md "A title")\n') == [("page.md", 1)]


def test_reference_style_links():
    text = "[click][ref]\n\n[ref]: https://example.com/page\n"
    assert targets(text) == [("https://example.com/page", 1)]


def test_reference_style_shorthand():
    text = "[ref]\n\n[ref]: other.md\n"
    assert targets(text) == [("other.md", 1)]


def test_autolink():
    assert targets("see <https://example.com> now\n") == [("https://example.com", 1)]


def test_code_fences_are_ignored():
    text = "```\n[fake](nope.md)\n```\n[real](yes.md)\n"
    assert targets(text) == [("yes.md", 4)]


def test_inline_code_is_ignored():
    text = "use `[x](nope.md)` here\n"
    assert targets(text) == []


def test_line_numbers_tracked():
    text = "# Title\n\nSome text\n\n[link](a.md)\n"
    assert targets(text) == [("a.md", 5)]


def test_slugify_github_style():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("  API & Usage  ") == "api-usage"
    assert slugify("C++ Guide") == "c-guide"
    assert slugify("What's New?") == "whats-new"


def test_heading_slugs_dedupe_like_github():
    text = "# Intro\n## Intro\n### Intro\n"
    assert heading_slugs(text) == {"intro", "intro-1", "intro-2"}


def test_heading_slugs_ignore_code_fences():
    text = "```\n# Not a heading\n```\n# Real\n"
    assert heading_slugs(text) == {"real"}
