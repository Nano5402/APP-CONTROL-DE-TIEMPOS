"""Repositorio de jornadas diarias (RF-05b, RF-06)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.enums import EstadoJornada
from data.models import Jornada
from data.repositorios.horarios import RepoHorarios
from data.tiempo import ahora


class RepoJornadas:
    """Acceso y creación de jornadas por fecha."""

    def __init__(self, s: Session) -> None:
        self.s = s

    def obtener_por_fecha(self, fecha: date) -> Jornada | None:
        return self.s.scalar(select(Jornada).where(Jornada.fecha == fecha))

    def obtener_o_crear(self, fecha: date | None = None, momento_inicio: datetime | None = None) -> Jornada:
        """Devuelve la jornada de ``fecha`` o la crea calculando si es día laboral.

        En un día sin bloques de horario (domingo o día no laboral configurado),
        ``es_laboral`` queda en ``False``, ``duracion_jornada_seg`` en ``0`` y
        ``productividad`` en ``None`` (RF-05b).
        """
        instante = momento_inicio or ahora()
        dia = fecha or instante.date()
        existente = self.obtener_por_fecha(dia)
        if existente:
            return existente

        repo_horarios = RepoHorarios(self.s)
        duracion = repo_horarios.duracion_jornada_seg(dia)
        es_laboral = duracion > 0

        nueva = Jornada(
            fecha=dia,
            hora_inicio=instante,
            es_laboral=es_laboral,
            duracion_jornada_seg=duracion,
            estado=EstadoJornada.ABIERTA.value,
        )
        self.s.add(nueva)
        self.s.flush()
        return nueva
