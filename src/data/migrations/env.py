"""Entorno de Alembic.

Dos formas de ejecución:
1. Desde la app (``data.db.migrar``): recibe una conexión ya abierta en
   ``config.attributes["connection"]``.
2. Desde la línea de comandos (``alembic ...``): usa la URL del config o, si no
   hay, una BD de desarrollo en ``./dev_data`` (nunca la BD real del usuario).
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine

from data.models import Base

config = context.config

if config.config_file_name is not None and config.attributes.get("connection") is None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url_cli() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    carpeta = Path(os.environ.get("CONTROL_TIEMPOS_DATA_DIR", "dev_data"))
    carpeta.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(carpeta / 'control_tiempos.db').as_posix()}"


def _configurar(conexion) -> None:
    context.configure(
        connection=conexion,
        target_metadata=target_metadata,
        render_as_batch=True,  # necesario para ALTER TABLE en SQLite
        compare_type=True,
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_url_cli(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    conexion = config.attributes.get("connection")
    if conexion is not None:
        _configurar(conexion)
        with context.begin_transaction():
            context.run_migrations()
        return

    motor = create_engine(_url_cli())
    with motor.connect() as conexion:
        _configurar(conexion)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
