"""Ventana emergente al frente para los avisos de recordatorio (RF-04).

Para el recordatorio de continuidad (``¿Sigues con [actividad]?``) ofrece:
- **Sí, sigo**: continúa el cronómetro.
- **No, ya terminé**: completa la actividad (con opción de descontar minutos si
  olvidó cerrarla antes).
- **Pausar**: pausa el cronómetro con tipo y motivo opcional.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
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


class DialogoRecordatorio(QDialog):
    """Ventana emergente siempre encima de otras ventanas."""

    def __init__(self, aviso: AvisoRecordatorio, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.aviso = aviso
        self.respuesta_elegida: RespuestaRecordatorio | None = None

        self.setWindowTitle(aviso.titulo)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl_titulo = QLabel(f"<b>{aviso.titulo}</b>")
        lbl_titulo.setTextFormat(Qt.TextFormat.RichText)
        lbl_mensaje = QLabel(aviso.mensaje)
        lbl_mensaje.setWordWrap(True)
        layout.addWidget(lbl_titulo)
        layout.addWidget(lbl_mensaje)

        # Controles adicionales solo para "¿Sigues con [actividad]?"
        self.combo_tipo_pausa = QComboBox(self)
        for tp in (
            TipoPausa.PERSONAL,
            TipoPausa.EXTERNA,
            TipoPausa.ALMUERZO,
            TipoPausa.OTRO,
        ):
            self.combo_tipo_pausa.addItem(tp.etiqueta(), tp.value)

        self.txt_motivo = QLineEdit(self)
        self.txt_motivo.setPlaceholderText("Motivo de pausa o de ajuste (opcional)")

        self.spin_ajuste_min = QSpinBox(self)
        self.spin_ajuste_min.setRange(0, 240)
        self.spin_ajuste_min.setSuffix(" min antes")
        self.spin_ajuste_min.setToolTip(
            "Si ya habías terminado antes, descuenta esos minutos al finalizar"
        )

        if aviso.tipo == TipoAviso.CONTINUIDAD:
            fila_extra = QHBoxLayout()
            fila_extra.addWidget(QLabel("Tipo pausa:"))
            fila_extra.addWidget(self.combo_tipo_pausa)
            fila_extra.addWidget(QLabel("Ajuste al finalizar:"))
            fila_extra.addWidget(self.spin_ajuste_min)
            layout.addLayout(fila_extra)
            layout.addWidget(self.txt_motivo)

            fila_botones = QHBoxLayout()
            self.btn_si = QPushButton("Sí, sigo", self)
            self.btn_no = QPushButton("No, ya terminé", self)
            self.btn_pausar = QPushButton("Pausar", self)

            self.btn_si.setDefault(True)
            self.btn_si.clicked.connect(self._elegir_si)
            self.btn_no.clicked.connect(self._elegir_no)
            self.btn_pausar.clicked.connect(self._elegir_pausar)

            fila_botones.addWidget(self.btn_si)
            fila_botones.addWidget(self.btn_no)
            fila_botones.addWidget(self.btn_pausar)
            layout.addLayout(fila_botones)
        else:
            btn_entendido = QPushButton("Entendido", self)
            btn_entendido.setDefault(True)
            btn_entendido.clicked.connect(self.accept)
            layout.addWidget(btn_entendido)

    def _elegir_si(self) -> None:
        self.respuesta_elegida = RespuestaRecordatorio.SI
        self.accept()

    def _elegir_no(self) -> None:
        self.respuesta_elegida = RespuestaRecordatorio.NO
        self.accept()

    def _elegir_pausar(self) -> None:
        self.respuesta_elegida = RespuestaRecordatorio.PAUSAR
        self.accept()

    @property
    def motivo_ingresado(self) -> str:
        return self.txt_motivo.text().strip()

    @property
    def tipo_pausa_seleccionado(self) -> str:
        return str(self.combo_tipo_pausa.currentData() or TipoPausa.PERSONAL.value)

    @property
    def ajuste_minutos(self) -> int:
        return int(self.spin_ajuste_min.value())
