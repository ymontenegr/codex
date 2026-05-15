"""Sprint 2 Task 9 — verify that saved content round-trips as valid Markdown.

These tests exercise the Python side of the editor: the _inject_content
escaping logic and the StorageService round-trip. They do NOT require GTK or
WebKit because the widget is not instantiated.
"""

import re
import tempfile
from pathlib import Path

import pytest

from src.services import StorageService
from src.models import Document


# ── Helpers that mirror editor.py's _inject_content escaping ─────────────────

def _escape_for_js_template_literal(text: str) -> str:
    """Replicate CodexEditorWidget._inject_content escaping."""
    return (
        text
        .replace("\\", "\\\\")
        .replace("`",  "\\`")
        .replace("$",  "\\$")
    )


# ── Markdown validity heuristics ──────────────────────────────────────────────

_HEADING_RE  = re.compile(r'^#{1,3} .+', re.MULTILINE)
_BOLD_RE     = re.compile(r'\*\*.+?\*\*')
_ITALIC_RE   = re.compile(r'\*.+?\*')
_CODE_RE     = re.compile(r'`[^`]+`')
_LINK_RE     = re.compile(r'\[.+?\]\(.+?\)')
_UL_RE       = re.compile(r'^- .+', re.MULTILINE)
_OL_RE       = re.compile(r'^\d+\. .+', re.MULTILINE)


def _is_valid_markdown(text: str) -> bool:
    """Return True if *text* looks like well-formed Markdown (no raw HTML tags)."""
    if re.search(r'<(?!br\b)[a-z]+[^>]*>', text, re.IGNORECASE):
        return False      # unexpected HTML tags leaked into the output
    return True


# ── JS template-literal escaping tests ───────────────────────────────────────

class TestInjectContentEscaping:
    def test_backtick_escaped(self):
        escaped = _escape_for_js_template_literal("use `code` here")
        assert "\\`" in escaped
        assert "`code`" not in escaped

    def test_dollar_sign_escaped(self):
        escaped = _escape_for_js_template_literal("price ${100}")
        assert "\\$" in escaped

    def test_backslash_doubled(self):
        escaped = _escape_for_js_template_literal("path\\to\\file")
        assert "\\\\" in escaped

    def test_plain_text_unchanged(self):
        plain = "Hello world, this is a test."
        assert _escape_for_js_template_literal(plain) == plain

    def test_combined_special_chars(self):
        src = "Use `$var` and C:\\path"
        esc = _escape_for_js_template_literal(src)
        assert "\\`" in esc
        assert "\\$" in esc
        assert "\\\\" in esc


# ── Markdown structural validity ──────────────────────────────────────────────

class TestMarkdownValidity:
    """Simulate the content a user would write and verify it stays clean MD."""

    def _sample_docs(self):
        return [
            "# My Title\n\nSome **bold** and *italic* text.\n",
            "## Chapter\n\n- item one\n- item two\n\n1. first\n2. second\n",
            "Inline `code` and a [link](https://example.com).\n",
            "Plain paragraph with no special formatting.\n",
            "### Deep heading\n\n**Bold** start, then `code`, then *italic*.\n",
        ]

    def test_no_html_tags_in_sample_docs(self):
        for doc in self._sample_docs():
            assert _is_valid_markdown(doc), f"Invalid MD: {doc!r}"

    def test_heading_pattern_recognized(self):
        md = "# Title\n\nBody text.\n"
        assert _HEADING_RE.search(md)

    def test_bold_pattern_recognized(self):
        assert _BOLD_RE.search("This is **bold** text.")

    def test_italic_pattern_recognized(self):
        assert _ITALIC_RE.search("This is *italic* text.")

    def test_inline_code_recognized(self):
        assert _CODE_RE.search("Use `print()` function.")

    def test_link_recognized(self):
        assert _LINK_RE.search("[Codex](https://github.com/ymontenegr/codex)")

    def test_unordered_list_recognized(self):
        assert _UL_RE.search("- first item\n- second item")

    def test_ordered_list_recognized(self):
        assert _OL_RE.search("1. step one\n2. step two")


# ── StorageService round-trip ─────────────────────────────────────────────────

@pytest.fixture()
def tmp_storage(tmp_path):
    return StorageService(root=tmp_path / "Codex")


@pytest.fixture()
def sample_doc(tmp_storage):
    book    = tmp_storage.create_book("TestBook")
    chapter = tmp_storage.create_chapter(book, "Chapter1")
    doc     = tmp_storage.create_document(chapter, "MyDoc")
    return doc


class TestStorageRoundTrip:
    def test_write_and_read_produces_same_content(self, tmp_storage, sample_doc):
        content = "# Hello\n\nSome **bold** text.\n"
        tmp_storage.write_document(sample_doc, content)
        read_back = tmp_storage.read_document(sample_doc)
        assert read_back == content

    def test_saved_content_has_no_html_tags(self, tmp_storage, sample_doc):
        content = "# Heading\n\nParagraph with `code`.\n"
        tmp_storage.write_document(sample_doc, content)
        read_back = tmp_storage.read_document(sample_doc)
        assert _is_valid_markdown(read_back)

    def test_special_chars_preserved(self, tmp_storage, sample_doc):
        content = "Use `$var` and C:\\\\path and backtick \\`.\n"
        tmp_storage.write_document(sample_doc, content)
        read_back = tmp_storage.read_document(sample_doc)
        assert read_back == content

    def test_unicode_content_preserved(self, tmp_storage, sample_doc):
        content = "# Título\n\nContenido con acentos: áéíóú ñ.\n"
        tmp_storage.write_document(sample_doc, content)
        read_back = tmp_storage.read_document(sample_doc)
        assert read_back == content

    def test_multiline_content_preserved(self, tmp_storage, sample_doc):
        content = "# H1\n\n## H2\n\n- a\n- b\n\n1. x\n2. y\n"
        tmp_storage.write_document(sample_doc, content)
        read_back = tmp_storage.read_document(sample_doc)
        assert read_back == content
