"""Pantalla 2: Planear el día — RF-01, RF-12.

Diseño sencillo e intuitivo:
- Barra superior de **Mandados rápidos (1 clic)**: botón directo «⚡ + Añadir Flyer rápido»
  y gestión de categorías propias («➕ Nueva categoría» / «🗑 Quitar categoría»).
- Formulario rápido con selector desplegable de categorías para agregar una actividad
  (o varias piezas iguales) con Enter.
- Si existen plantillas recurrentes para hoy, muestra una barra sugerida arriba; si
  no hay plantillas configuradas, oculta esa sección para no dejar cajas vacías.
- Al centro: lista clara de lo que ya planeaste hoy (izq) y el texto listo para
  copiar a WhatsApp en 1 clic (der).
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
from data.enums import Prioridad, TipoActividad
from data.repositorios.catalogos import RepoCategorias, RepoPlantillas
from data.repositorios.jornadas import RepoJornadas
from services.actividades import ServicioActividades
from services.cronometro import ServicioCronometro
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
        layout.setSpacing(12)

        lbl_tit = QLabel("Planear mis actividades del día", self)
        lbl_tit.setObjectName("tituloPantalla")
        lbl_sub = QLabel(
            "Paso 1: Agrega tus mandados de hoy (o usa «⚡ + Añadir Flyer rápido») · "
            "Paso 2: Pulsa «Copiar plan para WhatsApp».",
            self,
        )
        lbl_sub.setObjectName("subtitulo")
        layout.addWidget(lbl_tit)
        layout.addWidget(lbl_sub)

        # Barra de mandados rápidos (1 clic) y gestión de categorías
        card_rapidos = QFrame(self)
        card_rapidos.setProperty("card", True)
        fila_rapidos = QHBoxLayout(card_rapidos)
        fila_rapidos.setContentsMargins(12, 8, 12, 8)
        fila_rapidos.setSpacing(8)

        lbl_rap = QLabel("<b>⚡ Mandados rápidos:</b>", self)
        self.btn_flyer_rapido = QPushButton("⚡ + Añadir Flyer rápido al día", self)
        self.btn_flyer_rapido.setProperty("rol", "exito")
        self.btn_flyer_rapido.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_flyer_rapido.setToolTip(
            "Agrega inmediatamente el siguiente Flyer (Flyer 1, Flyer 2...) bajo la categoría Flyers"
        )
        self.btn_flyer_rapido.clicked.connect(self.accion_agregar_flyer_rapido)

        self.contenedor_chips = QWidget(self)
        self.layout_chips = QHBoxLayout(self.contenedor_chips)
        self.layout_chips.setContentsMargins(0, 0, 0, 0)
        self.layout_chips.setSpacing(6)

        self.btn_nueva_categoria = QPushButton("➕ Nueva categoría", self)
        self.btn_nueva_categoria.setProperty("rol", "secundario")
        self.btn_nueva_categoria.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nueva_categoria.clicked.connect(self.accion_crear_categoria)

        self.btn_quitar_categoria = QPushButton("🗑 Quitar categoría", self)
        self.btn_quitar_categoria.setProperty("rol", "secundario")
        self.btn_quitar_categoria.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quitar_categoria.clicked.connect(self.accion_quitar_categoria)

        fila_rapidos.addWidget(lbl_rap)
        fila_rapidos.addWidget(self.btn_flyer_rapido)
        fila_rapidos.addWidget(self.contenedor_chips)
        fila_rapidos.addStretch()
        fila_rapidos.addWidget(self.btn_nueva_categoria)
        fila_rapidos.addWidget(self.btn_quitar_categoria)
        layout.addWidget(card_rapidos)

        # Formulario de alta rápida con autocompletado y selector de categorías
        card_alta = QFrame(self)
        card_alta.setProperty("card", True)
        capa_alta = QVBoxLayout(card_alta)
        capa_alta.setSpacing(10)

        fila1 = QHBoxLayout()
        self.txt_nombre = QLineEdit(self)
        self.txt_nombre.setPlaceholderText(
            "¿Qué actividad vas a realizar? (ej. Flyer vacante, Video reel... o déjalo vacío para usar la categoría)"
        )
        self.modelo_autocompletar = QStringListModel(self)
        self.completer = QCompleter(self.modelo_autocompletar, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.txt_nombre.setCompleter(self.completer)

        self.combo_categoria = QComboBox(self)
        self.combo_categoria.setEditable(True)
        self.combo_categoria.setMinimumWidth(200)
        self.txt_categoria = self.combo_categoria.lineEdit()
        if self.txt_categoria is not None:
            self.txt_categoria.setPlaceholderText("Elige o escribe categoría (ej. Flyers)")
        self.modelo_cat = QStringListModel(self)
        self.completer_cat = QCompleter(self.modelo_cat, self)
        self.completer_cat.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.combo_categoria.setCompleter(self.completer_cat)

        fila1.addWidget(QLabel("<b>Actividad:</b>"))
        fila1.addWidget(self.txt_nombre, 2)
        fila1.addWidget(QLabel("<b>Categoría:</b>"))
        fila1.addWidget(self.combo_categoria, 1)
        capa_alta.addLayout(fila1)

        fila2 = QHBoxLayout()
        self.spin_estimado = QSpinBox(self)
        self.spin_estimado.setRange(0, 600)
        self.spin_estimado.setSuffix(" min")
        self.spin_estimado.setSpecialValueText("Sin estimado")

        self.spin_cantidad = QSpinBox(self)
        self.spin_cantidad.setRange(1, 100)
        self.spin_cantidad.setValue(1)
        self.spin_cantidad.setSuffix(" pieza(s)")

        self.combo_prioridad = QComboBox(self)
        for p in (Prioridad.NORMAL, Prioridad.MAXIMA, Prioridad.MINIMA):
            self.combo_prioridad.addItem(p.etiqueta(), p.value)

        self.btn_agregar = QPushButton("➕  Agregar a mi plan de hoy", self)
        self.btn_agregar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_agregar.clicked.connect(self.accion_agregar_planeada)
        self.txt_nombre.returnPressed.connect(self.accion_agregar_planeada)

        fila2.addWidget(QLabel("Tiempo estimado:"))
        fila2.addWidget(self.spin_estimado)
        fila2.addWidget(QLabel("¿Cuántas piezas iguales?:"))
        fila2.addWidget(self.spin_cantidad)
        fila2.addWidget(QLabel("Prioridad:"))
        fila2.addWidget(self.combo_prioridad)
        fila2.addStretch()
        fila2.addWidget(self.btn_agregar)
        capa_alta.addLayout(fila2)
        layout.addWidget(card_alta)

        # Tarjeta de plantillas recurrentes (se oculta automáticamente si no hay ninguna hoy)
        self.card_plant = QFrame(self)
        self.card_plant.setProperty("card", True)
        col_plant = QHBoxLayout(self.card_plant)
        col_plant.addWidget(QLabel("<b>✨ Plantillas frecuentes sugeridas para hoy:</b>"))
        self.lista_plantillas = QListWidget(self)
        self.lista_plantillas.setMaximumHeight(68)
        col_plant.addWidget(self.lista_plantillas, 1)
        self.btn_aceptar_plantilla = QPushButton("✔ Agregar plantilla seleccionada", self)
        self.btn_aceptar_plantilla.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_aceptar_plantilla.clicked.connect(self.accion_aceptar_plantilla)
        col_plant.addWidget(self.btn_aceptar_plantilla)
        layout.addWidget(self.card_plant)

        # Panel central: Actividades ya agregadas hoy (izq) + Texto para WhatsApp (der)
        fila_central = QHBoxLayout()

        card_lista_hoy = QFrame(self)
        card_lista_hoy.setProperty("card", True)
        col_hoy = QVBoxLayout(card_lista_hoy)
        col_hoy.addWidget(QLabel("<b>📌 Actividades en tu plan de hoy</b>"))
        self.lista_planeadas_hoy = QListWidget(self)
        col_hoy.addWidget(self.lista_planeadas_hoy, 1)

        card_wa = QFrame(self)
        card_wa.setProperty("card", True)
        col_wa = QVBoxLayout(card_wa)
        col_wa.addWidget(QLabel("<b>💬 Mensaje listo para enviar por WhatsApp (puedes editarlo)</b>"))
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

    def _reconstruir_chips_categorias(self, nombres_cat: list[str]) -> None:
        while self.layout_chips.count():
            item = self.layout_chips.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for nom in nombres_cat[:5]:
            if nom.strip().lower() == "flyers":
                continue
            btn = QPushButton(f"+ {nom}", self.contenedor_chips)
            btn.setProperty("rol", "secundario")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"Seleccionar o agregar rápido en la categoría «{nom}»")
            btn.clicked.connect(lambda _checked=False, n=nom: self._usar_chip_categoria(n))
            self.layout_chips.addWidget(btn)

    def _usar_chip_categoria(self, nombre_categoria: str) -> None:
        self.combo_categoria.setCurrentText(nombre_categoria)
        if not self.txt_nombre.text().strip():
            self.txt_nombre.setText(nombre_categoria)
        self.txt_nombre.setFocus()
        self.txt_nombre.selectAll()

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
            self.modelo_cat.setStringList(nombres_cat)

            self.combo_categoria.blockSignals(True)
            self.combo_categoria.clear()
            self.combo_categoria.addItem("Flyers")
            for nom in nombres_cat:
                if nom.strip().lower() != "flyers":
                    self.combo_categoria.addItem(nom)
            if texto_cat_actual:
                self.combo_categoria.setCurrentText(texto_cat_actual)
            else:
                self.combo_categoria.setCurrentIndex(0)
            self.combo_categoria.blockSignals(False)

            self._reconstruir_chips_categorias(nombres_cat)

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
            else:
                for idx, act in enumerate(visibles, start=1):
                    cat = f" [{act.categoria.nombre}]" if act.categoria else ""
                    est = f" · {act.tiempo_estimado_min} min" if act.tiempo_estimado_min else ""
                    self.lista_planeadas_hoy.addItem(f"{idx}. {act.nombre}{cat}{est}")

            texto = ServicioWhatsApp(s).generar_texto_plan(jornada)
            self.txt_plan_whatsapp.setPlainText(texto)

    def accion_agregar_flyer_rapido(self) -> None:
        """Agrega inmediatamente el siguiente Flyer (Flyer 1, Flyer 2...) bajo la categoría Flyers."""
        estimado = int(self.spin_estimado.value()) or None
        with self.bd.sesion() as s:
            jornada = RepoJornadas(s).obtener_o_crear()
            cat_flyers = RepoCategorias(s).obtener_o_crear("Flyers", "#003D95")
            cron = ServicioCronometro(s)
            nombre_flyer = cron.siguiente_nombre_flyer_del_dia(jornada.id)
            ServicioActividades(s).crear_planeada(
                nombre_flyer,
                categoria_id=cat_flyers.id,
                tiempo_estimado_min=estimado,
            )
        self.refrescar()
        if self.al_cambiar_plan:
            self.al_cambiar_plan()

    def accion_crear_categoria(self) -> None:
        nombre, ok = QInputDialog.getText(
            self,
            "Nueva categoría",
            "Escribe el nombre de la nueva categoría (ej. Flyers, Videos, Banners):",
        )
        if not ok or not nombre.strip():
            return
        limpio = nombre.strip()
        with self.bd.sesion() as s:
            RepoCategorias(s).obtener_o_crear(limpio)
        self.combo_categoria.setCurrentText(limpio)
        self.refrescar()
        if self.al_cambiar_plan:
            self.al_cambiar_plan()

    def accion_quitar_categoria(self) -> None:
        actual = self.combo_categoria.currentText().strip()
        if not actual:
            return
        if actual.lower() == "flyers":
            QMessageBox.information(
                self,
                "Categoría principal",
                "La categoría «Flyers» es fija del sistema porque tiene el flujo especial de múltiples flyers al día.",
            )
            return
        resp = QMessageBox.question(
            self,
            "Quitar categoría",
            f"¿Deseas quitar la categoría «{actual}» de la lista rápida?",
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        with self.bd.sesion() as s:
            repo = RepoCategorias(s)
            cat = repo.buscar_por_nombre(actual)
            if cat is not None:
                repo.desactivar(cat.id)
        self.combo_categoria.setCurrentText("Flyers")
        self.refrescar()

    def accion_agregar_planeada(self) -> None:
        nombre = self.txt_nombre.text().strip()
        cat_txt = self.combo_categoria.currentText().strip()

        if not nombre and cat_txt:
            if "flyer" in cat_txt.lower():
                with self.bd.sesion() as s:
                    jornada = RepoJornadas(s).obtener_o_crear()
                    nombre = ServicioCronometro(s).siguiente_nombre_flyer_del_dia(jornada.id)
            else:
                nombre = cat_txt

        if not nombre:
            QMessageBox.warning(self, "Nombre requerido", "Escribe el nombre de la actividad.")
            return

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
