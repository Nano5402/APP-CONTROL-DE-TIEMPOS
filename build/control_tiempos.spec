# -*- mode: python ; coding: utf-8 -*-
"""Especificación de PyInstaller para Control de Tiempos — Gente Util (v1.0.0).

Cumple la regla 6.2 / RNF-11 del plan:
- ``uac_admin=False`` y ``uac_uiaccess=False`` garantizan que el manifiesto de
  Windows use ``requestedExecutionLevel level="asInvoker"`` y nunca muestre el
  escudo de administrador ni solicite permisos elevados (UAC).
- Empaqueta las migraciones de Alembic y los activos visuales de ``src/assets``.
"""

from pathlib import Path

RAIZ = Path(SPECPATH).resolve().parent
SRC = RAIZ / "src"

datos_incluidos = [
    (str(RAIZ / "alembic.ini"), "."),
    (str(SRC / "data" / "migrations"), "data/migrations"),
    (str(SRC / "assets"), "assets"),
]

a = Analysis(
    [str(SRC / "main.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datos_incluidos,
    hiddenimports=[
        "alembic",
        "alembic.config",
        "alembic.runtime.migration",
        "alembic.script",
        "sqlalchemy.dialects.sqlite",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "numpy", "pandas"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ControlTiempos",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(SRC / "assets" / "icono_app.ico"),
    uac_admin=False,
    uac_uiaccess=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ControlTiempos",
)
