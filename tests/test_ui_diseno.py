"""Pruebas de diseño responsivo, geometría y ausencia de recortes en la UI."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select


def _sembrar_actividades_prueba(bd) -> None:
    """Siembra actividades de hoy en distintos estados para poblar tablas y vistas."""
    from data.enums import CanalSolicitud
    from data.models import Solicitante
    from data.repositorios.catalogos import RepoCategorias
    from services.actividades import ServicioActividades
    from services.cronometro import ServicioCronometro

    ahora = datetime.now()
    base = ahora.replace(hour=8, minute=0, second=0, microsecond=0)
    with bd.sesion() as s:
        srv_act = ServicioActividades(s)
        cron = ServicioCronometro(s)
        cat_flyers = RepoCategorias(s).obtener_o_crear("Flyers")
        cat_videos = RepoCategorias(s).obtener_o_crear("Videos")
        cat_redes = RepoCategorias(s).obtener_o_crear("Redes")
        jefe = s.scalar(select(Solicitante).where(Solicitante.nombre == "Ing. Luis Eduardo"))

        a1 = srv_act.crear_planeada(
            "Flyer promocional",
            categoria_id=cat_flyers.id,
            tiempo_estimado_min=30,
            momento=base,
        )
        cron.iniciar(a1, momento=base)
        cron.finalizar(a1, momento=base.replace(hour=8, minute=25))
        srv_act.corregir_actividad(a1, motivo="Ajustar texto", nombre="Flyer vacante abril")

        a2 = srv_act.crear_extra(
            "Video institucional",
            jefe,
            motivo_urgencia="Presentación",
            canal_solicitud=CanalSolicitud.WHATSAPP,
            descripcion="Video 1 min",
            categoria_id=cat_videos.id,
            tiempo_estimado_min=45,
            momento=base.replace(hour=9, minute=0),
        )
        cron.iniciar(a2, momento=base.replace(hour=9, minute=0))
        cron.pausar(a2, motivo="Pausa breve", momento=base.replace(hour=9, minute=10))
        cron.reanudar(a2, momento=base.replace(hour=9, minute=12))

        srv_act.crear_planeada(
            "Posts de redes sociales",
            categoria_id=cat_redes.id,
            tiempo_estimado_min=20,
            momento=base.replace(hour=9, minute=5),
        )


def _recortes_en_widgets(app, raiz, contexto: str) -> list[str]:
    """Detecta desajustes geométricos o recortes bajo `raiz`.

    En plataformas con fuentes reales (Windows), verifica además el ancho exacto
    calculado con `fontMetrics().horizontalAdvance`. Bajo `offscreen` (fuente
    bitmap monoespaciada sin métricas del sistema) valida `minimumSizeHint()` y
    alturas de controles/wrap para no producir falsos negativos.
    """
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QLabel,
        QPushButton,
        QRadioButton,
        QSpinBox,
        QTabBar,
    )

    raiz.ensurePolished()
    app.processEvents()
    hallazgos: list[str] = []
    es_offscreen = app.platformName().lower() == "offscreen"

    for btn in raiz.findChildren(QPushButton):
        if not btn.isVisibleTo(raiz):
            continue
        texto = (btn.text() or "").strip()
        if not texto:
            continue
        if not es_offscreen:
            min_hint_w = btn.minimumSizeHint().width()
            if btn.width() + 2 < min_hint_w:
                hallazgos.append(
                    f"{contexto}: QPushButton {texto!r} width={btn.width()} < minHint={min_hint_w}"
                )
            fm = btn.fontMetrics()
            texto_limpio = texto.replace("&", "")
            icono_w = (btn.iconSize().width() + 6) if not btn.icon().isNull() else 0
            min_w = fm.horizontalAdvance(texto_limpio) + icono_w + 8
            if btn.width() < min_w:
                hallazgos.append(
                    f"{contexto}: QPushButton {texto_limpio!r} width={btn.width()} < {min_w}"
                )

    for w in raiz.findChildren(QCheckBox) + raiz.findChildren(QRadioButton):
        if not w.isVisibleTo(raiz):
            continue
        texto = (w.text() or "").strip()
        if not texto:
            continue
        if not es_offscreen:
            if w.width() + 2 < w.minimumSizeHint().width():
                hallazgos.append(
                    f"{contexto}: {type(w).__name__} {texto!r} width={w.width()} < minHint={w.minimumSizeHint().width()}"
                )
            min_w = w.fontMetrics().horizontalAdvance(texto.replace("&", "")) + 20
            if w.width() < min_w:
                hallazgos.append(
                    f"{contexto}: {type(w).__name__} {texto!r} width={w.width()} < {min_w}"
                )

    for bar in raiz.findChildren(QTabBar):
        if not bar.isVisibleTo(raiz):
            continue
        if not es_offscreen:
            fm = bar.fontMetrics()
            for i in range(bar.count()):
                txt = (bar.tabText(i) or "").strip()
                rect_w = bar.tabRect(i).width()
                min_w = fm.horizontalAdvance(txt.replace("&", "")) + 12
                if rect_w < min_w:
                    hallazgos.append(
                        f"{contexto}: QTabBar tab[{i}] {txt!r} width={rect_w} < {min_w}"
                    )

    for ed in raiz.findChildren(QComboBox) + raiz.findChildren(QSpinBox):
        if not ed.isVisibleTo(raiz):
            continue
        fm = ed.fontMetrics()
        if ed.height() < fm.height() + 4:
            hallazgos.append(
                f"{contexto}: {type(ed).__name__} height={ed.height()} < {fm.height() + 4}"
            )

    if not es_offscreen:
        for lbl in raiz.findChildren(QLabel):
            if not lbl.isVisibleTo(raiz) or not lbl.text().strip():
                continue
            if lbl.wordWrap() and lbl.hasHeightForWidth():
                req_h = lbl.heightForWidth(max(lbl.width(), 1))
                if lbl.height() + 4 < req_h:
                    hallazgos.append(
                        f"{contexto}: QLabel(wrap) height={lbl.height()} < heightForWidth={req_h} ({lbl.text()[:40]!r})"
                    )
            elif not lbl.wordWrap() and "<" not in lbl.text():
                lines = lbl.text().splitlines() or [""]
                mw = max(lbl.fontMetrics().horizontalAdvance(x) for x in lines)
                if lbl.width() + 2 < mw:
                    hallazgos.append(
                        f"{contexto}: QLabel width={lbl.width()} < need={mw} ({lbl.text()[:40]!r})"
                    )

    return hallazgos


def _pausar_en_curso(bd) -> int | None:
    """Pausa la actividad activa antes de cerrar la ventana para evitar diálogo modal."""
    from services.cronometro import ServicioCronometro

    with bd.sesion() as s:
        cron = ServicioCronometro(s)
        act = cron.actividad_en_curso()
        if act is not None:
            act_id = act.id
            cron.pausar(act, motivo="Pausa automática de prueba")
            return act_id
    return None


def test_pantallas_sin_recortes_en_resoluciones_y_fuentes(bd, monkeypatch):
    """Audita las 8 pantallas y 5 pestañas de configuración en 1180x740 (13px) y 1024x680 (15px)."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QFrame, QMessageBox, QScrollArea, QTableWidget

    from data.repositorios.configuracion import RepoConfiguracion
    from ui.ventana_principal import VentanaPrincipal

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    _sembrar_actividades_prueba(bd)
    app = QApplication.instance() or QApplication([])

    escenarios = [
        ("1180x740_f13", 1180, 740, 13),
        ("1024x680_f15", 1024, 680, 15),
    ]
    todos_hallazgos: list[str] = []
    ventana = VentanaPrincipal(bd)
    try:
        ventana.show()
        for nombre_esc, ancho, alto, fuente in escenarios:
            with bd.sesion() as s:
                cfg = RepoConfiguracion(s)
                cfg.guardar("graficos.resolucion", f"{ancho}x{alto}")
                cfg.guardar("graficos.modo_ventana", "ventana")
                cfg.guardar("graficos.tamano_fuente", str(fuente))
            ventana.aplicar_graficos()
            ventana.resize(ancho, alto)
            app.processEvents()

            sidebar = ventana.findChild(QFrame, "sidebar")
            assert sidebar is not None and sidebar.width() == 260
            assert ventana.width() <= ancho, f"{nombre_esc}: ventana se ensanchó a {ventana.width()} > {ancho}"

            # Pantallas que deben tener QScrollArea interno para evitar desbordes
            for pantalla in (
                ventana.pantalla_planear,
                ventana.pantalla_planeacion,
                ventana.pantalla_extra,
                ventana.pantalla_cierre,
                ventana.pantalla_reportes,
                ventana.pantalla_estadisticas,
            ):
                scrolls = pantalla.findChildren(QScrollArea)
                assert any(sc.widgetResizable() for sc in scrolls), f"Falta QScrollArea en {type(pantalla).__name__}"

            for idx in range(9):
                ventana.cambiar_pagina(idx)
                app.processEvents()
                pagina = ventana.paginas.currentWidget()

                if idx == 7:
                    cfg_tab = ventana.pantalla_config
                    assert cfg_tab.tabs_config.count() == 5
                    for t_idx in range(cfg_tab.tabs_config.count()):
                        cfg_tab.tabs_config.setCurrentIndex(t_idx)
                        app.processEvents()
                        todos_hallazgos.extend(
                            _recortes_en_widgets(app, ventana, f"{nombre_esc}/ConfigTab{t_idx}")
                        )
                else:
                    todos_hallazgos.extend(
                        _recortes_en_widgets(app, ventana, f"{nombre_esc}/Pagina{idx}")
                    )

                # En 1180x740 las tablas principales deben caber sin scroll horizontal
                if nombre_esc == "1180x740_f13":
                    if idx == 0:
                        t_hoy = ventana.pantalla_hoy.tabla
                        if t_hoy.horizontalScrollBar().maximum() != 0:
                            cols_w = [t_hoy.columnWidth(c) for c in range(t_hoy.columnCount())]
                            todos_hallazgos.append(
                                f"{nombre_esc}/Hoy: tabla.hbar={t_hoy.horizontalScrollBar().maximum()} cols={cols_w} vp={t_hoy.viewport().width()}"
                            )
                    elif idx == 1:
                        t_plan = ventana.pantalla_planear.tabla_planeadas
                        if t_plan.horizontalScrollBar().maximum() != 0:
                            cols_w = [t_plan.columnWidth(c) for c in range(t_plan.columnCount())]
                            todos_hallazgos.append(
                                f"{nombre_esc}/Planear: tabla.hbar={t_plan.horizontalScrollBar().maximum()} cols={cols_w} vp={t_plan.viewport().width()}"
                            )
                    elif idx == 3:
                        cierre = ventana.pantalla_cierre
                        if cierre.tabla_abiertas.verticalHeader().defaultSectionSize() < 48:
                            todos_hallazgos.append(
                                f"{nombre_esc}/Cierre: defaultSectionSize={cierre.tabla_abiertas.verticalHeader().defaultSectionSize()} < 48"
                            )
                        if cierre.tabla_abiertas.rowCount() > 0:
                            rh = cierre.tabla_abiertas.rowHeight(0)
                            for c_idx in range(cierre.tabla_abiertas.columnCount()):
                                ed = cierre.tabla_abiertas.cellWidget(0, c_idx)
                                if ed is not None and ed.height() > rh:
                                    todos_hallazgos.append(
                                        f"{nombre_esc}/Cierre: cellWidget col={c_idx} height={ed.height()} > rowHeight={rh}"
                                    )
                        if cierre.tabla_abiertas.horizontalScrollBar().maximum() != 0:
                            cols_w = [cierre.tabla_abiertas.columnWidth(c) for c in range(cierre.tabla_abiertas.columnCount())]
                            todos_hallazgos.append(
                                f"{nombre_esc}/Cierre: tabla.hbar={cierre.tabla_abiertas.horizontalScrollBar().maximum()} cols={cols_w} vp={cierre.tabla_abiertas.viewport().width()}"
                            )
                    elif idx == 4:
                        t_hist = ventana.pantalla_historial.tabla
                        if t_hist.horizontalScrollBar().maximum() != 0:
                            cols_w = [t_hist.columnWidth(c) for c in range(t_hist.columnCount())]
                            todos_hallazgos.append(
                                f"{nombre_esc}/Historial: tabla.hbar={t_hist.horizontalScrollBar().maximum()} cols={cols_w} vp={t_hist.viewport().width()}"
                            )
                    elif idx == 6:
                        for t_i, tbl in enumerate(pagina.findChildren(QTableWidget)):
                            if tbl.horizontalScrollBar().maximum() != 0:
                                cols_w = [tbl.columnWidth(c) for c in range(tbl.columnCount())]
                                todos_hallazgos.append(
                                    f"{nombre_esc}/Estadisticas/Tabla{t_i}: hbar={tbl.horizontalScrollBar().maximum()} cols={cols_w} vp={tbl.viewport().width()}"
                                )
    finally:
        _pausar_en_curso(bd)
        ventana.close()
        app.processEvents()

    assert not todos_hallazgos, "Se detectaron recortes visuales:\n" + "\n".join(todos_hallazgos)


