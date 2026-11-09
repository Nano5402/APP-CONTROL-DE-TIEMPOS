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
        self.setWindowTitle("Cronómetro — Control de Tiempos")
        self.setFixedSize(310, 118)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        marco = QFrame(self)
        marco.setProperty("card", True)
        capa_marco = QVBoxLayout(marco)
        capa_marco.setContentsMargins(8, 6, 8, 6)
        capa_marco.setSpacing(4)

        fila_sup = QHBoxLayout()
        self.lbl_actividad = QLabel("Sin actividad en curso", self)
        self.lbl_actividad.setStyleSheet("font-weight: bold;")
        self.lbl_reloj = QLabel("00:00:00", self)
        self.lbl_reloj.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 18px; font-weight: bold; color: #2563EB;"
        )
        fila_sup.addWidget(self.lbl_actividad, 1)
        fila_sup.addWidget(self.lbl_reloj)
        capa_marco.addLayout(fila_sup)

        fila_btn = QHBoxLayout()
        self.btn_pausar = QPushButton("Pausar", self)
        self.btn_pausar.setProperty("rol", "advertencia")
        self.btn_finalizar = QPushButton("Finalizar", self)
        self.btn_finalizar.setProperty("rol", "exito")
        self.btn_siguiente = QPushButton("Fin + Siguiente", self)
        self.btn_siguiente.setToolTip("Finalizar esta pieza y empezar la siguiente")

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

    def actualizar_estado(self, nombre_actividad: str | None, segundos: int) -> None:
        """Actualiza el texto y el reloj del mini-widget."""
        activa = bool(nombre_actividad)
        self.lbl_actividad.setText(nombre_actividad or "Sin actividad en curso")
        self.lbl_reloj.setText(formatear_reloj_hms(segundos))
        self.btn_pausar.setEnabled(activa)
        self.btn_finalizar.setEnabled(activa)
        self.btn_siguiente.setEnabled(activa)
