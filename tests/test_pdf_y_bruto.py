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
from reports.generador_pdf import LienzoPDF, PaletaPDF
from reports.graficos_pdf import color_por_nivel_pct
from services.actividades import ServicioActividades
from services.cronometro import AccionSobreActiva, ServicioCronometro
from services.historial import FiltrosHistorial
from services.productividad import NivelSemaforo, ServicioProductividad
from services.reportes_pdf import ServicioReportesPDF, _colores_semaforo
from ui.pantallas.pantalla_cierre import PantallaCierre
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


def test_pausas_no_se_suman_al_tiempo_trabajado(s):
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
    assert res.tiempo_pausas_seg == 0
    assert res.tiempo_almuerzo_seg == 0
    assert res.tiempo_fuera_horario_seg == 15 * 60
    assert res.tiempo_trabajado_total_seg == 135 * 60
    assert res.tiempo_bruto_jornada_seg == 120 * 60
    assert res.tiempo_bruto_total_seg == 135 * 60


def test_pdf_diario_solo_tiempo_efectivo_sin_pausas_ni_duplicar_revision(s, monkeypatch):
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
    assert "TIEMPO EN JORNADA" in unificado
    assert "BRUTO EN JORNADA" not in unificado
    assert "1 h 58 min" not in unificado  # los 8m de pausa NO se suman
    assert "Pausas breves" not in unificado
    assert "Registro de pausas" not in unificado
    assert "Pausa breve" not in unificado
    assert "Cierre / fin de jornada" not in unificado
    assert f"Página 1 de {pags}" in unificado
    # Total actividad = 1h30m + 20m = 1h 50m (sin sumar pausas ni duplicar parent+hija)
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
    assert "TIEMPO TRABAJADO" in unificado
    assert "Bruto" not in unificado
    assert "Estimado vs. Real promedio" in unificado

    textos.clear()
    ruta_esp = srv_pdf.generar_pdf_especifico(
        FiltrosHistorial(fecha_desde=inicio, fecha_hasta=inicio + timedelta(days=14)),
        titulo_filtro="Reporte específico — Seguimiento Campaña Digital Noviembre Diciembre",
    )
    _verificar_pdf_generado(ruta_esp)
    assert "Campaña Digital" in "\n".join(textos)


def test_pantalla_hoy_y_cierre_muestran_solo_tiempo_efectivo_sin_pausas(bd, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])
    vista = PantallaHoy(bd)
    assert "Tiempo efectivo hoy:" in vista.lbl_meta.text()
    assert "Bruto en jornada:" not in vista.lbl_meta.text()
    assert "Meta de tiempo" not in vista.lbl_meta.text()
    vista.close()

    cierre = PantallaCierre(bd)
    cierre.refrescar()
    assert "Tiempo efectivo:" in cierre.lbl_tiempos.text()
    assert "En pausas:" not in cierre.lbl_tiempos.text()
    cierre.close()


def test_iniciar_otra_actividad_cierra_pausa_abierta_previa(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)

    act_a = srv_act.crear_planeada("Actividad A", momento=datetime(2026, 11, 9, 8, 0))
    act_b = srv_act.crear_planeada("Actividad B", momento=datetime(2026, 11, 9, 8, 0))
    act_c = srv_act.crear_planeada("Actividad C", momento=datetime(2026, 11, 9, 8, 0))

    cron.iniciar(act_a, momento=datetime(2026, 11, 9, 8, 0))
    pausa_a = cron.pausar(
        act_a, tipo=TipoPausa.PERSONAL, motivo="Baño", momento=datetime(2026, 11, 9, 9, 0)
    )
    assert pausa_a.fin is None

    # Al iniciar otra actividad diferente a las 09:10, la pausa abierta previa debe cerrarse
    cron.iniciar(act_b, momento=datetime(2026, 11, 9, 9, 10))
    s.refresh(pausa_a)
    assert pausa_a.fin == datetime(2026, 11, 9, 9, 10)
    assert cron.pausa_abierta() is None

    # Al cambiar directamente pausando B e iniciando C, no quedan pausas abiertas huérfanas
    cron.iniciar(act_c, accion_sobre_activa=AccionSobreActiva.PAUSAR, momento=datetime(2026, 11, 9, 10, 0))
    assert cron.pausa_abierta() is None
    assert act_b.pausas[-1].fin == datetime(2026, 11, 9, 10, 0)


