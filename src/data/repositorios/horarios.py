"""Consultas sobre el horario laboral configurado por día de la semana.

El horario se define con uno o más bloques por día (sección 6.1). Un día sin
bloques (domingo, por defecto) es **no laboral**: todo el tiempo trabajado se
registra como "fuera de horario" y la jornada no tiene porcentaje.
"""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models import Horario


def _segundos(t: time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


class RepoHorarios:
    """Acceso al horario laboral."""

    def __init__(self, s: Session) -> None:
        self.s = s

    def bloques_del_dia(self, dia_semana: int) -> list[Horario]:
        """Bloques del día (0 = lunes ... 6 = domingo), ordenados por hora."""
        consulta = (
            select(Horario)
            .where(Horario.dia_semana == dia_semana)
            .order_by(Horario.hora_inicio)
        )
        return list(self.s.scalars(consulta))

    def es_dia_laboral(self, fecha: date) -> bool:
        """``True`` si ese día de la semana tiene al menos un bloque."""
        return bool(self.bloques_del_dia(fecha.weekday()))

    def duracion_jornada_seg(self, fecha: date) -> int:
        """Duración laboral del día en segundos (suma de bloques, sin almuerzo)."""
        return sum(
            _segundos(b.hora_fin) - _segundos(b.hora_inicio)
            for b in self.bloques_del_dia(fecha.weekday())
        )

    def esta_en_horario(self, momento: datetime) -> bool:
        """``True`` si el momento cae dentro de algún bloque laboral (fin excluido)."""
        hora = momento.time()
        return any(
            b.hora_inicio <= hora < b.hora_fin for b in self.bloques_del_dia(momento.weekday())
        )

    def reemplazar_dia(self, dia_semana: int, bloques: list[tuple[time, time]]) -> None:
        """Sustituye todos los bloques de un día. Lista vacía = día no laboral.

        Lanza ``ValueError`` si algún bloque es inválido o si se solapan.
        """
        ordenados = sorted(bloques)
        for i, (inicio, fin) in enumerate(ordenados):
            if inicio >= fin:
                raise ValueError(f"Bloque inválido: {inicio:%H:%M} – {fin:%H:%M}")
            if i and inicio < ordenados[i - 1][1]:
                raise ValueError("Los bloques del día no pueden solaparse")

        for b in self.bloques_del_dia(dia_semana):
            self.s.delete(b)
        self.s.flush()
        for n, (inicio, fin) in enumerate(ordenados, start=1):
            self.s.add(Horario(dia_semana=dia_semana, bloque=n, hora_inicio=inicio, hora_fin=fin))
        self.s.flush()
