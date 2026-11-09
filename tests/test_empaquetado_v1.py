"""Pruebas de la configuración de empaquetado sin administrador y versión portable (Fase 9)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from build.empaquetar_portable import construir_paquete_portable
from config import rutas

RAIZ = Path(__file__).resolve().parent.parent


def test_scripts_instalacion_sin_administrador() -> None:
    """Verifica que PyInstaller e Inno Setup estén configurados sin UAC / por usuario."""
    spec = (RAIZ / "build" / "control_tiempos.spec").read_text(encoding="utf-8")
    assert "uac_admin=False" in spec
    assert "uac_uiaccess=False" in spec

    iss = (RAIZ / "build" / "instalador_usuario.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss
    assert "{localappdata}\\Programs\\" in iss
    assert "Root: HKCU" in iss
    assert "Root: HKLM" not in iss


def test_construir_paquete_portable_zip(tmp_path: Path) -> None:
    """Genera el archivo .zip portable y comprueba su estructura interna."""
    ruta_zip = construir_paquete_portable(tmp_path)
    assert ruta_zip.is_file()
    assert ruta_zip.stat().st_size > 1000

    with zipfile.ZipFile(ruta_zip, "r") as zf:
        nombres = zf.namelist()
    prefijo = f"{rutas.NOMBRE_APP}-Portable-v{rutas.VERSION}/"
    assert f"{prefijo}{rutas.ARCHIVO_BANDERA_PORTABLE}" in nombres
    assert f"{prefijo}Iniciar_ControlTiempos.bat" in nombres
    assert f"{prefijo}LEEME_PORTABLE.txt" in nombres
