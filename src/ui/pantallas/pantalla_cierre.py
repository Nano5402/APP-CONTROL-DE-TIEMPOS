"""Pantalla 4: Cierre de jornada — RF-06, RF-10.

Diseño claro y sin ruido visual:
- Si todas las actividades ya están cerradas, muestra un aviso verde directo
  y oculta la tabla de pendientes.
- En la tabla de actividades abiertas, el campo de ``% de avance`` permanece
  **oculto** salvo que el usuario seleccione «Arrastrar para mañana (% avance)».
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
from data.repositorios.jornadas import RepoJornadas
from reports.generador_pdf import abrir_archivo_pdf, abrir_carpeta_contenedora
from services.cierre_jornada import (
    AccionCierreActividad,
    DecisionActividadCierre,
    ServicioCierreJornada,
)
from services.productividad import ServicioProductividad
from services.whatsapp import ServicioWhatsApp, copiar_al_portapapeles, formatear_duracion_corta
from ui.iconos import configurar_boton


class PantallaCierre(QWidget):
    """Asistente de cierre de jornada y resumen de productividad."""

    def __init__(
        self,
        bd: BaseDatos,
        *,
        al_cerrar_jornada: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bd = bd
        self.al_cerrar_jornada = al_cerrar_jornada
        self._ids_abiertas: list[int] = []
        self._ultimo_pdf: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        lbl_tit = QLabel("Cierre de Jornada y Resumen del Día", self)
        lbl_tit.setObjectName("tituloPantalla")
        layout.addWidget(lbl_tit)

        # Tarjeta de indicadores del día
        card_ind = QFrame(self)
        card_ind.setObjectName("heroCronometro")
        capa_ind = QHBoxLayout(card_ind)

        self.lbl_semaforo = QLabel("—", self)
        self.lbl_semaforo.setStyleSheet("font-size: 22px; font-weight: bold;")
        self.lbl_desglose = QLabel("", self)
        self.lbl_tiempos = QLabel("", self)
        self.lbl_tiempos.setObjectName("subtitulo")

        col_ind = QVBoxLayout()
        col_ind.addWidget(self.lbl_semaforo)
        col_ind.addWidget(self.lbl_desglose)
        col_ind.addWidget(self.lbl_tiempos)
        capa_ind.addLayout(col_ind, 1)

        self.btn_cerrar_jornada = QPushButton("  Cerrar jornada, guardar copia y generar PDF", self)
        self.btn_cerrar_jornada.setProperty("rol", "exito")
        self.btn_cerrar_jornada.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_cerrar_jornada, "flag")
        self.btn_cerrar_jornada.clicked.connect(self.accion_cerrar_jornada)
        capa_ind.addWidget(self.btn_cerrar_jornada)
        layout.addWidget(card_ind)

        # Asistente de actividades abiertas
        self.card_asist = QFrame(self)
        self.card_asist.setProperty("card", True)
        col_asist = QVBoxLayout(self.card_asist)
        self.lbl_titulo_asist = QLabel(
            "<b>1. Tienes actividades abiertas — indica qué pasó con cada una antes de cerrar:</b>",
            self,
        )
        col_asist.addWidget(self.lbl_titulo_asist)

        self.lbl_todo_resuelto = QLabel(
            "Todas las actividades del día están completadas o resueltas. Ya puedes pulsar «Cerrar jornada».",
            self,
        )
        self.lbl_todo_resuelto.setStyleSheet(
            "color: #15803D; font-weight: 600; padding: 6px 2px;"
        )
        col_asist.addWidget(self.lbl_todo_resuelto)

        self.tabla_abiertas = QTableWidget(0, 4, self)
        self.tabla_abiertas.setHorizontalHeaderLabels(
            ["Actividad abierta", "¿Qué deseas hacer?", "% de avance hoy", "Motivo o nota"]
        )
        self.tabla_abiertas.setShowGrid(False)
        self.tabla_abiertas.verticalHeader().setVisible(False)
        self.tabla_abiertas.verticalHeader().setDefaultSectionSize(42)
        self.tabla_abiertas.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla_abiertas.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_abiertas.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        col_asist.addWidget(self.tabla_abiertas)
        layout.addWidget(self.card_asist, 1)

        # Resumen para WhatsApp
        card_wa = QFrame(self)
        card_wa.setProperty("card", True)
        col_wa = QVBoxLayout(card_wa)
        col_wa.addWidget(QLabel("<b>2. Resumen listo para enviar por WhatsApp</b>"))
        self.txt_resumen_wa = QPlainTextEdit(self)
        col_wa.addWidget(self.txt_resumen_wa, 1)

        fila_wa = QHBoxLayout()
        self.btn_generar_pdf_ahora = QPushButton("  Generar / Ver PDF del día", self)
        self.btn_generar_pdf_ahora.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_generar_pdf_ahora, "file-text")
        self.btn_generar_pdf_ahora.clicked.connect(self.accion_generar_pdf_ahora)
        self.btn_abrir_carpeta_pdf = QPushButton("  Abrir carpeta del PDF", self)
        self.btn_abrir_carpeta_pdf.setProperty("rol", "secundario")
        self.btn_abrir_carpeta_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_abrir_carpeta_pdf, "archive", color="#0F172A")
        self.btn_abrir_carpeta_pdf.clicked.connect(self.accion_abrir_carpeta_pdf)
        self.btn_copiar_wa = QPushButton("  Copiar resumen para WhatsApp", self)
        self.btn_copiar_wa.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_copiar_wa, "copy")
        self.btn_copiar_wa.clicked.connect(self.accion_copiar_resumen)
        fila_wa.addStretch()
        fila_wa.addWidget(self.btn_generar_pdf_ahora)
        fila_wa.addWidget(self.btn_abrir_carpeta_pdf)
        fila_wa.addWidget(self.btn_copiar_wa)
        col_wa.addLayout(fila_wa)
        layout.addWidget(card_wa, 1)

        self.refrescar()

    def refrescar(self) -> None:
        with self.bd.sesion() as s:
            jornada = RepoJornadas(s).obtener_o_crear()
            srv_cierre = ServicioCierreJornada(s)
            srv_prod = ServicioProductividad(s)
            srv_wa = ServicioWhatsApp(s)

            res = srv_prod.calcular_jornada(jornada)
            if res.es_laboral and res.productividad_pct is not None:
                self.lbl_semaforo.setText(
                    f"{res.semaforo.emoji()} Productividad del día: {res.productividad_pct:.1f}% "
                    f"— {res.semaforo.etiqueta()}"
                )
                c_txt = f"{res.cumplimiento_pct:.1f}%" if res.cumplimiento_pct is not None else "N/A"
                e_txt = f"{res.eficiencia_pct:.1f}%" if res.eficiencia_pct is not None else "N/A"
                f_txt = f"{res.foco_pct:.1f}%" if res.foco_pct is not None else "N/A"
                self.lbl_desglose.setText(
                    f"Cumplimiento: {c_txt}  ·  Eficiencia: {e_txt}  ·  Foco: {f_txt}"
                )
            else:
                self.lbl_semaforo.setText("Día no laboral (sin porcentaje de productividad)")
                self.lbl_desglose.setText("Todo el tiempo se registra como fuera de horario.")

            self.lbl_tiempos.setText(
                f"Tiempo efectivo: {formatear_duracion_corta(res.tiempo_efectivo_seg)}  ·  "
                f"En pausas: {formatear_duracion_corta(res.tiempo_pausas_seg)}  ·  "
                f"Fuera de horario: {formatear_duracion_corta(res.tiempo_fuera_horario_seg)}  ·  "
                f"Estado jornada: {jornada.estado.upper()}"
            )

            abiertas = srv_cierre.actividades_por_resolver(jornada)
            self._ids_abiertas = [a.id for a in abiertas]
            self.tabla_abiertas.setRowCount(len(abiertas))

            hay_abiertas = len(abiertas) > 0
            self.lbl_titulo_asist.setVisible(hay_abiertas)
            self.tabla_abiertas.setVisible(hay_abiertas)
            self.lbl_todo_resuelto.setVisible(not hay_abiertas)

            for i, act in enumerate(abiertas):
                self.tabla_abiertas.setItem(i, 0, QTableWidgetItem(act.nombre))

                combo = QComboBox(self.tabla_abiertas)
                combo.addItem("Ya la terminé hoy (100 %)", AccionCierreActividad.FINALIZAR.value)
                combo.addItem(
                    "Dejar para continuar mañana (% avance)",
                    AccionCierreActividad.ARRASTRAR.value,
                )
                combo.addItem("Aplazar", AccionCierreActividad.APLAZAR.value)
                self.tabla_abiertas.setCellWidget(i, 1, combo)

                spin = QSpinBox(self.tabla_abiertas)
                spin.setRange(0, 99)
                spin.setValue(act.avance_pct or 50)
                spin.setSuffix(" %")
                # Oculto por defecto porque la primera opción es "Ya la terminé hoy (100 %)"
                spin.setVisible(False)
                self.tabla_abiertas.setCellWidget(i, 2, spin)

                txt = QLineEdit(self.tabla_abiertas)
                txt.setPlaceholderText("Nota opcional...")
                self.tabla_abiertas.setCellWidget(i, 3, txt)

                combo.currentIndexChanged.connect(
                    lambda _idx, c=combo, sp=spin, tx=txt: self._al_cambiar_accion_fila(c, sp, tx)
                )

            self.txt_resumen_wa.setPlainText(srv_wa.generar_texto_resumen(jornada, res))

    @staticmethod
    def _al_cambiar_accion_fila(combo: QComboBox, spin: QSpinBox, txt: QLineEdit) -> None:
        es_arrastrar = combo.currentData() == AccionCierreActividad.ARRASTRAR.value
        spin.setVisible(es_arrastrar)
        if es_arrastrar:
            txt.setPlaceholderText("Obligatorio: ¿por qué queda pendiente para mañana?")
        else:
            txt.setPlaceholderText("Nota opcional...")

    def accion_cerrar_jornada(self) -> None:
        decisiones: list[DecisionActividadCierre] = []
        for i, act_id in enumerate(self._ids_abiertas):
            combo = self.tabla_abiertas.cellWidget(i, 1)
            spin = self.tabla_abiertas.cellWidget(i, 2)
            txt = self.tabla_abiertas.cellWidget(i, 3)

            accion = str(combo.currentData()) if isinstance(combo, QComboBox) else "finalizar"
            avance = int(spin.value()) if isinstance(spin, QSpinBox) else 50
            motivo = txt.text().strip() if isinstance(txt, QLineEdit) else ""

            decisiones.append(
                DecisionActividadCierre(
                    actividad_id=act_id,
                    accion=accion,
                    motivo=motivo or None,
                    avance_pct=avance if accion == AccionCierreActividad.ARRASTRAR.value else None,
                )
            )

        with self.bd.sesion() as s:
            jornada = RepoJornadas(s).obtener_o_crear()
            srv_cierre = ServicioCierreJornada(s)
            try:
                res = srv_cierre.cerrar_jornada(jornada, decisiones=decisiones)
            except Exception as exc:
                QMessageBox.warning(self, "No se pudo cerrar la jornada", str(exc))
                return

            ruta_copia = res.copia_seguridad.ruta if res.copia_seguridad else "—"
            self._ultimo_pdf = res.ruta_pdf

        if self._ultimo_pdf:
            abrir_archivo_pdf(self._ultimo_pdf)

        self.refrescar()
        if self.al_cerrar_jornada:
            self.al_cerrar_jornada()
        pdf_txt = f"\nReporte PDF generado en:\n{self._ultimo_pdf}" if self._ultimo_pdf else ""
        QMessageBox.information(
            self,
            "Jornada cerrada",
            f"Jornada cerrada correctamente.{pdf_txt}\n\nCopia de seguridad guardada en:\n{ruta_copia}",
        )

    def accion_generar_pdf_ahora(self) -> None:
        from services.reportes_pdf import ServicioReportesPDF

        try:
            with self.bd.sesion() as s:
                jornada = RepoJornadas(s).obtener_o_crear()
                ruta = ServicioReportesPDF(s).generar_pdf_jornada(jornada)
            self._ultimo_pdf = ruta
            abrir_archivo_pdf(ruta)
            QMessageBox.information(self, "PDF generado", f"Reporte PDF generado en:\n{ruta}")
        except Exception as exc:
            QMessageBox.critical(self, "Error al generar PDF", f"No se pudo crear el PDF:\n{exc}")

    def accion_abrir_carpeta_pdf(self) -> None:
        from config import rutas

        objetivo = self._ultimo_pdf if self._ultimo_pdf else rutas.carpeta_reportes()
        abrir_carpeta_contenedora(objetivo)

    def accion_copiar_resumen(self) -> None:
        copiar_al_portapapeles(self.txt_resumen_wa.toPlainText())
        QMessageBox.information(
            self,
            "Resumen copiado",
            "El resumen del día se copió al portapapeles para pegarlo en WhatsApp.",
        )
