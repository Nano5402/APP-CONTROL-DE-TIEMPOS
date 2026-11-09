"""Generador del paquete portable (.zip) sin permisos de administrador (Fase 9).

Construye ``dist/ControlTiempos-Portable-v1.0.0.zip`` listo para descomprimir
en cualquier carpeta del usuario (Documentos, Escritorio o memoria USB).
Incluye el archivo ``portable.flag`` para que la aplicación guarde la base de
datos, los logs, las copias de seguridad y los reportes PDF dentro de la
subcarpeta ``datos/`` junto a la app.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from config import rutas

RAIZ = Path(__file__).resolve().parent.parent


def construir_paquete_portable(carpeta_destino: Path | None = None) -> Path:
    """Crea la estructura portable y la comprime en un archivo ``.zip``."""
    dist_base = carpeta_destino or (RAIZ / "dist")
    dist_base.mkdir(parents=True, exist_ok=True)

    nombre_paquete = f"{rutas.NOMBRE_APP}-Portable-v{rutas.VERSION}"
    carpeta_staging = dist_base / nombre_paquete
    if carpeta_staging.exists():
        shutil.rmtree(carpeta_staging)
    carpeta_staging.mkdir(parents=True, exist_ok=True)

    # 1. Bandera de modo portable (activa el almacenamiento local en ./datos)
    (carpeta_staging / rutas.ARCHIVO_BANDERA_PORTABLE).write_text(
        "Modo portable activo: todos los datos se guardan en ./datos\n",
        encoding="utf-8",
    )
    (carpeta_staging / "datos").mkdir(exist_ok=True)

    # 2. Si ya se compiló el binario con PyInstaller en dist/ControlTiempos, lo copia;
    #    además incluye el código fuente limpio para poder correr también con Python local.
    binario_pyinstaller = RAIZ / "dist" / rutas.NOMBRE_APP
    if binario_pyinstaller.is_dir() and (binario_pyinstaller / "ControlTiempos.exe").is_file():
        shutil.copytree(binario_pyinstaller, carpeta_staging, dirs_exist_ok=True)
    else:
        shutil.copytree(
            RAIZ / "src",
            carpeta_staging / "src",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            dirs_exist_ok=True,
        )
        shutil.copy2(RAIZ / "alembic.ini", carpeta_staging / "alembic.ini")
        shutil.copy2(RAIZ / "requirements.txt", carpeta_staging / "requirements.txt")

    # 3. Lanzador por lotes (.bat) sin permisos de administrador
    bat = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "cd /d \"%~dp0\"\r\n"
        "set CONTROL_TIEMPOS_PORTABLE_ROOT=%~dp0\r\n"
        "if exist \"ControlTiempos.exe\" (\r\n"
        "    start \"\" \"ControlTiempos.exe\" %*\r\n"
        ") else if exist \".venv\\Scripts\\pythonw.exe\" (\r\n"
        "    start \"\" \".venv\\Scripts\\pythonw.exe\" src\\main.py %*\r\n"
        ") else (\r\n"
        "    python src\\main.py %*\r\n"
        ")\r\n"
    )
    (carpeta_staging / "Iniciar_ControlTiempos.bat").write_text(bat, encoding="utf-8")

    # 4. Manual de usuario e instrucciones rápidas
    manual_origen = RAIZ / "docs" / "manual_usuario.md"
    if manual_origen.is_file():
        shutil.copy2(manual_origen, carpeta_staging / "MANUAL_USUARIO.md")

    leeme = (
        f"{rutas.NOMBRE_VISIBLE} — Gente Util (v{rutas.VERSION}) — Edición Portable\n"
        "==================================================================\n\n"
        "1. No requiere instalación ni permisos de administrador.\n"
        "2. Descomprima esta carpeta en Documentos, Escritorio o una USB.\n"
        "3. Ejecute 'ControlTiempos.exe' o 'Iniciar_ControlTiempos.bat'.\n"
        "4. Todos sus datos, copias de seguridad y reportes PDF se guardarán\n"
        "   automáticamente dentro de la subcarpeta 'datos\\'.\n"
    )
    (carpeta_staging / "LEEME_PORTABLE.txt").write_text(leeme, encoding="utf-8")

    # 5. Comprimir en .zip
    ruta_zip = dist_base / f"{nombre_paquete}.zip"
    with zipfile.ZipFile(ruta_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for archivo in carpeta_staging.rglob("*"):
            if archivo.is_file():
                zf.write(archivo, archivo.relative_to(dist_base))

    return ruta_zip


if __name__ == "__main__":
    salida = construir_paquete_portable()
    print(f"Paquete portable generado en: {salida}")