def test_mini_widget_y_dialogos_sin_recortes(bd, monkeypatch):
    """Verifica tamaños y no-recorte en MiniWidgetCronometro, DialogoRecordatorio y DialogoPIN."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from data.repositorios.configuracion import RepoConfiguracion
    from services.recordatorios import AvisoRecordatorio, TipoAviso
    from ui.dialogo_recordatorio import DialogoRecordatorio
    from ui.dialogos import DialogoPIN
    from ui.ventana_principal import VentanaPrincipal

    _sembrar_actividades_prueba(bd)
    app = QApplication.instance() or QApplication([])
    hallazgos: list[str] = []

    esperados_mini = {
        "compacta": (350, 126),
        "normal": (384, 136),
        "grande": (420, 148),
    }
    ventana = VentanaPrincipal(bd)
    try:
        ventana.mostrar_ocultar_mini_widget(True)
        for mini_tam, (w_esp, h_esp) in esperados_mini.items():
            with bd.sesion() as s:
                cfg = RepoConfiguracion(s)
                cfg.guardar("graficos.mini_tamano", mini_tam)
                cfg.guardar("graficos.tamano_fuente", "15")
            ventana.aplicar_graficos()
            app.processEvents()
            mw = ventana.mini_widget
            assert (mw.width(), mw.height()) == (w_esp, h_esp)
            hallazgos.extend(_recortes_en_widgets(app, mw, f"MiniWidget/{mini_tam}"))
    finally:
        ventana.mini_widget.close()
        _pausar_en_curso(bd)
        ventana.close()
        app.processEvents()

    # DialogoRecordatorio
    aviso = AvisoRecordatorio(
        tipo=TipoAviso.CONTINUIDAD,
        titulo="¿Sigues con «Video institucional muy largo de ejemplo»?",
        mensaje="Han pasado 45 minutos desde el último registro.",
        actividad_id=1,
        actividad_nombre="Video institucional muy largo de ejemplo",
    )
    dlg_rec = DialogoRecordatorio(aviso)
    try:
        dlg_rec.show()
        app.processEvents()
        assert dlg_rec.minimumWidth() >= 500
        assert dlg_rec.lbl_titulo.wordWrap() is True
        hallazgos.extend(_recortes_en_widgets(app, dlg_rec, "DialogoRecordatorio"))
    finally:
        dlg_rec.close()

    # DialogoPIN
    dlg_pin = DialogoPIN(bd)
    try:
        dlg_pin.show()
        app.processEvents()
        assert dlg_pin.btn_ver_pin.width() >= 84
        hallazgos.extend(_recortes_en_widgets(app, dlg_pin, "DialogoPIN/Mostrar"))
        dlg_pin.btn_ver_pin.click()
        app.processEvents()
        hallazgos.extend(_recortes_en_widgets(app, dlg_pin, "DialogoPIN/Ocultar"))
    finally:
        dlg_pin.close()

    assert not hallazgos, "Se detectaron recortes en diálogos/mini-widget:\n" + "\n".join(hallazgos)


def test_configuracion_visibilidad_resolucion_por_modo_ventana(bd, monkeypatch):
    """Verifica que combo_resolucion solo es visible en modo 'ventana' o 'sin_bordes'."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui.ventana_principal import VentanaPrincipal

    app = QApplication.instance() or QApplication([])
    ventana = VentanaPrincipal(bd)
    try:
        ventana.show()
        ventana.cambiar_pagina(7)
        cfg = ventana.pantalla_config
        cfg.tabs_config.setCurrentIndex(0)
        app.processEvents()

        esperado_visible = {
            "ventana": True,
            "sin_bordes": True,
            "maximizada": False,
            "pantalla_completa": False,
        }
        for modo, debe_verse in esperado_visible.items():
            idx = cfg.combo_modo_ventana.findData(modo)
            assert idx >= 0, f"Modo {modo} no encontrado en combo_modo_ventana"
            cfg.combo_modo_ventana.setCurrentIndex(idx)
            app.processEvents()
            assert cfg.combo_resolucion.isVisibleTo(cfg) is debe_verse, (
                f"combo_resolucion visibilidad incorrecta para modo={modo!r}"
            )
    finally:
        ventana.close()
        app.processEvents()
