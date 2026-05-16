import re
import shutil
from datetime import datetime
from pathlib import Path

from ..models import Book, Chapter, Document

CODEX_ROOT = Path.home() / "Codex"


class StorageError(Exception):
    pass


class StorageService:
    """Filesystem operations for ~/Codex/Book/Chapter/document.md hierarchy."""

    def __init__(self, root: Path = CODEX_ROOT):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ books

    def create_book(self, name: str) -> Book:
        slug = self._sanitize(name)
        path = self.root / slug
        if path.exists():
            raise StorageError(f"Ya existe un libro con ese nombre: '{name}'")
        path.mkdir()
        now = datetime.now()
        return Book(name=name, path=path, created_at=now, updated_at=now)

    def list_books(self) -> list[Book]:
        books = []
        for p in sorted(self.root.iterdir()):
            if p.is_dir() and not p.name.startswith("."):
                books.append(Book(name=self._unsanitize(p.name), path=p))
        return books

    def rename_book(self, book: Book, new_name: str) -> Book:
        new_slug = self._sanitize(new_name)
        new_path = self.root / new_slug
        if new_path.exists():
            raise StorageError(f"Ya existe un libro con ese nombre: '{new_name}'")
        book.path.rename(new_path)
        return Book(
            name=new_name,
            path=new_path,
            id=book.id,
            created_at=book.created_at,
            updated_at=datetime.now(),
        )

    def delete_book(self, book: Book) -> None:
        if book.path.exists():
            shutil.rmtree(book.path)

    # --------------------------------------------------------------- chapters

    def create_chapter(self, book: Book, name: str) -> Chapter:
        slug = self._sanitize(name)
        path = book.path / slug
        if path.exists():
            raise StorageError(f"Ya existe un capítulo con ese nombre: '{name}'")
        try:
            path.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            raise StorageError(f"No se pudo crear el capítulo: {exc}") from exc
        now = datetime.now()
        return Chapter(
            name=name, path=path, book_id=book.id, created_at=now, updated_at=now
        )

    def list_chapters(self, book: Book) -> list[Chapter]:
        if not book.path.exists():
            return []
        chapters = []
        for p in sorted(book.path.iterdir()):
            if p.is_dir() and not p.name.startswith("."):
                chapters.append(
                    Chapter(name=self._unsanitize(p.name), path=p, book_id=book.id)
                )
        return chapters

    def rename_chapter(self, chapter: Chapter, new_name: str) -> Chapter:
        new_slug = self._sanitize(new_name)
        new_path = chapter.path.parent / new_slug
        if new_path.exists():
            raise StorageError(f"Ya existe un capítulo con ese nombre: '{new_name}'")
        chapter.path.rename(new_path)
        return Chapter(
            name=new_name,
            path=new_path,
            book_id=chapter.book_id,
            id=chapter.id,
            created_at=chapter.created_at,
            updated_at=datetime.now(),
        )

    def delete_chapter(self, chapter: Chapter) -> None:
        if chapter.path.exists():
            shutil.rmtree(chapter.path)

    # -------------------------------------------------------------- documents

    def create_document(self, chapter: Chapter, name: str) -> Document:
        slug = self._sanitize(name)
        path = chapter.path / f"{slug}.md"
        if path.exists():
            raise StorageError(f"Ya existe un documento con ese nombre: '{name}'")
        try:
            chapter.path.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {name}\n\n", encoding="utf-8")
        except OSError as exc:
            raise StorageError(f"No se pudo crear el documento: {exc}") from exc
        now = datetime.now()
        return Document(
            name=name, path=path, chapter_id=chapter.id, created_at=now, updated_at=now
        )

    def list_documents(self, chapter: Chapter) -> list[Document]:
        if not chapter.path.exists():
            return []
        docs = []
        for p in sorted(chapter.path.iterdir()):
            if p.is_file() and p.suffix == ".md":
                docs.append(
                    Document(
                        name=self._unsanitize(p.stem),
                        path=p,
                        chapter_id=chapter.id,
                    )
                )
        return docs

    def rename_document(self, doc: Document, new_name: str) -> Document:
        new_slug = self._sanitize(new_name)
        new_path = doc.path.parent / f"{new_slug}.md"
        if new_path.exists():
            raise StorageError(f"Ya existe un documento con ese nombre: '{new_name}'")
        doc.path.rename(new_path)
        return Document(
            name=new_name,
            path=new_path,
            chapter_id=doc.chapter_id,
            id=doc.id,
            word_count=doc.word_count,
            is_favorite=doc.is_favorite,
            created_at=doc.created_at,
            updated_at=datetime.now(),
        )

    def delete_document(self, doc: Document) -> None:
        if doc.path.exists():
            doc.path.unlink()

    def read_document(self, doc: Document) -> str:
        return doc.path.read_text(encoding="utf-8")

    def write_document(self, doc: Document, content: str) -> None:
        doc.path.write_text(content, encoding="utf-8")
        doc.updated_at = datetime.now()
        doc.word_count = len(content.split())

    # ----------------------------------------------------------------- utils

    @staticmethod
    def _sanitize(name: str) -> str:
        """Convert display name to filesystem-safe slug."""
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
        cleaned = re.sub(r"\s+", "_", cleaned.strip())
        return cleaned or "sin_titulo"

    @staticmethod
    def _unsanitize(slug: str) -> str:
        """Convert filesystem slug back to a readable name."""
        return slug.replace("_", " ")
