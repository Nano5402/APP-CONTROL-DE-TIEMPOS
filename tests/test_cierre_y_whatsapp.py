"""Pruebas del asistente de cierre de jornada y textos para WhatsApp (RF-01, RF-06)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from data.enums import EstadoActividad, EstadoJornada
from data.models import Usuario
from services.actividades import ServicioActividades
from services.cierre_jornada import (
    AccionCierreActividad,
    ActividadesAbiertasAlCierreError,
    DecisionActividadCierre,
    ServicioCierreJornada,
)
from services.cronometro import ServicioCronometro
from services.whatsapp import ServicioWhatsApp


def test_texto_plan_y_cierre_completo_de_jornada(s):
    usr = s.scalar(select(Usuario).limit(1))
    usr.nombre = "Andrés Calvete"

    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    srv_wa = ServicioWhatsApp(s)
    srv_cierre = ServicioCierreJornada(s)

    a1 = srv_act.crear_planeada(
        "Flyer vacantes",
        tiempo_estimado_min=30,
        momento=datetime(2026, 11, 9, 7, 30),
    )
    a2 = srv_act.crear_planeada(
        "Animación cumpleaños SIAM",
        tiempo_estimado_min=60,
        momento=datetime(2026, 11, 9, 7, 30),
    )

    plan_txt = srv_wa.generar_texto_plan(a1.jornada)
    assert "Andrés Calvete" in plan_txt
    assert "1. Flyer vacantes (30 min est.)" in plan_txt
    assert "2. Animación cumpleaños SIAM (60 min est.)" in plan_txt

    # Trabaja a1 y la completa; empieza a2 pero llega la hora de salida
    cron.iniciar(a1, momento=datetime(2026, 11, 9, 8, 0))
    cron.finalizar(a1, momento=datetime(2026, 11, 9, 8, 30))
    cron.iniciar(a2, momento=datetime(2026, 11, 9, 16, 0))

    # Si intenta cerrar sin resolver a2, lanza ActividadesAbiertasAlCierreError
    with pytest.raises(ActividadesAbiertasAlCierreError):
        srv_cierre.cerrar_jornada(a1.jornada, momento=datetime(2026, 11, 9, 16, 45))

    # Usa el asistente de cierre para arrastrar a2 con 70 % de avance
    res_cierre = srv_cierre.cerrar_jornada(
        a1.jornada,
        decisiones=[
            DecisionActividadCierre(
                actividad_id=a2.id,
                accion=AccionCierreActividad.ARRASTRAR,
                motivo="Falta exportar video final",
                avance_pct=70,
            )
        ],
        momento=datetime(2026, 11, 9, 16, 45),
    )

    assert a1.jornada.estado == EstadoJornada.CERRADA.value
    assert a1.jornada.productividad is not None
    assert a2.estado == EstadoActividad.ARRASTRADA.value
    assert a2.avance_pct == 70
    assert res_cierre.copia_seguridad is not None
    assert Path(res_cierre.copia_seguridad.ruta).exists()
    assert "Flyer vacantes" in res_cierre.texto_resumen_whatsapp
    assert "Animación cumpleaños SIAM (avance: 70%)" in res_cierre.texto_resumen_whatsapp
