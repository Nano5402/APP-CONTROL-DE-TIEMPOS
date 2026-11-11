"""Ventana emergente al frente para los avisos de recordatorio (RF-04).

Diseño limpio y progresivo:
- Por defecto muestra únicamente la pregunta ``¿Sigues con [actividad]?`` y los
  tres botones grandes (**Sí, sigo**, **No, ya terminé**, **Pausar**).
- Los controles de ajuste de minutos o de motivo de pausa permanecen **ocultos**
  salvo que el usuario despliegue la opción correspondiente.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        self.lbl_titulo = QLabel(aviso.titulo, self)
        self.lbl_titulo.setStyleSheet("font-size: 17px; font-weight: bold;")
        self.lbl_mensaje = QLabel(aviso.mensaje, self)
        self.lbl_mensaje.setWordWrap(True)
        self.lbl_mensaje.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.lbl_titulo)
        layout.addWidget(self.lbl_mensaje)

        # Controles adicionales ocultos hasta que el usuario los necesite
        self.combo_tipo_pausa = QComboBox(self)
        for tp in (
            TipoPausa.PERSONAL,
            TipoPausa.EXTERNA,
            TipoPausa.ALMUERZO,
            TipoPausa.OTRO,
        ):
            self.combo_tipo_pausa.addItem(tp.etiqueta(), tp.value)

        self.txt_motivo = QLineEdit(self)
        self.txt_motivo.setPlaceholderText("Motivo opcional (ej. baño, llamada...)")

        self.spin_ajuste_min = QSpinBox(self)
        self.spin_ajuste_min.setRange(0, 240)
        self.spin_ajuste_min.setSuffix(" min antes")
        self.spin_ajuste_min.setSpecialValueText("Terminé justo ahora (0 min)")

        if aviso.tipo == TipoAviso.CONTINUIDAD:
            self.btn_si = QPushButton("  Sí, sigo en esto", self)
            self.btn_si.setProperty("rol", "exito")
            self.btn_no = QPushButton("  No, ya terminé", self)
            self.btn_pausar = QPushButton("  Pausar", self)
            self.btn_pausar.setProperty("rol", "advertencia")

            configurar_boton(self.btn_si, "check", color="#FFFFFF")
            configurar_boton(self.btn_no, "stop", color="#FFFFFF")
            configurar_boton(self.btn_pausar, "pause", color="#FFFFFF")

            for b in (self.btn_si, self.btn_no, self.btn_pausar):
                b.setCursor(Qt.CursorShape.PointingHandCursor)

            self.btn_si.setDefault(True)
            self.btn_si.clicked.connect(self._elegir_si)
            self.btn_no.clicked.connect(self._elegir_no)
            self.btn_pausar.clicked.connect(self._elegir_pausar)

            fila_botones = QHBoxLayout()
            fila_botones.setSpacing(8)
            fila_botones.addWidget(self.btn_si, 2)
            fila_botones.addWidget(self.btn_no, 1)
            fila_botones.addWidget(self.btn_pausar, 1)
            layout.addLayout(fila_botones)

            # Botón discreto para mostrar opciones avanzadas solo si hace falta
            self.btn_opciones = QPushButton(
                "  ¿Terminaste hace unos minutos o quieres indicar motivo de pausa?", self
            )
            self.btn_opciones.setProperty("rol", "secundario")
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

            fila_tp = QHBoxLayout()
            fila_tp.addWidget(QLabel("Si vas a pausar, tipo:"))
            fila_tp.addWidget(self.combo_tipo_pausa, 1)
            col_extra.addLayout(fila_tp)
            col_extra.addWidget(self.txt_motivo)
            self.panel_extra.setVisible(False)
            self.btn_opciones.toggled.connect(self._mostrar_ocultar_extra)
            layout.addWidget(self.panel_extra)
        else:
            self.combo_tipo_pausa.setVisible(False)
            self.txt_motivo.setVisible(False)
            self.spin_ajuste_min.setVisible(False)
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
