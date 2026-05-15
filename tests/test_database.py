import pytest
from pathlib import Path
from src.services.database import Database
from src.models import Book, Chapter, Document


@pytest.fixture
def db(tmp_path):
    d = Database(db_path=tmp_path / "test.db")
    d.connect()
    yield d
    d.close()


# ------------------------------------------------------------------- books

def test_add_and_get_book(db, tmp_path):
    book = Book(name="Mi Libro", path=tmp_path / "Mi_Libro")
    db.add_book(book)
    assert book.id > 0

    books = db.get_books()
    assert len(books) == 1
    assert books[0].name == "Mi Libro"
    assert books[0].id == book.id


def test_update_book(db, tmp_path):
    book = Book(name="Original", path=tmp_path / "Original")
    db.add_book(book)
    book.name = "Actualizado"
    db.update_book(book)

    books = db.get_books()
    assert books[0].name == "Actualizado"


def test_delete_book_cascades(db, tmp_path):
    book = Book(name="A", path=tmp_path / "A")
    db.add_book(book)
    chapter = Chapter(name="Cap", path=tmp_path / "A" / "Cap", book_id=book.id)
    db.add_chapter(chapter)
    doc = Document(name="Doc", path=tmp_path / "A" / "Cap" / "doc.md", chapter_id=chapter.id)
    db.add_document(doc)

    db.delete_book(book.id)

    assert db.get_books() == []
    assert db.get_chapters(book.id) == []
    assert db.get_documents(chapter.id) == []


# --------------------------------------------------------------- chapters

def test_add_and_get_chapter(db, tmp_path):
    book = Book(name="B", path=tmp_path / "B")
    db.add_book(book)

    ch = Chapter(name="Cap 1", path=tmp_path / "B" / "Cap_1", book_id=book.id)
    db.add_chapter(ch)
    assert ch.id > 0

    chapters = db.get_chapters(book.id)
    assert len(chapters) == 1
    assert chapters[0].name == "Cap 1"


def test_update_chapter(db, tmp_path):
    book = Book(name="B", path=tmp_path / "B")
    db.add_book(book)
    ch = Chapter(name="Viejo", path=tmp_path / "B" / "Viejo", book_id=book.id)
    db.add_chapter(ch)

    ch.name = "Nuevo"
    db.update_chapter(ch)
    assert db.get_chapters(book.id)[0].name == "Nuevo"


def test_delete_chapter(db, tmp_path):
    book = Book(name="B", path=tmp_path / "B")
    db.add_book(book)
    ch = Chapter(name="C", path=tmp_path / "B" / "C", book_id=book.id)
    db.add_chapter(ch)
    db.delete_chapter(ch.id)
    assert db.get_chapters(book.id) == []


# -------------------------------------------------------------- documents

def _make_hierarchy(db, tmp_path):
    book = Book(name="B", path=tmp_path / "B")
    db.add_book(book)
    ch = Chapter(name="C", path=tmp_path / "B" / "C", book_id=book.id)
    db.add_chapter(ch)
    return book, ch


def test_add_and_get_document(db, tmp_path):
    _, ch = _make_hierarchy(db, tmp_path)
    doc = Document(name="Intro", path=tmp_path / "B" / "C" / "Intro.md", chapter_id=ch.id)
    db.add_document(doc)
    assert doc.id > 0

    docs = db.get_documents(ch.id)
    assert len(docs) == 1
    assert docs[0].name == "Intro"


def test_update_document(db, tmp_path):
    _, ch = _make_hierarchy(db, tmp_path)
    doc = Document(name="D", path=tmp_path / "B" / "C" / "D.md", chapter_id=ch.id)
    db.add_document(doc)
    doc.word_count = 42
    doc.is_favorite = True
    db.update_document(doc)

    updated = db.get_documents(ch.id)[0]
    assert updated.word_count == 42
    assert updated.is_favorite is True


def test_delete_document(db, tmp_path):
    _, ch = _make_hierarchy(db, tmp_path)
    doc = Document(name="D", path=tmp_path / "B" / "C" / "D.md", chapter_id=ch.id)
    db.add_document(doc)
    db.delete_document(doc.id)
    assert db.get_documents(ch.id) == []


def test_fts_search(db, tmp_path):
    _, ch = _make_hierarchy(db, tmp_path)
    doc = Document(name="Python Tips", path=tmp_path / "B" / "C" / "tips.md", chapter_id=ch.id)
    db.add_document(doc)
    db.index_document_content(doc, "Python es un lenguaje de programación versátil")

    results = db.search("python")
    assert len(results) == 1
    assert results[0].name == "Python Tips"


def test_fts_no_results(db, tmp_path):
    results = db.search("xyznotfound")
    assert results == []


def test_record_open(db, tmp_path):
    _, ch = _make_hierarchy(db, tmp_path)
    doc = Document(name="D", path=tmp_path / "B" / "C" / "D.md", chapter_id=ch.id)
    db.add_document(doc)
    db.record_open(doc)
    row = db.conn.execute("SELECT * FROM history WHERE document_id=?", (doc.id,)).fetchone()
    assert row is not None
