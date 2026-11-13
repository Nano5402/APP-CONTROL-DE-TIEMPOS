"""Mascota de escritorio interactiva «UTILÍN» con globo de texto estilo cómic.

Permanece en el escritorio cuando se cierra la aplicación, mostrando a Utilín
(personaje 3D de Gente Util saludando), un auténtico globo de texto con colita
apuntando hacia su cabeza con el cronómetro en vivo o saludos amigables,
arrastre libre y suave a cualquier parte de la pantalla, y restauración con doble clic.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import rutas
from ui.iconos import configurar_boton
from ui.mini_widget import formatear_reloj_hms


class GloboTextoWidget(QWidget):
    """Globo de diálogo tipo cómic con cuerpo redondeado y colita apuntando a Utilín."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(210)
        self.setMinimumHeight(84)

        # Layout interior con margen inferior ampliado para la colita del globo
        self.layout_globo = QVBoxLayout(self)
        self.layout_globo.setContentsMargins(12, 8, 12, 18)
        self.layout_globo.setSpacing(3)
        self.layout_globo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Línea 1: Reloj o Saludo destacado
        self.lbl_reloj = QLabel("👋 ¡Hola, soy Utilín!", self)
        f_reloj = self.lbl_reloj.font()
        f_reloj.setPointSize(11)
        f_reloj.setWeight(QFont.Weight.ExtraBold)
        self.lbl_reloj.setFont(f_reloj)
        self.lbl_reloj.setStyleSheet("color: #003D95; background: transparent; border: none;")
        self.lbl_reloj.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_globo.addWidget(self.lbl_reloj)

        # Línea 2: Tarea en curso o texto secundario
        self.lbl_actividad = QLabel("Doble clic para abrir app", self)
        self.lbl_actividad.setWordWrap(True)
        self.lbl_actividad.setMaximumWidth(185)
        self.lbl_actividad.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_actividad.setStyleSheet(
            "color: #475569; font-size: 10px; font-weight: 500; background: transparent; border: none;"
        )
        self.layout_globo.addWidget(self.lbl_actividad)

        # Línea 3: Botones de acción compactos dentro del globo
        self.fila_acciones = QHBoxLayout()
        self.fila_acciones.setSpacing(6)
        self.fila_acciones.setContentsMargins(0, 2, 0, 0)
        self.fila_acciones.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_abrir = QPushButton("Abrir app", self)
        self.btn_abrir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abrir.setStyleSheet(
            "QPushButton { background-color: #EFF6FF; color: #003D95; border: 1px solid #BFDBFE; "
            "border-radius: 4px; padding: 2px 7px; font-size: 10px; font-weight: 700; } "
            "QPushButton:hover { background-color: #003D95; color: #FFFFFF; border-color: #003D95; }"
        )
        configurar_boton(self.btn_abrir, "play", color="#003D95", tamano=10)
        self.fila_acciones.addWidget(self.btn_abrir)

        self.btn_finalizar = QPushButton("Finalizar", self)
        self.btn_finalizar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_finalizar.setStyleSheet(
            "QPushButton { background-color: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; "
            "border-radius: 4px; padding: 2px 7px; font-size: 10px; font-weight: 700; } "
            "QPushButton:hover { background-color: #DC2626; color: #FFFFFF; border-color: #DC2626; }"
        )
        configurar_boton(self.btn_finalizar, "stop", color="#DC2626", tamano=10)
        self.btn_finalizar.setVisible(False)
        self.fila_acciones.addWidget(self.btn_finalizar)

        self.layout_globo.addLayout(self.fila_acciones)

    def paintEvent(self, event) -> None:
        """Dibuja el globo de diálogo vectorial con su colita apuntando hacia abajo."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        alto_cola = 11.0

        # Cuerpo del globo redondeado
        rect_cuerpo = QRectF(3.0, 3.0, w - 6.0, h - alto_cola - 5.0)
        path = QPainterPath()
        path.addRoundedRect(rect_cuerpo, 13.0, 13.0)

        # Colita triangular del globo apuntando hacia la cabeza de Utilín
        cx = rect_cuerpo.center().x()
        by = rect_cuerpo.bottom()

        cola = QPainterPath()
        cola.moveTo(cx - 9.0, by - 0.5)
        cola.lineTo(cx + 3.0, by + alto_cola)  # Vértice apuntando a Utilín
        cola.lineTo(cx + 15.0, by - 0.5)
        cola.closeSubpath()

        globo_completo = path.united(cola)

        # Sombra sutil exterior
        p.setPen(QPen(QColor(15, 23, 42, 22), 3.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(globo_completo)

        # Fondo blanco nítido y borde elegante
        p.setPen(QPen(QColor("#94A3B8"), 1.4))
        p.setBrush(QColor(255, 255, 255, 253))
        p.drawPath(globo_completo)
        p.end()


class SombraSueloWidget(QWidget):
    """Sombra de contacto elíptica en el suelo para realismo 3D de Utilín."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(120, 10)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QRadialGradient(self.rect().center(), self.width() / 2.0)
        grad.setColorAt(0.0, QColor(0, 0, 0, 48))
        grad.setColorAt(0.55, QColor(0, 0, 0, 18))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(self.rect())
        p.end()


