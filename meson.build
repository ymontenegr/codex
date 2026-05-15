project('codex',
  version: '0.1.0',
  meson_version: '>= 1.3.0',
)

python = import('python').find_installation('python3', required: true)

gnome = import('gnome')
i18n = import('i18n')

app_id = 'io.github.ymontenegr.Codex'
pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()

subdir('data')
subdir('po')

install_subdir('src',
  install_dir: pkgdatadir,
  strip_directory: false,
)

configure_file(
  input: 'src/main.py',
  output: meson.project_name(),
  install: true,
  install_dir: get_option('prefix') / get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

gnome.post_install(
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)
