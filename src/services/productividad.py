"""Cálculo del porcentaje de productividad diario, semáforo, meta de tiempo y
datos de referencia (sección 7, RF-06 y RF-10 del plan).

Fórmula propuesta (v1):
    Productividad (%) = peso_cumplimiento × Cumplimiento
                      + peso_eficiencia  × Eficiencia
                      + peso_foco        × Foco

Reglas especiales (sección 7.3):
- **Cumplimiento**:
  - Entran las actividades ``planeadas`` de la jornada (no eliminadas ni rechazadas).
  - Las ``extras`` de jefe/doctoras (y las de compañeros/terceros aprobadas por el
    ingeniero) completadas suman como cumplimiento.
  - Si una actividad planeada quedó ``arrastrada`` (pausa de fin de jornada con motivo)
    o ``pausada`` por una urgencia de prioridad máxima, no se penaliza como 0 %:
    aporta su ``avance_pct`` (0–100 %) tanto al numerador como a una unidad del
    denominador; el día en que se termina aporta el porcentaje restante.
  - Las ``no_planeadas`` y las ``revisiones`` no entran al Cumplimiento.
- **Eficiencia**:
  - Por cada actividad trabajada en el día (no revisión): ``min(100, estimado / real × 100)``.
  - Si no tiene estimado propio, usa el promedio histórico de esa categoría; si no
    hay historial en la categoría, la actividad no entra en la Eficiencia.
  - Si ninguna actividad del día tiene estimado ni historial, el peso de Eficiencia
    se redistribuye proporcionalmente entre Cumplimiento y Foco (o se asume 100 %
    neutral si hubo trabajo efectivo) para no castigar al usuario.
- **Foco**:
  - ``tiempo_efectivo_dentro_de_horario ÷ max(1, duracion_jornada − pausas_causa_externa)``
    (con tope en 100 %).
  - Incluye el tiempo dentro de horario de todas las actividades (planeadas, extras,
    no planeadas, revisiones y reasignadas).
  - El tiempo ``fuera_horario`` se reporta aparte y no entra en el porcentaje.
- **Días no laborales**:
  - Cuando ``jornada.es_laboral`` es ``False``, ``productividad`` es ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from data.enums import (
    EstadoActividad,
    EstadoAprobacion,
    Prioridad,
    TipoActividad,
    TipoPausa,
)
from data.models import Actividad, Categoria, Jornada, Pausa, SesionTiempo
from data.repositorios.configuracion import RepoConfiguracion


class NivelSemaforo(StrEnum):
    EXCELENTE = "excelente"  # >= 85 %
    ACEPTABLE = "aceptable"  # 60 - 84 %
    POR_MEJORAR = "por_mejorar"  # < 60 %
    NO_APLICA = "no_aplica"  # Día no laboral

    def emoji(self) -> str:
        return {
            NivelSemaforo.EXCELENTE: "🟢",
            NivelSemaforo.ACEPTABLE: "🟡",
            NivelSemaforo.POR_MEJORAR: "🔴",
            NivelSemaforo.NO_APLICA: "⚪",
        }[self]

    def etiqueta(self) -> str:
        return {
            NivelSemaforo.EXCELENTE: "Excelente",
            NivelSemaforo.ACEPTABLE: "Aceptable",
            NivelSemaforo.POR_MEJORAR: "Por mejorar",
            NivelSemaforo.NO_APLICA: "Día no laboral",
        }[self]


@dataclass(frozen=True)
class DatoReferenciaCategoria:
    """Dato informativo sin juicio de valor (RF-10)."""

    categoria_nombre: str
    cantidad_hoy: int
    promedio_historico_min: int
    mensaje: str


@dataclass(frozen=True)
class ResultadoProductividad:
    """Resultado completo del cálculo de productividad de una jornada."""

    fecha: date
    es_laboral: bool
    cumplimiento_pct: float | None
    eficiencia_pct: float | None
    foco_pct: float | None
    productividad_pct: float | None
    semaforo: NivelSemaforo
    # Tiempos en segundos
    tiempo_efectivo_seg: int
    tiempo_fuera_horario_seg: int
    tiempo_pausas_seg: int
    tiempo_pausas_externas_seg: int
    duracion_jornada_seg: int
    # Meta de tiempo efectivo (RF-10)
    meta_tiempo_pct: float
    meta_tiempo_seg: int
    progreso_meta_pct: float
    # Conteos de resumen
    planeadas_total: int
    planeadas_completadas: int
    extras_completadas: int
    no_planeadas_completadas: int
    arrastradas: int
    pendientes: int
    revisiones_realizadas: int
    datos_referencia: list[DatoReferenciaCategoria]
    tiempo_almuerzo_seg: int = 0

    @property
    def tiempo_bruto_jornada_seg(self) -> int:
        """Tiempo bruto invertido en la jornada laboral (efectivo + pausas breves)."""
        return self.tiempo_efectivo_seg + self.tiempo_pausas_seg

    @property
    def tiempo_bruto_total_seg(self) -> int:
        """Tiempo total registrado en el día (bruto en jornada + fuera de horario)."""
        return self.tiempo_efectivo_seg + self.tiempo_pausas_seg + self.tiempo_fuera_horario_seg


class ServicioProductividad:
    """Calcula los indicadores de productividad y referencia de una jornada."""

    def __init__(self, s: Session) -> None:
        self.s = s
        self.config = RepoConfiguracion(s)

    def calcular_jornada(self, jornada: Jornada) -> ResultadoProductividad:
        """Calcula todos los indicadores de ``jornada`` sin modificar su estado."""
        inicio_dia = datetime.combine(jornada.fecha, datetime.min.time())
        fin_dia = datetime.combine(jornada.fecha, datetime.max.time())

        # Sesiones trabajadas en la fecha de la jornada (incluye arrastradas de días previos)
        sesiones_dia = list(
            self.s.scalars(
                select(SesionTiempo).where(
                    SesionTiempo.inicio >= inicio_dia,
                    SesionTiempo.inicio <= fin_dia,
                    SesionTiempo.fin.is_not(None),
                )
            )
        )

        tiempo_efectivo_seg = sum(s.duracion_seg for s in sesiones_dia if not s.fuera_horario)
        tiempo_fuera_seg = sum(s.duracion_seg for s in sesiones_dia if s.fuera_horario)

        # Pausas cerradas de la jornada
        pausas_jornada = list(
            self.s.scalars(
                select(Pausa).where(
                    Pausa.jornada_id == jornada.id,
                    Pausa.fin.is_not(None),
                )
            )
        )
        pausas_excluidas = {
            TipoPausa.FIN_JORNADA.value,
            TipoPausa.ALMUERZO.value,
        }
        tiempo_pausas_seg = sum(
            max(0, int((p.fin - p.inicio).total_seconds()))
            for p in pausas_jornada
            if p.fin and p.tipo not in pausas_excluidas
        )
        tiempo_almuerzo_seg = sum(
            max(0, int((p.fin - p.inicio).total_seconds()))
            for p in pausas_jornada
            if p.fin and p.tipo == TipoPausa.ALMUERZO.value
        )
        tiempo_pausas_ext_seg = sum(
            max(0, int((p.fin - p.inicio).total_seconds()))
            for p in pausas_jornada
            if p.fin and p.es_externa
        )

        actividades_jornada = list(
            self.s.scalars(
                select(Actividad).where(
                    Actividad.jornada_id == jornada.id,
                    Actividad.estado != EstadoActividad.ELIMINADA.value,
                )
            )
        )

        # Conteos de resumen
        planeadas = [
            a
            for a in actividades_jornada
            if a.tipo == TipoActividad.PLANEADA.value
            and not a.es_revision
            and a.estado != EstadoActividad.RECHAZADA.value
        ]
        planeadas_comp = [
            a for a in planeadas if a.estado == EstadoActividad.COMPLETADA.value
        ]
        extras_comp = [
            a
            for a in actividades_jornada
            if a.tipo == TipoActividad.EXTRA.value
            and not a.es_revision
            and a.estado == EstadoActividad.COMPLETADA.value
        ]
        no_plan_comp = [
            a
            for a in actividades_jornada
            if a.tipo == TipoActividad.NO_PLANEADA.value
            and not a.es_revision
            and a.estado == EstadoActividad.COMPLETADA.value
        ]
        arrastradas = [
            a
            for a in actividades_jornada
            if a.estado == EstadoActividad.ARRASTRADA.value
        ]
        pendientes = [
            a
            for a in actividades_jornada
            if a.estado in (EstadoActividad.PENDIENTE.value, EstadoActividad.PAUSADA.value)
        ]
        revisiones_realizadas = [
            a
            for a in actividades_jornada
            if a.es_revision and a.estado == EstadoActividad.COMPLETADA.value
        ]

        # Referencia de jornada completa (100 % del horario salvo ajuste manual)
        meta_pct = self.config.obtener_float("meta.tiempo_efectivo_pct", 100.0)
        meta_seg = int(round(jornada.duracion_jornada_seg * (meta_pct / 100.0)))
        if meta_seg > 0:
            progreso_meta = min(100.0, round((tiempo_efectivo_seg / meta_seg) * 100.0, 1))
        else:
            progreso_meta = 0.0

        datos_ref = self._calcular_datos_referencia(actividades_jornada)

        # Día no laboral → sin porcentaje (RF-05b)
        if not jornada.es_laboral or jornada.duracion_jornada_seg <= 0:
            return ResultadoProductividad(
                fecha=jornada.fecha,
                es_laboral=False,
                cumplimiento_pct=None,
                eficiencia_pct=None,
                foco_pct=None,
                productividad_pct=None,
                semaforo=NivelSemaforo.NO_APLICA,
                tiempo_efectivo_seg=tiempo_efectivo_seg,
                tiempo_fuera_horario_seg=tiempo_fuera_seg,
                tiempo_pausas_seg=tiempo_pausas_seg,
                tiempo_pausas_externas_seg=tiempo_pausas_ext_seg,
                duracion_jornada_seg=0,
                meta_tiempo_pct=meta_pct,
                meta_tiempo_seg=0,
                progreso_meta_pct=0.0,
                planeadas_total=len(planeadas),
                planeadas_completadas=len(planeadas_comp),
                extras_completadas=len(extras_comp),
                no_planeadas_completadas=len(no_plan_comp),
                arrastradas=len(arrastradas),
                pendientes=len(pendientes),
                revisiones_realizadas=len(revisiones_realizadas),
                datos_referencia=datos_ref,
                tiempo_almuerzo_seg=tiempo_almuerzo_seg,
            )

        cumplimiento = self._calcular_cumplimiento(actividades_jornada, sesiones_dia, jornada)
        eficiencia = self._calcular_eficiencia(actividades_jornada, sesiones_dia)
        foco = self._calcular_foco(
            tiempo_efectivo_seg, jornada.duracion_jornada_seg, tiempo_pausas_ext_seg
        )

        w_c = self.config.obtener_float("productividad.peso_cumplimiento", 0.40)
        w_e = self.config.obtener_float("productividad.peso_eficiencia", 0.30)
        w_f = self.config.obtener_float("productividad.peso_foco", 0.30)

        # Si no hubo plan ni extras (ej. trabajó solo con no planeadas) o no hay
        # actividades con estimado/historial para eficiencia, ponderamos sobre los
        # indicadores disponibles para no castigar injustamente.
        componentes: list[tuple[float, float]] = []
        if cumplimiento is not None:
            componentes.append((w_c, cumplimiento))
        if eficiencia is not None:
            componentes.append((w_e, eficiencia))
        componentes.append((w_f, foco))

        suma_pesos = sum(p for p, _ in componentes) or 1.0
        productividad = round(sum(p * val for p, val in componentes) / suma_pesos, 1)
        semaforo = self.clasificar_semaforo(productividad)

        return ResultadoProductividad(
            fecha=jornada.fecha,
            es_laboral=True,
            cumplimiento_pct=round(cumplimiento, 1) if cumplimiento is not None else None,
            eficiencia_pct=round(eficiencia, 1) if eficiencia is not None else None,
            foco_pct=round(foco, 1),
            productividad_pct=productividad,
            semaforo=semaforo,
            tiempo_efectivo_seg=tiempo_efectivo_seg,
            tiempo_fuera_horario_seg=tiempo_fuera_seg,
            tiempo_pausas_seg=tiempo_pausas_seg,
            tiempo_pausas_externas_seg=tiempo_pausas_ext_seg,
            duracion_jornada_seg=jornada.duracion_jornada_seg,
            meta_tiempo_pct=meta_pct,
            meta_tiempo_seg=meta_seg,
            progreso_meta_pct=progreso_meta,
            planeadas_total=len(planeadas),
            planeadas_completadas=len(planeadas_comp),
            extras_completadas=len(extras_comp),
            no_planeadas_completadas=len(no_plan_comp),
            arrastradas=len(arrastradas),
            pendientes=len(pendientes),
            revisiones_realizadas=len(revisiones_realizadas),
            datos_referencia=datos_ref,
            tiempo_almuerzo_seg=tiempo_almuerzo_seg,
        )

    def clasificar_semaforo(self, productividad_pct: float | None) -> NivelSemaforo:
        if productividad_pct is None:
            return NivelSemaforo.NO_APLICA
        verde = self.config.obtener_float("semaforo.verde_min", 85.0)
        amarillo = self.config.obtener_float("semaforo.amarillo_min", 60.0)
        if productividad_pct >= verde:
            return NivelSemaforo.EXCELENTE
        if productividad_pct >= amarillo:
            return NivelSemaforo.ACEPTABLE
        return NivelSemaforo.POR_MEJORAR

    # ------------------------------------------------------------------
    # Sub-indicadores (sección 7.1 y 7.3)
    # ------------------------------------------------------------------

    def _calcular_cumplimiento(
        self,
        actividades_jornada: list[Actividad],
        sesiones_dia: list[SesionTiempo],
        jornada: Jornada,
    ) -> float | None:
        numerador = 0.0
        denominador = 0.0

        for act in actividades_jornada:
            if act.es_revision:
                continue  # Las revisiones no cuentan como nuevo cumplimiento
            if act.estado in (EstadoActividad.RECHAZADA.value, EstadoActividad.ELIMINADA.value):
                continue

            if act.tipo == TipoActividad.PLANEADA.value:
                if act.estado == EstadoActividad.COMPLETADA.value:
                    numerador += 1.0
                    denominador += 1.0
                elif act.estado == EstadoActividad.REASIGNADA.value:
                    # Si fue reasignada a otra persona, no penaliza el cumplimiento
                    continue
                elif self._fue_interrumpida_o_arrastrada_con_motivo(act):
                    avance = max(0, min(100, act.avance_pct or 0)) / 100.0
                    numerador += avance
                    denominador += 1.0
                else:
                    denominador += 1.0

            elif act.tipo == TipoActividad.EXTRA.value:
                # Extras de jefe/doctoras o aprobadas por el ingeniero cuentan como cumplimiento
                es_valida = (
                    act.prioridad == Prioridad.MAXIMA.value
                    or act.aprobacion_estado == EstadoAprobacion.APROBADA.value
                )
                if not es_valida:
                    continue
                if act.estado == EstadoActividad.COMPLETADA.value:
                    numerador += 1.0
                    denominador += 1.0
                elif self._fue_interrumpida_o_arrastrada_con_motivo(act):
                    avance = max(0, min(100, act.avance_pct or 0)) / 100.0
                    numerador += avance
                    denominador += 1.0

        # Actividades arrastradas de jornadas anteriores que se finalizaron hoy:
        # completan el porcentaje restante que les faltaba (sección 7.3).
        ids_jornada = {a.id for a in actividades_jornada}
        ids_trabajadas_hoy = {s.actividad_id for s in sesiones_dia} - ids_jornada
        for act_id in ids_trabajadas_hoy:
            act_previa = self.s.get(Actividad, act_id)
            if (
                act_previa
                and not act_previa.es_revision
                and act_previa.estado == EstadoActividad.COMPLETADA.value
                and act_previa.finalizada_en
                and act_previa.finalizada_en.date() == jornada.fecha
            ):
                # Aporta la fracción finalizada hoy
                numerador += 1.0
                denominador += 1.0

        if denominador == 0:
            return None
        return min(100.0, (numerador / denominador) * 100.0)

    def _fue_interrumpida_o_arrastrada_con_motivo(self, act: Actividad) -> bool:
        if act.estado == EstadoActividad.ARRASTRADA.value:
            return True
        if act.estado == EstadoActividad.PAUSADA.value:
            return any(
                p.tipo in (TipoPausa.PRIORIDAD.value, TipoPausa.FIN_JORNADA.value)
                for p in act.pausas
            )
        return False

    def _calcular_eficiencia(
        self,
        actividades_jornada: list[Actividad],
        sesiones_dia: list[SesionTiempo],
    ) -> float | None:
        eficiencias: list[float] = []

        # Agrupar segundos reales por actividad
        seg_por_act: dict[int, int] = {}
        for ses in sesiones_dia:
            seg_por_act[ses.actividad_id] = seg_por_act.get(ses.actividad_id, 0) + ses.duracion_seg

        for act in actividades_jornada:
            if act.es_revision:
                continue
            if act.estado != EstadoActividad.COMPLETADA.value:
                continue
            real_seg = seg_por_act.get(act.id, 0) or sum(s.duracion_seg for s in act.sesiones)
            if real_seg <= 0:
                continue

            estimado_seg = self._estimado_o_promedio_historico_seg(act)
            if estimado_seg is None or estimado_seg <= 0:
                continue

            ef = min(100.0, (estimado_seg / real_seg) * 100.0)
            eficiencias.append(ef)

        if not eficiencias:
            return None
        return sum(eficiencias) / len(eficiencias)

    def _estimado_o_promedio_historico_seg(self, actividad: Actividad) -> float | None:
        if actividad.tiempo_estimado_min and actividad.tiempo_estimado_min > 0:
            return float(actividad.tiempo_estimado_min * 60)
        if actividad.categoria_id is None:
            return None

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
        return float(prom_seg) if prom_seg and prom_seg > 0 else None

    def _calcular_foco(
        self,
        tiempo_efectivo_seg: int,
        duracion_jornada_seg: int,
        tiempo_pausas_externas_seg: int,
    ) -> float:
        # Los tiempos en pausa con tipo "causa externa" no penalizan el Foco (sección 7.3)
        base_disponible = max(1, duracion_jornada_seg - tiempo_pausas_externas_seg)
        return min(100.0, (tiempo_efectivo_seg / base_disponible) * 100.0)

    def _calcular_datos_referencia(
        self, actividades_jornada: list[Actividad]
    ) -> list[DatoReferenciaCategoria]:
        """Genera frases de referencia sin evaluar, ej. 'Hoy hiciste 12 flyers; tu promedio es 25 min'."""
        completadas_por_cat: dict[int, int] = {}
        for act in actividades_jornada:
            if (
                not act.es_revision
                and act.estado == EstadoActividad.COMPLETADA.value
                and act.categoria_id is not None
            ):
                completadas_por_cat[act.categoria_id] = (
                    completadas_por_cat.get(act.categoria_id, 0) + 1
                )

        referencias: list[DatoReferenciaCategoria] = []
        for cat_id, cant_hoy in completadas_por_cat.items():
            cat = self.s.get(Categoria, cat_id)
            if cat is None:
                continue
            sub = (
                select(
                    Actividad.id,
                    func.sum(SesionTiempo.duracion_seg).label("total_seg"),
                )
                .join(SesionTiempo, SesionTiempo.actividad_id == Actividad.id)
                .where(
                    Actividad.categoria_id == cat_id,
                    Actividad.estado == EstadoActividad.COMPLETADA.value,
                    Actividad.es_revision.is_(False),
                )
                .group_by(Actividad.id)
            ).subquery()
            prom_seg = self.s.scalar(select(func.avg(sub.c.total_seg))) or 0
            prom_min = max(1, int(round(float(prom_seg) / 60))) if prom_seg else 0
            nombre_cat = cat.nombre.lower()
            mensaje = (
                f"Hoy completaste {cant_hoy} de «{cat.nombre}»; "
                f"tu promedio es {prom_min} min por {nombre_cat}."
            )
            referencias.append(
                DatoReferenciaCategoria(
                    categoria_nombre=cat.nombre,
                    cantidad_hoy=cant_hoy,
                    promedio_historico_min=prom_min,
                    mensaje=mensaje,
                )
            )
        return referencias
