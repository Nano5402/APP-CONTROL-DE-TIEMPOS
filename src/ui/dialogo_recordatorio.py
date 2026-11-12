"""Ventana emergente al frente para los avisos de recordatorio (RF-04).

Diseño limpio y progresivo:
- Por defecto muestra únicamente la pregunta ``¿Sigues con [actividad]?`` y los
  dos botones grandes (**Sí, sigo**, **No, ya terminé**).
- El ajuste de minutos ya transcurridos permanece **oculto** salvo que el
  usuario despliegue la opción correspondiente.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from data.enums import RespuestaRecordatorio, TipoPausa
from services.recordatorios import AvisoRecordatorio, TipoAviso
from ui.iconos import configurar_boton


class DialogoRecordatorio(QDialog):
    """Ventana emergente siempre encima de otras ventanas."""

    def __init__(self, aviso: AvisoRecordatorio, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.aviso = aviso
        self.respuesta_elegida: RespuestaRecordatorio | None = None

        self.setWindowTitle(aviso.titulo)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        self.lbl_titulo = QLabel(aviso.titulo, self)
        self.lbl_titulo.setWordWrap(True)
        self.lbl_titulo.setStyleSheet("font-size: 17px; font-weight: bold;")
        self.lbl_mensaje = QLabel(aviso.mensaje, self)
        self.lbl_mensaje.setWordWrap(True)
        self.lbl_mensaje.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.lbl_titulo)
        layout.addWidget(self.lbl_mensaje)

        self.spin_ajuste_min = QSpinBox(self)
        self.spin_ajuste_min.setRange(0, 240)
        self.spin_ajuste_min.setSuffix(" min antes")
        self.spin_ajuste_min.setSpecialValueText("Terminé justo ahora (0 min)")

        self.txt_motivo = QLineEdit(self)
        self.txt_motivo.setPlaceholderText("Motivo del ajuste si terminaste antes (opcional)")

        if aviso.tipo == TipoAviso.CONTINUIDAD:
            self.btn_si = QPushButton("  Sí, sigo en esto", self)
            self.btn_si.setProperty("rol", "exito")
            self.btn_no = QPushButton("  No, ya terminé", self)

            configurar_boton(self.btn_si, "check", color="#FFFFFF")
            configurar_boton(self.btn_no, "stop", color="#FFFFFF")

            for b in (self.btn_si, self.btn_no):
                b.setCursor(Qt.CursorShape.PointingHandCursor)

            self.btn_si.setDefault(True)
            self.btn_si.clicked.connect(self._elegir_si)
            self.btn_no.clicked.connect(self._elegir_no)

            fila_botones = QHBoxLayout()
            fila_botones.setSpacing(10)
            fila_botones.addWidget(self.btn_si, 1)
            fila_botones.addWidget(self.btn_no, 1)
            layout.addLayout(fila_botones)

            # Botón discreto para ajustar la hora de fin si terminó antes
            self.btn_opciones = QPushButton("  Ajustar hora de fin", self)
            self.btn_opciones.setProperty("rol", "secundario")
            self.btn_opciones.setProperty("compact", True)
            self.btn_opciones.setCheckable(True)
            configurar_boton(self.btn_opciones, "settings", color="#0F172A")
            layout.addWidget(self.btn_opciones)

            self.panel_extra = QFrame(self)
            self.panel_extra.setProperty("card", True)
            col_extra = QVBoxLayout(self.panel_extra)
            fila_aj = QHBoxLayout()
            fila_aj.addWidget(QLabel("Si ya habías terminado, descontar:"))
            fila_aj.addWidget(self.spin_ajuste_min, 1)
            col_extra.addLayout(fila_aj)
            col_extra.addWidget(self.txt_motivo)
            self.panel_extra.setVisible(False)
            self.btn_opciones.toggled.connect(self._mostrar_ocultar_extra)
            layout.addWidget(self.panel_extra)
        else:
            self.spin_ajuste_min.setVisible(False)
            self.txt_motivo.setVisible(False)
            btn_entendido = QPushButton("  Entendido", self)
            btn_entendido.setDefault(True)
            configurar_boton(btn_entendido, "check", color="#FFFFFF")
            btn_entendido.clicked.connect(self.accept)
            layout.addWidget(btn_entendido)

    def actualizar_aviso(self, aviso: AvisoRecordatorio) -> None:
        """Actualiza título y mensaje si llega una repetición sin respuesta previa."""
        self.aviso = aviso
        self.setWindowTitle(aviso.titulo)
        self.lbl_titulo.setText(aviso.titulo)
        self.lbl_mensaje.setText(aviso.mensaje)

    def _mostrar_ocultar_extra(self, visible: bool) -> None:
        self.panel_extra.setVisible(visible)
        self.adjustSize()

    def _elegir_si(self) -> None:
        self.respuesta_elegida = RespuestaRecordatorio.SI
        self.accept()

    def _elegir_no(self) -> None:
        self.respuesta_elegida = RespuestaRecordatorio.NO
        self.accept()

    @property
    def motivo_ingresado(self) -> str:
        return self.txt_motivo.text().strip()

    @property
    def tipo_pausa_seleccionado(self) -> str:
        return TipoPausa.PERSONAL.value

    @property
    def ajuste_minutos(self) -> int:
        return int(self.spin_ajuste_min.value())
