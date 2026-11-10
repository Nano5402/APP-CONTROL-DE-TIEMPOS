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
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
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
from services.historial import (
    FiltrosHistorial,
    ServicioHistorial,
    rango_mes,
    rango_semana,
)
from services.whatsapp import formatear_duracion_corta
from ui.dialogos import DialogoCorregirActividad
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

        fila_fechas = QHBoxLayout()
        hoy = QDate.currentDate()
        self.dt_desde = QDateEdit(hoy.addDays(-6), self)
        self.dt_desde.setCalendarPopup(True)
        self.dt_desde.setDisplayFormat("dd/MM/yyyy")

        self.dt_hasta = QDateEdit(hoy, self)
        self.dt_hasta.setCalendarPopup(True)
        self.dt_hasta.setDisplayFormat("dd/MM/yyyy")

        btn_hoy = QPushButton("Hoy", self)
        btn_hoy.setProperty("rol", "secundario")
        btn_hoy.clicked.connect(self._rango_hoy)

        btn_sem = QPushButton("Esta semana", self)
        btn_sem.setProperty("rol", "secundario")
        btn_sem.clicked.connect(self._rango_semana_actual)

        btn_mes = QPushButton("Este mes", self)
        btn_mes.setProperty("rol", "secundario")
        btn_mes.clicked.connect(self._rango_mes_actual)

        fila_fechas.addWidget(QLabel("Desde:"))
        fila_fechas.addWidget(self.dt_desde)
        fila_fechas.addWidget(QLabel("Hasta:"))
        fila_fechas.addWidget(self.dt_hasta)
        fila_fechas.addWidget(btn_hoy)
        fila_fechas.addWidget(btn_sem)
        fila_fechas.addWidget(btn_mes)
        fila_fechas.addStretch()
        col_filtros.addLayout(fila_fechas)

        fila_combos = QHBoxLayout()
        self.combo_categoria = QComboBox(self)
        self.combo_estado = QComboBox(self)
        self.combo_solicitante = QComboBox(self)
        self.combo_tipo = QComboBox(self)

        self.btn_filtrar = QPushButton("  Consultar historial", self)
        self.btn_filtrar.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_filtrar, "clipboard", color="#FFFFFF")
        self.btn_filtrar.clicked.connect(self.aplicar_filtros)

        fila_combos.addWidget(QLabel("Categoría:"))
        fila_combos.addWidget(self.combo_categoria)
        fila_combos.addWidget(QLabel("Estado:"))
        fila_combos.addWidget(self.combo_estado)
        fila_combos.addWidget(QLabel("Solicitante:"))
        fila_combos.addWidget(self.combo_solicitante)
        fila_combos.addWidget(QLabel("Tipo:"))
        fila_combos.addWidget(self.combo_tipo)
        fila_combos.addStretch()
        fila_combos.addWidget(self.btn_filtrar)
        col_filtros.addLayout(fila_combos)
        layout.addWidget(card_filtros)

        # Panel dividido: tabla de actividades + panel de detalle y ediciones
        fila_cuerpo = QHBoxLayout()

        self.tabla = QTableWidget(0, 7, self)
        self.tabla.setHorizontalHeaderLabels(
            [
                "Fecha",
                "Actividad",
                "Categoría",
                "Tipo / Solicitante",
                "Estado",
                "Tiempo total",
                "Revisiones / Editado",
            ]
        )
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.itemSelectionChanged.connect(self._mostrar_detalle_seleccionada)

        card_det = QFrame(self)
        card_det.setProperty("card", True)
        col_det = QVBoxLayout(card_det)
        col_det.addWidget(QLabel("<b>Detalle de la actividad y trazabilidad</b>"))
        self.txt_detalle = QPlainTextEdit(self)
        self.txt_detalle.setReadOnly(True)
        col_det.addWidget(self.txt_detalle, 1)

        self.btn_corregir = QPushButton("  Corregir registro seleccionado (con motivo)", self)
        self.btn_corregir.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_corregir, "edit", color="#0F172A")
        self.btn_corregir.clicked.connect(self.accion_corregir_seleccionada)
        col_det.addWidget(self.btn_corregir)

        fila_cuerpo.addWidget(self.tabla, 2)
        fila_cuerpo.addWidget(card_det, 1)
        layout.addLayout(fila_cuerpo, 1)

        self._cargar_combos()
        self.aplicar_filtros()

    def _rango_hoy(self) -> None:
        h = QDate.currentDate()
        self.dt_desde.setDate(h)
        self.dt_hasta.setDate(h)
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

                self.tabla.setItem(i, 0, it_fecha)
                self.tabla.setItem(i, 1, QTableWidgetItem(nom_txt))
                self.tabla.setItem(i, 2, QTableWidgetItem(cat_txt))
                self.tabla.setItem(i, 3, QTableWidgetItem(f"{act.tipo}{sol_txt}"))
                self.tabla.setItem(i, 4, QTableWidgetItem(act.estado))
                self.tabla.setItem(i, 5, QTableWidgetItem(formatear_reloj_hms(desglose.segundos_total)))
                self.tabla.setItem(i, 6, QTableWidgetItem(rev_txt))

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

            if det.pausas:
                lineas.append("\n--- Pausas registradas ---")
                for p in det.pausas:
                    fin_p = p.fin.strftime("%H:%M") if p.fin else "abierta"
                    mot = f" — {p.motivo}" if p.motivo else ""
                    lineas.append(f"  • [{p.tipo}] {p.inicio:%H:%M}–{fin_p}{mot}")

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
            srv_act = ServicioActividades(s)
            srv_act.corregir_actividad(
                act,
                motivo=dlg.motivo,
                nombre=dlg.nuevo_nombre,
                tiempo_estimado_min=dlg.nuevo_estimado,
                descripcion=dlg.nueva_descripcion,
            )
            if act.sesiones and dlg.nuevo_inicio and dlg.nuevo_fin:
                srv_act.corregir_sesion_tiempo(
                    act.sesiones[-1],
                    motivo=dlg.motivo,
                    nuevo_inicio=dlg.nuevo_inicio,
                    nuevo_fin=dlg.nuevo_fin,
                )
        self.aplicar_filtros()
