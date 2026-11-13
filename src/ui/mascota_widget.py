"""Mascota de escritorio interactiva inspirada en las mascotas de Codex.

Permanece flotando en el escritorio cuando se cierra la ventana principal de la
aplicación, mostrando el personaje 3D corporativo de Gente Util saludando,
el cronómetro en vivo de la actividad en curso (o saludo si no hay tarea activa),
y permitiendo arrastrarla a cualquier lugar de la pantalla, abrir la app con
doble clic o finalizar tareas con 1 clic.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config import rutas
from ui.iconos import configurar_boton, obtener_icono
from ui.mini_widget import formatear_reloj_hms


class MascotaWidget(QWidget):
    """Ventana flotante translúcida que muestra la mascota en el escritorio."""

    def __init__(
        self,
        *,
        al_restaurar: Callable[[], None] | None = None,
        al_finalizar: Callable[[], None] | None = None,
        al_cerrar_definitivo: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.al_restaurar = al_restaurar
        self.al_finalizar = al_finalizar
        self.al_cerrar_definitivo = al_cerrar_definitivo

        self.setWindowTitle("Mascota · Control de Tiempos")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._drag_pos: QPoint | None = None
        self._nombre_actividad: str | None = None
        self._segundos_actividad: int = 0
        self._globo_visible: bool = True

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(6, 6, 6, 6)
        layout_raiz.setSpacing(4)
        layout_raiz.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Globo de diálogo / Tarjeta de estado flotante
        self.globo = QFrame(self)
        self.globo.setObjectName("globoMascota")
        self.globo.setStyleSheet(
            "QFrame#globoMascota { "
            "  background-color: rgba(255, 255, 255, 0.96); "
            "  border: 1.5px solid #CBD5E1; "
            "  border-radius: 12px; "
            "} "
            "QLabel { background: transparent; border: none; } "
            "QPushButton { font-size: 10px; font-weight: 600; border-radius: 4px; padding: 2px 6px; }"
        )
        capa_globo = QVBoxLayout(self.globo)
        capa_globo.setContentsMargins(10, 8, 10, 8)
        capa_globo.setSpacing(4)

        # Fila superior del globo: Reloj o Saludo
        self.lbl_reloj = QLabel("👋 ¡Hola!", self.globo)
        f_reloj = self.lbl_reloj.font()
        f_reloj.setPointSize(11)
        f_reloj.setWeight(QFont.Weight.Bold)
        self.lbl_reloj.setFont(f_reloj)
        self.lbl_reloj.setStyleSheet("color: #003D95;")
        self.lbl_reloj.setAlignment(Qt.AlignmentFlag.AlignCenter)
        capa_globo.addWidget(self.lbl_reloj)

        # Subtítulo: Nombre de actividad o pista
        self.lbl_actividad = QLabel("Doble clic para abrir", self.globo)
        self.lbl_actividad.setWordWrap(True)
        self.lbl_actividad.setMaximumWidth(170)
        self.lbl_actividad.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_actividad.setStyleSheet("color: #475569; font-size: 10.5px; font-weight: 500;")
        capa_globo.addWidget(self.lbl_actividad)

        # Fila de acciones compactas dentro del globo
        self.fila_acciones = QHBoxLayout()
        self.fila_acciones.setSpacing(6)
        self.fila_acciones.setContentsMargins(0, 2, 0, 0)
        self.fila_acciones.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_abrir = QPushButton("Abrir app", self.globo)
        self.btn_abrir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abrir.setStyleSheet(
            "QPushButton { background-color: #EFF6FF; color: #003D95; border: 1px solid #BFDBFE; } "
            "QPushButton:hover { background-color: #003D95; color: #FFFFFF; }"
        )
        configurar_boton(self.btn_abrir, "play", color="#003D95", tamano=10)
        if al_restaurar:
            self.btn_abrir.clicked.connect(al_restaurar)
        self.fila_acciones.addWidget(self.btn_abrir)

        self.btn_finalizar = QPushButton("Finalizar", self.globo)
        self.btn_finalizar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_finalizar.setStyleSheet(
            "QPushButton { background-color: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; } "
            "QPushButton:hover { background-color: #DC2626; color: #FFFFFF; }"
        )
        configurar_boton(self.btn_finalizar, "stop", color="#DC2626", tamano=10)
        if al_finalizar:
            self.btn_finalizar.clicked.connect(al_finalizar)
        self.btn_finalizar.setVisible(False)
        self.fila_acciones.addWidget(self.btn_finalizar)

        capa_globo.addLayout(self.fila_acciones)
        layout_raiz.addWidget(self.globo, 0, Qt.AlignmentFlag.AlignCenter)

        # 2. Mascota 3D (personaje saludando)
        self.lbl_mascota = QLabel(self)
        self.lbl_mascota.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mascota.setToolTip(
            "Mascota de Control de Tiempos\n"
            "• Doble clic: Abrir ventana principal\n"
            "• Arrastrar: Mover a cualquier lugar\n"
            "• Clic derecho: Opciones y menú"
        )

        self._cargar_imagen_mascota()
        layout_raiz.addWidget(self.lbl_mascota, 0, Qt.AlignmentFlag.AlignCenter)

        self.adjustSize()
        self._posicionar_defecto()

    def _cargar_imagen_mascota(self) -> None:
        """Carga y escala con alta resolución la imagen de la mascota."""
        ruta_img = rutas.carpeta_assets() / "mascota_codex.png"
        if ruta_img.is_file():
            pix = QPixmap(str(ruta_img))
            if not pix.isNull():
                pix_escalada = pix.scaled(
                    150,
                    160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.lbl_mascota.setPixmap(pix_escalada)
                return

        # Fallback si no está el asset gráfico
        self.lbl_mascota.setText("🤖\n[Mascota]")
        self.lbl_mascota.setStyleSheet("font-size: 40px; color: #003D95;")

    def _posicionar_defecto(self) -> None:
        """Ubica la mascota en la esquina inferior derecha del escritorio."""
        pantalla = QApplication.primaryScreen()
        if pantalla:
            geom = pantalla.availableGeometry()
            ancho = self.sizeHint().width() or 180
            alto = self.sizeHint().height() or 240
            x = max(10, geom.right() - ancho - 30)
            y = max(10, geom.bottom() - alto - 40)
            self.move(x, y)

    def mostrar_mascota(self) -> None:
        """Muestra y trae al frente la mascota."""
        self.show()
        self.raise_()
        self.activateWindow()

    def ocultar_mascota(self) -> None:
        """Oculta la mascota del escritorio."""
        self.hide()

    def actualizar_estado(
        self,
        nombre_actividad: str | None,
        segundos: int = 0,
    ) -> None:
        """Actualiza el globo informativo con la tarea y cronómetro en vivo."""
        self._nombre_actividad = nombre_actividad
        self._segundos_actividad = max(0, int(segundos))

        if nombre_actividad:
            tiempo_str = formatear_reloj_hms(self._segundos_actividad)
            self.lbl_reloj.setText(f"⏱ {tiempo_str}")
            self.lbl_reloj.setStyleSheet("color: #003D95; font-size: 13px; font-weight: 800;")

            texto_nom = nombre_actividad.strip()
            if len(texto_nom) > 26:
                self.lbl_actividad.setText(f"{texto_nom[:23]}...")
            else:
                self.lbl_actividad.setText(texto_nom)
            self.lbl_actividad.setToolTip(f"Actividad en curso: {nombre_actividad}")
            self.btn_finalizar.setVisible(True)
        else:
            self.lbl_reloj.setText("👋 ¡Hola!")
            self.lbl_reloj.setStyleSheet("color: #003D95; font-size: 12px; font-weight: 800;")
            self.lbl_actividad.setText("Doble clic para abrir")
            self.lbl_actividad.setToolTip("Sin actividad en curso · Doble clic para abrir la app")
            self.btn_finalizar.setVisible(False)

        self.globo.setVisible(self._globo_visible)
        self.adjustSize()

    def alternar_globo(self) -> None:
        """Oculta o muestra el globo de diálogo flotante."""
        self._globo_visible = not self._globo_visible
        self.globo.setVisible(self._globo_visible)
        self.adjustSize()

    # Eventos de interacción del ratón
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.al_restaurar:
                self.al_restaurar()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:
        """Menú contextual con opciones al dar clic derecho en la mascota."""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; padding: 4px; } "
            "QMenu::item { padding: 6px 14px; border-radius: 4px; font-size: 11px; color: #0F172A; } "
            "QMenu::item:selected { background-color: #EFF6FF; color: #003D95; font-weight: 600; } "
            "QMenu::separator { height: 1px; background-color: #E2E8F0; margin: 4px 6px; }"
        )

        act_abrir = menu.addAction("📱 Abrir Control de Tiempos")
        if self.al_restaurar:
            act_abrir.triggered.connect(self.al_restaurar)

        if self._nombre_actividad:
            menu.addSeparator()
            tiempo_str = formatear_reloj_hms(self._segundos_actividad)
            act_info = menu.addAction(f"⏱ {self._nombre_actividad} ({tiempo_str})")
            act_info.setEnabled(False)

            if self.al_finalizar:
                act_fin = menu.addAction("⏹ Finalizar tarea en curso")
                act_fin.triggered.connect(self.al_finalizar)

        menu.addSeparator()
        act_globo = menu.addAction(
            "Ocultar globo informativo" if self._globo_visible else "Mostrar globo informativo"
        )
        act_globo.triggered.connect(self.alternar_globo)

        menu.addSeparator()
        act_salir = menu.addAction("❌ Salir por completo")
        if self.al_cerrar_definitivo:
            act_salir.triggered.connect(self.al_cerrar_definitivo)

        menu.exec(event.globalPos())
