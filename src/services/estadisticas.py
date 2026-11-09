"""Servicio de estadísticas e indicadores analíticos (RF-11).

Calcula en un rango de fechas:
1. Productividad por día, por semana y por mes (línea de tendencia).
2. Tiempo total invertido por categoría.
3. Tiempo estimado vs. tiempo real promedio por categoría / tipo de actividad.
4. Tiempo invertido por solicitante (cuánto trabajo piden el jefe, las doctoras y otros).
5. Número de revisiones y desglose por motivos (error propio, cambio de criterio,
   información nueva), sin alertas punitivas (RF-03b).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.enums import EstadoActividad
from data.models import Actividad, Categoria, Jornada, SesionTiempo, Solicitante
from services.productividad import ServicioProductividad


@dataclass(frozen=True)
class PuntoTendencia:
    etiqueta: str
    fecha_inicio: date
    productividad_pct: float
    tiempo_efectivo_seg: int


@dataclass(frozen=True)
class TiempoPorCategoria:
    categoria_nombre: str
    color: str
    segundos: int
    cantidad_actividades: int


@dataclass(frozen=True)
class ComparativoEstimadoReal:
    grupo: str
    cantidad: int
    estimado_promedio_min: float
    real_promedio_min: float


@dataclass(frozen=True)
class TiempoPorSolicitante:
    solicitante_nombre: str
    tipo_solicitante: str
    segundos: int
    cantidad_solicitudes: int


@dataclass(frozen=True)
class ResumenRevisiones:
    total_revisiones: int
    segundos_totales: int
    por_motivo: dict[str, int]
    por_tipo: dict[str, int]


@dataclass(frozen=True)
class ReporteEstadisticas:
    fecha_desde: date
    fecha_hasta: date
    tendencia_diaria: list[PuntoTendencia]
    tendencia_semanal: list[PuntoTendencia]
    tendencia_mensual: list[PuntoTendencia]
    por_categoria: list[TiempoPorCategoria]
    estimado_vs_real: list[ComparativoEstimadoReal]
    por_solicitante: list[TiempoPorSolicitante]
    revisiones: ResumenRevisiones


class ServicioEstadisticas:
    """Agrega y resume métricas históricas para la pantalla de Estadísticas y PDFs."""

    def __init__(self, s: Session) -> None:
        self.s = s
        self.srv_prod = ServicioProductividad(s)

    def calcular(self, fecha_desde: date, fecha_hasta: date) -> ReporteEstadisticas:
        tend_dia = self._tendencia_diaria(fecha_desde, fecha_hasta)
        tend_sem = self._agrupar_semanal(tend_dia)
        tend_mes = self._agrupar_mensual(tend_dia)

        por_cat = self._tiempo_por_categoria(fecha_desde, fecha_hasta)
        est_real = self._estimado_vs_real(fecha_desde, fecha_hasta)
        por_sol = self._tiempo_por_solicitante(fecha_desde, fecha_hasta)
        revs = self._resumen_revisiones(fecha_desde, fecha_hasta)

        return ReporteEstadisticas(
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            tendencia_diaria=tend_dia,
            tendencia_semanal=tend_sem,
            tendencia_mensual=tend_mes,
            por_categoria=por_cat,
            estimado_vs_real=est_real,
            por_solicitante=por_sol,
            revisiones=revs,
        )

    def _tendencia_diaria(self, desde: date, hasta: date) -> list[PuntoTendencia]:
        jornadas = list(
            self.s.scalars(
                select(Jornada)
                .where(Jornada.fecha >= desde, Jornada.fecha <= hasta)
                .order_by(Jornada.fecha)
            )
        )
        puntos: list[PuntoTendencia] = []
        for j in jornadas:
            res = self.srv_prod.calcular_jornada(j)
            if res.es_laboral and res.productividad_pct is not None:
                puntos.append(
                    PuntoTendencia(
                        etiqueta=j.fecha.strftime("%d/%m"),
                        fecha_inicio=j.fecha,
                        productividad_pct=res.productividad_pct,
                        tiempo_efectivo_seg=res.tiempo_efectivo_seg,
                    )
                )
        return puntos

    @staticmethod
    def _agrupar_semanal(puntos: list[PuntoTendencia]) -> list[PuntoTendencia]:
        grupos: dict[tuple[int, int], list[PuntoTendencia]] = {}
        for p in puntos:
            iso = p.fecha_inicio.isocalendar()
            grupos.setdefault((iso.year, iso.week), []).append(p)

        salida: list[PuntoTendencia] = []
        for (anio, sem), items in sorted(grupos.items()):
            prom = round(sum(x.productividad_pct for x in items) / len(items), 1)
            seg = sum(x.tiempo_efectivo_seg for x in items)
            salida.append(
                PuntoTendencia(
                    etiqueta=f"Sem {sem}/{anio}",
                    fecha_inicio=items[0].fecha_inicio,
                    productividad_pct=prom,
                    tiempo_efectivo_seg=seg,
                )
            )
        return salida

    @staticmethod
    def _agrupar_mensual(puntos: list[PuntoTendencia]) -> list[PuntoTendencia]:
        grupos: dict[tuple[int, int], list[PuntoTendencia]] = {}
        for p in puntos:
            grupos.setdefault((p.fecha_inicio.year, p.fecha_inicio.month), []).append(p)

        salida: list[PuntoTendencia] = []
        for (anio, mes), items in sorted(grupos.items()):
            prom = round(sum(x.productividad_pct for x in items) / len(items), 1)
            seg = sum(x.tiempo_efectivo_seg for x in items)
            salida.append(
                PuntoTendencia(
                    etiqueta=f"{mes:02d}/{anio}",
                    fecha_inicio=items[0].fecha_inicio,
                    productividad_pct=prom,
                    tiempo_efectivo_seg=seg,
                )
            )
        return salida

    def _sesiones_en_rango(
        self, desde: date, hasta: date
    ) -> list[tuple[SesionTiempo, Actividad]]:
        ini = datetime.combine(desde, datetime.min.time())
        fin = datetime.combine(hasta, datetime.max.time())
        filas = self.s.execute(
            select(SesionTiempo, Actividad)
            .join(Actividad, SesionTiempo.actividad_id == Actividad.id)
            .where(
                SesionTiempo.inicio >= ini,
                SesionTiempo.inicio <= fin,
                SesionTiempo.fin.is_not(None),
                Actividad.estado != EstadoActividad.ELIMINADA.value,
            )
        ).all()
        return [(ses, act) for ses, act in filas]

    def _tiempo_por_categoria(self, desde: date, hasta: date) -> list[TiempoPorCategoria]:
        pares = self._sesiones_en_rango(desde, hasta)
        seg_por_cat: dict[int | None, int] = {}
        acts_por_cat: dict[int | None, set[int]] = {}

        for ses, act in pares:
            seg_por_cat[act.categoria_id] = seg_por_cat.get(act.categoria_id, 0) + ses.duracion_seg
            acts_por_cat.setdefault(act.categoria_id, set()).add(act.id)

        resultado: list[TiempoPorCategoria] = []
        for cat_id, seg in seg_por_cat.items():
            if cat_id is None:
                nombre = "Sin categoría"
                color = "#6B7280"
            else:
                cat = self.s.get(Categoria, cat_id)
                nombre = cat.nombre if cat else "Sin categoría"
                color = cat.color if cat else "#6B7280"
            resultado.append(
                TiempoPorCategoria(
                    categoria_nombre=nombre,
                    color=color,
                    segundos=seg,
                    cantidad_actividades=len(acts_por_cat.get(cat_id, set())),
                )
            )
        return sorted(resultado, key=lambda x: x.segundos, reverse=True)

    def _estimado_vs_real(self, desde: date, hasta: date) -> list[ComparativoEstimadoReal]:
        actividades = list(
            self.s.scalars(
                select(Actividad)
                .join(Jornada, Actividad.jornada_id == Jornada.id)
                .where(
                    Jornada.fecha >= desde,
                    Jornada.fecha <= hasta,
                    Actividad.es_revision.is_(False),
                    Actividad.estado == EstadoActividad.COMPLETADA.value,
                    Actividad.tiempo_estimado_min.is_not(None),
                )
            )
        )
        grupos: dict[str, list[tuple[int, float]]] = {}
        for act in actividades:
            sesiones = list(
                self.s.scalars(select(SesionTiempo).where(SesionTiempo.actividad_id == act.id))
            )
            real_min = sum(s.duracion_seg for s in sesiones) / 60.0
            if real_min <= 0 or not act.tiempo_estimado_min:
                continue
            etiqueta = act.categoria.nombre if act.categoria else f"Tipo: {act.tipo}"
            grupos.setdefault(etiqueta, []).append((act.tiempo_estimado_min, real_min))

        salida: list[ComparativoEstimadoReal] = []
        for grupo, items in sorted(grupos.items()):
            est_prom = round(sum(e for e, _ in items) / len(items), 1)
            real_prom = round(sum(r for _, r in items) / len(items), 1)
            salida.append(
                ComparativoEstimadoReal(
                    grupo=grupo,
                    cantidad=len(items),
                    estimado_promedio_min=est_prom,
                    real_promedio_min=real_prom,
                )
            )
        return salida

    def _tiempo_por_solicitante(self, desde: date, hasta: date) -> list[TiempoPorSolicitante]:
        pares = self._sesiones_en_rango(desde, hasta)
        seg_por_sol: dict[int | None, int] = {}
        acts_por_sol: dict[int | None, set[int]] = {}

        for ses, act in pares:
            sol_id = act.solicitante_id or act.revision_solicitante_id
            seg_por_sol[sol_id] = seg_por_sol.get(sol_id, 0) + ses.duracion_seg
            acts_por_sol.setdefault(sol_id, set()).add(act.id)

        salida: list[TiempoPorSolicitante] = []
        for sol_id, seg in seg_por_sol.items():
            if sol_id is None:
                nombre = "Iniciativa propia / Plan"
                tipo = "propia"
            else:
                sol = self.s.get(Solicitante, sol_id)
                nombre = sol.nombre if sol else "Solicitante"
                tipo = sol.tipo if sol else "tercero"
            salida.append(
                TiempoPorSolicitante(
                    solicitante_nombre=nombre,
                    tipo_solicitante=tipo,
                    segundos=seg,
                    cantidad_solicitudes=len(acts_por_sol.get(sol_id, set())),
                )
            )
        return sorted(salida, key=lambda x: x.segundos, reverse=True)

    def _resumen_revisiones(self, desde: date, hasta: date) -> ResumenRevisiones:
        revs = list(
            self.s.scalars(
                select(Actividad)
                .join(Jornada, Actividad.jornada_id == Jornada.id)
                .where(
                    Jornada.fecha >= desde,
                    Jornada.fecha <= hasta,
                    Actividad.es_revision.is_(True),
                    Actividad.estado != EstadoActividad.ELIMINADA.value,
                )
            )
        )
        por_motivo: dict[str, int] = {}
        por_tipo: dict[str, int] = {}
        seg_total = 0

        for r in revs:
            mot = r.revision_motivo or "sin_especificar"
            tip = r.revision_tipo or "sin_especificar"
            por_motivo[mot] = por_motivo.get(mot, 0) + 1
            por_tipo[tip] = por_tipo.get(tip, 0) + 1
            sesiones = list(
                self.s.scalars(select(SesionTiempo).where(SesionTiempo.actividad_id == r.id))
            )
            seg_total += sum(s.duracion_seg for s in sesiones)

        return ResumenRevisiones(
            total_revisiones=len(revs),
            segundos_totales=seg_total,
            por_motivo=por_motivo,
            por_tipo=por_tipo,
        )
