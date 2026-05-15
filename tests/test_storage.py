import pytest
from pathlib import Path
from src.services.storage import StorageService, StorageError
from src.models import Book, Chapter, Document


@pytest.fixture
def storage(tmp_path):
    return StorageService(root=tmp_path / "Codex")


# ------------------------------------------------------------------- books

def test_create_book(storage):
    book = storage.create_book("Mi Libro")
    assert isinstance(book, Book)
    assert book.path.exists()
    assert book.path.is_dir()
    assert book.name == "Mi Libro"


def test_create_book_slug(storage):
    book = storage.create_book("Mi Libro con Espacios")
    assert book.path.name == "Mi_Libro_con_Espacios"


def test_create_book_duplicate_raises(storage):
    storage.create_book("Dupl")
    with pytest.raises(StorageError):
        storage.create_book("Dupl")


def test_list_books_empty(storage):
    assert storage.list_books() == []


def test_list_books(storage):
    storage.create_book("Libro A")
    storage.create_book("Libro B")
    books = storage.list_books()
    assert len(books) == 2
    assert all(isinstance(b, Book) for b in books)


def test_rename_book(storage):
    book = storage.create_book("Original")
    renamed = storage.rename_book(book, "Renombrado")
    assert renamed.name == "Renombrado"
    assert renamed.path.exists()
    assert not book.path.exists()


def test_rename_book_conflict_raises(storage):
    b1 = storage.create_book("A")
    storage.create_book("B")
    with pytest.raises(StorageError):
        storage.rename_book(b1, "B")


def test_delete_book(storage):
    book = storage.create_book("Para Borrar")
    storage.delete_book(book)
    assert not book.path.exists()
    assert storage.list_books() == []


# --------------------------------------------------------------- chapters

@pytest.fixture
def book(storage):
    return storage.create_book("Libro")


def test_create_chapter(storage, book):
    ch = storage.create_chapter(book, "Capítulo 1")
    assert isinstance(ch, Chapter)
    assert ch.path.exists()
    assert ch.name == "Capítulo 1"


def test_list_chapters(storage, book):
    storage.create_chapter(book, "Cap A")
    storage.create_chapter(book, "Cap B")
    chapters = storage.list_chapters(book)
    assert len(chapters) == 2


def test_rename_chapter(storage, book):
    ch = storage.create_chapter(book, "Viejo")
    new_ch = storage.rename_chapter(ch, "Nuevo")
    assert new_ch.name == "Nuevo"
    assert new_ch.path.exists()
    assert not ch.path.exists()


def test_delete_chapter(storage, book):
    ch = storage.create_chapter(book, "Borrar")
    storage.delete_chapter(ch)
    assert not ch.path.exists()


# -------------------------------------------------------------- documents

@pytest.fixture
def chapter(storage, book):
    return storage.create_chapter(book, "Capítulo")


def test_create_document(storage, chapter):
    doc = storage.create_document(chapter, "Introducción")
    assert isinstance(doc, Document)
    assert doc.path.exists()
    assert doc.path.suffix == ".md"
    assert doc.name == "Introducción"


def test_document_initial_content(storage, chapter):
    doc = storage.create_document(chapter, "Mi Nota")
    content = storage.read_document(doc)
    assert "# Mi Nota" in content


def test_list_documents(storage, chapter):
    storage.create_document(chapter, "Doc 1")
    storage.create_document(chapter, "Doc 2")
    docs = storage.list_documents(chapter)
    assert len(docs) == 2
    assert all(isinstance(d, Document) for d in docs)


def test_write_and_read_document(storage, chapter):
    doc = storage.create_document(chapter, "Test")
    storage.write_document(doc, "# Test\n\nContenido de prueba.")
    content = storage.read_document(doc)
    assert "Contenido de prueba" in content


def test_write_updates_word_count(storage, chapter):
    doc = storage.create_document(chapter, "WC")
    storage.write_document(doc, "uno dos tres cuatro")
    assert doc.word_count == 4


def test_rename_document(storage, chapter):
    doc = storage.create_document(chapter, "Borrador")
    new_doc = storage.rename_document(doc, "Final")
    assert new_doc.name == "Final"
    assert new_doc.path.suffix == ".md"
    assert new_doc.path.exists()
    assert not doc.path.exists()


def test_delete_document(storage, chapter):
    doc = storage.create_document(chapter, "Efímero")
    storage.delete_document(doc)
    assert not doc.path.exists()


def test_sanitize_strips_dangerous_chars(storage):
    book = storage.create_book('Libro: "peligroso"')
    assert ":" not in book.path.name
    assert '"' not in book.path.name
