from ..models import Document
from .database import Database
from .storage import StorageService
from ..utils.markdown_parser import extract_references, strip_markdown


class Indexer:
    """Keeps the `links` SQLite table in sync with [[references]] in documents."""

    def __init__(self, db: Database, storage: StorageService) -> None:
        self._db = db
        self._storage = storage

    def index_document(self, doc: Document, content: str) -> None:
        """Parse [[refs]] in *content* and rebuild outgoing links for *doc*."""
        refs = extract_references(content)
        self._db.clear_links_from(doc.id)
        for name in refs:
            target = self._db.get_document_by_name(name)
            if target and target.id != doc.id:
                self._db.add_link(doc.id, target.id)

    def update_content_index(self, doc: Document, markdown: str) -> None:
        """Strip markdown syntax and update the FTS content index for *doc*."""
        self._db.index_document_content(doc, strip_markdown(markdown))

    def reindex_all(self) -> None:
        """Full re-index of every document in the library (e.g. on startup)."""
        for book in self._db.get_books():
            for chapter in self._db.get_chapters(book.id):
                for doc in self._db.get_documents(chapter.id):
                    try:
                        content = self._storage.read_document(doc)
                        self.index_document(doc, content)
                    except Exception:
                        pass
