"""Rutas de la app en el perfil del usuario.

Regla del plan (sección 6.2): la app funciona 100 % en el espacio del usuario,
sin permisos de administrador. Por eso los datos nunca se guardan junto al
ejecutable ni en carpetas del sistema:

- Datos y base de datos: ``%LOCALAPPDATA%\\ControlTiempos``
- Copias de seguridad:   ``Documentos\\ControlTiempos\\Copias``

Para pruebas o para la versión portable se puede forzar otra carpeta con la
variable de entorno ``CONTROL_TIEMPOS_DATA_DIR``.
"""

from __future__ import annotations

import os
from pathlib import Path

NOMBRE_APP = "ControlTiempos"
NOMBRE_VISIBLE = "Control de Tiempos"
VERSION = "0.8.0"

#: Variable de entorno que permite cambiar la carpeta de datos.
ENV_DATA_DIR = "CONTROL_TIEMPOS_DATA_DIR"

NOMBRE_BD = "control_tiempos.db"


def carpeta_datos() -> Path:
    """Devuelve (y crea si no existe) la carpeta de datos del usuario."""
    forzada = os.environ.get(ENV_DATA_DIR)
    if forzada:
        ruta = Path(forzada)
    else:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        ruta = Path(base) / NOMBRE_APP
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def ruta_bd() -> Path:
    """Ruta del archivo SQLite principal."""
    return carpeta_datos() / NOMBRE_BD


def carpeta_logs() -> Path:
    """Carpeta para los archivos de registro (logs)."""
    ruta = carpeta_datos() / "logs"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def carpeta_copias() -> Path:
    """Carpeta por defecto de las copias de seguridad automáticas.

    Se ubica en Documentos del usuario para que sea fácil de encontrar.
    Si se forzó la carpeta de datos (pruebas/portable), las copias van dentro
    de ella para no ensuciar Documentos.
    """
    if os.environ.get(ENV_DATA_DIR):
        ruta = carpeta_datos() / "Copias"
    else:
        ruta = Path.home() / "Documents" / NOMBRE_APP / "Copias"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def carpeta_reportes() -> Path:
    """Carpeta por defecto donde se exportan los reportes PDF."""
    if os.environ.get(ENV_DATA_DIR):
        ruta = carpeta_datos() / "Reportes"
    else:
        ruta = Path.home() / "Documents" / NOMBRE_APP / "Reportes"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta
