# Codex

Editor de documentos Markdown organizado en jerarquía **Libro → Capítulo → Documento**,
con referencias cruzadas estilo `[[nombre-doc]]`, vista de grafo interactiva,
búsqueda full-text y modo escritura enfocada.

## Funcionalidades

- Jerarquía de tres niveles con CRUD completo (crear, renombrar, eliminar)
- Editor WYSIWYG con auto-guardado cada 30 segundos y barra de herramientas
- Referencias cruzadas `[[nombre-doc]]` navegables + botón en toolbar + panel de backlinks
- Búsqueda full-text en todos los documentos (SQLite FTS5, Ctrl+F)
- Favoritos y documentos recientes en el panel lateral (recientes fijos en la mitad inferior)
- Etiquetas con agrupación en el sidebar
- Exportación a Markdown, texto plano y PDF (via pandoc + LaTeX)
- Plantillas de documento (reunión, artículo, análisis, README)
- Modo escritura enfocada sin distracciones (Ctrl+Shift+F / Esc)
- Vista de grafo de conexiones entre documentos (Ctrl+G)
- Contador de palabras y tiempo de lectura estimado
- Tema claro/oscuro automático según preferencia del sistema
- Pantalla de splash al iniciar con ícono, nombre y desarrollador
- Menú de aplicación con diálogo "Acerca de"

## Requisitos del sistema

- Ubuntu 24.04 LTS (o compatible)
- Python 3.12+
- GTK 4.14+ / Libadwaita 1.5+
- WebKit 6.0 (`gir1.2-webkit-6.0`)
- pandoc + texlive-xetex (para exportación a PDF)

```bash
sudo apt install -y \
  python3 python3-venv \
  libgtk-4-1 libadwaita-1-0 \
  python3-gi python3-gi-cairo \
  gir1.2-gtk-4.0 gir1.2-adw-1 \
  libwebkitgtk-6.0-4 gir1.2-webkit-6.0 \
  pandoc texlive-xetex
```

## Instalación para desarrollo

```bash
git clone https://github.com/ymontenegr/codex.git
cd codex

# El flag --system-site-packages es necesario para que el venv
# acceda a python3-gi (GTK/WebKit), que se instala via apt, no pip
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt
```

### Ejecutar

```bash
./run.sh
```

O manualmente:

```bash
source .venv/bin/activate
python3 -m src.main
```

> **Nota para VMs:** Si aparece el error `bwrap: setting up uid map: Permission denied`,
> el sandbox de WebKit no está disponible. El script `run.sh` ya incluye el workaround
> necesario (`WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1`).

## Instalación con Meson

```bash
meson setup builddir --prefix=/usr
ninja -C builddir
sudo ninja -C builddir install
```

## Instalación como Flatpak

```bash
sudo apt install flatpak flatpak-builder
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

flatpak-builder --user --install --force-clean \
  build-dir io.github.ymontenegr.Codex.json

flatpak run io.github.ymontenegr.Codex
```

## Tests

```bash
pytest tests/ -v
pytest tests/ --cov=src --cov-report=term-missing
```

## Atajos de teclado

| Atajo | Acción |
|---|---|
| Ctrl+N | Nuevo documento |
| Ctrl+S | Guardar |
| Ctrl+F | Búsqueda |
| Ctrl+G | Vista de grafo |
| Ctrl+Shift+F | Modo escritura enfocada |
| Ctrl+E | Exportar |
| Ctrl+B | Negrita |
| Ctrl+I | Cursiva |
| Ctrl+Shift+C | Código inline |
| `[[` o botón `[[…]]` | Insertar referencia cruzada |
| Esc | Salir del modo enfocado |
| F11 | Pantalla completa |
| Ctrl+Q | Salir |

## Estructura del proyecto

```
codex/
├── src/
│   ├── main.py              # Adw.Application
│   ├── window.py            # Ventana principal
│   ├── models/              # Book, Chapter, Document, Tag
│   ├── services/            # Database, Storage, Indexer, Exporter, GraphService, Settings
│   ├── widgets/             # Editor, Sidebar, Toolbar, BacklinksPanel, GraphView, Splash…
│   └── utils/               # Markdown parser
├── data/
│   ├── js/editor.js         # Lógica del editor WYSIWYG
│   ├── css/                 # Estilos editor claro/oscuro
│   ├── templates/           # Plantillas de documento
│   └── icons/               # Ícono SVG y PNGs (hicolor)
├── tests/                   # Suite pytest
├── run.sh                   # Script de desarrollo
└── io.github.ymontenegr.Codex.json  # Flatpak manifest
```

## Historial de versiones

### v1.1.0
- Pantalla de splash al iniciar (ícono, nombre de la app, desarrollador)
- Menú de aplicación con opción "Acerca de Codex" (versión, tecnología, desarrollador)
- Documentos recientes fijos en la mitad inferior del sidebar, separados del árbol
- Botón `[[…]]` en la toolbar para insertar referencias a documentos internos
- Nombre del desarrollador: Yovani Montenegro

### v1.0.0
- Primera versión funcional con jerarquía Libro → Capítulo → Documento
- Editor WYSIWYG (WebKit), búsqueda full-text, exportación PDF, vista de grafo
- Correcciones de compatibilidad: Yaru icon theme, WebKit sandbox, sidebar layout

## Licencia

GPL-3.0-or-later © 2026 Yovani Montenegro
