"""Pantalla 7: Estadísticas — RF-11.

Visualiza:
- Gráfico vectorial de **Tendencia de productividad** (por día, semana o mes).
- Tabla de **Tiempo por categoría**.
- Tabla de **Tiempo estimado vs. real** por grupo.
- Tabla de **Tiempo por solicitante** (jefe, doctoras, compañeros, terceros).
- Tarjeta de **Revisiones y motivos** (`error_propio`, `cambio_criterio`, `informacion_nueva`).
"""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from data.db import BaseDatos
from services.estadisticas import PuntoTendencia, ServicioEstadisticas
from services.whatsapp import formatear_duracion_corta


class GraficoTendenciaWidget(QWidget):
    """Gráfico vectorial ligero en `QPainter` para la línea de tendencia de productividad."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.puntos: list[PuntoTendencia] = []
        self.setMinimumHeight(175)

    def establecer_puntos(self, puntos: list[PuntoTendencia]) -> None:
        self.puntos = puntos
        self.update()

    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        ancho = self.width()
        alto = self.height()
        margen_izq = 44
        margen_der = 20
        margen_sup = 20
        margen_inf = 30

        area_w = max(10, ancho - margen_izq - margen_der)
        area_h = max(10, alto - margen_sup - margen_inf)

        # Guías horizontales (0%, 60%, 85%, 100%)
        pen_guia = QPen(QColor("#CBD5E1"), 1, Qt.PenStyle.DashLine)
        for nivel in (0, 60, 85, 100):
            y = margen_sup + area_h * (1.0 - nivel / 100.0)
            p.setPen(pen_guia)
            p.drawLine(int(margen_izq), int(y), int(margen_izq + area_w), int(y))
            p.setPen(QColor("#64748B"))
            p.drawText(4, int(y + 4), f"{nivel}%")

        if not self.puntos:
            p.setPen(QColor("#64748B"))
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Sin jornadas laborales con porcentaje en el rango elegido",
            )
            p.end()
            return

        coords: list[QPointF] = []
        n = len(self.puntos)
        for i, pt in enumerate(self.puntos):
            x = margen_izq + (area_w * i / max(1, n - 1)) if n > 1 else margen_izq + area_w / 2
            val = max(0.0, min(100.0, pt.productividad_pct))
            y = margen_sup + area_h * (1.0 - val / 100.0)
            coords.append(QPointF(x, y))

        # Línea de tendencia
        pen_linea = QPen(QColor("#2563EB"), 2.5)
        p.setPen(pen_linea)
        for a, b in zip(coords, coords[1:]):
            p.drawLine(a, b)

        # Puntos y etiquetas
        for i, (coord, pt) in enumerate(zip(coords, self.puntos)):
            p.setBrush(QColor("#2563EB"))
            p.setPen(QColor("#FFFFFF"))
            p.drawEllipse(coord, 4.5, 4.5)
            p.setPen(QColor("#475569"))
            if n <= 10 or i in (0, n - 1, n // 2):
                p.drawText(int(coord.x() - 18), int(alto - 8), pt.etiqueta)

        p.end()


class PantallaEstadisticas(QWidget):
    """Pantalla de estadísticas e indicadores analíticos."""

    def __init__(self, bd: BaseDatos, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bd = bd

        layout_ext = QVBoxLayout(self)
        layout_ext.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }")
        cont_scroll = QWidget(scroll)
        layout = QVBoxLayout(cont_scroll)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Encabezado y selector de periodo en dos niveles claros para evitar recortes
        lbl_tit = QLabel("Estadísticas y Tendencias", cont_scroll)
        lbl_tit.setObjectName("tituloPantalla")
        layout.addWidget(lbl_tit)

        card_filtros = QFrame(cont_scroll)
        card_filtros.setProperty("card", True)
        fila_sup = QHBoxLayout(card_filtros)
        fila_sup.setContentsMargins(12, 8, 12, 8)
        fila_sup.setSpacing(8)

        hoy = date.today()
        hace_30 = hoy - timedelta(days=29)
        self.dt_desde = QDateEdit(QDate(hace_30.year, hace_30.month, hace_30.day), card_filtros)
        self.dt_desde.setCalendarPopup(True)
        self.dt_desde.setDisplayFormat("dd/MM/yyyy")

        self.dt_hasta = QDateEdit(QDate(hoy.year, hoy.month, hoy.day), card_filtros)
        self.dt_hasta.setCalendarPopup(True)
        self.dt_hasta.setDisplayFormat("dd/MM/yyyy")

        self.combo_escala = QComboBox(card_filtros)
        self.combo_escala.addItem("Por día", "dia")
        self.combo_escala.addItem("Por semana", "semana")
        self.combo_escala.addItem("Por mes", "mes")
        self.combo_escala.currentIndexChanged.connect(self.refrescar)

        self.btn_actualizar = QPushButton("Actualizar", card_filtros)
        self.btn_actualizar.setProperty("compact", True)
        self.btn_actualizar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_actualizar.clicked.connect(self.refrescar)

        fila_sup.addWidget(QLabel("Desde:", card_filtros))
        fila_sup.addWidget(self.dt_desde)
        fila_sup.addWidget(QLabel("Hasta:", card_filtros))
        fila_sup.addWidget(self.dt_hasta)
        fila_sup.addWidget(QLabel("Escala:", card_filtros))
        fila_sup.addWidget(self.combo_escala)
        fila_sup.addStretch()
        fila_sup.addWidget(self.btn_actualizar)
        layout.addWidget(card_filtros)

        # Tarjeta de gráfico de tendencia
        card_graf = QFrame(cont_scroll)
        card_graf.setProperty("card", True)
        col_graf = QVBoxLayout(card_graf)
        col_graf.addWidget(QLabel("<b>Productividad en el periodo (%)</b>", card_graf))
        self.grafico = GraficoTendenciaWidget(card_graf)
        col_graf.addWidget(self.grafico)
        layout.addWidget(card_graf)

        # Cuadrícula 2x2 amplia: Categorías, Solicitantes, Estimado vs Real y Revisiones
        grid_tablas = QGridLayout()
        grid_tablas.setSpacing(12)

        def _crear_card_tabla(titulo: str, cabeceras: list[str]) -> tuple[QFrame, QTableWidget]:
            card = QFrame(cont_scroll)
            card.setProperty("card", True)
            col = QVBoxLayout(card)
            col.setContentsMargins(12, 10, 12, 10)
            col.setSpacing(6)
            col.addWidget(QLabel(f"<b>{titulo}</b>", card))
            tbl = QTableWidget(0, len(cabeceras), card)
            tbl.setHorizontalHeaderLabels(cabeceras)
            tbl.setMinimumHeight(145)
            tbl.setAlternatingRowColors(True)
            tbl.setShowGrid(False)
            tbl.verticalHeader().setVisible(False)
            tbl.verticalHeader().setDefaultSectionSize(34)
            tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for idx in range(1, len(cabeceras)):
                tbl.horizontalHeader().setSectionResizeMode(idx, QHeaderView.ResizeMode.ResizeToContents)
            col.addWidget(tbl, 1)
            return card, tbl

        card_cat, self.tabla_cat = _crear_card_tabla(
            "Tiempo por categoría", ["Categoría", "Cant.", "Tiempo"]
        )
        card_sol, self.tabla_sol = _crear_card_tabla(
            "Tiempo por solicitante", ["Solicitante", "Cant.", "Tiempo"]
        )
        card_est, self.tabla_est = _crear_card_tabla(
            "Tiempo estimado vs. real", ["Grupo", "Est.", "Real"]
        )

        # Resumen de revisiones y motivos (sin alertas)
        card_rev = QFrame(cont_scroll)
        card_rev.setProperty("card", True)
        col_rev = QVBoxLayout(card_rev)
        col_rev.setContentsMargins(12, 10, 12, 10)
        col_rev.setSpacing(8)
        col_rev.addWidget(QLabel("<b>Revisiones y motivos en el periodo</b>", card_rev))
        self.lbl_revisiones = QLabel("", card_rev)
        self.lbl_revisiones.setWordWrap(True)
        self.lbl_revisiones.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        col_rev.addWidget(self.lbl_revisiones, 1)

        grid_tablas.addWidget(card_cat, 0, 0)
        grid_tablas.addWidget(card_sol, 0, 1)
        grid_tablas.addWidget(card_est, 1, 0)
        grid_tablas.addWidget(card_rev, 1, 1)
        grid_tablas.setColumnStretch(0, 1)
        grid_tablas.setColumnStretch(1, 1)
        layout.addLayout(grid_tablas, 1)

        scroll.setWidget(cont_scroll)
        layout_ext.addWidget(scroll)

        self.refrescar()

    def refrescar(self) -> None:
        desde = self.dt_desde.date().toPython()
        hasta = self.dt_hasta.date().toPython()
        escala = str(self.combo_escala.currentData())

        with self.bd.sesion() as s:
            rep = ServicioEstadisticas(s).calcular(desde, hasta)

        if escala == "semana":
            self.grafico.establecer_puntos(rep.tendencia_semanal)
        elif escala == "mes":
            self.grafico.establecer_puntos(rep.tendencia_mensual)
        else:
            self.grafico.establecer_puntos(rep.tendencia_diaria)

        self.tabla_cat.setRowCount(len(rep.por_categoria))
        for i, c in enumerate(rep.por_categoria):
            self.tabla_cat.setItem(i, 0, QTableWidgetItem(c.categoria_nombre))
            self.tabla_cat.setItem(i, 1, QTableWidgetItem(str(c.cantidad_actividades)))
            self.tabla_cat.setItem(i, 2, QTableWidgetItem(formatear_duracion_corta(c.segundos)))

        self.tabla_est.setRowCount(len(rep.estimado_vs_real))
        for i, er in enumerate(rep.estimado_vs_real):
            self.tabla_est.setItem(i, 0, QTableWidgetItem(er.grupo))
            self.tabla_est.setItem(i, 1, QTableWidgetItem(f"{er.estimado_promedio_min:.1f} min"))
            self.tabla_est.setItem(i, 2, QTableWidgetItem(f"{er.real_promedio_min:.1f} min"))

        self.tabla_sol.setRowCount(len(rep.por_solicitante))
        for i, sol in enumerate(rep.por_solicitante):
            self.tabla_sol.setItem(i, 0, QTableWidgetItem(sol.solicitante_nombre))
            self.tabla_sol.setItem(i, 1, QTableWidgetItem(str(sol.cantidad_solicitudes)))
            self.tabla_sol.setItem(i, 2, QTableWidgetItem(formatear_duracion_corta(sol.segundos)))

        rev = rep.revisiones
        motivos_txt = (
            ", ".join(f"{k}: {v}" for k, v in sorted(rev.por_motivo.items()))
            if rev.por_motivo
            else "ninguna en el periodo"
        )
        self.lbl_revisiones.setText(
            f"Revisiones en el periodo: {rev.total_revisiones} "
            f"(tiempo dedicado: {formatear_duracion_corta(rev.segundos_totales)})  ·  "
            f"Motivos: {motivos_txt}"
        )
