from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Book, Chapter, Document
    from .database import Database
    from .storage import StorageService

from ..utils.markdown_parser import strip_markdown


class ExportError(Exception):
    """Raised when an export operation fails."""


class Exporter:
    """
    Exports documents, chapters or books to .md, .txt or .pdf.

    Usage::
        exporter = Exporter(storage, db)
        exporter.export(doc, fmt="pdf", dest=Path("/tmp/doc.pdf"))
    """

    def __init__(self, storage: "StorageService", db: "Database") -> None:
        self._storage = storage
        self._db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def export(self, target, fmt: str, dest: Path) -> None:
        """Export *target* (Document | Chapter | Book) in *fmt* to *dest*.

        *fmt* must be one of: 'md', 'txt', 'pdf'.
        """
        md = self._collect_markdown(target)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "md":
            dest.write_text(md, encoding="utf-8")
        elif fmt == "txt":
            dest.write_text(strip_markdown(md), encoding="utf-8")
        elif fmt == "pdf":
            self._write_pdf(md, dest)
        else:
            raise ExportError(f"Formato desconocido: {fmt!r}")

    # ── Markdown collection ───────────────────────────────────────────────────

    def _collect_markdown(self, target) -> str:
        from ..models import Document, Chapter, Book

        if isinstance(target, Document):
            return self._doc_md(target)
        if isinstance(target, Chapter):
            return self._chapter_md(target)
        if isinstance(target, Book):
            return self._book_md(target)
        raise ExportError(f"Tipo de destino no soportado: {type(target)}")

    def _doc_md(self, doc: "Document") -> str:
        return self._storage.read_document(doc)

    def _chapter_md(self, chapter: "Chapter") -> str:
        docs = self._db.get_documents(chapter.id)
        parts = [f"# {chapter.name}\n\n"]
        for doc in docs:
            parts.append(self._storage.read_document(doc))
            parts.append("\n\n---\n\n")
        return "".join(parts)

    def _book_md(self, book: "Book") -> str:
        parts = [f"# {book.name}\n\n"]
        for chapter in self._db.get_chapters(book.id):
            parts.append(f"## {chapter.name}\n\n")
            for doc in self._db.get_documents(chapter.id):
                parts.append(self._storage.read_document(doc))
                parts.append("\n\n---\n\n")
        return "".join(parts)

    # ── PDF via pandoc ────────────────────────────────────────────────────────

    # ── LaTeX header that matches the app's visual style ─────────────────────

    _LATEX_HEADER = r"""
\usepackage{xcolor}
\definecolor{accent}{HTML}{3584e4}
\usepackage{sectsty}
\allsectionsfont{\color{accent}\sffamily\bfseries}
\usepackage{hyperref}
\hypersetup{colorlinks=true, linkcolor=accent, urlcolor=accent}
\renewcommand{\familydefault}{\sfdefault}
"""

    def _write_pdf(self, md: str, dest: Path) -> None:
        import subprocess
        import tempfile

        pandoc_path = shutil.which("pandoc")
        if not pandoc_path:
            raise ExportError(
                "pandoc no está instalado.\n"
                "Ejecuta: sudo apt install pandoc"
            )

        tmp_md = tmp_hdr = None
        try:
            # Markdown source
            with tempfile.NamedTemporaryFile(
                suffix=".md", mode="w", encoding="utf-8", delete=False
            ) as f:
                f.write(md)
                tmp_md = f.name

            # LaTeX header for styling
            with tempfile.NamedTemporaryFile(
                suffix=".tex", mode="w", encoding="utf-8", delete=False
            ) as f:
                f.write(self._LATEX_HEADER)
                tmp_hdr = f.name

            last_error = ""
            for engine in [e for e in ("xelatex", "lualatex", "pdflatex") if shutil.which(e)]:
                cmd = [
                    pandoc_path, tmp_md, "-o", str(dest),
                    f"--pdf-engine={engine}",
                    "--include-in-header", tmp_hdr,
                    "--variable", "geometry:margin=2.5cm,top=3cm",
                    "--variable", "fontsize=12pt",
                    "--variable", "linestretch=1.4",
                ]
                # xelatex/lualatex support system fonts; set Liberation Sans
                if engine in ("xelatex", "lualatex"):
                    cmd += ["--variable", "mainfont=Liberation Sans"]

                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    return
                last_error = result.stderr.strip()

        finally:
            for p in (tmp_md, tmp_hdr):
                if p:
                    Path(p).unlink(missing_ok=True)

        raise ExportError(
            "No se pudo generar el PDF.\n"
            "Asegúrate de tener instalado: sudo apt install texlive-xetex\n"
            f"Error: {last_error[:300]}"
        )
