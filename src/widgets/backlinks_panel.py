from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from typing import TYPE_CHECKING

from gi.repository import GObject, Gtk

if TYPE_CHECKING:
    from ..models import Document
    from ..services import Database


class BacklinksPanel(Gtk.Box):
    """
    Panel that lists documents which contain a [[reference]] to the current one.

    Signals
    -------
    document-selected(doc: Document)
        Emitted when the user clicks a backlink row.
    """

    __gtype_name__ = "BacklinksPanel"

    __gsignals__ = {
        "document-selected": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (GObject.TYPE_PYOBJECT,),
        ),
    }

    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header row: icon + label
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            margin_start=12,
            margin_end=12,
            margin_top=9,
            margin_bottom=6,
        )
        icon = Gtk.Image.new_from_icon_name("go-previous-symbolic")
        icon.add_css_class("dim-label")
        lbl = Gtk.Label(
            label="Referencias entrantes",
            css_classes=["heading"],
            halign=Gtk.Align.START,
            hexpand=True,
        )
        header_box.append(icon)
        header_box.append(lbl)
        self.append(header_box)

        # Scrollable list (max 3–4 rows visible)
        sw = Gtk.ScrolledWindow(
            min_content_height=0,
            max_content_height=120,
        )
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._list = Gtk.ListBox(css_classes=["boxed-list"])
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.set_margin_start(12)
        self._list.set_margin_end(12)
        self._list.set_margin_bottom(9)
        self._list.connect("row-activated", self._on_row_activated)
        sw.set_child(self._list)
        self.append(sw)

        # Empty-state label (hidden when there are backlinks)
        self._empty_lbl = Gtk.Label(
            label="Ningún documento hace referencia a este.",
            css_classes=["dim-label"],
            halign=Gtk.Align.CENTER,
            margin_top=3,
            margin_bottom=9,
        )
        self.append(self._empty_lbl)

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, doc: "Document", db: "Database") -> None:
        """Refresh the backlinks list for *doc* using *db*."""
        # Clear existing rows
        while (row := self._list.get_row_at_index(0)) is not None:
            self._list.remove(row)

        backlinks = db.get_backlinks(doc.id)
        for bl in backlinks:
            row = Gtk.ListBoxRow()
            row._doc = bl
            lbl = Gtk.Label(
                label=bl.name,
                halign=Gtk.Align.START,
                margin_start=12,
                margin_end=12,
                margin_top=6,
                margin_bottom=6,
            )
            row.set_child(lbl)
            self._list.append(row)

        has_links = bool(backlinks)
        self._list.set_visible(has_links)
        self._empty_lbl.set_visible(not has_links)

    # ── Signals ───────────────────────────────────────────────────────────────

    def _on_row_activated(self, _list, row: Gtk.ListBoxRow) -> None:
        self.emit("document-selected", row._doc)
