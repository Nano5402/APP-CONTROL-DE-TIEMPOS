"""Diálogos modales para acciones operativas de la pantalla Hoy e Historial:
- Verificación de PIN al iniciar (si está habilitado).
- Pausar con tipo, motivo y % de avance (si es fin de jornada).
- Crear revisión vinculada (solicitante, tipo, qué cambiar, motivo).
- Reasignar actividad a otra persona.
- Corregir actividad y su último tramo de tiempo (con motivo obligatorio).
- Aprobar o rechazar solicitud bloqueada según decisión del ingeniero.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from data.enums import CanalSolicitud, MotivoRevision, TipoPausa, TipoRevision
from data.models import Actividad, Solicitante


class DialogoPIN(QDialog):
    """Solicita el PIN de acceso al abrir la aplicación (RF-09)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ingresar PIN — Control de Tiempos")
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Ingresa tu PIN para desbloquear la aplicación:"))
        self.txt_pin = QLineEdit(self)
        self.txt_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pin.setPlaceholderText("PIN numérico")
        layout.addWidget(self.txt_pin)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    @property
    def pin(self) -> str:
        return self.txt_pin.text().strip()


class DialogoPausa(QDialog):
    """Formulario rápido para pausar una actividad indicando tipo y motivo (RF-05)."""

    def __init__(self, nombre_actividad: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Pausar: {nombre_actividad}")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.combo_tipo = QComboBox(self)
        for tp in (
            TipoPausa.PERSONAL,
            TipoPausa.EXTERNA,
            TipoPausa.ALMUERZO,
            TipoPausa.FIN_JORNADA,
            TipoPausa.OTRO,
        ):
            self.combo_tipo.addItem(tp.etiqueta(), tp.value)

        self.txt_motivo = QLineEdit(self)
        self.txt_motivo.setPlaceholderText("Ej. Baño, internet lento, falta renderizar...")

        self.spin_avance = QSpinBox(self)
        self.spin_avance.setRange(0, 100)
        self.spin_avance.setValue(50)
        self.spin_avance.setSuffix(" %")
        self.spin_avance.setEnabled(False)

        self.combo_tipo.currentIndexChanged.connect(self._actualizar_avance)

        form.addRow("Tipo de pausa:", self.combo_tipo)
        form.addRow("Motivo:", self.txt_motivo)
        form.addRow("% de avance (fin jornada):", self.spin_avance)
        layout.addLayout(form)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _actualizar_avance(self) -> None:
        es_fin = self.combo_tipo.currentData() == TipoPausa.FIN_JORNADA.value
        self.spin_avance.setEnabled(es_fin)

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
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

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
        self.txt_que_cambiar.setPlaceholderText("Describe qué cambio solicitaron...")

        form.addRow("¿Quién pidió el cambio?:", self.combo_solicitante)
        form.addRow("Tipo de cambio:", self.combo_tipo)
        form.addRow("Motivo del cambio:", self.combo_motivo)
        form.addRow("¿Qué se pidió cambiar?:", self.txt_que_cambiar)
        layout.addLayout(form)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
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
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_persona = QLineEdit(self)
        self.txt_persona.setPlaceholderText("Nombre del compañero")
        self.txt_motivo = QLineEdit(self)
        self.txt_motivo.setPlaceholderText("Motivo de la reasignación")

        form.addRow("Reasignada a:", self.txt_persona)
        form.addRow("Motivo:", self.txt_motivo)
        layout.addLayout(form)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
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
        self.setMinimumWidth(440)
        self._tiene_sesion = bool(actividad.sesiones)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_nombre = QLineEdit(actividad.nombre, self)
        self.spin_estimado = QSpinBox(self)
        self.spin_estimado.setRange(0, 960)
        self.spin_estimado.setValue(actividad.tiempo_estimado_min or 0)
        self.spin_estimado.setSuffix(" min")

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
            self.dt_inicio.setEnabled(False)
            self.dt_fin.setEnabled(False)

        self.txt_motivo = QLineEdit(self)
        self.txt_motivo.setPlaceholderText("Obligatorio: por qué se corrige el registro")

        form.addRow("Nombre:", self.txt_nombre)
        form.addRow("Tiempo estimado:", self.spin_estimado)
        form.addRow("Descripción:", self.txt_descripcion)
        if self._tiene_sesion:
            form.addRow("Inicio último tramo:", self.dt_inicio)
            form.addRow("Fin último tramo:", self.dt_fin)
        form.addRow("Motivo de corrección*:", self.txt_motivo)
        layout.addLayout(form)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        botones.accepted.connect(self._validar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _validar(self) -> None:
        if not self.txt_motivo.text().strip():
            QMessageBox.warning(
                self,
                "Motivo obligatorio",
                "Debes escribir el motivo de la corrección para conservar la trazabilidad.",
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
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.combo_decision = QComboBox(self)
        self.combo_decision.addItem("Aprobada (habilitar botón Iniciar)", True)
        self.combo_decision.addItem("Rechazada", False)

        self.combo_canal = QComboBox(self)
        for c in CanalSolicitud:
            self.combo_canal.addItem(c.etiqueta(), c.value)

        form.addRow("Decisión:", self.combo_decision)
        form.addRow("Canal de decisión:", self.combo_canal)
        layout.addLayout(form)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    @property
    def aprobada(self) -> bool:
        return bool(self.combo_decision.currentData())

    @property
    def canal(self) -> str:
        return str(self.combo_canal.currentData())
