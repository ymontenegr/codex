#!/usr/bin/env bash
# run.sh — Lanzador de desarrollo para Codex
# Aplica workaround para bug GTK 4.14 + Ubuntu 24.04:
#   GTK intenta leer 'antialiasing' de org.gnome.settings-daemon.plugins.xsettings
#   pero esa clave no existe en esta versión de gnome-settings-daemon.

set -e
cd "$(dirname "$0")"

export PYTHONPATH="$(pwd)"
export G_MESSAGES_DEBUG=none          # suprime warnings no fatales
export GSETTINGS_BACKEND=keyfile      # evita el schema corrupto sin usar memoria pura

exec python3 -m src.main "$@"
