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
    assert "¡Hola!" in widget.lbl_reloj.text()
    assert widget.btn_finalizar.isVisible() is False
    assert widget.lbl_mascota.pixmap() is not None

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
