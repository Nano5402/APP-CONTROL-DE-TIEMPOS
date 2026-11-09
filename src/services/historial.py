"""Servicio de consulta y filtrado del historial (RF-07).

Permite:
- Consultar por día, semana actual/elegida, mes o rango de fechas arbitrario.
- Filtrar actividades por categoría, estado, solicitante y tipo (planeada / extra / no_planeada).
- Obtener el detalle completo de una actividad: sesiones de tiempo, pausas,
  revisiones vinculadas y bitácora de ediciones (``ediciones_log``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.enums import EstadoActividad
from data.models import Actividad, EdicionLog, Jornada, Pausa, SesionTiempo
from services.actividades import DesgloseTiempoActividad, ServicioActividades
from services.productividad import ResultadoProductividad, ServicioProductividad


@dataclass(frozen=True)
class FiltrosHistorial:
    fecha_desde: date
    fecha_hasta: date
    categoria_id: int | None = None
    estado: str | None = None
    solicitante_id: int | None = None
    tipo: str | None = None


@dataclass(frozen=True)
class DetalleActividadHistorial:
    actividad: Actividad
    desglose: DesgloseTiempoActividad
    sesiones: list[SesionTiempo]
    pausas: list[Pausa]
    revisiones: list[Actividad]
    ediciones: list[EdicionLog]


def rango_semana(fecha_ref: date) -> tuple[date, date]:
    """Devuelve ``(lunes, domingo)`` de la semana de ``fecha_ref``."""
    lunes = fecha_ref - timedelta(days=fecha_ref.weekday())
    return lunes, lunes + timedelta(days=6)


def rango_mes(fecha_ref: date) -> tuple[date, date]:
    """Devuelve ``(primer_dia, ultimo_dia)`` del mes de ``fecha_ref``."""
    primero = fecha_ref.replace(day=1)
    if primero.month == 12:
        sig = primero.replace(year=primero.year + 1, month=1, day=1)
    else:
        sig = primero.replace(month=primero.month + 1, day=1)
    return primero, sig - timedelta(days=1)


class ServicioHistorial:
    """Consultas de jornadas y actividades históricas con filtros y trazabilidad."""

    def __init__(self, s: Session) -> None:
        self.s = s
        self.srv_act = ServicioActividades(s)
        self.srv_prod = ServicioProductividad(s)

    def listar_jornadas(
        self, fecha_desde: date, fecha_hasta: date
    ) -> list[tuple[Jornada, ResultadoProductividad]]:
        """Devuelve las jornadas en el rango junto con su cálculo de productividad."""
        consulta = (
            select(Jornada)
            .where(Jornada.fecha >= fecha_desde, Jornada.fecha <= fecha_hasta)
            .order_by(Jornada.fecha.desc())
        )
        jornadas = list(self.s.scalars(consulta))
        return [(j, self.srv_prod.calcular_jornada(j)) for j in jornadas]

    def buscar_actividades(self, filtros: FiltrosHistorial) -> list[Actividad]:
        """Filtra actividades en el rango de fechas según categoría, estado, solicitante y tipo."""
        consulta = (
            select(Actividad)
            .join(Jornada, Actividad.jornada_id == Jornada.id)
            .where(
                Jornada.fecha >= filtros.fecha_desde,
                Jornada.fecha <= filtros.fecha_hasta,
                Actividad.estado != EstadoActividad.ELIMINADA.value,
            )
            .order_by(Jornada.fecha.desc(), Actividad.id.desc())
        )
        if filtros.categoria_id is not None:
            consulta = consulta.where(Actividad.categoria_id == filtros.categoria_id)
        if filtros.estado:
            consulta = consulta.where(Actividad.estado == filtros.estado)
        if filtros.solicitante_id is not None:
            consulta = consulta.where(Actividad.solicitante_id == filtros.solicitante_id)
        if filtros.tipo:
            consulta = consulta.where(Actividad.tipo == filtros.tipo)

        return list(self.s.scalars(consulta))

    def detalle_actividad(self, actividad_id: int) -> DetalleActividadHistorial | None:
        """Recupera todo el historial y trazabilidad de una actividad."""
        act = self.s.get(Actividad, actividad_id)
        if act is None:
            return None

        desglose = self.srv_act.desglose_tiempos(act)
        sesiones = list(
            self.s.scalars(
                select(SesionTiempo)
                .where(SesionTiempo.actividad_id == act.id)
                .order_by(SesionTiempo.inicio)
            )
        )
        pausas = list(
            self.s.scalars(
                select(Pausa)
                .where(Pausa.actividad_id == act.id)
                .order_by(Pausa.inicio)
            )
        )
        raiz_id = act.actividad_padre_id or act.id
        revisiones = list(
            self.s.scalars(
                select(Actividad)
                .where(
                    Actividad.actividad_padre_id == raiz_id,
                    Actividad.estado != EstadoActividad.ELIMINADA.value,
                )
                .order_by(Actividad.id)
            )
        )

        ids_sesiones = [s.id for s in sesiones]
        ediciones_act = list(
            self.s.scalars(
                select(EdicionLog)
                .where(EdicionLog.tabla == "actividades", EdicionLog.registro_id == act.id)
                .order_by(EdicionLog.momento.desc())
            )
        )
        ediciones_ses: list[EdicionLog] = []
        if ids_sesiones:
            ediciones_ses = list(
                self.s.scalars(
                    select(EdicionLog)
                    .where(
                        EdicionLog.tabla == "sesiones_tiempo",
                        EdicionLog.registro_id.in_(ids_sesiones),
                    )
                    .order_by(EdicionLog.momento.desc())
                )
            )
        ediciones = sorted(
            ediciones_act + ediciones_ses, key=lambda e: e.momento, reverse=True
        )

        return DetalleActividadHistorial(
            actividad=act,
            desglose=desglose,
            sesiones=sesiones,
            pausas=pausas,
            revisiones=revisiones,
            ediciones=ediciones,
        )
