"""Pantalla 5: Historial — RF-07.

Permite:
- Consultar por **Hoy**, **Esta semana**, **Este mes** o **Rango de fechas**.
- Filtrar por **categoría**, **estado**, **solicitante** y **tipo** (`planeada` / `extra` / `no_planeada`).
- Ver el detalle completo de la actividad seleccionada (tramos de tiempo, pausas,
  revisiones vinculadas y bitácora de ediciones `ediciones_log`).
- Corregir un registro histórico exigiendo **motivo obligatorio** y marca visible de editado (`★`).
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from data.db import BaseDatos
from data.enums import EstadoActividad, TipoActividad
from data.models import Actividad
from data.repositorios.catalogos import RepoCategorias, RepoSolicitantes
from services.actividades import ServicioActividades
from services.cronometro import ServicioCronometro
from services.historial import (
    FiltrosHistorial,
    ServicioHistorial,
    rango_mes,
    rango_semana,
)
from services.whatsapp import formatear_duracion_corta
from ui.dialogos import DialogoCorregirActividad, aplicar_correccion_desde_dialogo
from ui.iconos import configurar_boton
from ui.mini_widget import formatear_reloj_hms


class PantallaHistorial(QWidget):
    """Pantalla de consulta, filtros, detalle y corrección de historial."""

    def __init__(self, bd: BaseDatos, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bd = bd

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        lbl_tit = QLabel("Historial de Jornadas y Actividades", self)
        lbl_tit.setObjectName("tituloPantalla")
        layout.addWidget(lbl_tit)

        # Barra de fechas y filtros
        card_filtros = QFrame(self)
        card_filtros.setProperty("card", True)
        col_filtros = QVBoxLayout(card_filtros)
        col_filtros.setSpacing(8)

        fila_fechas = QHBoxLayout()
        fila_fechas.setSpacing(8)
        hoy = QDate.currentDate()
        self.dt_desde = QDateEdit(hoy.addDays(-6), self)
        self.dt_desde.setCalendarPopup(True)
        self.dt_desde.setDisplayFormat("dd/MM/yyyy")

        self.dt_hasta = QDateEdit(hoy, self)
        self.dt_hasta.setCalendarPopup(True)
        self.dt_hasta.setDisplayFormat("dd/MM/yyyy")

        btn_hoy = QPushButton("Hoy", self)
        btn_hoy.setProperty("rol", "secundario")
        btn_hoy.setProperty("compact", True)
        btn_hoy.clicked.connect(self._rango_hoy)

        self.btn_ayer = QPushButton("Ayer", self)
        self.btn_ayer.setProperty("rol", "secundario")
        self.btn_ayer.setProperty("compact", True)
        self.btn_ayer.clicked.connect(self._rango_ayer)

        btn_sem = QPushButton("Esta semana", self)
        btn_sem.setProperty("rol", "secundario")
        btn_sem.setProperty("compact", True)
        btn_sem.clicked.connect(self._rango_semana_actual)

        btn_mes = QPushButton("Este mes", self)
        btn_mes.setProperty("rol", "secundario")
        btn_mes.setProperty("compact", True)
        btn_mes.clicked.connect(self._rango_mes_actual)

        self.btn_filtrar = QPushButton("  Consultar", self)
        self.btn_filtrar.setProperty("compact", True)
        self.btn_filtrar.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_filtrar, "clipboard", color="#FFFFFF")
        self.btn_filtrar.clicked.connect(self.aplicar_filtros)

        fila_fechas.addWidget(QLabel("Desde:"))
        fila_fechas.addWidget(self.dt_desde)
        fila_fechas.addWidget(QLabel("Hasta:"))
        fila_fechas.addWidget(self.dt_hasta)
        fila_fechas.addWidget(btn_hoy)
        fila_fechas.addWidget(self.btn_ayer)
        fila_fechas.addWidget(btn_sem)
        fila_fechas.addWidget(btn_mes)
        fila_fechas.addStretch()
        fila_fechas.addWidget(self.btn_filtrar)
        col_filtros.addLayout(fila_fechas)

        grid_combos = QGridLayout()
        grid_combos.setHorizontalSpacing(10)
        grid_combos.setVerticalSpacing(6)
        self.combo_categoria = QComboBox(self)
        self.combo_estado = QComboBox(self)
        self.combo_solicitante = QComboBox(self)
        self.combo_tipo = QComboBox(self)

        for cb in (
            self.combo_categoria,
            self.combo_estado,
            self.combo_solicitante,
            self.combo_tipo,
        ):
            cb.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )

        grid_combos.addWidget(QLabel("Categoría:"), 0, 0)
        grid_combos.addWidget(self.combo_categoria, 0, 1)
        grid_combos.addWidget(QLabel("Estado:"), 0, 2)
        grid_combos.addWidget(self.combo_estado, 0, 3)
        grid_combos.addWidget(QLabel("Solicitante:"), 0, 4)
        grid_combos.addWidget(self.combo_solicitante, 0, 5)
        grid_combos.addWidget(QLabel("Tipo:"), 0, 6)
        grid_combos.addWidget(self.combo_tipo, 0, 7)
        for col_s in (1, 3, 5, 7):
            grid_combos.setColumnStretch(col_s, 1)
        col_filtros.addLayout(grid_combos)
        layout.addWidget(card_filtros)

        # Panel dividido verticalmente: tabla ancha arriba + detalle y ediciones abajo
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.setChildrenCollapsible(False)

        self.tabla = QTableWidget(0, 7, self)
        self.tabla.setHorizontalHeaderLabels(
            [
                "Fecha",
                "Actividad",
                "Categoría",
                "Tipo",
                "Estado",
                "Tiempo",
                "Notas",
            ]
        )
        self.tabla.setMinimumHeight(195)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setShowGrid(False)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(38)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.tabla.setColumnWidth(3, 115)
        self.tabla.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        self.tabla.setColumnWidth(6, 110)
        for col_idx in (0, 2, 4, 5):
            self.tabla.horizontalHeader().setSectionResizeMode(
                col_idx, QHeaderView.ResizeMode.ResizeToContents
            )
        self.tabla.itemSelectionChanged.connect(self._mostrar_detalle_seleccionada)

        card_det = QFrame(self)
        card_det.setProperty("card", True)
        card_det.setMinimumHeight(150)
        col_det = QVBoxLayout(card_det)
        col_det.setContentsMargins(14, 12, 14, 12)
        col_det.setSpacing(8)

        fila_det_head = QHBoxLayout()
        fila_det_head.addWidget(QLabel("<b>Detalle de la actividad y trazabilidad</b>"))
        fila_det_head.addStretch()

        self.btn_corregir = QPushButton("  Corregir actividad", self)
        self.btn_corregir.setProperty("compact", True)
        self.btn_corregir.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_corregir, "edit", color="#0F172A")
        self.btn_corregir.clicked.connect(self.accion_corregir_seleccionada)
        fila_det_head.addWidget(self.btn_corregir)

        self.btn_eliminar = QPushButton("  Eliminar registro", self)
        self.btn_eliminar.setProperty("rol", "peligro")
        self.btn_eliminar.setProperty("compact", True)
        self.btn_eliminar.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_eliminar, "trash", color="#FFFFFF")
        self.btn_eliminar.clicked.connect(self.accion_eliminar_seleccionada)
        fila_det_head.addWidget(self.btn_eliminar)
        col_det.addLayout(fila_det_head)

        self.txt_detalle = QPlainTextEdit(self)
        self.txt_detalle.setReadOnly(True)
        col_det.addWidget(self.txt_detalle, 1)

        splitter.addWidget(self.tabla)
        splitter.addWidget(card_det)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self._cargar_combos()
        self.aplicar_filtros()

    def _rango_hoy(self) -> None:
        h = QDate.currentDate()
        self.dt_desde.setDate(h)
        self.dt_hasta.setDate(h)
        self.aplicar_filtros()

    def _rango_ayer(self) -> None:
        ayer = QDate.currentDate().addDays(-1)
        self.dt_desde.setDate(ayer)
        self.dt_hasta.setDate(ayer)
        self.aplicar_filtros()

    def _rango_semana_actual(self) -> None:
        ini, fin = rango_semana(date.today())
        self.dt_desde.setDate(QDate(ini.year, ini.month, ini.day))
        self.dt_hasta.setDate(QDate(fin.year, fin.month, fin.day))
        self.aplicar_filtros()

    def _rango_mes_actual(self) -> None:
        ini, fin = rango_mes(date.today())
        self.dt_desde.setDate(QDate(ini.year, ini.month, ini.day))
        self.dt_hasta.setDate(QDate(fin.year, fin.month, fin.day))
        self.aplicar_filtros()

    def _cargar_combos(self) -> None:
        with self.bd.sesion() as s:
            categorias = RepoCategorias(s).listar_activas()
            solicitantes = RepoSolicitantes(s).listar_activos()

            self.combo_categoria.clear()
            self.combo_categoria.addItem("Todas", None)
            for c in categorias:
                self.combo_categoria.addItem(c.nombre, c.id)

            self.combo_estado.clear()
            self.combo_estado.addItem("Todos", None)
            for e in EstadoActividad:
                if e != EstadoActividad.ELIMINADA:
                    self.combo_estado.addItem(e.etiqueta(), e.value)

            self.combo_solicitante.clear()
            self.combo_solicitante.addItem("Todos", None)
            for sol in solicitantes:
                self.combo_solicitante.addItem(sol.nombre, sol.id)

            self.combo_tipo.clear()
            self.combo_tipo.addItem("Todos", None)
            for t in TipoActividad:
                self.combo_tipo.addItem(t.etiqueta(), t.value)

    def refrescar(self) -> None:
        self._cargar_combos()
        self.aplicar_filtros()

    def aplicar_filtros(self) -> None:
        desde = self.dt_desde.date().toPython()
        hasta = self.dt_hasta.date().toPython()
        filtros = FiltrosHistorial(
            fecha_desde=desde,
            fecha_hasta=hasta,
            categoria_id=self.combo_categoria.currentData(),
            estado=self.combo_estado.currentData(),
            solicitante_id=self.combo_solicitante.currentData(),
            tipo=self.combo_tipo.currentData(),
        )

        with self.bd.sesion() as s:
            srv_hist = ServicioHistorial(s)
            srv_act = ServicioActividades(s)
            actividades = srv_hist.buscar_actividades(filtros)

            self.tabla.setRowCount(len(actividades))
            for i, act in enumerate(actividades):
                desglose = srv_act.desglose_tiempos(act)
                fecha_txt = act.jornada.fecha.strftime("%d/%m/%Y") if act.jornada else "—"
                nom_txt = act.nombre + (" ★ Editado" if act.editado else "")

                it_fecha = QTableWidgetItem(fecha_txt)
                it_fecha.setData(Qt.ItemDataRole.UserRole, act.id)

                cat_txt = act.categoria.nombre if act.categoria else "Sin categoría"
                sol_txt = f" ({act.solicitante.nombre})" if act.solicitante else ""
                rev_txt = f"Rev: {desglose.cantidad_revisiones}"
                if act.editado:
                    rev_txt += " · ★ Editado"

                it_tipo = QTableWidgetItem(f"{act.tipo}{sol_txt}")
                it_tipo.setToolTip(it_tipo.text())
                it_notas = QTableWidgetItem(rev_txt)
                if rev_txt:
                    it_notas.setToolTip(rev_txt)

                self.tabla.setItem(i, 0, it_fecha)
                self.tabla.setItem(i, 1, QTableWidgetItem(nom_txt))
                self.tabla.setItem(i, 2, QTableWidgetItem(cat_txt))
                self.tabla.setItem(i, 3, it_tipo)
                self.tabla.setItem(i, 4, QTableWidgetItem(act.estado))
                self.tabla.setItem(i, 5, QTableWidgetItem(formatear_reloj_hms(desglose.segundos_total)))
                self.tabla.setItem(i, 6, it_notas)

        if self.tabla.rowCount() > 0:
            self.tabla.selectRow(0)
        else:
            self.txt_detalle.setPlainText("No hay actividades que coincidan con el filtro.")

    def _actividad_seleccionada_id(self) -> int | None:
        fila = self.tabla.currentRow()
        if fila < 0:
            return None
        it = self.tabla.item(fila, 0)
        return int(it.data(Qt.ItemDataRole.UserRole)) if it else None

    def _mostrar_detalle_seleccionada(self) -> None:
        act_id = self._actividad_seleccionada_id()
        if act_id is None:
            return
        with self.bd.sesion() as s:
            det = ServicioHistorial(s).detalle_actividad(act_id)
            if det is None:
                return
            act = det.actividad
            lineas = [
                f"Actividad: {act.nombre}",
                f"Fecha jornada: {act.jornada.fecha:%d/%m/%Y}",
                f"Tipo: {act.tipo} | Prioridad: {act.prioridad} | Estado: {act.estado}",
                f"Tiempo original: {formatear_duracion_corta(det.desglose.segundos_original)}",
                f"Tiempo revisiones ({det.desglose.cantidad_revisiones}): "
                f"{formatear_duracion_corta(det.desglose.segundos_revisiones)}",
                f"Tiempo total: {formatear_duracion_corta(det.desglose.segundos_total)}",
            ]
            if act.descripcion:
                lineas.append(f"Descripción: {act.descripcion}")
            if act.editado:
                lineas.append(f"★ EDITADO — Último motivo: {act.editado_motivo}")

            if det.sesiones:
                lineas.append("\n--- Tramos de cronómetro ---")
                for idx, ses in enumerate(det.sesiones, start=1):
                    fin_s = ses.fin.strftime("%H:%M:%S") if ses.fin else "en curso"
                    fh = " [Fuera de horario]" if ses.fuera_horario else ""
                    lineas.append(
                        f"  {idx}. {ses.inicio:%H:%M:%S} – {fin_s} "
                        f"({formatear_duracion_corta(ses.duracion_seg)}){fh}"
                    )

            if det.ediciones:
                lineas.append("\n--- Trazabilidad de correcciones ---")
                for ed in det.ediciones:
                    lineas.append(
                        f"  • {ed.momento:%d/%m %H:%M} [{ed.campo}]: "
                        f"'{ed.valor_anterior}' → '{ed.valor_nuevo}' (Motivo: {ed.motivo})"
                    )

            self.txt_detalle.setPlainText("\n".join(lineas))

    def accion_corregir_seleccionada(self) -> None:
        act_id = self._actividad_seleccionada_id()
        if act_id is None:
            return
        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is None:
                return
            dlg = DialogoCorregirActividad(act, self)
            if dlg.exec() != DialogoCorregirActividad.DialogCode.Accepted:
                return
            aplicar_correccion_desde_dialogo(s, act, dlg)
        self.aplicar_filtros()

    def accion_eliminar_seleccionada(self) -> None:
        act_id = self._actividad_seleccionada_id()
        if act_id is None:
            return
        resp = QMessageBox.question(
            self,
            "Eliminar registro",
            "¿Confirmas que deseas eliminar esta actividad del historial? "
            "Se recalculará la jornada correspondiente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is None:
                return
            if act.estado == EstadoActividad.EN_CURSO.value:
                ServicioCronometro(s).detener(act, motivo="Eliminada desde Historial")
            ServicioActividades(s).cambiar_estado_manual(
                act, EstadoActividad.ELIMINADA, motivo="Eliminado desde Historial"
            )
        self.aplicar_filtros()
