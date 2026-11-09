"""Pruebas de historial, filtros, trazabilidad de ediciones y estadísticas (Fase 6)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select

from data.enums import (
    CanalSolicitud,
    MotivoRevision,
    TipoActividad,
    TipoRevision,
)
from data.models import Solicitante
from data.repositorios.catalogos import RepoCategorias
from services.actividades import ServicioActividades
from services.cronometro import ServicioCronometro
from services.estadisticas import ServicioEstadisticas
from services.historial import (
    FiltrosHistorial,
    ServicioHistorial,
    rango_mes,
    rango_semana,
)


def test_rangos_semana_y_mes():
    ini_s, fin_s = rango_semana(date(2026, 11, 11))  # miércoles
    assert ini_s == date(2026, 11, 9)
    assert fin_s == date(2026, 11, 15)

    ini_m, fin_m = rango_mes(date(2026, 11, 11))
    assert ini_m == date(2026, 11, 1)
    assert fin_m == date(2026, 11, 30)


def test_historial_filtros_detalle_y_estadisticas_completas(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    srv_hist = ServicioHistorial(s)
    srv_est = ServicioEstadisticas(s)

    cat_flyers = RepoCategorias(s).obtener_o_crear("Flyers")
    cat_videos = RepoCategorias(s).obtener_o_crear("Videos")
    jefe = s.scalar(select(Solicitante).where(Solicitante.nombre == "Ing. Luis Eduardo"))

    # Día 1 (lunes 9 nov): planeada de Flyers (estimado 30 min, real 25 min)
    a1 = srv_act.crear_planeada(
        "Flyer 1",
        categoria_id=cat_flyers.id,
        tiempo_estimado_min=30,
        momento=datetime(2026, 11, 9, 8, 0),
    )
    cron.iniciar(a1, momento=datetime(2026, 11, 9, 8, 0))
    cron.finalizar(a1, momento=datetime(2026, 11, 9, 8, 25))

    # Corrección sobre a1 para verificar que aparece en el detalle del historial
    srv_act.corregir_actividad(a1, motivo="Ajustar título", nombre="Flyer vacante 1")

    # Día 2 (martes 10 nov): extra de Videos pedida por el jefe + 1 revisión
    extra = srv_act.crear_extra(
        "Video institucional",
        jefe,
        motivo_urgencia="Presentación",
        canal_solicitud=CanalSolicitud.WHATSAPP,
        descripcion="Video 1 min",
        categoria_id=cat_videos.id,
        tiempo_estimado_min=60,
        momento=datetime(2026, 11, 10, 9, 0),
    )
    cron.iniciar(extra, momento=datetime(2026, 11, 10, 9, 0))
    cron.finalizar(extra, momento=datetime(2026, 11, 10, 10, 10))  # 70 min

    rev = srv_act.crear_revision(
        extra,
        solicitante=jefe,
        tipo_revision=TipoRevision.MINIMO,
        que_cambiar="Subtítulo final",
        motivo=MotivoRevision.INFORMACION_NUEVA,
        momento=datetime(2026, 11, 10, 11, 0),
    )
    cron.iniciar(rev, momento=datetime(2026, 11, 10, 11, 0))
    cron.finalizar(rev, momento=datetime(2026, 11, 10, 11, 15))  # 15 min

    # 1. Filtros de historial
    todas = srv_hist.buscar_actividades(
        FiltrosHistorial(fecha_desde=date(2026, 11, 9), fecha_hasta=date(2026, 11, 10))
    )
    assert len(todas) == 3

    solo_extras = srv_hist.buscar_actividades(
        FiltrosHistorial(
            fecha_desde=date(2026, 11, 9),
            fecha_hasta=date(2026, 11, 10),
            tipo=TipoActividad.EXTRA.value,
            solicitante_id=jefe.id,
        )
    )
    assert {x.id for x in solo_extras} == {extra.id, rev.id}

    # 2. Detalle de actividad con trazabilidad de ediciones y revisiones
    det_a1 = srv_hist.detalle_actividad(a1.id)
    assert det_a1 is not None
    assert len(det_a1.ediciones) == 1
    assert det_a1.ediciones[0].motivo == "Ajustar título"

    det_extra = srv_hist.detalle_actividad(extra.id)
    assert det_extra is not None
    assert det_extra.desglose.cantidad_revisiones == 1
    assert det_extra.desglose.segundos_total == (70 + 15) * 60

    # 3. Estadísticas completas del rango
    rep = srv_est.calcular(date(2026, 11, 9), date(2026, 11, 10))
    assert len(rep.tendencia_diaria) == 2
    assert len(rep.tendencia_semanal) == 1
    assert len(rep.tendencia_mensual) == 1

    por_cat = {c.categoria_nombre: c.segundos for c in rep.por_categoria}
    assert por_cat["Flyers"] == 25 * 60
    assert por_cat["Videos"] == 85 * 60

    por_sol = {s.solicitante_nombre: s.segundos for s in rep.por_solicitante}
    assert por_sol["Ing. Luis Eduardo"] == 85 * 60
    assert por_sol["Iniciativa propia / Plan"] == 25 * 60

    assert rep.revisiones.total_revisiones == 1
    assert rep.revisiones.por_motivo[MotivoRevision.INFORMACION_NUEVA.value] == 1
