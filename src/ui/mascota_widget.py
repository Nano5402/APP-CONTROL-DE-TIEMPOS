"""Mascota de escritorio «UTILÍN» en 3D ultra-pulida con físicas fluidas.

Muestra la imagen 3D original de Utilín con su máxima nitidez y textura de felpa,
combinada con:
- Flotación y levitación continua (bobbing suave).
- Respiración elástica orgánica (squash & stretch sutil).
- Física de inercia e inclinación en vuelo al arrastrar por la pantalla.
- Rebote elástico (hop) de respuesta táctil al hacer clic.
- Sombra elíptica 3D dinámica en el suelo que reacciona a la altura.
- Globo de texto cómic vectorial con colita apuntando a su cabeza.
- Arrastre libre universal y restauración instantánea con doble clic.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
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
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import rutas
from ui.iconos import configurar_boton
from ui.mini_widget import formatear_reloj_hms


class HiloConsultaIA(QThread):
    """Hilo secundario para no bloquear la interfaz gráfica al consultar a la IA."""

    respuesta_lista = Signal(object)

    def __init__(self, srv_ia: Any, mensaje: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.srv_ia = srv_ia
        self.mensaje = mensaje

    def run(self) -> None:
        try:
            res = self.srv_ia.consultar(self.mensaje)
            self.respuesta_lista.emit(res)
        except Exception as e:
            from services.ia_utilin import RespuestaUtilin

            self.respuesta_lista.emit(RespuestaUtilin(mensaje=f"Lo siento, ocurrió un error: {e}"))


class GloboTextoWidget(QWidget):
    """Globo de diálogo tipo cómic vectorial moderno con cuerpo redondeado, sombra y chat IA."""

    def __init__(
        self,
        parent: QWidget | None = None,
        al_cerrar: Callable[[], None] | None = None,
        al_pausar: Callable[[], None] | None = None,
        al_enviar_chat: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.al_cerrar = al_cerrar
        self.al_pausar = al_pausar
        self.al_enviar_chat = al_enviar_chat
        self._modo_chat: bool = False
        self._modo_respuesta_ia: bool = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(252)
        self.setMinimumHeight(96)

        self.layout_globo = QVBoxLayout(self)
        self.layout_globo.setContentsMargins(14, 9, 14, 22)
        self.layout_globo.setSpacing(3)
        self.layout_globo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Fila superior: Título / Reloj y botones auxiliares
        self.fila_cabecera = QHBoxLayout()
        self.fila_cabecera.setContentsMargins(0, 0, 0, 0)
        self.fila_cabecera.setSpacing(4)

        # Botón volver al cronómetro (visible solo cuando se muestra respuesta IA)
        self.btn_volver_reloj = QPushButton("⏱", self)
        self.btn_volver_reloj.setFixedSize(16, 16)
        self.btn_volver_reloj.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_volver_reloj.setToolTip("Volver al cronómetro")
        self.btn_volver_reloj.setStyleSheet(
            "QPushButton { background: transparent; color: #003D95; border: none; font-size: 11px; font-weight: bold; border-radius: 8px; } "
            "QPushButton:hover { background-color: #EFF6FF; }"
        )
        self.btn_volver_reloj.setVisible(False)
        self.btn_volver_reloj.clicked.connect(self.volver_a_cronometro)
        self.fila_cabecera.addWidget(self.btn_volver_reloj)

        # Espaciador dummy para centrar el título
        self.espaciador_izq = QWidget(self)
        self.espaciador_izq.setFixedSize(16, 16)
        self.fila_cabecera.addWidget(self.espaciador_izq)

        # Línea 1: Reloj o Saludo destacado
        self.lbl_reloj = QLabel("👋 ¡Hola, soy Utilín!", self)
        f_reloj = self.lbl_reloj.font()
        f_reloj.setPointSize(11)
        f_reloj.setWeight(QFont.Weight.ExtraBold)
        self.lbl_reloj.setFont(f_reloj)
        self.lbl_reloj.setStyleSheet("color: #003D95; background: transparent; border: none;")
        self.lbl_reloj.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fila_cabecera.addWidget(self.lbl_reloj, 1)

        # Botón sutil de cerrar (ocultar globo de texto)
        self.btn_cerrar = QPushButton("✕", self)
        self.btn_cerrar.setFixedSize(16, 16)
        self.btn_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cerrar.setToolTip("Ocultar globo de texto")
        self.btn_cerrar.setStyleSheet(
            "QPushButton { background: transparent; color: #94A3B8; border: none; font-size: 11px; font-weight: bold; border-radius: 8px; } "
            "QPushButton:hover { background-color: #F1F5F9; color: #475569; }"
        )
        if self.al_cerrar:
            self.btn_cerrar.clicked.connect(self.al_cerrar)
        self.fila_cabecera.addWidget(self.btn_cerrar)

        self.layout_globo.addLayout(self.fila_cabecera)

        # Línea 2: Tarea en curso o texto secundario (sin quiebres forzados)
        self.lbl_actividad = QLabel("Doble clic para abrir app", self)
        self.lbl_actividad.setWordWrap(False)
        self.lbl_actividad.setMaximumWidth(224)
        self.lbl_actividad.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_actividad.setStyleSheet(
            "color: #64748B; font-size: 10.5px; font-weight: 500; background: transparent; border: none;"
        )
        self.layout_globo.addWidget(self.lbl_actividad)

        # Línea 3: Botones de acción estilo píldora moderna
        self.fila_acciones = QHBoxLayout()
        self.fila_acciones.setSpacing(6)
        self.fila_acciones.setContentsMargins(0, 3, 0, 0)
        self.fila_acciones.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_abrir = QPushButton("Abrir app", self)
        self.btn_abrir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abrir.setStyleSheet(
            "QPushButton { background-color: #003D95; color: #FFFFFF; border: 1px solid #002D6E; "
            "border-radius: 12px; padding: 3px 12px; font-size: 10px; font-weight: 700; } "
            "QPushButton:hover { background-color: #0284C7; border-color: #0284C7; color: #FFFFFF; } "
            "QPushButton:pressed { background-color: #002255; }"
        )
        configurar_boton(self.btn_abrir, "play", color="#FFFFFF", tamano=10)
        self.fila_acciones.addWidget(self.btn_abrir)

        # Botón Pausar rápido
        self.btn_pausar = QPushButton("Pausar", self)
        self.btn_pausar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pausar.setStyleSheet(
            "QPushButton { background-color: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; "
            "border-radius: 12px; padding: 3px 10px; font-size: 10px; font-weight: 700; } "
            "QPushButton:hover { background-color: #FDE68A; color: #78350F; border-color: #FCD34D; } "
            "QPushButton:pressed { background-color: #F59E0B; color: #FFFFFF; }"
        )
        configurar_boton(self.btn_pausar, "pause", color="#92400E", tamano=10)
        self.btn_pausar.setVisible(False)
        if self.al_pausar:
            self.btn_pausar.clicked.connect(self.al_pausar)
        self.fila_acciones.addWidget(self.btn_pausar)

        # Botón Finalizar
        self.btn_finalizar = QPushButton("Finalizar", self)
        self.btn_finalizar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_finalizar.setStyleSheet(
            "QPushButton { background-color: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; "
            "border-radius: 12px; padding: 3px 10px; font-size: 10px; font-weight: 700; } "
            "QPushButton:hover { background-color: #DC2626; color: #FFFFFF; border-color: #DC2626; } "
            "QPushButton:pressed { background-color: #B91C1C; color: #FFFFFF; }"
        )
        configurar_boton(self.btn_finalizar, "stop", color="#DC2626", tamano=10)
        self.btn_finalizar.setVisible(False)
        self.fila_acciones.addWidget(self.btn_finalizar)

        # Botón alternar chat IA
        self.btn_chat = QPushButton("💬", self)
        self.btn_chat.setFixedSize(22, 22)
        self.btn_chat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_chat.setToolTip("Hablar con Utilín IA (Gemma)")
        self.btn_chat.setStyleSheet(
            "QPushButton { background-color: #EFF6FF; color: #003D95; border: 1px solid #BFDBFE; "
            "border-radius: 11px; font-size: 10px; font-weight: bold; } "
            "QPushButton:hover { background-color: #DBEAFE; color: #1E40AF; }"
        )
        self.btn_chat.clicked.connect(self.alternar_modo_chat)
        self.fila_acciones.addWidget(self.btn_chat)

        self.layout_globo.addLayout(self.fila_acciones)

        # Línea 4: Campo de entrada de chat IA (oculto por defecto)
        self.widget_chat = QWidget(self)
        self.widget_chat.setVisible(False)
        layout_input_chat = QHBoxLayout(self.widget_chat)
        layout_input_chat.setContentsMargins(0, 3, 0, 0)
        layout_input_chat.setSpacing(4)

        self.txt_pregunta = QLineEdit(self.widget_chat)
        self.txt_pregunta.setPlaceholderText("Escribe a Utilín... (Enter)")
        self.txt_pregunta.setStyleSheet(
            "QLineEdit { background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 10px; "
            "padding: 2px 8px; font-size: 10px; color: #0F172A; } "
            "QLineEdit:focus { border-color: #003D95; background-color: #FFFFFF; }"
        )
        self.txt_pregunta.returnPressed.connect(self._al_enviar_pregunta)
        layout_input_chat.addWidget(self.txt_pregunta, 1)

        self.btn_enviar_chat = QPushButton("➤", self.widget_chat)
        self.btn_enviar_chat.setFixedSize(20, 20)
        self.btn_enviar_chat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_enviar_chat.setStyleSheet(
            "QPushButton { background-color: #003D95; color: #FFFFFF; border: none; border-radius: 10px; font-size: 9px; font-weight: bold; } "
            "QPushButton:hover { background-color: #0284C7; }"
        )
        self.btn_enviar_chat.clicked.connect(self._al_enviar_pregunta)
        layout_input_chat.addWidget(self.btn_enviar_chat)

        self.layout_globo.addWidget(self.widget_chat)

    def alternar_modo_chat(self) -> None:
        """Abre o cierra la barra de chat de Utilín."""
        self._modo_chat = not self._modo_chat
        self.widget_chat.setVisible(self._modo_chat)
        if self._modo_chat:
            self.txt_pregunta.setFocus()
            # Si el widget padre tiene la mascota, dar saltito de atención
            padre = self.parent()
            if padre and hasattr(padre, "lbl_mascota"):
                padre.lbl_mascota.activar_saltito()
        self.adjustSize()

    def _al_enviar_pregunta(self) -> None:
        texto = self.txt_pregunta.text().strip()
        if not texto:
            return
        self.mostrar_pensando()
        if self.al_enviar_chat:
            self.al_enviar_chat(texto)
        self.txt_pregunta.clear()

    def mostrar_pensando(self) -> None:
        self._modo_respuesta_ia = True
        self.espaciador_izq.setVisible(False)
        self.btn_volver_reloj.setVisible(True)
        self.lbl_reloj.setText("💭 Utilín pensando...")
        self.lbl_reloj.setStyleSheet(
            "color: #0284C7; font-size: 11px; font-weight: 800; background: transparent; border: none;"
        )
        self.lbl_actividad.setText("Analizando tu solicitud...")
        self.lbl_actividad.setWordWrap(True)
        self.adjustSize()

    def mostrar_respuesta_ia(self, mensaje: str) -> None:
        self._modo_respuesta_ia = True
        self.espaciador_izq.setVisible(False)
        self.btn_volver_reloj.setVisible(True)
        self.lbl_reloj.setText("🤖 Utilín:")
        self.lbl_reloj.setStyleSheet(
            "color: #003D95; font-size: 11.5px; font-weight: 800; background: transparent; border: none;"
        )
        self.lbl_actividad.setText(mensaje)
        self.lbl_actividad.setWordWrap(True)
        self.adjustSize()

    def volver_a_cronometro(self) -> None:
        self._modo_respuesta_ia = False
        self.btn_volver_reloj.setVisible(False)
        self.espaciador_izq.setVisible(True)
        self.lbl_actividad.setWordWrap(False)
        p = self.parent()
        if p and hasattr(p, "actualizar_estado"):
            p.actualizar_estado(
                getattr(p, "_nombre_actividad", None),
                getattr(p, "_segundos_actividad", 0),
            )
        self.adjustSize()

    def paintEvent(self, event) -> None:
        """Dibuja el globo de diálogo vectorial continuo sin costuras, con sombra suave y degradado perla."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        alto_cola = 11.0
        ancho_cola = 16.0
        r = 14.0

        rect = QRectF(5.0, 4.0, w - 10.0, h - alto_cola - 6.0)

        # Contorno único continuo (evita costuras visibles o artefactos de unión)
        path = QPainterPath()
        path.moveTo(rect.left() + r, rect.top())
        path.lineTo(rect.right() - r, rect.top())
        path.arcTo(rect.right() - 2 * r, rect.top(), 2 * r, 2 * r, 90, -90)
        path.lineTo(rect.right(), rect.bottom() - r)
        path.arcTo(rect.right() - 2 * r, rect.bottom() - 2 * r, 2 * r, 2 * r, 0, -90)

        cx = rect.center().x()
        hw = ancho_cola / 2.0
        path.lineTo(cx + hw, rect.bottom())
        path.quadTo(cx + 2.5, rect.bottom() + alto_cola * 0.6, cx, rect.bottom() + alto_cola)
        path.quadTo(cx - 2.5, rect.bottom() + alto_cola * 0.6, cx - hw, rect.bottom())

        path.lineTo(rect.left() + r, rect.bottom())
        path.arcTo(rect.left(), rect.bottom() - 2 * r, 2 * r, 2 * r, 270, -90)
        path.lineTo(rect.left(), rect.top() + r)
        path.arcTo(rect.left(), rect.top(), 2 * r, 2 * r, 180, -90)
        path.closeSubpath()

        # Sombra suave multicapa moderna
        for offset, alpha in [(4, 6), (3, 10), (2, 16), (1, 24)]:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(15, 23, 42, alpha))
            p.save()
            p.translate(0, offset)
            p.drawPath(path)
            p.restore()

        # Fondo con sutil degradado blanco a perla y borde refinado
        grad = QLinearGradient(0, 0, 0, rect.bottom())
        grad.setColorAt(0.0, QColor(255, 255, 255))
        grad.setColorAt(1.0, QColor(248, 250, 252))
        p.setBrush(grad)
        p.setPen(QPen(QColor("#CBD5E1"), 1.2))
        p.drawPath(path)
        p.end()


