"""Conexión a SQLite, sesiones y arranque de la base de datos.

Uso típico::

    bd = BaseDatos.abrir()          # crea/migra la BD y carga datos iniciales
    with bd.sesion() as s:          # commit automático al salir, rollback si hay error
        s.add(...)

Confiabilidad (RNF-04): se activa el modo WAL de SQLite y cada operación se
confirma en su propia transacción corta, de modo que un cierre inesperado de la
app o un apagado del PC no corrompe ni pierde lo ya guardado.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from config import rutas

log = logging.getLogger(__name__)

CARPETA_MIGRACIONES = Path(__file__).resolve().parent / "migrations"


def _configurar_conexion(dbapi_conn, _registro) -> None:
    """Ajustes de SQLite que se aplican a cada conexión nueva."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def crear_motor(ruta: Path | str | None = None) -> Engine:
    """Crea el motor de SQLAlchemy para el archivo indicado (o el de por defecto)."""
    ruta_final = Path(ruta) if ruta else rutas.ruta_bd()
    motor = create_engine(f"sqlite:///{ruta_final.as_posix()}")
    event.listen(motor, "connect", _configurar_conexion)
    return motor


def migrar(motor: Engine) -> None:
    """Aplica todas las migraciones de Alembic pendientes (``upgrade head``)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    # Se escapa "%" porque Alembic usa interpolación de configparser.
    # No se define sqlalchemy.url: env.py recibe la conexión ya abierta.
    cfg.set_main_option("script_location", str(CARPETA_MIGRACIONES).replace("%", "%%"))
    with motor.connect() as conexion:
        # En SQLite, las migraciones "batch" recrean tablas: se desactivan las
        # llaves foráneas mientras tanto (debe hacerse fuera de una transacción).
        conexion.exec_driver_sql("PRAGMA foreign_keys=OFF")
        cfg.attributes["connection"] = conexion
        command.upgrade(cfg, "head")
        conexion.commit()
        conexion.exec_driver_sql("PRAGMA foreign_keys=ON")


class BaseDatos:
    """Punto de acceso único a la base de datos de la app."""

    def __init__(self, motor: Engine) -> None:
        self.motor = motor
        self._fabrica = sessionmaker(bind=motor, expire_on_commit=False)

    @classmethod
    def abrir(cls, ruta: Path | str | None = None, *, cargar_datos_iniciales: bool = True) -> BaseDatos:
        """Abre la BD: la crea si no existe, la migra y carga los datos iniciales."""
        from data.semilla import sembrar_datos_iniciales

        motor = crear_motor(ruta)
        migrar(motor)
        bd = cls(motor)
        if cargar_datos_iniciales:
            with bd.sesion() as s:
                sembrar_datos_iniciales(s)
        log.info("Base de datos lista en %s", motor.url.database)
        return bd

    @contextmanager
    def sesion(self) -> Iterator[Session]:
        """Sesión transaccional: confirma al salir o deshace si ocurre un error."""
        s = self._fabrica()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def cerrar(self) -> None:
        """Libera las conexiones (llamar al salir de la app)."""
        self.motor.dispose()
