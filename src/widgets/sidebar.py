import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")

from gi.repository import Adw, Gdk, GLib, GObject, Gtk

from ..models import Book, Chapter, Document
from ..services import Database, StorageError, StorageService
from .template_dialog import TemplateDialog

# ── TreeStore column indices ──────────────────────────────────────────────────
_C_NAME = 0  # str  — display name
_C_TYPE = 1  # str  — "book" | "chapter" | "document"
_C_ITEM = 2  # any  — Book / Chapter / Document instance
_C_ICON = 3  # str  — icon-name

_ICONS = {
    "book": "user-bookmarks-symbolic",
    "chapter": "folder-symbolic",
    "document": "document-text-symbolic",
}
_LABELS = {
    "book": ("Nuevo libro", "Nombre del libro"),
    "chapter": ("Nuevo capítulo", "Nombre del capítulo"),
    "document": ("Nuevo documento", "Nombre del documento"),
}


class CodexSidebar(Gtk.Box):
    """Left-panel widget: hierarchical tree Book → Chapter → Document."""

    __gtype_name__ = "CodexSidebar"

    __gsignals__ = {
        "document-selected": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (GObject.TYPE_PYOBJECT,),
        ),
    }

    def __init__(self, storage: StorageService, db: Database, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self._storage = storage
        self._db = db
        self._ctx_popover: Gtk.Popover | None = None
        self._search_query = ""
        self._setup_ui()
        self._load()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        header = Adw.HeaderBar()
        header.set_show_start_title_buttons(False)
        header.set_show_end_title_buttons(False)

        # Title: app icon + "Biblioteca"
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        app_icon = Gtk.Image.new_from_icon_name("io.github.ymontenegr.Codex")
        app_icon.set_pixel_size(22)
        title_box.append(app_icon)
        title_box.append(Gtk.Label(label="Biblioteca", css_classes=["heading"]))
        header.set_title_widget(title_box)

        # Search toggle button
        self._search_toggle = Gtk.ToggleButton(
            icon_name="system-search-symbolic",
            tooltip_text="Buscar en biblioteca",
            css_classes=["flat"],
        )
        self._search_toggle.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Buscar en biblioteca"]
        )
        self._search_toggle.connect("toggled", self._on_search_toggled)
        header.pack_end(self._search_toggle)

        # New book button
        new_book_btn = Gtk.Button(
            icon_name="list-add-symbolic",
            tooltip_text="Nuevo libro",
            css_classes=["flat"],
        )
        new_book_btn.update_property([Gtk.AccessibleProperty.LABEL], ["Nuevo libro"])
        new_book_btn.connect(
            "clicked", lambda _: self._show_create_dialog("book", None)
        )
        header.pack_end(new_book_btn)
        self.append(header)

        # Search bar (hidden by default, shown when toggle is active)
        self._search_entry = Gtk.SearchEntry(
            placeholder_text="Buscar libros, capítulos y documentos…",
            hexpand=True,
            margin_start=8,
            margin_end=8,
            margin_top=4,
            margin_bottom=4,
        )
        self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_entry.connect("stop-search", self._on_search_stop)

        self._search_bar = Gtk.SearchBar(show_close_button=False)
        self._search_bar.set_child(self._search_entry)
        self._search_bar.connect_entry(self._search_entry)
        self._search_bar.set_search_mode(False)
        self.append(self._search_bar)

        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self._stack.add_named(self._build_tree_page(), "tree")
        self._stack.add_named(self._build_empty_page(), "empty")
        self.append(self._stack)

    def _build_tree_page(self) -> Gtk.Box:
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow(
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vexpand=True,
        )

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # ── TreeView ──────────────────────────────────────────────────────────
        self._store = Gtk.TreeStore(str, str, GObject.TYPE_PYOBJECT, str)
        self._filter = self._store.filter_new()
        self._filter.set_visible_func(self._filter_visible)

        self._tree = Gtk.TreeView(
            model=self._filter,
            headers_visible=False,
            activate_on_single_click=True,
            enable_tree_lines=True,
            hexpand=True,
        )
        self._tree.set_level_indentation(12)

        # Main column: icon + name (cell data func for search highlight)
        col = Gtk.TreeViewColumn()
        icon_r = Gtk.CellRendererPixbuf()
        self._text_r = Gtk.CellRendererText()
        self._text_r.set_property("ellipsize", 3)  # Pango.EllipsizeMode.END
        col.pack_start(icon_r, False)
        col.pack_start(self._text_r, True)
        col.add_attribute(icon_r, "icon-name", _C_ICON)
        col.set_cell_data_func(self._text_r, self._text_cell_data)
        col.set_spacing(3)
        col.set_expand(True)
        self._tree.append_column(col)

        # Star column (rightmost, documents only)
        self._star_col = Gtk.TreeViewColumn()
        star_r = Gtk.CellRendererPixbuf()
        self._star_col.pack_start(star_r, False)
        self._star_col.set_cell_data_func(star_r, self._star_cell_data)
        self._star_col.set_fixed_width(32)
        self._star_col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self._tree.append_column(self._star_col)

        self._tree.connect("row-activated", self._on_row_activated)

        sel = self._tree.get_selection()
        sel.set_mode(Gtk.SelectionMode.SINGLE)
        sel.connect("changed", self._on_selection_changed)

        rclick = Gtk.GestureClick(button=3)
        rclick.connect("pressed", self._on_right_click)
        self._tree.add_controller(rclick)

        outer.append(self._tree)

        # ── Favorites section ─────────────────────────────────────────────────
        self._fav_section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._fav_section_box.append(Gtk.Separator())

        fav_hdr = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            margin_start=12,
            margin_end=12,
            margin_top=9,
            margin_bottom=6,
        )
        fav_icon = Gtk.Image.new_from_icon_name("starred-symbolic")
        fav_icon.add_css_class("dim-label")
        fav_hdr.append(fav_icon)
        fav_hdr.append(
            Gtk.Label(
                label="Favoritos",
                css_classes=["heading"],
                halign=Gtk.Align.START,
                hexpand=True,
            )
        )
        self._fav_section_box.append(fav_hdr)

        self._fav_list = Gtk.ListBox(css_classes=["boxed-list"])
        self._fav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._fav_list.set_margin_start(12)
        self._fav_list.set_margin_end(12)
        self._fav_list.set_margin_bottom(9)
        self._fav_list.connect("row-activated", self._on_section_row_activated)
        self._fav_section_box.append(self._fav_list)

        outer.append(self._fav_section_box)

        # ── Tags section ──────────────────────────────────────────────────────
        self._tags_section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._tags_section_box.append(Gtk.Separator())

        tags_hdr = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            margin_start=12,
            margin_end=12,
            margin_top=9,
            margin_bottom=6,
        )
        tags_icon = Gtk.Image.new_from_icon_name("tag-symbolic")
        tags_icon.add_css_class("dim-label")
        tags_hdr.append(tags_icon)
        tags_hdr.append(
            Gtk.Label(
                label="Etiquetas",
                css_classes=["heading"],
                halign=Gtk.Align.START,
                hexpand=True,
            )
        )
        self._tags_section_box.append(tags_hdr)

        self._tags_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._tags_section_box.append(self._tags_container)

        outer.append(self._tags_section_box)

        scroll.set_child(outer)
        container.append(scroll)

        # ── Recents section — pinned to the bottom half ───────────────────────
        self._rec_section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._rec_section_box.append(Gtk.Separator())

        rec_hdr = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            margin_start=12,
            margin_end=12,
            margin_top=9,
            margin_bottom=6,
        )
        rec_icon = Gtk.Image.new_from_icon_name("document-open-recent-symbolic")
        rec_icon.add_css_class("dim-label")
        rec_hdr.append(rec_icon)
        rec_hdr.append(
            Gtk.Label(
                label="Recientes",
                css_classes=["heading"],
                halign=Gtk.Align.START,
                hexpand=True,
            )
        )
        self._rec_section_box.append(rec_hdr)

        self._rec_list = Gtk.ListBox(css_classes=["boxed-list"])
        self._rec_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._rec_list.set_margin_start(12)
        self._rec_list.set_margin_end(12)
        self._rec_list.set_margin_bottom(9)
        self._rec_list.connect("row-activated", self._on_section_row_activated)
        self._rec_section_box.append(self._rec_list)

        container.append(self._rec_section_box)
        return container

    def _build_empty_page(self) -> Adw.StatusPage:
        empty = Adw.StatusPage(
            icon_name="accessories-text-editor-symbolic",
            title="Sin libros",
            description='Crea tu primer libro con el botón "+"',
            vexpand=True,
        )
        btn = Gtk.Button(
            label="Crear libro",
            css_classes=["pill", "suggested-action"],
            halign=Gtk.Align.CENTER,
        )
        btn.connect("clicked", lambda _: self._show_create_dialog("book", None))
        empty.set_child(btn)
        return empty

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        self._load_tree()
        self._load_favorites()
        self._load_recents()
        self._load_tags()

    def _load_tree(self) -> None:
        self._store.clear()
        books = self._db.get_books()

        for book in books:
            it_b = self._store.append(None, [book.name, "book", book, _ICONS["book"]])
            for chapter in self._db.get_chapters(book.id):
                it_c = self._store.append(
                    it_b, [chapter.name, "chapter", chapter, _ICONS["chapter"]]
                )
                for doc in self._db.get_documents(chapter.id):
                    self._store.append(
                        it_c, [doc.name, "document", doc, _ICONS["document"]]
                    )

        self._filter.refilter()
        self._tree.expand_all()
        self._stack.set_visible_child_name("empty" if not books else "tree")

    def _load_favorites(self) -> None:
        while (row := self._fav_list.get_row_at_index(0)) is not None:
            self._fav_list.remove(row)

        favorites = self._db.get_favorites()
        for doc in favorites:
            row = Gtk.ListBoxRow()
            row._doc = doc
            lbl = Gtk.Label(
                label=doc.name,
                halign=Gtk.Align.START,
                margin_start=12,
                margin_end=12,
                margin_top=6,
                margin_bottom=6,
            )
            row.set_child(lbl)
            self._fav_list.append(row)

        self._fav_section_box.set_visible(bool(favorites))

    def _load_recents(self) -> None:
        while (row := self._rec_list.get_row_at_index(0)) is not None:
            self._rec_list.remove(row)

        recents = self._db.get_recent_documents(limit=5)
        for doc in recents:
            row = Gtk.ListBoxRow()
            row._doc = doc
            lbl = Gtk.Label(
                label=doc.name,
                halign=Gtk.Align.START,
                margin_start=12,
                margin_end=12,
                margin_top=6,
                margin_bottom=6,
            )
            row.set_child(lbl)
            self._rec_list.append(row)

        self._rec_section_box.set_visible(bool(recents))

    def _load_tags(self) -> None:
        while (ch := self._tags_container.get_last_child()) is not None:
            self._tags_container.remove(ch)

        all_tags = self._db.get_all_tags()
        has_any = False
        for tag, count in all_tags:
            if count == 0:
                continue
            has_any = True

            tag_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

            toggle_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=6,
                margin_start=12,
                margin_end=12,
                margin_top=3,
                margin_bottom=3,
            )
            arrow = Gtk.Image.new_from_icon_name("go-next-symbolic")
            arrow.add_css_class("dim-label")
            lbl = Gtk.Label(
                label=f"{tag.name}  ({count})",
                halign=Gtk.Align.START,
                hexpand=True,
            )
            toggle_box.append(arrow)
            toggle_box.append(lbl)
            toggle_btn = Gtk.Button(css_classes=["flat"], child=toggle_box)
            toggle_btn.set_hexpand(True)
            tag_row.append(toggle_btn)

            doc_list = Gtk.ListBox(css_classes=["boxed-list"])
            doc_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
            doc_list.set_margin_start(24)
            doc_list.set_margin_end(12)
            doc_list.set_margin_bottom(4)

            for doc in self._db.get_docs_by_tag(tag.id):
                row = Gtk.ListBoxRow()
                row._doc = doc
                row_lbl = Gtk.Label(
                    label=doc.name,
                    halign=Gtk.Align.START,
                    margin_start=12,
                    margin_end=12,
                    margin_top=4,
                    margin_bottom=4,
                )
                row.set_child(row_lbl)
                doc_list.append(row)

            doc_list.connect("row-activated", self._on_section_row_activated)

            revealer = Gtk.Revealer(
                child=doc_list,
                transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
                reveal_child=False,
            )
            tag_row.append(revealer)
            self._tags_container.append(tag_row)

            def _on_toggle(_btn, rev=revealer, ico=arrow):
                expanded = rev.get_reveal_child()
                rev.set_reveal_child(not expanded)
                ico.set_from_icon_name(
                    "go-down-symbolic" if not expanded else "go-next-symbolic"
                )

            toggle_btn.connect("clicked", _on_toggle)

        self._tags_section_box.set_visible(has_any)

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Refresh tree, favorites, and recents."""
        self._load()

    # ── Search / filter ───────────────────────────────────────────────────────

    def _on_search_toggled(self, btn: Gtk.ToggleButton) -> None:
        active = btn.get_active()
        self._search_bar.set_search_mode(active)
        if active:
            self._search_entry.grab_focus()
        else:
            self._search_entry.set_text("")

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self._search_query = entry.get_text().strip().lower()
        self._filter.refilter()
        self._tree.expand_all()

    def _on_search_stop(self, _entry) -> None:
        self._search_toggle.set_active(False)

    def _filter_visible(self, model, it, _data) -> bool:
        if not self._search_query:
            return True
        return self._node_matches(model, it, self._search_query)

    def _node_matches(self, model, it, query: str) -> bool:
        name = model.get_value(it, _C_NAME) or ""
        if query in name.lower():
            return True
        child = model.iter_children(it)
        while child:
            if self._node_matches(model, child, query):
                return True
            child = model.iter_next(child)
        return False

    # ── Cell data functions ───────────────────────────────────────────────────

    def _text_cell_data(self, _col, cell, model, it, _data) -> None:
        name = model.get_value(it, _C_NAME) or ""
        q = self._search_query
        if q and q in name.lower():
            idx = name.lower().find(q)
            pre = GLib.markup_escape_text(name[:idx])
            mid = GLib.markup_escape_text(name[idx : idx + len(q)])
            post = GLib.markup_escape_text(name[idx + len(q) :])
            cell.set_property("markup", f"{pre}<b><u>{mid}</u></b>{post}")
        else:
            cell.set_property("markup", GLib.markup_escape_text(name))

    def _star_cell_data(self, _col, cell, model, it, _data) -> None:
        kind = model.get_value(it, _C_TYPE)
        if kind != "document":
            cell.set_property("icon-name", None)
            return
        doc = model.get_value(it, _C_ITEM)
        cell.set_property(
            "icon-name",
            "starred-symbolic" if doc.is_favorite else "non-starred-symbolic",
        )

    # ── Tree events ───────────────────────────────────────────────────────────

    def _on_row_activated(self, _tree, path, col) -> None:
        # Only handles star-column favorite toggle; document opening is via selection.changed
        if col is not self._star_col:
            return
        it = self._filter.get_iter(path)
        if it is None:
            return
        if self._filter.get_value(it, _C_TYPE) != "document":
            return
        doc = self._filter.get_value(it, _C_ITEM)
        self._db.toggle_favorite(doc)
        self._filter.refilter()
        self._load_favorites()

    def _on_selection_changed(self, selection) -> None:
        model, it = selection.get_selected()
        if it is None:
            return
        kind = model.get_value(it, _C_TYPE)
        if kind != "document":
            return
        item = model.get_value(it, _C_ITEM)
        self.emit("document-selected", item)

    def _on_right_click(self, _gesture, _n, x, y) -> None:
        result = self._tree.get_path_at_pos(int(x), int(y))
        if not result or result[0] is None:
            return
        path = result[0]
        it = self._filter.get_iter(path)
        if it is None:
            return
        kind = self._filter.get_value(it, _C_TYPE)
        item = self._filter.get_value(it, _C_ITEM)
        self._show_context_menu(x, y, kind, item)

    def _on_section_row_activated(self, _list, row: Gtk.ListBoxRow) -> None:
        self.emit("document-selected", row._doc)

    # ── Context menu ──────────────────────────────────────────────────────────

    def _show_context_menu_at_path(self, path, kind: str, item) -> None:
        area = self._tree.get_cell_area(path, self._tree.get_column(0))
        self._show_context_menu(area.x + area.width * 0.25, area.y + area.height, kind, item)

    def _show_context_menu(self, x: float, y: float, kind: str, item) -> None:
        if self._ctx_popover:
            self._ctx_popover.unparent()
            self._ctx_popover = None

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            margin_top=4,
            margin_bottom=4,
            width_request=200,
        )

        if kind == "book":
            self._ctx_btn(
                box,
                "Nuevo capítulo",
                "folder-new-symbolic",
                lambda: self._show_create_dialog("chapter", item),
            )
        elif kind == "chapter":
            self._ctx_btn(
                box,
                "Nuevo documento",
                "document-new-symbolic",
                lambda: self._show_create_dialog("document", item),
            )

        self._ctx_btn(
            box,
            "Renombrar",
            "document-edit-symbolic",
            lambda: self._show_rename_dialog(kind, item),
        )

        box.append(Gtk.Separator(margin_top=4, margin_bottom=4))

        self._ctx_btn(
            box,
            "Eliminar",
            "edit-delete-symbolic",
            lambda: self._show_delete_confirm(kind, item),
            destructive=True,
        )

        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1

        popover = Gtk.Popover(child=box, has_arrow=False)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.set_pointing_to(rect)
        popover.set_parent(self._tree)
        self._ctx_popover = popover
        popover.popup()

    def _ctx_btn(
        self, box: Gtk.Box, label: str, icon: str, cb, *, destructive=False
    ) -> None:
        btn = Gtk.Button(css_classes=["flat"])
        row = Gtk.Box(
            spacing=3, margin_start=6, margin_end=6, margin_top=3, margin_bottom=3
        )
        row.append(Gtk.Image(icon_name=icon))
        lbl = Gtk.Label(halign=Gtk.Align.START, hexpand=True)
        lbl.set_label(label)
        if destructive:
            lbl.add_css_class("error")
        row.append(lbl)
        btn.set_child(row)

        def _on_click(_btn):
            if self._ctx_popover:
                self._ctx_popover.popdown()
            cb()

        btn.connect("clicked", _on_click)
        box.append(btn)

    # ── Create dialog ─────────────────────────────────────────────────────────

    def _show_create_dialog(self, kind: str, parent_item) -> None:
        heading, placeholder = _LABELS[kind]

        entry = Gtk.Entry(
            placeholder_text=placeholder,
            activates_default=True,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
        )

        dialog = Adw.AlertDialog(heading=heading)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("create", "Crear")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("create")
        dialog.set_close_response("cancel")

        def on_response(_d, response: str) -> None:
            if response != "create":
                return
            name = entry.get_text().strip()
            if not name:
                return
            try:
                if kind == "book":
                    book = self._storage.create_book(name)
                    self._db.add_book(book)
                elif kind == "chapter":
                    ch = self._storage.create_chapter(parent_item, name)
                    ch.book_id = parent_item.id
                    self._db.add_chapter(ch)
                elif kind == "document":
                    doc = self._storage.create_document(parent_item, name)
                    doc.chapter_id = parent_item.id
                    self._db.add_document(doc)
                    self._load()
                    self._ask_template(doc)
                    return
                self._load()
            except StorageError as exc:
                self._show_error(str(exc))

        dialog.connect("response", on_response)
        dialog.present(self.get_root())

    def _ask_template(self, doc) -> None:
        def on_template_chosen(key: str) -> None:
            content = TemplateDialog.load_content(key)
            if content:
                self._storage.write_document(doc, content)
            self.emit("document-selected", doc)

        TemplateDialog(self.get_root()).show(on_template_chosen)

    # ── Rename dialog ─────────────────────────────────────────────────────────

    def _show_rename_dialog(self, kind: str, item) -> None:
        entry = Gtk.Entry(
            text=item.name,
            activates_default=True,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
        )
        entry.set_position(-1)

        dialog = Adw.AlertDialog(heading="Renombrar")
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("rename", "Renombrar")
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("rename")
        dialog.set_close_response("cancel")

        def on_response(_d, response: str) -> None:
            if response != "rename":
                return
            new_name = entry.get_text().strip()
            if not new_name or new_name == item.name:
                return
            try:
                if kind == "book":
                    updated = self._storage.rename_book(item, new_name)
                    updated.id = item.id
                    self._db.update_book(updated)
                elif kind == "chapter":
                    updated = self._storage.rename_chapter(item, new_name)
                    updated.id = item.id
                    self._db.update_chapter(updated)
                elif kind == "document":
                    updated = self._storage.rename_document(item, new_name)
                    updated.id = item.id
                    self._db.update_document(updated)
                self._load()
            except StorageError as exc:
                self._show_error(str(exc))

        dialog.connect("response", on_response)
        dialog.present(self.get_root())

    # ── Delete confirm ────────────────────────────────────────────────────────

    def _show_delete_confirm(self, kind: str, item) -> None:
        # Validate: must be empty before deleting
        if kind == "book":
            chapters = self._db.get_chapters(item.id)
            if chapters:
                n = len(chapters)
                self._show_error(
                    f'El libro "{item.name}" contiene {n} capítulo{"s" if n > 1 else ""}.\n'
                    "Elimina primero todos los capítulos y documentos que contiene."
                )
                return
        elif kind == "chapter":
            docs = self._db.get_documents(item.id)
            if docs:
                n = len(docs)
                self._show_error(
                    f'El capítulo "{item.name}" contiene {n} documento{"s" if n > 1 else ""}.\n'
                    "Elimina primero todos los documentos que contiene."
                )
                return

        kind_es = {"book": "libro", "chapter": "capítulo", "document": "documento"}[kind]
        dialog = Adw.AlertDialog(
            heading=f"¿Eliminar {kind_es}?",
            body=(
                f'"{item.name}" se eliminará permanentemente. '
                "Esta acción no se puede deshacer."
            ),
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("delete", "Eliminar")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_d, response: str) -> None:
            if response != "delete":
                return
            try:
                if kind == "book":
                    self._storage.delete_book(item)
                    self._db.delete_book(item.id)
                elif kind == "chapter":
                    self._storage.delete_chapter(item)
                    self._db.delete_chapter(item.id)
                elif kind == "document":
                    self._storage.delete_document(item)
                    self._db.delete_document(item.id)
                self._load()
            except Exception as exc:
                self._show_error(str(exc))

        dialog.connect("response", on_response)
        dialog.present(self.get_root())

    # ── Error helper ──────────────────────────────────────────────────────────

    def _show_error(self, message: str) -> None:
        dialog = Adw.AlertDialog(heading="Error", body=message)
        dialog.add_response("ok", "Entendido")
        dialog.present(self.get_root())
