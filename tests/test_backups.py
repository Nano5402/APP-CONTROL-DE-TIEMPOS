"""Pruebas de copias de seguridad (automática, externa/USB, rotación y restauración)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from data.enums import TipoCopia
from data.repositorios.catalogos import RepoCategorias
from data.repositorios.configuracion import RepoConfiguracion
from services.backups import ServicioBackups


def test_crear_copia_automatica_externa_y_rotacion(s, tmp_path):
    RepoConfiguracion(s).guardar("copias.conservar", 2)
    srv = ServicioBackups(s)

    c1 = srv.crear_copia(TipoCopia.AUTOMATICA, momento=datetime(2026, 11, 9, 17, 0, 1))
    c2 = srv.crear_copia(TipoCopia.AUTOMATICA, momento=datetime(2026, 11, 10, 17, 0, 2))
    c3 = srv.crear_copia(TipoCopia.AUTOMATICA, momento=datetime(2026, 11, 11, 17, 0, 3))

    assert not Path(c1.ruta).exists()  # rotada por superar copias.conservar=2
    assert Path(c2.ruta).exists()
    assert Path(c3.ruta).exists()

    # Copia a carpeta externa / USB
    carpeta_usb = tmp_path / "mi_usb"
    c_usb = srv.copiar_a_carpeta_externa(carpeta_usb, momento=datetime(2026, 11, 11, 17, 5))
    assert Path(c_usb.ruta).parent == carpeta_usb
    assert Path(c_usb.ruta).exists()


def test_restaurar_desde_copia_y_rechazar_archivo_invalido(bd, tmp_path):
    with bd.sesion() as s:
        RepoCategorias(s).obtener_o_crear("AntesDeRestaurar")
        srv = ServicioBackups(s)
        copia = srv.crear_copia(TipoCopia.MANUAL, carpeta_destino=tmp_path)

    # Agregamos otra categoría después de la copia
    with bd.sesion() as s:
        RepoCategorias(s).obtener_o_crear("DespuesDeCopia")

    # Restauramos la copia anterior
    with bd.sesion() as s:
        srv = ServicioBackups(s)
        srv.restaurar_desde_archivo(copia.ruta)

    with bd.sesion() as s:
        nombres = [c.nombre for c in RepoCategorias(s).listar_activas()]
        assert "AntesDeRestaurar" in nombres
        assert "DespuesDeCopia" not in nombres

    # Un archivo que no es SQLite válido es rechazado sin dañar la BD
    archivo_falso = tmp_path / "corrupto.db"
    archivo_falso.write_text("no soy sqlite", encoding="utf-8")
    with bd.sesion() as s:
        srv = ServicioBackups(s)
        with pytest.raises(ValueError):
            srv.restaurar_desde_archivo(archivo_falso)
