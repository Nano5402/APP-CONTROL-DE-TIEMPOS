"""Pruebas de la base de datos: creación, migraciones y ajustes de SQLite."""

from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import func, inspect, select, text

from config import rutas
from data.db import BaseDatos
from data.models import Base, Configuracion, Solicitante


def test_se_crean_todas_las_tablas(bd):
    tablas = set(inspect(bd.motor).get_table_names())
    esperadas = set(Base.metadata.tables)
    assert esperadas <= tablas
    assert "alembic_version" in tablas
    assert rutas.ruta_bd().exists()


def test_migraciones_coinciden_con_modelos(bd):
    """Si falla, se cambió models.py sin crear la migración de Alembic."""
    with bd.motor.connect() as conexion:
        contexto = MigrationContext.configure(conexion, opts={"compare_type": True})
        diferencias = compare_metadata(contexto, Base.metadata)
    assert diferencias == []


def test_pragmas_sqlite(bd):
    with bd.motor.connect() as c:
        assert c.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert c.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_reabrir_no_duplica_datos(carpeta_datos):
    primera = BaseDatos.abrir()
    with primera.sesion() as s:
        n_solicitantes = s.scalar(select(func.count()).select_from(Solicitante))
        n_config = s.scalar(select(func.count()).select_from(Configuracion))
    primera.cerrar()

    segunda = BaseDatos.abrir()
    with segunda.sesion() as s:
        assert s.scalar(select(func.count()).select_from(Solicitante)) == n_solicitantes
        assert s.scalar(select(func.count()).select_from(Configuracion)) == n_config
    segunda.cerrar()


def test_sesion_deshace_si_hay_error(bd):
    try:
        with bd.sesion() as s:
            s.add(Configuracion(clave="prueba.rollback", valor="x"))
            s.flush()
            raise RuntimeError("falla simulada")
    except RuntimeError:
        pass
    with bd.sesion() as s:
        assert s.get(Configuracion, "prueba.rollback") is None
