"""Fixtures comunes: cada prueba usa una carpeta de datos temporal y aislada."""

from __future__ import annotations

import pytest

from config import rutas
from data.db import BaseDatos


@pytest.fixture
def carpeta_datos(tmp_path, monkeypatch):
    """Redirige la carpeta de datos de la app a una carpeta temporal."""
    monkeypatch.setenv(rutas.ENV_DATA_DIR, str(tmp_path))
    return tmp_path


@pytest.fixture
def bd(carpeta_datos):
    """Base de datos nueva, migrada y con los datos iniciales."""
    base = BaseDatos.abrir()
    yield base
    base.cerrar()


@pytest.fixture
def s(bd):
    """Sesión abierta sobre la BD de prueba (confirma al terminar la prueba)."""
    with bd.sesion() as sesion:
        yield sesion
