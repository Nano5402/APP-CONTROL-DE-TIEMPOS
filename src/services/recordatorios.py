"""Motor de recordatorios y notificaciones de la jornada (RF-04, RF-05, RF-06).

Tipos de aviso que evalúa:
1. **Continuidad (`¿Sigues con [actividad]?`)**:
   - Intervalo con jerarquía: ``actividad → plantilla → categoría → configuración global``.
   - Si ya se mostró el aviso y el usuario no responde tras
     ``recordatorio.repetir_sin_respuesta_min`` (2 min por defecto), registra
     ``sin_respuesta`` en ``recordatorios_log``, el cronómetro sigue contando y
     vuelve a lanzar el aviso.
2. **Finalización (`Superaste el tiempo estimado`)**:
   - Cuando el tiempo trabajado supera el estimado de la actividad (o el promedio
     histórico de su categoría si no tiene estimado). Se emite una vez por actividad.
3. **Inicio sin actividad (`No tienes ninguna actividad en curso`)**:
   - En horario laboral, si no hay actividad en curso ni pausa de almuerzo abierta
     durante ``recordatorio.inicio_sin_actividad_min`` minutos.
4. **Almuerzo (`Hora de almuerzo`)**:
   - Al terminar el bloque 1 en días que tienen 2 bloques (lunes a viernes 12:00 m).
5. **Salida (`Hora de cerrar la jornada`)**:
   - Al terminar el último bloque del día (lunes a viernes 4:45 pm; sábado 12:15 pm).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from data.enums import (
    EstadoActividad,
    EstadoJornada,
    RespuestaRecordatorio,
    TipoPausa,
)
from data.models import Actividad, Jornada, Pausa, RecordatorioLog, SesionTiempo
from data.repositorios.configuracion import RepoConfiguracion
from data.repositorios.horarios import RepoHorarios
from data.tiempo import ahora
from services.cronometro import ServicioCronometro


class TipoAviso(StrEnum):
    CONTINUIDAD = "continuidad"
    FINALIZACION = "finalizacion"
    SIN_ACTIVIDAD = "sin_actividad"
    ALMUERZO = "almuerzo"
    SALIDA = "salida"


@dataclass(frozen=True)
class AvisoRecordatorio:
    """Aviso listo para mostrarse en ventana emergente o notificación de bandeja."""

    tipo: TipoAviso
    titulo: str
    mensaje: str
    actividad_id: int | None = None
    actividad_nombre: str | None = None
    es_repeticion_sin_respuesta: bool = False


class ServicioRecordatorios:
    """Evalúa qué avisos corresponden en cada instante y registra las respuestas."""

    def __init__(self, s: Session) -> None:
        self.s = s
        self.config = RepoConfiguracion(s)
        self.horarios = RepoHorarios(s)
        self.cron = ServicioCronometro(s)

        # Estado en memoria para no repetir avisos únicos en el mismo día/actividad
        self._momento_aviso_continuidad_abierto: datetime | None = None
        self._actividad_aviso_continuidad_id: int | None = None
        self._finalizacion_notificada_ids: set[int] = set()
        self._almuerzo_notificado_fecha: date | None = None
        self._salida_notificada_fecha: date | None = None
        self._ultimo_aviso_sin_actividad: datetime | None = None

    # ------------------------------------------------------------------
    # Cálculo de intervalos (jerarquía RF-04)
    # ------------------------------------------------------------------

    def intervalo_continuidad_min(self, actividad: Actividad) -> int:
        """Devuelve el intervalo en minutos para ``¿Sigues con [actividad]?``.

        Prioridad: ``actividad → plantilla → categoría → configuración del usuario``.
        """
        if actividad.intervalo_recordatorio_min and actividad.intervalo_recordatorio_min > 0:
            return actividad.intervalo_recordatorio_min
        if (
            actividad.plantilla
            and actividad.plantilla.intervalo_recordatorio_min
            and actividad.plantilla.intervalo_recordatorio_min > 0
        ):
            return actividad.plantilla.intervalo_recordatorio_min
        if (
            actividad.categoria
            and actividad.categoria.intervalo_recordatorio_min
            and actividad.categoria.intervalo_recordatorio_min > 0
        ):
            return actividad.categoria.intervalo_recordatorio_min
        return max(1, self.config.obtener_int("recordatorio.continuidad_min", 10))

    def tiempo_referencia_min(self, actividad: Actividad) -> int | None:
        """Tiempo estimado de la actividad o promedio histórico de su categoría (RF-04, 7.3)."""
        if actividad.tiempo_estimado_min and actividad.tiempo_estimado_min > 0:
            return actividad.tiempo_estimado_min
        if actividad.categoria_id is None:
            return None

        # Promedio histórico de actividades completadas de la misma categoría
        sub = (
            select(
                Actividad.id,
                func.sum(SesionTiempo.duracion_seg).label("total_seg"),
            )
            .join(SesionTiempo, SesionTiempo.actividad_id == Actividad.id)
            .where(
                Actividad.categoria_id == actividad.categoria_id,
                Actividad.estado == EstadoActividad.COMPLETADA.value,
                Actividad.es_revision.is_(False),
                Actividad.id != actividad.id,
            )
            .group_by(Actividad.id)
        ).subquery()

        prom_seg = self.s.scalar(select(func.avg(sub.c.total_seg)))
        if prom_seg and prom_seg >= 60:
            return int(round(prom_seg / 60))
        return None

    # ------------------------------------------------------------------
    # Evaluación periódica
    # ------------------------------------------------------------------

    def evaluar(self, momento: datetime | None = None) -> list[AvisoRecordatorio]:
        """Evalúa todos los recordatorios en ``momento`` y devuelve los que deben dispararse."""
        instante = momento or ahora()
        avisos: list[AvisoRecordatorio] = []

        aviso_almuerzo = self._evaluar_almuerzo(instante)
        if aviso_almuerzo:
            avisos.append(aviso_almuerzo)

        aviso_salida = self._evaluar_salida(instante)
        if aviso_salida:
            avisos.append(aviso_salida)

        activa = self.cron.actividad_en_curso()
        if activa is not None:
            self._ultimo_aviso_sin_actividad = None
            aviso_cont = self._evaluar_continuidad(activa, instante)
            if aviso_cont:
                avisos.append(aviso_cont)
            aviso_fin = self._evaluar_finalizacion(activa, instante)
            if aviso_fin:
                avisos.append(aviso_fin)
        else:
            self._limpiar_aviso_continuidad()
            aviso_inactivo = self._evaluar_sin_actividad(instante)
            if aviso_inactivo:
                avisos.append(aviso_inactivo)

        return avisos

    def _evaluar_continuidad(
        self, actividad: Actividad, instante: datetime
    ) -> AvisoRecordatorio | None:
        # Si cambió la actividad activa, reiniciamos el seguimiento del popup
        if (
            self._actividad_aviso_continuidad_id is not None
            and self._actividad_aviso_continuidad_id != actividad.id
        ):
            self._limpiar_aviso_continuidad()

        # Caso 1: ya hay un aviso "¿Sigues con...?" abierto esperando respuesta
        if self._momento_aviso_continuidad_abierto is not None:
            repetir_min = max(
                1, self.config.obtener_int("recordatorio.repetir_sin_respuesta_min", 2)
            )
            if instante >= self._momento_aviso_continuidad_abierto + timedelta(minutes=repetir_min):
                # Registra "sin_respuesta", mantiene el cronómetro corriendo y repite el aviso
                self.s.add(
                    RecordatorioLog(
                        actividad_id=actividad.id,
                        momento=instante,
                        respuesta=RespuestaRecordatorio.SIN_RESPUESTA.value,
                    )
                )
                self.s.flush()
                self._momento_aviso_continuidad_abierto = instante
                return AvisoRecordatorio(
                    tipo=TipoAviso.CONTINUIDAD,
                    titulo="¿Sigues con la actividad?",
                    mensaje=f"¿Sigues con «{actividad.nombre}»? (sin respuesta previa)",
                    actividad_id=actividad.id,
                    actividad_nombre=actividad.nombre,
                    es_repeticion_sin_respuesta=True,
                )
            return None

        # Caso 2: verificar si ya transcurrió el intervalo desde el inicio de la sesión o el último "Sí"
        sesion = self.cron.sesion_abierta(actividad.id)
        if sesion is None:
            return None

        ultimo_log = self.s.scalar(
            select(RecordatorioLog.momento)
            .where(RecordatorioLog.actividad_id == actividad.id)
            .order_by(RecordatorioLog.momento.desc())
            .limit(1)
        )
        referencia = max(sesion.inicio, ultimo_log) if ultimo_log else sesion.inicio
        intervalo = self.intervalo_continuidad_min(actividad)

        if instante >= referencia + timedelta(minutes=intervalo):
            self._momento_aviso_continuidad_abierto = instante
            self._actividad_aviso_continuidad_id = actividad.id
            return AvisoRecordatorio(
                tipo=TipoAviso.CONTINUIDAD,
                titulo="¿Sigues con la actividad?",
                mensaje=f"¿Sigues trabajando en «{actividad.nombre}»?",
                actividad_id=actividad.id,
                actividad_nombre=actividad.nombre,
                es_repeticion_sin_respuesta=False,
            )
        return None

    def _evaluar_finalizacion(
        self, actividad: Actividad, instante: datetime
    ) -> AvisoRecordatorio | None:
        if actividad.id in self._finalizacion_notificada_ids:
            return None
        meta_min = self.tiempo_referencia_min(actividad)
        if meta_min is None:
            return None

        trabajado_seg = self.cron.segundos_trabajados(actividad, momento_actual=instante)
        if trabajado_seg >= meta_min * 60:
            self._finalizacion_notificada_ids.add(actividad.id)
            lleva_min = trabajado_seg // 60
            return AvisoRecordatorio(
                tipo=TipoAviso.FINALIZACION,
                titulo="Tiempo estimado alcanzado",
                mensaje=(
                    f"Llevas {lleva_min} min en «{actividad.nombre}» "
                    f"(referencia: {meta_min} min). ¿Ya la finalizaste?"
                ),
                actividad_id=actividad.id,
                actividad_nombre=actividad.nombre,
            )
        return None

    def _evaluar_sin_actividad(self, instante: datetime) -> AvisoRecordatorio | None:
        if not self.horarios.esta_en_horario(instante):
            return None

        # Si hay una pausa de almuerzo o causa externa abierta, no molestar
        pausa_almuerzo = self.s.scalar(
            select(Pausa).where(
                Pausa.fin.is_(None),
                Pausa.tipo == TipoPausa.ALMUERZO.value,
            )
        )
        if pausa_almuerzo is not None:
            return None

        # Si la jornada ya se cerró hoy, no avisar
        jornada_hoy = self.s.scalar(select(Jornada).where(Jornada.fecha == instante.date()))
        if jornada_hoy and jornada_hoy.estado == EstadoJornada.CERRADA.value:
            return None

        intervalo_min = max(
            1, self.config.obtener_int("recordatorio.inicio_sin_actividad_min", 10)
        )

        # Punto de referencia: último fin de sesión hoy, o inicio del bloque actual
        bloques_hoy = self.horarios.bloques_del_dia(instante.weekday())
        bloque_actual = next(
            (b for b in bloques_hoy if b.hora_inicio <= instante.time() < b.hora_fin),
            None,
        )
        if bloque_actual is None:
            return None

        inicio_bloque = datetime.combine(instante.date(), bloque_actual.hora_inicio)
        inicio_dia = datetime.combine(instante.date(), datetime.min.time())
        ultimo_fin = self.s.scalar(
            select(func.max(SesionTiempo.fin)).where(SesionTiempo.fin >= inicio_dia)
        )
        referencia = max(
            x
            for x in [inicio_bloque, ultimo_fin, self._ultimo_aviso_sin_actividad]
            if x is not None
        )

        if instante >= referencia + timedelta(minutes=intervalo_min):
            self._ultimo_aviso_sin_actividad = instante
            return AvisoRecordatorio(
                tipo=TipoAviso.SIN_ACTIVIDAD,
                titulo="Sin actividad en curso",
                mensaje="No tienes ninguna actividad en curso. ¡Inicia o registra lo que estás haciendo!",
            )
        return None

    def _evaluar_almuerzo(self, instante: datetime) -> AvisoRecordatorio | None:
        if not self.config.obtener_bool("recordatorio.aviso_almuerzo", True):
            return None
        if self._almuerzo_notificado_fecha == instante.date():
            return None

        bloques = self.horarios.bloques_del_dia(instante.weekday())
        if len(bloques) < 2:
            return None

        inicio_almuerzo = bloques[0].hora_fin
        fin_almuerzo = bloques[1].hora_inicio
        if inicio_almuerzo <= instante.time() < fin_almuerzo:
            self._almuerzo_notificado_fecha = instante.date()
            return AvisoRecordatorio(
                tipo=TipoAviso.ALMUERZO,
                titulo="Hora de almuerzo",
                mensaje=(
                    f"Es hora de almuerzo ({inicio_almuerzo:%H:%M} – {fin_almuerzo:%H:%M}). "
                    "Recuerda pausar tu actividad."
                ),
            )
        return None

    def _evaluar_salida(self, instante: datetime) -> AvisoRecordatorio | None:
        if not self.config.obtener_bool("recordatorio.aviso_salida", True):
            return None
        if self._salida_notificada_fecha == instante.date():
            return None

        bloques = self.horarios.bloques_del_dia(instante.weekday())
        if not bloques:
            return None

        hora_salida = bloques[-1].hora_fin
        jornada_hoy = self.s.scalar(select(Jornada).where(Jornada.fecha == instante.date()))
        if jornada_hoy and jornada_hoy.estado == EstadoJornada.CERRADA.value:
            return None

        if instante.time() >= hora_salida:
            self._salida_notificada_fecha = instante.date()
            return AvisoRecordatorio(
                tipo=TipoAviso.SALIDA,
                titulo="Fin de la jornada laboral",
                mensaje=(
                    f"Llegó la hora de salida ({hora_salida:%H:%M}). "
                    "Abre el asistente de cierre para calcular tu productividad y generar el PDF."
                ),
            )
        return None

    # ------------------------------------------------------------------
    # Respuestas del usuario al aviso "¿Sigues con [actividad]?" (RF-04)
    # ------------------------------------------------------------------

    def responder_continuidad(
        self,
        actividad: Actividad,
        respuesta: RespuestaRecordatorio | str,
        *,
        motivo_pausa: str | None = None,
        tipo_pausa: TipoPausa | str = TipoPausa.PERSONAL,
        ajuste_minutos_menos: int = 0,
        motivo_ajuste: str | None = None,
        momento: datetime | None = None,
    ) -> RecordatorioLog:
        """Procesa la respuesta del usuario al aviso ``¿Sigues con [actividad]?``:

        - ``SI``: el cronómetro continúa y se reinicia el contador del intervalo.
        - ``NO``: la actividad se marca como completada y el cronómetro se detiene
          (con opción de descontar minutos si olvidó cerrarla antes).
        - ``PAUSAR``: pausa la actividad con el motivo indicado.
        """
        instante = momento or ahora()
        resp_enum = RespuestaRecordatorio(respuesta)

        log = RecordatorioLog(
            actividad_id=actividad.id,
            momento=instante,
            respuesta=resp_enum.value,
        )
        self.s.add(log)

        if resp_enum == RespuestaRecordatorio.NO:
            self.cron.finalizar(
                actividad,
                ajuste_minutos_menos=ajuste_minutos_menos,
                motivo_ajuste=motivo_ajuste,
                momento=instante,
            )
        elif resp_enum == RespuestaRecordatorio.PAUSAR:
            self.cron.pausar(
                actividad,
                tipo=tipo_pausa,
                motivo=motivo_pausa,
                momento=instante,
            )

        self._limpiar_aviso_continuidad()
        self.s.flush()
        return log

    def _limpiar_aviso_continuidad(self) -> None:
        self._momento_aviso_continuidad_abierto = None
        self._actividad_aviso_continuidad_id = None
