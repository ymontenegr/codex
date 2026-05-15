from __future__ import annotations

import json
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "codex"
_SETTINGS_FILE = _CONFIG_DIR / "settings.json"

_DEFAULTS: dict = {
    "theme": "default",  # "default" | "force-light" | "force-dark"
    "editor_font": "system",  # "system"  | "mono"        | "serif"
    "editor_font_size": 15,
    "sidebar_width": 280,
    "export_format": "md",  # "md" | "txt" | "pdf"
    "export_dir": "",
    "library_path": str(Path.home() / "Codex"),
}


class Settings:
    """
    Persistent application settings stored as JSON in ~/.config/codex/.

    Usage::
        s = Settings()
        s.get("theme")           # "default"
        s.set("theme", "force-dark")
        s.save()
    """

    def __init__(self) -> None:
        self._data: dict = dict(_DEFAULTS)
        self.load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load settings from disk, silently ignoring any parse errors."""
        try:
            if _SETTINGS_FILE.exists():
                raw = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
                self._data.update({k: v for k, v in raw.items() if k in _DEFAULTS})
        except Exception:
            pass

    def save(self) -> None:
        """Persist current settings to disk."""
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            _SETTINGS_FILE.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ── Access ────────────────────────────────────────────────────────────────

    def get(self, key: str, default=None):
        """Return the value for *key*, falling back to *default* then the built-in default."""
        if default is None:
            default = _DEFAULTS.get(key)
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        """Update *key* in memory (call :meth:`save` to persist)."""
        if key in _DEFAULTS:
            self._data[key] = value

    def reset(self) -> None:
        """Reset all settings to built-in defaults (in memory only)."""
        self._data = dict(_DEFAULTS)
