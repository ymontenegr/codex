from pathlib import Path
from datetime import datetime
from src.models import Book, Chapter, Document


def test_book_path_coercion(tmp_path):
    b = Book(name="Test", path=str(tmp_path))
    assert isinstance(b.path, Path)


def test_book_defaults():
    b = Book(name="X", path=Path("/tmp/x"))
    assert b.id == 0
    assert isinstance(b.created_at, datetime)


def test_chapter_defaults():
    c = Chapter(name="C", path=Path("/tmp/c"))
    assert c.id == 0
    assert c.book_id == 0


def test_document_defaults():
    d = Document(name="D", path=Path("/tmp/d.md"))
    assert d.id == 0
    assert d.word_count == 0
    assert d.is_favorite is False
