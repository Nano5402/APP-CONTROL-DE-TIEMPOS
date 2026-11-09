"""Pruebas de rutas: los datos siempre quedan en el perfil del usuario o en la carpeta portable."""

from __future__ import annotations

from pathlib import Path

from config import rutas


def test_carpeta_forzada_por_variable(carpeta_datos):
    assert rutas.carpeta_datos() == carpeta_datos
    assert rutas.ruta_bd() == carpeta_datos / rutas.NOMBRE_BD
    assert rutas.carpeta_copias().is_relative_to(carpeta_datos)


def test_carpeta_por_defecto_en_localappdata(tmp_path, monkeypatch):
    monkeypatch.delenv(rutas.ENV_DATA_DIR, raising=False)
    monkeypatch.delenv(rutas.ENV_PORTABLE_ROOT, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert not rutas.es_modo_portable()
    assert rutas.carpeta_datos() == Path(tmp_path) / "ControlTiempos"
    assert rutas.carpeta_datos().is_dir()


def test_modo_portable_con_archivo_bandera(tmp_path, monkeypatch):
    monkeypatch.delenv(rutas.ENV_DATA_DIR, raising=False)
    monkeypatch.setenv(rutas.ENV_PORTABLE_ROOT, str(tmp_path))
    (tmp_path / rutas.ARCHIVO_BANDERA_PORTABLE).write_text("portable\n", encoding="utf-8")

    assert rutas.es_modo_portable() is True
    assert rutas.carpeta_datos() == tmp_path / "datos"
    assert rutas.carpeta_copias() == tmp_path / "datos" / "Copias"
    assert rutas.carpeta_reportes() == tmp_path / "datos" / "Reportes"
    assert rutas.ruta_logo_por_defecto().is_file()
