"""Pantalla 6: Reportes en PDF — RF-08.

Permite generar en 1 clic:
- **PDF general de un día** (o PDF de día no laboral si ese día no tiene horario).
- **PDF específico** filtrado por categoría, solicitante, tipo o rango de fechas.
- **PDF semanal** o **PDF mensual** con evolución de tendencia.
- Botón directo para **Abrir el PDF** y **"📂 Abrir carpeta de reportes"** para
  adjuntarlo en WhatsApp.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import rutas
from data.db import BaseDatos
from data.enums import TipoActividad
from data.repositorios.catalogos import RepoCategorias, RepoSolicitantes
from data.repositorios.jornadas import RepoJornadas
from reports.generador_pdf import abrir_archivo_pdf, abrir_carpeta_contenedora
from services.historial import FiltrosHistorial, rango_mes, rango_semana
from services.reportes_pdf import ServicioReportesPDF


class PantallaReportes(QWidget):
    """Pantalla para generar y abrir todos los reportes en PDF."""

    def __init__(self, bd: BaseDatos, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bd = bd
        self._ultimo_pdf: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        lbl_tit = QLabel("Exportación de Reportes en PDF", self)
        lbl_tit.setObjectName("tituloPantalla")
        layout.addWidget(lbl_tit)

        hoy = QDate.currentDate()

        # 1. PDF del día (laboral o no laboral)
        card_dia = QFrame(self)
        card_dia.setProperty("card", True)
        fila_dia = QHBoxLayout(card_dia)
        fila_dia.addWidget(QLabel("<b>1. Reporte general del día (o día no laboral):</b>"))
        self.dt_dia = QDateEdit(hoy, self)
        self.dt_dia.setCalendarPopup(True)
        self.dt_dia.setDisplayFormat("dd/MM/yyyy")
        self.btn_pdf_dia = QPushButton("📄 Generar PDF del día", self)
        self.btn_pdf_dia.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pdf_dia.clicked.connect(self.accion_pdf_dia)
        fila_dia.addWidget(self.dt_dia)
        fila_dia.addStretch()
        fila_dia.addWidget(self.btn_pdf_dia)
        layout.addWidget(card_dia)

        # 2. PDF semanal y mensual con tendencia
        card_per = QFrame(self)
        card_per.setProperty("card", True)
        fila_per = QHBoxLayout(card_per)
        fila_per.addWidget(QLabel("<b>2. Reportes ejecutivos con tendencia:</b>"))
        self.btn_pdf_semana = QPushButton("📊 Generar PDF de esta semana", self)
        self.btn_pdf_mes = QPushButton("📆 Generar PDF de este mes", self)
        self.btn_pdf_semana.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pdf_mes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pdf_semana.clicked.connect(self.accion_pdf_semana)
        self.btn_pdf_mes.clicked.connect(self.accion_pdf_mes)
        fila_per.addStretch()
        fila_per.addWidget(self.btn_pdf_semana)
        fila_per.addWidget(self.btn_pdf_mes)
        layout.addWidget(card_per)

        # 3. PDF específico con filtros
        card_esp = QFrame(self)
        card_esp.setProperty("card", True)
        form_esp = QFormLayout(card_esp)
        form_esp.addRow(
            QLabel("<b>3. Reporte específico (por categoría, solicitante o rango de fechas)</b>")
        )

        fila_rango = QHBoxLayout()
        self.dt_esp_desde = QDateEdit(hoy.addDays(-6), self)
        self.dt_esp_desde.setCalendarPopup(True)
        self.dt_esp_desde.setDisplayFormat("dd/MM/yyyy")
        self.dt_esp_hasta = QDateEdit(hoy, self)
        self.dt_esp_hasta.setCalendarPopup(True)
        self.dt_esp_hasta.setDisplayFormat("dd/MM/yyyy")
        fila_rango.addWidget(QLabel("Desde:"))
        fila_rango.addWidget(self.dt_esp_desde)
        fila_rango.addWidget(QLabel("Hasta:"))
        fila_rango.addWidget(self.dt_esp_hasta)
        fila_rango.addStretch()

        self.combo_categoria = QComboBox(self)
        self.combo_solicitante = QComboBox(self)
        self.combo_tipo = QComboBox(self)

        self.btn_pdf_especifico = QPushButton("🎯 Generar PDF específico", self)
        self.btn_pdf_especifico.setProperty("rol", "exito")
        self.btn_pdf_especifico.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pdf_especifico.clicked.connect(self.accion_pdf_especifico)

        form_esp.addRow("Rango de fechas:", fila_rango)
        form_esp.addRow("Categoría:", self.combo_categoria)
        form_esp.addRow("Solicitante:", self.combo_solicitante)
        form_esp.addRow("Tipo de actividad:", self.combo_tipo)
        form_esp.addRow("", self.btn_pdf_especifico)
        layout.addWidget(card_esp)

        # Barra inferior de acceso rápido al archivo / carpeta
        card_acc = QFrame(self)
        card_acc.setProperty("card", True)
        fila_acc = QHBoxLayout(card_acc)
        self.lbl_ultimo_pdf = QLabel(f"Carpeta de reportes: {rutas.carpeta_reportes()}", self)
        self.lbl_ultimo_pdf.setObjectName("subtitulo")
        self.btn_abrir_carpeta = QPushButton("📂 Abrir carpeta del PDF", self)
        self.btn_abrir_carpeta.setProperty("rol", "secundario")
        self.btn_abrir_carpeta.clicked.connect(self.accion_abrir_carpeta)
        fila_acc.addWidget(self.lbl_ultimo_pdf, 1)
        fila_acc.addWidget(self.btn_abrir_carpeta)
        layout.addWidget(card_acc)

        layout.addStretch()
        self.refrescar()

    def refrescar(self) -> None:
        with self.bd.sesion() as s:
            categorias = RepoCategorias(s).listar_activas()
            solicitantes = RepoSolicitantes(s).listar_activos()

            self.combo_categoria.clear()
            self.combo_categoria.addItem("Todas las categorías", None)
            for c in categorias:
                self.combo_categoria.addItem(c.nombre, c.id)

            self.combo_solicitante.clear()
            self.combo_solicitante.addItem("Todos los solicitantes", None)
            for sol in solicitantes:
                self.combo_solicitante.addItem(sol.nombre, sol.id)

            self.combo_tipo.clear()
            self.combo_tipo.addItem("Todos los tipos", None)
            for t in TipoActividad:
                self.combo_tipo.addItem(t.etiqueta(), t.value)

    def _notificar_pdf(self, ruta: Path) -> None:
        self._ultimo_pdf = ruta
        self.lbl_ultimo_pdf.setText(f"Último PDF generado: {ruta}")
        abrir_archivo_pdf(ruta)
        QMessageBox.information(self, "PDF generado", f"Reporte guardado en:\n{ruta}")

    def accion_pdf_dia(self) -> None:
        try:
            fecha = self.dt_dia.date().toPython()
            with self.bd.sesion() as s:
                jornada = RepoJornadas(s).obtener_o_crear(fecha)
                ruta = ServicioReportesPDF(s).generar_pdf_jornada(jornada)
            self._notificar_pdf(ruta)
        except Exception as exc:
            QMessageBox.critical(self, "Error al generar PDF", f"No se pudo crear el PDF:\n{exc}")

    def accion_pdf_semana(self) -> None:
        try:
            ini, fin = rango_semana(self.dt_dia.date().toPython())
            with self.bd.sesion() as s:
                ruta = ServicioReportesPDF(s).generar_pdf_periodo(
                    ini, fin, etiqueta_periodo="Semanal"
                )
            self._notificar_pdf(ruta)
        except Exception as exc:
            QMessageBox.critical(self, "Error al generar PDF", f"No se pudo crear el PDF:\n{exc}")

    def accion_pdf_mes(self) -> None:
        try:
            ini, fin = rango_mes(self.dt_dia.date().toPython())
            with self.bd.sesion() as s:
                ruta = ServicioReportesPDF(s).generar_pdf_periodo(
                    ini, fin, etiqueta_periodo="Mensual"
                )
            self._notificar_pdf(ruta)
        except Exception as exc:
            QMessageBox.critical(self, "Error al generar PDF", f"No se pudo crear el PDF:\n{exc}")

    def accion_pdf_especifico(self) -> None:
        try:
            filtros = FiltrosHistorial(
                fecha_desde=self.dt_esp_desde.date().toPython(),
                fecha_hasta=self.dt_esp_hasta.date().toPython(),
                categoria_id=self.combo_categoria.currentData(),
                solicitante_id=self.combo_solicitante.currentData(),
                tipo=self.combo_tipo.currentData(),
            )
            partes = ["Reporte específico"]
            if self.combo_categoria.currentData() is not None:
                partes.append(f"Categoría: {self.combo_categoria.currentText()}")
            if self.combo_solicitante.currentData() is not None:
                partes.append(f"Solicitante: {self.combo_solicitante.currentText()}")
            titulo = " — ".join(partes)

            with self.bd.sesion() as s:
                ruta = ServicioReportesPDF(s).generar_pdf_especifico(
                    filtros, titulo_filtro=titulo
                )
            self._notificar_pdf(ruta)
        except Exception as exc:
            QMessageBox.critical(self, "Error al generar PDF", f"No se pudo crear el PDF:\n{exc}")

    def accion_abrir_carpeta(self) -> None:
        objetivo = self._ultimo_pdf if self._ultimo_pdf else rutas.carpeta_reportes()
        abrir_carpeta_contenedora(objetivo)
