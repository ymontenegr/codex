"""Sprint 4 tests: strip_markdown, favorites, recent documents, FTS search."""
import pytest
from pathlib import Path

from src.utils.markdown_parser import strip_markdown
from src.services import StorageService, Database
from src.services.indexer import Indexer


# ── strip_markdown ────────────────────────────────────────────────────────────

def test_strip_heading():
    assert strip_markdown("# Hello World") == "Hello World"


def test_strip_subheadings():
    result = strip_markdown("## Section\n### Subsection")
    assert "Section" in result
    assert "Subsection" in result
    assert "#" not in result


def test_strip_bold():
    assert strip_markdown("**bold text**") == "bold text"


def test_strip_italic():
    assert strip_markdown("*italic text*") == "italic text"


def test_strip_inline_code():
    assert strip_markdown("`some code`") == "some code"


def test_strip_crossrefs():
    assert strip_markdown("See [[Other Doc]] for details.") == "See Other Doc for details."


def test_strip_link():
    assert strip_markdown("[click here](https://example.com)") == "click here"


def test_strip_unordered_list():
    result = strip_markdown("- item one\n- item two")
    assert "item one" in result
    assert "item two" in result
    assert "- " not in result


def test_strip_ordered_list():
    result = strip_markdown("1. first\n2. second")
    assert "first" in result
    assert "1." not in result


def test_strip_blockquote():
    result = strip_markdown("> quoted text")
    assert "quoted text" in result
    assert ">" not in result


def test_strip_empty():
    assert strip_markdown("") == ""


def test_strip_plain_text_unchanged():
    text = "Just plain text here."
    assert strip_markdown(text) == text


def test_strip_fenced_code_block():
    md = "```python\nprint('hello')\n```"
    result = strip_markdown(md)
    assert "```" not in result


# ── Database: favorites ───────────────────────────────────────────────────────

@pytest.fixture
def env(tmp_path):
    storage = StorageService(root=tmp_path / "Codex")
    db = Database(db_path=tmp_path / "codex.db")
    db.connect()

    book = storage.create_book("Book")
    db.add_book(book)
    ch = storage.create_chapter(book, "Chapter")
    db.add_chapter(ch)

    doc_a = storage.create_document(ch, "Doc A")
    db.add_document(doc_a)
    doc_b = storage.create_document(ch, "Doc B")
    db.add_document(doc_b)

    yield storage, db, {"a": doc_a, "b": doc_b}
    db.close()


def test_toggle_favorite_sets_true(env):
    _, db, docs = env
    result = db.toggle_favorite(docs["a"])
    assert result is True
    assert docs["a"].is_favorite is True


def test_toggle_favorite_unsets(env):
    _, db, docs = env
    db.toggle_favorite(docs["a"])
    result = db.toggle_favorite(docs["a"])
    assert result is False
    assert docs["a"].is_favorite is False


def test_get_favorites_returns_only_favorited(env):
    _, db, docs = env
    db.toggle_favorite(docs["a"])
    favs = db.get_favorites()
    ids = {d.id for d in favs}
    assert docs["a"].id in ids
    assert docs["b"].id not in ids


def test_get_favorites_empty_initially(env):
    _, db, _ = env
    assert db.get_favorites() == []


# ── Database: recent documents ────────────────────────────────────────────────

def test_get_recent_empty_initially(env):
    _, db, _ = env
    assert db.get_recent_documents() == []


def test_get_recent_returns_opened_docs(env):
    _, db, docs = env
    db.record_open(docs["a"])
    recents = db.get_recent_documents()
    assert any(d.id == docs["a"].id for d in recents)


def test_get_recent_deduplicates(env):
    _, db, docs = env
    db.record_open(docs["a"])
    db.record_open(docs["a"])
    recents = db.get_recent_documents()
    assert sum(1 for d in recents if d.id == docs["a"].id) == 1


def test_get_recent_ordered_by_most_recent(env):
    _, db, docs = env
    db.record_open(docs["a"])
    db.record_open(docs["b"])
    recents = db.get_recent_documents()
    assert recents[0].id == docs["b"].id


def test_get_recent_respects_limit(env):
    _, db, docs = env
    db.record_open(docs["a"])
    db.record_open(docs["b"])
    recents = db.get_recent_documents(limit=1)
    assert len(recents) == 1


# ── Database: search_fts ──────────────────────────────────────────────────────

def test_search_fts_empty_query_returns_empty(env):
    _, db, _ = env
    assert db.search_fts("") == []


def test_search_fts_finds_indexed_content(env):
    storage, db, docs = env
    db.index_document_content(docs["a"], "The quick brown fox")
    results = db.search_fts("quick")
    assert any(r["doc"].id == docs["a"].id for r in results)


def test_search_fts_no_match_returns_empty(env):
    _, db, docs = env
    db.index_document_content(docs["a"], "The quick brown fox")
    results = db.search_fts("elephant")
    assert results == []


def test_search_fts_result_has_expected_keys(env):
    _, db, docs = env
    db.index_document_content(docs["a"], "Some content here")
    results = db.search_fts("content")
    assert results
    r = results[0]
    assert "doc" in r
    assert "chapter_name" in r
    assert "book_name" in r
    assert "snippet" in r


def test_search_fts_snippet_marks_match(env):
    _, db, docs = env
    db.index_document_content(docs["a"], "The quick brown fox jumps")
    results = db.search_fts("quick")
    assert results
    snip = results[0]["snippet"]
    # \x02 and \x03 are the highlight markers from char(2)/char(3)
    assert "\x02" in snip or "quick" in snip


def test_search_fts_special_chars_in_query_no_crash(env):
    _, db, docs = env
    db.index_document_content(docs["a"], "hello world")
    # These should not raise even if FTS syntax would normally be invalid
    assert db.search_fts('hello "AND" OR') is not None
    assert db.search_fts("()[]{}") is not None


# ── Indexer: update_content_index ────────────────────────────────────────────

def test_update_content_index_strips_markdown(env):
    storage, db, docs = env
    indexer = Indexer(db, storage)
    indexer.update_content_index(docs["a"], "# Heading\n**bold** content")
    results = db.search_fts("bold")
    assert any(r["doc"].id == docs["a"].id for r in results)


def test_update_content_index_excludes_markdown_symbols(env):
    storage, db, docs = env
    indexer = Indexer(db, storage)
    indexer.update_content_index(docs["a"], "# My Title")
    # The '#' should not appear in the indexed content
    row = db.conn.execute(
        "SELECT content_index FROM documents WHERE id=?", (docs["a"].id,)
    ).fetchone()
    assert row and "#" not in (row["content_index"] or "")
