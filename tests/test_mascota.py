"""Pruebas de la mascota de escritorio interactiva (Codex Pets)."""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from ui.mascota_widget import MascotaWidget
from ui.ventana_principal import VentanaPrincipal


def test_mascota_widget_creacion_y_estados():
    app = QApplication.instance() or QApplication([])

    restaurado = False
    finalizado = False
    cerrado = False

    def on_restaurar():
        nonlocal restaurado
        restaurado = True

    def on_finalizar():
        nonlocal finalizado
        finalizado = True

    def on_cerrar():
        nonlocal cerrado
        cerrado = True

    widget = MascotaWidget(
        al_restaurar=on_restaurar,
        al_finalizar=on_finalizar,
        al_cerrar_definitivo=on_cerrar,
    )
    widget.show()
    app.processEvents()

    # Estado inicial: Sin actividad
    assert "Utilín" in widget.lbl_reloj.text()
    assert widget.btn_finalizar.isVisible() is False
    assert widget.lbl_mascota.pixmap() is not None

    # Prueba de arrastre a otro lugar de la pantalla
    pos_inicial = widget.pos()
    ev_press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPoint(20, 20),
        QPoint(200, 200),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.eventFilter(widget.lbl_mascota, ev_press)

    ev_move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPoint(50, 50),
        QPoint(350, 450),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.eventFilter(widget.lbl_mascota, ev_move)
    assert widget.pos() != pos_inicial

    ev_release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPoint(50, 50),
        QPoint(350, 450),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.eventFilter(widget.lbl_mascota, ev_release)
    assert widget._arrastrando is False

    # Estado con actividad en curso
    widget.actualizar_estado("Flyer promocional vacantes", 125)
    app.processEvents()

    assert "00:02:05" in widget.lbl_reloj.text()
    assert "Flyer" in widget.lbl_actividad.text()
    assert widget.btn_finalizar.isVisible() is True

    # Alternar visibilidad del globo informativo
    assert widget.globo.isVisible() is True
    widget.alternar_globo()
    assert widget.globo.isVisible() is False
    widget.alternar_globo()
    assert widget.globo.isVisible() is True

    # Simular doble clic para restaurar app
    ev_dbl = QMouseEvent(
        QMouseEvent.Type.MouseButtonDblClick,
        QPoint(10, 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseDoubleClickEvent(ev_dbl)
    assert restaurado is True

    widget.close()


def test_ventana_principal_integracion_mascota(bd):
    app = QApplication.instance() or QApplication([])

    ventana = VentanaPrincipal(bd)
    assert hasattr(ventana, "mascota_widget")
    assert ventana.mascota_widget is not None

    # Botón en sidebar para alternar mascota
    assert hasattr(ventana, "btn_toggle_mascota")
    ventana.mostrar_ocultar_mascota(True)
    assert ventana.mascota_widget.isVisible() is True
    assert ventana.btn_toggle_mascota.isChecked() is True

    ventana.mostrar_ocultar_mascota(False)
    assert ventana.mascota_widget.isVisible() is False
    assert ventana.btn_toggle_mascota.isChecked() is False

    # Restauración desde mascota
    ventana.restaurar_desde_mascota()
    assert ventana.isVisible() is True

    ventana.cerrar_definitivo()


def test_mascota_animaciones_saludo_y_caminata():
    app = QApplication.instance() or QApplication([])

    widget = MascotaWidget()
    lbl = widget.lbl_mascota

    # 1. Verificación de sprites cargados correctamente
    assert not lbl._pix_neutral.isNull()
    assert not lbl._pix_wave.isNull()
    assert not lbl._pix_walk1.isNull()
    assert not lbl._pix_walk2.isNull()

    # 2. Caminata hacia la izquierda (pose espejada y paso activo)
    lbl.registrar_movimiento(-12.0)
    assert lbl._esta_caminando is True
    assert lbl._direccion_caminar == -1
    lbl.repaint()
    app.processEvents()

    # 3. Caminata hacia la derecha
    lbl.registrar_movimiento(15.0)
    assert lbl._esta_caminando is True
    assert lbl._direccion_caminar == 1
    lbl.repaint()
    app.processEvents()

    # 4. Soltar arrastre: regresa a reposo
    lbl.soltar_arrastre()
    assert lbl._esta_caminando is False
    lbl.repaint()
    app.processEvents()

    # 5. Saludo forzado y saludo periódico cada 10s
    lbl.forzar_saludo()
    assert lbl._saludando is True
    lbl.repaint()
    app.processEvents()

    # Completar duración del saludo
    lbl._tiempo_saludo = 2.5
    lbl._actualizar_fisicas()
    assert lbl._saludando is False

    # Avanzar el temporizador a 10s para disparar saludo automático
    lbl._temporizador_saludo = 10.1
    lbl._actualizar_fisicas()
    assert lbl._saludando is True

    # 6. Modo Bot IA: Halo neural pensando y pedestal con actividad
    lbl.set_pensando(True)
    assert lbl._pensando is True
    lbl.repaint()
    app.processEvents()

    lbl.set_tiene_actividad(True)
    assert lbl._tiene_actividad is True
    lbl.repaint()
    app.processEvents()

    # 7. Emotes de mascota virtual y siesta
    lbl.activar_saltito()
    assert len(lbl._emotes) > 0
    assert lbl._jump_y < 0.0
    lbl.repaint()
    app.processEvents()

    # Siesta y despertar
    lbl.set_durmiendo(True)
    assert lbl._durmiendo is True
    lbl.despertar()
    assert lbl._durmiendo is False

    lbl.activar_eureka()
    assert lbl._pensando is False
    assert lbl._saludando is True
    lbl.repaint()
    app.processEvents()

    widget.close()


def test_globo_dinamico_ia_y_reloj():
    """Valida la adaptabilidad dinámica del globo: anchos, scroll, botones contextuales y anclaje."""
    app = QApplication.instance() or QApplication([])
    widget = MascotaWidget()
    widget.show()
    app.processEvents()

    globo = widget.globo

    # 1. Modo reloj inicial: compacto 268px
    assert globo.width() == globo._ancho_compacto
    assert globo.btn_volver_reloj.isVisible() is False
    assert globo.btn_copiar.isVisible() is False
    assert globo.widget_chat.isVisible() is False

    # 2. Abrir chat: expande a 308px
    globo.alternar_modo_chat()
    app.processEvents()
    assert globo._modo_chat is True
    assert globo.width() == globo._ancho_expandido
    assert globo.widget_chat.isVisible() is True

    # 3. Mostrar estado pensando
    globo.mostrar_pensando()
    app.processEvents()
    assert "pensando" in globo.lbl_reloj.text().lower()
    assert globo.btn_volver_reloj.isVisible() is True
    assert globo.btn_abrir.isVisible() is False
    assert globo.btn_copiar.isVisible() is False

    # 4. Mostrar respuesta IA extensa: verifica auto-expansión y scroll
    mensaje_largo = (
        "¡Hola! Soy Utilín, tu copiloto de IA en Gente Útil. "
        "Puedo ayudarte a organizar tu jornada laboral, crear tareas y mucho más... "
        "¿Qué te gustaría hacer hoy?"
    )
    globo.mostrar_respuesta_ia(mensaje_largo, accion_ejecutada=None)
    app.processEvents()

    assert "Utilín" in globo.lbl_reloj.text()
    assert globo.scroll_mensaje.height() >= 34
    assert globo.btn_copiar.isVisible() is True
    assert globo.btn_volver_reloj.isVisible() is True
    # Botones de cronómetro deben estar ocultos para no saturar la vista
    assert globo.btn_abrir.isVisible() is False
    assert globo.btn_pausar.isVisible() is False
    assert globo.btn_finalizar.isVisible() is False

    # 5. Volver al cronómetro: restaura modo compacto y controles
    widget.actualizar_estado("Rediseño UI", 45)
    app.processEvents()
    globo.volver_a_cronometro()
    app.processEvents()

    assert globo._modo_respuesta_ia is False
    assert globo.btn_volver_reloj.isVisible() is False
    assert globo.btn_copiar.isVisible() is False
    assert globo.btn_abrir.isVisible() is True
    assert globo.btn_pausar.isVisible() is True
    assert globo.btn_finalizar.isVisible() is True
    assert "00:00:45" in widget.lbl_reloj.text()

    # 6. Verificación de anclaje de suelo al ajustar tamaño
    suelo_inicial = widget.y() + widget.height()
    globo.mostrar_respuesta_ia(mensaje_largo)
    app.processEvents()
    suelo_expandido = widget.y() + widget.height()
    # El suelo debe mantenerse fijo (variación menor a 2px)
    assert abs(suelo_expandido - suelo_inicial) <= 2

    widget.close()

