"""Pruebas de rutas: los datos siempre quedan en el perfil del usuario."""

from __future__ import annotations

from pathlib import Path

from config import rutas


def test_carpeta_forzada_por_variable(carpeta_datos):
    assert rutas.carpeta_datos() == carpeta_datos
    assert rutas.ruta_bd() == carpeta_datos / rutas.NOMBRE_BD
    assert rutas.carpeta_copias().is_relative_to(carpeta_datos)


def test_carpeta_por_defecto_en_localappdata(tmp_path, monkeypatch):
    monkeypatch.delenv(rutas.ENV_DATA_DIR, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert rutas.carpeta_datos() == Path(tmp_path) / "ControlTiempos"
    assert rutas.carpeta_datos().is_dir()