def test_colores_semaforo_cubre_todos_los_niveles(tmp_path):
    pal = PaletaPDF.desde_hex("#003D95")
    vistos: set[NivelSemaforo] = set()
    for nivel in NivelSemaforo:
        fondo, texto_c, arco = _colores_semaforo(nivel, pal)
        assert fondo.isValid() and texto_c.isValid() and arco.isValid()
        vistos.add(nivel)
    assert len(vistos) == len(list(NivelSemaforo))
    assert _colores_semaforo(NivelSemaforo.EXCELENTE, pal) == (pal.verde_suave, pal.verde, pal.verde)
    assert _colores_semaforo(NivelSemaforo.ACEPTABLE, pal) == (pal.ambar_suave, pal.ambar, pal.ambar)
    assert _colores_semaforo(NivelSemaforo.POR_MEJORAR, pal) == (pal.rojo_suave, pal.rojo, pal.rojo)
    assert _colores_semaforo(NivelSemaforo.NO_APLICA, pal) == (pal.neutro_suave, pal.neutro, pal.neutro)

    lienzo = LienzoPDF(tmp_path / "paleta.pdf", "Paleta", "Test")
    try:
        assert color_por_nivel_pct(90.0, lienzo) == pal.verde
        assert color_por_nivel_pct(72.0, lienzo) == pal.ambar
        assert color_por_nivel_pct(40.0, lienzo) == pal.rojo
        assert color_por_nivel_pct(None, lienzo) == pal.neutro
    finally:
        lienzo.finalizar()


def test_pdf_jornada_y_periodo_con_semaforo_por_mejorar_y_aceptable(s, monkeypatch):
    textos = _espiar_textos_lienzo(monkeypatch)
    srv_act = ServicioActividades(s)
    srv_cron = ServicioCronometro(s)
    srv_prod = ServicioProductividad(s)
    srv_pdf = ServicioReportesPDF(s)

    # Día con productividad baja (< 60 % -> NivelSemaforo.POR_MEJORAR)
    dia_bajo = date(2026, 11, 16)
    act_b1 = srv_act.crear_planeada(
        "Tarea baja 1", tiempo_estimado_min=180, momento=datetime(2026, 11, 16, 7, 30)
    )
    srv_act.crear_planeada(
        "Tarea baja 2", tiempo_estimado_min=180, momento=datetime(2026, 11, 16, 7, 30)
    )
    srv_act.crear_planeada(
        "Tarea baja 3", tiempo_estimado_min=180, momento=datetime(2026, 11, 16, 7, 30)
    )
    srv_cron.iniciar(act_b1, momento=datetime(2026, 11, 16, 8, 0))
    srv_cron.finalizar(act_b1, momento=datetime(2026, 11, 16, 8, 20))
    res_bajo = srv_prod.calcular_jornada(act_b1.jornada)
    assert res_bajo.semaforo == NivelSemaforo.POR_MEJORAR

    ruta_bajo = srv_pdf.generar_pdf_jornada(act_b1.jornada)
    _verificar_pdf_generado(ruta_bajo)
    assert "Por mejorar" in "\n".join(textos)

    # Día con productividad media (60 - 84 % -> NivelSemaforo.ACEPTABLE)
    textos.clear()
    dia_medio = date(2026, 11, 17)
    act_m1 = srv_act.crear_planeada(
        "Tarea media 1", tiempo_estimado_min=120, momento=datetime(2026, 11, 17, 7, 30)
    )
    act_m2 = srv_act.crear_planeada(
        "Tarea media 2", tiempo_estimado_min=120, momento=datetime(2026, 11, 17, 7, 30)
    )
    srv_cron.iniciar(act_m1, momento=datetime(2026, 11, 17, 7, 30))
    srv_cron.finalizar(act_m1, momento=datetime(2026, 11, 17, 9, 30))
    srv_cron.iniciar(act_m2, momento=datetime(2026, 11, 17, 9, 30))
    srv_cron.finalizar(act_m2, momento=datetime(2026, 11, 17, 12, 0))
    res_med = srv_prod.calcular_jornada(act_m1.jornada)
    assert res_med.semaforo == NivelSemaforo.ACEPTABLE

    ruta_med = srv_pdf.generar_pdf_jornada(act_m1.jornada)
    _verificar_pdf_generado(ruta_med)
    assert "Aceptable" in "\n".join(textos)

    # Período con promedio bajo/medio también debe generarse sin errores
    textos.clear()
    ruta_per = srv_pdf.generar_pdf_periodo(dia_bajo, dia_medio, etiqueta_periodo="Comparativo")
    _verificar_pdf_generado(ruta_per)

