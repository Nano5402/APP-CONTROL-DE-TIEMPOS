"""Pantalla 3: Actividad extra (urgencias y solicitudes) — RF-03.

Diseño intuitivo con revelación progresiva:
- El selector de solicitante muestra claramente a quiénes tienen prioridad máxima
  (Ing. Luis Eduardo y Doctoras).
- El formulario para crear un solicitante nuevo permanece **oculto** hasta pulsar
  «+ Otra persona».
- La casilla de «Ya cuenta con aprobación previa del Ing. Luis Eduardo» permanece
  **oculta** cuando quien pide es el Jefe o una Doctora (porque no requieren aprobación).
- El selector de fecha/hora límite permanece **oculto** salvo que el usuario marque
  «Tiene fecha/hora límite».
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QDateTime, Qt
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
from ui.iconos import configurar_boton


class PantallaExtra(QWidget):
    """Formulario guiado para registrar actividades extra."""

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
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        lbl_tit = QLabel("Registrar Actividad Extra", self)
        lbl_tit.setObjectName("tituloPantalla")
        lbl_sub = QLabel(
            "Usa esta pantalla cuando alguien te pida una tarea adicional que no estaba en tu plan de la mañana.",
            self,
        )
        lbl_sub.setObjectName("subtitulo")
        layout.addWidget(lbl_tit)
        layout.addWidget(lbl_sub)

        card = QFrame(self)
        card.setProperty("card", True)
        form = QFormLayout(card)
        form.setSpacing(10)

        self.txt_nombre = QLineEdit(self)
        self.txt_nombre.setPlaceholderText("Ej. Flyer urgente vacante, Ajuste presentación...")

        # Selector limpio de solicitante + botón opcional para agregar una persona nueva
        fila_sol = QHBoxLayout()
        self.combo_solicitante = QComboBox(self)
        self.combo_solicitante.currentIndexChanged.connect(self._al_cambiar_solicitante)
        self.btn_mostrar_nuevo_sol = QPushButton("  Registrar otra persona", self)
        self.btn_mostrar_nuevo_sol.setProperty("rol", "secundario")
        self.btn_mostrar_nuevo_sol.setCheckable(True)
        self.btn_mostrar_nuevo_sol.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_mostrar_nuevo_sol, "plus", color="#0F172A")

        fila_sol.addWidget(self.combo_solicitante, 1)
        fila_sol.addWidget(self.btn_mostrar_nuevo_sol)

        # Panel desplegable para dar de alta un nuevo solicitante (oculto por defecto)
        self.panel_nuevo_sol = QWidget(self)
        fila_nuevo_sol = QHBoxLayout(self.panel_nuevo_sol)
        fila_nuevo_sol.setContentsMargins(0, 0, 0, 0)
        self.txt_nuevo_sol = QLineEdit(self.panel_nuevo_sol)
        self.txt_nuevo_sol.setPlaceholderText("Nombre de la persona (ej. Carlos, Cliente X...)")
        self.combo_tipo_nuevo_sol = QComboBox(self.panel_nuevo_sol)
        for ts in (TipoSolicitante.COMPANERO, TipoSolicitante.TERCERO, TipoSolicitante.DOCTORA):
            self.combo_tipo_nuevo_sol.addItem(ts.etiqueta(), ts.value)
        self.btn_crear_sol = QPushButton("Guardar persona", self.panel_nuevo_sol)
        self.btn_crear_sol.clicked.connect(self.accion_crear_solicitante)
        fila_nuevo_sol.addWidget(self.txt_nuevo_sol, 2)
        fila_nuevo_sol.addWidget(self.combo_tipo_nuevo_sol, 1)
        fila_nuevo_sol.addWidget(self.btn_crear_sol)
        self.panel_nuevo_sol.setVisible(False)
        self.btn_mostrar_nuevo_sol.toggled.connect(self.panel_nuevo_sol.setVisible)

        self.lbl_regla_prioridad = QLabel("", self)
        self.lbl_regla_prioridad.setWordWrap(True)
        self.lbl_regla_prioridad.setObjectName("bannerInfo")

        # Solo visible cuando quien solicita es compañero o tercero
        self.chk_aprobada_ing = QCheckBox(
            "El Ing. Luis Eduardo ya autorizó esta solicitud", self
        )
        self.chk_aprobada_ing.setVisible(False)

        self.combo_canal = QComboBox(self)
        for c in CanalSolicitud:
            self.combo_canal.addItem(c.etiqueta(), c.value)

        self.txt_motivo_urgencia = QLineEdit(self)
        self.txt_motivo_urgencia.setPlaceholderText("¿Por qué la necesitan hoy? (ej. Reunión, publicación urgente...)")

        self.combo_categoria = QComboBox(self)
        self.combo_categoria.setEditable(True)
        self.txt_categoria = self.combo_categoria.lineEdit()
        if self.txt_categoria is not None:
            self.txt_categoria.setPlaceholderText("Elige o escribe categoría (ej. Flyers)")

        self.spin_estimado = QSpinBox(self)
        self.spin_estimado.setRange(0, 600)
        self.spin_estimado.setSuffix(" min")
        self.spin_estimado.setSpecialValueText("Sin estimado")

        # Fecha límite oculta salvo que marque la casilla
        fila_lim = QHBoxLayout()
        self.chk_tiene_limite = QCheckBox("Tiene hora o fecha límite de entrega", self)
        self.dt_limite = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600), self)
        self.dt_limite.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.dt_limite.setVisible(False)
        self.chk_tiene_limite.toggled.connect(self.dt_limite.setVisible)
        fila_lim.addWidget(self.chk_tiene_limite)
        fila_lim.addWidget(self.dt_limite)
        fila_lim.addStretch()

        self.txt_descripcion = QPlainTextEdit(self)
        self.txt_descripcion.setPlaceholderText(
            "Describe brevemente qué pidieron hacer..."
        )
        self.txt_descripcion.setMaximumHeight(85)

        form.addRow("¿Qué actividad te pidieron?*:", self.txt_nombre)
        form.addRow("¿Quién la solicita?*:", fila_sol)
        form.addRow("", self.panel_nuevo_sol)
        form.addRow("Prioridad asignada:", self.lbl_regla_prioridad)
        form.addRow("", self.chk_aprobada_ing)
        form.addRow("¿Por qué medio la pidieron?*:", self.combo_canal)
        form.addRow("Motivo de la solicitud*:", self.txt_motivo_urgencia)
        form.addRow("Categoría:", self.combo_categoria)
        form.addRow("Tiempo estimado:", self.spin_estimado)
        form.addRow("Fecha límite:", fila_lim)
        form.addRow("Descripción breve*:", self.txt_descripcion)
        layout.addWidget(card)

        fila_btn = QHBoxLayout()
        self.btn_guardar = QPushButton("  Guardar en mi lista", self)
        self.btn_guardar.setProperty("rol", "secundario")
        configurar_boton(self.btn_guardar, "plus", color="#0F172A")
        self.btn_guardar_iniciar = QPushButton("  Guardar y empezar ahora", self)
        self.btn_guardar_iniciar.setProperty("rol", "exito")
        configurar_boton(self.btn_guardar_iniciar, "play")

        for b in (self.btn_guardar, self.btn_guardar_iniciar):
            b.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_guardar.clicked.connect(lambda: self._guardar(iniciar_ya=False))
        self.btn_guardar_iniciar.clicked.connect(lambda: self._guardar(iniciar_ya=True))

        fila_btn.addStretch()
        fila_btn.addWidget(self.btn_guardar)
        fila_btn.addWidget(self.btn_guardar_iniciar)
        layout.addLayout(fila_btn)
        layout.addStretch()

        self.refrescar()

    def refrescar(self) -> None:
        cat_actual = self.combo_categoria.currentText().strip()
        with self.bd.sesion() as s:
            solicitantes = RepoSolicitantes(s).listar_activos()
            categorias = RepoCategorias(s).asegurar_categorias_base()
            self.combo_solicitante.blockSignals(True)
            self.combo_solicitante.clear()
            for sol in solicitantes:
                self.combo_solicitante.addItem(
                    f"{sol.nombre} ({sol.tipo})", sol.id
                )
            self.combo_solicitante.blockSignals(False)

            self.combo_categoria.blockSignals(True)
            self.combo_categoria.clear()
            self.combo_categoria.addItem("Flyers")
            for c in categorias:
                if c.nombre.strip().lower() != "flyers":
                    self.combo_categoria.addItem(c.nombre)
            if cat_actual:
                self.combo_categoria.setCurrentText(cat_actual)
            self.combo_categoria.blockSignals(False)
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
                    f"Solicitud de {sol.tipo}: requiere autorización del Ing. Luis Eduardo. "
                    "Si aún no te la ha aprobado, quedará en espera en la pantalla Hoy."
                )
                self.chk_aprobada_ing.setVisible(True)
                self.chk_aprobada_ing.setEnabled(True)
            else:
                self.lbl_regla_prioridad.setText(
                    "Prioridad MÁXIMA: no requiere aprobación, puedes iniciarla de inmediato "
                    "(pausará lo que tengas en curso) y suma a tu Cumplimiento."
                )
                self.chk_aprobada_ing.setChecked(False)
                self.chk_aprobada_ing.setVisible(False)

    def accion_crear_solicitante(self) -> None:
        nombre = self.txt_nuevo_sol.text().strip()
        if not nombre:
            return
        tipo = str(self.combo_tipo_nuevo_sol.currentData())
        with self.bd.sesion() as s:
            nuevo = RepoSolicitantes(s).crear(nombre, tipo)
            nuevo_id = nuevo.id
        self.txt_nuevo_sol.clear()
        self.btn_mostrar_nuevo_sol.setChecked(False)
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
                "Completa el nombre, solicitante, motivo de la solicitud y descripción.",
            )
            return

        canal = str(self.combo_canal.currentData())
        cat_txt = self.combo_categoria.currentText().strip()
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
                        "Guardada en espera de aprobación",
                        "La solicitud requiere aprobación del Ing. Luis Eduardo. "
                        "Quedó registrada en la pantalla Hoy para desbloquearla cuando te confirme.",
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
