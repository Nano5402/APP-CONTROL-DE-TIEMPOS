"""Mascota de escritorio interactiva «UTILÍN» con animaciones fluidas (Codex Pets).

Incluye:
- Flotación y respiración suave (bobbing y squash & stretch).
- Animación de saludo rítmico con la mano en 3 poses (izquierda, centro, derecha).
- Parpadeo de ojos natural y tierno (^ ^) cada pocos segundos.
- Física de inercia e inclinación al arrastrar por la pantalla.
- Rebote elástico (hop) al hacer clic.
- Sombra de contacto 3D dinámica que reacciona a la altura del personaje.
- Auténtico globo de texto tipo cómic con colita apuntando a su cabeza.
- Arrastre libre a cualquier monitor y restauración con doble clic.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTransform,
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
        self.setFixedWidth(214)
        self.setMinimumHeight(86)

        self.layout_globo = QVBoxLayout(self)
        self.layout_globo.setContentsMargins(12, 8, 12, 19)
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
        self.lbl_actividad.setMaximumWidth(188)
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
        """Dibuja el globo de diálogo vectorial con su colita apuntando a Utilín."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        alto_cola = 11.0

        # Cuerpo del globo redondeado
        rect_cuerpo = QRectF(3.0, 3.0, w - 6.0, h - alto_cola - 5.0)
        path = QPainterPath()
        path.addRoundedRect(rect_cuerpo, 13.0, 13.0)

        # Colita triangular del globo
        cx = rect_cuerpo.center().x()
        by = rect_cuerpo.bottom()

        cola = QPainterPath()
        cola.moveTo(cx - 9.0, by - 0.5)
        cola.lineTo(cx + 3.0, by + alto_cola)
        cola.lineTo(cx + 15.0, by - 0.5)
        cola.closeSubpath()

        globo_completo = path.united(cola)

        # Sombra sutil exterior
        p.setPen(QPen(QColor(15, 23, 42, 24), 3.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(globo_completo)

        # Fondo blanco nítido y borde
        p.setPen(QPen(QColor("#94A3B8"), 1.4))
        p.setBrush(QColor(255, 255, 255, 253))
        p.drawPath(globo_completo)
        p.end()


class UtilinAnimadoWidget(QWidget):
    """Lienzo interactivo animado de Utilín con física de inercia y saludo dinámico."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(164, 184)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._t: float = 0.0
        self._parpadeando: bool = False
        self._duracion_parpadeo: int = 0
        self._tiempo_proximo_parpadeo: float = random.uniform(3.0, 5.0)

        self._fase_saludo: int = 0  # 0=neutral, 1=wave_l, 2=neutral, 3=wave_r
        self._timer_saludo: float = 0.0
        self._velocidad_saludo: float = 1.0  # se acelera en hover o drag

        self._tilt_deg: float = 0.0
        self._tilt_objetivo: float = 0.0
        self._jump_y: float = 0.0
        self._is_hovered: bool = False

        self._cargar_frames()

        # Timer principal de animación (33 FPS / ~30ms para suavidad sin carga CPU)
        self._timer_anim = QTimer(self)
        self._timer_anim.setInterval(30)
        self._timer_anim.timeout.connect(self._actualizar_animacion)
        self._timer_anim.start()

    def _cargar_frames(self) -> None:
        """Carga las 6 variaciones de animación de Utilín."""
        d = rutas.carpeta_assets()
        self.pix_neutral = QPixmap(str(d / "mascota_codex.png"))
        self.pix_blink = QPixmap(str(d / "mascota_blink.png"))
        self.pix_wave_l = QPixmap(str(d / "mascota_wave_l.png"))
        self.pix_wave_l_blink = QPixmap(str(d / "mascota_wave_l_blink.png"))
        self.pix_wave_r = QPixmap(str(d / "mascota_wave_r.png"))
        self.pix_wave_r_blink = QPixmap(str(d / "mascota_wave_r_blink.png"))

        # Fallback de seguridad si faltase alguna imagen
        if self.pix_blink.isNull():
            self.pix_blink = self.pix_neutral
        if self.pix_wave_l.isNull():
            self.pix_wave_l = self.pix_neutral
        if self.pix_wave_l_blink.isNull():
            self.pix_wave_l_blink = self.pix_wave_l
        if self.pix_wave_r.isNull():
            self.pix_wave_r = self.pix_neutral
        if self.pix_wave_r_blink.isNull():
            self.pix_wave_r_blink = self.pix_wave_r

    def pixmap(self) -> QPixmap:
        """Devuelve el pixmap actual de Utilín (compatibilidad con tests e inspección)."""
        return self._obtener_frame_actual()

    def _obtener_frame_actual(self) -> QPixmap:
        """Determina qué frame mostrar según parpadeo y fase del saludo."""
        if self._parpadeando:
            if self._fase_saludo == 1:
                return self.pix_wave_l_blink
            elif self._fase_saludo == 3:
                return self.pix_wave_r_blink
            return self.pix_blink
        else:
            if self._fase_saludo == 1:
                return self.pix_wave_l
            elif self._fase_saludo == 3:
                return self.pix_wave_r
            return self.pix_neutral

    def set_inclinacion_arrastre(self, inclinacion_grados: float) -> None:
        """Aplica inclinación dinámica por inercia mientras el usuario arrastra."""
        self._tilt_objetivo = max(-14.0, min(14.0, inclinacion_grados))
        self._velocidad_saludo = 2.4

    def soltar_arrastre(self) -> None:
        """Restablece la inclinación suavemente con rebote."""
        self._tilt_objetivo = 0.0
        self._velocidad_saludo = 1.0

    def activar_saltito(self) -> None:
        """Activa un salto alegre al hacer clic en Utilín."""
        self._jump_y = -10.0
        self._velocidad_saludo = 2.8

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self._velocidad_saludo = 2.0
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self._velocidad_saludo = 1.0
        super().leaveEvent(event)

    def _actualizar_animacion(self) -> None:
        dt = 0.030
        self._t += dt

        # 1. Parpadeo periódico
        if not self._parpadeando:
            if self._t >= self._tiempo_proximo_parpadeo:
                self._parpadeando = True
                self._duracion_parpadeo = 4  # 4 frames (~120ms)
        else:
            self._duracion_parpadeo -= 1
            if self._duracion_parpadeo <= 0:
                self._parpadeando = False
                self._tiempo_proximo_parpadeo = self._t + random.uniform(3.0, 5.5)

        # 2. Ciclo de saludo con la mano
        self._timer_saludo += dt * self._velocidad_saludo
        # Alterna entre: 0=neutral (0.5s), 1=wave_l (0.28s), 2=neutral (0.2s), 3=wave_r (0.28s)
        ciclo = self._timer_saludo % 1.26
        if ciclo < 0.40:
            self._fase_saludo = 0
        elif ciclo < 0.68:
            self._fase_saludo = 1
        elif ciclo < 0.88:
            self._fase_saludo = 0
        else:
            self._fase_saludo = 3

        # 3. Amortiguación del salto (jump physics)
        if abs(self._jump_y) > 0.1:
            self._jump_y *= 0.86
        else:
            self._jump_y = 0.0

        # 4. Amortiguación de inclinación (inercia)
        self._tilt_deg += (self._tilt_objetivo - self._tilt_deg) * 0.22

        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cx = self.width() / 2.0
        # Flotación sinusoidal suave (bobbing)
        bob_y = math.sin(self._t * 2.8) * 4.2 + self._jump_y

        # 1. Dibujar sombra de suelo dinámica debajo de Utilín
        cy_sombra = self.height() - 9.0
        factor_sombra = max(0.60, min(1.15, 1.0 - (bob_y / 24.0)))
        w_sombra = 98.0 * factor_sombra
        h_sombra = 12.0 * factor_sombra

        grad_sombra = QRadialGradient(cx, cy_sombra, w_sombra / 2.0)
        grad_sombra.setColorAt(0.0, QColor(0, 0, 0, int(52 * factor_sombra)))
        grad_sombra.setColorAt(0.55, QColor(0, 0, 0, int(20 * factor_sombra)))
        grad_sombra.setColorAt(1.0, QColor(0, 0, 0, 0))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad_sombra)
        p.drawEllipse(QRectF(cx - w_sombra / 2.0, cy_sombra - h_sombra / 2.0, w_sombra, h_sombra))

        # 2. Dibujar personaje con transformaciones de flotación, respiración e inercia
        frame = self._obtener_frame_actual()
        if not frame.isNull():
            # Escala de respiración sutil (squash & stretch)
            escala_x = 1.0 + math.cos(self._t * 2.8) * 0.014
            escala_y = 1.0 - math.cos(self._t * 2.8) * 0.014

            ancho_pj = 146.0 * escala_x
            alto_pj = 154.0 * escala_y
            cy_pj = cy_sombra - (alto_pj / 2.0) - 2.0 + bob_y

            t = QTransform()
            t.translate(cx, cy_pj + alto_pj * 0.4)
            t.rotate(self._tilt_deg)
            t.translate(-cx, -(cy_pj + alto_pj * 0.4))

            p.setTransform(t)
            rect_pj = QRectF(cx - ancho_pj / 2.0, cy_pj - alto_pj / 2.0, ancho_pj, alto_pj)
            p.drawPixmap(rect_pj.toRect(), frame)
        else:
            p.setPen(QColor("#003D95"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "🤖 Utilín")

        p.end()


class MascotaWidget(QWidget):
    """Mascota de escritorio animada «UTILÍN» con arrastre libre y globo cómic."""

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
        self._ultimo_pos_raton: QPoint = QPoint()
        self._posicion_personalizada: QPoint | None = None

        self._nombre_actividad: str | None = None
        self._segundos_actividad: int = 0
        self._globo_visible: bool = True

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(4, 4, 4, 4)
        layout_raiz.setSpacing(0)
        layout_raiz.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Globo de texto tipo cómic con colita
        self.globo = GloboTextoWidget(self)
        if al_restaurar:
            self.globo.btn_abrir.clicked.connect(al_restaurar)
        if al_finalizar:
            self.globo.btn_finalizar.clicked.connect(al_finalizar)

        # Alias de compatibilidad
        self.lbl_reloj = self.globo.lbl_reloj
        self.lbl_actividad = self.globo.lbl_actividad
        self.btn_abrir = self.globo.btn_abrir
        self.btn_finalizar = self.globo.btn_finalizar

        layout_raiz.addWidget(self.globo, 0, Qt.AlignmentFlag.AlignCenter)

        # 2. Utilín animado (saludo, parpadeo, flotación y física)
        self.lbl_mascota = UtilinAnimadoWidget(self)
        self.lbl_mascota.setToolTip(
            "Utilín — Mascota de Control de Tiempos\n"
            "• Arrastra para moverme a cualquier sitio\n"
            "• Doble clic para abrir la aplicación\n"
            "• Clic derecho para opciones"
        )
        layout_raiz.addWidget(self.lbl_mascota, 0, Qt.AlignmentFlag.AlignCenter)

        self.adjustSize()
        self._posicionar_defecto()
        self._instalar_filtro_arrastre()

    def _posicionar_defecto(self) -> None:
        """Ubica a Utilín en la esquina inferior derecha o en su posición guardada."""
        if self._posicion_personalizada is not None:
            self.move(self._posicion_personalizada)
            return

        pantalla = QApplication.primaryScreen()
        if pantalla:
            geom = pantalla.availableGeometry()
            ancho = self.sizeHint().width() or 214
            alto = self.sizeHint().height() or 270
            x = max(10, geom.right() - ancho - 30)
            y = max(10, geom.bottom() - alto - 35)
            self.move(x, y)

    def restablecer_posicion(self) -> None:
        """Vuelve a colocar a Utilín en la esquina inferior derecha habitual."""
        self._posicion_personalizada = None
        self._posicionar_defecto()

    def mostrar_mascota(self) -> None:
        """Muestra a Utilín en el escritorio con animación activa."""
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
        """Actualiza el globo de texto con el cronómetro y tarea en curso."""
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
        """Muestra u oculta el globo de texto cómic."""
        self._globo_visible = not self._globo_visible
        self.globo.setVisible(self._globo_visible)
        self.adjustSize()

    # ------------------------------------------------------------------
    # Arrastre suave con física de inercia e inclinación
    # ------------------------------------------------------------------

    def _instalar_filtro_arrastre(self) -> None:
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
                self._ultimo_pos_raton = ev.globalPosition().toPoint()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.lbl_mascota.activar_saltito()
                return False

        elif t == QEvent.Type.MouseMove:
            if self._arrastrando:
                ev_m: QMouseEvent = evento
                pos_actual = ev_m.globalPosition().toPoint()
                delta_global = pos_actual - self._drag_start_pos
                nueva_pos = self._widget_start_pos + delta_global
                self.move(nueva_pos)
                self._posicion_personalizada = nueva_pos

                # Calcular inclinación por velocidad de arrastre horizontal
                vx = float(pos_actual.x() - self._ultimo_pos_raton.x())
                self._ultimo_pos_raton = pos_actual
                inclinacion = vx * 0.75
                self.lbl_mascota.set_inclinacion_arrastre(inclinacion)
                return True

        elif t == QEvent.Type.MouseButtonRelease:
            if self._arrastrando:
                self._arrastrando = False
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self._posicion_personalizada = self.pos()
                self.lbl_mascota.soltar_arrastre()

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
        """Menú contextual de Utilín."""
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
