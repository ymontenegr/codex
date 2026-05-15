import os
import shutil
import sys
from pathlib import Path

# WebKit sandbox requires user namespaces (unavailable in VMs/containers).
os.environ.setdefault("WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS", "1")

_ICONS_SRC = Path(__file__).resolve().parent.parent / "data" / "icons" / "hicolor"


def _install_dev_icons() -> None:
    """Copy app icons to ~/.local/share/icons/hicolor/ for dev-mode runs."""
    dest_base = Path.home() / ".local" / "share" / "icons" / "hicolor"
    for size_dir in _ICONS_SRC.iterdir():
        if not size_dir.is_dir():
            continue
        for ctx_dir in size_dir.iterdir():
            if not ctx_dir.is_dir():
                continue
            dest = dest_base / size_dir.name / ctx_dir.name
            dest.mkdir(parents=True, exist_ok=True)
            for icon_file in ctx_dir.iterdir():
                shutil.copy2(icon_file, dest / icon_file.name)


_install_dev_icons()

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, Gio, Gtk
from .window import CodexWindow

APP_ID = "io.github.ymontenegr.Codex"


class CodexApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        # error #3 — acciones con atajos de teclado
        self._create_action("quit", self.quit, ["<primary>q"])
        self._create_action("about", self._on_about)
        self._create_action("new-document", self._on_new_document, ["<primary>n"])
        self._create_action("search", self._on_search, ["<primary>f"])
        # Shortcuts for these are registered at window level (win.*) to avoid conflicts
        self._create_action("graph-view", self._on_graph_view)
        self._create_action("focus-mode", self._on_focus_mode)
        self._create_action("export", self._on_export)
        self._create_action("save", self._on_save)  # Ctrl+S lo maneja win.save-document

    def do_activate(self):
        # error #8 — respetar la preferencia de color del sistema
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.DEFAULT)

        win = self.get_active_window()
        if not win:
            win = CodexWindow(application=self)
        win.set_icon_name("io.github.ymontenegr.Codex")
        win.present()

    # ── Handlers de acciones ──────────────────────────────────────────────────

    def _on_about(self, *_):
        dialog = Adw.AboutDialog(
            application_name="Codex",
            application_icon=APP_ID,
            developer_name="ymontenegr",
            version="0.1.0",
            website="https://github.com/ymontenegr/codex",
            issue_url="https://github.com/ymontenegr/codex/issues",
            developers=["ymontenegr"],
            copyright="© 2025 ymontenegr",
            license_type=Gtk.License.GPL_3_0,
        )
        dialog.present(self.get_active_window())

    def _on_new_document(self, *_):
        pass  # Sprint 2: delegar al editor activo

    def _on_search(self, *_):
        win = self.get_active_window()
        if win:
            win.toggle_search()

    def _on_graph_view(self, *_):
        win = self.get_active_window()
        if win:
            win.open_graph_view()

    def _on_focus_mode(self, *_):
        win = self.get_active_window()
        if win:
            win.toggle_focus_mode()

    def _on_export(self, *_):
        win = self.get_active_window()
        if win:
            win.show_export_dialog()

    def _on_save(self, *_):
        pass  # Sprint 2: guardar documento activo

    # ── Helper ────────────────────────────────────────────────────────────────

    def _create_action(self, name: str, callback, shortcuts: list[str] | None = None):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main():
    app = CodexApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
