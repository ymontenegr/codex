from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from typing import TYPE_CHECKING

from gi.repository import Adw, GLib, GObject, Gtk

if TYPE_CHECKING:
    from ..models import Document
    from ..services import Database


class SearchOverlay(Gtk.Revealer):
    """
    Full-text search overlay (Ctrl+F).  Slides down from the top of the window.

    Signals
    -------
    document-selected(doc: Document)
        Emitted when the user activates a search result.
    """

    __gtype_name__ = "SearchOverlay"

    __gsignals__ = {
        "document-selected": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (GObject.TYPE_PYOBJECT,),
        ),
    }

    def __init__(self, db: "Database", **kwargs):
        super().__init__(
            transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
            transition_duration=200,
            reveal_child=False,
            valign=Gtk.Align.START,
            **kwargs,
        )
        self._db = db
        self._debounce_id: int | None = None
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["card"],
            margin_start=12,
            margin_end=12,
            margin_top=6,
        )

        # Entry row
        entry_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            margin_start=12,
            margin_end=12,
            margin_top=9,
            margin_bottom=9,
        )
        self._entry = Gtk.SearchEntry(
            placeholder_text="Buscar en todos los documentos…",
            hexpand=True,
        )
        self._entry.connect("search-changed", self._on_search_changed)
        self._entry.connect("activate", self._on_entry_activate)

        close_btn = Gtk.Button(icon_name="window-close-symbolic", css_classes=["flat"])
        close_btn.update_property([Gtk.AccessibleProperty.LABEL], ["Cerrar búsqueda"])
        close_btn.connect("clicked", lambda _: self.toggle(False))

        entry_box.append(self._entry)
        entry_box.append(close_btn)
        card.append(entry_box)

        # Results area (hidden until there's a query)
        self._results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        card.append(Gtk.Separator())

        sw = Gtk.ScrolledWindow(
            min_content_height=0,
            max_content_height=320,
        )
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._results_list = Gtk.ListBox(css_classes=["boxed-list"])
        self._results_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._results_list.set_margin_start(12)
        self._results_list.set_margin_end(12)
        self._results_list.set_margin_top(6)
        self._results_list.set_margin_bottom(6)
        self._results_list.connect("row-activated", self._on_row_activated)
        sw.set_child(self._results_list)

        self._empty_page = Adw.StatusPage(
            icon_name="system-search-symbolic",
            title="Sin resultados",
            description="Prueba con otras palabras",
        )

        self._results_box.append(sw)
        self._results_box.append(self._empty_page)
        self._results_box.set_visible(False)
        card.append(self._results_box)

        self.set_child(card)

    # ── Public API ────────────────────────────────────────────────────────────

    def toggle(self, show: bool | None = None) -> None:
        """Show or hide the overlay; grabs focus when shown."""
        if show is None:
            show = not self.get_reveal_child()
        self.set_reveal_child(show)
        if show:
            self._entry.grab_focus()
        else:
            if self._debounce_id is not None:
                GLib.source_remove(self._debounce_id)
                self._debounce_id = None

    # ── Search logic ──────────────────────────────────────────────────────────

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        if self._debounce_id is not None:
            GLib.source_remove(self._debounce_id)
        self._debounce_id = GLib.timeout_add(300, self._do_search)

    def _do_search(self) -> bool:
        self._debounce_id = None
        self._populate(self._entry.get_text().strip())
        return False  # one-shot

    def _populate(self, query: str) -> None:
        while (row := self._results_list.get_row_at_index(0)) is not None:
            self._results_list.remove(row)

        if not query:
            self._results_box.set_visible(False)
            return

        results = self._db.search_fts(query)
        self._results_box.set_visible(True)

        sw = self._results_list.get_parent()
        self._empty_page.set_visible(not results)
        sw.set_visible(bool(results))

        for item in results:
            row = Gtk.ListBoxRow()
            row._doc = item["doc"]

            vbox = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                margin_start=12,
                margin_end=12,
                margin_top=8,
                margin_bottom=8,
                spacing=2,
            )

            name_lbl = Gtk.Label(
                label=item["doc"].name,
                halign=Gtk.Align.START,
                css_classes=["heading"],
            )
            vbox.append(name_lbl)

            path_lbl = Gtk.Label(
                label=f"{item['book_name']} › {item['chapter_name']}",
                halign=Gtk.Align.START,
                css_classes=["caption", "dim-label"],
            )
            vbox.append(path_lbl)

            snip = item["snippet"]
            if snip:
                # Escape HTML first (so < > & are safe), then restore highlight markers
                snip_markup = (
                    GLib.markup_escape_text(snip)
                    .replace("\x02", "<b>")
                    .replace("\x03", "</b>")
                )
                snip_lbl = Gtk.Label(
                    halign=Gtk.Align.START,
                    css_classes=["caption"],
                    use_markup=True,
                    label=snip_markup,
                    max_width_chars=80,
                    wrap=True,
                )
                vbox.append(snip_lbl)

            row.set_child(vbox)
            self._results_list.append(row)

        first = self._results_list.get_row_at_index(0)
        if first:
            self._results_list.select_row(first)

    # ── Signals ───────────────────────────────────────────────────────────────

    def _on_entry_activate(self, _entry: Gtk.SearchEntry) -> None:
        row = self._results_list.get_selected_row()
        if row:
            self.emit("document-selected", row._doc)
            self.toggle(False)

    def _on_row_activated(self, _list, row: Gtk.ListBoxRow) -> None:
        self.emit("document-selected", row._doc)
        self.toggle(False)
