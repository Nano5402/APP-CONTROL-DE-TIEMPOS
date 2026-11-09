"""Pantalla 4: Cierre de jornada — RF-06, RF-10.

Contiene:
- Asistente para resolver las actividades abiertas del día (Finalizar, Arrastrar
  con motivo y % de avance, o Aplazar).
- Tarjeta con el **Porcentaje de productividad**, semáforo visual, desglose
  (Cumplimiento, Eficiencia, Foco), meta de tiempo efectivo y datos de referencia.
- Botón **"Cerrar jornada"** (que ejecuta la copia de seguridad diaria) y botón
  permanente **"📋 Copiar resumen para WhatsApp"**.
"""

from __future__ import annotations

from collections.abc import Callable

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
from services.cierre_jornada import (
    AccionCierreActividad,
    DecisionActividadCierre,
    ServicioCierreJornada,
)
from services.productividad import ServicioProductividad
from services.whatsapp import ServicioWhatsApp, copiar_al_portapapeles, formatear_duracion_corta


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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        lbl_tit = QLabel("Cierre de Jornada y Productividad", self)
        lbl_tit.setObjectName("tituloPantalla")
        layout.addWidget(lbl_tit)

        # Tarjeta de indicadores del día
        card_ind = QFrame(self)
        card_ind.setProperty("card", True)
        capa_ind = QHBoxLayout(card_ind)

        self.lbl_semaforo = QLabel("—", self)
        self.lbl_semaforo.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.lbl_desglose = QLabel("", self)
        self.lbl_tiempos = QLabel("", self)
        self.lbl_tiempos.setObjectName("subtitulo")

        col_ind = QVBoxLayout()
        col_ind.addWidget(self.lbl_semaforo)
        col_ind.addWidget(self.lbl_desglose)
        col_ind.addWidget(self.lbl_tiempos)
        capa_ind.addLayout(col_ind, 1)

        self.btn_cerrar_jornada = QPushButton("🔒 Cerrar jornada y guardar copia", self)
        self.btn_cerrar_jornada.setProperty("rol", "exito")
        self.btn_cerrar_jornada.clicked.connect(self.accion_cerrar_jornada)
        capa_ind.addWidget(self.btn_cerrar_jornada)
        layout.addWidget(card_ind)

        # Asistente de actividades abiertas
        card_asist = QFrame(self)
        card_asist.setProperty("card", True)
        col_asist = QVBoxLayout(card_asist)
        col_asist.addWidget(
            QLabel(
                "<b>1. Asistente de cierre — Actividades abiertas</b> "
                "(elige qué hacer con cada una antes de cerrar):"
            )
        )
        self.tabla_abiertas = QTableWidget(0, 4, self)
        self.tabla_abiertas.setHorizontalHeaderLabels(
            ["Actividad", "Acción al cerrar", "% Avance (si se arrastra)", "Motivo / Nota"]
        )
        self.tabla_abiertas.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla_abiertas.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        col_asist.addWidget(self.tabla_abiertas)
        layout.addWidget(card_asist, 1)

        # Resumen para WhatsApp
        card_wa = QFrame(self)
        card_wa.setProperty("card", True)
        col_wa = QVBoxLayout(card_wa)
        col_wa.addWidget(QLabel("<b>2. Resumen del día para WhatsApp</b>"))
        self.txt_resumen_wa = QPlainTextEdit(self)
        col_wa.addWidget(self.txt_resumen_wa, 1)

        fila_wa = QHBoxLayout()
        self.btn_copiar_wa = QPushButton("📋 Copiar resumen para WhatsApp", self)
        self.btn_copiar_wa.clicked.connect(self.accion_copiar_resumen)
        fila_wa.addStretch()
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
                self.lbl_semaforo.setText("⚪ Día no laboral (sin porcentaje de productividad)")
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

            for i, act in enumerate(abiertas):
                self.tabla_abiertas.setItem(i, 0, QTableWidgetItem(act.nombre))

                combo = QComboBox(self.tabla_abiertas)
                combo.addItem("Finalizar (100 % completada)", AccionCierreActividad.FINALIZAR.value)
                combo.addItem("Arrastrar para mañana (% avance)", AccionCierreActividad.ARRASTRAR.value)
                combo.addItem("Aplazar", AccionCierreActividad.APLAZAR.value)
                self.tabla_abiertas.setCellWidget(i, 1, combo)

                spin = QSpinBox(self.tabla_abiertas)
                spin.setRange(0, 99)
                spin.setValue(act.avance_pct or 50)
                spin.setSuffix(" %")
                self.tabla_abiertas.setCellWidget(i, 2, spin)

                txt = QLineEdit(self.tabla_abiertas)
                txt.setPlaceholderText("Motivo si se arrastra o nota final...")
                self.tabla_abiertas.setCellWidget(i, 3, txt)

            self.txt_resumen_wa.setPlainText(srv_wa.generar_texto_resumen(jornada, res))

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

        self.refrescar()
        if self.al_cerrar_jornada:
            self.al_cerrar_jornada()
        QMessageBox.information(
            self,
            "Jornada cerrada",
            f"Jornada cerrada correctamente.\nCopia de seguridad guardada en:\n{ruta_copia}",
        )

    def accion_copiar_resumen(self) -> None:
        copiar_al_portapapeles(self.txt_resumen_wa.toPlainText())
        QMessageBox.information(
            self,
            "Resumen copiado",
            "El resumen del día se copió al portapapeles para pegarlo en WhatsApp.",
        )
