"""Pruebas del rediseño gráfico del PDF, pausas reales y bruto en jornada."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication

from data.enums import MotivoRevision, TipoPausa, TipoRevision
from data.models import Pausa, SesionTiempo, Solicitante
from data.repositorios.catalogos import RepoCategorias
from data.repositorios.jornadas import RepoJornadas
from reports.generador_pdf import LienzoPDF
from services.actividades import ServicioActividades
from services.cronometro import ServicioCronometro
from services.historial import FiltrosHistorial
from services.productividad import ServicioProductividad
from services.reportes_pdf import ServicioReportesPDF
from ui.pantallas.pantalla_hoy import PantallaHoy


def _espiar_textos_lienzo(monkeypatch) -> list[str]:
    """Captura todas las cadenas dibujadas en textos, pills y pie sobre LienzoPDF."""
    capturados: list[str] = []
    orig_texto = LienzoPDF.dibujar_texto
    orig_pill = LienzoPDF.dibujar_pill
    orig_cromo = LienzoPDF._dibujar_cromo_pagina

    def spy_texto(self, rect, texto, *args, **kwargs):
        capturados.append(str(texto))
        return orig_texto(self, rect, texto, *args, **kwargs)

    def spy_pill(self, x, y, texto, *args, **kwargs):
        capturados.append(str(texto))
        return orig_pill(self, x, y, texto, *args, **kwargs)

    def spy_cromo(self, p, num_pag, total_pags):
        capturados.append(f"Página {num_pag} de {total_pags}")
        return orig_cromo(self, p, num_pag, total_pags)

    monkeypatch.setattr(LienzoPDF, "dibujar_texto", spy_texto)
    monkeypatch.setattr(LienzoPDF, "dibujar_pill", spy_pill)
    monkeypatch.setattr(LienzoPDF, "_dibujar_cromo_pagina", spy_cromo)
    return capturados


def _verificar_pdf_generado(ruta: Path) -> int:
    assert ruta.exists()
    contenido = ruta.read_bytes()
    assert contenido.startswith(b"%PDF")
    assert len(contenido) > 2000
    doc = QPdfDocument()
    doc.load(str(ruta))
    assert doc.pageCount() >= 1
    return doc.pageCount()


def test_pausa_almuerzo_no_infla_pausas_y_calcula_bruto(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    srv_prod = ServicioProductividad(s)

    lunes = date(2026, 11, 9)
    act = srv_act.crear_planeada(
        "Campaña web", tiempo_estimado_min=120, momento=datetime(2026, 11, 9, 8, 0)
    )
    cron.iniciar(act, momento=datetime(2026, 11, 9, 8, 0))
    cron.finalizar(act, momento=datetime(2026, 11, 9, 10, 0))  # 2h efectivas

    # Pausa personal breve (10m) + Almuerzo no laboral (90m) + marca fin_jornada (0m)
    s.add_all(
        [
            Pausa(
                jornada_id=act.jornada.id,
                actividad_id=act.id,
                tipo=TipoPausa.PERSONAL.value,
                motivo="Baño",
                inicio=datetime.combine(lunes, time(10, 5)),
                fin=datetime.combine(lunes, time(10, 15)),
                es_externa=False,
            ),
            Pausa(
                jornada_id=act.jornada.id,
                actividad_id=None,
                tipo=TipoPausa.ALMUERZO.value,
                motivo="Hora de almuerzo",
                inicio=datetime.combine(lunes, time(12, 0)),
                fin=datetime.combine(lunes, time(13, 30)),
                es_externa=False,
            ),
            Pausa(
                jornada_id=act.jornada.id,
                actividad_id=act.id,
                tipo=TipoPausa.FIN_JORNADA.value,
                motivo="Cierre",
                inicio=datetime.combine(lunes, time(16, 45)),
                fin=datetime.combine(lunes, time(16, 45)),
                es_externa=False,
            ),
        ]
    )
    s.add(
        SesionTiempo(
            actividad_id=act.id,
            inicio=datetime.combine(lunes, time(17, 0)),
            fin=datetime.combine(lunes, time(17, 15)),
            duracion_seg=15 * 60,
            fuera_horario=True,
        )
    )
    s.flush()

    res = srv_prod.calcular_jornada(act.jornada)
    assert res.meta_tiempo_pct == 100.0
    assert res.tiempo_efectivo_seg == 120 * 60
    assert res.tiempo_pausas_seg == 10 * 60
    assert res.tiempo_almuerzo_seg == 90 * 60
    assert res.tiempo_fuera_horario_seg == 15 * 60
    assert res.tiempo_bruto_jornada_seg == 130 * 60
    assert res.tiempo_bruto_total_seg == 145 * 60


def test_pdf_diario_sin_meta_con_bruto_y_sin_duplicar_revision(s, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])
    textos = _espiar_textos_lienzo(monkeypatch)

    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    srv_pdf = ServicioReportesPDF(s)
    cat = RepoCategorias(s).obtener_o_crear("Flyers Redes")
    jefe = s.query(Solicitante).first()

    plan = srv_act.crear_planeada(
        "Flyer lanzamiento",
        categoria_id=cat.id,
        tiempo_estimado_min=90,
        momento=datetime(2026, 11, 10, 7, 30),
    )
    cron.iniciar(plan, momento=datetime(2026, 11, 10, 7, 30))
    cron.finalizar(plan, momento=datetime(2026, 11, 10, 9, 0))  # 1h 30m

    rev = srv_act.crear_revision(
        plan,
        solicitante=jefe,
        tipo_revision=TipoRevision.MINIMO,
        que_cambiar="Ajustar precio promocional",
        motivo=MotivoRevision.CAMBIO_CRITERIO,
        momento=datetime(2026, 11, 10, 9, 15),
    )
    cron.iniciar(rev, momento=datetime(2026, 11, 10, 9, 15))
    cron.finalizar(rev, momento=datetime(2026, 11, 10, 9, 35))  # 20m

    s.add_all(
        [
            Pausa(
                jornada_id=plan.jornada.id,
                actividad_id=plan.id,
                tipo=TipoPausa.PERSONAL.value,
                motivo="Hidratación",
                inicio=datetime(2026, 11, 10, 9, 0),
                fin=datetime(2026, 11, 10, 9, 8),
                es_externa=False,
            ),
            Pausa(
                jornada_id=plan.jornada.id,
                actividad_id=None,
                tipo=TipoPausa.ALMUERZO.value,
                motivo="Almuerzo",
                inicio=datetime(2026, 11, 10, 12, 0),
                fin=datetime(2026, 11, 10, 13, 30),
                es_externa=False,
            ),
            Pausa(
                jornada_id=plan.jornada.id,
                actividad_id=plan.id,
                tipo=TipoPausa.FIN_JORNADA.value,
                motivo="Cierre",
                inicio=datetime(2026, 11, 10, 16, 45),
                fin=datetime(2026, 11, 10, 16, 45),
                es_externa=False,
            ),
        ]
    )
    s.flush()

    ruta = srv_pdf.generar_pdf_jornada(plan.jornada)
    pags = _verificar_pdf_generado(ruta)
    unificado = "\n".join(textos)

    assert pags >= 1
    assert "Meta:" not in unificado
    assert "Meta diaria" not in unificado
    assert "BRUTO EN JORNADA" in unificado
    assert "1 h 58 min" in unificado  # 90m + 20m + 8m pausa breve (sin almuerzo)
    assert "Pausas breves: 8 min" in unificado
    assert "Cierre / fin de jornada" not in unificado
    assert f"Página 1 de {pags}" in unificado
    # Total actividad = 1h30m + 20m = 1h 50m (sin sumar doblemente 1h50m sobre parent+hija)
    assert "1 h 50 min" in unificado
    assert "Total (1 revisión)" in unificado


def test_pdf_mensual_denso_y_especifico_titulo_largo(s, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])
    textos = _espiar_textos_lienzo(monkeypatch)

    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    srv_pdf = ServicioReportesPDF(s)
    cat = RepoCategorias(s).obtener_o_crear("Editorial")

    inicio = date(2026, 11, 2)
    for d in range(15):
        dia = inicio + timedelta(days=d)
        if dia.weekday() == 6:
            RepoJornadas(s).obtener_o_crear(dia)
            continue
        act = srv_act.crear_planeada(
            f"Pieza día {d + 1}",
            categoria_id=cat.id,
            tiempo_estimado_min=60,
            momento=datetime.combine(dia, time(8, 0)),
        )
        cron.iniciar(act, momento=datetime.combine(dia, time(8, 0)))
        cron.finalizar(act, momento=datetime.combine(dia, time(9, 15)))

    ruta_mensual = srv_pdf.generar_pdf_periodo(
        inicio,
        inicio + timedelta(days=14),
        etiqueta_periodo="Mensual",
    )
    _verificar_pdf_generado(ruta_mensual)
    unificado = "\n".join(textos)
    assert "Reporte Mensual de Productividad" in unificado
    assert "Estimado vs. Real promedio" in unificado

    textos.clear()
    ruta_esp = srv_pdf.generar_pdf_especifico(
        FiltrosHistorial(fecha_desde=inicio, fecha_hasta=inicio + timedelta(days=14)),
        titulo_filtro="Reporte específico — Seguimiento Campaña Digital Noviembre Diciembre",
    )
    _verificar_pdf_generado(ruta_esp)
    assert "Campaña Digital" in "\n".join(textos)


def test_pantalla_hoy_muestra_bruto_sin_meta(bd, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])
    vista = PantallaHoy(bd)
    assert "Bruto en jornada:" in vista.lbl_meta.text()
    assert "Meta de tiempo" not in vista.lbl_meta.text()
    vista.close()
