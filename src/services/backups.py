"""Servicio de copias de seguridad (RF-06, RF-09, RNF-04).

Soporta los tres modos del plan:
1. **Automática diaria** al cerrar la jornada, en la carpeta local del usuario
   (con rotación de las últimas ``copias.conservar`` copias).
2. **Externa (USB o carpeta elegida)**: botón para copiar a una ruta seleccionada.
3. **Manual y restauración**: crear copia manual o restaurar desde un archivo
   ``.db`` existente validando antes que sea una base SQLite íntegra.

Usa la API nativa ``sqlite3.Connection.backup`` de Python para que la copia sea
consistente incluso con el archivo abierto en modo WAL.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import rutas
from data.enums import TipoCopia
from data.models import CopiaSeguridad
from data.repositorios.configuracion import RepoConfiguracion
from data.tiempo import ahora


class ServicioBackups:
    """Creación, rotación y restauración de copias de seguridad de la base SQLite."""

    def __init__(self, s: Session, ruta_bd_origen: Path | None = None) -> None:
        self.s = s
        self.config = RepoConfiguracion(s)
        self.ruta_origen = ruta_bd_origen or rutas.ruta_bd()

    def carpeta_automatica(self) -> Path:
        """Devuelve la carpeta configurada para copias automáticas o la de por defecto."""
        personalizada = self.config.obtener("copias.carpeta", "")
        if personalizada and personalizada.strip():
            carpeta = Path(personalizada.strip())
            carpeta.mkdir(parents=True, exist_ok=True)
            return carpeta
        return rutas.carpeta_copias()

    def crear_copia(
        self,
        tipo: TipoCopia | str = TipoCopia.AUTOMATICA,
        *,
        carpeta_destino: Path | str | None = None,
        momento: datetime | None = None,
    ) -> CopiaSeguridad:
        """Genera una copia consistente de la base de datos y la registra en ``copias_seguridad``."""
        instante = momento or ahora()
        tipo_enum = TipoCopia(tipo)

        if carpeta_destino is not None:
            destino_dir = Path(carpeta_destino)
        else:
            destino_dir = self.carpeta_automatica()
        destino_dir.mkdir(parents=True, exist_ok=True)

        marca = instante.strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"control_tiempos_{tipo_enum.value}_{marca}.db"
        ruta_destino = destino_dir / nombre_archivo

        # Confirmamos cambios en curso para que queden incluidos en el archivo respaldado
        self.s.commit()
        self._respaldar_sqlite(self.ruta_origen, ruta_destino)

        registro = CopiaSeguridad(
            fecha=instante,
            ruta=str(ruta_destino),
            tipo=tipo_enum.value,
        )
        self.s.add(registro)
        self.s.flush()

        if tipo_enum == TipoCopia.AUTOMATICA:
            self._rotar_automaticas(destino_dir)

        return registro

    def copiar_a_carpeta_externa(
        self, carpeta_usb_o_usuario: Path | str, *, momento: datetime | None = None
    ) -> CopiaSeguridad:
        """Copia la base de datos a una USB o carpeta elegida por el usuario (RF-09)."""
        return self.crear_copia(
            TipoCopia.EXTERNA,
            carpeta_destino=carpeta_usb_o_usuario,
            momento=momento,
        )

    def restaurar_desde_archivo(self, archivo_respaldo: Path | str) -> None:
        """Valida un archivo ``.db`` de respaldo y restaura su contenido sobre la BD actual."""
        ruta_src = Path(archivo_respaldo)
        if not ruta_src.is_file():
            raise FileNotFoundError(f"No existe el archivo de copia: {ruta_src}")

        self._validar_archivo_sqlite(ruta_src)
        self.s.close()
        self._respaldar_sqlite(ruta_src, self.ruta_origen)

    def listar_copias(self) -> list[CopiaSeguridad]:
        consulta = select(CopiaSeguridad).order_by(CopiaSeguridad.fecha.desc(), CopiaSeguridad.id.desc())
        return list(self.s.scalars(consulta))

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    @staticmethod
    def _respaldar_sqlite(origen: Path, destino: Path) -> None:
        with (
            closing(sqlite3.connect(str(origen))) as conn_orig,
            closing(sqlite3.connect(str(destino))) as conn_dest,
        ):
            conn_orig.backup(conn_dest)

    @staticmethod
    def _validar_archivo_sqlite(ruta: Path) -> None:
        try:
            with closing(sqlite3.connect(str(ruta))) as conn:
                res = conn.execute("PRAGMA integrity_check").fetchone()
                if not res or res[0] != "ok":
                    raise ValueError("El archivo de respaldo no pasó la verificación de integridad")
                tablas = {
                    fila[0]
                    for fila in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                if "jornadas" not in tablas or "actividades" not in tablas:
                    raise ValueError(
                        "El archivo seleccionado no parece ser una base de Control de Tiempos"
                    )
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"Archivo SQLite inválido: {exc}") from exc

    def _rotar_automaticas(self, carpeta: Path) -> None:
        conservar = max(1, self.config.obtener_int("copias.conservar", 30))
        archivos = sorted(
            carpeta.glob("control_tiempos_automatica_*.db"),
            key=lambda p: (p.name, p.stat().st_mtime),
            reverse=True,
        )
        for viejo in archivos[conservar:]:
            try:
                viejo.unlink()
            except OSError:
                pass
