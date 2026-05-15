"""Sprint 5 tests: Exporter (MD/TXT), tag CRUD, template loading."""
import pytest
from pathlib import Path

from src.services import StorageService, Database, Exporter, ExportError

_gi_available = False
try:
    import gi  # noqa: F401
    _gi_available = True
except ImportError:
    pass

requires_gi = pytest.mark.skipif(
    not _gi_available, reason="gi (PyGObject) not in venv"
)


@pytest.fixture
def env(tmp_path):
    storage = StorageService(root=tmp_path / "Codex")
    db = Database(db_path=tmp_path / "codex.db")
    db.connect()

    book = storage.create_book("Book")
    db.add_book(book)
    ch = storage.create_chapter(book, "Chapter")
    db.add_chapter(ch)

    doc = storage.create_document(ch, "Doc")
    db.add_document(doc)
    storage.write_document(doc, "# Hello\n\n**World**")

    yield storage, db, book, ch, doc
    db.close()


# ── Exporter: MD ─────────────────────────────────────────────────────────────

def test_export_md_creates_file(env, tmp_path):
    storage, db, book, ch, doc = env
    dest = tmp_path / "out.md"
    Exporter(storage, db).export(doc, "md", dest)
    assert dest.exists()


def test_export_md_content_matches(env, tmp_path):
    storage, db, book, ch, doc = env
    dest = tmp_path / "out.md"
    Exporter(storage, db).export(doc, "md", dest)
    assert dest.read_text() == "# Hello\n\n**World**"


# ── Exporter: TXT ────────────────────────────────────────────────────────────

def test_export_txt_creates_file(env, tmp_path):
    storage, db, book, ch, doc = env
    dest = tmp_path / "out.txt"
    Exporter(storage, db).export(doc, "txt", dest)
    assert dest.exists()


def test_export_txt_strips_markdown(env, tmp_path):
    storage, db, book, ch, doc = env
    dest = tmp_path / "out.txt"
    Exporter(storage, db).export(doc, "txt", dest)
    content = dest.read_text()
    assert "#" not in content
    assert "**" not in content
    assert "Hello" in content
    assert "World" in content


# ── Exporter: Chapter scope ───────────────────────────────────────────────────

def test_export_chapter_md_includes_all_docs(env, tmp_path):
    storage, db, book, ch, doc = env
    doc2 = storage.create_document(ch, "Doc 2")
    db.add_document(doc2)
    storage.write_document(doc2, "Second doc content")
    dest = tmp_path / "ch.md"
    Exporter(storage, db).export(ch, "md", dest)
    content = dest.read_text()
    assert "Hello" in content
    assert "Second doc content" in content


# ── Exporter: Book scope ──────────────────────────────────────────────────────

def test_export_book_md_includes_chapters(env, tmp_path):
    storage, db, book, ch, doc = env
    dest = tmp_path / "book.md"
    Exporter(storage, db).export(book, "md", dest)
    content = dest.read_text()
    assert book.name in content
    assert "Hello" in content


# ── Exporter: unknown format ──────────────────────────────────────────────────

def test_export_unknown_format_raises(env, tmp_path):
    storage, db, book, ch, doc = env
    with pytest.raises(ExportError):
        Exporter(storage, db).export(doc, "rtf", tmp_path / "out.rtf")


# ── Exporter: PDF (skip if pypandoc absent, tolerate engine absence) ──────────

def test_export_pdf_does_not_crash(env, tmp_path):
    pytest.importorskip("pypandoc")
    storage, db, book, ch, doc = env
    dest = tmp_path / "out.pdf"
    try:
        Exporter(storage, db).export(doc, "pdf", dest)
    except ExportError:
        pass  # no PDF engine available — acceptable in CI


# ── Tags: CRUD ────────────────────────────────────────────────────────────────

def test_get_or_create_tag_creates(env):
    _, db, book, ch, doc = env
    tag = db.get_or_create_tag("python")
    assert tag.id is not None
    assert tag.name == "python"


def test_get_or_create_tag_idempotent(env):
    _, db, book, ch, doc = env
    t1 = db.get_or_create_tag("python")
    t2 = db.get_or_create_tag("python")
    assert t1.id == t2.id


def test_add_tag_to_doc(env):
    _, db, book, ch, doc = env
    tag = db.get_or_create_tag("alpha")
    db.add_tag_to_doc(doc.id, tag)
    tags = db.get_doc_tags(doc.id)
    assert any(t.name == "alpha" for t in tags)


def test_add_tag_to_doc_duplicate_no_error(env):
    _, db, book, ch, doc = env
    tag = db.get_or_create_tag("beta")
    db.add_tag_to_doc(doc.id, tag)
    db.add_tag_to_doc(doc.id, tag)
    tags = db.get_doc_tags(doc.id)
    assert sum(1 for t in tags if t.name == "beta") == 1


def test_remove_tag_from_doc(env):
    _, db, book, ch, doc = env
    tag = db.get_or_create_tag("remove-me")
    db.add_tag_to_doc(doc.id, tag)
    db.remove_tag_from_doc(doc.id, tag.id)
    tags = db.get_doc_tags(doc.id)
    assert not any(t.name == "remove-me" for t in tags)


def test_get_doc_tags_empty_initially(env):
    _, db, book, ch, doc = env
    assert db.get_doc_tags(doc.id) == []


def test_get_all_tags_with_count(env):
    _, db, book, ch, doc = env
    tag = db.get_or_create_tag("counted")
    db.add_tag_to_doc(doc.id, tag)
    all_tags = db.get_all_tags()
    entry = next((t for t, c in all_tags if t.name == "counted"), None)
    assert entry is not None


def test_delete_unused_tags_removes_orphans(env):
    _, db, book, ch, doc = env
    db.get_or_create_tag("orphan")  # created but not linked to any doc
    db.delete_unused_tags()
    all_tags = db.get_all_tags()
    assert not any(t.name == "orphan" for t, _ in all_tags)


def test_get_docs_by_tag(env):
    _, db, book, ch, doc = env
    tag = db.get_or_create_tag("findme")
    db.add_tag_to_doc(doc.id, tag)
    docs = db.get_docs_by_tag(tag.id)
    assert any(d.id == doc.id for d in docs)


# ── TemplateDialog: static helpers ───────────────────────────────────────────

@requires_gi
def test_load_content_empty_returns_string():
    from src.widgets.template_dialog import TemplateDialog
    content = TemplateDialog.load_content("empty")
    assert isinstance(content, str)


@requires_gi
def test_load_content_meeting_not_empty():
    from src.widgets.template_dialog import TemplateDialog
    content = TemplateDialog.load_content("meeting")
    assert len(content) > 0


@requires_gi
def test_load_content_unknown_key_returns_empty():
    from src.widgets.template_dialog import TemplateDialog
    content = TemplateDialog.load_content("nonexistent_key_xyz")
    assert content == ""


@requires_gi
def test_template_keys_contains_all():
    from src.widgets.template_dialog import TemplateDialog
    keys = TemplateDialog.template_keys()
    for expected in ("empty", "meeting", "article", "analysis", "readme"):
        assert expected in keys
