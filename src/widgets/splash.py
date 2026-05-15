from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk


class SplashScreen(Gtk.Window):
    """Startup splash: shows icon, name and developer for 2 seconds."""

    def __init__(self, application):
        super().__init__(application=application)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(340, 260)

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            margin_top=48,
            margin_bottom=48,
            margin_start=48,
            margin_end=48,
        )

        icon = Gtk.Image.new_from_icon_name("io.github.ymontenegr.Codex")
        icon.set_pixel_size(96)
        box.append(icon)

        box.append(
            Gtk.Label(
                label="Codex",
                css_classes=["title-1"],
                margin_top=8,
            )
        )
        box.append(
            Gtk.Label(
                label="Yovani Montenegro",
                css_classes=["dim-label"],
            )
        )
        box.append(
            Gtk.Label(
                label="v1.1.0",
                css_classes=["caption", "dim-label"],
            )
        )

        self.set_child(box)

    def show_then(self, delay_ms: int, callback) -> None:
        """Present the splash and call *callback* after *delay_ms* milliseconds."""
        self.present()
        GLib.timeout_add(delay_ms, callback)
