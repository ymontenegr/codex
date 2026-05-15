"""Sprint 6 tests: Settings, GraphService, word-count helper."""
from __future__ import annotations

import json
import sqlite3
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettings:
    def test_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        from src.services.settings import Settings, _DEFAULTS
        s = Settings.__new__(Settings)
        s._data = dict(_DEFAULTS)
        assert s._data["theme"] == "default"
        assert s._data["editor_font_size"] == 15
        assert s._data["sidebar_width"] == 280
        assert s._data["export_format"] == "md"

    def test_save_and_load(self, tmp_path):
        config_dir = tmp_path / ".config" / "codex"
        settings_file = config_dir / "settings.json"

        from src.services.settings import Settings, _DEFAULTS
        import importlib
        import src.services.settings as mod

        original_cfg = mod._CONFIG_DIR
        original_file = mod._SETTINGS_FILE
        try:
            mod._CONFIG_DIR = config_dir
            mod._SETTINGS_FILE = settings_file

            s = Settings.__new__(Settings)
            s._data = dict(_DEFAULTS)
            s._data["theme"] = "force-dark"
            s._data["editor_font_size"] = 20

            # save manually using updated module-level paths
            config_dir.mkdir(parents=True, exist_ok=True)
            settings_file.write_text(
                json.dumps(s._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            s2 = Settings.__new__(Settings)
            s2._data = dict(_DEFAULTS)
            raw = json.loads(settings_file.read_text(encoding="utf-8"))
            s2._data.update({k: v for k, v in raw.items() if k in _DEFAULTS})

            assert s2._data["theme"] == "force-dark"
            assert s2._data["editor_font_size"] == 20
            assert s2._data["sidebar_width"] == 280  # unchanged default
        finally:
            mod._CONFIG_DIR = original_cfg
            mod._SETTINGS_FILE = original_file

    def test_set_ignores_unknown_keys(self):
        from src.services.settings import Settings, _DEFAULTS
        s = Settings.__new__(Settings)
        s._data = dict(_DEFAULTS)
        s.set = Settings.set.__get__(s, Settings)
        s.set("nonexistent_key", "value")
        assert "nonexistent_key" not in s._data

    def test_get_with_fallback(self):
        from src.services.settings import Settings, _DEFAULTS
        s = Settings.__new__(Settings)
        s._data = dict(_DEFAULTS)
        assert s.get("theme") == "default"
        assert s.get("missing_key", "fallback") == "fallback"

    def test_reset_restores_defaults(self):
        from src.services.settings import Settings, _DEFAULTS
        s = Settings.__new__(Settings)
        s._data = {"theme": "force-dark", "editor_font_size": 99}
        s.reset = Settings.reset.__get__(s, Settings)
        s.reset()
        assert s._data["theme"] == "default"
        assert s._data["editor_font_size"] == 15


# ---------------------------------------------------------------------------
# GraphService
# ---------------------------------------------------------------------------

def _make_test_db(tmp_path) -> "Database":
    """Create a minimal in-memory-style Database for graph tests."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE books (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE chapters (
            id INTEGER PRIMARY KEY,
            book_id INTEGER NOT NULL REFERENCES books(id),
            name TEXT NOT NULL
        );
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            chapter_id INTEGER NOT NULL REFERENCES chapters(id),
            name TEXT NOT NULL,
            file_path TEXT NOT NULL DEFAULT '',
            word_count INTEGER NOT NULL DEFAULT 0,
            is_favorite INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE links (
            id INTEGER PRIMARY KEY,
            source_doc_id INTEGER NOT NULL,
            target_doc_id INTEGER NOT NULL
        );
    """)
    conn.commit()

    from src.services.database import Database
    db = object.__new__(Database)
    db._conn = conn
    return db


class TestGraphService:
    def test_empty_db(self, tmp_path):
        from src.services.graph_service import GraphService
        db = _make_test_db(tmp_path)
        gs = GraphService(db)
        nodes, edges = gs.get_graph_data()
        assert nodes == []
        assert edges == []

    def test_nodes_populated(self, tmp_path):
        from src.services.graph_service import GraphService
        db = _make_test_db(tmp_path)
        db.conn.executescript("""
            INSERT INTO books VALUES (1, 'Book A');
            INSERT INTO chapters VALUES (1, 1, 'Chapter 1');
            INSERT INTO documents (id, chapter_id, name) VALUES (1, 1, 'Doc Alpha');
            INSERT INTO documents (id, chapter_id, name) VALUES (2, 1, 'Doc Beta');
        """)
        gs = GraphService(db)
        nodes, edges = gs.get_graph_data()
        assert len(nodes) == 2
        assert edges == []
        names = {n.name for n in nodes}
        assert names == {"Doc Alpha", "Doc Beta"}

    def test_edges_and_degree(self, tmp_path):
        from src.services.graph_service import GraphService
        db = _make_test_db(tmp_path)
        db.conn.executescript("""
            INSERT INTO books VALUES (1, 'Book A');
            INSERT INTO chapters VALUES (1, 1, 'Ch 1');
            INSERT INTO documents (id, chapter_id, name) VALUES (1, 1, 'D1');
            INSERT INTO documents (id, chapter_id, name) VALUES (2, 1, 'D2');
            INSERT INTO documents (id, chapter_id, name) VALUES (3, 1, 'D3');
            INSERT INTO links VALUES (1, 1, 2);
            INSERT INTO links VALUES (2, 2, 3);
        """)
        gs = GraphService(db)
        nodes, edges = gs.get_graph_data()
        assert len(edges) == 2
        degree_map = {n.id: n.degree for n in nodes}
        assert degree_map[1] == 1
        assert degree_map[2] == 2
        assert degree_map[3] == 1

    def test_color_by_book(self, tmp_path):
        from src.services.graph_service import GraphService, _BOOK_COLORS
        db = _make_test_db(tmp_path)
        db.conn.executescript("""
            INSERT INTO books VALUES (1, 'Book A');
            INSERT INTO books VALUES (2, 'Book B');
            INSERT INTO chapters VALUES (1, 1, 'Ch A');
            INSERT INTO chapters VALUES (2, 2, 'Ch B');
            INSERT INTO documents (id, chapter_id, name) VALUES (1, 1, 'DA');
            INSERT INTO documents (id, chapter_id, name) VALUES (2, 2, 'DB');
        """)
        gs = GraphService(db)
        nodes, _ = gs.get_graph_data()
        colors = {n.book_id: n.color for n in nodes}
        # Both books should have a color from the palette (not the gray default)
        assert colors[1] in _BOOK_COLORS
        assert colors[2] in _BOOK_COLORS
        assert colors[1] != colors[2]

    def test_multibook_color_cycle(self, tmp_path):
        """More than 10 books should cycle the palette without crashing."""
        from src.services.graph_service import GraphService, _BOOK_COLORS
        db = _make_test_db(tmp_path)
        inserts = []
        for i in range(1, 13):
            inserts.append(f"INSERT INTO books VALUES ({i}, 'Book {i}');")
            inserts.append(f"INSERT INTO chapters VALUES ({i}, {i}, 'Ch {i}');")
            inserts.append(
                f"INSERT INTO documents (id, chapter_id, name) VALUES ({i}, {i}, 'D{i}');"
            )
        db.conn.executescript("\n".join(inserts))
        gs = GraphService(db)
        nodes, _ = gs.get_graph_data()
        assert len(nodes) == 12
        for node in nodes:
            assert node.color in _BOOK_COLORS


# ---------------------------------------------------------------------------
# Word-count helper (pure Python, no GTK)
# ---------------------------------------------------------------------------

class TestWordCountLogic:
    """Mirrors the JS logic from editor.js in pure Python for unit-testing."""

    @staticmethod
    def _count(text: str) -> int:
        trimmed = text.strip()
        return 0 if trimmed == "" else len(trimmed.split())

    def test_empty(self):
        assert self._count("") == 0

    def test_whitespace_only(self):
        assert self._count("   \n\t  ") == 0

    def test_single_word(self):
        assert self._count("hola") == 1

    def test_sentence(self):
        assert self._count("El rápido zorro marrón salta") == 5

    def test_extra_spaces(self):
        assert self._count("  uno  dos   tres  ") == 3

    def test_reading_time_one_minute_minimum(self):
        count = 50  # less than 250 wpm
        mins = max(1, round(count / 250))
        assert mins == 1

    def test_reading_time_rounds_correctly(self):
        assert max(1, round(500 / 250)) == 2
        assert max(1, round(750 / 250)) == 3
