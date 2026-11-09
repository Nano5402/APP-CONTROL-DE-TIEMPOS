"""Pruebas de la fórmula de productividad, reglas especiales, semáforo y referencias (sección 7)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from data.enums import (
    CanalSolicitud,
    MotivoRevision,
    TipoPausa,
    TipoRevision,
)
from data.models import Solicitante
from data.repositorios.catalogos import RepoCategorias
from services.actividades import ServicioActividades
from services.cronometro import ServicioCronometro
from services.productividad import NivelSemaforo, ServicioProductividad


def test_formula_productividad_y_semaforo(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    srv_prod = ServicioProductividad(s)

    # Lunes: duración jornada = 7 h 45 min = 27.900 s (465 min)
    # Planeamos 2 actividades, cada una con estimado 120 min
    a1 = srv_act.crear_planeada(
        "Diseño catálogo",
        tiempo_estimado_min=120,
        momento=datetime(2026, 11, 9, 7, 30),
    )
    a2 = srv_act.crear_planeada(
        "Animación logo",
        tiempo_estimado_min=120,
        momento=datetime(2026, 11, 9, 7, 30),
    )

    # Trabaja a1 en 120 min exactos (eficiencia 100 %)
    cron.iniciar(a1, momento=datetime(2026, 11, 9, 7, 30))
    cron.finalizar(a1, momento=datetime(2026, 11, 9, 9, 30))

    # Trabaja a2 en 150 min (eficiencia = 120/150 = 80 %)
    cron.iniciar(a2, momento=datetime(2026, 11, 9, 9, 30))
    cron.finalizar(a2, momento=datetime(2026, 11, 9, 12, 0))

    # Cumplimiento = 2/2 = 100 %
    # Eficiencia promedio = (100 + 80) / 2 = 90 %
    # Foco = 270 min / 465 min = 58.06 %
    res = srv_prod.calcular_jornada(a1.jornada)
    assert res.cumplimiento_pct == 100.0
    assert res.eficiencia_pct == 90.0
    assert res.foco_pct == pytest.approx(58.1, abs=0.1)

    # Productividad = 0.40*100 + 0.30*90 + 0.30*58.06 = 40 + 27 + 17.42 = 84.4 % → Aceptable (🟡)
    assert res.productividad_pct == pytest.approx(84.4, abs=0.1)
    assert res.semaforo == NivelSemaforo.ACEPTABLE
    assert res.semaforo.emoji() == "🟡"


def test_reglas_especiales_extras_arrastradas_causa_externa_y_fuera_horario(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    srv_prod = ServicioProductividad(s)
    cat = RepoCategorias(s).obtener_o_crear("Flyers")
    jefe = s.scalar(select(Solicitante).where(Solicitante.nombre == "Ing. Luis Eduardo"))

    # 1 actividad planeada que queda arrastrada al 60 % porque llegó una urgencia del jefe
    plan = srv_act.crear_planeada(
        "Flyer 1",
        categoria_id=cat.id,
        tiempo_estimado_min=60,
        momento=datetime(2026, 11, 9, 8, 0),
    )
    cron.iniciar(plan, momento=datetime(2026, 11, 9, 8, 0))
    cron.pausar(
        plan,
        tipo=TipoPausa.FIN_JORNADA,
        motivo="Desplazada por urgencia de gerencia",
        avance_pct=60,
        momento=datetime(2026, 11, 9, 9, 0),
    )

    # Extra del jefe completada (cuenta como cumplimiento)
    extra = srv_act.crear_extra(
        "Presentación urgente",
        jefe,
        motivo_urgencia="Junta directiva",
        canal_solicitud=CanalSolicitud.WHATSAPP,
        descripcion="Diapositivas",
        tiempo_estimado_min=60,
        momento=datetime(2026, 11, 9, 9, 0),
    )
    cron.iniciar(extra, momento=datetime(2026, 11, 9, 9, 0))
    cron.finalizar(extra, momento=datetime(2026, 11, 9, 10, 0))

    # Pausa por causa externa de 60 min (internet caído): no penaliza el Foco
    pausa_ext = cron.pausar(
        None,
        tipo=TipoPausa.EXTERNA,
        motivo="Falla de internet en la oficina",
        momento=datetime(2026, 11, 9, 10, 0),
    )
    pausa_ext.fin = datetime(2026, 11, 9, 11, 0)

    # Revisión de la extra y trabajo fuera de horario (5:00 pm a 5:30 pm)
    rev = srv_act.crear_revision(
        extra,
        solicitante=jefe,
        tipo_revision=TipoRevision.MINIMO,
        que_cambiar="Logo",
        motivo=MotivoRevision.CAMBIO_CRITERIO,
        momento=datetime(2026, 11, 9, 11, 0),
    )
    cron.iniciar(rev, momento=datetime(2026, 11, 9, 11, 0))
    cron.finalizar(rev, momento=datetime(2026, 11, 9, 11, 30))

    no_plan_noche = srv_act.crear_no_planeada(
        "Adelanto desde casa",
        momento=datetime(2026, 11, 9, 17, 0),
    )
    cron.iniciar(no_plan_noche, momento=datetime(2026, 11, 9, 17, 0))
    cron.finalizar(no_plan_noche, momento=datetime(2026, 11, 9, 17, 30))

    res = srv_prod.calcular_jornada(plan.jornada)

    # Cumplimiento: (0.60 de planeada arrastrada + 1.0 de extra jefe) / 2 = 80 %
    # (la revisión y la no planeada no alteran el cumplimiento)
    assert res.cumplimiento_pct == pytest.approx(80.0)
    # Tiempo efectivo en horario: 60 min (plan) + 60 min (extra) + 30 min (revisión) = 150 min (9000 s)
    assert res.tiempo_efectivo_seg == 9000
    # Tiempo fuera de horario: 30 min (1800 s), reportado aparte
    assert res.tiempo_fuera_horario_seg == 1800
    # Pausas externas descontadas del denominador de Foco: 3600 s
    assert res.tiempo_pausas_externas_seg == 3600


def test_dia_no_laboral_no_tiene_porcentaje_y_datos_referencia(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    srv_prod = ServicioProductividad(s)
    cat = RepoCategorias(s).obtener_o_crear("Flyers")

    # Domingo (día sin horario configurado)
    dom = srv_act.crear_no_planeada(
        "Flyer urgente domingo",
        categoria_id=cat.id,
        momento=datetime(2026, 11, 15, 10, 0),
    )
    cron.iniciar(dom, momento=datetime(2026, 11, 15, 10, 0))
    cron.finalizar(dom, momento=datetime(2026, 11, 15, 10, 25))

    res = srv_prod.calcular_jornada(dom.jornada)
    assert res.es_laboral is False
    assert res.productividad_pct is None
    assert res.semaforo == NivelSemaforo.NO_APLICA
    assert res.tiempo_fuera_horario_seg == 25 * 60
    assert len(res.datos_referencia) == 1
    assert "25 min" in res.datos_referencia[0].mensaje
