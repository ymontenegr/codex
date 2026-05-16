from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")

from typing import TYPE_CHECKING

from gi.repository import Adw, Gdk, Gtk

if TYPE_CHECKING:
    from .editor import CodexEditorWidget


class EditorToolbar(Gtk.Box):
    """Horizontal formatting toolbar for the Codex editor."""

    __gtype_name__ = "EditorToolbar"

    _FONTS = [
        "Cantarell",
        "Ubuntu",
        "Noto Sans",
        "Georgia",
        "Roboto",
        "Playfair Display",
        "Open Sans",
        "Lato",
        "Merriweather",
        "Courier New",
        "JetBrains Mono",
        "Fira Code",
    ]

    _COLOR_PALETTE = [
        ("#1c1c1c", "Negro"),
        ("#e01b24", "Rojo"),
        ("#e66100", "Naranja"),
        ("#c9a227", "Dorado"),
        ("#33d17a", "Verde"),
        ("#3584e4", "Azul"),
        ("#1a5fb4", "Azul oscuro"),
        ("#9141ac", "Morado"),
        ("#613583", "Violeta"),
        ("#865e3c", "Marrón"),
        ("#77767b", "Gris"),
        ("#2ec27e", "Esmeralda"),
    ]

    def __init__(self, **kwargs):
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
            **kwargs,
        )
        self.add_css_class("toolbar")
        self.add_css_class("codex-toolbar")
        self._editor: CodexEditorWidget | None = None
        self._link_dialog_open = False
        self._current_color = "#1c1c1c"
        self._color_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self._color_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self._build()

    def set_editor(self, editor: CodexEditorWidget) -> None:
        self._editor = editor

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Font family dropdown
        font_store = Gtk.StringList()
        for f in self._FONTS:
            font_store.append(f)
        self._font_dd = Gtk.DropDown(
            model=font_store,
            selected=self._FONTS.index("Ubuntu"),
            tooltip_text="Familia de fuente",
        )
        self._font_dd.set_size_request(80, -1)
        self._font_dd.set_margin_top(3)
        self._font_dd.set_margin_bottom(3)
        self._font_dd.connect("notify::selected", self._on_font_changed)
        self.append(self._font_dd)

        self._sep()

        # Font size spinner
        adj = Gtk.Adjustment(
            value=15, lower=8, upper=96, step_increment=1, page_increment=4
        )
        self._size_spin = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        self._size_spin.set_numeric(True)
        self._size_spin.set_width_chars(3)
        self._size_spin.set_tooltip_text("Tamaño de fuente (px)")
        self._size_spin.set_margin_top(4)
        self._size_spin.set_margin_bottom(4)
        self._size_spin.connect("value-changed", self._on_size_changed)
        self.append(self._size_spin)

        self._sep()

        # Text color picker
        self._build_color_btn()

        self._sep()

        # Bold / Italic / Code
        self._btn_icon(
            "format-text-bold-symbolic",
            "Negrita (Ctrl+B)",
            lambda: self._cmd("bold"),
            css="btn-bold",
        )
        self._btn_icon(
            "format-text-italic-symbolic",
            "Cursiva (Ctrl+I)",
            lambda: self._cmd("italic"),
            css="btn-italic",
        )
        self._btn_label(
            "</>",
            "Código inline (Ctrl+Shift+C)",
            lambda: self._editor and self._editor.insert_code(),
            css="btn-code",
        )

        self._sep()

        # Headings
        self._btn_label("H1", "Encabezado 1", lambda: self._block("h1"), css="btn-heading")
        self._btn_label("H2", "Encabezado 2", lambda: self._block("h2"), css="btn-heading")
        self._btn_label("H3", "Encabezado 3", lambda: self._block("h3"), css="btn-heading")

        self._sep()

        # Lists
        self._btn_icon(
            "view-list-bullet-symbolic",
            "Lista no ordenada",
            lambda: self._cmd("insertUnorderedList"),
            css="btn-list",
        )
        self._btn_icon(
            "view-list-ordered-symbolic",
            "Lista ordenada",
            lambda: self._cmd("insertOrderedList"),
            css="btn-list",
        )

        self._sep()

        # Link + crossref
        self._btn_icon(
            "insert-link-symbolic",
            "Insertar enlace web",
            self._show_link_dialog,
            css="btn-link",
        )
        self._btn_label(
            "[[…]]",
            "Insertar referencia a documento interno",
            lambda: self._editor and self._editor.trigger_crossref(),
            css="btn-crossref",
        )

    def _build_color_btn(self) -> None:
        grid = Gtk.FlowBox(
            min_children_per_line=4,
            max_children_per_line=4,
            row_spacing=6,
            column_spacing=6,
            margin_top=10,
            margin_bottom=10,
            margin_start=10,
            margin_end=10,
            homogeneous=True,
            selection_mode=Gtk.SelectionMode.NONE,
        )

        for hex_color, name in self._COLOR_PALETTE:
            swatch = Gtk.Button(tooltip_text=name)
            swatch.set_size_request(24, 24)
            cls = f"swatch-{hex_color[1:]}"
            swatch.add_css_class("color-swatch")
            swatch.add_css_class(cls)
            provider = Gtk.CssProvider()
            provider.load_from_string(
                f".{cls} {{"
                f"  background-color: {hex_color};"
                f"  border-radius: 50%;"
                f"  padding: 0;"
                f"  min-width: 24px;"
                f"  min-height: 24px;"
                f"  border: 2px solid alpha(black, 0.15);"
                f"}}"
                f".{cls}:hover {{"
                f"  border-color: alpha(black, 0.4);"
                f"}}"
            )
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
            swatch.connect("clicked", lambda _b, c=hex_color: self._apply_color(c))
            grid.append(swatch)

        self._color_popover = Gtk.Popover(child=grid, has_arrow=True)

        # Button content: "A" label + colored underline strip
        btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self._color_lbl = Gtk.Label(label="A")
        self._color_lbl.add_css_class("heading")
        self._color_strip = Gtk.Box()
        self._color_strip.set_size_request(16, 3)
        self._color_strip.add_css_class("color-strip-indicator")
        btn_box.append(self._color_lbl)
        btn_box.append(self._color_strip)

        self._color_btn = Gtk.MenuButton(
            popover=self._color_popover,
            child=btn_box,
            tooltip_text="Color de texto",
            css_classes=["flat"],
        )
        self.append(self._color_btn)
        self._update_color_indicator()

    # ── Command helpers ───────────────────────────────────────────────────────

    def _cmd(self, command: str) -> None:
        if self._editor:
            self._editor.format(command)

    def _block(self, tag: str) -> None:
        if self._editor:
            self._editor.format("formatBlock", tag)

    # ── Font / size / color handlers ──────────────────────────────────────────

    def _on_font_changed(self, dd, _param) -> None:
        if not self._editor or not self._editor._doc:
            return
        idx = dd.get_selected()
        if 0 <= idx < len(self._FONTS):
            self._editor.apply_font_family(self._FONTS[idx])

    def _on_size_changed(self, spin) -> None:
        if not self._editor or not self._editor._doc:
            return
        self._editor.apply_font_size(int(spin.get_value()))

    def _apply_color(self, hex_color: str) -> None:
        self._current_color = hex_color
        self._update_color_indicator()
        if self._editor:
            self._editor.apply_text_color(hex_color)
        self._color_popover.popdown()

    def _update_color_indicator(self) -> None:
        self._color_provider.load_from_string(
            f".color-strip-indicator {{"
            f"  background-color: {self._current_color};"
            f"  border-radius: 2px;"
            f"}}"
        )

    # ── Widget builders ───────────────────────────────────────────────────────

    def _btn_icon(self, icon: str, tooltip: str, cb, css: str = "") -> None:
        btn = Gtk.Button(
            icon_name=icon,
            tooltip_text=tooltip,
            css_classes=["flat"],
        )
        if css:
            btn.add_css_class(css)
        btn.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
        btn.connect("clicked", lambda _: cb())
        self.append(btn)

    def _btn_label(self, label: str, tooltip: str, cb, css: str = "") -> None:
        btn = Gtk.Button(
            label=label,
            tooltip_text=tooltip,
            css_classes=["flat"],
        )
        if css:
            btn.add_css_class(css)
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
