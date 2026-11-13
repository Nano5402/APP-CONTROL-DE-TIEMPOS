"""Servicio del tablero colaborativo de Planeación Semanal.

Permite organizar de forma visual las tareas de la semana entre todos los miembros
del equipo, filtrar por responsable o día, marcar avance y trasladar tareas
con un solo clic al plan diario individual en PantallaHoy.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from data.enums import EstadoActividad, Prioridad, TipoActividad
from data.models import Actividad, Categoria, ItemPlaneacion, Jornada, Solicitante, Usuario
from data.repositorios.jornadas import RepoJornadas
from data.tiempo import ahora


def inicio_semana(fecha: date | None = None) -> date:
    """Devuelve el lunes de la semana correspondiente a ``fecha``."""
    f = fecha or date.today()
    return f - timedelta(days=f.weekday())


class ServicioPlaneacion:
    """Operaciones de consulta, alta y gestión del tablero de planeación."""

    def __init__(self, s: Session) -> None:
        self.s = s

    def listar_items(
        self,
        fecha_semana: date,
        *,
        responsable: str | None = None,
        solo_pendientes: bool = False,
    ) -> list[ItemPlaneacion]:
        """Obtiene las tareas de la semana dada ordenadas por día y orden."""
        lunes = inicio_semana(fecha_semana)
        consulta = (
            select(ItemPlaneacion)
            .options(selectinload(ItemPlaneacion.categoria))
            .where(ItemPlaneacion.fecha_semana == lunes)
            .order_by(
                ItemPlaneacion.dia_semana.nulls_last(),
                ItemPlaneacion.orden.asc(),
                ItemPlaneacion.id.asc(),
            )
        )
        if responsable and responsable.strip():
            consulta = consulta.where(ItemPlaneacion.responsable == responsable.strip())
        if solo_pendientes:
            consulta = consulta.where(ItemPlaneacion.completado.is_(False))

        return list(self.s.scalars(consulta).all())

    def crear_item(
        self,
        titulo: str,
        *,
        responsable: str = "",
        fecha_semana: date | None = None,
        dia_semana: int | None = None,
        categoria_id: int | None = None,
        prioridad: Prioridad | str = Prioridad.NORMAL,
        tiempo_estimado_min: int | None = None,
        descripcion: str | None = None,
    ) -> ItemPlaneacion:
        """Crea una nueva tarea en el tablero de la semana."""
        titulo_limpio = titulo.strip()
        if not titulo_limpio:
            raise ValueError("El título de la tarea es obligatorio")

        lunes = inicio_semana(fecha_semana)
        dia_val = dia_semana if (dia_semana is not None and 0 <= dia_semana <= 6) else None
        prio_val = Prioridad(prioridad).value

        # Calcular orden al final de la columna correspondiente
        consulta_orden = (
            select(ItemPlaneacion.orden)
            .where(
                ItemPlaneacion.fecha_semana == lunes,
                ItemPlaneacion.dia_semana == dia_val,
            )
            .order_by(ItemPlaneacion.orden.desc())
            .limit(1)
        )
        ultimo_orden = self.s.scalar(consulta_orden)
        nuevo_orden = (ultimo_orden + 1) if ultimo_orden is not None else 0

        item = ItemPlaneacion(
            titulo=titulo_limpio,
            responsable=responsable.strip(),
            descripcion=descripcion.strip() if descripcion else None,
            categoria_id=categoria_id,
            dia_semana=dia_val,
            fecha_semana=lunes,
            prioridad=prio_val,
            tiempo_estimado_min=tiempo_estimado_min if (tiempo_estimado_min and tiempo_estimado_min > 0) else None,
            completado=False,
            orden=nuevo_orden,
            creado_en=ahora(),
        )
        self.s.add(item)
        self.s.flush()
        return item

    def actualizar_item(
        self,
        item_id: int,
        *,
        titulo: str | None = None,
        responsable: str | None = None,
        dia_semana: int | None = -999,  # Centinela para permitir None explícito
        categoria_id: int | None = -999,
        prioridad: Prioridad | str | None = None,
        tiempo_estimado_min: int | None = -999,
        descripcion: str | None = None,
    ) -> ItemPlaneacion:
        item = self.s.get(ItemPlaneacion, item_id)
        if item is None:
            raise ValueError(f"No existe el ítem de planeación {item_id}")

        if titulo is not None:
            t = titulo.strip()
            if not t:
                raise ValueError("El título no puede estar vacío")
            item.titulo = t
        if responsable is not None:
            item.responsable = responsable.strip()
        if dia_semana != -999:
            item.dia_semana = dia_semana if (dia_semana is not None and 0 <= dia_semana <= 6) else None
        if categoria_id != -999:
            item.categoria_id = categoria_id
        if prioridad is not None:
            item.prioridad = Prioridad(prioridad).value
        if tiempo_estimado_min != -999:
            item.tiempo_estimado_min = (
                tiempo_estimado_min if (tiempo_estimado_min and tiempo_estimado_min > 0) else None
            )
        if descripcion is not None:
            item.descripcion = descripcion.strip() if descripcion.strip() else None

        self.s.flush()
        return item

    def alternar_completado(self, item_id: int) -> bool:
        """Invierte el estado completado de la tarea y registra fecha si aplica."""
        item = self.s.get(ItemPlaneacion, item_id)
        if item is None:
            raise ValueError(f"No existe el ítem de planeación {item_id}")

        item.completado = not item.completado
        item.completado_en = ahora() if item.completado else None
        self.s.flush()
        return item.completado

    def mover_dia(self, item_id: int, nuevo_dia: int | None) -> ItemPlaneacion:
        """Cambia el día asignado a la tarea en la semana."""
        return self.actualizar_item(item_id, dia_semana=nuevo_dia)

    def eliminar_item(self, item_id: int) -> None:
        """Elimina una tarea del tablero."""
        item = self.s.get(ItemPlaneacion, item_id)
        if item is not None:
            self.s.delete(item)
            self.s.flush()

    def pasar_a_plan_hoy(self, item_id: int, jornada_id: int | None = None) -> Actividad:
        """Convierte una tarea del tablero semanal en actividad planeada de la jornada."""
        item = self.s.get(ItemPlaneacion, item_id)
        if item is None:
            raise ValueError(f"No existe el ítem de planeación {item_id}")

        instante = ahora()
        repo_j = RepoJornadas(self.s)
        jornada = (
            self.s.get(Jornada, jornada_id)
            if jornada_id
            else repo_j.obtener_o_crear(instante.date(), instante)
        )

        act = Actividad(
            jornada_id=jornada.id,
            categoria_id=item.categoria_id,
            nombre=item.titulo,
            tipo=TipoActividad.PLANEADA.value,
            prioridad=item.prioridad,
            estado=EstadoActividad.PENDIENTE.value,
            tiempo_estimado_min=item.tiempo_estimado_min,
            descripcion=item.descripcion,
            notas=f"[Desde Planeación Semanal] Responsable: {item.responsable}" if item.responsable else "[Desde Planeación Semanal]",
            creada_en=instante,
        )
        self.s.add(act)
        self.s.flush()
        return act

    def listar_responsables_conocidos(self) -> list[str]:
        """Obtiene la lista de nombres sugeridos para el responsable de la tarea."""
        nombres: set[str] = set()
        for r in self.s.scalars(select(ItemPlaneacion.responsable).distinct()):
            if r and r.strip():
                nombres.add(r.strip())
        for u in self.s.scalars(select(Usuario.nombre).distinct()):
            if u and u.strip():
                nombres.add(u.strip())
        for sol in self.s.scalars(select(Solicitante.nombre).where(Solicitante.activo.is_(True))):
            if sol and sol.strip():
                nombres.add(sol.strip())
        for rea in self.s.scalars(select(Actividad.reasignada_a).distinct()):
            if rea and rea.strip():
                nombres.add(rea.strip())

        return sorted(nombres)
