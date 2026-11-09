"""Pruebas de generación de reportes PDF: general del día, día no laboral,
específico y semanal/mensual (Fase 7 — RF-08).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select

from data.enums import CanalSolicitud, MotivoRevision, TipoRevision
from data.models import Solicitante
from data.repositorios.catalogos import RepoCategorias
from services.actividades import ServicioActividades
from services.cierre_jornada import ServicioCierreJornada
from services.cronometro import ServicioCronometro
from services.historial import FiltrosHistorial
from services.reportes_pdf import ServicioReportesPDF


def _es_pdf_valido(ruta) -> bool:
    return ruta.is_file() and ruta.stat().st_size > 500 and ruta.read_bytes()[:4] == b"%PDF"


def test_generar_los_cuatro_tipos_de_pdf_y_en_cierre(s, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    srv_pdf = ServicioReportesPDF(s)
    cat = RepoCategorias(s).obtener_o_crear("Flyers")
    jefe = s.scalar(select(Solicitante).where(Solicitante.nombre == "Ing. Luis Eduardo"))

    # 1. Jornada laboral con planeada, extra y revisión
    plan = srv_act.crear_planeada(
        "Flyer vacante",
        categoria_id=cat.id,
        tiempo_estimado_min=30,
        momento=datetime(2026, 11, 9, 8, 0),
    )
    cron.iniciar(plan, momento=datetime(2026, 11, 9, 8, 0))
    cron.finalizar(plan, momento=datetime(2026, 11, 9, 8, 25))

    extra = srv_act.crear_extra(
        "Banner urgente",
        jefe,
        motivo_urgencia="Cliente",
        canal_solicitud=CanalSolicitud.WHATSAPP,
        descripcion="Banner web",
        momento=datetime(2026, 11, 9, 9, 0),
    )
    cron.iniciar(extra, momento=datetime(2026, 11, 9, 9, 0))
    cron.finalizar(extra, momento=datetime(2026, 11, 9, 9, 30))

    rev = srv_act.crear_revision(
        extra,
        solicitante=jefe,
        tipo_revision=TipoRevision.MINIMO,
        que_cambiar="Logo más grande",
        motivo=MotivoRevision.CAMBIO_CRITERIO,
        momento=datetime(2026, 11, 9, 10, 0),
    )
    cron.iniciar(rev, momento=datetime(2026, 11, 9, 10, 0))
    cron.finalizar(rev, momento=datetime(2026, 11, 9, 10, 10))

    # Cierre de jornada genera automáticamente el PDF general del día
    res_cierre = ServicioCierreJornada(s).cerrar_jornada(
        plan.jornada, momento=datetime(2026, 11, 9, 16, 45)
    )
    assert res_cierre.ruta_pdf is not None
    assert _es_pdf_valido(res_cierre.ruta_pdf)

    # 2. PDF de día no laboral (domingo)
    dom = srv_act.crear_no_planeada(
        "Apoyo domingo",
        momento=datetime(2026, 11, 15, 10, 0),
    )
    cron.iniciar(dom, momento=datetime(2026, 11, 15, 10, 0))
    cron.finalizar(dom, momento=datetime(2026, 11, 15, 10, 30))
    pdf_dom = srv_pdf.generar_pdf_jornada(dom.jornada)
    assert "no_laboral" in pdf_dom.name
    assert _es_pdf_valido(pdf_dom)

    # 3. PDF específico por solicitante
    pdf_esp = srv_pdf.generar_pdf_especifico(
        FiltrosHistorial(
            fecha_desde=date(2026, 11, 9),
            fecha_hasta=date(2026, 11, 15),
            solicitante_id=jefe.id,
        ),
        titulo_filtro="Actividades de Ing. Luis Eduardo",
    )
    assert _es_pdf_valido(pdf_esp)

    # 4. PDF semanal / mensual
    pdf_sem = srv_pdf.generar_pdf_periodo(
        date(2026, 11, 9), date(2026, 11, 15), etiqueta_periodo="Semanal"
    )
    assert _es_pdf_valido(pdf_sem)
