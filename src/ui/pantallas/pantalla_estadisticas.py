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
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Encabezado y selector de periodo
        fila_sup = QHBoxLayout()
        lbl_tit = QLabel("Estadísticas y Tendencias", self)
        lbl_tit.setObjectName("tituloPantalla")

        hoy = date.today()
        hace_30 = hoy - timedelta(days=29)
        self.dt_desde = QDateEdit(QDate(hace_30.year, hace_30.month, hace_30.day), self)
        self.dt_desde.setCalendarPopup(True)
        self.dt_desde.setDisplayFormat("dd/MM/yyyy")

        self.dt_hasta = QDateEdit(QDate(hoy.year, hoy.month, hoy.day), self)
        self.dt_hasta.setCalendarPopup(True)
        self.dt_hasta.setDisplayFormat("dd/MM/yyyy")

        self.combo_escala = QComboBox(self)
        self.combo_escala.addItem("Tendencia por día", "dia")
        self.combo_escala.addItem("Tendencia por semana", "semana")
        self.combo_escala.addItem("Tendencia por mes", "mes")
        self.combo_escala.currentIndexChanged.connect(self.refrescar)

        self.btn_actualizar = QPushButton("Actualizar", self)
        self.btn_actualizar.clicked.connect(self.refrescar)

        fila_sup.addWidget(lbl_tit)
        fila_sup.addStretch()
        fila_sup.addWidget(QLabel("Desde:"))
        fila_sup.addWidget(self.dt_desde)
        fila_sup.addWidget(QLabel("Hasta:"))
        fila_sup.addWidget(self.dt_hasta)
        fila_sup.addWidget(self.combo_escala)
        fila_sup.addWidget(self.btn_actualizar)
        layout.addLayout(fila_sup)

        # Tarjeta de gráfico de tendencia
        card_graf = QFrame(self)
        card_graf.setProperty("card", True)
        col_graf = QVBoxLayout(card_graf)
        col_graf.addWidget(QLabel("<b>Productividad en el periodo (%)</b>"))
        self.grafico = GraficoTendenciaWidget(card_graf)
        col_graf.addWidget(self.grafico)
        layout.addWidget(card_graf)

        # Tablas inferiores: Categorías, Estimado vs Real, Solicitantes
        fila_tablas = QHBoxLayout()

        self.tabla_cat = QTableWidget(0, 3, self)
        self.tabla_cat.setHorizontalHeaderLabels(["Categoría", "Actividades", "Tiempo total"])
        self.tabla_cat.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self.tabla_est = QTableWidget(0, 3, self)
        self.tabla_est.setHorizontalHeaderLabels(["Grupo", "Estimado prom.", "Real prom."])
        self.tabla_est.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self.tabla_sol = QTableWidget(0, 3, self)
        self.tabla_sol.setHorizontalHeaderLabels(["Solicitante", "Solicitudes", "Tiempo"])
        self.tabla_sol.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        fila_tablas.addWidget(self.tabla_cat, 1)
        fila_tablas.addWidget(self.tabla_est, 1)
        fila_tablas.addWidget(self.tabla_sol, 1)
        layout.addLayout(fila_tablas, 1)

        # Resumen de revisiones y motivos (sin alertas)
        card_rev = QFrame(self)
        card_rev.setProperty("card", True)
        fila_rev = QHBoxLayout(card_rev)
        self.lbl_revisiones = QLabel("", self)
        fila_rev.addWidget(self.lbl_revisiones)
        layout.addWidget(card_rev)

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
            f"🔄 Revisiones en el periodo: {rev.total_revisiones} "
            f"(tiempo dedicado: {formatear_duracion_corta(rev.segundos_totales)})  ·  "
            f"Motivos: {motivos_txt}"
        )
