import pytest
from pathlib import Path

from src.services import StorageService, Database
from src.services.indexer import Indexer


@pytest.fixture
def env(tmp_path):
    """Set up storage + db with three documents (A, B, C) under one book/chapter."""
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
    doc_c = storage.create_document(ch, "Doc C")
    db.add_document(doc_c)

    yield storage, db, {"a": doc_a, "b": doc_b, "c": doc_c}
    db.close()


# ── Indexer.index_document ────────────────────────────────────────────────────

def test_index_creates_link(env):
    storage, db, docs = env
    Indexer(db, storage).index_document(docs["a"], "See [[Doc B]] for details.")
    backlinks = db.get_backlinks(docs["b"].id)
    assert any(d.id == docs["a"].id for d in backlinks)


def test_index_missing_target_creates_no_link(env):
    storage, db, docs = env
    Indexer(db, storage).index_document(docs["a"], "See [[Nonexistent Doc]].")
    assert db.get_backlinks(docs["a"].id) == []


def test_index_clears_old_links(env):
    storage, db, docs = env
    indexer = Indexer(db, storage)
    indexer.index_document(docs["a"], "See [[Doc B]].")
    assert db.get_backlinks(docs["b"].id)

    # Re-index pointing to C instead
    indexer.index_document(docs["a"], "Now [[Doc C]].")
    assert not db.get_backlinks(docs["b"].id)
    assert db.get_backlinks(docs["c"].id)


def test_index_multiple_refs(env):
    storage, db, docs = env
    Indexer(db, storage).index_document(docs["a"], "See [[Doc B]] and [[Doc C]].")
    assert db.get_backlinks(docs["b"].id)
    assert db.get_backlinks(docs["c"].id)


def test_self_reference_ignored(env):
    storage, db, docs = env
    Indexer(db, storage).index_document(docs["a"], "Self-ref [[Doc A]].")
    backlinks = db.get_backlinks(docs["a"].id)
    assert not any(d.id == docs["a"].id for d in backlinks)


def test_index_no_refs_clears_previous(env):
    storage, db, docs = env
    indexer = Indexer(db, storage)
    indexer.index_document(docs["a"], "Points to [[Doc B]].")
    assert db.get_backlinks(docs["b"].id)

    indexer.index_document(docs["a"], "No references here.")
    assert not db.get_backlinks(docs["b"].id)


# ── Indexer.reindex_all ───────────────────────────────────────────────────────

def test_reindex_all(env):
    storage, db, docs = env
    storage.write_document(docs["a"], "Points to [[Doc B]].")
    storage.write_document(docs["b"], "Points to [[Doc C]].")
    storage.write_document(docs["c"], "No references here.")

    Indexer(db, storage).reindex_all()

    assert db.get_backlinks(docs["b"].id)
    assert db.get_backlinks(docs["c"].id)
    assert not db.get_backlinks(docs["a"].id)


# ── Database link helpers ─────────────────────────────────────────────────────

def test_get_all_documents_returns_all(env):
    _, db, docs = env
    all_docs = db.get_all_documents()
    ids = {d.id for d in all_docs}
    assert docs["a"].id in ids
    assert docs["b"].id in ids
    assert docs["c"].id in ids


def test_get_document_by_name_found(env):
    _, db, docs = env
    found = db.get_document_by_name("Doc B")
    assert found is not None
    assert found.id == docs["b"].id


def test_get_document_by_name_missing(env):
    _, db, _ = env
    assert db.get_document_by_name("Nonexistent") is None


def test_add_and_clear_links(env):
    _, db, docs = env
    db.add_link(docs["a"].id, docs["b"].id)
    assert db.get_backlinks(docs["b"].id)

    db.clear_links_from(docs["a"].id)
    assert not db.get_backlinks(docs["b"].id)


def test_add_link_idempotent(env):
    _, db, docs = env
    db.add_link(docs["a"].id, docs["b"].id)
    db.add_link(docs["a"].id, docs["b"].id)   # duplicate — must not raise
    assert len(db.get_backlinks(docs["b"].id)) == 1