class MascotaWidget(QWidget):
    """Mascota de escritorio interactiva «UTILÍN» con arrastre libre en pantalla."""

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

        self.setWindowTitle("Utilín · Mascota de Control de Tiempos")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._arrastrando: bool = False
        self._drag_start_pos: QPoint = QPoint()
        self._widget_start_pos: QPoint = QPoint()
        self._posicion_personalizada: QPoint | None = None

        self._nombre_actividad: str | None = None
        self._segundos_actividad: int = 0
        self._globo_visible: bool = True

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(4, 4, 4, 4)
        layout_raiz.setSpacing(1)
        layout_raiz.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Globo de texto tipo cómic
        self.globo = GloboTextoWidget(self)
        if al_restaurar:
            self.globo.btn_abrir.clicked.connect(al_restaurar)
        if al_finalizar:
            self.globo.btn_finalizar.clicked.connect(al_finalizar)

        # Alias de compatibilidad para pruebas y llamadas directas
        self.lbl_reloj = self.globo.lbl_reloj
        self.lbl_actividad = self.globo.lbl_actividad
        self.btn_abrir = self.globo.btn_abrir
        self.btn_finalizar = self.globo.btn_finalizar

        layout_raiz.addWidget(self.globo, 0, Qt.AlignmentFlag.AlignCenter)

        # 2. Utilín (personaje 3D saludando)
        self.lbl_mascota = QLabel(self)
        self.lbl_mascota.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mascota.setToolTip(
            "Utilín — Mascota de Gente Util\n"
            "• Arrastra para moverme a cualquier sitio\n"
            "• Doble clic para abrir Control de Tiempos\n"
            "• Clic derecho para opciones"
        )
        self._cargar_imagen_mascota()
        layout_raiz.addWidget(self.lbl_mascota, 0, Qt.AlignmentFlag.AlignCenter)

        # 3. Sombra de suelo para perspectiva 3D
        self.sombra = SombraSueloWidget(self)
        layout_raiz.addWidget(self.sombra, 0, Qt.AlignmentFlag.AlignCenter)

        self.adjustSize()
        self._posicionar_defecto()

        # Instalar filtro de eventos para arrastre suave universal
        self._instalar_filtro_arrastre()

    def _cargar_imagen_mascota(self) -> None:
        """Carga y renderiza a Utilín con alta resolución y bordes limpios."""
        ruta_img = rutas.carpeta_assets() / "mascota_codex.png"
        if ruta_img.is_file():
            pix = QPixmap(str(ruta_img))
            if not pix.isNull():
                pix_escalada = pix.scaled(
                    150,
                    158,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.lbl_mascota.setPixmap(pix_escalada)
                return

        self.lbl_mascota.setText("🤖\n[Utilín]")
        self.lbl_mascota.setStyleSheet("font-size: 38px; color: #003D95;")

    def _posicionar_defecto(self) -> None:
        """Ubica a Utilín en la esquina inferior derecha o en su posición guardada."""
        if self._posicion_personalizada is not None:
            self.move(self._posicion_personalizada)
            return

        pantalla = QApplication.primaryScreen()
        if pantalla:
            geom = pantalla.availableGeometry()
            ancho = self.sizeHint().width() or 210
            alto = self.sizeHint().height() or 260
            x = max(10, geom.right() - ancho - 30)
            y = max(10, geom.bottom() - alto - 35)
            self.move(x, y)

    def restablecer_posicion(self) -> None:
        """Vuelve a colocar a Utilín en la esquina inferior derecha habitual."""
        self._posicion_personalizada = None
        self._posicionar_defecto()

    def mostrar_mascota(self) -> None:
        """Muestra a Utilín en el escritorio."""
        if self._posicion_personalizada is not None:
            self.move(self._posicion_personalizada)
        self.show()
        self.raise_()
        self.activateWindow()

    def ocultar_mascota(self) -> None:
        """Oculta a Utilín."""
        self.hide()

    def actualizar_estado(
        self,
        nombre_actividad: str | None,
        segundos: int = 0,
    ) -> None:
        """Actualiza el globo de texto con el cronómetro y tarea en curso de Utilín."""
        self._nombre_actividad = nombre_actividad
        self._segundos_actividad = max(0, int(segundos))

        if nombre_actividad:
            tiempo_str = formatear_reloj_hms(self._segundos_actividad)
            self.lbl_reloj.setText(f"⏱ {tiempo_str}")
            self.lbl_reloj.setStyleSheet(
                "color: #003D95; font-size: 13px; font-weight: 800; background: transparent; border: none;"
            )

            texto_nom = nombre_actividad.strip()
            if len(texto_nom) > 24:
                self.lbl_actividad.setText(f"{texto_nom[:21]}…")
            else:
                self.lbl_actividad.setText(texto_nom)
            self.lbl_actividad.setToolTip(f"Actividad en curso: {nombre_actividad}")
            self.btn_finalizar.setVisible(True)
        else:
            self.lbl_reloj.setText("👋 ¡Hola, soy Utilín!")
            self.lbl_reloj.setStyleSheet(
                "color: #003D95; font-size: 11.5px; font-weight: 800; background: transparent; border: none;"
            )
            self.lbl_actividad.setText("Doble clic para abrir app")
            self.lbl_actividad.setToolTip("Sin actividad en curso · Doble clic para abrir Control de Tiempos")
            self.btn_finalizar.setVisible(False)

        self.globo.setVisible(self._globo_visible)
        self.adjustSize()

    def alternar_globo(self) -> None:
        """Muestra u oculta el globo de diálogo de Utilín."""
        self._globo_visible = not self._globo_visible
        self.globo.setVisible(self._globo_visible)
        self.adjustSize()

    # ------------------------------------------------------------------
    # Arrastre libre suave y fluido a cualquier lugar de la pantalla
    # ------------------------------------------------------------------

    def _instalar_filtro_arrastre(self) -> None:
        """Permite que hacer clic en cualquier parte de Utilín o el globo active el arrastre."""
        self.installEventFilter(self)
        for hijo in self.findChildren(QWidget):
            if not isinstance(hijo, QPushButton):
                hijo.installEventFilter(self)

    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:
        t = evento.type()

        if t == QEvent.Type.MouseButtonPress:
            ev: QMouseEvent = evento
            if ev.button() == Qt.MouseButton.LeftButton:
                self._arrastrando = True
                self._drag_start_pos = ev.globalPosition().toPoint()
                self._widget_start_pos = self.pos()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                return False

        elif t == QEvent.Type.MouseMove:
            if self._arrastrando:
                ev_m: QMouseEvent = evento
                delta = ev_m.globalPosition().toPoint() - self._drag_start_pos
                nueva_pos = self._widget_start_pos + delta
                self.move(nueva_pos)
                self._posicion_personalizada = nueva_pos
                return True

        elif t == QEvent.Type.MouseButtonRelease:
            if self._arrastrando:
                self._arrastrando = False
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self._posicion_personalizada = self.pos()

        elif t == QEvent.Type.MouseButtonDblClick:
            ev_d: QMouseEvent = evento
            if ev_d.button() == Qt.MouseButton.LeftButton:
                if self.al_restaurar:
                    self.al_restaurar()
                return True

        return super().eventFilter(objeto, evento)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.al_restaurar:
                self.al_restaurar()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:
        """Menú contextual con opciones al dar clic derecho en Utilín o en su globo."""
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
            "Ocultar globo de texto" if self._globo_visible else "Mostrar globo de texto"
        )
        act_globo.triggered.connect(self.alternar_globo)

        act_pos = menu.addAction("📌 Reubicar en esquina inferior derecha")
        act_pos.triggered.connect(self.restablecer_posicion)

        menu.addSeparator()
        act_salir = menu.addAction("❌ Salir por completo")
        if self.al_cerrar_definitivo:
            act_salir.triggered.connect(self.al_cerrar_definitivo)

        menu.exec(event.globalPos())
