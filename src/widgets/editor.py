import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from pathlib import Path

from gi.repository import Adw, GLib, GObject, Gtk, WebKit

from ..models import Document
from ..services import Database, StorageService

# Absolute path to data/ so the WebView can reach CSS and JS regardless of cwd
_DATA = Path(__file__).resolve().parent.parent.parent / "data"

# HTML template: structural CSS is embedded; theme variables come from editor-*.css
_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style id="theme-css">{theme_css}</style>
<style>
/* ── Structural styles (layout, typography, spacing) ─────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

html, body {{
  height: 100%;
  background: var(--bg);
  color: var(--text);
  /* Cantarell — fuente sistema GNOME (§3 design-guidelines) */
  font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
  font-size: 15px;
  line-height: 1.7;
}}

#editor {{
  outline: none;
  /* L token (24px) top/bottom; XL (36px) lateral — modo normal ocupa todo el ancho (§6) */
  padding: 24px 48px;
  min-height: 100vh;
  caret-color: var(--accent);
  word-break: break-word;
}}

#editor:empty::before {{
  content: 'Empieza a escribir…';
  color: var(--placeholder);
  pointer-events: none;
}}

/* Headings — coloreados con el acento del sistema (§2 design-guidelines) */
h1, h2, h3 {{
  color: var(--accent);
  font-family: 'Cantarell', sans-serif;
  line-height: 1.3;
  margin-top: 1.2em;
  margin-bottom: 0.4em;
}}
h1 {{ font-size: 2em;    font-weight: 800; }}  /* .title-1 (§3) */
h2 {{ font-size: 1.5em;  font-weight: 700; }}  /* .title-2 */
h3 {{ font-size: 1.25em; font-weight: 600; }}  /* .title-3 */

p {{ margin: 0.5em 0; }}

/* Código inline */
code {{
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 0.875em;
  color: var(--code-fg);
  background: var(--code-bg);
  border-radius: 4px;
  padding: 0.1em 0.35em;
}}

