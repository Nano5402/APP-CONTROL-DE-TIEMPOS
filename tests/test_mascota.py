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

    widget.close()
