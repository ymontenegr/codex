from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .database import Database

# Palette of 10 visually distinct RGB colours for book nodes.
_BOOK_COLORS: list[tuple[float, float, float]] = [
    (0.27, 0.52, 0.83),  # blue
    (0.20, 0.63, 0.43),  # green
    (0.83, 0.38, 0.38),  # red
    (0.75, 0.56, 0.15),  # amber
    (0.54, 0.36, 0.72),  # purple
    (0.15, 0.68, 0.73),  # cyan
    (0.87, 0.50, 0.20),  # orange
    (0.42, 0.58, 0.22),  # olive
    (0.72, 0.25, 0.54),  # magenta
    (0.35, 0.55, 0.62),  # steel-blue
]


class GraphNode:
    """Represents a document in the graph."""

    def __init__(
        self,
        doc_id: int,
        name: str,
        book_id: int,
        book_name: str,
        chapter_name: str,
    ) -> None:
        self.id = doc_id
        self.name = name
        self.book_id = book_id
        self.book_name = book_name
        self.chapter_name = chapter_name
        self.degree: int = 0
        self.color: tuple[float, float, float] = (0.5, 0.5, 0.5)


class GraphService:
    """Builds node/edge data for the graph view from the SQLite links table."""

    def __init__(self, db: "Database") -> None:
        self._db = db

    def get_graph_data(self) -> tuple[list[GraphNode], list[tuple[int, int]]]:
        """Return (nodes, edges).  Edges are (source_doc_id, target_doc_id)."""
        nodes = self._get_nodes()
        edges = self._get_edges()

        # Assign degree counts
        degree: dict[int, int] = {}
        for src, tgt in edges:
            degree[src] = degree.get(src, 0) + 1
            degree[tgt] = degree.get(tgt, 0) + 1
        for node in nodes:
            node.degree = degree.get(node.id, 0)

        # Assign colours by book
        book_ids = sorted({n.book_id for n in nodes})
        color_map = {
            bid: _BOOK_COLORS[i % len(_BOOK_COLORS)] for i, bid in enumerate(book_ids)
        }
        for node in nodes:
            node.color = color_map.get(node.book_id, (0.5, 0.5, 0.5))

        return nodes, edges

    # ── Queries ───────────────────────────────────────────────────────────────

    def _get_nodes(self) -> list[GraphNode]:
        rows = self._db.conn.execute("""
            SELECT d.id, d.name,
                   b.id AS book_id, b.name AS book_name,
                   c.name AS chapter_name
            FROM documents d
            JOIN chapters c ON c.id = d.chapter_id
            JOIN books    b ON b.id = c.book_id
            ORDER BY b.name, c.name, d.name
        """).fetchall()
        return [
            GraphNode(
                r["id"], r["name"], r["book_id"], r["book_name"], r["chapter_name"]
            )
            for r in rows
        ]

    def _get_edges(self) -> list[tuple[int, int]]:
        rows = self._db.conn.execute(
            "SELECT source_doc_id, target_doc_id FROM links"
        ).fetchall()
        return [(r["source_doc_id"], r["target_doc_id"]) for r in rows]
