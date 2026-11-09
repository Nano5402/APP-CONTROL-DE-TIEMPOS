"""Pantalla 3: Actividad extra (urgencias y solicitudes) — RF-03.

Captura:
- Solicitante (o creación rápida de un nuevo solicitante: compañero / tercero).
- Motivo de la urgencia, canal de solicitud, fecha/hora límite opcional y descripción.
- Si el solicitante es jefe o doctora (prioridad máxima), permite **"Crear e iniciar ya"**
  (pausando automáticamente la actividad en curso).
- Si es compañero o tercero, queda bloqueada hasta la aprobación del ingeniero, o
  permite marcar que ya cuenta con aprobación previa del ingeniero.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from data.db import BaseDatos
from data.enums import CanalSolicitud, TipoSolicitante
from data.models import Solicitante
from data.repositorios.catalogos import RepoCategorias, RepoSolicitantes
from services.actividades import ServicioActividades
from services.cronometro import AccionSobreActiva, ServicioCronometro


class PantallaExtra(QWidget):
    """Formulario rápido para registrar actividades extra."""

    def __init__(
        self,
        bd: BaseDatos,
        *,
        al_crear_extra: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bd = bd
        self.al_crear_extra = al_crear_extra

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        lbl_tit = QLabel("Registrar Actividad Extra", self)
        lbl_tit.setObjectName("tituloPantalla")
        layout.addWidget(lbl_tit)

        card = QFrame(self)
        card.setProperty("card", True)
        form = QFormLayout(card)
        form.setSpacing(10)

        self.txt_nombre = QLineEdit(self)
        self.txt_nombre.setPlaceholderText("Ej. Flyer urgente vacante, Ajuste presentación...")

        # Selector de solicitante + alta rápida de solicitante nuevo
        fila_sol = QHBoxLayout()
        self.combo_solicitante = QComboBox(self)
        self.combo_solicitante.currentIndexChanged.connect(self._al_cambiar_solicitante)
        self.txt_nuevo_sol = QLineEdit(self)
        self.txt_nuevo_sol.setPlaceholderText("Nuevo solicitante (ej. Dr. Pérez, Compañero)")
        self.combo_tipo_nuevo_sol = QComboBox(self)
        for ts in (TipoSolicitante.COMPANERO, TipoSolicitante.TERCERO, TipoSolicitante.DOCTORA):
            self.combo_tipo_nuevo_sol.addItem(ts.etiqueta(), ts.value)
        self.btn_crear_sol = QPushButton("+ Añadir solicitante", self)
        self.btn_crear_sol.setProperty("rol", "secundario")
        self.btn_crear_sol.clicked.connect(self.accion_crear_solicitante)

        fila_sol.addWidget(self.combo_solicitante, 2)
        fila_sol.addWidget(self.txt_nuevo_sol, 2)
        fila_sol.addWidget(self.combo_tipo_nuevo_sol, 1)
        fila_sol.addWidget(self.btn_crear_sol)

        self.lbl_regla_prioridad = QLabel("", self)
        self.lbl_regla_prioridad.setObjectName("subtitulo")

        self.combo_canal = QComboBox(self)
        for c in CanalSolicitud:
            self.combo_canal.addItem(c.etiqueta(), c.value)

        self.txt_motivo_urgencia = QLineEdit(self)
        self.txt_motivo_urgencia.setPlaceholderText("¿Por qué es urgente o extraordinaria?")

        self.txt_categoria = QLineEdit(self)
        self.txt_categoria.setPlaceholderText("Categoría (opcional)")

        self.spin_estimado = QSpinBox(self)
        self.spin_estimado.setRange(0, 600)
        self.spin_estimado.setSuffix(" min")
        self.spin_estimado.setSpecialValueText("Sin estimado")

        self.chk_tiene_limite = QCheckBox("Tiene fecha/hora límite", self)
        self.dt_limite = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600), self)
        self.dt_limite.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.dt_limite.setEnabled(False)
        self.chk_tiene_limite.toggled.connect(self.dt_limite.setEnabled)

        self.chk_aprobada_ing = QCheckBox(
            "Ya cuenta con aprobación previa del Ing. Luis Eduardo", self
        )

        self.txt_descripcion = QPlainTextEdit(self)
        self.txt_descripcion.setPlaceholderText(
            "Describe en qué consiste la actividad para evaluar el tiempo invertido..."
        )
        self.txt_descripcion.setMaximumHeight(90)

        form.addRow("Nombre de la actividad*:", self.txt_nombre)
        form.addRow("Solicitante*:", fila_sol)
        form.addRow("Regla aplicada:", self.lbl_regla_prioridad)
        form.addRow("Canal de solicitud*:", self.combo_canal)
        form.addRow("Motivo de la urgencia*:", self.txt_motivo_urgencia)
        form.addRow("Categoría:", self.txt_categoria)
        form.addRow("Tiempo estimado:", self.spin_estimado)
        form.addRow(self.chk_tiene_limite, self.dt_limite)
        form.addRow("", self.chk_aprobada_ing)
        form.addRow("Descripción detallada*:", self.txt_descripcion)
        layout.addWidget(card)

        fila_btn = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar actividad extra", self)
        self.btn_guardar_iniciar = QPushButton("⚡ Guardar e iniciar ahora", self)
        self.btn_guardar_iniciar.setProperty("rol", "exito")

        self.btn_guardar.clicked.connect(lambda: self._guardar(iniciar_ya=False))
        self.btn_guardar_iniciar.clicked.connect(lambda: self._guardar(iniciar_ya=True))

        fila_btn.addStretch()
        fila_btn.addWidget(self.btn_guardar)
        fila_btn.addWidget(self.btn_guardar_iniciar)
        layout.addLayout(fila_btn)
        layout.addStretch()

        self.refrescar()

    def refrescar(self) -> None:
        with self.bd.sesion() as s:
            solicitantes = RepoSolicitantes(s).listar_activos()
            self.combo_solicitante.blockSignals(True)
            self.combo_solicitante.clear()
            for sol in solicitantes:
                self.combo_solicitante.addItem(
                    f"{sol.nombre} ({sol.tipo})", sol.id
                )
            self.combo_solicitante.blockSignals(False)
        self._al_cambiar_solicitante()

    def _al_cambiar_solicitante(self) -> None:
        sol_id = self.combo_solicitante.currentData()
        if sol_id is None:
            return
        with self.bd.sesion() as s:
            sol = s.get(Solicitante, int(sol_id))
            if sol is None:
                return
            if sol.requiere_aprobacion:
                self.lbl_regla_prioridad.setText(
                    f"Prioridad {sol.prioridad_defecto}: requiere aprobación del ingeniero "
                    "(quedará bloqueada salvo que marques aprobación previa)."
                )
                self.chk_aprobada_ing.setEnabled(True)
            else:
                self.lbl_regla_prioridad.setText(
                    f"Prioridad {sol.prioridad_defecto.upper()}: se puede iniciar de inmediato "
                    "y cuenta como cumplimiento."
                )
                self.chk_aprobada_ing.setChecked(False)
                self.chk_aprobada_ing.setEnabled(False)

    def accion_crear_solicitante(self) -> None:
        nombre = self.txt_nuevo_sol.text().strip()
        if not nombre:
            return
        tipo = str(self.combo_tipo_nuevo_sol.currentData())
        with self.bd.sesion() as s:
            nuevo = RepoSolicitantes(s).crear(nombre, tipo)
            nuevo_id = nuevo.id
        self.txt_nuevo_sol.clear()
        self.refrescar()
        idx = self.combo_solicitante.findData(nuevo_id)
        if idx >= 0:
            self.combo_solicitante.setCurrentIndex(idx)

    def _guardar(self, *, iniciar_ya: bool) -> None:
        nombre = self.txt_nombre.text().strip()
        motivo = self.txt_motivo_urgencia.text().strip()
        desc = self.txt_descripcion.toPlainText().strip()
        sol_id = self.combo_solicitante.currentData()

        if not nombre or not motivo or not desc or sol_id is None:
            QMessageBox.warning(
                self,
                "Datos incompletos",
                "Completa el nombre, solicitante, motivo de la urgencia y descripción.",
            )
            return

        canal = str(self.combo_canal.currentData())
        cat_txt = self.txt_categoria.text().strip()
        estimado = int(self.spin_estimado.value()) or None
        limite = (
            self.dt_limite.dateTime().toPython().replace(microsecond=0)
            if self.chk_tiene_limite.isChecked()
            else None
        )
        aprobada_prev = self.chk_aprobada_ing.isChecked()

        with self.bd.sesion() as s:
            sol = s.get(Solicitante, int(sol_id))
            if sol is None:
                return
            cat_id = RepoCategorias(s).obtener_o_crear(cat_txt).id if cat_txt else None
            srv_act = ServicioActividades(s)
            extra = srv_act.crear_extra(
                nombre,
                sol,
                motivo_urgencia=motivo,
                canal_solicitud=canal,
                descripcion=desc,
                categoria_id=cat_id,
                tiempo_estimado_min=estimado,
                fecha_limite=limite,
                aprobada_previamente=aprobada_prev,
            )

            if iniciar_ya:
                if sol.requiere_aprobacion and not aprobada_prev:
                    QMessageBox.information(
                        self,
                        "Guardada como bloqueada",
                        "La solicitud requiere aprobación del Ing. Luis Eduardo. "
                        "Quedó registrada como bloqueada en la pantalla Hoy.",
                    )
                else:
                    ServicioCronometro(s).iniciar(
                        extra, accion_sobre_activa=AccionSobreActiva.PAUSAR
                    )

        self.txt_nombre.clear()
        self.txt_motivo_urgencia.clear()
        self.txt_descripcion.clear()
        if self.al_crear_extra:
            self.al_crear_extra()