def _dibujar_corazon(p: QPainter, cx: float, cy: float, tamano: float = 14.0, alpha: int = 255) -> None:
    """Dibuja un corazón vectorial brillante flotante."""
    path = QPainterPath()
    r = tamano
    path.moveTo(cx, cy + r * 0.75)
    path.cubicTo(cx - r * 1.3, cy - r * 0.3, cx - r * 1.3, cy - r * 1.25, cx, cy - r * 0.6)
    path.cubicTo(cx + r * 1.3, cy - r * 1.25, cx + r * 1.3, cy - r * 0.3, cx, cy + r * 0.75)

    grad = QLinearGradient(cx, cy - r, cx, cy + r)
    grad.setColorAt(0.0, QColor(244, 63, 94, alpha))
    grad.setColorAt(1.0, QColor(225, 29, 72, alpha))
    p.setPen(QPen(QColor(190, 18, 60, alpha), 1.0))
    p.setBrush(grad)
    p.drawPath(path)

    # Brillo reflejo superior
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, int(alpha * 0.7)))
    p.drawEllipse(QPointF(cx - r * 0.45, cy - r * 0.45), r * 0.25, r * 0.18)


def _dibujar_estrella(p: QPainter, cx: float, cy: float, radio: float = 10.0, alpha: int = 255) -> None:
    """Dibuja una estrellita dorada brillante de 4 puntas."""
    path = QPainterPath()
    path.moveTo(cx, cy - radio)
    path.quadTo(cx, cy, cx + radio, cy)
    path.quadTo(cx, cy, cx, cy + radio)
    path.quadTo(cx, cy, cx - radio, cy)
    path.quadTo(cx, cy, cx, cy - radio)
    p.setPen(QPen(QColor(217, 119, 6, alpha), 1.0))
    p.setBrush(QColor(251, 191, 36, alpha))
    p.drawPath(path)


