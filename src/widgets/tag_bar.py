from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from typing import TYPE_CHECKING

from gi.repository import Gtk

if TYPE_CHECKING:
    from ..models import Document, Tag
    from ..services import Database


class TagBar(Gtk.Box):
    """
    Horizontal bar that shows a document's tags as removable chips,
    plus an entry field to add new ones.

    Call :meth:`load` whenever a new document is opened.
    """

    __gtype_name__ = "TagBar"

    def __init__(self, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self._doc: "Document | None" = None
        self._db: "Database | None" = None
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Section header
        hdr = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            margin_start=12,
            margin_end=12,
            margin_top=6,
        )
        icon = Gtk.Image.new_from_icon_name("tag-symbolic")
        icon.add_css_class("dim-label")
        lbl = Gtk.Label(
            label="Etiquetas",
            css_classes=["caption", "dim-label"],
            halign=Gtk.Align.START,
            hexpand=True,
        )
        hdr.append(icon)
        hdr.append(lbl)
        self.append(hdr)

        # Chips container (wrapping horizontal flow)
        self._chips_box = Gtk.FlowBox()
        self._chips_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._chips_box.set_homogeneous(False)
        self._chips_box.set_max_children_per_line(20)
        self._chips_box.set_margin_start(10)
        self._chips_box.set_margin_end(10)
        self._chips_box.set_column_spacing(4)
        self._chips_box.set_row_spacing(4)
        self.append(self._chips_box)

        # Add-tag entry row
        entry_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
            margin_start=12,
            margin_end=12,
            margin_top=4,
            margin_bottom=6,
        )
        self._entry = Gtk.Entry(
            placeholder_text="Agregar etiqueta…",
            hexpand=True,
        )
        self._entry.connect("activate", self._on_add)
        add_btn = Gtk.Button(
            icon_name="list-add-symbolic",
            css_classes=["flat"],
            tooltip_text="Agregar etiqueta",
        )
        add_btn.update_property([Gtk.AccessibleProperty.LABEL], ["Agregar etiqueta"])
        add_btn.connect("clicked", lambda _: self._on_add(self._entry))
        entry_box.append(self._entry)
        entry_box.append(add_btn)
        self.append(entry_box)

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self, doc: "Document", db: "Database") -> None:
        """Refresh the bar for *doc*."""
        self._doc = doc
        self._db = db
        self._refresh()

    def clear(self) -> None:
        """Remove all chips and reset state."""
        self._doc = None
        self._db = None
        self._refresh()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        while (child := self._chips_box.get_child_at_index(0)) is not None:
            self._chips_box.remove(child)

        if not self._doc or not self._db:
            return

        for tag in self._db.get_doc_tags(self._doc.id):
            self._chips_box.append(self._make_chip(tag))

    def _make_chip(self, tag: "Tag") -> Gtk.Box:
        # Outer box styled as a pill using "linked" (two adjacent flat buttons)
        chip = Gtk.Box(spacing=0, css_classes=["linked"])
        chip.set_margin_top(2)
        chip.set_margin_bottom(2)
        chip.set_margin_start(2)

        name_btn = Gtk.Button(
            label=tag.name,
            css_classes=["flat"],
        )
        name_btn.set_can_focus(False)

        del_btn = Gtk.Button(
            icon_name="window-close-symbolic",
            css_classes=["flat"],
            tooltip_text=f"Quitar etiqueta «{tag.name}»",
        )
        del_btn.update_property(
            [Gtk.AccessibleProperty.LABEL], [f"Quitar etiqueta {tag.name}"]
        )

        def on_remove(_btn, t=tag) -> None:
            if self._doc and self._db:
                self._db.remove_tag_from_doc(self._doc.id, t.id)
                self._db.delete_unused_tags()
                self._refresh()

        del_btn.connect("clicked", on_remove)
        chip.append(name_btn)
        chip.append(del_btn)
        return chip

    def _on_add(self, entry: Gtk.Entry) -> None:
        name = entry.get_text().strip()
        if not name or not self._doc or not self._db:
            return
        tag = self._db.get_or_create_tag(name)
        self._db.add_tag_to_doc(self._doc.id, tag)
        entry.set_text("")
        self._refresh()
