from __future__ import annotations

from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..services.settings import Settings


class PreferencesWindow(Adw.PreferencesWindow):
    """
    Application preferences window.

    Usage::
        prefs = PreferencesWindow(settings, on_apply=window.apply_setting)
        prefs.present(parent)

    *on_apply(key, value)* is called immediately when a setting changes so the
    app can react without requiring a restart.
    """

    __gtype_name__ = "CodexPreferencesWindow"

    def __init__(
        self,
        settings: Settings,
        on_apply: Callable[[str, object], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(title="Preferencias de Codex", **kwargs)
        self._settings = settings
        self._on_apply = on_apply
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._build_appearance_page()
        self._build_editor_page()
        self._build_sidebar_page()
        self._build_export_page()
        self._build_storage_page()

    # ── Appearance ────────────────────────────────────────────────────────────

    def _build_appearance_page(self) -> None:
        page = Adw.PreferencesPage(
            title="Apariencia",
            icon_name="preferences-desktop-wallpaper-symbolic",
        )
        self.add(page)

        group = Adw.PreferencesGroup(title="Tema de color")
        page.add(group)

        self._theme_row = Adw.ComboRow(title="Tema")
        self._theme_row.set_model(Gtk.StringList.new(["Sistema", "Claro", "Oscuro"]))
        theme_idx = {"default": 0, "force-light": 1, "force-dark": 2}
        self._theme_row.set_selected(theme_idx.get(self._settings.get("theme"), 0))
        self._theme_row.connect("notify::selected", self._on_theme_changed)
        group.add(self._theme_row)

    # ── Editor ────────────────────────────────────────────────────────────────

    def _build_editor_page(self) -> None:
        page = Adw.PreferencesPage(
            title="Editor",
            icon_name="accessories-text-editor-symbolic",
        )
        self.add(page)

        font_group = Adw.PreferencesGroup(title="Tipografía")
        page.add(font_group)

        self._font_row = Adw.ComboRow(title="Fuente del editor")
        self._font_row.set_model(
            Gtk.StringList.new(
                ["Sistema (Cantarell)", "Monoespaciada (Fira Code)", "Serif (Georgia)"]
            )
        )
        font_idx = {"system": 0, "mono": 1, "serif": 2}
        self._font_row.set_selected(font_idx.get(self._settings.get("editor_font"), 0))
        self._font_row.connect("notify::selected", self._on_font_changed)
        font_group.add(self._font_row)

        self._size_row = Adw.SpinRow.new_with_range(10, 32, 1)
        self._size_row.set_title("Tamaño de fuente")
        self._size_row.set_subtitle("Puntos (10–32)")
        self._size_row.set_value(self._settings.get("editor_font_size", 15))
        self._size_row.connect("notify::value", self._on_font_size_changed)
        font_group.add(self._size_row)

        content_group = Adw.PreferencesGroup(title="Contenido del editor")
        page.add(content_group)

        self._backlinks_row = Adw.SwitchRow(
            title="Referencias entrantes",
            subtitle="Mostrar documentos que enlazan al documento actual",
        )
        self._backlinks_row.set_active(self._settings.get("show_backlinks", False))
        self._backlinks_row.connect("notify::active", self._on_backlinks_changed)
        content_group.add(self._backlinks_row)

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar_page(self) -> None:
        page = Adw.PreferencesPage(
            title="Panel lateral",
            icon_name="sidebar-show-symbolic",
        )
        self.add(page)

        group = Adw.PreferencesGroup(title="Dimensiones")
        page.add(group)

        self._sidebar_w_row = Adw.SpinRow.new_with_range(200, 400, 10)
        self._sidebar_w_row.set_title("Ancho del panel")
        self._sidebar_w_row.set_subtitle("Píxeles (200–400)")
        self._sidebar_w_row.set_value(self._settings.get("sidebar_width", 280))
        self._sidebar_w_row.connect("notify::value", self._on_sidebar_width_changed)
        group.add(self._sidebar_w_row)

    # ── Export ────────────────────────────────────────────────────────────────

    def _build_export_page(self) -> None:
        page = Adw.PreferencesPage(
            title="Exportación",
            icon_name="document-send-symbolic",
        )
        self.add(page)

        group = Adw.PreferencesGroup(title="Opciones predeterminadas")
        page.add(group)

        self._export_fmt_row = Adw.ComboRow(title="Formato predeterminado")
        self._export_fmt_row.set_model(
            Gtk.StringList.new(["Markdown (.md)", "Texto plano (.txt)", "PDF (.pdf)"])
        )
        fmt_idx = {"md": 0, "txt": 1, "pdf": 2}
        self._export_fmt_row.set_selected(
            fmt_idx.get(self._settings.get("export_format"), 0)
        )
        self._export_fmt_row.connect("notify::selected", self._on_export_format_changed)
        group.add(self._export_fmt_row)

    # ── Storage ───────────────────────────────────────────────────────────────

    def _build_storage_page(self) -> None:
        page = Adw.PreferencesPage(
            title="Almacenamiento",
            icon_name="drive-harddisk-symbolic",
        )
        self.add(page)

        group = Adw.PreferencesGroup(title="Biblioteca de documentos")
        page.add(group)

        lib_path = self._settings.get("library_path", str(Path.home() / "Codex"))
        self._library_row = Adw.ActionRow(
            title="Carpeta de la biblioteca",
            subtitle=lib_path,
        )
        choose_btn = Gtk.Button(
            icon_name="folder-open-symbolic",
            css_classes=["flat"],
            valign=Gtk.Align.CENTER,
            tooltip_text="Cambiar carpeta",
        )
        choose_btn.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Cambiar carpeta de la biblioteca"]
        )
        choose_btn.connect("clicked", self._on_choose_library)
        self._library_row.add_suffix(choose_btn)
        group.add(self._library_row)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_theme_changed(self, row: Adw.ComboRow, _param) -> None:
        themes = ["default", "force-light", "force-dark"]
        key = themes[row.get_selected()]
        self._settings.set("theme", key)
        self._settings.save()
        scheme = {
            "default": Adw.ColorScheme.DEFAULT,
            "force-light": Adw.ColorScheme.FORCE_LIGHT,
            "force-dark": Adw.ColorScheme.FORCE_DARK,
        }[key]
        Adw.StyleManager.get_default().set_color_scheme(scheme)
        if self._on_apply:
            self._on_apply("theme", key)

    def _on_font_changed(self, row: Adw.ComboRow, _param) -> None:
        fonts = ["system", "mono", "serif"]
        key = fonts[row.get_selected()]
        self._settings.set("editor_font", key)
        self._settings.save()
        if self._on_apply:
            self._on_apply("editor_font", key)

    def _on_font_size_changed(self, row: Adw.SpinRow, _param) -> None:
        size = int(row.get_value())
        self._settings.set("editor_font_size", size)
        self._settings.save()
        if self._on_apply:
            self._on_apply("editor_font_size", size)

    def _on_backlinks_changed(self, row: Adw.SwitchRow, _param) -> None:
        active = row.get_active()
        self._settings.set("show_backlinks", active)
        self._settings.save()
        if self._on_apply:
            self._on_apply("show_backlinks", active)

    def _on_sidebar_width_changed(self, row: Adw.SpinRow, _param) -> None:
        width = int(row.get_value())
        self._settings.set("sidebar_width", width)
        self._settings.save()
        if self._on_apply:
            self._on_apply("sidebar_width", width)

    def _on_export_format_changed(self, row: Adw.ComboRow, _param) -> None:
        fmts = ["md", "txt", "pdf"]
        key = fmts[row.get_selected()]
        self._settings.set("export_format", key)
        self._settings.save()
        if self._on_apply:
            self._on_apply("export_format", key)

    def _on_choose_library(self, _btn: Gtk.Button) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Seleccionar carpeta de la biblioteca")

        def on_result(_fd, result) -> None:
            try:
                gfile = _fd.select_folder_finish(result)
            except Exception:
                return
            path = gfile.get_path()
            self._settings.set("library_path", path)
            self._settings.save()
            self._library_row.set_subtitle(path)
            if self._on_apply:
                self._on_apply("library_path", path)

        dialog.select_folder(self, None, on_result)
