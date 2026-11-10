"""Pruebas de PIN opcional, temas QSS, mini-widget y pantallas de la Fase 5."""

from __future__ import annotations

import pytest

from data.enums import EstadoActividad
from services.seguridad_pin import ServicioPIN, generar_hash_pin, verificar_hash_pin
from ui.temas import TEMAS, generar_qss


def test_pin_hash_y_servicio(s):
    with pytest.raises(ValueError):
        generar_hash_pin("12")
    with pytest.raises(ValueError):
        generar_hash_pin("abcd")

    h = generar_hash_pin("2580")
    assert verificar_hash_pin("2580", h) is True
    assert verificar_hash_pin("9999", h) is False

    srv = ServicioPIN(s)
    assert srv.tiene_pin() is False
    assert srv.verificar("cualquiera") is True

    srv.establecer_pin("1470")
    assert srv.tiene_pin() is True
    assert srv.verificar("1470") is True
    assert srv.verificar("0000") is False

    srv.desactivar_pin()
    assert srv.tiene_pin() is False


def test_generar_qss_todos_los_temas():
    for codigo, paleta in TEMAS.items():
        qss = generar_qss(codigo)
        assert paleta.acento in qss
        assert "QMainWindow" in qss


def test_ventana_principal_pantallas_y_mini_widget_offscreen(bd, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui.ventana_principal import VentanaPrincipal

    _app = QApplication.instance() or QApplication([])
    ventana = VentanaPrincipal(bd)
    ventana.show()

    # 1. Planear una actividad desde PantallaPlanear
    ventana.cambiar_pagina(1)
    ventana.pantalla_planear.txt_nombre.setText("Flyer 1")
    ventana.pantalla_planear.txt_categoria.setText("Flyers")
    ventana.pantalla_planear.spin_estimado.setValue(25)
    ventana.pantalla_planear.accion_agregar_planeada()

    # 2. Volver a Hoy, iniciar y usar "Finalizar y empezar siguiente"
    ventana.cambiar_pagina(0)
    assert ventana.pantalla_hoy.tabla.rowCount() == 1
    ventana.pantalla_hoy.tabla.selectRow(0)
    ventana.pantalla_hoy.accion_iniciar_seleccionada()

    nombre_activo, _ = ventana.pantalla_hoy.actualizar_reloj_en_vivo()
    assert nombre_activo == "Flyer 1"

    # Por defecto no hay ningún atajo de teclado activo (evita activaciones accidentales)
    assert len(ventana._atajos_activos) == 0
    assert "desactivados" in ventana.lbl_atajos.text()

    # Mostrar mini-widget y verificar que se sincroniza con la actividad activa
    ventana.mostrar_ocultar_mini_widget(True)
    assert "Flyer 1" in ventana.mini_widget.lbl_actividad.text()
    assert ventana.mini_widget.btn_siguiente.isEnabled() is True

    # Personalizar un atajo y recargar en caliente, luego limpiar todos
    from data.repositorios.configuracion import RepoConfiguracion

    with bd.sesion() as s:
        RepoConfiguracion(s).guardar("atajo.finalizar", "F9")
    ventana.recargar_atajos()
    assert len(ventana._atajos_activos) == 1
    assert "F9" in ventana.lbl_atajos.text()

    ventana.pantalla_config.refrescar()
    ventana.pantalla_config.accion_limpiar_todos_los_atajos()
    with bd.sesion() as s:
        RepoConfiguracion(s).guardar("atajo.finalizar", "")
    ventana.recargar_atajos()
    assert len(ventana._atajos_activos) == 0

    # Finalizar y empezar siguiente pieza desde Hoy
    ventana.pantalla_hoy.accion_finalizar_y_siguiente()
    assert ventana.pantalla_hoy.tabla.rowCount() == 2
    nombre_activo_2, _ = ventana.pantalla_hoy.actualizar_reloj_en_vivo()
    assert nombre_activo_2 == "Flyer 2"

    # Finalizar la segunda pieza
    ventana.pantalla_hoy.accion_finalizar_activa()
    nombre_activo_3, _ = ventana.pantalla_hoy.actualizar_reloj_en_vivo()
    assert nombre_activo_3 is None

    # Verificar que otra categoría (no Flyers) NO muestra el botón de iniciar otro Flyer
    ventana.pantalla_hoy.txt_no_planeada.setText("Edición de video institucional")
    ventana.pantalla_hoy.accion_iniciar_no_planeada_rapida()
    ventana.pantalla_hoy.actualizar_reloj_en_vivo()
    assert ventana.pantalla_hoy.btn_siguiente.isVisible() is False
    ventana.pantalla_hoy.accion_finalizar_activa()

    # 3. Cambiar a Cierre de jornada y verificar que las dos están completadas
    ventana.cambiar_pagina(3)
    assert ventana.pantalla_cierre.tabla_abiertas.rowCount() == 0
    assert "Flyer 1" in ventana.pantalla_cierre.txt_resumen_wa.toPlainText()
    assert "Flyer 2" in ventana.pantalla_cierre.txt_resumen_wa.toPlainText()

    # 4. Verificar pestañas segmentadas de Configuración y sección de Gráficos
    ventana.cambiar_pagina(7)
    assert ventana.pantalla_config.tabs_config.count() == 5
    assert "Gráficos" in ventana.pantalla_config.tabs_config.tabText(0)
    with bd.sesion() as s:
        cfg = RepoConfiguracion(s)
        cfg.guardar("graficos.resolucion", "1280x800")
        cfg.guardar("graficos.tamano_fuente", 15)
        cfg.guardar("graficos.mini_tamano", "grande")
    ventana.aplicar_graficos()
    assert ventana.width() == 1280
    assert ventana.height() == 800
    assert ventana.mini_widget.width() == 420

    # 5. Cambiar de tema en vivo
    ventana.aplicar_tema("oscuro")
    ventana.mostrar_ocultar_mini_widget(False)
    ventana.close()


def test_dialogo_pausa_y_visibilidad_contextual(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from data.enums import TipoPausa
    from ui.dialogos import DialogoPausa

    _app = QApplication.instance() or QApplication([])
    dlg = DialogoPausa("Flyer promocional")
    dlg.show()

    # Por defecto (Pausa personal / baño), el % de avance está OCULTO
    assert dlg.widget_avance.isVisible() is False

    # Solo cuando se selecciona FIN_JORNADA se hace visible el % de avance
    idx_fin = dlg.combo_tipo.findData(TipoPausa.FIN_JORNADA.value)
    dlg.combo_tipo.setCurrentIndex(idx_fin)
    assert dlg.widget_avance.isVisible() is True

    # Al volver a pausa personal o almuerzo, se vuelve a ocultar
    idx_almuerzo = dlg.combo_tipo.findData(TipoPausa.ALMUERZO.value)
    dlg.combo_tipo.setCurrentIndex(idx_almuerzo)
    assert dlg.widget_avance.isVisible() is False

    # Botón rápido de baño/pausa personal cierra el diálogo con PERSONAL y sin % de avance
    dlg._pausa_rapida(TipoPausa.PERSONAL, "Baño / pausa breve")
    assert dlg.tipo_pausa == TipoPausa.PERSONAL.value
    assert dlg.avance_pct is None
    dlg.close()


def test_cierre_ventana_detiene_timers_y_cierra_por_completo(bd, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication

    from ui.bandeja import CoordinadorRecordatoriosUI, IconoBandeja
    from ui.ventana_principal import VentanaPrincipal

    _app = QApplication.instance() or QApplication([])
    ventana = VentanaPrincipal(bd)
    bandeja = IconoBandeja(ventana)
    coordinador = CoordinadorRecordatoriosUI(bd, ventana, bandeja)
    coordinador.iniciar()
    ventana.coordinador_recordatorios = coordinador
    ventana.icono_bandeja = bandeja

    assert coordinador.timer.isActive() is True

    # Al cerrar la ventana, el coordinador se detiene y no quedan timers sonando
    evento = QCloseEvent()
    ventana.closeEvent(evento)
    assert evento.isAccepted() is True
    assert coordinador.timer.isActive() is False


def test_modos_visualizacion_configuracion_y_pantalla_completa(bd, monkeypatch):
    """Verifica los modos de visualización (Ventana, Sin bordes, Pantalla completa, Maximizada) desde Configuración."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from ui.temas import TEMAS, generar_qss
    from ui.ventana_principal import VentanaPrincipal

    _app = QApplication.instance() or QApplication([])

    # 1. Verificar tema corporativo Gente Útil
    assert "gente_util" in TEMAS
    paleta_gu = TEMAS["gente_util"]
    assert paleta_gu.acento == "#003D95"
    qss_gu = generar_qss("gente_util")
    assert "#003D95" in qss_gu

    # 2. Inicializar ventana principal y barra de título
    ventana = VentanaPrincipal(bd)
    ventana.show()
    assert hasattr(ventana, "barra_titulo")

    # 3. Probar modo 'sin_bordes' (Frameless estético: activa barra minimalista integrada)
    ventana.cambiar_modo_ventana("sin_bordes")
    assert ventana._modo_ventana_actual == "sin_bordes"
    assert bool(ventana.windowFlags() & Qt.WindowType.FramelessWindowHint) is True
    assert ventana.barra_titulo.isVisible() is True

    # 4. Probar modo 'ventana' (Marco estándar de Windows: oculta la barra integrada)
    ventana.cambiar_modo_ventana("ventana")
    assert ventana._modo_ventana_actual == "ventana"
    assert bool(ventana.windowFlags() & Qt.WindowType.FramelessWindowHint) is False
    assert ventana.barra_titulo.isVisible() is False

    # 5. Probar modo 'pantalla_completa' y atajo F11
    ventana.cambiar_modo_ventana("pantalla_completa")
    assert ventana._modo_ventana_actual == "pantalla_completa"
    assert ventana.barra_titulo.isVisible() is False

    # Alternar F11 restaura el modo anterior
    ventana.alternar_pantalla_completa()
    assert ventana.isFullScreen() is False

    # 6. Probar modo 'maximizada'
    ventana.cambiar_modo_ventana("maximizada")
    assert ventana._modo_ventana_actual == "maximizada"
    assert ventana.barra_titulo.isVisible() is False

    ventana.close()


def test_pantalla_planear_mejoras_chips_reordenar_editar_e_iniciar(bd, monkeypatch):
    """Verifica las mejoras de PantallaPlanear: chips de 1 clic, reordenamiento, inicio directo y copia."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from ui.ventana_principal import VentanaPrincipal

    _app = QApplication.instance() or QApplication([])
    ventana = VentanaPrincipal(bd)
    ventana.show()
    plan = ventana.pantalla_planear

    # 1. Navegar a Planear el día
    ventana.cambiar_pagina(1)
    assert plan.tabla_planeadas.rowCount() == 0

    # 2. Agregar tareas con chips de 1 clic
    plan.btn_chip_flyers.click()
    assert plan.tabla_planeadas.rowCount() == 1
    assert plan.tabla_planeadas.item(0, 1).text() == "Flyers"
    assert plan.tabla_planeadas.item(0, 2).text() == "Flyers"

    plan.btn_chip_redes.click()
    assert plan.tabla_planeadas.rowCount() == 2
    assert "redes" in plan.tabla_planeadas.item(1, 1).text().lower()

    # 3. Agregar tarea manual con tiempo estimado
    plan.txt_nombre.setText("Video institucional")
    plan.txt_categoria.setText("Videos")
    plan.spin_estimado.setValue(45)
    plan.accion_agregar_planeada()
    assert plan.tabla_planeadas.rowCount() == 3

    # 4. Verificar métricas del encabezado
    assert "3 actividades" in plan.lbl_chip_total.text()
    assert "45 min" in plan.lbl_chip_tiempo.text()

    # 5. Reordenar tareas (subir la segunda tarea para que quede de primera)
    plan.tabla_planeadas.selectRow(1)
    plan.accion_subir_planeada()

    # Ahora la fila 0 debe ser la de redes y la 1 la de flyers
    assert "redes" in plan.tabla_planeadas.item(0, 1).text().lower()
    assert plan.tabla_planeadas.item(1, 1).text() == "Flyers"
    wa_texto = plan.txt_plan_whatsapp.toPlainText()
    assert "1. Posts de redes sociales" in wa_texto
    assert "2. Flyers" in wa_texto

    # 6. Iniciar directamente una tarea desde la tabla de planeadas
    plan.tabla_planeadas.setCurrentCell(0, 1)
    plan.tabla_planeadas.selectRow(0)
    assert plan.btn_iniciar_ahora.isEnabled() is True
    plan.accion_iniciar_planeada()

    # Debe haber saltado automáticamente a la página de Hoy y el reloj estar activo
    assert ventana.paginas.currentIndex() == 0
    nombre_activo, _ = ventana.pantalla_hoy.actualizar_reloj_en_vivo()
    assert "redes" in nombre_activo.lower()

    # Pausar en BD antes de cerrar para evitar el diálogo interactivo de cierre con tarea activa
    from services.cronometro import ServicioCronometro
    with bd.sesion() as s:
        cron = ServicioCronometro(s)
        act = cron.actividad_en_curso()
        if act:
            cron.pausar(act, motivo="Pausa de prueba")

    # 7. Copiar para WhatsApp y verificar feedback visual
    plan.accion_copiar_whatsapp()
    assert "✓" in plan.btn_copiar_wa.text()

    ventana.close()


def test_pantalla_planear_limpiar_todo_el_plan(bd, monkeypatch):
    """Verifica que el botón 'Limpiar todo el plan' vacía la lista completa tras confirmación."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox
    from ui.ventana_principal import VentanaPrincipal

    _app = QApplication.instance() or QApplication([])
    ventana = VentanaPrincipal(bd)
    ventana.show()
    plan = ventana.pantalla_planear

    # Navegar a Planear el día
    ventana.cambiar_pagina(1)
    assert plan.tabla_planeadas.rowCount() == 0
    assert plan.btn_limpiar_todo.isEnabled() is False

    # Agregar 3 tareas
    plan.btn_chip_flyers.click()
    plan.btn_chip_redes.click()
    plan.btn_chip_video.click()
    assert plan.tabla_planeadas.rowCount() == 3
    assert plan.btn_limpiar_todo.isEnabled() is True
    assert "3 actividades" in plan.lbl_chip_total.text()

    # Si el usuario responde No a la confirmación, no se borra nada
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.No)
    plan.accion_limpiar_todo_el_plan()
    assert plan.tabla_planeadas.rowCount() == 3

    # Si el usuario responde Yes, se vacía toda la lista
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    plan.accion_limpiar_todo_el_plan()
    assert plan.tabla_planeadas.rowCount() == 0
    assert "0 actividades" in plan.lbl_chip_total.text()
    assert plan.btn_limpiar_todo.isEnabled() is False

    ventana.close()