def _dibujar_zzz(p: QPainter, cx: float, cy: float, sz: float = 12.0, alpha: int = 255) -> None:
    """Dibuja una letra Z estilizada de siesta."""
    path = QPainterPath()
    w, h = sz * 0.75, sz
    path.moveTo(cx - w / 2.0, cy - h / 2.0)
    path.lineTo(cx + w / 2.0, cy - h / 2.0)
    path.lineTo(cx - w / 2.0, cy + h / 2.0)
    path.lineTo(cx + w / 2.0, cy + h / 2.0)
    p.setPen(
        QPen(
            QColor(99, 102, 241, alpha),
            max(1.8, sz * 0.18),
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)


class UtilinRender3DWidget(QWidget):
    """Lienzo de mascota virtual 3D con ciclo de caminata, expresiones, siesta y físicas de rebote."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(176, 196)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._t: float = 0.0
        self._tilt_deg: float = 0.0
        self._tilt_objetivo: float = 0.0
        self._jump_y: float = 0.0

        # Físicas de caminata al arrastrar o paseo libre
        self._esta_caminando: bool = False
        self._direccion_caminar: int = 1  # 1 = derecha, -1 = izquierda
        self._distancia_caminar: float = 0.0
        self._tiempo_quieto: float = 0.0

        # Animación de saludo periódico (cada 10 segundos)
        self._temporizador_saludo: float = 0.0
        self._intervalo_saludo: float = 10.0
        self._saludando: bool = False
        self._tiempo_saludo: float = 0.0
        self._duracion_saludo: float = 2.4

        # Estados de mascota virtual
        self._durmiendo: bool = False
        self._tiempo_siesta: float = 0.0
        self._tiene_actividad: bool = False
        self._pensando: bool = False

        # Sistema de emotes flotantes estilo VS Code Pets
        self._emotes: list[dict] = []

        # Cargar poses 3D ultra-nítidas
        d = rutas.carpeta_assets()
        p_neutral = d / "mascota_codex.png"
        p_wave = d / "mascota_wave.png"
        p_walk1 = d / "mascota_walk1.png"
        p_walk2 = d / "mascota_walk2.png"

        self._pix_neutral = QPixmap(str(p_neutral)) if p_neutral.is_file() else QPixmap()
        self._pix_wave = QPixmap(str(p_wave)) if p_wave.is_file() else self._pix_neutral
        self._pix_walk1 = QPixmap(str(p_walk1)) if p_walk1.is_file() else self._pix_neutral
        self._pix_walk2 = QPixmap(str(p_walk2)) if p_walk2.is_file() else self._pix_neutral

        # Timer de física y animación fluido (30ms / ~33 FPS con mínimo consumo)
        self._timer_anim = QTimer(self)
        self._timer_anim.setInterval(30)
        self._timer_anim.timeout.connect(self._actualizar_fisicas)
        self._timer_anim.start()

    def pixmap(self) -> QPixmap:
        """Devuelve el pixmap 3D neutral de Utilín para compatibilidad."""
        return self._pix_neutral

    def set_inclinacion_arrastre(self, inclinacion_grados: float) -> None:
        """Aplica inclinación en el aire cuando se arrastra por la pantalla."""
        self._tilt_objetivo = max(-14.0, min(14.0, inclinacion_grados))

    def registrar_movimiento(self, vx: float) -> None:
        """Registra el desplazamiento horizontal para cambiar a pose caminando (izq/der)."""
        self.set_inclinacion_arrastre(vx * 0.70)
        self._tiempo_quieto = 0.0

        if vx < -0.8:
            self._direccion_caminar = -1  # Caminando a la izquierda
            self._esta_caminando = True
            self._distancia_caminar += abs(vx)
            self._saludando = False
            self._temporizador_saludo = 0.0
            if self._durmiendo:
                self.despertar()
        elif vx > 0.8:
            self._direccion_caminar = 1   # Caminando a la derecha
            self._esta_caminando = True
            self._distancia_caminar += abs(vx)
            self._saludando = False
            self._temporizador_saludo = 0.0
            if self._durmiendo:
                self.despertar()

    def soltar_arrastre(self) -> None:
        """Restablece la pose de pie y la inclinación suavemente con rebote elástico."""
        self._esta_caminando = False
        self._tilt_objetivo = 0.0
        self._tiempo_quieto = 0.0

    def activar_saltito(self) -> None:
        """Efecto rebote táctil (hop) al hacer clic con corazoncito amoroso."""
        self._jump_y = -9.0
        self._temporizador_saludo = 0.0
        if self._durmiendo:
            self.despertar()
        else:
            self.agregar_emote("heart")

    def agregar_emote(self, tipo: str = "heart", offset_x: float = 0.0) -> None:
        """Genera un emote flotante estilo mascota virtual que asciende y se desvanece."""
        cx = self.width() / 2.0 + offset_x
        cy = self.height() - 14.0 - 154.0 * 0.55
        self._emotes.append({
            "tipo": tipo,
            "x": cx,
            "y": cy,
            "vx": random.uniform(-6.0, 6.0),
            "vy": random.uniform(-28.0, -36.0),
            "alpha": 255.0,
            "tamano": 13.0 if tipo == "heart" else (11.0 if tipo == "star" else 12.0),
            "vida": 0.0,
            "max_vida": 1.4,
        })

    def set_durmiendo(self, durmiendo: bool) -> None:
        """Activa o desactiva la siesta de Utilín."""
        self._durmiendo = durmiendo
        self._tiempo_siesta = 0.0
        if durmiendo:
            self._saludando = False
            self._esta_caminando = False

    def despertar(self) -> None:
        """Despierta a Utilín con sorpresa y un salto alegre."""
        if self._durmiendo:
            self._durmiendo = False
            self._jump_y = -9.0
            self.agregar_emote("star")
            self.forzar_saludo()

    def set_pensando(self, pensando: bool) -> None:
        """Activa o desactiva el modo de cálculo/pensamiento IA."""
        self._pensando = pensando
        if pensando:
            self._saludando = False
            self._durmiendo = False

    def set_tiene_actividad(self, tiene: bool) -> None:
        """Actualiza si hay una actividad/cronómetro en ejecución."""
        self._tiene_actividad = tiene
        if tiene and self._durmiendo:
            self.despertar()

    def activar_eureka(self) -> None:
        """Dispara reacción alegre de respuesta encontrada: salto, estrellitas y saludo."""
        self._pensando = False
        self._jump_y = -10.0
        self.agregar_emote("star", -16.0)
        self.agregar_emote("star", 16.0)
        self.forzar_saludo()

    def forzar_saludo(self) -> None:
        """Dispara de inmediato la animación de saludo amigable."""
        self._saludando = True
        self._tiempo_saludo = 0.0
        self._temporizador_saludo = 0.0

    def _actualizar_fisicas(self) -> None:
        dt = 0.030
        self._t += dt

        # Actualizar emotes flotantes
        for em in self._emotes:
            em["x"] += em["vx"] * dt
            em["y"] += em["vy"] * dt
            em["vida"] += dt
            em["alpha"] = max(0.0, 255.0 * (1.0 - (em["vida"] / em["max_vida"])))
        self._emotes = [em for em in self._emotes if em["vida"] < em["max_vida"]]

        # Si está durmiendo, emitir burbujitas Zzz periódicas
        if self._durmiendo:
            self._tiempo_siesta += dt
            if self._tiempo_siesta >= 1.6:
                self._tiempo_siesta = 0.0
                self.agregar_emote("zzz", offset_x=random.uniform(8.0, 24.0))

        # Control del saludo periódico cada 12 segundos (si está despierto y quieto)
        if not self._esta_caminando and not self._pensando and not self._durmiendo:
            if not self._saludando:
                self._temporizador_saludo += dt
                if self._temporizador_saludo >= self._intervalo_saludo:
                    self._saludando = True
                    self._tiempo_saludo = 0.0
                    self._temporizador_saludo = 0.0
            else:
                self._tiempo_saludo += dt
                if self._tiempo_saludo >= self._duracion_saludo:
                    self._saludando = False
                    self._tiempo_saludo = 0.0
                    self._temporizador_saludo = 0.0
        else:
            if self._esta_caminando:
                self._tiempo_quieto += dt
                if self._tiempo_quieto > 0.22:
                    self._esta_caminando = False

        # Amortiguación elástica de inclinación
        self._tilt_deg += (self._tilt_objetivo - self._tilt_deg) * 0.25

        # Amortiguación del salto al hacer clic
        if abs(self._jump_y) > 0.1:
            self._jump_y *= 0.85
        else:
            self._jump_y = 0.0

        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cx = self.width() / 2.0
        cy_sombra = self.height() - 14.0

        step_y = 0.0
        waddle_tilt = 0.0
        wave_tilt = 0.0

        if self._esta_caminando:
            # Física de paso al caminar: rebote de zancada y vaivén lateral
            step_y = -abs(math.sin(self._distancia_caminar * 0.11)) * 4.8
            waddle_tilt = math.sin(self._distancia_caminar * 0.11) * 3.8
            bob_y = step_y + self._jump_y
        elif self._durmiendo:
            # Respiración más lenta y relajada de siesta
            bob_y = math.sin(self._t * 1.4) * 1.8 + self._jump_y
        elif self._pensando:
            # Flotación analítica
            bob_y = math.sin(self._t * 3.6) * 3.0 + self._jump_y
        elif self._saludando:
            # Pequeño rebote alegre durante el saludo
            wave_hop = -abs(math.sin(self._tiempo_saludo * 6.0)) * 2.8
            wave_tilt = math.sin(self._tiempo_saludo * 12.0) * 5.5
            bob_y = math.sin(self._t * 2.4) * 3.5 + wave_hop + self._jump_y
        else:
            # Flotación / levitación idle suave
            bob_y = math.sin(self._t * 2.4) * 4.2 + self._jump_y

        # Sombra de contacto 3D natural en el suelo
        factor_sombra = max(0.58, min(1.15, 1.0 - (bob_y / 24.0)))
        w_sombra = (88.0 if self._esta_caminando else 94.0) * factor_sombra
        h_sombra = 12.0 * factor_sombra

        grad_sombra = QRadialGradient(cx, cy_sombra, w_sombra / 2.0)
        grad_sombra.setColorAt(0.0, QColor(0, 0, 0, int(50 * factor_sombra)))
        grad_sombra.setColorAt(0.55, QColor(0, 0, 0, int(18 * factor_sombra)))
        grad_sombra.setColorAt(1.0, QColor(0, 0, 0, 0))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad_sombra)
        p.drawEllipse(QRectF(cx - w_sombra / 2.0, cy_sombra - h_sombra / 2.0, w_sombra, h_sombra))

        # Selección de sprite y proporciones según estado
        pix_a_dibujar = self._pix_neutral
        es_caminata = False
        escala_x_respiracion = 1.0
        escala_y_respiracion = 1.0

        if self._esta_caminando:
            es_caminata = True
            paso_idx = int(self._distancia_caminar / 24.0) % 2
            pix_a_dibujar = self._pix_walk1 if paso_idx == 0 else self._pix_walk2
            ancho_base = 122.0
            alto_base = 154.0
        elif self._saludando:
            fase_wave = math.sin(self._tiempo_saludo * 11.0)
            if fase_wave > -0.15 and not self._pix_wave.isNull():
                pix_a_dibujar = self._pix_wave
                ancho_base = 145.0
                alto_base = 154.0
            else:
                pix_a_dibujar = self._pix_neutral
                ancho_base = 146.0
                alto_base = 154.0
        elif self._durmiendo:
            # Postura relajada de siesta
            escala_x_respiracion = 1.04 - math.sin(self._t * 1.4) * 0.015
            escala_y_respiracion = 0.96 + math.sin(self._t * 1.4) * 0.015
            pix_a_dibujar = self._pix_neutral
            ancho_base = 146.0
            alto_base = 154.0
        else:
            # Respiración elástica en reposo
            escala_x_respiracion = 1.0 + math.cos(self._t * 2.4) * 0.012
            escala_y_respiracion = 1.0 - math.cos(self._t * 2.4) * 0.012
            pix_a_dibujar = self._pix_neutral
            ancho_base = 146.0
            alto_base = 154.0

        if not pix_a_dibujar.isNull():
            ancho_pj = ancho_base * escala_x_respiracion
            alto_pj = alto_base * escala_y_respiracion
            cy_pj = cy_sombra - (alto_pj / 2.0) - 2.0 + bob_y

            rotacion_total = self._tilt_deg + waddle_tilt + wave_tilt

            t = QTransform()
            t.translate(cx, cy_pj + alto_pj * 0.40)
            if es_caminata and self._direccion_caminar == -1:
                t.scale(-1.0, 1.0)
            t.rotate(rotacion_total)
            t.translate(-cx, -(cy_pj + alto_pj * 0.40))

            p.setTransform(t)
            rect_pj = QRectF(cx - ancho_pj / 2.0, cy_pj - alto_pj / 2.0, ancho_pj, alto_pj)
            p.drawPixmap(rect_pj.toRect(), pix_a_dibujar)
            p.resetTransform()

            # Dibujar emotes flotantes activos (Corazoncitos, Estrellitas, Zzz)
            for em in self._emotes:
                tipo = em["tipo"]
                alpha = int(em["alpha"])
                if tipo == "heart":
                    _dibujar_corazon(p, em["x"], em["y"], em["tamano"], alpha)
                elif tipo == "star":
                    _dibujar_estrella(p, em["x"], em["y"], em["tamano"], alpha)
                elif tipo == "zzz":
                    _dibujar_zzz(p, em["x"], em["y"], em["tamano"], alpha)
        else:
            p.setPen(QColor("#003D95"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "🤖 Utilín")

        p.end()


class MascotaWidget(QWidget):
    """Mascota de escritorio «UTILÍN» con arrastre libre a cualquier monitor y Asistente IA."""

    def __init__(
        self,
        *,
        al_restaurar: Callable[[], None] | None = None,
        al_finalizar: Callable[[], None] | None = None,
        al_pausar: Callable[[], None] | None = None,
        al_cerrar_definitivo: Callable[[], None] | None = None,
        srv_ia: Any = None,
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
        self.al_pausar = al_pausar
        self.al_cerrar_definitivo = al_cerrar_definitivo
        self.srv_ia = srv_ia
        self._hilos_ia: list[QThread] = []

        self.setWindowTitle("Utilín · Mascota de Control de Tiempos")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._arrastrando: bool = False
        self._drag_start_pos: QPoint = QPoint()
        self._widget_start_pos: QPoint = QPoint()
        self._ultimo_pos_raton: QPoint = QPoint()
        self._posicion_personalizada: QPoint | None = None

        # Autonomía de mascota virtual (estilo VS Code Pets)
        self._permitir_paseo_libre: bool = True
        self._caminando_autonomo: bool = False
        self._destino_x: int = 0
        self._temporizador_decision: float = 0.0
        self._tiempo_inactivo: float = 0.0
        self._cayendo: bool = False
        self._velocidad_caida: float = 0.0
        self._y_suelo: int = 0
        self._jugando_pelota: bool = False
        self._paso_pelota: int = 0
        self._origen_pelota_x: int = 0

        self._nombre_actividad: str | None = None
        self._segundos_actividad: int = 0
        self._globo_visible: bool = True

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(4, 4, 4, 4)
        layout_raiz.setSpacing(0)
        layout_raiz.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Globo de texto tipo cómic con colita y asistente IA
        self.globo = GloboTextoWidget(
            parent=self,
            al_cerrar=self.alternar_globo,
            al_pausar=al_pausar,
            al_enviar_chat=self._procesar_mensaje_chat,
        )
        if al_restaurar:
            self.globo.btn_abrir.clicked.connect(al_restaurar)
        if al_finalizar:
            self.globo.btn_finalizar.clicked.connect(al_finalizar)

        # Alias de compatibilidad
        self.lbl_reloj = self.globo.lbl_reloj
        self.lbl_actividad = self.globo.lbl_actividad
        self.btn_abrir = self.globo.btn_abrir
        self.btn_finalizar = self.globo.btn_finalizar
        self.btn_pausar = self.globo.btn_pausar
        self.btn_chat = self.globo.btn_chat

        layout_raiz.addWidget(self.globo, 0, Qt.AlignmentFlag.AlignCenter)

        # 2. Utilín con render 3D original y físicas fluidas
        self.lbl_mascota = UtilinRender3DWidget(self)
        self.lbl_mascota.setToolTip(
            "Utilín — Mascota Virtual de Control de Tiempos\n"
            "• Arrastra para moverme a cualquier sitio (¡caigo con gravedad!)\n"
            "• Doble clic para abrir la aplicación\n"
            "• Clic derecho para jugar, acariciar o hablar con IA"
        )
        layout_raiz.addWidget(self.lbl_mascota, 0, Qt.AlignmentFlag.AlignCenter)

        # Timer de comportamiento autónomo continuo
        self._timer_autonomia = QTimer(self)
        self._timer_autonomia.setInterval(30)
        self._timer_autonomia.timeout.connect(self._actualizar_autonomia)
        self._timer_autonomia.start()

        self.adjustSize()
        self._posicionar_defecto()
        self._instalar_filtro_arrastre()

    def _procesar_mensaje_chat(self, pregunta: str) -> None:
        """Envía la pregunta al servicio de IA en segundo plano sin congelar la interfaz."""
        self.globo.mostrar_pensando()
        self.lbl_mascota.set_pensando(True)

        if not self.srv_ia:
            self.lbl_mascota.set_pensando(False)
            self.globo.mostrar_respuesta_ia("Servicio de IA no inicializado.")
            return

        hilo = HiloConsultaIA(self.srv_ia, pregunta, self)
        hilo.respuesta_lista.connect(self._al_recibir_respuesta_ia)
        self._hilos_ia.append(hilo)
        hilo.start()

    def _al_recibir_respuesta_ia(self, respuesta: Any) -> None:
        """Muestra la respuesta en el globo y hace que Utilín celebre con eureka bot."""
        self.lbl_mascota.set_pensando(False)
        self.lbl_mascota.activar_eureka()
        mensaje = getattr(respuesta, "mensaje", str(respuesta))
        self.globo.mostrar_respuesta_ia(mensaje)

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
        """Muestra a Utilín en el escritorio con sus físicas activas."""
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
        self.lbl_mascota.set_tiene_actividad(bool(nombre_actividad))

        # Si está respondiendo la IA, no sobrescribir el texto de la respuesta
        if not self.globo._modo_respuesta_ia:
            if nombre_actividad:
                tiempo_str = formatear_reloj_hms(self._segundos_actividad)
                self.lbl_reloj.setText(f"⏱ {tiempo_str}")
                self.lbl_reloj.setStyleSheet(
                    "color: #003D95; font-size: 13px; font-weight: 800; background: transparent; border: none;"
                )

                texto_nom = nombre_actividad.strip()
                if len(texto_nom) > 28:
                    self.lbl_actividad.setText(f"{texto_nom[:25]}…")
                else:
                    self.lbl_actividad.setText(texto_nom)
                self.lbl_actividad.setToolTip(f"Actividad en curso: {nombre_actividad}")
                self.btn_finalizar.setVisible(True)
                self.btn_pausar.setVisible(True)
            else:
                self.lbl_reloj.setText("👋 ¡Hola, soy Utilín!")
                self.lbl_reloj.setStyleSheet(
                    "color: #003D95; font-size: 11.5px; font-weight: 800; background: transparent; border: none;"
                )
                self.lbl_actividad.setText("Doble clic para abrir app")
                self.lbl_actividad.setToolTip("Sin actividad en curso · Doble clic para abrir Control de Tiempos")
                self.btn_finalizar.setVisible(False)
                self.btn_pausar.setVisible(False)

        self.globo.setVisible(self._globo_visible)
        self.adjustSize()

    def alternar_globo(self) -> None:
        """Muestra u oculta el globo de texto cómic."""
        self._globo_visible = not self._globo_visible
        self.globo.setVisible(self._globo_visible)
        self.adjustSize()

    # ------------------------------------------------------------------
    # Autonomía de Mascota Virtual (estilo VS Code Pets)
    # ------------------------------------------------------------------

    def _actualizar_autonomia(self) -> None:
        """Ciclo de vida autónomo: gravedad, paseos, siestas y juego."""
        dt = 0.030

        # Si el usuario lo está arrastrando con el ratón
        if self._arrastrando:
            self._tiempo_inactivo = 0.0
            return

        # 1. Física de caída libre con gravedad al soltarlo en el aire
        if self._cayendo:
            self._velocidad_caida += 1400.0 * dt
            nueva_y = self.y() + int(self._velocidad_caida * dt)
            if nueva_y >= self._y_suelo:
                nueva_y = self._y_suelo
                self._cayendo = False
                self._velocidad_caida = 0.0
                self.lbl_mascota.activar_saltito()
                self.lbl_mascota.agregar_emote("star")
            self.move(self.x(), nueva_y)
            self._posicion_personalizada = self.pos()
            return

        # 2. Si está jugando a la pelota
        if self._jugando_pelota:
            dist = self._destino_x - self.x()
            if abs(dist) > 5:
                paso = 3 if dist > 0 else -3
                self.move(self.x() + paso, self.y())
                self.lbl_mascota.registrar_movimiento(float(paso * 1.5))
            else:
                if self._paso_pelota == 1:
                    # Atrapó la pelota: salto y corazoncito
                    self.lbl_mascota.activar_saltito()
                    self.lbl_mascota.agregar_emote("heart")
                    self._paso_pelota = 2
                    self._destino_x = self._origen_pelota_x
                else:
                    # Regresó con la pelota
                    self._jugando_pelota = False
                    self._paso_pelota = 0
                    self.lbl_mascota.soltar_arrastre()
                    self.lbl_mascota.forzar_saludo()
            return

        # 3. Si está en paseo autónomo por la pantalla
        if self._caminando_autonomo:
            dist = self._destino_x - self.x()
            if abs(dist) > 4:
                paso = 2 if dist > 0 else -2
                self.move(self.x() + paso, self.y())
                self.lbl_mascota.registrar_movimiento(float(paso * 1.2))
            else:
                self._caminando_autonomo = False
                self.lbl_mascota.soltar_arrastre()
                self.lbl_mascota.forzar_saludo()
            return

        # 4. Modo Inactividad / Siesta
        self._tiempo_inactivo += dt
        if not self._nombre_actividad and not self.globo._modo_chat and self._tiempo_inactivo > 40.0:
            if not self.lbl_mascota._durmiendo:
                self.lbl_mascota.set_durmiendo(True)

        # 5. Toma de decisiones de paseo autónomo (cada 12-16 segundos)
        if self._permitir_paseo_libre and not self.lbl_mascota._durmiendo and not self.globo._modo_chat:
            self._temporizador_decision += dt
            if self._temporizador_decision >= 14.0:
                self._temporizador_decision = 0.0
                if random.random() < 0.45:
                    self.iniciar_paseo_autonomo()

    def iniciar_paseo_autonomo(self) -> None:
        """Elige un destino cercano para caminar libremente por la pantalla."""
        pantalla = QApplication.primaryScreen()
        if not pantalla:
            return
        geom = pantalla.availableGeometry()
        ancho = self.width() or 220
        desplazamiento = random.choice([-110, -70, 70, 110])
        nuevo_x = max(geom.left() + 20, min(geom.right() - ancho - 20, self.x() + desplazamiento))
        if abs(nuevo_x - self.x()) > 25:
            self._destino_x = nuevo_x
            self._caminando_autonomo = True

    def jugar_pelota(self) -> None:
        """Lanza una pelota para que Utilín corra tras ella y la traiga feliz."""
        self.lbl_mascota.despertar()
        self._tiempo_inactivo = 0.0
        self._caminando_autonomo = False
        pantalla = QApplication.primaryScreen()
        geom = pantalla.availableGeometry() if pantalla else None

        self._origen_pelota_x = self.x()
        offset = 130 if (geom and self.x() - 130 < geom.left() + 40) else -130
        self._destino_x = self.x() + offset
        self._jugando_pelota = True
        self._paso_pelota = 1
        self.lbl_mascota.activar_saltito()

    def acariciar(self) -> None:
        """Le da caricias y afecto a Utilín (saltito y corazoncitos)."""
        self.lbl_mascota.despertar()
        self._tiempo_inactivo = 0.0
        self.lbl_mascota.activar_saltito()
        self.lbl_mascota.agregar_emote("heart")

    def alternar_paseo_libre(self, activo: bool) -> None:
        """Habilita o deshabilita los paseos autónomos de Utilín."""
        self._permitir_paseo_libre = activo
        if not activo and self._caminando_autonomo:
            self._caminando_autonomo = False
            self.lbl_mascota.soltar_arrastre()

    def alternar_siesta(self) -> None:
        """Envía a dormir o despierta manualmente a Utilín."""
        if self.lbl_mascota._durmiendo:
            self.lbl_mascota.despertar()
            self._tiempo_inactivo = 0.0
        else:
            self.lbl_mascota.set_durmiendo(True)

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
                self._tiempo_inactivo = 0.0
                if self.lbl_mascota._durmiendo:
                    self.lbl_mascota.despertar()
                if self._caminando_autonomo or self._jugando_pelota:
                    self._caminando_autonomo = False
                    self._jugando_pelota = False
                    self.lbl_mascota.soltar_arrastre()

                self._arrastrando = True
                self._cayendo = False
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

                # Calcular desplazamiento horizontal y notificar a Utilín (caminata izq/der)
                vx = float(pos_actual.x() - self._ultimo_pos_raton.x())
                self._ultimo_pos_raton = pos_actual
                self.lbl_mascota.registrar_movimiento(vx)
                return True

        elif t == QEvent.Type.MouseButtonRelease:
            if self._arrastrando:
                self._arrastrando = False
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self._posicion_personalizada = self.pos()
                self.lbl_mascota.soltar_arrastre()

                pantalla = QApplication.primaryScreen()
                if pantalla:
                    geom = pantalla.availableGeometry()
                    alto = self.height() or 270
                    suelo = geom.bottom() - alto - 35
                    # Si el usuario lo soltó en el aire, caer con gravedad hasta el suelo
                    if self.y() < suelo - 30:
                        self._cayendo = True
                        self._velocidad_caida = 0.0
                        self._y_suelo = suelo

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

        act_chat = menu.addAction("💬 Hablar con Utilín IA")
        act_chat.triggered.connect(self.globo.alternar_modo_chat)

        act_saludar = menu.addAction("👋 Saludar")
        act_saludar.triggered.connect(self.lbl_mascota.forzar_saludo)

        act_caricia = menu.addAction("💖 Acariciar a Utilín")
        act_caricia.triggered.connect(self.acariciar)

        act_pelota = menu.addAction("🎾 Jugar con la pelota")
        act_pelota.triggered.connect(self.jugar_pelota)

        act_paseo = menu.addAction("🚶 Paseo autónomo libre")
        act_paseo.setCheckable(True)
        act_paseo.setChecked(self._permitir_paseo_libre)
        act_paseo.toggled.connect(self.alternar_paseo_libre)

        act_siesta = menu.addAction("💤 Despertar" if self.lbl_mascota._durmiendo else "💤 Enviar a dormir")
        act_siesta.triggered.connect(self.alternar_siesta)

        if self._nombre_actividad:
            menu.addSeparator()
            tiempo_str = formatear_reloj_hms(self._segundos_actividad)
            act_info = menu.addAction(f"⏱ {self._nombre_actividad} ({tiempo_str})")
            act_info.setEnabled(False)

            if self.al_pausar:
                act_pausa = menu.addAction("⏸ Pausar actividad en curso")
                act_pausa.triggered.connect(self.al_pausar)

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
