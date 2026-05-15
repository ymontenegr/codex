datadir = get_option('prefix') / get_option('datadir')

# CSS
install_data(
  'css/editor-light.css',
  'css/editor-dark.css',
  install_dir: datadir / meson.project_name() / 'css',
)

# JS
install_data(
  'js/editor.js',
  install_dir: datadir / meson.project_name() / 'js',
)

# Templates
install_data(
  'templates/empty.md',
  'templates/meeting.md',
  'templates/article.md',
  'templates/analysis.md',
  'templates/readme.md',
  install_dir: datadir / meson.project_name() / 'templates',
)

# Desktop entry
install_data(
  'io.github.ymontenegr.Codex.desktop',
  install_dir: datadir / 'applications',
)

# AppStream metadata
install_data(
  'io.github.ymontenegr.Codex.appdata.xml',
  install_dir: datadir / 'appdata',
)

# Icons
install_data(
  'icons/hicolor/scalable/apps/io.github.ymontenegr.Codex.svg',
  install_dir: datadir / 'icons' / 'hicolor' / 'scalable' / 'apps',
)
install_data(
  'icons/hicolor/48x48/apps/io.github.ymontenegr.Codex.png',
  install_dir: datadir / 'icons' / 'hicolor' / '48x48' / 'apps',
)
install_data(
  'icons/hicolor/128x128/apps/io.github.ymontenegr.Codex.png',
  install_dir: datadir / 'icons' / 'hicolor' / '128x128' / 'apps',
)
install_data(
  'icons/hicolor/256x256/apps/io.github.ymontenegr.Codex.png',
  install_dir: datadir / 'icons' / 'hicolor' / '256x256' / 'apps',
)
