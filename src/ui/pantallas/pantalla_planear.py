"""Pantalla 2: Planear el día — RF-01, RF-12.

Diseño intuitivo, moderno y libre de sobrecargas:
- Encabezado ejecutivo con chips de métricas en vivo: fecha, total de tareas y tiempo estimado.
- Formulario de alta rápido con autocompletado y botones directos de 1 clic para tareas frecuentes.
- Tabla clara de actividades con badges de categoría y prioridad.
- Controles de gestión: subir / bajar orden, editar datos, quitar actividad o iniciar cronómetro de inmediato.
- Vista previa de WhatsApp con botón de copia con confirmación visual instantánea.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QStringListModel, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from data.db import BaseDatos
from data.enums import EstadoActividad, Prioridad, TipoActividad
from data.models import Actividad
from data.repositorios.catalogos import RepoCategorias, RepoPlantillas
from data.repositorios.jornadas import RepoJornadas
from services.actividades import ServicioActividades
from services.cronometro import ActividadYaEnCursoError, ServicioCronometro
from services.whatsapp import ServicioWhatsApp, copiar_al_portapapeles
from ui.iconos import configurar_boton


def _formatear_fecha_es(fecha: date) -> str:
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    return f"{dias[fecha.weekday()]}, {fecha.day} de {meses[fecha.month - 1]}"


def _etiqueta_prioridad_visual(prio: str) -> str:
    if prio == Prioridad.MAXIMA.value:
        return "🔥 Alta"
    if prio == Prioridad.MINIMA.value:
        return "☕ Baja"
    return "Normal"


class DialogoEditarPlaneada(QDialog):
    """Diálogo modal limpio para corregir o afinar una actividad del plan matutino."""

    def __init__(
        self,
        nombre: str,
        categoria_actual: str,
        categorias_disponibles: list[str],
        estimado_min: int | None,
        prioridad: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar actividad del plan")
        self.setMinimumWidth(380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        lbl = QLabel("<b>Ajustar datos de la actividad planeada:</b>", self)
        layout.addWidget(lbl)

        form = QFormLayout()
        form.setSpacing(10)

        self.txt_nombre = QLineEdit(nombre, self)
        form.addRow("Actividad:", self.txt_nombre)

        self.combo_categoria = QComboBox(self)
        self.combo_categoria.setEditable(True)
        cats = list(dict.fromkeys(([categoria_actual] if categoria_actual else []) + categorias_disponibles))
        for c in cats:
            if c:
                self.combo_categoria.addItem(c)
        if categoria_actual:
            self.combo_categoria.setCurrentText(categoria_actual)
        form.addRow("Categoría:", self.combo_categoria)

        self.spin_estimado = QSpinBox(self)
        self.spin_estimado.setRange(0, 600)
        self.spin_estimado.setSuffix(" min")
        self.spin_estimado.setSpecialValueText("Sin estimado")
        self.spin_estimado.setValue(estimado_min or 0)
        form.addRow("Tiempo estimado:", self.spin_estimado)

        self.combo_prioridad = QComboBox(self)
        for p in (Prioridad.NORMAL, Prioridad.MAXIMA, Prioridad.MINIMA):
            self.combo_prioridad.addItem(p.etiqueta(), p.value)
        idx_p = self.combo_prioridad.findData(prioridad)
        if idx_p >= 0:
            self.combo_prioridad.setCurrentIndex(idx_p)
        form.addRow("Prioridad:", self.combo_prioridad)

        layout.addLayout(form)

        fila_botones = QHBoxLayout()
        fila_botones.addStretch()
        self.btn_cancelar = QPushButton("Cancelar", self)
        self.btn_cancelar.setProperty("rol", "secundario")
        self.btn_cancelar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancelar.clicked.connect(self.reject)

        self.btn_guardar = QPushButton("  Guardar cambios", self)
        self.btn_guardar.setProperty("rol", "exito")
        self.btn_guardar.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_guardar, "check")
        self.btn_guardar.clicked.connect(self.accept)

        fila_botones.addWidget(self.btn_cancelar)
        fila_botones.addWidget(self.btn_guardar)
        layout.addLayout(fila_botones)


class PantallaPlanear(QWidget):
    """Pantalla para planear las actividades de la mañana y copiar el plan a WhatsApp."""

    def __init__(
        self,
        bd: BaseDatos,
        *,
        al_cambiar_plan: Callable[[], None] | None = None,
        al_ir_a_hoy: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bd = bd
        self.al_cambiar_plan = al_cambiar_plan
        self.al_ir_a_hoy = al_ir_a_hoy

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        # 1. Cabecera con título e indicadores clave en vivo
        fila_cabecera = QHBoxLayout()
        fila_cabecera.setSpacing(12)

        col_tit = QVBoxLayout()
        col_tit.setSpacing(2)
        lbl_tit = QLabel("Planear mis actividades del día", self)
        lbl_tit.setObjectName("tituloPantalla")
        lbl_sub = QLabel(
            "Paso 1: Agrega las tareas previstas para hoy · Paso 2: Copia el mensaje para WhatsApp.",
            self,
        )
        lbl_sub.setObjectName("subtitulo")
        col_tit.addWidget(lbl_tit)
        col_tit.addWidget(lbl_sub)
        fila_cabecera.addLayout(col_tit, 1)

        self.lbl_chip_fecha = QLabel(self)
        self.lbl_chip_fecha.setObjectName("chipMetricaPlan")

        self.lbl_chip_total = QLabel(self)
        self.lbl_chip_total.setObjectName("chipMetricaPlan")

        self.lbl_chip_tiempo = QLabel(self)
        self.lbl_chip_tiempo.setObjectName("chipMetricaPlan")

        fila_cabecera.addWidget(self.lbl_chip_fecha)
        fila_cabecera.addWidget(self.lbl_chip_total)
        fila_cabecera.addWidget(self.lbl_chip_tiempo)
        layout.addLayout(fila_cabecera)

        # 2. Formulario limpio y ágil de alta de tareas
        card_alta = QFrame(self)
        card_alta.setProperty("card", True)
        capa_alta = QVBoxLayout(card_alta)
        capa_alta.setContentsMargins(16, 14, 16, 14)
        capa_alta.setSpacing(10)

        fila1 = QHBoxLayout()
        fila1.setSpacing(10)
        lbl_act = QLabel("<b>Actividad:</b>", self)
        self.txt_nombre = QLineEdit(self)
        self.txt_nombre.setPlaceholderText(
            "¿Qué tarea vas a realizar? (ej. Flyers, Video institucional, Campaña...)"
        )
        self.modelo_autocompletar = QStringListModel(self)
        self.completer = QCompleter(self.modelo_autocompletar, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.txt_nombre.setCompleter(self.completer)

        lbl_cat = QLabel("<b>Categoría:</b>", self)
        self.combo_categoria = QComboBox(self)
        self.combo_categoria.setEditable(True)
        self.combo_categoria.setMinimumWidth(180)
        self.txt_categoria = self.combo_categoria.lineEdit()
        if self.txt_categoria is not None:
            self.txt_categoria.setPlaceholderText("Selecciona o escribe categoría")

        self.btn_nueva_cat = QPushButton("  Nueva", self)
        self.btn_nueva_cat.setProperty("rol", "secundario")
        self.btn_nueva_cat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nueva_cat.setToolTip("Crear una nueva categoría en el sistema")
        configurar_boton(self.btn_nueva_cat, "plus", color="#0F172A", tamano=12)
        self.btn_nueva_cat.clicked.connect(self.accion_crear_categoria)

        fila1.addWidget(lbl_act)
        fila1.addWidget(self.txt_nombre, 3)
        fila1.addWidget(lbl_cat)
        fila1.addWidget(self.combo_categoria, 2)
        fila1.addWidget(self.btn_nueva_cat)
        capa_alta.addLayout(fila1)

        fila2 = QHBoxLayout()
        fila2.setSpacing(10)
        lbl_est = QLabel("Tiempo estimado (opcional):", self)
        self.spin_estimado = QSpinBox(self)
        self.spin_estimado.setRange(0, 600)
        self.spin_estimado.setSuffix(" min")
        self.spin_estimado.setSpecialValueText("Sin estimado")

        lbl_prio = QLabel("Prioridad:", self)
        self.combo_prioridad = QComboBox(self)
        for p in (Prioridad.NORMAL, Prioridad.MAXIMA, Prioridad.MINIMA):
            self.combo_prioridad.addItem(p.etiqueta(), p.value)

        self.btn_agregar = QPushButton("  Agregar a mi plan de hoy", self)
        self.btn_agregar.setProperty("rol", "exito")
        self.btn_agregar.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_agregar, "plus")
        self.btn_agregar.clicked.connect(self.accion_agregar_planeada)
        self.txt_nombre.returnPressed.connect(self.accion_agregar_planeada)

        fila2.addWidget(lbl_est)
        fila2.addWidget(self.spin_estimado)
        fila2.addWidget(lbl_prio)
        fila2.addWidget(self.combo_prioridad)
        fila2.addStretch()
        fila2.addWidget(self.btn_agregar)
        capa_alta.addLayout(fila2)

        # Fila 3: Chips rápidos de 1 clic para tareas frecuentes del equipo
        fila_chips = QHBoxLayout()
        fila_chips.setSpacing(8)
        lbl_frec = QLabel("⚡ Tareas frecuentes (1 clic):", self)
        lbl_frec.setStyleSheet("font-weight: 700; font-size: 13px; padding-right: 4px;")
        fila_chips.addWidget(lbl_frec)

        self.btn_chip_flyers = QPushButton("  + Flyers", self)
        self.btn_chip_redes = QPushButton("  + Redes sociales", self)
        self.btn_chip_video = QPushButton("  + Video / Animación", self)
        self.btn_chip_diseno = QPushButton("  + Diseño general", self)

        for chip in (self.btn_chip_flyers, self.btn_chip_redes, self.btn_chip_video, self.btn_chip_diseno):
            chip.setProperty("chip", True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            fila_chips.addWidget(chip)

        configurar_boton(self.btn_chip_flyers, "zap", tamano=12)
        configurar_boton(self.btn_chip_redes, "plus", tamano=12)
        configurar_boton(self.btn_chip_video, "plus", tamano=12)
        configurar_boton(self.btn_chip_diseno, "plus", tamano=12)

        self.btn_chip_flyers.setToolTip("Agrega inmediatamente la tarea de Flyers al plan de hoy")
        self.btn_chip_redes.setToolTip("Agrega posts para Instagram o historias")
        self.btn_chip_video.setToolTip("Agrega edición de video o animación")
        self.btn_chip_diseno.setToolTip("Agrega pieza de diseño gráfico general")

        self.btn_chip_flyers.clicked.connect(lambda: self.accion_agregar_chip("Flyers", "Flyers"))
        self.btn_chip_redes.clicked.connect(lambda: self.accion_agregar_chip("Posts de redes sociales", "Redes sociales"))
        self.btn_chip_video.clicked.connect(lambda: self.accion_agregar_chip("Video / Animación", "Videos"))
        self.btn_chip_diseno.clicked.connect(lambda: self.accion_agregar_chip("Diseño gráfico general", "Diseño"))

        fila_chips.addStretch()
        capa_alta.addLayout(fila_chips)
        layout.addWidget(card_alta)

        # 3. Tarjeta de plantillas recurrentes (se oculta automáticamente si no hay hoy)
        self.card_plant = QFrame(self)
        self.card_plant.setProperty("card", True)
        col_plant = QHBoxLayout(self.card_plant)
        col_plant.addWidget(QLabel("<b>Plantillas sugeridas para hoy:</b>"))
        self.lista_plantillas = QListWidget(self)
        self.lista_plantillas.setMaximumHeight(64)
        col_plant.addWidget(self.lista_plantillas, 1)
        self.btn_aceptar_plantilla = QPushButton("  Agregar plantilla", self)
        self.btn_aceptar_plantilla.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_aceptar_plantilla, "check", color="#0F172A")
        self.btn_aceptar_plantilla.clicked.connect(self.accion_aceptar_plantilla)
        col_plant.addWidget(self.btn_aceptar_plantilla)
        layout.addWidget(self.card_plant)

        # 4. Panel central dividido: Actividades en el plan (izq) y Mensaje WhatsApp (der)
        fila_central = QHBoxLayout()
        fila_central.setSpacing(14)

        # Columna Izquierda: Tabla interactiva del plan de hoy
        card_tabla = QFrame(self)
        card_tabla.setProperty("card", True)
        col_tabla = QVBoxLayout(card_tabla)
        col_tabla.setContentsMargins(14, 12, 14, 12)
        col_tabla.setSpacing(10)

        fila_tit_tabla = QHBoxLayout()
        lbl_tit_tabla = QLabel("<b>Actividades en tu plan de hoy</b>", self)
        lbl_guia_tabla = QLabel("(doble clic para editar)", self)
        lbl_guia_tabla.setObjectName("subtitulo")
        fila_tit_tabla.addWidget(lbl_tit_tabla)
        fila_tit_tabla.addWidget(lbl_guia_tabla)
        fila_tit_tabla.addStretch()
        col_tabla.addLayout(fila_tit_tabla)

        self.tabla_planeadas = QTableWidget(0, 5, self)
        self.tabla_planeadas.setHorizontalHeaderLabels(
            ["#", "Actividad", "Categoría", "Estimado", "Prioridad"]
        )
        self.tabla_planeadas.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_planeadas.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla_planeadas.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla_planeadas.setAlternatingRowColors(True)
        self.tabla_planeadas.setShowGrid(False)
        self.tabla_planeadas.verticalHeader().setVisible(False)
        self.tabla_planeadas.verticalHeader().setDefaultSectionSize(40)
        self.tabla_planeadas.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.tabla_planeadas.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla_planeadas.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_planeadas.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tabla_planeadas.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.tabla_planeadas.setColumnWidth(0, 42)
        self.tabla_planeadas.setColumnWidth(3, 95)
        self.tabla_planeadas.setColumnWidth(4, 95)
        self.tabla_planeadas.itemSelectionChanged.connect(self._actualizar_estado_botones)
        self.tabla_planeadas.cellDoubleClicked.connect(self.accion_editar_planeada)
        col_tabla.addWidget(self.tabla_planeadas, 1)

        # Alias de compatibilidad
        self.lista_planeadas_hoy = self.tabla_planeadas

        # Barra de acciones de la tabla
        fila_acciones = QHBoxLayout()
        fila_acciones.setSpacing(6)

        self.btn_subir = QPushButton("  Subir", self)
        self.btn_subir.setProperty("rol", "secundario")
        self.btn_subir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_subir.setToolTip("Mueve la actividad hacia arriba en la lista y en el mensaje")
        configurar_boton(self.btn_subir, "chevron-up", color="#0F172A", tamano=12)
        self.btn_subir.clicked.connect(self.accion_subir_planeada)

        self.btn_bajar = QPushButton("  Bajar", self)
        self.btn_bajar.setProperty("rol", "secundario")
        self.btn_bajar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bajar.setToolTip("Mueve la actividad hacia abajo en la lista y en el mensaje")
        configurar_boton(self.btn_bajar, "chevron-down", color="#0F172A", tamano=12)
        self.btn_bajar.clicked.connect(self.accion_bajar_planeada)

        self.btn_editar = QPushButton("  Editar", self)
        self.btn_editar.setProperty("rol", "secundario")
        self.btn_editar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_editar.setToolTip("Modifica el nombre, categoría o tiempo estimado")
        configurar_boton(self.btn_editar, "edit", color="#0F172A", tamano=12)
        self.btn_editar.clicked.connect(self.accion_editar_planeada)

        self.btn_quitar_planeada = QPushButton("  Quitar", self)
        self.btn_quitar_planeada.setProperty("rol", "secundario")
        self.btn_quitar_planeada.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quitar_planeada.setToolTip("Quita la actividad seleccionada del plan de hoy")
        configurar_boton(self.btn_quitar_planeada, "trash", color="#0F172A", tamano=12)
        self.btn_quitar_planeada.clicked.connect(self.accion_quitar_planeada)

        self.btn_limpiar_todo = QPushButton("  Limpiar todo el plan", self)
        self.btn_limpiar_todo.setProperty("rol", "secundario")
        self.btn_limpiar_todo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_limpiar_todo.setToolTip("Vacía todas las actividades planeadas de hoy para empezar de cero")
        configurar_boton(self.btn_limpiar_todo, "trash-2", color="#DC2626", tamano=12)
        self.btn_limpiar_todo.clicked.connect(self.accion_limpiar_todo_el_plan)

        self.btn_iniciar_ahora = QPushButton("  ▶ Iniciar tarea ya", self)
        self.btn_iniciar_ahora.setProperty("rol", "exito")
        self.btn_iniciar_ahora.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_iniciar_ahora.setToolTip("Pasa de inmediato al cronómetro de Hoy con esta actividad corriendo")
        self.btn_iniciar_ahora.clicked.connect(self.accion_iniciar_planeada)

        fila_acciones.addWidget(self.btn_subir)
        fila_acciones.addWidget(self.btn_bajar)
        fila_acciones.addWidget(self.btn_editar)
        fila_acciones.addWidget(self.btn_quitar_planeada)
        fila_acciones.addWidget(self.btn_limpiar_todo)
        fila_acciones.addStretch()
        fila_acciones.addWidget(self.btn_iniciar_ahora)
        col_tabla.addLayout(fila_acciones)

        # Columna Derecha: Vista previa de WhatsApp
        card_wa = QFrame(self)
        card_wa.setProperty("card", True)
        col_wa = QVBoxLayout(card_wa)
        col_wa.setContentsMargins(14, 12, 14, 12)
        col_wa.setSpacing(8)

        lbl_tit_wa = QLabel("<b>Mensaje listo para enviar por WhatsApp</b>", self)
        col_wa.addWidget(lbl_tit_wa)

        self.txt_plan_whatsapp = QPlainTextEdit(self)
        self.txt_plan_whatsapp.setPlaceholderText(
            "El mensaje para tu jefe y equipo se generará aquí automáticamente..."
        )
        col_wa.addWidget(self.txt_plan_whatsapp, 1)

        self.lbl_feedback_wa = QLabel("", self)
        self.lbl_feedback_wa.setStyleSheet("color: #16A34A; font-weight: 600; font-size: 11px;")
        self.lbl_feedback_wa.setVisible(False)
        col_wa.addWidget(self.lbl_feedback_wa)

        fila_wa_btns = QHBoxLayout()
        fila_wa_btns.setSpacing(8)

        self.btn_copiar_wa = QPushButton("  Copiar plan para WhatsApp", self)
        self.btn_copiar_wa.setProperty("rol", "exito")
        self.btn_copiar_wa.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_copiar_wa, "copy")
        self.btn_copiar_wa.clicked.connect(self.accion_copiar_whatsapp)

        self.btn_ir_a_hoy = QPushButton("  🚀 Ir al cronómetro", self)
        self.btn_ir_a_hoy.setProperty("rol", "secundario")
        self.btn_ir_a_hoy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ir_a_hoy.setToolTip("Comenzar a registrar tu jornada en la pantalla de Hoy")
        configurar_boton(self.btn_ir_a_hoy, "clock", color="#0F172A", tamano=13)
        self.btn_ir_a_hoy.clicked.connect(self._navegar_a_hoy)

        fila_wa_btns.addWidget(self.btn_copiar_wa, 2)
        fila_wa_btns.addWidget(self.btn_ir_a_hoy, 1)
        col_wa.addLayout(fila_wa_btns)

        fila_central.addWidget(card_tabla, 3)
        fila_central.addWidget(card_wa, 2)
        layout.addLayout(fila_central, 1)

        with self.bd.sesion() as s:
            RepoCategorias(s).asegurar_categorias_base()
        self.refrescar()

    def _navegar_a_hoy(self) -> None:
        if self.al_ir_a_hoy:
            self.al_ir_a_hoy()

    def fila_seleccionada(self) -> int:
        """Devuelve el índice de la fila seleccionada, ya sea por celda actual o selección visual."""
        row = self.tabla_planeadas.currentRow()
        if row >= 0:
            return row
        sel_ranges = self.tabla_planeadas.selectedRanges()
        if sel_ranges:
            return sel_ranges[0].topRow()
        items = self.tabla_planeadas.selectedItems()
        if items:
            return items[0].row()
        return -1

    def _actualizar_estado_botones(self) -> None:
        row = self.fila_seleccionada()
        count = self.tabla_planeadas.rowCount()
        has_sel = row >= 0
        self.btn_subir.setEnabled(has_sel and row > 0)
        self.btn_bajar.setEnabled(has_sel and row < count - 1)
        self.btn_editar.setEnabled(has_sel)
        self.btn_quitar_planeada.setEnabled(has_sel)
        self.btn_limpiar_todo.setEnabled(count > 0)
        self.btn_iniciar_ahora.setEnabled(has_sel)

    def refrescar(self) -> None:
        texto_cat_actual = self.combo_categoria.currentText().strip()
        with self.bd.sesion() as s:
            srv_act = ServicioActividades(s)
            repo_cat = RepoCategorias(s)
            repo_plant = RepoPlantillas(s)
            jornada = RepoJornadas(s).obtener_o_crear()

            self.modelo_autocompletar.setStringList(srv_act.nombres_para_autocompletado())
            categorias = repo_cat.listar_activas()
            nombres_cat = [c.nombre for c in categorias]

            self.combo_categoria.blockSignals(True)
            self.combo_categoria.clear()
            # Flyers siempre como primera sugerencia
            self.combo_categoria.addItem("Flyers")
            for nom in nombres_cat:
                if nom.strip().lower() != "flyers":
                    self.combo_categoria.addItem(nom)
            if texto_cat_actual:
                self.combo_categoria.setCurrentText(texto_cat_actual)
            else:
                self.combo_categoria.setCurrentIndex(0)
            self.combo_categoria.blockSignals(False)

            propuestas = repo_plant.propuestas_para_fecha(jornada.fecha)
            self.lista_plantillas.clear()
            for p in propuestas:
                est = f" ({p.tiempo_estimado_min} min)" if p.tiempo_estimado_min else ""
                item = QListWidgetItem(f"{p.nombre}{est}")
                item.setData(Qt.ItemDataRole.UserRole, p.id)
                self.lista_plantillas.addItem(item)
            self.card_plant.setVisible(len(propuestas) > 0)

            visibles = [
                a
                for a in srv_act.listar_visibles_jornada(jornada.id)
                if a.tipo == TipoActividad.PLANEADA.value and not a.es_revision
            ]

            # Actualizar chips de resumen del encabezado
            num_tareas = len(visibles)
            total_min = sum(a.tiempo_estimado_min or 0 for a in visibles)
            fecha_txt = _formatear_fecha_es(jornada.fecha)
            self.lbl_chip_fecha.setText(f"📅 {fecha_txt}")
            self.lbl_chip_total.setText(f"📋 {num_tareas} actividades")
            if total_min > 0:
                h, m = divmod(total_min, 60)
                t_txt = f"{h} h {m} min est." if h and m else (f"{h} h est." if h else f"{m} min est.")
                self.lbl_chip_tiempo.setText(f"⏱ {t_txt}")
            else:
                self.lbl_chip_tiempo.setText("⏱ Sin estimado")

            # Poblar tabla de actividades planeadas
            self.tabla_planeadas.setRowCount(len(visibles))
            for row_idx, act in enumerate(visibles):
                item_num = QTableWidgetItem(str(row_idx + 1))
                item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_num.setData(Qt.ItemDataRole.UserRole, act.id)

                item_nom = QTableWidgetItem(act.nombre)
                f_nom = item_nom.font()
                f_nom.setWeight(QFont.Weight.DemiBold)
                item_nom.setFont(f_nom)

                cat_nom = act.categoria.nombre if act.categoria else "Sin categoría"
                item_cat = QTableWidgetItem(cat_nom)

                est_str = f"{act.tiempo_estimado_min} min" if act.tiempo_estimado_min else "—"
                item_est = QTableWidgetItem(est_str)
                item_est.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                prio_str = _etiqueta_prioridad_visual(act.prioridad)
                item_prio = QTableWidgetItem(prio_str)
                item_prio.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                self.tabla_planeadas.setItem(row_idx, 0, item_num)
                self.tabla_planeadas.setItem(row_idx, 1, item_nom)
                self.tabla_planeadas.setItem(row_idx, 2, item_cat)
                self.tabla_planeadas.setItem(row_idx, 3, item_est)
                self.tabla_planeadas.setItem(row_idx, 4, item_prio)

            self._actualizar_estado_botones()

            texto = ServicioWhatsApp(s).generar_texto_plan(jornada)
            self.txt_plan_whatsapp.setPlainText(texto)

    def accion_crear_categoria(self) -> None:
        nombre, ok = QInputDialog.getText(
            self,
            "Nueva categoría",
            "Nombre de la nueva categoría (ej. Campañas, Diseño Editorial, etc.):",
        )
        if not ok or not nombre.strip():
            return
        limpio = nombre.strip()
        with self.bd.sesion() as s:
            RepoCategorias(s).obtener_o_crear(limpio)
        self.combo_categoria.setCurrentText(limpio)
        self.refrescar()

    def accion_agregar_planeada(self) -> None:
        nombre = self.txt_nombre.text().strip()
        cat_txt = self.combo_categoria.currentText().strip()

        # Si el usuario no escribió un nombre específico, usa el nombre de la categoría elegida
        if not nombre:
            if cat_txt:
                nombre = cat_txt
            else:
                QMessageBox.warning(
                    self,
                    "Actividad requerida",
                    "Escribe el nombre de la actividad o elige una categoría.",
                )
                return

        estimado = int(self.spin_estimado.value()) or None
        prioridad = str(self.combo_prioridad.currentData())

        with self.bd.sesion() as s:
            cat_id = (
                RepoCategorias(s).obtener_o_crear(cat_txt).id if cat_txt else None
            )
            ServicioActividades(s).crear_planeada(
                nombre,
                categoria_id=cat_id,
                tiempo_estimado_min=estimado,
                prioridad=prioridad,
            )

        self.txt_nombre.clear()
        self.txt_nombre.setFocus()
        self.refrescar()
        if self.al_cambiar_plan:
            self.al_cambiar_plan()

    def accion_agregar_chip(
        self, nombre_actividad: str, nombre_categoria: str, estimado_min: int | None = None
    ) -> None:
        """Agrega directamente una actividad frecuente con 1 clic."""
        estimado = int(self.spin_estimado.value()) or estimado_min
        prioridad = str(self.combo_prioridad.currentData())
        with self.bd.sesion() as s:
            cat = RepoCategorias(s).obtener_o_crear(nombre_categoria)
            ServicioActividades(s).crear_planeada(
                nombre_actividad,
                categoria_id=cat.id,
                tiempo_estimado_min=estimado,
                prioridad=prioridad,
            )
        self.refrescar()
        if self.al_cambiar_plan:
            self.al_cambiar_plan()

    def accion_quitar_planeada(self) -> None:
        row = self.fila_seleccionada()
        if row < 0:
            QMessageBox.information(
                self,
                "Selecciona una actividad",
                "Elige en la tabla la actividad que deseas quitar de tu plan.",
            )
            return
        item = self.tabla_planeadas.item(row, 0)
        if not item:
            return
        act_id = int(item.data(Qt.ItemDataRole.UserRole))

        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is not None:
                ServicioActividades(s).cambiar_estado_manual(
                    act, EstadoActividad.ELIMINADA, motivo="Quitada del plan por el usuario"
                )
        self.refrescar()
        if self.al_cambiar_plan:
            self.al_cambiar_plan()

    def accion_limpiar_todo_el_plan(self) -> None:
        """Vacía en 1 clic todas las actividades planeadas del día tras confirmación."""
        count = self.tabla_planeadas.rowCount()
        if count == 0:
            QMessageBox.information(
                self,
                "Plan vacío",
                "No tienes actividades en tu plan de hoy para limpiar.",
            )
            return

        resp = QMessageBox.question(
            self,
            "Limpiar todo el plan",
            f"¿Deseas vaciar las {count} actividades de tu plan de hoy para comenzar de cero?\n\n"
            "Esta acción quitará todas las tareas de la lista y del mensaje de WhatsApp.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        with self.bd.sesion() as s:
            jornada = RepoJornadas(s).obtener_o_crear()
            srv_act = ServicioActividades(s)
            visibles = [
                a
                for a in srv_act.listar_visibles_jornada(jornada.id)
                if a.tipo == TipoActividad.PLANEADA.value and not a.es_revision
            ]
            for act in visibles:
                srv_act.cambiar_estado_manual(
                    act, EstadoActividad.ELIMINADA, motivo="Plan vaciado por el usuario"
                )

        self.refrescar()
        if self.al_cambiar_plan:
            self.al_cambiar_plan()

    def accion_editar_planeada(self) -> None:
        row = self.fila_seleccionada()
        if row < 0:
            QMessageBox.information(
                self, "Selecciona una actividad", "Elige en la tabla la actividad que deseas editar."
            )
            return
        item = self.tabla_planeadas.item(row, 0)
        if not item:
            return
        act_id = int(item.data(Qt.ItemDataRole.UserRole))

        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if not act:
                return
            nombre_actual = act.nombre
            cat_actual = act.categoria.nombre if act.categoria else ""
            estimado_actual = act.tiempo_estimado_min
            prio_actual = act.prioridad
            repo_cat = RepoCategorias(s)
            nombres_cat = [c.nombre for c in repo_cat.listar_activas()]

        dlg = DialogoEditarPlaneada(
            nombre_actual,
            cat_actual,
            nombres_cat,
            estimado_actual,
            prio_actual,
            self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            nuevo_nom = dlg.txt_nombre.text().strip()
            nueva_cat = dlg.combo_categoria.currentText().strip()
            nuevo_est = int(dlg.spin_estimado.value()) or None
            nueva_prio = str(dlg.combo_prioridad.currentData())

            if not nuevo_nom:
                nuevo_nom = nueva_cat or nombre_actual

            with self.bd.sesion() as s:
                act = s.get(Actividad, act_id)
                if act:
                    cat_id = RepoCategorias(s).obtener_o_crear(nueva_cat).id if nueva_cat else None
                    act.nombre = nuevo_nom
                    act.categoria_id = cat_id
                    act.tiempo_estimado_min = nuevo_est
                    act.prioridad = nueva_prio

            self.refrescar()
            self.tabla_planeadas.setCurrentCell(row, 1)
            self.tabla_planeadas.selectRow(row)
            if self.al_cambiar_plan:
                self.al_cambiar_plan()

    def accion_subir_planeada(self) -> None:
        row = self.fila_seleccionada()
        if row <= 0:
            return
        self._intercambiar_filas(row, row - 1)

    def accion_bajar_planeada(self) -> None:
        row = self.fila_seleccionada()
        if row < 0 or row >= self.tabla_planeadas.rowCount() - 1:
            return
        self._intercambiar_filas(row, row + 1)

    def _intercambiar_filas(self, fila_a: int, fila_b: int) -> None:
        item_a = self.tabla_planeadas.item(fila_a, 0)
        item_b = self.tabla_planeadas.item(fila_b, 0)
        if not item_a or not item_b:
            return
        id_a = int(item_a.data(Qt.ItemDataRole.UserRole))
        id_b = int(item_b.data(Qt.ItemDataRole.UserRole))

        with self.bd.sesion() as s:
            act_a = s.get(Actividad, id_a)
            act_b = s.get(Actividad, id_b)
            if act_a and act_b:
                (
                    act_a.nombre, act_b.nombre,
                    act_a.categoria_id, act_b.categoria_id,
                    act_a.tiempo_estimado_min, act_b.tiempo_estimado_min,
                    act_a.prioridad, act_b.prioridad,
                    act_a.descripcion, act_b.descripcion,
                ) = (
                    act_b.nombre, act_a.nombre,
                    act_b.categoria_id, act_a.categoria_id,
                    act_b.tiempo_estimado_min, act_a.tiempo_estimado_min,
                    act_b.prioridad, act_a.prioridad,
                    act_b.descripcion, act_a.descripcion,
                )

        self.refrescar()
        self.tabla_planeadas.setCurrentCell(fila_b, 1)
        self.tabla_planeadas.selectRow(fila_b)
        if self.al_cambiar_plan:
            self.al_cambiar_plan()

    def accion_iniciar_planeada(self) -> None:
        """Inicia el cronómetro de la actividad planeada y lleva a la pantalla Hoy."""
        row = self.fila_seleccionada()
        if row < 0:
            QMessageBox.information(
                self, "Selecciona una actividad", "Elige en la tabla la actividad que deseas iniciar."
            )
            return
        item = self.tabla_planeadas.item(row, 0)
        if not item:
            return
        act_id = int(item.data(Qt.ItemDataRole.UserRole))

        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is None:
                return
            cron = ServicioCronometro(s)
            try:
                cron.iniciar(act)
            except ActividadYaEnCursoError as exc:
                resp = QMessageBox.question(
                    self,
                    "Ya hay una actividad en curso",
                    f"«{exc.actividad_activa.nombre}» está en curso actualmente.\n\n"
                    f"¿Deseas pausarla e iniciar «{act.nombre}»?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if resp == QMessageBox.StandardButton.Yes:
                    cron.pausar(exc.actividad_activa)
                    cron.iniciar(act)
                else:
                    return

        self.refrescar()
        if self.al_cambiar_plan:
            self.al_cambiar_plan()
        if self.al_ir_a_hoy:
            self.al_ir_a_hoy()

    def accion_aceptar_plantilla(self) -> None:
        item = self.lista_plantillas.currentItem()
        if item is None:
            return
        plant_id = int(item.data(Qt.ItemDataRole.UserRole))
        with self.bd.sesion() as s:
            plant = RepoPlantillas(s).obtener(plant_id)
            if plant is not None:
                ServicioActividades(s).crear_desde_plantilla(plant)
        self.refrescar()
        if self.al_cambiar_plan:
            self.al_cambiar_plan()

    def accion_copiar_whatsapp(self) -> None:
        texto = self.txt_plan_whatsapp.toPlainText()
        copiar_al_portapapeles(texto)
        self.btn_copiar_wa.setText("  ✓ ¡Plan copiado!")
        self.btn_copiar_wa.setStyleSheet("background-color: #15803D; color: #FFFFFF; font-weight: bold;")
        self.lbl_feedback_wa.setText("✓ Copiado al portapapeles. Pégalo en tu grupo de WhatsApp con Ctrl+V.")
        self.lbl_feedback_wa.setVisible(True)

        def restaurar() -> None:
            self.btn_copiar_wa.setText("  Copiar plan para WhatsApp")
            self.btn_copiar_wa.setStyleSheet("")
            configurar_boton(self.btn_copiar_wa, "copy")
            self.lbl_feedback_wa.setVisible(False)

        QTimer.singleShot(2500, restaurar)
