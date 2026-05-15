from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from pathlib import Path

from gi.repository import Adw, Gdk, Gio, Gtk

from .models import Document
from .services import Database, Exporter, ExportError, Indexer, StorageService
from .services.graph_service import GraphService
from .services.settings import Settings
from .widgets.backlinks_panel import BacklinksPanel
from .widgets.editor import CodexEditorWidget
from .widgets.graph_view import GraphView
from .widgets.preferences_window import PreferencesWindow
from .widgets.search_overlay import SearchOverlay
from .widgets.sidebar import CodexSidebar
from .widgets.tag_bar import TagBar
from .widgets.toolbar import EditorToolbar


class CodexWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Codex")
        self.set_default_size(1100, 700)

        self._settings = Settings()
        self._storage = StorageService()
        self._db = Database()
        self._db.connect()
        self._indexer = Indexer(self._db, self._storage)
        self._current_doc: Document | None = None
        self._focus_mode = False

        self._setup_ui()
        self._setup_actions()
        self._apply_stored_settings()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self._toast_overlay = Adw.ToastOverlay()
        self.set_content(self._toast_overlay)

        main_overlay = Gtk.Overlay()
        self._toast_overlay.set_child(main_overlay)

        self._split_view = Adw.NavigationSplitView()
        w = self._settings.get("sidebar_width", 280)
        self._split_view.set_min_sidebar_width(w)
        self._split_view.set_max_sidebar_width(w + 60)
        main_overlay.set_child(self._split_view)

        # Search overlay (floats on top of split view)
        self._search_overlay = SearchOverlay(db=self._db)
        self._search_overlay.set_halign(Gtk.Align.CENTER)
        self._search_overlay.set_valign(Gtk.Align.START)
        self._search_overlay.set_size_request(600, -1)
        self._search_overlay.connect("document-selected", self._on_document_selected)
        main_overlay.add_overlay(self._search_overlay)

        # Focus-mode ESC hint (hidden by default)
        self._focus_hint = Gtk.Label(
            label="Esc para salir del modo enfocado",
            css_classes=["caption"],
            halign=Gtk.Align.END,
            valign=Gtk.Align.END,
            margin_end=18,
            margin_bottom=18,
        )
        self._focus_hint.set_opacity(0.35)
        self._focus_hint.set_visible(False)
        main_overlay.add_overlay(self._focus_hint)

        # ── Sidebar pane ──────────────────────────────────────────────────────
        self._sidebar = CodexSidebar(storage=self._storage, db=self._db)
        self._sidebar.connect("document-selected", self._on_document_selected)

        sidebar_nav = Adw.NavigationPage(title="Biblioteca")
        sidebar_nav.set_child(self._sidebar)
        self._split_view.set_sidebar(sidebar_nav)

        # ── Content pane ──────────────────────────────────────────────────────
        self._content_toolbar_view = Adw.ToolbarView()

        self._content_header = Adw.HeaderBar()
        self._doc_title_label = Gtk.Label(label="Codex", css_classes=["heading"])
        self._content_header.set_title_widget(self._doc_title_label)

        # Export button
        self._export_btn = Gtk.Button(
            icon_name="document-save-as-symbolic",
            tooltip_text="Exportar (Ctrl+E)",
            css_classes=["flat"],
            sensitive=False,
        )
        self._export_btn.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Exportar documento"]
        )
        self._export_btn.connect("clicked", lambda _: self.show_export_dialog())
        self._content_header.pack_end(self._export_btn)

        # Graph view button
        graph_btn = Gtk.Button(
            icon_name="view-grid-symbolic",
            tooltip_text="Vista de grafo (Ctrl+G)",
            css_classes=["flat"],
        )
        graph_btn.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Abrir vista de grafo"]
        )
        graph_btn.connect("clicked", lambda _: self.open_graph_view())
        self._content_header.pack_end(graph_btn)

        # Preferences button
        prefs_btn = Gtk.Button(
            icon_name="preferences-system-symbolic",
            tooltip_text="Preferencias",
            css_classes=["flat"],
        )
        prefs_btn.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Abrir preferencias"]
        )
        prefs_btn.connect("clicked", lambda _: self.open_preferences())
        self._content_header.pack_end(prefs_btn)

        # App menu button (About, etc.)
        app_menu = Gio.Menu()
        app_menu.append("Acerca de Codex", "app.about")
        menu_btn = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            menu_model=app_menu,
            tooltip_text="Menú",
            css_classes=["flat"],
        )
        menu_btn.update_property([Gtk.AccessibleProperty.LABEL], ["Menú de la aplicación"])
        self._content_header.pack_end(menu_btn)

        self._content_toolbar_view.add_top_bar(self._content_header)

        self._toolbar = EditorToolbar()
        self._content_toolbar_view.add_top_bar(self._toolbar)

        self._content_stack = Gtk.Stack()
        self._content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._content_stack.add_named(self._build_empty_page(), "empty")
        self._content_stack.add_named(self._build_editor_page(), "editor")
        self._content_toolbar_view.set_content(self._content_stack)

        content_nav = Adw.NavigationPage(title="Codex")
        content_nav.set_child(self._content_toolbar_view)
        self._split_view.set_content(content_nav)

        # Esc key exits focus mode
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _build_empty_page(self) -> Adw.StatusPage:
        return Adw.StatusPage(
            icon_name="accessories-text-editor-symbolic",
            title="Selecciona un documento",
            description="Elige un documento del panel izquierdo para empezar a escribir",
            vexpand=True,
        )

    def _build_editor_page(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self._editor = CodexEditorWidget(
            storage=self._storage,
            db=self._db,
            indexer=self._indexer,
        )
        self._editor.set_vexpand(True)
        self._editor.connect("document-saved", self._on_document_saved)
        self._editor.connect("content-changed", self._on_content_changed)
        self._editor.connect("navigate-document", self._on_navigate_document)
        self._editor.connect("word-count-changed", self._on_word_count_changed)
        box.append(self._editor)

        self._toolbar.set_editor(self._editor)

        # Backlinks panel
        box.append(Gtk.Separator())
        self._backlinks = BacklinksPanel()
        self._backlinks.connect("document-selected", self._on_document_selected)
        box.append(self._backlinks)

        # Tag bar
        box.append(Gtk.Separator())
        self._tag_bar = TagBar()
        box.append(self._tag_bar)

        # Footer: word count + reading time
        self._footer = Gtk.Label(
            css_classes=["caption", "numeric"],
            halign=Gtk.Align.END,
            margin_end=12,
            margin_top=4,
            margin_bottom=4,
        )
        box.append(self._footer)

        return box

    # ── Actions ───────────────────────────────────────────────────────────────

    def _setup_actions(self) -> None:
        def _add(name: str, callback, shortcuts: list[str] | None = None) -> None:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if shortcuts:
                self.get_application().set_accels_for_action(f"win.{name}", shortcuts)

        _add("save-document", lambda *_: self._editor_save_and_toast(), ["<primary>s"])
        _add("export-document", lambda *_: self.show_export_dialog(), ["<primary>e"])
        _add("toggle-focus", lambda *_: self.toggle_focus_mode(), ["<primary><shift>f"])
        _add("open-graph", lambda *_: self.open_graph_view(), ["<primary>g"])
        _add("open-prefs", lambda *_: self.open_preferences())

    def _apply_stored_settings(self) -> None:
        """Apply settings that affect the UI immediately at startup."""
        scheme = {
            "default": Adw.ColorScheme.DEFAULT,
            "force-light": Adw.ColorScheme.FORCE_LIGHT,
            "force-dark": Adw.ColorScheme.FORCE_DARK,
        }.get(self._settings.get("theme"), Adw.ColorScheme.DEFAULT)
        Adw.StyleManager.get_default().set_color_scheme(scheme)

    # ── Key handler ───────────────────────────────────────────────────────────

    def _on_key_pressed(self, _ctrl, keyval: int, _keycode: int, _state) -> bool:
        if self._focus_mode and keyval == Gdk.KEY_Escape:
            self.toggle_focus_mode()
            return True
        return False

    # ── Focus mode ────────────────────────────────────────────────────────────

    def toggle_focus_mode(self) -> None:
        """Toggle distraction-free writing mode (Ctrl+Shift+F / Esc)."""
        self._focus_mode = not self._focus_mode
        if self._focus_mode:
            self._enter_focus_mode()
        else:
            self._exit_focus_mode()

    def _enter_focus_mode(self) -> None:
        # Collapse sidebar so only content pane is visible
        self._split_view.set_collapsed(True)
        try:
            self._split_view.set_show_content(True)
        except AttributeError:
            pass

        # Hide chrome
        self._content_header.set_visible(False)
        self._toolbar.set_visible(False)
        self._backlinks.set_visible(False)
        self._tag_bar.set_visible(False)
        self._footer.set_visible(False)

        # Hint overlay
        self._focus_hint.set_visible(True)

        # Center editor content at 720 px
        self._editor.set_focus_mode(True)

    def _exit_focus_mode(self) -> None:
        self._split_view.set_collapsed(False)

        self._content_header.set_visible(True)
        self._toolbar.set_visible(True)
        self._backlinks.set_visible(True)
        self._tag_bar.set_visible(True)
        self._footer.set_visible(True)

        self._focus_hint.set_visible(False)

        self._editor.set_focus_mode(False)

    # ── Graph view ────────────────────────────────────────────────────────────

    def open_graph_view(self) -> None:
        """Open the document connection graph in a secondary window (Ctrl+G)."""
        gs = GraphService(self._db)
        gv = GraphView(gs)
        gv.connect("navigate-document", self._on_graph_navigate)

        header = Adw.HeaderBar()
        header.set_title_widget(
            Gtk.Label(label="Vista de Grafo", css_classes=["heading"])
        )

        def _graph_btn(icon, tip, cb):
            btn = Gtk.Button(icon_name=icon, css_classes=["flat"], tooltip_text=tip)
            btn.connect("clicked", lambda _: cb())
            return btn

        header.pack_end(_graph_btn("view-refresh-symbolic", "Recargar grafo", gv.reload))

        # PDF export
        def _export_pdf():
            fd = Gtk.FileDialog()
            fd.set_title("Guardar grafo como PDF")
            fd.set_initial_name("grafo-codex.pdf")

            def on_save(_fd, result):
                try:
                    gfile = _fd.save_finish(result)
                except Exception:
                    return
                gv.export_pdf(gfile.get_path())

            fd.save(win, None, on_save)

        header.pack_end(_graph_btn("document-save-as-symbolic", "Exportar PDF (tamaño carta)", _export_pdf))
        header.pack_end(_graph_btn("zoom-fit-best-symbolic",    "Centrar grafo",              gv.fit_to_view))
        header.pack_end(_graph_btn("zoom-out-symbolic",         "Alejar",                     gv.zoom_out))
        header.pack_end(_graph_btn("zoom-in-symbolic",          "Acercar",                    gv.zoom_in))

        tv = Adw.ToolbarView()
        tv.add_top_bar(header)
        tv.set_content(gv)

        win = Adw.Window(application=self.get_application())
        win.set_title("Vista de Grafo — Codex")
        win.set_default_size(960, 680)
        win.set_content(tv)
        win.set_transient_for(self)
        win.present()

    def _on_graph_navigate(self, _view, doc_id: int) -> None:
        doc = self._db.get_document_by_id(doc_id)
        if doc:
            self._on_document_selected(None, doc)

    # ── Preferences ───────────────────────────────────────────────────────────

    def open_preferences(self) -> None:
        """Open the preferences window."""
        prefs = PreferencesWindow(
            settings=self._settings,
            on_apply=self._apply_setting,
        )
        prefs.set_transient_for(self)
        prefs.present()

    def _apply_setting(self, key: str, value) -> None:
        """Called by PreferencesWindow immediately when a setting changes."""
        if key == "editor_font":
            font_map = {
                "system": "Cantarell, Noto Sans, system-ui, sans-serif",
                "mono": "JetBrains Mono, Fira Code, Cascadia Code, monospace",
                "serif": "Georgia, Linux Libertine, serif",
            }
            css = font_map.get(str(value), font_map["system"])
            self._editor._js(f"document.body.style.fontFamily = `{css}`;")
        elif key == "editor_font_size":
            self._editor._js(f"document.body.style.fontSize = `{int(value)}px`;")
        elif key == "sidebar_width":
            w = int(value)
            self._split_view.set_min_sidebar_width(w)
            self._split_view.set_max_sidebar_width(w + 60)

    # ── Signals ───────────────────────────────────────────────────────────────

    def toggle_search(self) -> None:
        """Toggle the full-text search overlay (Ctrl+F)."""
        self._search_overlay.toggle()

    def _on_document_selected(self, _widget, doc: Document) -> None:
        self._current_doc = doc
        self._db.record_open(doc)
        self._editor.load_document(doc)
        self._doc_title_label.set_label(doc.name)
        self._footer.set_label("")
        self._content_stack.set_visible_child_name("editor")
        self._backlinks.update(doc, self._db)
        self._tag_bar.load(doc, self._db)
        self._export_btn.set_sensitive(True)
        self._sidebar.refresh()

    def _on_navigate_document(self, _editor, name: str) -> None:
        doc = self._db.get_document_by_name(name)
        if doc:
            self._on_document_selected(None, doc)
        else:
            self.show_toast(f"Documento «{name}» no encontrado")

    def _on_document_saved(self, _editor, doc: Document) -> None:
        self.show_toast("Guardado")
        self._backlinks.update(doc, self._db)
        self._sidebar.refresh()

    def _on_content_changed(self, _editor) -> None:
        pass

    def _on_word_count_changed(self, _editor, count: int) -> None:
        if count == 1:
            words = "1 palabra"
        else:
            words = f"{count:,} palabras"
        mins = max(1, round(count / 250))
        self._footer.set_label(f"{words} · ~{mins} min lectura")

    # ── Export ────────────────────────────────────────────────────────────────

    def show_export_dialog(self) -> None:
        if not self._current_doc:
            return

        fmt_row = Adw.ComboRow(title="Formato")
        fmt_row.set_model(
            Gtk.StringList.new(["Markdown (.md)", "Texto plano (.txt)", "PDF (.pdf)"])
        )
        # Pre-select stored default format
        default_fmt = self._settings.get("export_format", "md")
        fmt_row.set_selected({"md": 0, "txt": 1, "pdf": 2}.get(default_fmt, 0))

        scope_row = Adw.ComboRow(title="Alcance")
        scope_row.set_model(
            Gtk.StringList.new(
                ["Documento actual", "Capítulo completo", "Libro completo"]
            )
        )

        group = Adw.PreferencesGroup()
        group.add(fmt_row)
        group.add(scope_row)

        dialog = Adw.AlertDialog(heading="Exportar")
        dialog.set_extra_child(group)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("export", "Exportar…")
        dialog.set_response_appearance("export", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("export")
        dialog.set_close_response("cancel")

        def on_response(_d, response: str) -> None:
            if response != "export":
                return
            fmt_map = ["md", "txt", "pdf"]
            ext_map = [".md", ".txt", ".pdf"]
            fi = fmt_row.get_selected()
            si = scope_row.get_selected()
            fmt = fmt_map[fi]
            ext = ext_map[fi]
            doc = self._current_doc

            if si == 0:
                target, default_name = doc, doc.name + ext
            elif si == 1:
                target = self._db.get_chapter_by_id(doc.chapter_id)
                default_name = (target.name if target else doc.name) + ext
            else:
                ch = self._db.get_chapter_by_id(doc.chapter_id)
                target = self._db.get_book_by_id(ch.book_id) if ch else None
                default_name = (target.name if target else doc.name) + ext

            if not target:
                self.show_toast("No se pudo determinar el alcance")
                return
            self._do_export(target, fmt, default_name)

        dialog.connect("response", on_response)
        dialog.present(self)

    def _do_export(self, target, fmt: str, default_name: str) -> None:
        fd = Gtk.FileDialog()
        fd.set_title("Exportar documento")
        fd.set_initial_name(default_name)

        def on_save(_fd, result) -> None:
            try:
                gfile = _fd.save_finish(result)
            except Exception:
                return
            dest = Path(gfile.get_path())
            try:
                Exporter(self._storage, self._db).export(target, fmt, dest)
                self.show_toast(f"Exportado en {dest}")
            except ExportError as exc:
                self.show_toast(f"Error al exportar: {exc}")

        fd.save(self, None, on_save)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _editor_save_and_toast(self) -> None:
        if self._editor.is_dirty:
            self._editor.save_current()
        else:
            self.show_toast("Sin cambios")

    def show_toast(self, message: str) -> None:
        self._toast_overlay.add_toast(Adw.Toast(title=message))

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def do_close_request(self) -> bool:
        if self._focus_mode:
            self._exit_focus_mode()
        if self._editor.is_dirty:
            self._editor.save_current()
        self._editor.stop()
        self._db.close()
        return False