a {{ color: var(--link); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

/* Cross-references [[name]] — wiki-style green links */
a.crossref {{
  color: var(--crossref);
  background: var(--crossref-bg);
  border-radius: 3px;
  padding: 0.05em 0.3em;
  text-decoration: none;
  cursor: pointer;
}}
a.crossref:hover {{ text-decoration: underline; }}

ul, ol {{ padding-left: 1.5em; margin: 0.5em 0; }}
li {{ margin: 0.25em 0; }}

::selection {{ background: var(--selection); }}

::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
</style>
</head>
<body>
<div id="editor" contenteditable="true" spellcheck="true"></div>
<script>{editor_js}</script>
</body>
</html>
"""


class CodexEditorWidget(Gtk.Box):
    """
    WebKit-based WYSIWYG markdown editor.

    Signals
    -------
    document-saved(doc: Document)
        Emitted after a successful save (manual or auto).
    content-changed()
        Emitted whenever the user edits the document.
    navigate-document(name: str)
        Emitted when the user clicks a [[crossref]] link inside the editor.
    """

    __gtype_name__ = "CodexEditorWidget"

    __gsignals__ = {
        "document-saved": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (GObject.TYPE_PYOBJECT,),
        ),
        "content-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "navigate-document": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "word-count-changed": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(self, storage: StorageService, db: Database, indexer=None, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self._storage = storage
        self._db = db
        self._indexer = indexer  # optional services.Indexer
        self._doc: Document | None = None
        self._dirty = False
        self._loaded = False  # True once the WebView has finished its first load
        self._pending_md: str | None = None  # content to inject after load
        self._autosave_id: int | None = None
        self._crossref_open = False

        # Detect dark mode first so the HTML template uses the right theme
        self._is_dark = Adw.StyleManager.get_default().get_dark()
        Adw.StyleManager.get_default().connect("notify::dark", self._on_dark_changed)

        self._build_webview()
        self._schedule_autosave()

    def _build_webview(self) -> None:
        # UserContentManager — registers JS → Python message channels
        ucm = WebKit.UserContentManager()
        ucm.register_script_message_handler("save")  # JS posts markdown text
        ucm.register_script_message_handler("editor")  # JS posts 'dirty'
        ucm.register_script_message_handler("crossref")  # JS typed [[
        ucm.register_script_message_handler("navigate")  # JS clicked a crossref
        ucm.register_script_message_handler(
            "wordcount"
        )  # JS posts word count (debounced)
        ucm.connect("script-message-received::save", self._on_js_save)
        ucm.connect("script-message-received::editor", self._on_js_editor)
        ucm.connect("script-message-received::crossref", self._on_js_crossref)
        ucm.connect("script-message-received::navigate", self._on_js_navigate)
        ucm.connect("script-message-received::wordcount", self._on_js_wordcount)

        settings = WebKit.Settings()
        settings.set_enable_javascript(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_enable_write_console_messages_to_stdout(True)
        settings.set_enable_developer_extras(True)

        self._wv = WebKit.WebView(user_content_manager=ucm)
        self._wv.set_settings(settings)
        self._wv.set_vexpand(True)
        self._wv.set_hexpand(True)
        self._wv.connect("load-changed", self._on_load_changed)
        self._wv.connect("decide-policy", self._on_decide_policy)
        self.append(self._wv)

        self._reload_html()

    # ── Public API ────────────────────────────────────────────────────────────

    def load_document(self, doc: Document) -> None:
        """Load a Document into the editor (reads from filesystem)."""
        self._doc = doc
        self._dirty = False
        content = self._storage.read_document(doc)
        if self._loaded:
            self._inject_content(content)
        else:
            self._pending_md = content  # will be injected on load-finished

    def save_current(self) -> None:
        """Request save: asks JS for the markdown, then writes the file."""
        if not self._doc:
            return
        self._js("codexSave();")

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def set_focus_mode(self, enabled: bool) -> None:
        """Apply or remove the focus-mode CSS to the editor's WebView."""
        if enabled:
            self._js(
                "var e=document.getElementById('editor');"
                "e.style.maxWidth='720px'; e.style.margin='0 auto';"
            )
        else:
            self._js(
                "var e=document.getElementById('editor');"
                "e.style.maxWidth=''; e.style.margin='';"
            )

    # ── Formatting (called by toolbar) ────────────────────────────────────────

    def format(self, cmd: str, value: str = "") -> None:
        safe_cmd = cmd.replace("'", "")
        safe_value = value.replace("'", "")
        self._js(
            f"window._editor && window._editor.format('{safe_cmd}', '{safe_value}');"
        )

    def insert_code(self) -> None:
        self._js("window._editor && window._editor.insertCode();")

    def trigger_crossref(self) -> None:
        """Open the cross-reference picker from the toolbar button.

        Restores focus to the editor and saves the current cursor position
        into _savedRange before the dialog opens, so codexInsertRef can
        insert the anchor at the right place without requiring [[ to be typed.
        """
        self._js(
            "if (window._editor) {"
            "  window._editor._el.focus();"
            "  const sel = window.getSelection();"
            "  if (sel && sel.rangeCount) {"
            "    window._editor._savedRange = sel.getRangeAt(0).cloneRange();"
            "  }"
            "}"
        )
        GLib.idle_add(self._show_crossref_dialog)

    # ── Internal: JS execution ────────────────────────────────────────────────

    def _js(self, script: str) -> None:
        """Fire-and-forget JavaScript execution."""
        self._wv.evaluate_javascript(script, -1, None, None, None, None)

    def _inject_content(self, markdown: str) -> None:
        # Escape backticks and template-literal special chars for a JS template literal
        escaped = markdown.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
        self._js(f"codexLoad(`{escaped}`);")

    # ── Internal: HTML template ───────────────────────────────────────────────

    def _reload_html(self) -> None:
        """(Re)build the full HTML page and load it into the WebView."""
        self._loaded = False
        css_file = "editor-dark.css" if self._is_dark else "editor-light.css"
        theme_css = (_DATA / "css" / css_file).read_text(encoding="utf-8")
        editor_js = (_DATA / "js" / "editor.js").read_text(encoding="utf-8")
        html = _HTML_TEMPLATE.format(
            theme_css=theme_css,
            editor_js=editor_js,
        )
        self._wv.load_html(html, "file:///")

    # ── Internal: dark-mode switch (task 8) ───────────────────────────────────

    def _on_dark_changed(self, manager: Adw.StyleManager, _param) -> None:
        self._is_dark = manager.get_dark()
        if not self._loaded:
            self._reload_html()
            return
        # Swap only the CSS variables — no page reload, content is preserved
        css_file = "editor-dark.css" if self._is_dark else "editor-light.css"
        theme_css = (_DATA / "css" / css_file).read_text(encoding="utf-8")
        escaped = theme_css.replace("`", "\\`").replace("$", "\\$")
        self._js(f"document.getElementById('theme-css').textContent = `{escaped}`;")

    # ── Internal: WebKit signals ──────────────────────────────────────────────

    def _on_decide_policy(self, _wv, decision, decision_type) -> bool:
        """Intercept navigation: external links open in the system browser."""
        if decision_type != WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            return False
        action = decision.get_navigation_action()
        uri = action.get_request().get_uri()
        # Let the editor's own page load freely
        if uri.startswith("file:///") or uri.startswith("about:"):
            return False
        # codex:// links are handled in JS via the 'navigate' message handler
        if uri.startswith("codex://"):
            decision.ignore()
            return True
        # Everything else (http/https) → open in system browser, block WebView
        from gi.repository import Gio

        Gio.AppInfo.launch_default_for_uri(uri, None)
        decision.ignore()
        return True

    def _on_load_changed(self, _wv, event: WebKit.LoadEvent) -> None:
        if event != WebKit.LoadEvent.FINISHED:
            return
        self._loaded = True
        if self._pending_md is not None:
            self._inject_content(self._pending_md)
            self._pending_md = None

    def _on_js_save(self, _ucm, jsc_value) -> None:
        """JS posted the markdown content via window.webkit.messageHandlers.save."""
        try:
            markdown = jsc_value.to_string()
        except Exception:
            return
        if not self._doc or not markdown:
            return
        try:
            self._storage.write_document(self._doc, markdown)
            self._db.update_document(self._doc)
            if self._indexer:
                self._indexer.update_content_index(self._doc, markdown)
                self._indexer.index_document(self._doc, markdown)
            else:
                self._db.index_document_content(self._doc, markdown)
            self._dirty = False
            self.emit("document-saved", self._doc)
        except Exception as exc:
            print(f"[Codex] Save error: {exc}")

    def _on_js_editor(self, _ucm, _jsc_value) -> None:
        """JS notified us that the document was edited."""
        self._dirty = True
        self.emit("content-changed")

    def _on_js_crossref(self, _ucm, _jsc_value) -> None:
        """JS detected [[ — open the cross-reference picker dialog."""
        GLib.idle_add(self._show_crossref_dialog)

    def _on_js_navigate(self, _ucm, jsc_value) -> None:
        """JS clicked a [[crossref]] link — emit signal so window can navigate."""
        try:
            name = jsc_value.to_string()
        except Exception:
            return
        if name:
            self.emit("navigate-document", name)

    def _on_js_wordcount(self, _ucm, jsc_value) -> None:
        """JS posted word count after 1-second debounce."""
        try:
            count = int(jsc_value.to_string())
        except Exception:
            return
        self.emit("word-count-changed", count)

    # ── Cross-reference picker dialog ─────────────────────────────────────────

    def _show_crossref_dialog(self) -> None:
        if self._crossref_open:
            return
        all_docs = self._db.get_all_documents()
        if not all_docs:
            return
        self._crossref_open = True

        # ── Search entry ──────────────────────────────────────────────────────
        search = Gtk.SearchEntry(placeholder_text="Buscar documento…")
        search.set_margin_bottom(6)

        # ── Document list ─────────────────────────────────────────────────────
        list_box = Gtk.ListBox(css_classes=["boxed-list"])
        list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)

        for doc in all_docs:
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
            list_box.append(row)

        # Select first row by default
        first = list_box.get_row_at_index(0)
        if first:
            list_box.select_row(first)

        def _filter(_entry):
            query = search.get_text().strip().lower()
            i = 0
            while (row := list_box.get_row_at_index(i)) is not None:
                row.set_visible(not query or query in row._doc.name.lower())
                i += 1

        search.connect("search-changed", _filter)

        sw = Gtk.ScrolledWindow(min_content_height=180, max_content_height=300)
        sw.set_child(list_box)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.append(search)
        box.append(sw)

        # ── Dialog ───────────────────────────────────────────────────────────
        dialog = Adw.AlertDialog(heading="Insertar referencia")
        dialog.set_extra_child(box)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("insert", "Insertar")
        dialog.set_response_appearance("insert", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("insert")
        dialog.set_close_response("cancel")

        def on_response(_d, response: str) -> None:
            self._crossref_open = False
            if response != "insert":
                return
            row = list_box.get_selected_row()
            if not row:
                return
            name = row._doc.name.replace("'", "\\'")
            self._js(f"codexInsertRef('{name}');")

        dialog.connect("response", on_response)
        dialog.present(self.get_root())
        return False  # remove idle_add source

    # ── Internal: auto-save (task 7) ─────────────────────────────────────────

    def _schedule_autosave(self) -> None:
        self._autosave_id = GLib.timeout_add(30_000, self._autosave_tick)

    def _autosave_tick(self) -> bool:
        if self._dirty and self._doc:
            self.save_current()
        return GLib.SOURCE_CONTINUE

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Cancel the autosave timer. Call before destroying the widget."""
        if self._autosave_id is not None:
            GLib.source_remove(self._autosave_id)
            self._autosave_id = None
