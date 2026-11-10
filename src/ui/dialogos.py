"""Diálogos modales intuitivos y guiados para acciones operativas:
- Verificación de PIN al iniciar (si está habilitado).
- Pausar con botones rápidos en 1 clic (Baño, Almuerzo, Causa externa) y ocultación
  automática del % de avance salvo que se elija "Fin de jornada".
- Crear revisión vinculada (solicitante, tipo, qué cambiar, motivo).
- Reasignar actividad a otra persona.
- Corregir actividad y su último tramo de tiempo (con motivo obligatorio).
- Aprobar o rechazar solicitud bloqueada según decisión del ingeniero.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from data.db import BaseDatos
from data.enums import CanalSolicitud, MotivoRevision, TipoPausa, TipoRevision
from data.models import Actividad, Solicitante
from ui.iconos import configurar_boton


class DialogoPIN(QDialog):
    """Solicita el PIN de acceso al abrir la aplicación (RF-09)."""

    def __init__(self, bd: BaseDatos | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bd = bd
        self.setWindowTitle("Ingresar PIN — Control de Tiempos")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        lbl_tit = QLabel("Acceso protegido con PIN", self)
        lbl_tit.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(lbl_tit)

        layout.addWidget(QLabel("Escribe tu PIN numérico para entrar a la aplicación:"))

        fila_input = QHBoxLayout()
        self.txt_pin = QLineEdit(self)
        self.txt_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pin.setPlaceholderText("PIN de 4 o más dígitos")
        self.txt_pin.returnPressed.connect(self._intentar_aceptar)

        self.btn_ver_pin = QPushButton("Ver", self)
        self.btn_ver_pin.setProperty("rol", "secundario")
        self.btn_ver_pin.setCheckable(True)
        self.btn_ver_pin.setFixedWidth(56)
        self.btn_ver_pin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ver_pin.toggled.connect(self._alternar_ver_pin)

        fila_input.addWidget(self.txt_pin, 1)
        fila_input.addWidget(self.btn_ver_pin)
        layout.addLayout(fila_input)

        self.lbl_error = QLabel("", self)
        self.lbl_error.setStyleSheet("color: #EF4444; font-size: 12px; font-weight: 600;")
        self.lbl_error.setVisible(False)
        layout.addWidget(self.lbl_error)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.btn_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_ok.setText("  Entrar")
        self.btn_ok.setProperty("rol", "exito")
        configurar_boton(self.btn_ok, "check", color="#FFFFFF")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._intentar_aceptar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _alternar_ver_pin(self, ver: bool) -> None:
        self.txt_pin.setEchoMode(
            QLineEdit.EchoMode.Normal if ver else QLineEdit.EchoMode.Password
        )
        self.btn_ver_pin.setText("Ocultar" if ver else "Ver")

    def _intentar_aceptar(self) -> None:
        pin = self.pin
        if not pin:
            self.lbl_error.setText("Escribe tu PIN numérico.")
            self.lbl_error.setVisible(True)
            return

        if self.bd is not None:
            from services.seguridad_pin import ServicioPIN

            with self.bd.sesion() as s:
                if not ServicioPIN(s).verificar(pin):
                    self.lbl_error.setText("PIN incorrecto. Revisa los dígitos e inténtalo de nuevo.")
                    self.lbl_error.setVisible(True)
                    self.txt_pin.selectAll()
                    self.txt_pin.setFocus()
                    return

        self.accept()

    @property
    def pin(self) -> str:
        return self.txt_pin.text().strip()


class DialogoPausa(QDialog):
    """Ventana sencilla para pausar en 1 clic o elegir motivo personalizado (RF-05).

    El campo de ``% de avance`` permanece **oculto** salvo que el usuario elija
    explícitamente ``Fin de jornada (dejar para mañana)``.
    """

    def __init__(self, nombre_actividad: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pausar actividad")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        lbl_tit = QLabel(f"Pausar «{nombre_actividad}»", self)
        lbl_tit.setStyleSheet("font-size: 16px; font-weight: bold;")
        lbl_tit.setWordWrap(True)
        layout.addWidget(lbl_tit)

        lbl_rap = QLabel("<b>Opción rápida en 1 clic:</b>", self)
        layout.addWidget(lbl_rap)

        fila_rap1 = QHBoxLayout()
        btn_bano = QPushButton("  Baño / Pausa personal", self)
        btn_almuerzo = QPushButton("  Hora de almuerzo", self)
        configurar_boton(btn_bano, "user", color="#0F172A")
        configurar_boton(btn_almuerzo, "clock", color="#0F172A")
        for b in (btn_bano, btn_almuerzo):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_bano.clicked.connect(lambda: self._pausa_rapida(TipoPausa.PERSONAL, "Baño / pausa breve"))
        btn_almuerzo.clicked.connect(lambda: self._pausa_rapida(TipoPausa.ALMUERZO, "Hora de almuerzo"))
        fila_rap1.addWidget(btn_bano)
        fila_rap1.addWidget(btn_almuerzo)
        layout.addLayout(fila_rap1)

        fila_rap2 = QHBoxLayout()
        btn_internet = QPushButton("  Falla de internet / luz (Causa externa)", self)
        btn_internet.setProperty("rol", "advertencia")
        btn_internet.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(btn_internet, "zap", color="#FFFFFF")
        btn_internet.clicked.connect(
            lambda: self._pausa_rapida(TipoPausa.EXTERNA, "Falla de internet o energía")
        )
        fila_rap2.addWidget(btn_internet)
        layout.addLayout(fila_rap2)

        # Separador hacia opciones detalladas
        marco_det = QFrame(self)
        marco_det.setProperty("card", True)
        form = QFormLayout(marco_det)
        form.setSpacing(10)
        form.addRow(QLabel("<b>O indica otro motivo / fin de jornada:</b>"))

        self.combo_tipo = QComboBox(self)
        self.combo_tipo.addItem("Necesidad personal (baño, agua, etc.)", TipoPausa.PERSONAL.value)
        self.combo_tipo.addItem("Causa externa (luz, internet, equipo lento)", TipoPausa.EXTERNA.value)
        self.combo_tipo.addItem("Almuerzo", TipoPausa.ALMUERZO.value)
        self.combo_tipo.addItem("Otro motivo", TipoPausa.OTRO.value)
        self.combo_tipo.addItem(
            "Fin de jornada (dejar para continuar mañana)", TipoPausa.FIN_JORNADA.value
        )

        self.txt_motivo = QLineEdit(self)
        self.txt_motivo.setPlaceholderText("Detalle opcional (ej. llamada rápida, esperando archivo...)")

        # Contenedor exclusivo para Fin de Jornada (oculto por defecto)
        self.widget_avance = QWidget(self)
        fila_av = QHBoxLayout(self.widget_avance)
        fila_av.setContentsMargins(0, 0, 0, 0)
        self.lbl_avance = QLabel("¿Qué % de avance dejas hoy?:", self.widget_avance)
        self.spin_avance = QSpinBox(self.widget_avance)
        self.spin_avance.setRange(0, 99)
        self.spin_avance.setValue(50)
        self.spin_avance.setSuffix(" % completado")
        fila_av.addWidget(self.lbl_avance)
        fila_av.addWidget(self.spin_avance, 1)
        self.widget_avance.setVisible(False)

        self.combo_tipo.currentIndexChanged.connect(self._actualizar_avance)

        form.addRow("Tipo de pausa:", self.combo_tipo)
        form.addRow("Detalle:", self.txt_motivo)
        form.addRow(self.widget_avance)
        layout.addWidget(marco_det)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Pausar ahora")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _pausa_rapida(self, tipo: TipoPausa, motivo_defecto: str) -> None:
        idx = self.combo_tipo.findData(tipo.value)
        if idx >= 0:
            self.combo_tipo.setCurrentIndex(idx)
        if not self.txt_motivo.text().strip():
            self.txt_motivo.setText(motivo_defecto)
        self.accept()

    def _actualizar_avance(self) -> None:
        es_fin = self.combo_tipo.currentData() == TipoPausa.FIN_JORNADA.value
        self.widget_avance.setVisible(es_fin)
        if es_fin:
            self.txt_motivo.setPlaceholderText(
                "Obligatorio: ¿por qué queda pendiente para mañana?"
            )
        else:
            self.txt_motivo.setPlaceholderText(
                "Detalle opcional (ej. baño, esperando archivo...)"
            )
        self.adjustSize()

    def _validar_y_aceptar(self) -> None:
        es_fin = self.combo_tipo.currentData() == TipoPausa.FIN_JORNADA.value
        if es_fin and not self.txt_motivo.text().strip():
            QMessageBox.warning(
                self,
                "Motivo requerido",
                "Al pausar por fin de jornada, escribe brevemente por qué continuará mañana.",
            )
            return
        self.accept()

    @property
    def tipo_pausa(self) -> str:
        return str(self.combo_tipo.currentData())

    @property
    def motivo(self) -> str:
        return self.txt_motivo.text().strip()

    @property
    def avance_pct(self) -> int | None:
        if self.combo_tipo.currentData() == TipoPausa.FIN_JORNADA.value:
            return int(self.spin_avance.value())
        return None


class DialogoRevision(QDialog):
    """Formulario para reabrir una actividad completada como Revisión (RF-03b)."""

    def __init__(
        self,
        nombre_original: str,
        solicitantes: list[Solicitante],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Nueva revisión de: {nombre_original}")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        lbl_tit = QLabel(f"Registrar revisión de «{nombre_original}»", self)
        lbl_tit.setStyleSheet("font-size: 16px; font-weight: bold;")
        lbl_tit.setWordWrap(True)
        layout.addWidget(lbl_tit)

        lbl_ayuda = QLabel(
            "Se creará una revisión con su propio cronómetro sin borrar el tiempo original.",
            self,
        )
        lbl_ayuda.setObjectName("subtitulo")
        lbl_ayuda.setWordWrap(True)
        layout.addWidget(lbl_ayuda)

        form = QFormLayout()
        form.setSpacing(10)

        self.combo_solicitante = QComboBox(self)
        for sol in solicitantes:
            self.combo_solicitante.addItem(sol.nombre, sol.id)

        self.combo_tipo = QComboBox(self)
        for tr in TipoRevision:
            self.combo_tipo.addItem(tr.etiqueta(), tr.value)

        self.combo_motivo = QComboBox(self)
        for mr in MotivoRevision:
            self.combo_motivo.addItem(mr.etiqueta(), mr.value)

        self.txt_que_cambiar = QLineEdit(self)
        self.txt_que_cambiar.setPlaceholderText("Ej. Cambiar color de fondo, ajustar texto...")

        form.addRow("¿Quién pidió el cambio?:", self.combo_solicitante)
        form.addRow("Tamaño del ajuste:", self.combo_tipo)
        form.addRow("Motivo del cambio:", self.combo_motivo)
        form.addRow("¿Qué se pidió cambiar?*:", self.txt_que_cambiar)
        layout.addLayout(form)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Iniciar revisión ahora")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _validar_y_aceptar(self) -> None:
        if not self.txt_que_cambiar.text().strip():
            QMessageBox.warning(self, "Campo obligatorio", "Indica qué se pidió cambiar.")
            return
        self.accept()

    @property
    def solicitante_id(self) -> int:
        return int(self.combo_solicitante.currentData())

    @property
    def tipo_revision(self) -> str:
        return str(self.combo_tipo.currentData())

    @property
    def motivo_revision(self) -> str:
        return str(self.combo_motivo.currentData())

    @property
    def que_cambiar(self) -> str:
        return self.txt_que_cambiar.text().strip()


class DialogoReasignar(QDialog):
    """Formulario para marcar una actividad como reasignada a otra persona (RF-03c)."""

    def __init__(self, nombre_actividad: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Reasignar: {nombre_actividad}")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        lbl_tit = QLabel(f"Reasignar «{nombre_actividad}»", self)
        lbl_tit.setStyleSheet("font-size: 16px; font-weight: bold;")
        lbl_tit.setWordWrap(True)
        layout.addWidget(lbl_tit)

        lbl_ayuda = QLabel(
            "El tiempo que ya trabajaste en esta actividad sí te contará en el día.",
            self,
        )
        lbl_ayuda.setObjectName("subtitulo")
        lbl_ayuda.setWordWrap(True)
        layout.addWidget(lbl_ayuda)

        form = QFormLayout()
        form.setSpacing(10)

        self.txt_persona = QLineEdit(self)
        self.txt_persona.setPlaceholderText("Nombre del compañero que la continuará")
        self.txt_motivo = QLineEdit(self)
        self.txt_motivo.setPlaceholderText("Ej. Se redistribuyó carga de trabajo")

        form.addRow("Pasar a:", self.txt_persona)
        form.addRow("Motivo:", self.txt_motivo)
        layout.addLayout(form)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Confirmar reasignación")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._validar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _validar(self) -> None:
        if not self.txt_persona.text().strip() or not self.txt_motivo.text().strip():
            QMessageBox.warning(self, "Campos obligatorios", "Indica la persona y el motivo.")
            return
        self.accept()

    @property
    def persona(self) -> str:
        return self.txt_persona.text().strip()

    @property
    def motivo(self) -> str:
        return self.txt_motivo.text().strip()


class DialogoCorregirActividad(QDialog):
    """Formulario para corregir una actividad y/o su último tramo de tiempo (RF-07)."""

    def __init__(self, actividad: Actividad, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Corregir registro: {actividad.nombre}")
        self.setMinimumWidth(460)
        self._tiene_sesion = bool(actividad.sesiones)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        lbl_tit = QLabel(f"Corregir «{actividad.nombre}»", self)
        lbl_tit.setStyleSheet("font-size: 16px; font-weight: bold;")
        lbl_tit.setWordWrap(True)
        layout.addWidget(lbl_tit)

        form = QFormLayout()
        form.setSpacing(10)

        self.txt_nombre = QLineEdit(actividad.nombre, self)
        self.spin_estimado = QSpinBox(self)
        self.spin_estimado.setRange(0, 960)
        self.spin_estimado.setValue(actividad.tiempo_estimado_min or 0)
        self.spin_estimado.setSuffix(" min")
        self.spin_estimado.setSpecialValueText("Sin estimado")

        self.txt_descripcion = QLineEdit(actividad.descripcion or "", self)

        self.dt_inicio = QDateTimeEdit(self)
        self.dt_inicio.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        self.dt_fin = QDateTimeEdit(self)
        self.dt_fin.setDisplayFormat("dd/MM/yyyy HH:mm:ss")

        if self._tiene_sesion:
            ult = actividad.sesiones[-1]
            self.dt_inicio.setDateTime(
                QDateTime(
                    ult.inicio.year,
                    ult.inicio.month,
                    ult.inicio.day,
                    ult.inicio.hour,
                    ult.inicio.minute,
                    ult.inicio.second,
                )
            )
            fin_ref = ult.fin or datetime.now().replace(microsecond=0)
            self.dt_fin.setDateTime(
                QDateTime(
                    fin_ref.year,
                    fin_ref.month,
                    fin_ref.day,
                    fin_ref.hour,
                    fin_ref.minute,
                    fin_ref.second,
                )
            )
        else:
            self.dt_inicio.setVisible(False)
            self.dt_fin.setVisible(False)

        self.txt_motivo = QLineEdit(self)
        self.txt_motivo.setPlaceholderText("Obligatorio: ej. Olvidé detener el cronómetro al salir")

        form.addRow("Nombre:", self.txt_nombre)
        form.addRow("Tiempo estimado:", self.spin_estimado)
        form.addRow("Descripción:", self.txt_descripcion)
        if self._tiene_sesion:
            form.addRow("Inicio último tramo:", self.dt_inicio)
            form.addRow("Fin último tramo:", self.dt_fin)
        form.addRow("Motivo del ajuste*:", self.txt_motivo)
        layout.addLayout(form)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar corrección")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._validar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _validar(self) -> None:
        if not self.txt_motivo.text().strip():
            QMessageBox.warning(
                self,
                "Motivo obligatorio",
                "Debes escribir el motivo de la corrección para conservar el registro.",
            )
            return
        self.accept()

    @property
    def motivo(self) -> str:
        return self.txt_motivo.text().strip()

    @property
    def nuevo_nombre(self) -> str:
        return self.txt_nombre.text().strip()

    @property
    def nuevo_estimado(self) -> int | None:
        val = int(self.spin_estimado.value())
        return val if val > 0 else None

    @property
    def nueva_descripcion(self) -> str:
        return self.txt_descripcion.text().strip()

    @property
    def nuevo_inicio(self) -> datetime | None:
        if not self._tiene_sesion:
            return None
        return self.dt_inicio.dateTime().toPython().replace(microsecond=0)

    @property
    def nuevo_fin(self) -> datetime | None:
        if not self._tiene_sesion:
            return None
        return self.dt_fin.dateTime().toPython().replace(microsecond=0)


class DialogoAprobacionIngeniero(QDialog):
    """Permite marcar si el ingeniero aprobó o rechazó una solicitud de compañero/tercero."""

    def __init__(self, nombre_actividad: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Decisión del ingeniero: {nombre_actividad}")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        lbl_tit = QLabel(f"Decisión sobre «{nombre_actividad}»", self)
        lbl_tit.setStyleSheet("font-size: 16px; font-weight: bold;")
        lbl_tit.setWordWrap(True)
        layout.addWidget(lbl_tit)

        form = QFormLayout()
        form.setSpacing(10)

        self.combo_decision = QComboBox(self)
        self.combo_decision.addItem("Aprobada por el Ing. Luis Eduardo (desbloquear)", True)
        self.combo_decision.addItem("Rechazada por el Ing. Luis Eduardo", False)

        self.combo_canal = QComboBox(self)
        for c in CanalSolicitud:
            self.combo_canal.addItem(c.etiqueta(), c.value)

        form.addRow("Decisión:", self.combo_decision)
        form.addRow("¿Por qué medio respondió?:", self.combo_canal)
        layout.addLayout(form)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar decisión")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    @property
    def aprobada(self) -> bool:
        return bool(self.combo_decision.currentData())

    @property
    def canal(self) -> str:
        return str(self.combo_canal.currentData())
