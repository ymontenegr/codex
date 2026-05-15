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
- Vista de grafo de conexiones entre documentos (Ctrl+G) con zoom, centrado y exportación a PDF
- Buscador en el sidebar para filtrar libros, capítulos y documentos con resaltado de coincidencias
- Buscador dentro del documento activo en la barra de herramientas del editor (WebKit FindController)
- Eliminación de libros, capítulos y documentos con validación de contenido y confirmación
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

### v1.4.0
**Nuevas funcionalidades**
- Ícono de la aplicación visible en la cabecera del sidebar, al lado del título "Biblioteca"
- Título de la ventana principal muestra nombre de la app y versión (`Adw.WindowTitle`)
- Buscador en el sidebar (lupa junto al "+") filtra libros, capítulos y documentos; resalta coincidencias en negrita
- Buscador de texto dentro del documento activo en la barra de herramientas; navega con Intro/Shift+Intro
- Eliminación de libros y capítulos valida que estén vacíos antes de mostrar confirmación; muestra mensaje de error si contienen elementos
- Sección "Recientes" limitada a los 5 últimos documentos abiertos

### v1.2.0
**Nuevas funcionalidades**
- Vista de grafo: auto-centrado al abrir (el grafo se ajusta al tamaño del lienzo automáticamente)
- Vista de grafo: botones de zoom in y zoom out en la barra de herramientas
- Vista de grafo: botón para centrar/ajustar el grafo en cualquier momento
- Vista de grafo: exportación del grafo a PDF tamaño carta (8.5 × 11 in) desde la barra de herramientas

**Corrección de errores**
- Splash screen aparecía en la esquina superior izquierda en Wayland → centrada usando `transient_for` + `modal`
- La ventana principal no se abría maximizada al iniciar → se agrega `win.maximize()` al activar la aplicación
- Creación y renombrado de libros, capítulos y documentos requería dos clics en el botón → reemplazado `Adw.EntryRow` con `Gtk.Entry(activates_default=True)`
- Inserción de referencias cruzadas desde el botón de toolbar no funcionaba → se guarda la posición del cursor vía JavaScript antes de abrir el diálogo

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
