"""Pantalla 2: Planear el día — RF-01, RF-12.

Incluye:
- Alta rápida de actividades planeadas con **autocompletado** de actividades y
  categorías usadas anteriormente.
- Opción de crear 1 actividad o un lote de N piezas (ej. 10 flyers).
- Tarjeta de **Plantillas y recurrentes propuestas para hoy** (aceptar en 1 clic).
- Vista previa editable y botón permanente **"📋 Copiar plan para WhatsApp"**.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFrame,
    QHBoxLayout,
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
from data.enums import Prioridad
from data.models import Plantilla
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
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        lbl_tit = QLabel("Planear actividades del día", self)
        lbl_tit.setObjectName("tituloPantalla")
        layout.addWidget(lbl_tit)

        # Formulario de alta rápida con autocompletado
        card_alta = QFrame(self)
        card_alta.setProperty("card", True)
        capa_alta = QVBoxLayout(card_alta)

        fila1 = QHBoxLayout()
        self.txt_nombre = QLineEdit(self)
        self.txt_nombre.setPlaceholderText("Nombre de la actividad (ej. Flyer vacante, Animación...)")
        self.modelo_autocompletar = QStringListModel(self)
        self.completer = QCompleter(self.modelo_autocompletar, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.txt_nombre.setCompleter(self.completer)

        self.txt_categoria = QLineEdit(self)
        self.txt_categoria.setPlaceholderText("Categoría libre (ej. Flyers, Videos...)")
        self.modelo_cat = QStringListModel(self)
        self.completer_cat = QCompleter(self.modelo_cat, self)
        self.completer_cat.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.txt_categoria.setCompleter(self.completer_cat)

        fila1.addWidget(QLabel("Actividad:"))
        fila1.addWidget(self.txt_nombre, 2)
        fila1.addWidget(QLabel("Categoría:"))
        fila1.addWidget(self.txt_categoria, 1)
        capa_alta.addLayout(fila1)

        fila2 = QHBoxLayout()
        self.spin_estimado = QSpinBox(self)
        self.spin_estimado.setRange(0, 600)
        self.spin_estimado.setSuffix(" min est.")
        self.spin_estimado.setSpecialValueText("Sin estimado")

        self.spin_cantidad = QSpinBox(self)
        self.spin_cantidad.setRange(1, 100)
        self.spin_cantidad.setValue(1)
        self.spin_cantidad.setSuffix(" pieza(s)")

        self.combo_prioridad = QComboBox(self)
        for p in (Prioridad.NORMAL, Prioridad.MAXIMA, Prioridad.MINIMA):
            self.combo_prioridad.addItem(p.etiqueta(), p.value)

        self.btn_agregar = QPushButton("+ Agregar al plan", self)
        self.btn_agregar.clicked.connect(self.accion_agregar_planeada)
        self.txt_nombre.returnPressed.connect(self.accion_agregar_planeada)

        fila2.addWidget(QLabel("Estimado:"))
        fila2.addWidget(self.spin_estimado)
        fila2.addWidget(QLabel("Cantidad:"))
        fila2.addWidget(self.spin_cantidad)
        fila2.addWidget(QLabel("Prioridad:"))
        fila2.addWidget(self.combo_prioridad)
        fila2.addStretch()
        fila2.addWidget(self.btn_agregar)
        capa_alta.addLayout(fila2)
        layout.addWidget(card_alta)

        # Panel central: Plantillas propuestas (izq) + Texto para WhatsApp (der)
        fila_central = QHBoxLayout()

        card_plant = QFrame(self)
        card_plant.setProperty("card", True)
        col_plant = QVBoxLayout(card_plant)
        col_plant.addWidget(QLabel("<b>Plantillas y recurrentes propuestas para hoy</b>"))
        self.lista_plantillas = QListWidget(self)
        col_plant.addWidget(self.lista_plantillas, 1)
        self.btn_aceptar_plantilla = QPushButton("✔ Agregar plantilla seleccionada al plan", self)
        self.btn_aceptar_plantilla.clicked.connect(self.accion_aceptar_plantilla)
        col_plant.addWidget(self.btn_aceptar_plantilla)

        card_wa = QFrame(self)
        card_wa.setProperty("card", True)
        col_wa = QVBoxLayout(card_wa)
        col_wa.addWidget(QLabel("<b>Listado para el grupo de WhatsApp (editable)</b>"))
        self.txt_plan_whatsapp = QPlainTextEdit(self)
        col_wa.addWidget(self.txt_plan_whatsapp, 1)
        self.btn_copiar_wa = QPushButton("📋 Copiar plan para WhatsApp", self)
        self.btn_copiar_wa.setProperty("rol", "exito")
        self.btn_copiar_wa.clicked.connect(self.accion_copiar_whatsapp)
        col_wa.addWidget(self.btn_copiar_wa)

        fila_central.addWidget(card_plant, 1)
        fila_central.addWidget(card_wa, 1)
        layout.addLayout(fila_central, 1)

        self.refrescar()

    def refrescar(self) -> None:
        with self.bd.sesion() as s:
            srv_act = ServicioActividades(s)
            repo_cat = RepoCategorias(s)
            repo_plant = RepoPlantillas(s)
            jornada = RepoJornadas(s).obtener_o_crear()

            self.modelo_autocompletar.setStringList(srv_act.nombres_para_autocompletado())
            self.modelo_cat.setStringList([c.nombre for c in repo_cat.listar_activas()])

            self.lista_plantillas.clear()
            for p in repo_plant.propuestas_para_fecha(jornada.fecha):
                est = f" ({p.tiempo_estimado_min} min)" if p.tiempo_estimado_min else ""
                item = QListWidgetItem(f"{p.nombre}{est} [{p.recurrencia}]")
                item.setData(Qt.ItemDataRole.UserRole, p.id)
                self.lista_plantillas.addItem(item)

            texto = ServicioWhatsApp(s).generar_texto_plan(jornada)
            self.txt_plan_whatsapp.setPlainText(texto)

    def accion_agregar_planeada(self) -> None:
        nombre = self.txt_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Nombre requerido", "Escribe el nombre de la actividad.")
            return

        cat_txt = self.txt_categoria.text().strip()
        estimado = int(self.spin_estimado.value()) or None
        cantidad = int(self.spin_cantidad.value())
        prioridad = str(self.combo_prioridad.currentData())

        with self.bd.sesion() as s:
            cat_id = (
                RepoCategorias(s).obtener_o_crear(cat_txt).id if cat_txt else None
            )
            srv_act = ServicioActividades(s)
            if cantidad == 1:
                srv_act.crear_planeada(
                    nombre,
                    categoria_id=cat_id,
                    tiempo_estimado_min=estimado,
                    prioridad=prioridad,
                )
            else:
                srv_act.crear_lote_piezas(
                    nombre,
                    cantidad,
                    categoria_id=cat_id,
                    tiempo_estimado_min=estimado,
                    prioridad=prioridad,
                )

        self.txt_nombre.clear()
        self.spin_cantidad.setValue(1)
        self.refrescar()
        if self.al_cambiar_plan:
            self.al_cambiar_plan()

    def accion_aceptar_plantilla(self) -> None:
        item = self.lista_plantillas.currentItem()
        if item is None:
            return
        plant_id = int(item.data(Qt.ItemDataRole.UserRole))
        cantidad = int(self.spin_cantidad.value())

        with self.bd.sesion() as s:
            plantilla = s.get(Plantilla, plant_id)
            if plantilla is not None:
                ServicioActividades(s).crear_desde_plantilla(plantilla, cantidad=cantidad)

        self.refrescar()
        if self.al_cambiar_plan:
            self.al_cambiar_plan()

    def accion_copiar_whatsapp(self) -> None:
        texto = self.txt_plan_whatsapp.toPlainText()
        copiar_al_portapapeles(texto)
        QMessageBox.information(
            self,
            "Plan copiado",
            "El plan del día se copió al portapapeles. Ya puedes pegarlo en el grupo de WhatsApp.",
        )
