"""Rutas de la app en el perfil del usuario y soporte de modo portable.

Regla del plan (sección 6.2): la app funciona 100 % en el espacio del usuario,
sin permisos de administrador. Por eso los datos nunca se guardan en carpetas
protegidas del sistema:

- Modo instalado por usuario:
  - Datos y base de datos: ``%LOCALAPPDATA%\\ControlTiempos``
  - Copias de seguridad:   ``Documentos\\ControlTiempos\\Copias``
  - Reportes PDF:          ``Documentos\\ControlTiempos\\Reportes``
- Modo portable (cuando existe un archivo ``portable.flag`` junto al ejecutable
  o en la raíz del paquete portable, o cuando se define ``CONTROL_TIEMPOS_DATA_DIR``):
  - Todo se guarda dentro de ``<carpeta_portable>\\datos`` (BD, logs, copias y PDFs).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

NOMBRE_APP = "ControlTiempos"
NOMBRE_VISIBLE = "Control de Tiempos"
VERSION = "1.0.0"

#: Variable de entorno que permite cambiar la carpeta de datos.
ENV_DATA_DIR = "CONTROL_TIEMPOS_DATA_DIR"
#: Variable opcional para indicar la raíz de una ejecución portable.
ENV_PORTABLE_ROOT = "CONTROL_TIEMPOS_PORTABLE_ROOT"

ARCHIVO_BANDERA_PORTABLE = "portable.flag"
NOMBRE_BD = "control_tiempos.db"


def _raiz_ejecucion() -> Path:
    """Devuelve la carpeta base donde reside el ejecutable o la raíz del proyecto."""
    env_root = os.environ.get(ENV_PORTABLE_ROOT)
    if env_root:
        return Path(env_root)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def es_modo_portable() -> bool:
    """Indica si la aplicación corre en modo portable (con ``portable.flag``)."""
    return (_raiz_ejecucion() / ARCHIVO_BANDERA_PORTABLE).is_file()


def carpeta_datos() -> Path:
    """Devuelve (y crea si no existe) la carpeta de datos del usuario."""
    forzada = os.environ.get(ENV_DATA_DIR)
    if forzada:
        ruta = Path(forzada)
    elif es_modo_portable():
        ruta = _raiz_ejecucion() / "datos"
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
    Si se forzó la carpeta de datos (pruebas) o está en modo portable, las
    copias van dentro de la carpeta de datos para no ensuciar Documentos.
    """
    if os.environ.get(ENV_DATA_DIR) or es_modo_portable():
        ruta = carpeta_datos() / "Copias"
    else:
        ruta = Path.home() / "Documents" / NOMBRE_APP / "Copias"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def carpeta_reportes() -> Path:
    """Carpeta por defecto donde se exportan los reportes PDF."""
    if os.environ.get(ENV_DATA_DIR) or es_modo_portable():
        ruta = carpeta_datos() / "Reportes"
    else:
        ruta = Path.home() / "Documents" / NOMBRE_APP / "Reportes"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def carpeta_assets() -> Path:
    """Devuelve la carpeta de recursos gráficos (`src/assets`)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / "assets"
    return Path(__file__).resolve().parents[1] / "assets"


def ruta_logo_por_defecto() -> Path:
    """Devuelve la ruta del logo corporativo oficial de Gente Util."""
    png = carpeta_assets() / "logo_gente_util.png"
    if png.is_file():
        return png
    return carpeta_assets() / "logo_gente_util.svg"
