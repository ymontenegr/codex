import re
import sqlite3
from datetime import datetime
from pathlib import Path

from ..models import Book, Chapter, Document

DB_PATH = Path.home() / ".local" / "share" / "codex" / "codex.db"

_TS_FMT = "%Y-%m-%dT%H:%M:%S.%f"
_TS_FMT_S = "%Y-%m-%dT%H:%M:%S"  # legacy rows without microseconds


def _ts(dt: datetime) -> str:
    return dt.strftime(_TS_FMT)


def _dt(s: str) -> datetime:
    try:
        return datetime.strptime(s, _TS_FMT)
    except ValueError:
        return datetime.strptime(s, _TS_FMT_S)


class Database:
    """SQLite persistence for Codex metadata and full-text search index."""

    SCHEMA = """
    PRAGMA journal_mode = WAL;
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS books (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        folder_path TEXT NOT NULL UNIQUE,
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS chapters (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id     INTEGER NOT NULL,
        name        TEXT NOT NULL,
        folder_path TEXT NOT NULL UNIQUE,
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL,
        FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS documents (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        chapter_id    INTEGER NOT NULL,
        name          TEXT NOT NULL,
        file_path     TEXT NOT NULL UNIQUE,
        content_index TEXT,
        word_count    INTEGER DEFAULT 0,
        is_favorite   INTEGER DEFAULT 0,
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL,
        FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS tags (
        id   INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS document_tags (
        document_id INTEGER NOT NULL,
        tag_id      INTEGER NOT NULL,
        PRIMARY KEY (document_id, tag_id),
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
        FOREIGN KEY (tag_id)      REFERENCES tags(id)      ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS links (
        source_doc_id INTEGER NOT NULL,
        target_doc_id INTEGER NOT NULL,
        PRIMARY KEY (source_doc_id, target_doc_id),
        FOREIGN KEY (source_doc_id) REFERENCES documents(id) ON DELETE CASCADE,
        FOREIGN KEY (target_doc_id) REFERENCES documents(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        opened_at   TEXT NOT NULL,
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
    );

    CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
        name, content_index,
        content='documents', content_rowid='id'
    );
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------ connection

    def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if not self._conn:
            self.connect()
        return self._conn

    # ----------------------------------------------------------------- books

    def add_book(self, book: Book) -> Book:
        now = _ts(datetime.now())
        cur = self.conn.execute(
            "INSERT INTO books (name, folder_path, created_at, updated_at) VALUES (?,?,?,?)",
            (book.name, str(book.path), now, now),
        )
        self.conn.commit()
        book.id = cur.lastrowid
        return book

    def get_books(self) -> list[Book]:
        rows = self.conn.execute(
            "SELECT id, name, folder_path, created_at, updated_at FROM books ORDER BY name"
        ).fetchall()
        return [
            Book(
                id=r["id"],
                name=r["name"],
                path=Path(r["folder_path"]),
                created_at=_dt(r["created_at"]),
                updated_at=_dt(r["updated_at"]),
            )
            for r in rows
        ]

    def get_book_by_id(self, book_id: int) -> "Book | None":
        row = self.conn.execute(
            "SELECT id, name, folder_path, created_at, updated_at FROM books WHERE id=? LIMIT 1",
            (book_id,),
        ).fetchone()
        if not row:
            return None
        return Book(
            id=row["id"],
            name=row["name"],
            path=Path(row["folder_path"]),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    def update_book(self, book: Book) -> None:
        self.conn.execute(
            "UPDATE books SET name=?, folder_path=?, updated_at=? WHERE id=?",
            (book.name, str(book.path), _ts(datetime.now()), book.id),
        )
        self.conn.commit()

    def delete_book(self, book_id: int) -> None:
        self.conn.execute("DELETE FROM books WHERE id=?", (book_id,))
        self.conn.commit()

    # --------------------------------------------------------------- chapters

    def add_chapter(self, chapter: Chapter) -> Chapter:
        now = _ts(datetime.now())
        cur = self.conn.execute(
            "INSERT INTO chapters (book_id, name, folder_path, created_at, updated_at) VALUES (?,?,?,?,?)",
            (chapter.book_id, chapter.name, str(chapter.path), now, now),
        )
        self.conn.commit()
        chapter.id = cur.lastrowid
        return chapter

    def get_chapter_by_id(self, chapter_id: int) -> "Chapter | None":
        row = self.conn.execute(
            "SELECT id, book_id, name, folder_path, created_at, updated_at "
            "FROM chapters WHERE id=? LIMIT 1",
            (chapter_id,),
        ).fetchone()
        if not row:
            return None
        return Chapter(
            id=row["id"],
            book_id=row["book_id"],
            name=row["name"],
            path=Path(row["folder_path"]),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    def get_chapters(self, book_id: int) -> list[Chapter]:
        rows = self.conn.execute(
            "SELECT id, book_id, name, folder_path, created_at, updated_at "
            "FROM chapters WHERE book_id=? ORDER BY name",
            (book_id,),
        ).fetchall()
        return [
            Chapter(
                id=r["id"],
                book_id=r["book_id"],
                name=r["name"],
                path=Path(r["folder_path"]),
                created_at=_dt(r["created_at"]),
                updated_at=_dt(r["updated_at"]),
            )
            for r in rows
        ]

    def update_chapter(self, chapter: Chapter) -> None:
        self.conn.execute(
            "UPDATE chapters SET name=?, folder_path=?, updated_at=? WHERE id=?",
            (chapter.name, str(chapter.path), _ts(datetime.now()), chapter.id),
        )
        self.conn.commit()

    def delete_chapter(self, chapter_id: int) -> None:
        self.conn.execute("DELETE FROM chapters WHERE id=?", (chapter_id,))
        self.conn.commit()

    # -------------------------------------------------------------- documents

    def add_document(self, doc: Document) -> Document:
        now = _ts(datetime.now())
        cur = self.conn.execute(
            "INSERT INTO documents "
            "(chapter_id, name, file_path, word_count, is_favorite, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                doc.chapter_id,
                doc.name,
                str(doc.path),
                doc.word_count,
                int(doc.is_favorite),
                now,
                now,
            ),
        )
        self.conn.commit()
        doc.id = cur.lastrowid
        return doc

    def get_documents(self, chapter_id: int) -> list[Document]:
        rows = self.conn.execute(
            "SELECT id, chapter_id, name, file_path, word_count, is_favorite, "
            "created_at, updated_at "
            "FROM documents WHERE chapter_id=? ORDER BY name",
            (chapter_id,),
        ).fetchall()
        return [
            Document(
                id=r["id"],
                chapter_id=r["chapter_id"],
                name=r["name"],
                path=Path(r["file_path"]),
                word_count=r["word_count"],
                is_favorite=bool(r["is_favorite"]),
                created_at=_dt(r["created_at"]),
                updated_at=_dt(r["updated_at"]),
            )
            for r in rows
        ]

    def get_document_by_id(self, doc_id: int) -> "Document | None":
        row = self.conn.execute(
            "SELECT id, chapter_id, name, file_path, word_count, is_favorite, "
            "created_at, updated_at FROM documents WHERE id=? LIMIT 1",
            (doc_id,),
        ).fetchone()
        if not row:
            return None
        return Document(
            id=row["id"],
            chapter_id=row["chapter_id"],
            name=row["name"],
            path=Path(row["file_path"]),
            word_count=row["word_count"],
            is_favorite=bool(row["is_favorite"]),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    def update_document(self, doc: Document) -> None:
        self.conn.execute(
            "UPDATE documents SET name=?, file_path=?, word_count=?, is_favorite=?, "
            "updated_at=? WHERE id=?",
            (
                doc.name,
                str(doc.path),
                doc.word_count,
                int(doc.is_favorite),
                _ts(datetime.now()),
                doc.id,
            ),
        )
        self.conn.commit()

    def delete_document(self, doc_id: int) -> None:
        self.conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        self.conn.commit()

    def update_fts(self, doc: Document) -> None:
        """Rebuild FTS entry after content changes."""
        self.conn.execute(
            "INSERT OR REPLACE INTO documents_fts(rowid, name, content_index) VALUES (?,?,?)",
            (
                doc.id,
                doc.name,
                self.conn.execute(
                    "SELECT content_index FROM documents WHERE id=?", (doc.id,)
                ).fetchone()["content_index"]
                or "",
            ),
        )
        self.conn.commit()

    def index_document_content(self, doc: Document, plain_text: str) -> None:
        """Store plain-text content for FTS indexing."""
        self.conn.execute(
            "UPDATE documents SET content_index=?, updated_at=? WHERE id=?",
            (plain_text, _ts(datetime.now()), doc.id),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO documents_fts(rowid, name, content_index) VALUES (?,?,?)",
            (doc.id, doc.name, plain_text),
        )
        self.conn.commit()

    def search(self, query: str) -> list[Document]:
        """Full-text search across document names and content."""
        rows = self.conn.execute(
            "SELECT d.id, d.chapter_id, d.name, d.file_path, d.word_count, "
            "d.is_favorite, d.created_at, d.updated_at "
            "FROM documents d "
            "JOIN documents_fts fts ON fts.rowid = d.id "
            "WHERE documents_fts MATCH ? "
            "ORDER BY rank",
            (query,),
        ).fetchall()
        return [
            Document(
                id=r["id"],
                chapter_id=r["chapter_id"],
                name=r["name"],
                path=Path(r["file_path"]),
                word_count=r["word_count"],
                is_favorite=bool(r["is_favorite"]),
                created_at=_dt(r["created_at"]),
                updated_at=_dt(r["updated_at"]),
            )
            for r in rows
        ]

    def get_all_documents(self) -> list[Document]:
        """Return every document across all chapters, ordered by name."""
        rows = self.conn.execute(
            "SELECT id, chapter_id, name, file_path, word_count, is_favorite, "
            "created_at, updated_at FROM documents ORDER BY name"
        ).fetchall()
        return [
            Document(
                id=r["id"],
                chapter_id=r["chapter_id"],
                name=r["name"],
                path=Path(r["file_path"]),
                word_count=r["word_count"],
                is_favorite=bool(r["is_favorite"]),
                created_at=_dt(r["created_at"]),
                updated_at=_dt(r["updated_at"]),
            )
            for r in rows
        ]

    def get_document_by_name(self, name: str) -> Document | None:
        """Return the first document whose name matches exactly, or None."""
        row = self.conn.execute(
            "SELECT id, chapter_id, name, file_path, word_count, is_favorite, "
            "created_at, updated_at FROM documents WHERE name=? LIMIT 1",
            (name,),
        ).fetchone()
        if not row:
            return None
        return Document(
            id=row["id"],
            chapter_id=row["chapter_id"],
            name=row["name"],
            path=Path(row["file_path"]),
            word_count=row["word_count"],
            is_favorite=bool(row["is_favorite"]),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    # --------------------------------------------------------------- links

    def clear_links_from(self, source_doc_id: int) -> None:
        """Remove all outgoing links recorded for *source_doc_id*."""
        self.conn.execute("DELETE FROM links WHERE source_doc_id=?", (source_doc_id,))
        self.conn.commit()

    def add_link(self, source_id: int, target_id: int) -> None:
        """Record that *source_id* references *target_id*. Ignores duplicates."""
        self.conn.execute(
            "INSERT OR IGNORE INTO links (source_doc_id, target_doc_id) VALUES (?,?)",
            (source_id, target_id),
        )
        self.conn.commit()

    def get_backlinks(self, doc_id: int) -> list[Document]:
        """Return all documents that contain a [[link]] pointing to *doc_id*."""
        rows = self.conn.execute(
            "SELECT d.id, d.chapter_id, d.name, d.file_path, d.word_count, "
            "d.is_favorite, d.created_at, d.updated_at "
            "FROM documents d "
            "JOIN links l ON l.source_doc_id = d.id "
            "WHERE l.target_doc_id=? ORDER BY d.name",
            (doc_id,),
        ).fetchall()
        return [
            Document(
                id=r["id"],
                chapter_id=r["chapter_id"],
                name=r["name"],
                path=Path(r["file_path"]),
                word_count=r["word_count"],
                is_favorite=bool(r["is_favorite"]),
                created_at=_dt(r["created_at"]),
                updated_at=_dt(r["updated_at"]),
            )
            for r in rows
        ]

    # -------------------------------------------------------------- history

    def record_open(self, doc: Document) -> None:
        self.conn.execute(
            "INSERT INTO history (document_id, opened_at) VALUES (?,?)",
            (doc.id, _ts(datetime.now())),
        )
        self.conn.commit()

    def get_recent_documents(self, limit: int = 10) -> list[Document]:
        """Return up to *limit* documents ordered by most recently opened."""
        rows = self.conn.execute(
            "SELECT d.id, d.chapter_id, d.name, d.file_path, d.word_count, "
            "d.is_favorite, d.created_at, d.updated_at "
            "FROM documents d "
            "JOIN (SELECT document_id, MAX(opened_at) AS last_opened "
            "      FROM history GROUP BY document_id) h ON h.document_id = d.id "
            "ORDER BY h.last_opened DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            Document(
                id=r["id"],
                chapter_id=r["chapter_id"],
                name=r["name"],
                path=Path(r["file_path"]),
                word_count=r["word_count"],
                is_favorite=bool(r["is_favorite"]),
                created_at=_dt(r["created_at"]),
                updated_at=_dt(r["updated_at"]),
            )
            for r in rows
        ]

    # --------------------------------------------------------------- favorites

    def toggle_favorite(self, doc: Document) -> bool:
        """Flip *doc*'s is_favorite flag. Updates *doc* in-place and returns new value."""
        self.conn.execute(
            "UPDATE documents SET is_favorite = 1 - is_favorite WHERE id=?",
            (doc.id,),
        )
        row = self.conn.execute(
            "SELECT is_favorite FROM documents WHERE id=?", (doc.id,)
        ).fetchone()
        self.conn.commit()
        new_val = bool(row["is_favorite"]) if row else doc.is_favorite
        doc.is_favorite = new_val
        return new_val

    def get_favorites(self) -> list[Document]:
        """Return all documents marked as favorite, ordered by name."""
        rows = self.conn.execute(
            "SELECT id, chapter_id, name, file_path, word_count, is_favorite, "
            "created_at, updated_at FROM documents WHERE is_favorite=1 ORDER BY name"
        ).fetchall()
        return [
            Document(
                id=r["id"],
                chapter_id=r["chapter_id"],
                name=r["name"],
                path=Path(r["file_path"]),
                word_count=r["word_count"],
                is_favorite=bool(r["is_favorite"]),
                created_at=_dt(r["created_at"]),
                updated_at=_dt(r["updated_at"]),
            )
            for r in rows
        ]

    # ------------------------------------------------------------ full-text search

    def search_fts(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search with snippets. Returns list of dicts:
        {doc, chapter_name, book_name, snippet}."""
        clean = re.sub(r"[^\w\s]", " ", query, flags=re.UNICODE).strip()
        if not clean:
            return []
        fts_query = " AND ".join(f'"{t}"*' for t in clean.split())
        try:
            rows = self.conn.execute(
                "SELECT d.id, d.chapter_id, d.name, d.file_path, d.word_count, "
                "d.is_favorite, d.created_at, d.updated_at, "
                "c.name AS chapter_name, b.name AS book_name, "
                "snippet(documents_fts, 1, char(2), char(3), '…', 20) AS snip "
                "FROM documents_fts "
                "JOIN documents d ON d.id = documents_fts.rowid "
                "JOIN chapters c ON c.id = d.chapter_id "
                "JOIN books b ON b.id = c.book_id "
                "WHERE documents_fts MATCH ? "
                "ORDER BY documents_fts.rank LIMIT ?",
                (fts_query, limit),
            ).fetchall()
        except Exception:
            return []
        return [
            {
                "doc": Document(
                    id=r["id"],
                    chapter_id=r["chapter_id"],
                    name=r["name"],
                    path=Path(r["file_path"]),
                    word_count=r["word_count"],
                    is_favorite=bool(r["is_favorite"]),
                    created_at=_dt(r["created_at"]),
                    updated_at=_dt(r["updated_at"]),
                ),
                "chapter_name": r["chapter_name"],
                "book_name": r["book_name"],
                "snippet": r["snip"] or "",
            }
            for r in rows
        ]

    # ------------------------------------------------------------------- tags

    def get_or_create_tag(self, name: str) -> "Tag":
        from ..models import Tag

        row = self.conn.execute(
            "SELECT id, name FROM tags WHERE name=? LIMIT 1", (name,)
        ).fetchone()
        if row:
            return Tag(id=row["id"], name=row["name"])
        cur = self.conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
        self.conn.commit()
        return Tag(id=cur.lastrowid, name=name)

    def add_tag_to_doc(self, doc_id: int, tag: "Tag") -> None:
        """Associate *tag* with *doc_id* (idempotent)."""
        self.conn.execute(
            "INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?,?)",
            (doc_id, tag.id),
        )
        self.conn.commit()

    def remove_tag_from_doc(self, doc_id: int, tag_id: int) -> None:
        self.conn.execute(
            "DELETE FROM document_tags WHERE document_id=? AND tag_id=?",
            (doc_id, tag_id),
        )
        self.conn.commit()

    def get_doc_tags(self, doc_id: int) -> list["Tag"]:
        from ..models import Tag

        rows = self.conn.execute(
            "SELECT t.id, t.name FROM tags t "
            "JOIN document_tags dt ON dt.tag_id = t.id "
            "WHERE dt.document_id=? ORDER BY t.name",
            (doc_id,),
        ).fetchall()
        return [Tag(id=r["id"], name=r["name"]) for r in rows]

    def get_all_tags(self) -> list[tuple["Tag", int]]:
        """Return every tag paired with its document count."""
        from ..models import Tag

        rows = self.conn.execute(
            "SELECT t.id, t.name, COUNT(dt.document_id) AS doc_count "
            "FROM tags t "
            "LEFT JOIN document_tags dt ON dt.tag_id = t.id "
            "GROUP BY t.id ORDER BY t.name"
        ).fetchall()
        return [(Tag(id=r["id"], name=r["name"]), r["doc_count"]) for r in rows]

    def get_docs_by_tag(self, tag_id: int) -> list[Document]:
        rows = self.conn.execute(
            "SELECT d.id, d.chapter_id, d.name, d.file_path, d.word_count, "
            "d.is_favorite, d.created_at, d.updated_at "
            "FROM documents d "
            "JOIN document_tags dt ON dt.document_id = d.id "
            "WHERE dt.tag_id=? ORDER BY d.name",
            (tag_id,),
        ).fetchall()
        return [
            Document(
                id=r["id"],
                chapter_id=r["chapter_id"],
                name=r["name"],
                path=Path(r["file_path"]),
                word_count=r["word_count"],
                is_favorite=bool(r["is_favorite"]),
                created_at=_dt(r["created_at"]),
                updated_at=_dt(r["updated_at"]),
            )
            for r in rows
        ]

    def delete_unused_tags(self) -> None:
        """Remove tags that have no associated documents."""
        self.conn.execute(
            "DELETE FROM tags WHERE id NOT IN "
            "(SELECT DISTINCT tag_id FROM document_tags)"
        )
        self.conn.commit()
