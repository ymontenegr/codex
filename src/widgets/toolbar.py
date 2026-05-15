from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from typing import TYPE_CHECKING

from gi.repository import Adw, Gtk

if TYPE_CHECKING:
    from .editor import CodexEditorWidget


class EditorToolbar(Gtk.Box):
    """
    Horizontal formatting toolbar for the Codex editor.

    Follows §4 design-guidelines (Gtk.Box + Gtk.Button horizontales) and
    §7 iconografía (symbolic icons only).
    """

    __gtype_name__ = "EditorToolbar"

    def __init__(self, **kwargs):
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
            **kwargs,
        )
        self.add_css_class("toolbar")
        self._editor: CodexEditorWidget | None = None
        self._link_dialog_open = False
        self._build()

    def set_editor(self, editor: CodexEditorWidget) -> None:
        self._editor = editor

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Bold — Ctrl+B (§8 atajos)
        self._btn_icon(
            "format-text-bold-symbolic",
            "Negrita (Ctrl+B)",
            lambda: self._cmd("bold"),
        )
        # Italic — Ctrl+I
        self._btn_icon(
            "format-text-italic-symbolic",
            "Cursiva (Ctrl+I)",
            lambda: self._cmd("italic"),
        )
        # Code inline — Ctrl+Shift+C (label porque format-text-monospace-symbolic
        # no está en todos los temas)
        self._btn_label(
            "</>",
            "Código inline (Ctrl+Shift+C)",
            lambda: self._editor and self._editor.insert_code(),
        )

        self._sep()

        # Headings H1 / H2 / H3 (§3 tipografía: .title-1, .title-2, .title-3)
        self._btn_label("H1", "Encabezado 1", lambda: self._block("h1"))
        self._btn_label("H2", "Encabezado 2", lambda: self._block("h2"))
        self._btn_label("H3", "Encabezado 3", lambda: self._block("h3"))

        self._sep()

        # Lists
        self._btn_icon(
            "view-list-bullet-symbolic",
            "Lista no ordenada",
            lambda: self._cmd("insertUnorderedList"),
        )
        self._btn_icon(
            "view-list-ordered-symbolic",
            "Lista ordenada",
            lambda: self._cmd("insertOrderedList"),
        )

        self._sep()

        # Link — insert-link-symbolic (§7 iconografía)
        self._btn_icon(
            "insert-link-symbolic",
            "Insertar enlace web",
            self._show_link_dialog,
        )

        # Cross-reference — internal document link [[nombre]]
        self._btn_label(
            "[[…]]",
            "Insertar referencia a documento interno",
            lambda: self._editor and self._editor.trigger_crossref(),
        )

        # Push the find bar to the right
        spacer = Gtk.Box(hexpand=True)
        self.append(spacer)

        self._sep()

        # Find in document
        self._find_entry = Gtk.SearchEntry(
            placeholder_text="Buscar en documento…",
            width_chars=20,
        )
        self._find_entry.connect("search-changed", self._on_find_changed)
        self._find_entry.connect(
            "next-match", lambda _: self._editor and self._editor.find_next()
        )
        self._find_entry.connect(
            "previous-match", lambda _: self._editor and self._editor.find_prev()
        )
        self._find_entry.connect(
            "stop-search",
            lambda e: (e.set_text(""), self._editor and self._editor.find_text("")),
        )
        self.append(self._find_entry)

    def _on_find_changed(self, entry: Gtk.SearchEntry) -> None:
        if self._editor:
            self._editor.find_text(entry.get_text())

    # ── Command helpers ───────────────────────────────────────────────────────

    def _cmd(self, command: str) -> None:
        if self._editor:
            self._editor.format(command)

    def _block(self, tag: str) -> None:
        """Change the current block to a heading or paragraph."""
        if self._editor:
            self._editor.format("formatBlock", tag)

    # ── Widget builders ───────────────────────────────────────────────────────

    def _btn_icon(self, icon: str, tooltip: str, cb) -> None:
        btn = Gtk.Button(
            icon_name=icon,
            tooltip_text=tooltip,
            css_classes=["flat"],
        )
        # §8 accesibilidad: label explícito en botones sin texto visible
        btn.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
        btn.connect("clicked", lambda _: cb())
        self.append(btn)

    def _btn_label(self, label: str, tooltip: str, cb) -> None:
        btn = Gtk.Button(
            label=label,
            tooltip_text=tooltip,
            css_classes=["flat"],
        )
        btn.connect("clicked", lambda _: cb())
        self.append(btn)

    def _sep(self) -> None:
        self.append(
            Gtk.Separator(
                orientation=Gtk.Orientation.VERTICAL,
                margin_top=6,
                margin_bottom=6,
            )
        )

    # ── Link dialog ───────────────────────────────────────────────────────────

    def _show_link_dialog(self) -> None:
        if not self._editor or self._link_dialog_open:
            return
        self._link_dialog_open = True

        entry_text = Adw.EntryRow(title="Texto del enlace")
        entry_url = Adw.EntryRow(title="URL  (https://…)")
        group = Adw.PreferencesGroup()
        group.add(entry_text)
        group.add(entry_url)

        dialog = Adw.AlertDialog(heading="Insertar enlace")
        dialog.set_extra_child(group)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("insert", "Insertar")
        dialog.set_response_appearance("insert", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("insert")
        dialog.set_close_response("cancel")

        def on_response(_d, response: str) -> None:
            self._link_dialog_open = False
            if response != "insert":
                return
            text = entry_text.get_text().strip()
            url = entry_url.get_text().strip()
            if not url:
                return
            display = text or url
            # insertHTML keeps the action undoable inside the WebView
            safe_html = f'<a href="{url}">{display}</a>'.replace("'", "\\'")
            self._editor._wv.evaluate_javascript(
                f"document.execCommand('insertHTML', false, '{safe_html}');",
                -1,
                None,
                None,
                None,
                None,
            )

        dialog.connect("response", on_response)
        dialog.present(self.get_root())
