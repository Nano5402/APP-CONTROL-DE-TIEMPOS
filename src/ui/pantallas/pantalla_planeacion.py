"""Pantalla de Planeación Semanal colaborativa.

Tablero compartido donde todos los miembros del equipo pueden colocar y revisar
las tareas de la semana, organizadas por día y responsable, con opción de
trasladarlas directamente al plan de trabajo diario en Hoy · Cronómetro.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from data.db import BaseDatos
from data.enums import Prioridad
from data.models import ItemPlaneacion
from data.repositorios.catalogos import RepoCategorias
from data.repositorios.jornadas import RepoJornadas
from services.planeacion import ServicioPlaneacion, inicio_semana
from ui.iconos import configurar_boton


_DIAS_SEMANA_NOMBRES = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
]

_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]


def _formatear_rango_semana(lunes: date) -> str:
    domingo = lunes + timedelta(days=6)
    m_ini = _MESES_ES[lunes.month - 1]
    m_fin = _MESES_ES[domingo.month - 1]
    if lunes.month == domingo.month:
        return f"{lunes.day} al {domingo.day} de {m_fin} de {lunes.year}"
    return f"{lunes.day} {m_ini[:3]} – {domingo.day} {m_fin[:3]} {lunes.year}"


class DialogoItemPlaneacion(QDialog):
    """Diálogo modal para crear o editar una tarea en el tablero semanal."""

    def __init__(
        self,
        bd: BaseDatos,
        *,
        item: ItemPlaneacion | None = None,
        dia_sugerido: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bd = bd
        self.item = item
        self.setWindowTitle("Editar tarea de la semana" if item else "Nueva tarea para la semana")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        lbl_tit = QLabel(
            "Editar tarea semanal" if item else "Agregar tarea al tablero de la semana",
            self,
        )
        lbl_tit.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(lbl_tit)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setSpacing(8)

        self.txt_titulo = QLineEdit(item.titulo if item else "", self)
        self.txt_titulo.setPlaceholderText("¿Qué tarea hay que realizar en la semana?")

        self.combo_responsable = QComboBox(self)
        self.combo_responsable.setEditable(True)
        self.combo_responsable.lineEdit().setPlaceholderText("Nombre del responsable o equipo")

        with self.bd.sesion() as s:
            conocidos = ServicioPlaneacion(s).listar_responsables_conocidos()
            categorias = RepoCategorias(s).listar_activas()

        for c in conocidos:
            self.combo_responsable.addItem(c)
        if item and item.responsable:
            self.combo_responsable.setCurrentText(item.responsable)
        elif not item and self.combo_responsable.count() > 0:
            self.combo_responsable.setCurrentIndex(0)

        self.combo_dia = QComboBox(self)
        self.combo_dia.addItem("Sin día específico (Semana general)", -1)
        for idx, nom in enumerate(_DIAS_SEMANA_NOMBRES):
            self.combo_dia.addItem(nom, idx)

        dia_preseleccion = item.dia_semana if item else dia_sugerido
        if dia_preseleccion is not None and 0 <= dia_preseleccion < len(_DIAS_SEMANA_NOMBRES):
            self.combo_dia.setCurrentIndex(dia_preseleccion + 1)
        else:
            self.combo_dia.setCurrentIndex(0)

        self.combo_categoria = QComboBox(self)
        self.combo_categoria.addItem("Sin categoría", None)
        for cat in categorias:
            self.combo_categoria.addItem(cat.nombre, cat.id)
        if item and item.categoria_id:
            idx_c = self.combo_categoria.findData(item.categoria_id)
            if idx_c >= 0:
                self.combo_categoria.setCurrentIndex(idx_c)

        self.combo_prioridad = QComboBox(self)
        for p in (Prioridad.NORMAL, Prioridad.MAXIMA, Prioridad.MINIMA):
            self.combo_prioridad.addItem(p.etiqueta(), p.value)
        if item and item.prioridad:
            idx_p = self.combo_prioridad.findData(item.prioridad)
            if idx_p >= 0:
                self.combo_prioridad.setCurrentIndex(idx_p)

        self.spin_estimado = QSpinBox(self)
        self.spin_estimado.setRange(0, 960)
        self.spin_estimado.setValue(item.tiempo_estimado_min or 0 if item else 0)
        self.spin_estimado.setSuffix(" min")
        self.spin_estimado.setSpecialValueText("Sin estimado")

        self.txt_desc = QLineEdit(item.descripcion or "" if item else "", self)
        self.txt_desc.setPlaceholderText("Detalles, enlaces o requerimientos (opcional)")

        form.addRow("Tarea / Actividad*:", self.txt_titulo)
        form.addRow("Responsable:", self.combo_responsable)
        form.addRow("Día asignado:", self.combo_dia)
        form.addRow("Categoría:", self.combo_categoria)
        form.addRow("Prioridad:", self.combo_prioridad)
        form.addRow("Tiempo estimado:", self.spin_estimado)
        form.addRow("Notas adicionales:", self.txt_desc)
        layout.addLayout(form)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        botones.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Guardar tarea" if item else "Agregar al tablero"
        )
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._validar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _validar(self) -> None:
        if not self.txt_titulo.text().strip():
            QMessageBox.warning(self, "Título obligatorio", "Debes ingresar el nombre o título de la tarea.")
            return
        self.accept()

    @property
    def datos(self) -> dict:
        dia_data = self.combo_dia.currentData()
        dia_final = int(dia_data) if (dia_data is not None and int(dia_data) >= 0) else None
        cat_id = self.combo_categoria.currentData()
        est_min = int(self.spin_estimado.value())
        return {
            "titulo": self.txt_titulo.text().strip(),
            "responsable": self.combo_responsable.currentText().strip(),
            "dia_semana": dia_final,
            "categoria_id": int(cat_id) if cat_id is not None else None,
            "prioridad": str(self.combo_prioridad.currentData() or Prioridad.NORMAL.value),
            "tiempo_estimado_min": est_min if est_min > 0 else None,
            "descripcion": self.txt_desc.text().strip() or None,
        }


class TarjetaPlaneacion(QFrame):
    """Tarjeta individual de tarea en el tablero semanal adaptada al ancho disponible."""

    def __init__(
        self,
        item: ItemPlaneacion,
        *,
        al_alternar: Callable[[int], None],
        al_editar: Callable[[ItemPlaneacion], None],
        al_eliminar: Callable[[int], None],
        al_pasar_hoy: Callable[[int], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.item_id = item.id
        self.setProperty("card", True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet(
            "QFrame[card='true'] { background-color: #FFFFFF; border: 1px solid #E2E8F0; "
            "border-radius: 6px; padding: 2px; } QFrame[card='true']:hover { border-color: #CBD5E1; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Fila superior: Checkbox + Título
        fila_sup = QHBoxLayout()
        fila_sup.setSpacing(6)
        fila_sup.setContentsMargins(0, 0, 0, 0)
        self.chk = QCheckBox(self)
        self.chk.setChecked(item.completado)
        self.chk.toggled.connect(lambda _c: al_alternar(item.id))

        self.lbl_titulo = QLabel(item.titulo, self)
        self.lbl_titulo.setWordWrap(True)
        f = self.lbl_titulo.font()
        f.setWeight(QFont.Weight.DemiBold)
        f.setStrikeOut(item.completado)
        self.lbl_titulo.setFont(f)
        if item.completado:
            self.lbl_titulo.setStyleSheet("color: #94A3B8;")

        fila_sup.addWidget(self.chk)
        fila_sup.addWidget(self.lbl_titulo, 1)
        layout.addLayout(fila_sup)

        # Fila badges compacta
        fila_badges = QHBoxLayout()
        fila_badges.setSpacing(4)
        fila_badges.setContentsMargins(0, 0, 0, 0)

        if item.responsable:
            lbl_resp = QLabel(f"👤 {item.responsable}", self)
            lbl_resp.setStyleSheet(
                "background-color: #E0E7FF; color: #1E3A8A; font-size: 10px; "
                "font-weight: 600; padding: 1px 4px; border-radius: 3px;"
            )
            fila_badges.addWidget(lbl_resp)

        if item.categoria:
            lbl_cat = QLabel(item.categoria.nombre, self)
            lbl_cat.setStyleSheet(
                f"background-color: {item.categoria.color}20; color: {item.categoria.color}; "
                "font-size: 10px; font-weight: 600; padding: 1px 4px; border-radius: 3px;"
            )
            fila_badges.addWidget(lbl_cat)

        if item.prioridad == Prioridad.MAXIMA.value:
            lbl_prio = QLabel("🔥 Alta", self)
            lbl_prio.setStyleSheet(
                "background-color: #FEE2E2; color: #DC2626; font-size: 10px; "
                "font-weight: 600; padding: 1px 4px; border-radius: 3px;"
            )
            fila_badges.addWidget(lbl_prio)

        if item.tiempo_estimado_min:
            lbl_est = QLabel(f"⏱ {item.tiempo_estimado_min}m", self)
            lbl_est.setStyleSheet("color: #64748B; font-size: 10px;")
            fila_badges.addWidget(lbl_est)

        fila_badges.addStretch()
        layout.addLayout(fila_badges)

        if item.descripcion:
            lbl_desc = QLabel(item.descripcion, self)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color: #475569; font-size: 10px;")
            layout.addWidget(lbl_desc)

        # Fila inferior: Botón trasladar a Hoy + Editar + Eliminar
        fila_acciones = QHBoxLayout()
        fila_acciones.setSpacing(4)
        fila_acciones.setContentsMargins(0, 2, 0, 0)

        btn_hoy = QPushButton("  A mi plan", self)
        btn_hoy.setProperty("compact", True)
        btn_hoy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_hoy.setToolTip("Agregar esta tarea a mi plan de hoy en Hoy · Cronómetro")
        btn_hoy.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        configurar_boton(btn_hoy, "play", color="#003D95", tamano=11)
        btn_hoy.clicked.connect(lambda: al_pasar_hoy(item.id))

        btn_edit = QPushButton(self)
        btn_edit.setProperty("compact", True)
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.setToolTip("Editar datos de la tarea")
        configurar_boton(btn_edit, "edit", color="#0F172A", tamano=11)
        btn_edit.clicked.connect(lambda: al_editar(item))

        btn_del = QPushButton(self)
        btn_del.setProperty("compact", True)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setToolTip("Eliminar del tablero")
        configurar_boton(btn_del, "trash", color="#EF4444", tamano=11)
        btn_del.clicked.connect(lambda: al_eliminar(item.id))

        fila_acciones.addWidget(btn_hoy)
        fila_acciones.addStretch()
        fila_acciones.addWidget(btn_edit)
        fila_acciones.addWidget(btn_del)
        layout.addLayout(fila_acciones)


class PantallaPlaneacion(QWidget):
    """Pantalla con el tablero semanal colaborativo del equipo adaptado al tamaño de la app."""

    def __init__(
        self,
        bd: BaseDatos,
        *,
        al_pasar_a_plan: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bd = bd
        self.al_pasar_a_plan = al_pasar_a_plan
        self.fecha_lunes_actual = inicio_semana()

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }"
        )

        cont_scroll = QWidget(scroll)
        layout = QVBoxLayout(cont_scroll)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # 1. Cabecera compacta y proporcionada
        card_cabecera = QFrame(cont_scroll)
        card_cabecera.setProperty("card", True)
        capa_cabecera = QVBoxLayout(card_cabecera)
        capa_cabecera.setContentsMargins(14, 10, 14, 10)
        capa_cabecera.setSpacing(8)

        # Fila superior de título
        fila_tit = QHBoxLayout()
        col_tit = QVBoxLayout()
        col_tit.setSpacing(1)
        lbl_tit = QLabel("Tablero de Planeación Semanal", card_cabecera)
        lbl_tit.setObjectName("tituloPantalla")
        lbl_sub = QLabel(
            "Tablero compartido del equipo para organizar lo que tenemos que hacer en la semana.",
            card_cabecera,
        )
        lbl_sub.setObjectName("subtitulo")
        col_tit.addWidget(lbl_tit)
        col_tit.addWidget(lbl_sub)
        fila_tit.addLayout(col_tit, 1)

        self.btn_nueva_tarea = QPushButton("  + Agregar tarea a la semana", card_cabecera)
        self.btn_nueva_tarea.setProperty("rol", "exito")
        self.btn_nueva_tarea.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_nueva_tarea, "plus", color="#FFFFFF", tamano=13)
        self.btn_nueva_tarea.clicked.connect(lambda: self.accion_nueva_tarea())
        fila_tit.addWidget(self.btn_nueva_tarea)
        capa_cabecera.addLayout(fila_tit)

        # Fila intermedia de controles
        fila_controles = QHBoxLayout()
        fila_controles.setSpacing(6)

        self.btn_ant_sem = QPushButton("◀", card_cabecera)
        self.btn_ant_sem.setProperty("rol", "secundario")
        self.btn_ant_sem.setProperty("compact", True)
        self.btn_ant_sem.setToolTip("Semana anterior")
        self.btn_ant_sem.clicked.connect(self._semana_anterior)

        self.lbl_rango_semana = QLabel("", card_cabecera)
        self.lbl_rango_semana.setStyleSheet(
            "font-weight: 700; font-size: 12px; color: #003D95; padding: 0 4px;"
        )

        self.btn_sig_sem = QPushButton("▶", card_cabecera)
        self.btn_sig_sem.setProperty("rol", "secundario")
        self.btn_sig_sem.setProperty("compact", True)
        self.btn_sig_sem.setToolTip("Semana siguiente")
        self.btn_sig_sem.clicked.connect(self._semana_siguiente)

        self.btn_esta_sem = QPushButton("Hoy", card_cabecera)
        self.btn_esta_sem.setProperty("rol", "secundario")
        self.btn_esta_sem.setProperty("compact", True)
        self.btn_esta_sem.setToolTip("Ir a la semana actual")
        self.btn_esta_sem.clicked.connect(self._ir_esta_semana)

        fila_controles.addWidget(self.btn_ant_sem)
        fila_controles.addWidget(self.lbl_rango_semana)
        fila_controles.addWidget(self.btn_sig_sem)
        fila_controles.addWidget(self.btn_esta_sem)
        fila_controles.addSpacing(10)

        fila_controles.addWidget(QLabel("Responsable:"))
        self.combo_filtro_resp = QComboBox(card_cabecera)
        self.combo_filtro_resp.setMinimumWidth(130)
        self.combo_filtro_resp.currentIndexChanged.connect(lambda _i: self.refrescar())
        fila_controles.addWidget(self.combo_filtro_resp)

        fila_controles.addWidget(QLabel("Estado:"))
        self.combo_filtro_est = QComboBox(card_cabecera)
        self.combo_filtro_est.addItem("Todas", "todas")
        self.combo_filtro_est.addItem("Pendientes", "pendientes")
        self.combo_filtro_est.addItem("Completadas", "completadas")
        self.combo_filtro_est.currentIndexChanged.connect(lambda _i: self.refrescar())
        fila_controles.addWidget(self.combo_filtro_est)

        fila_controles.addStretch()

        self.lbl_resumen_tot = QLabel(card_cabecera)
        self.lbl_resumen_tot.setObjectName("chipMetricaPlan")
        self.lbl_resumen_pen = QLabel(card_cabecera)
        self.lbl_resumen_pen.setObjectName("chipMetricaPlan")
        self.lbl_resumen_com = QLabel(card_cabecera)
        self.lbl_resumen_com.setObjectName("chipMetricaPlan")

        fila_controles.addWidget(self.lbl_resumen_tot)
        fila_controles.addWidget(self.lbl_resumen_pen)
        fila_controles.addWidget(self.lbl_resumen_com)

        capa_cabecera.addLayout(fila_controles)
        layout.addWidget(card_cabecera)

        # 2. Contenedor de columnas del tablero que se expande al 100% del ancho
        self.cont_columnas = QWidget(cont_scroll)
        self.layout_columnas = QHBoxLayout(self.cont_columnas)
        self.layout_columnas.setContentsMargins(0, 0, 0, 0)
        self.layout_columnas.setSpacing(8)
        self.layout_columnas.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self.cont_columnas, 1)

        scroll.setWidget(cont_scroll)
        layout_raiz.addWidget(scroll)

        self._cargar_filtro_responsables()
        self.refrescar()

    def _semana_anterior(self) -> None:
        self.fecha_lunes_actual -= timedelta(days=7)
        self.refrescar()

    def _semana_siguiente(self) -> None:
        self.fecha_lunes_actual += timedelta(days=7)
        self.refrescar()

    def _ir_esta_semana(self) -> None:
        self.fecha_lunes_actual = inicio_semana()
        self.refrescar()

    def _cargar_filtro_responsables(self) -> None:
        sel_ant = self.combo_filtro_resp.currentData()
        self.combo_filtro_resp.blockSignals(True)
        self.combo_filtro_resp.clear()
        self.combo_filtro_resp.addItem("Todos", "")
        with self.bd.sesion() as s:
            conocidos = ServicioPlaneacion(s).listar_responsables_conocidos()
        for c in conocidos:
            self.combo_filtro_resp.addItem(f"👤 {c}", c)
        if sel_ant:
            idx = self.combo_filtro_resp.findData(sel_ant)
            if idx >= 0:
                self.combo_filtro_resp.setCurrentIndex(idx)
        self.combo_filtro_resp.blockSignals(False)

    def refrescar(self) -> None:
        """Carga y dibuja las columnas del tablero ajustadas al ancho."""
        self.lbl_rango_semana.setText(_formatear_rango_semana(self.fecha_lunes_actual))

        resp_filtro = self.combo_filtro_resp.currentData() or None
        est_filtro = self.combo_filtro_est.currentData() or "todas"
        solo_pendientes = (est_filtro == "pendientes")

        with self.bd.sesion() as s:
            srv = ServicioPlaneacion(s)
            items = srv.listar_items(
                self.fecha_lunes_actual,
                responsable=resp_filtro,
                solo_pendientes=solo_pendientes,
            )

        if est_filtro == "completadas":
            items = [it for it in items if it.completado]

        total_items = len(items)
        completados = sum(1 for it in items if it.completado)
        pendientes = total_items - completados
        self.lbl_resumen_tot.setText(f"📋 {total_items}")
        self.lbl_resumen_pen.setText(f"⏳ {pendientes}")
        self.lbl_resumen_com.setText(f"✅ {completados}")

        while self.layout_columnas.count():
            item_h = self.layout_columnas.takeAt(0)
            widget = item_h.widget()
            if widget:
                widget.deleteLater()

        items_por_dia: dict[int | None, list[ItemPlaneacion]] = {None: []}
        for d in range(6):
            items_por_dia[d] = []
        for it in items:
            d_key = it.dia_semana if (it.dia_semana is not None and 0 <= it.dia_semana <= 5) else None
            items_por_dia[d_key].append(it)

        columnas_def = [
            (0, "Lunes", self.fecha_lunes_actual),
            (1, "Martes", self.fecha_lunes_actual + timedelta(days=1)),
            (2, "Miércoles", self.fecha_lunes_actual + timedelta(days=2)),
            (3, "Jueves", self.fecha_lunes_actual + timedelta(days=3)),
            (4, "Viernes", self.fecha_lunes_actual + timedelta(days=4)),
            (None, "Sin día fijo", None),
        ]

        for dia_idx, titulo_col, fecha_col in columnas_def:
            col_widget = self._construir_columna(
                dia_idx, titulo_col, fecha_col, items_por_dia[dia_idx]
            )
            self.layout_columnas.addWidget(col_widget, 1)

    def _construir_columna(
        self,
        dia_idx: int | None,
        titulo: str,
        fecha_col: date | None,
        items: list[ItemPlaneacion],
    ) -> QWidget:
        col_frame = QFrame(self.cont_columnas)
        col_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        col_frame.setMinimumWidth(130)
        col_frame.setStyleSheet(
            "background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px;"
        )

        layout_col = QVBoxLayout(col_frame)
        layout_col.setContentsMargins(6, 6, 6, 6)
        layout_col.setSpacing(5)

        # Header de la columna
        fila_h = QHBoxLayout()
        fila_h.setSpacing(4)
        fila_h.setContentsMargins(2, 0, 2, 2)

        col_t = QVBoxLayout()
        col_t.setSpacing(0)
        sub_txt = f"{fecha_col.day} {_MESES_ES[fecha_col.month - 1][:3]}" if fecha_col else "Semana"
        lbl_nombre = QLabel(f"<b>{titulo}</b>", col_frame)
        lbl_nombre.setStyleSheet("font-size: 12px;")
        lbl_sub = QLabel(f"{sub_txt} ({len(items)})", col_frame)
        lbl_sub.setStyleSheet("color: #64748B; font-size: 10px;")
        col_t.addWidget(lbl_nombre)
        col_t.addWidget(lbl_sub)
        fila_h.addLayout(col_t, 1)

        btn_add = QPushButton(col_frame)
        btn_add.setProperty("compact", True)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setToolTip(f"Agregar tarea para {titulo}")
        configurar_boton(btn_add, "plus", color="#003D95", tamano=11)
        btn_add.clicked.connect(lambda _c=False, d=dia_idx: self.accion_nueva_tarea(d))
        fila_h.addWidget(btn_add)
        layout_col.addLayout(fila_h)

        # Lista de tarjetas
        if not items:
            lbl_vacio = QLabel("Sin tareas", col_frame)
            lbl_vacio.setStyleSheet(
                "color: #94A3B8; font-size: 11px; font-style: italic; padding: 12px 0;"
            )
            lbl_vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout_col.addWidget(lbl_vacio)
        else:
            for it in items:
                tarjeta = TarjetaPlaneacion(
                    it,
                    al_alternar=self.accion_alternar_completado,
                    al_editar=self.accion_editar_tarea,
                    al_eliminar=self.accion_eliminar_tarea,
                    al_pasar_hoy=self.accion_pasar_a_hoy,
                    parent=col_frame,
                )
                layout_col.addWidget(tarjeta)

        layout_col.addStretch()
        return col_frame

    def accion_nueva_tarea(self, dia_sugerido: int | None = None) -> None:
        dlg = DialogoItemPlaneacion(self.bd, dia_sugerido=dia_sugerido, parent=self)
        if dlg.exec() != DialogoItemPlaneacion.DialogCode.Accepted:
            return

        with self.bd.sesion() as s:
            srv = ServicioPlaneacion(s)
            d = dlg.datos
            srv.crear_item(
                d["titulo"],
                responsable=d["responsable"],
                fecha_semana=self.fecha_lunes_actual,
                dia_semana=d["dia_semana"],
                categoria_id=d["categoria_id"],
                prioridad=d["prioridad"],
                tiempo_estimado_min=d["tiempo_estimado_min"],
                descripcion=d["descripcion"],
            )
        self._cargar_filtro_responsables()
        self.refrescar()

    def accion_editar_tarea(self, item: ItemPlaneacion) -> None:
        dlg = DialogoItemPlaneacion(self.bd, item=item, parent=self)
        if dlg.exec() != DialogoItemPlaneacion.DialogCode.Accepted:
            return

        with self.bd.sesion() as s:
            srv = ServicioPlaneacion(s)
            d = dlg.datos
            srv.actualizar_item(
                item.id,
                titulo=d["titulo"],
                responsable=d["responsable"],
                dia_semana=d["dia_semana"],
                categoria_id=d["categoria_id"],
                prioridad=d["prioridad"],
                tiempo_estimado_min=d["tiempo_estimado_min"],
                descripcion=d["descripcion"],
            )
        self._cargar_filtro_responsables()
        self.refrescar()

    def accion_alternar_completado(self, item_id: int) -> None:
        with self.bd.sesion() as s:
            ServicioPlaneacion(s).alternar_completado(item_id)
        self.refrescar()

    def accion_eliminar_tarea(self, item_id: int) -> None:
        resp = QMessageBox.question(
            self,
            "Eliminar tarea",
            "¿Deseas quitar esta tarea del tablero semanal?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        with self.bd.sesion() as s:
            ServicioPlaneacion(s).eliminar_item(item_id)
        self.refrescar()

    def accion_pasar_a_hoy(self, item_id: int) -> None:
        with self.bd.sesion() as s:
            srv = ServicioPlaneacion(s)
            act = srv.pasar_a_plan_hoy(item_id)
            nom = act.nombre
        QMessageBox.information(
            self,
            "Tarea agregada a Hoy",
            f"«{nom}» fue agregada a tus actividades planeadas de hoy.\n"
            "Ya puedes iniciar su cronómetro en la pantalla Hoy.",
        )
        if self.al_pasar_a_plan:
            self.al_pasar_a_plan()
