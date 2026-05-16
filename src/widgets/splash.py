from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk


class SplashScreen(Adw.Window):
    """Startup splash: shows icon, name and developer.

    Must be presented as a transient modal over the main window so the
    compositor centres it on screen (GTK4/Wayland has no direct positioning).
    """

    def __init__(self, application, transient_for: Gtk.Window):
        super().__init__(application=application)
        self.set_transient_for(transient_for)
        self.set_modal(True)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(340, 280)

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
                label="v1.5.0",
                css_classes=["caption", "dim-label"],
            )
        )

        self.set_content(box)
