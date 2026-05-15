from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from pathlib import Path
from typing import Callable

from gi.repository import Adw, Gtk

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "templates"

_TEMPLATES: list[tuple[str, str, str]] = [
    ("empty", "Vacío", "Documento en blanco"),
    ("meeting", "Reunión", "Acta de reunión con agenda y acuerdos"),
    ("article", "Artículo", "Introducción, desarrollo, conclusión y referencias"),
    ("analysis", "Análisis", "Contexto, opciones evaluadas, decisión e impacto"),
    ("readme", "README", "Descripción, instalación, uso y licencia"),
]


class TemplateDialog:
    """
    Non-modal dialog that lets the user choose a document template.

    Usage::
        TemplateDialog(parent_widget).show(callback)

    *callback(template_key: str)* is called with the chosen key
    (e.g. ``"meeting"``).  Key ``"empty"`` means no template.
    """

    def __init__(self, parent: Gtk.Widget) -> None:
        self._parent = parent
        self._selected_key = "empty"
        self._dialog = self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> Adw.AlertDialog:
        list_box = Gtk.ListBox(css_classes=["boxed-list"])
        list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        list_box.set_margin_bottom(4)

        for key, name, desc in _TEMPLATES:
            row = Adw.ActionRow(title=name, subtitle=desc)
            row._template_key = key  # type: ignore[attr-defined]
            list_box.append(row)

        # Select first row
        first = list_box.get_row_at_index(0)
        if first:
            list_box.select_row(first)

        def on_row_selected(_lb, row) -> None:
            if row and hasattr(row, "_template_key"):
                self._selected_key = row._template_key

        list_box.connect("row-selected", on_row_selected)

        dialog = Adw.AlertDialog(
            heading="¿Iniciar desde una plantilla?",
            body="Elige una estructura inicial para el documento.",
        )
        dialog.set_extra_child(list_box)
        dialog.add_response("blank", "Documento vacío")
        dialog.add_response("use", "Usar plantilla")
        dialog.set_response_appearance("use", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("use")
        dialog.set_close_response("blank")
        return dialog

    # ── Public API ────────────────────────────────────────────────────────────

    def show(self, callback: Callable[[str], None]) -> None:
        """Present the dialog; *callback* receives the chosen template key."""

        def on_response(_d, response: str) -> None:
            key = self._selected_key if response == "use" else "empty"
            callback(key)

        self._dialog.connect("response", on_response)
        self._dialog.present(self._parent)

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def load_content(key: str) -> str:
        """Return the Markdown text for *key*, or an empty string."""
        path = _TEMPLATES_DIR / f"{key}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    @staticmethod
    def template_keys() -> list[str]:
        return [k for k, _, _ in _TEMPLATES]
