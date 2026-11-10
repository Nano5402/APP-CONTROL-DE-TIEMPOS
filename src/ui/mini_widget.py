"""Mini-ventana flotante siempre visible con el cronómetro activo (RF-12, 10.3).

Permite ver el tiempo en vivo de la actividad actual encima de cualquier otra
aplicación (Illustrator, Photoshop, navegador, etc.) y ejecutar en 1 clic:
- Pausar
- Finalizar
- Finalizar y empezar siguiente pieza
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def formatear_reloj_hms(segundos: int) -> str:
    seg = max(0, int(segundos))
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class MiniWidgetCronometro(QWidget):
    """Ventana compacta siempre encima de otras ventanas (`WindowStaysOnTopHint`)."""

    def __init__(
        self,
        *,
        al_pausar: Callable[[], None] | None = None,
        al_finalizar: Callable[[], None] | None = None,
        al_siguiente_pieza: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setWindowTitle("Cronómetro — Gente Util")
        self.setFixedSize(348, 130)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        marco = QFrame(self)
        marco.setObjectName("heroCronometro")
        capa_marco = QVBoxLayout(marco)
        capa_marco.setContentsMargins(12, 10, 12, 10)
        capa_marco.setSpacing(8)

        fila_sup = QHBoxLayout()
        self.lbl_actividad = QLabel("⚪ Sin actividad en curso", self)
        self.lbl_actividad.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.lbl_reloj = QLabel("00:00:00", self)
        self.lbl_reloj.setObjectName("relojMini")
        fila_sup.addWidget(self.lbl_actividad, 1)
        fila_sup.addWidget(self.lbl_reloj)
        capa_marco.addLayout(fila_sup)

        fila_btn = QHBoxLayout()
        fila_btn.setSpacing(6)
        self.btn_pausar = QPushButton("⏸ Pausar", self)
        self.btn_pausar.setProperty("rol", "advertencia")
        self.btn_finalizar = QPushButton("⏹ Finalizar", self)
        self.btn_finalizar.setProperty("rol", "exito")
        self.btn_siguiente = QPushButton("⏭ Siguiente", self)
        self.btn_siguiente.setToolTip("Terminar esta actividad y empezar la siguiente")

        for b in (self.btn_pausar, self.btn_finalizar, self.btn_siguiente):
            b.setCursor(Qt.CursorShape.PointingHandCursor)

        if al_pausar:
            self.btn_pausar.clicked.connect(al_pausar)
        if al_finalizar:
            self.btn_finalizar.clicked.connect(al_finalizar)
        if al_siguiente_pieza:
            self.btn_siguiente.clicked.connect(al_siguiente_pieza)

        fila_btn.addWidget(self.btn_pausar)
        fila_btn.addWidget(self.btn_finalizar)
        fila_btn.addWidget(self.btn_siguiente)
        capa_marco.addLayout(fila_btn)

        layout.addWidget(marco)
        self.actualizar_estado(None, 0)

    def actualizar_estado(
        self,
        nombre_actividad: str | None,
        segundos: int,
        nombre_siguiente: str | None = "",
    ) -> None:
        """Actualiza el texto, el reloj y el botón de siguiente del mini-widget."""
        activa = bool(nombre_actividad)
        if nombre_actividad:
            corto = nombre_actividad if len(nombre_actividad) <= 22 else nombre_actividad[:21] + "…"
            self.lbl_actividad.setText(f"🟢 {corto}")
        else:
            self.lbl_actividad.setText("⚪ Sin actividad en curso")
        self.lbl_reloj.setText(formatear_reloj_hms(segundos))
        self.btn_pausar.setEnabled(activa)
        self.btn_finalizar.setEnabled(activa)

        if nombre_siguiente is None:
            self.btn_siguiente.setEnabled(False)
            self.btn_siguiente.setVisible(False)
        else:
            self.btn_siguiente.setVisible(True)
            self.btn_siguiente.setEnabled(activa)
            if nombre_siguiente:
                self.btn_siguiente.setToolTip(f"Terminar e iniciar «{nombre_siguiente}»")
