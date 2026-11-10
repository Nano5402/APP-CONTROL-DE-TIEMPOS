"""Servicio de cronómetro, sesiones de tiempo y pausas (RF-02, RF-03, RF-05, RF-05b).

Reglas clave:
- Solo puede haber **una actividad en curso** a la vez.
- Al iniciar una actividad mientras otra está activa:
  - Si es una urgencia de prioridad máxima, la anterior se pausa con tipo ``prioridad``.
  - En caso normal, el llamador decide si ``finalizar`` o ``pausar`` la anterior
    (si no lo indica, lanza ``ActividadYaEnCursoError`` para que la UI pregunte).
- Cuando un tramo de cronómetro cruza un límite del horario laboral (ej. empieza a las
  4:30 pm y termina a las 5:00 pm, siendo las 4:45 pm la salida), el tramo se divide
  automáticamente en sesiones dentro de horario (``fuera_horario=False``) y fuera de
  horario (``fuera_horario=True``), de modo que el porcentaje del día sea exacto.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from data.enums import (
    EstadoActividad,
    EstadoAprobacion,
    Lugar,
    Prioridad,
    TipoPausa,
)
from data.models import Actividad, Pausa, SesionTiempo
from data.repositorios.horarios import RepoHorarios
from data.repositorios.jornadas import RepoJornadas
from data.tiempo import ahora
from services.numeracion import separar_base_y_numero, siguiente_nombre_pieza


class AccionSobreActiva(StrEnum):
    """Qué hacer con la actividad que estaba en curso al iniciar otra."""

    PREGUNTAR = "preguntar"
    PAUSAR = "pausar"
    FINALIZAR = "finalizar"


class ActividadYaEnCursoError(RuntimeError):
    """Se lanza cuando hay otra actividad activa y no se indicó si pausar o finalizar."""

    def __init__(self, actividad_activa: Actividad) -> None:
        super().__init__(f"La actividad '{actividad_activa.nombre}' ya está en curso")
        self.actividad_activa = actividad_activa


class ActividadBloqueadaError(RuntimeError):
    """Se lanza cuando se intenta iniciar una actividad sin aprobación del ingeniero."""


def dividir_tramo_por_horario(
    repo_horarios: RepoHorarios,
    inicio: datetime,
    fin: datetime,
) -> list[tuple[datetime, datetime, bool]]:
    """Divide ``[inicio, fin]`` en subtramos ``(sub_ini, sub_fin, fuera_horario)``.

    Considera los límites de cada bloque laboral de cada día que abarque el tramo.
    """
    if fin <= inicio:
        fuera = not repo_horarios.esta_en_horario(inicio)
        return [(inicio, inicio, fuera)]

    cortes: set[datetime] = {inicio, fin}
    dia_cursor = inicio.date()
    while dia_cursor <= fin.date():
        for b in repo_horarios.bloques_del_dia(dia_cursor.weekday()):
            c_ini = datetime.combine(dia_cursor, b.hora_inicio)
            c_fin = datetime.combine(dia_cursor, b.hora_fin)
            if inicio < c_ini < fin:
                cortes.add(c_ini)
            if inicio < c_fin < fin:
                cortes.add(c_fin)
        medianoche = datetime.combine(dia_cursor + timedelta(days=1), datetime.min.time())
        if inicio < medianoche < fin:
            cortes.add(medianoche)
        dia_cursor += timedelta(days=1)

    ordenados = sorted(cortes)
    tramos: list[tuple[datetime, datetime, bool]] = []
    for a, b in zip(ordenados, ordenados[1:]):
        fuera = not repo_horarios.esta_en_horario(a)
        if tramos and tramos[-1][2] == fuera:
            tramos[-1] = (tramos[-1][0], b, fuera)
        else:
            tramos.append((a, b, fuera))
    return tramos


class ServicioCronometro:
    """Control de cronómetro, pausas, reanudación, finalización y piezas seguidas."""

    def __init__(self, s: Session) -> None:
        self.s = s
        self.repo_horarios = RepoHorarios(s)
        self.repo_jornadas = RepoJornadas(s)

    # ------------------------------------------------------------------
    # Estado actual
    # ------------------------------------------------------------------

    def actividad_en_curso(self) -> Actividad | None:
        """Devuelve la única actividad con estado ``en_curso`` (o ``None``)."""
        consulta = select(Actividad).where(Actividad.estado == EstadoActividad.EN_CURSO.value)
        return self.s.scalar(consulta)

    def sesion_abierta(self, actividad_id: int | None = None) -> SesionTiempo | None:
        """Devuelve la sesión de cronómetro abierta (``fin IS NULL``)."""
        consulta = select(SesionTiempo).where(SesionTiempo.fin.is_(None))
        if actividad_id is not None:
            consulta = consulta.where(SesionTiempo.actividad_id == actividad_id)
        return self.s.scalar(consulta)

    def pausa_abierta(self, actividad_id: int | None = None) -> Pausa | None:
        """Devuelve la pausa abierta (``fin IS NULL``), si existe."""
        consulta = select(Pausa).where(Pausa.fin.is_(None))
        if actividad_id is not None:
            consulta = consulta.where(Pausa.actividad_id == actividad_id)
        return self.s.scalar(consulta)

    def segundos_trabajados(
        self,
        actividad: Actividad,
        *,
        momento_actual: datetime | None = None,
        incluir_fuera_horario: bool = True,
    ) -> int:
        """Segundos acumulados en la actividad (incluyendo el tramo en curso si corre)."""
        instante = momento_actual or ahora()
        total = 0
        for ses in actividad.sesiones:
            if ses.fin is not None:
                if incluir_fuera_horario or not ses.fuera_horario:
                    total += ses.duracion_seg
            else:
                for a, b, fuera in dividir_tramo_por_horario(self.repo_horarios, ses.inicio, instante):
                    if incluir_fuera_horario or not fuera:
                        total += int((b - a).total_seconds())
        return total

    # ------------------------------------------------------------------
    # Iniciar, pausar, reanudar, finalizar
    # ------------------------------------------------------------------

    def iniciar(
        self,
        actividad: Actividad,
        *,
        accion_sobre_activa: AccionSobreActiva | str = AccionSobreActiva.PREGUNTAR,
        motivo_pausa_activa: str | None = None,
        lugar: Lugar | str = Lugar.OFICINA,
        momento: datetime | None = None,
    ) -> Actividad:
        """Arranca el cronómetro sobre ``actividad`` (RF-02, RF-03)."""
        if (
            actividad.estado == EstadoActividad.BLOQUEADA.value
            or actividad.aprobacion_estado == EstadoAprobacion.PENDIENTE.value
        ):
            raise ActividadBloqueadaError(
                "Esta actividad requiere aprobación del ingeniero antes de iniciarse"
            )
        if actividad.estado in (
            EstadoActividad.RECHAZADA.value,
            EstadoActividad.ELIMINADA.value,
            EstadoActividad.REASIGNADA.value,
        ):
            raise ValueError(f"No se puede iniciar una actividad en estado '{actividad.estado}'")

        instante = momento or ahora()
        activa = self.actividad_en_curso()

        if activa and activa.id == actividad.id:
            return actividad

        if activa and activa.id != actividad.id:
            accion = AccionSobreActiva(accion_sobre_activa)
            # Si la nueva es de prioridad máxima y no se especificó finalizar,
            # la regla RF-03 indica pausar por actividad prioritaria.
            if accion == AccionSobreActiva.PREGUNTAR:
                if actividad.prioridad == Prioridad.MAXIMA.value:
                    accion = AccionSobreActiva.PAUSAR
                else:
                    raise ActividadYaEnCursoError(activa)

            if accion == AccionSobreActiva.PAUSAR:
                es_urgencia = actividad.prioridad == Prioridad.MAXIMA.value
                tipo_pausa = TipoPausa.PRIORIDAD if es_urgencia else TipoPausa.OTRO
                motivo = motivo_pausa_activa or (
                    f"Interrupción por prioridad máxima: {actividad.nombre}"
                    if es_urgencia
                    else f"Cambio a actividad: {actividad.nombre}"
                )
                self.pausar(activa, tipo=tipo_pausa, motivo=motivo, momento=instante)
            elif accion == AccionSobreActiva.FINALIZAR:
                self.finalizar(activa, momento=instante)

        # Si la actividad tenía una pausa abierta (estaba pausada o arrastrada), se cierra.
        self._cerrar_pausas_abiertas(actividad.id, instante)

        # Garantiza que exista la jornada del día en que corre el cronómetro.
        self.repo_jornadas.obtener_o_crear(instante.date(), instante)

        fuera = not self.repo_horarios.esta_en_horario(instante)
        sesion = SesionTiempo(
            actividad=actividad,
            inicio=instante,
            fin=None,
            duracion_seg=0,
            fuera_horario=fuera,
            lugar=Lugar(lugar).value,
        )
        self.s.add(sesion)
        actividad.estado = EstadoActividad.EN_CURSO.value
        self.s.flush()
        return actividad

    def pausar(
        self,
        actividad: Actividad | None = None,
        *,
        tipo: TipoPausa | str = TipoPausa.OTRO,
        motivo: str | None = None,
        avance_pct: int | None = None,
        momento: datetime | None = None,
    ) -> Pausa:
        """Pausa la actividad en curso (o registra una pausa de jornada como almuerzo)."""
        instante = momento or ahora()
        tipo_enum = TipoPausa(tipo)

        if tipo_enum == TipoPausa.FIN_JORNADA and avance_pct is None:
            raise ValueError("Al pausar por fin de jornada debe indicar el porcentaje de avance")
        if avance_pct is not None and not (0 <= avance_pct <= 100):
            raise ValueError("El porcentaje de avance debe estar entre 0 y 100")

        objetivo = actividad or self.actividad_en_curso()
        jornada_hoy = self.repo_jornadas.obtener_o_crear(instante.date(), instante)

        if objetivo is not None:
            self._cerrar_sesion_activa(objetivo, instante)
            if avance_pct is not None:
                objetivo.avance_pct = avance_pct
            if tipo_enum == TipoPausa.FIN_JORNADA:
                objetivo.estado = EstadoActividad.ARRASTRADA.value
            else:
                objetivo.estado = EstadoActividad.PAUSADA.value

        pausa = Pausa(
            jornada_id=jornada_hoy.id,
            actividad=objetivo,
            inicio=instante,
            fin=None,
            motivo=motivo.strip() if motivo else None,
            tipo=tipo_enum.value,
            es_externa=(tipo_enum == TipoPausa.EXTERNA),
            avance_pct=avance_pct if tipo_enum == TipoPausa.FIN_JORNADA else None,
        )
        self.s.add(pausa)
        self.s.flush()
        return pausa

    def reanudar(
        self,
        actividad: Actividad,
        *,
        accion_sobre_activa: AccionSobreActiva | str = AccionSobreActiva.PREGUNTAR,
        lugar: Lugar | str = Lugar.OFICINA,
        momento: datetime | None = None,
    ) -> Actividad:
        """Reanuda una actividad pausada o arrastrada (en la oficina o desde casa)."""
        if actividad.estado not in (
            EstadoActividad.PAUSADA.value,
            EstadoActividad.ARRASTRADA.value,
        ):
            raise ValueError("Solo se pueden reanudar actividades pausadas o arrastradas")
        return self.iniciar(
            actividad,
            accion_sobre_activa=accion_sobre_activa,
            lugar=lugar,
            momento=momento,
        )

    def cerrar_pausa_jornada(self, momento: datetime | None = None) -> Pausa | None:
        """Cierra una pausa general sin actividad (ej. regreso de almuerzo)."""
        instante = momento or ahora()
        pausa = self.s.scalar(
            select(Pausa).where(Pausa.fin.is_(None), Pausa.actividad_id.is_(None))
        )
        if pausa:
            pausa.fin = instante
            self.s.flush()
        return pausa

    def finalizar(
        self,
        actividad: Actividad,
        *,
        descripcion: str | None = None,
        ajuste_minutos_menos: int = 0,
        motivo_ajuste: str | None = None,
        momento: datetime | None = None,
    ) -> Actividad:
        """Detiene el cronómetro y marca la actividad como ``completada`` (RF-02).

        Si ``ajuste_minutos_menos > 0`` (ej. cuando responde "No" en el recordatorio
        y descuenta minutos de inactividad), retrocede el fin de la sesión activa y
        deja trazabilidad si se indicó motivo.
        """
        instante = momento or ahora()
        if ajuste_minutos_menos < 0:
            raise ValueError("El ajuste de minutos no puede ser negativo")

        instante_fin = instante - timedelta(minutes=ajuste_minutos_menos)
        self._cerrar_sesion_activa(actividad, instante_fin)
        self._cerrar_pausas_abiertas(actividad.id, instante_fin)

        if descripcion is not None and descripcion.strip():
            actividad.descripcion = descripcion.strip()
        if ajuste_minutos_menos > 0 and motivo_ajuste and motivo_ajuste.strip():
            actividad.editado = True
            actividad.editado_motivo = motivo_ajuste.strip()

        actividad.avance_pct = 100
        actividad.estado = EstadoActividad.COMPLETADA.value
        actividad.finalizada_en = instante_fin
        self.s.flush()
        return actividad

    def siguiente_actividad_sugerida(
        self, actividad_actual: Actividad | None = None
    ) -> tuple[Actividad | None, str | None]:
        """Determina cuál es la siguiente actividad lógica tras ``actividad_actual``.

        Reglas:
        1. Si ``actividad_actual`` es una pieza explícitamente numerada (ej. ``Flyer 1``),
           busca la siguiente pieza numerada ``pendiente`` (ej. ``Flyer 2``) o sugiere
           crearla con ese nombre.
        2. Si ``actividad_actual`` **no** tiene número al final (ej. ``Depuración``),
           **nunca** inventa ``Depuración 2``: busca la siguiente actividad ``pendiente``
           (o ``pausada``/``arrastrada``) que ya exista en la lista de la jornada.
        """
        act = actividad_actual or self.actividad_en_curso()
        if act is None:
            return None, None

        _base, num_actual = separar_base_y_numero(act.nombre)
        if num_actual is not None:
            consulta_trabajadas = select(Actividad.nombre).where(
                Actividad.jornada_id == act.jornada_id,
                Actividad.id != act.id,
                Actividad.estado.not_in(
                    [EstadoActividad.ELIMINADA.value, EstadoActividad.PENDIENTE.value]
                ),
            )
            trabajadas = list(self.s.scalars(consulta_trabajadas)) + [act.nombre]
            nombre_pieza = siguiente_nombre_pieza(act.nombre, trabajadas)
            candidata = self.s.scalar(
                select(Actividad)
                .where(
                    Actividad.jornada_id == act.jornada_id,
                    Actividad.id != act.id,
                    Actividad.estado == EstadoActividad.PENDIENTE.value,
                    Actividad.nombre.ilike(nombre_pieza),
                )
                .order_by(Actividad.id)
            )
            if candidata is not None:
                return candidata, candidata.nombre
            return None, nombre_pieza

        orden_prio = case(
            (Actividad.prioridad == Prioridad.MAXIMA.value, 0),
            (Actividad.prioridad == Prioridad.NORMAL.value, 1),
            else_=2,
        )
        pendiente = self.s.scalar(
            select(Actividad)
            .where(
                Actividad.jornada_id == act.jornada_id,
                Actividad.id != act.id,
                Actividad.estado == EstadoActividad.PENDIENTE.value,
                Actividad.aprobacion_estado != EstadoAprobacion.PENDIENTE.value,
            )
            .order_by(orden_prio, Actividad.id)
        )
        if pendiente is not None:
            return pendiente, pendiente.nombre

        pausada = self.s.scalar(
            select(Actividad)
            .where(
                Actividad.jornada_id == act.jornada_id,
                Actividad.id != act.id,
                Actividad.estado.in_(
                    [EstadoActividad.PAUSADA.value, EstadoActividad.ARRASTRADA.value]
                ),
                Actividad.aprobacion_estado != EstadoAprobacion.PENDIENTE.value,
            )
            .order_by(orden_prio, Actividad.id)
        )
        if pausada is not None:
            return pausada, pausada.nombre

        return None, None

    def finalizar_y_empezar_siguiente(
        self,
        actividad_actual: Actividad,
        *,
        nombre_siguiente: str | None = None,
        descripcion_actual: str | None = None,
        lugar: Lugar | str = Lugar.OFICINA,
        momento: datetime | None = None,
    ) -> Actividad:
        """Finaliza la actividad actual y arranca la siguiente en 1 acción (RF-02).

        - Si la actividad actual es una pieza numerada (ej. ``Flyer 1``), continúa con
          la siguiente pieza numerada (``Flyer 2``), reutilizándola si ya estaba
          planeada o creándola si es una serie.
        - Si la actividad actual **no** es numerada (ej. ``Depuración``), inicia la
          siguiente actividad ``pendiente`` (o ``pausada``) de la lista del día sin
          inventar ``Depuración 2``.
        """
        instante = momento or ahora()
        self.finalizar(actividad_actual, descripcion=descripcion_actual, momento=instante)

        if nombre_siguiente and nombre_siguiente.strip():
            nombre_obj = nombre_siguiente.strip()
            candidata = self.s.scalar(
                select(Actividad)
                .where(
                    Actividad.jornada_id == actividad_actual.jornada_id,
                    Actividad.estado == EstadoActividad.PENDIENTE.value,
                    Actividad.nombre.ilike(nombre_obj),
                )
                .order_by(Actividad.id)
            )
            if candidata is None:
                candidata = self._clonar_pieza(actividad_actual, nombre_obj, instante)
            return self.iniciar(candidata, lugar=lugar, momento=instante)

        candidata, nombre_crear = self.siguiente_actividad_sugerida(actividad_actual)
        if candidata is not None:
            return self.iniciar(candidata, lugar=lugar, momento=instante)

        if nombre_crear is not None:
            nueva = self._clonar_pieza(actividad_actual, nombre_crear, instante)
            return self.iniciar(nueva, lugar=lugar, momento=instante)

        return actividad_actual

    def _clonar_pieza(
        self, base: Actividad, nombre_pieza: str, instante: datetime
    ) -> Actividad:
        nueva = Actividad(
            jornada_id=base.jornada_id,
            categoria_id=base.categoria_id,
            plantilla_id=base.plantilla_id,
            nombre=nombre_pieza,
            tipo=base.tipo,
            solicitante_id=base.solicitante_id,
            prioridad=base.prioridad,
            estado=EstadoActividad.PENDIENTE.value,
            aprobacion_estado=base.aprobacion_estado,
            tiempo_estimado_min=base.tiempo_estimado_min,
            intervalo_recordatorio_min=base.intervalo_recordatorio_min,
            creada_en=instante,
        )
        self.s.add(nueva)
        self.s.flush()
        return nueva

    def reasignar(
        self,
        actividad: Actividad,
        *,
        persona: str,
        motivo: str,
        momento: datetime | None = None,
    ) -> Actividad:
        """Marca la actividad como reasignada conservando el tiempo ya trabajado (RF-03c)."""
        persona_limpia = persona.strip()
        motivo_limpio = motivo.strip()
        if not persona_limpia:
            raise ValueError("Debe indicar a quién se reasigna la actividad")
        if not motivo_limpio:
            raise ValueError("Debe indicar el motivo de la reasignación")

        instante = momento or ahora()
        self._cerrar_sesion_activa(actividad, instante)
        self._cerrar_pausas_abiertas(actividad.id, instante)

        actividad.reasignada_a = persona_limpia
        actividad.reasignacion_motivo = motivo_limpio
        actividad.estado = EstadoActividad.REASIGNADA.value
        self.s.flush()
        return actividad

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _cerrar_sesion_activa(self, actividad: Actividad, instante_fin: datetime) -> None:
        sesion = self.sesion_abierta(actividad.id)
        if sesion is None:
            return
        fin_real = max(instante_fin, sesion.inicio)
        tramos = dividir_tramo_por_horario(self.repo_horarios, sesion.inicio, fin_real)

        # El primer tramo actualiza la sesión existente; si cruzó horario se crean las demás.
        primero_ini, primero_fin, primero_fuera = tramos[0]
        sesion.inicio = primero_ini
        sesion.fin = primero_fin
        sesion.duracion_seg = int((primero_fin - primero_ini).total_seconds())
        sesion.fuera_horario = primero_fuera

        for sub_ini, sub_fin, sub_fuera in tramos[1:]:
            self.s.add(
                SesionTiempo(
                    actividad=actividad,
                    inicio=sub_ini,
                    fin=sub_fin,
                    duracion_seg=int((sub_fin - sub_ini).total_seconds()),
                    fuera_horario=sub_fuera,
                    lugar=sesion.lugar,
                )
            )
        self.s.flush()

    def _cerrar_pausas_abiertas(self, actividad_id: int, instante_fin: datetime) -> None:
        consulta = select(Pausa).where(
            Pausa.actividad_id == actividad_id,
            Pausa.fin.is_(None),
        )
        for p in self.s.scalars(consulta):
            p.fin = max(instante_fin, p.inicio)
        self.s.flush()
