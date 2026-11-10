"""Pantalla 2: Planear el día — RF-01, RF-12.

Diseño limpio, espacioso y sin elementos confusos:
- Formulario directo para planear tareas matutinas con actividad, categoría,
  tiempo estimado opcional y prioridad.
- No exige adivinar cantidades por adelantado (las piezas o flyers adicionales
  se inician sobre la marcha según lleguen durante la jornada).
- Lista clara de lo planeado con opción de quitar si hubo un error.
- Resumen generado en tiempo real listo para copiar a WhatsApp en 1 clic.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from data.db import BaseDatos
from data.enums import EstadoActividad, Prioridad, TipoActividad
from data.models import Actividad
from data.repositorios.catalogos import RepoCategorias, RepoPlantillas
from data.repositorios.jornadas import RepoJornadas
from services.actividades import ServicioActividades
from services.whatsapp import ServicioWhatsApp, copiar_al_portapapeles


class PantallaPlanear(QWidget):
    """Pantalla para planear las actividades de la mañana y copiar el plan a WhatsApp."""

    def __init__(
        self,
        bd: BaseDatos,
        *,
        al_cambiar_plan: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bd = bd
        self.al_cambiar_plan = al_cambiar_plan

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        lbl_tit = QLabel("Planear mis actividades del día", self)
        lbl_tit.setObjectName("tituloPantalla")
        lbl_sub = QLabel(
            "Paso 1: Agrega las tareas previstas para hoy · "
            "Paso 2: Pulsa «Copiar plan para WhatsApp» y envíalo a tu grupo.",
            self,
        )
        lbl_sub.setObjectName("subtitulo")
        layout.addWidget(lbl_tit)
        layout.addWidget(lbl_sub)

        # Formulario limpio de agregar actividad
        card_alta = QFrame(self)
        card_alta.setProperty("card", True)
        capa_alta = QVBoxLayout(card_alta)
        capa_alta.setContentsMargins(16, 14, 16, 14)
        capa_alta.setSpacing(12)

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

        self.btn_nueva_cat = QPushButton("➕ Nueva", self)
        self.btn_nueva_cat.setProperty("rol", "secundario")
        self.btn_nueva_cat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nueva_cat.setToolTip("Crear una nueva categoría en el sistema")
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

        self.btn_agregar = QPushButton("➕  Agregar a mi plan de hoy", self)
        self.btn_agregar.setProperty("rol", "exito")
        self.btn_agregar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_agregar.clicked.connect(self.accion_agregar_planeada)
        self.txt_nombre.returnPressed.connect(self.accion_agregar_planeada)

        fila2.addWidget(lbl_est)
        fila2.addWidget(self.spin_estimado)
        fila2.addWidget(lbl_prio)
        fila2.addWidget(self.combo_prioridad)
        fila2.addStretch()
        fila2.addWidget(self.btn_agregar)
        capa_alta.addLayout(fila2)
        layout.addWidget(card_alta)

        # Tarjeta de plantillas recurrentes (se oculta automáticamente si no hay hoy)
        self.card_plant = QFrame(self)
        self.card_plant.setProperty("card", True)
        col_plant = QHBoxLayout(self.card_plant)
        col_plant.addWidget(QLabel("<b>✨ Plantillas sugeridas para hoy:</b>"))
        self.lista_plantillas = QListWidget(self)
        self.lista_plantillas.setMaximumHeight(64)
        col_plant.addWidget(self.lista_plantillas, 1)
        self.btn_aceptar_plantilla = QPushButton("✔ Agregar plantilla", self)
        self.btn_aceptar_plantilla.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_aceptar_plantilla.clicked.connect(self.accion_aceptar_plantilla)
        col_plant.addWidget(self.btn_aceptar_plantilla)
        layout.addWidget(self.card_plant)

        # Panel central dividido: Actividades en el plan (izq) y Mensaje WhatsApp (der)
        fila_central = QHBoxLayout()
        fila_central.setSpacing(14)

        card_lista_hoy = QFrame(self)
        card_lista_hoy.setProperty("card", True)
        col_hoy = QVBoxLayout(card_lista_hoy)
        col_hoy.setContentsMargins(14, 12, 14, 12)
        col_hoy.setSpacing(8)
        col_hoy.addWidget(QLabel("<b>📌 Actividades en tu plan de hoy</b>"))

        self.lista_planeadas_hoy = QListWidget(self)
        col_hoy.addWidget(self.lista_planeadas_hoy, 1)

        self.btn_quitar_planeada = QPushButton("🗑  Quitar actividad seleccionada del plan", self)
        self.btn_quitar_planeada.setProperty("rol", "secundario")
        self.btn_quitar_planeada.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quitar_planeada.clicked.connect(self.accion_quitar_planeada)
        col_hoy.addWidget(self.btn_quitar_planeada)

        card_wa = QFrame(self)
        card_wa.setProperty("card", True)
        col_wa = QVBoxLayout(card_wa)
        col_wa.setContentsMargins(14, 12, 14, 12)
        col_wa.setSpacing(8)
        col_wa.addWidget(QLabel("<b>💬 Mensaje listo para enviar por WhatsApp</b>"))

        self.txt_plan_whatsapp = QPlainTextEdit(self)
        col_wa.addWidget(self.txt_plan_whatsapp, 1)

        self.btn_copiar_wa = QPushButton("📋  Copiar plan para WhatsApp", self)
        self.btn_copiar_wa.setProperty("rol", "exito")
        self.btn_copiar_wa.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copiar_wa.clicked.connect(self.accion_copiar_whatsapp)
        col_wa.addWidget(self.btn_copiar_wa)

        fila_central.addWidget(card_lista_hoy, 1)
        fila_central.addWidget(card_wa, 1)
        layout.addLayout(fila_central, 1)

        with self.bd.sesion() as s:
            RepoCategorias(s).asegurar_categorias_base()
        self.refrescar()

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

            self.lista_planeadas_hoy.clear()
            visibles = [
                a
                for a in srv_act.listar_visibles_jornada(jornada.id)
                if a.tipo == TipoActividad.PLANEADA.value and not a.es_revision
            ]
            if not visibles:
                self.lista_planeadas_hoy.addItem(
                    "Aún no has agregado actividades planeadas hoy."
                )
                self.btn_quitar_planeada.setEnabled(False)
            else:
                self.btn_quitar_planeada.setEnabled(True)
                for idx, act in enumerate(visibles, start=1):
                    cat = f" [{act.categoria.nombre}]" if act.categoria else ""
                    est = f" · {act.tiempo_estimado_min} min" if act.tiempo_estimado_min else ""
                    item = QListWidgetItem(f"{idx}. {act.nombre}{cat}{est}")
                    item.setData(Qt.ItemDataRole.UserRole, act.id)
                    self.lista_planeadas_hoy.addItem(item)

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

    def accion_quitar_planeada(self) -> None:
        item = self.lista_planeadas_hoy.currentItem()
        if not item:
            QMessageBox.information(
                self,
                "Selecciona una actividad",
                "Elige en la lista la actividad que deseas quitar de tu plan.",
            )
            return
        act_id = item.data(Qt.ItemDataRole.UserRole)
        if act_id is None:
            return

        with self.bd.sesion() as s:
            act = s.get(Actividad, int(act_id))
            if act is not None:
                ServicioActividades(s).cambiar_estado_manual(
                    act, EstadoActividad.ELIMINADA, motivo="Quitada del plan por el usuario"
                )
        self.refrescar()
        if self.al_cambiar_plan:
            self.al_cambiar_plan()

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
        QMessageBox.information(
            self,
            "Plan copiado",
            "El plan del día se copió al portapapeles.\nYa puedes pegarlo (Ctrl+V) en el grupo de WhatsApp.",
        )
