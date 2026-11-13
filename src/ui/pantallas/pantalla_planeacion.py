"""Pantalla de Planeación Semanal colaborativa de nivel profesional.

Tablero compartido del equipo con estética moderna (tarjetas limpias, jerarquía
tipográfica, badges en píldoras, bordes semánticos, indicador del día actual,
filtro en tiempo real, KPIs semanales y menú rápido de reasignación de día).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon
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
    QMenu,
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
from services.planeacion import ServicioPlaneacion, inicio_semana
from ui.iconos import configurar_boton, obtener_icono


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
    """Retorna una cadena legible del rango de la semana (ej. '10 al 15 de nov de 2026')."""
    sabado = lunes + timedelta(days=5)
    m_ini = _MESES_ES[lunes.month - 1]
    m_fin = _MESES_ES[sabado.month - 1]
    if lunes.month == sabado.month:
        return f"{lunes.day} al {sabado.day} de {m_fin[:3]} {lunes.year}"
    return f"{lunes.day} {m_ini[:3]} – {sabado.day} {m_fin[:3]} {lunes.year}"


def _formatear_est_min(minutos: int | None) -> str:
    """Formatea minutos a texto conciso (ej. '45m', '1h 30m')."""
    if not minutos or minutos <= 0:
        return ""
    if minutos < 60:
        return f"{minutos}m"
    h = minutos // 60
    m = minutos % 60
    return f"{h}h {m}m" if m else f"{h}h"


class DialogoItemPlaneacion(QDialog):
    """Diálogo modal elegante para crear o editar una tarea en el tablero semanal."""

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
        self.setMinimumWidth(480)
        self.setStyleSheet(
            "QDialog { background-color: #FFFFFF; } "
            "QLabel { color: #0F172A; font-size: 12px; } "
            "QLineEdit, QComboBox, QSpinBox { "
            "  background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 6px; "
            "  padding: 6px 10px; font-size: 12px; min-height: 22px; color: #0F172A; "
            "} "
            "QLineEdit:focus, QComboBox:focus, QSpinBox:focus { "
            "  border-color: #003D95; background-color: #FFFFFF; "
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        # Encabezado visual del diálogo
        fila_cab = QHBoxLayout()
        fila_cab.setSpacing(12)

        icono_banner = QLabel(self)
        icono_banner.setFixedSize(40, 40)
        icono_banner.setStyleSheet(
            "background-color: #EFF6FF; border: 1px solid #BFDBFE; "
            "border-radius: 10px;"
        )
        icono_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icono_banner.setPixmap(obtener_icono("calendar", color="#003D95", tamano=22).pixmap(22, 22))
        fila_cab.addWidget(icono_banner)

        col_tit = QVBoxLayout()
        col_tit.setSpacing(2)
        lbl_tit = QLabel(
            "Editar tarea semanal" if item else "Agregar tarea al tablero semanal",
            self,
        )
        lbl_tit.setStyleSheet("font-size: 15px; font-weight: 700; color: #003D95;")
        lbl_sub = QLabel(
            "Planifica actividades con el equipo y asígnalas a los días de la semana.",
            self,
        )
        lbl_sub.setStyleSheet("font-size: 11px; color: #64748B;")
        col_tit.addWidget(lbl_tit)
        col_tit.addWidget(lbl_sub)
        fila_cab.addLayout(col_tit, 1)
        layout.addLayout(fila_cab)

        # Formulario
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.txt_titulo = QLineEdit(item.titulo if item else "", self)
        self.txt_titulo.setPlaceholderText("Ej. Diseñar carrusel de vacantes, revisar contrato...")

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
        self.combo_dia.addItem("📋 Sin día específico (Semana general)", -1)
        for idx, nom in enumerate(_DIAS_SEMANA_NOMBRES):
            self.combo_dia.addItem(f"📅 {nom}", idx)

        dia_preseleccion = item.dia_semana if item else dia_sugerido
        if dia_preseleccion is not None and 0 <= dia_preseleccion < len(_DIAS_SEMANA_NOMBRES):
            self.combo_dia.setCurrentIndex(dia_preseleccion + 1)
        else:
            self.combo_dia.setCurrentIndex(0)

        self.combo_categoria = QComboBox(self)
        self.combo_categoria.addItem("Sin categoría", None)
        for cat in categorias:
            self.combo_categoria.addItem(f"🏷️ {cat.nombre}", cat.id)
        if item and item.categoria_id:
            idx_c = self.combo_categoria.findData(item.categoria_id)
            if idx_c >= 0:
                self.combo_categoria.setCurrentIndex(idx_c)

        self.combo_prioridad = QComboBox(self)
        self.combo_prioridad.addItem("⚡ Prioridad Normal", Prioridad.NORMAL.value)
        self.combo_prioridad.addItem("🔥 Prioridad Alta (Urgente)", Prioridad.MAXIMA.value)
        self.combo_prioridad.addItem("🔽 Prioridad Baja", Prioridad.MINIMA.value)
        if item and item.prioridad:
            idx_p = self.combo_prioridad.findData(item.prioridad)
            if idx_p >= 0:
                self.combo_prioridad.setCurrentIndex(idx_p)

        # Tiempo estimado con presets rápidos
        cont_tiempo = QWidget(self)
        layout_t = QHBoxLayout(cont_tiempo)
        layout_t.setContentsMargins(0, 0, 0, 0)
        layout_t.setSpacing(6)

        self.spin_estimado = QSpinBox(cont_tiempo)
        self.spin_estimado.setRange(0, 960)
        self.spin_estimado.setValue(item.tiempo_estimado_min or 0 if item else 0)
        self.spin_estimado.setSuffix(" min")
        self.spin_estimado.setSpecialValueText("Sin estimado")
        layout_t.addWidget(self.spin_estimado, 1)

        for min_val, txt_p in ((15, "15m"), (30, "30m"), (45, "45m"), (60, "1h"), (120, "2h")):
            btn_p = QPushButton(txt_p, cont_tiempo)
            btn_p.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_p.setStyleSheet(
                "QPushButton { background: #F1F5F9; border: 1px solid #CBD5E1; "
                "border-radius: 4px; padding: 3px 6px; font-size: 11px; font-weight: 600; color: #475569; } "
                "QPushButton:hover { background: #E2E8F0; color: #003D95; border-color: #003D95; }"
            )
            btn_p.clicked.connect(lambda _c=False, v=min_val: self.spin_estimado.setValue(v))
            layout_t.addWidget(btn_p)

        self.txt_desc = QLineEdit(item.descripcion or "" if item else "", self)
        self.txt_desc.setPlaceholderText("Notas, especificaciones, enlaces o contexto...")

        form.addRow("<b>Tarea*</b>:", self.txt_titulo)
        form.addRow("Responsable:", self.combo_responsable)
        form.addRow("Día asignado:", self.combo_dia)
        form.addRow("Categoría:", self.combo_categoria)
        form.addRow("Prioridad:", self.combo_prioridad)
        form.addRow("Tiempo estimado:", cont_tiempo)
        form.addRow("Detalles / Notas:", self.txt_desc)
        layout.addLayout(form)

        # Botones de acción
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        btn_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        btn_ok.setText("Guardar tarea" if item else "Agregar al tablero")
        btn_ok.setStyleSheet(
            "QPushButton { background-color: #003D95; color: #FFFFFF; font-weight: 700; "
            "border-radius: 6px; padding: 7px 16px; border: none; font-size: 12px; } "
            "QPushButton:hover { background-color: #002D70; }"
        )
        btn_cancel = botones.button(QDialogButtonBox.StandardButton.Cancel)
        btn_cancel.setText("Cancelar")
        btn_cancel.setStyleSheet(
            "QPushButton { background-color: #F1F5F9; color: #475569; font-weight: 600; "
            "border-radius: 6px; padding: 7px 14px; border: 1px solid #CBD5E1; font-size: 12px; } "
            "QPushButton:hover { background-color: #E2E8F0; }"
        )
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
    """Tarjeta individual de tarea en el tablero semanal con diseño pulido y moderno."""

    def __init__(
        self,
        item: ItemPlaneacion,
        *,
        al_alternar: Callable[[int], None],
        al_editar: Callable[[ItemPlaneacion], None],
        al_eliminar: Callable[[int], None],
        al_pasar_hoy: Callable[[int], None],
        al_mover_dia: Callable[[int, int | None], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.item_id = item.id
        self.item = item
        self.al_mover_dia = al_mover_dia

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Color de acento semántico en el borde izquierdo
        if item.completado:
            color_borde = "#CBD5E1"
            bg_card = "#F8FAFC"
        elif item.prioridad == Prioridad.MAXIMA.value:
            color_borde = "#EF4444"
            bg_card = "#FFFFFF"
        elif item.categoria and item.categoria.color:
            color_borde = item.categoria.color
            bg_card = "#FFFFFF"
        else:
            color_borde = "#003D95"
            bg_card = "#FFFFFF"

        self.setStyleSheet(
            f"TarjetaPlaneacion {{ "
            f"  background-color: {bg_card}; "
            f"  border: 1px solid #E2E8F0; "
            f"  border-left: 3.5px solid {color_borde}; "
            f"  border-radius: 8px; "
            f"}} "
            f"TarjetaPlaneacion:hover {{ "
            f"  border-color: #94A3B8; "
            f"  border-left: 3.5px solid {color_borde}; "
            f"}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 7, 9, 7)
        layout.setSpacing(5)

        # 1. Fila superior: Checkbox + Título + Menú rápido de mover
        fila_sup = QHBoxLayout()
        fila_sup.setSpacing(6)
        fila_sup.setContentsMargins(0, 0, 0, 0)

        self.chk = QCheckBox(self)
        self.chk.setChecked(item.completado)
        self.chk.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk.setStyleSheet(
            "QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1.5px solid #CBD5E1; } "
            "QCheckBox::indicator:checked { background-color: #15803D; border-color: #15803D; }"
        )
        self.chk.toggled.connect(lambda _c: al_alternar(item.id))
        fila_sup.addWidget(self.chk)

        self.lbl_titulo = QLabel(item.titulo, self)
        self.lbl_titulo.setWordWrap(True)
        f = self.lbl_titulo.font()
        f.setPointSize(9)
        f.setWeight(QFont.Weight.DemiBold)
        f.setStrikeOut(item.completado)
        self.lbl_titulo.setFont(f)
        if item.completado:
            self.lbl_titulo.setStyleSheet("color: #94A3B8;")
        else:
            self.lbl_titulo.setStyleSheet("color: #0F172A;")

        fila_sup.addWidget(self.lbl_titulo, 1)
        layout.addLayout(fila_sup)

        # 2. Fila badges en píldoras refinadas
        fila_badges = QHBoxLayout()
        fila_badges.setSpacing(4)
        fila_badges.setContentsMargins(0, 0, 0, 0)

        if item.responsable:
            lbl_resp = QLabel(f"👤 {item.responsable}", self)
            lbl_resp.setStyleSheet(
                "background-color: #EEF2FF; color: #3730A3; border: 1px solid #C7D2FE; "
                "font-size: 9.5px; font-weight: 600; padding: 1px 6px; border-radius: 9px;"
            )
            fila_badges.addWidget(lbl_resp)

        if item.categoria:
            c_hex = item.categoria.color or "#003D95"
            lbl_cat = QLabel(item.categoria.nombre, self)
            lbl_cat.setStyleSheet(
                f"background-color: {c_hex}16; color: {c_hex}; border: 1px solid {c_hex}35; "
                "font-size: 9.5px; font-weight: 600; padding: 1px 6px; border-radius: 9px;"
            )
            fila_badges.addWidget(lbl_cat)

        if item.prioridad == Prioridad.MAXIMA.value:
            lbl_prio = QLabel("🔥 Urgente", self)
            lbl_prio.setStyleSheet(
                "background-color: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; "
                "font-size: 9.5px; font-weight: 700; padding: 1px 6px; border-radius: 9px;"
            )
            fila_badges.addWidget(lbl_prio)
        elif item.prioridad == Prioridad.MINIMA.value:
            lbl_prio = QLabel("🔽 Baja", self)
            lbl_prio.setStyleSheet(
                "background-color: #F8FAFC; color: #64748B; border: 1px solid #E2E8F0; "
                "font-size: 9.5px; padding: 1px 6px; border-radius: 9px;"
            )
            fila_badges.addWidget(lbl_prio)

        if item.tiempo_estimado_min:
            t_txt = _formatear_est_min(item.tiempo_estimado_min)
            lbl_est = QLabel(f"⏱ {t_txt}", self)
            lbl_est.setStyleSheet(
                "background-color: #F8FAFC; color: #475569; border: 1px solid #E2E8F0; "
                "font-size: 9.5px; font-weight: 500; padding: 1px 6px; border-radius: 9px;"
            )
            fila_badges.addWidget(lbl_est)

        fila_badges.addStretch()
        layout.addLayout(fila_badges)

        # 3. Descripción o notas si existen
        if item.descripcion:
            lbl_desc = QLabel(item.descripcion, self)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color: #64748B; font-size: 10px; font-style: italic;")
            lbl_desc.setToolTip(item.descripcion)
            layout.addWidget(lbl_desc)

        # 4. Fila inferior: Acción "A mi plan" + Botón Mover día + Editar + Eliminar
        fila_acciones = QHBoxLayout()
        fila_acciones.setSpacing(4)
        fila_acciones.setContentsMargins(0, 3, 0, 0)

        btn_hoy = QPushButton(" A mi plan", self)
        btn_hoy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_hoy.setToolTip("Agregar esta tarea a mi plan de hoy en Hoy · Cronómetro")
        btn_hoy.setStyleSheet(
            "QPushButton { background-color: #EFF6FF; color: #003D95; border: 1px solid #BFDBFE; "
            "border-radius: 5px; font-size: 10px; font-weight: 600; padding: 2px 7px; } "
            "QPushButton:hover { background-color: #003D95; color: #FFFFFF; border-color: #003D95; }"
        )
        configurar_boton(btn_hoy, "play", color="#003D95", tamano=10)
        btn_hoy.clicked.connect(lambda: al_pasar_hoy(item.id))
        fila_acciones.addWidget(btn_hoy)

        fila_acciones.addStretch()

        # Botón para mover a otro día rápidamente vía menú contextual
        btn_mover = QPushButton(self)
        btn_mover.setFixedSize(22, 22)
        btn_mover.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_mover.setToolTip("Mover a otro día de la semana")
        btn_mover.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 0; } "
            "QPushButton:hover { background: #F1F5F9; border-color: #CBD5E1; }"
        )
        configurar_boton(btn_mover, "calendar", color="#475569", tamano=11)
        btn_mover.clicked.connect(lambda: self._mostrar_menu_mover(btn_mover))
        fila_acciones.addWidget(btn_mover)

        btn_edit = QPushButton(self)
        btn_edit.setFixedSize(22, 22)
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.setToolTip("Editar datos de la tarea")
        btn_edit.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 0; } "
            "QPushButton:hover { background: #F1F5F9; border-color: #CBD5E1; }"
        )
        configurar_boton(btn_edit, "edit", color="#475569", tamano=11)
        btn_edit.clicked.connect(lambda: al_editar(item))
        fila_acciones.addWidget(btn_edit)

        btn_del = QPushButton(self)
        btn_del.setFixedSize(22, 22)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setToolTip("Eliminar del tablero")
        btn_del.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 0; } "
            "QPushButton:hover { background: #FEE2E2; border-color: #FECACA; }"
        )
        configurar_boton(btn_del, "trash", color="#EF4444", tamano=11)
        btn_del.clicked.connect(lambda: al_eliminar(item.id))
        fila_acciones.addWidget(btn_del)

        layout.addLayout(fila_acciones)

    def _mostrar_menu_mover(self, boton_ancla: QWidget) -> None:
        """Despliega un menú emergente para mover la tarea a cualquier día de la semana."""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; padding: 4px; } "
            "QMenu::item { padding: 5px 12px; border-radius: 4px; font-size: 11px; color: #0F172A; } "
            "QMenu::item:selected { background-color: #EFF6FF; color: #003D95; font-weight: 600; } "
            "QMenu::separator { height: 1px; background-color: #E2E8F0; margin: 4px 6px; }"
        )

        for idx, nom in enumerate(_DIAS_SEMANA_NOMBRES):
            act = menu.addAction(f"📅 Mover a {nom}")
            act.triggered.connect(lambda _c=False, d=idx: self.al_mover_dia(self.item_id, d))

        menu.addSeparator()
        act_sin = menu.addAction("📋 Mover a Sin día fijo")
        act_sin.triggered.connect(lambda _c=False: self.al_mover_dia(self.item_id, None))

        pos_global = boton_ancla.mapToGlobal(QPoint(0, boton_ancla.height()))
        menu.exec(pos_global)


class PantallaPlaneacion(QWidget):
    """Tablero colaborativo de planeación semanal responsivo y de alta estética."""

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
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        # 1. Cabecera moderna y cinta de herramientas
        card_cabecera = QFrame(cont_scroll)
        card_cabecera.setObjectName("cardCabeceraPlaneacion")
        card_cabecera.setStyleSheet(
            "QFrame#cardCabeceraPlaneacion { "
            "  background-color: #FFFFFF; "
            "  border: 1px solid #E2E8F0; "
            "  border-radius: 12px; "
            "} "
            "QLabel#tituloPantallaPlan { font-size: 16px; font-weight: 700; color: #003D95; } "
            "QLabel#subtituloPlan { font-size: 11px; color: #64748B; }"
        )
        capa_cabecera = QVBoxLayout(card_cabecera)
        capa_cabecera.setContentsMargins(14, 10, 14, 10)
        capa_cabecera.setSpacing(10)

        # Fila 1: Icono + Título + Navegación + Botón Nueva Tarea
        fila_tit = QHBoxLayout()
        fila_tit.setSpacing(10)

        # Badge icono
        lbl_ico = QLabel(card_cabecera)
        lbl_ico.setFixedSize(36, 36)
        lbl_ico.setStyleSheet(
            "background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 9px;"
        )
        lbl_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_ico.setPixmap(obtener_icono("calendar", color="#003D95", tamano=20).pixmap(20, 20))
        fila_tit.addWidget(lbl_ico)

        col_textos = QVBoxLayout()
        col_textos.setSpacing(1)
        lbl_tit = QLabel("Planeación Semanal", card_cabecera)
        lbl_tit.setObjectName("tituloPantallaPlan")
        lbl_sub = QLabel(
            "Tablero de equipo para planificar la semana y trasladar tareas a tu cronómetro.",
            card_cabecera,
        )
        lbl_sub.setObjectName("subtituloPlan")
        col_textos.addWidget(lbl_tit)
        col_textos.addWidget(lbl_sub)
        fila_tit.addLayout(col_textos, 1)

        # Segmented Control de Navegación de Semana
        cont_nav = QFrame(card_cabecera)
        cont_nav.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 2px; }"
        )
        layout_nav = QHBoxLayout(cont_nav)
        layout_nav.setContentsMargins(3, 2, 3, 2)
        layout_nav.setSpacing(4)

        self.btn_ant_sem = QPushButton("◀", cont_nav)
        self.btn_ant_sem.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ant_sem.setToolTip("Semana anterior")
        self.btn_ant_sem.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 11px; font-weight: 700; "
            "color: #475569; padding: 3px 7px; border-radius: 4px; } "
            "QPushButton:hover { background-color: #E2E8F0; color: #003D95; }"
        )
        self.btn_ant_sem.clicked.connect(self._semana_anterior)

        self.lbl_rango_semana = QLabel("", cont_nav)
        self.lbl_rango_semana.setStyleSheet(
            "font-weight: 700; font-size: 11.5px; color: #003D95; padding: 0 6px;"
        )

        self.btn_sig_sem = QPushButton("▶", cont_nav)
        self.btn_sig_sem.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sig_sem.setToolTip("Semana siguiente")
        self.btn_sig_sem.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 11px; font-weight: 700; "
            "color: #475569; padding: 3px 7px; border-radius: 4px; } "
            "QPushButton:hover { background-color: #E2E8F0; color: #003D95; }"
        )
        self.btn_sig_sem.clicked.connect(self._semana_siguiente)

        self.btn_esta_sem = QPushButton("Esta semana", cont_nav)
        self.btn_esta_sem.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_esta_sem.setToolTip("Ir a la semana actual")
        self.btn_esta_sem.setStyleSheet(
            "QPushButton { background-color: #FFFFFF; border: 1px solid #CBD5E1; font-size: 10.5px; "
            "font-weight: 600; color: #0F172A; padding: 2px 7px; border-radius: 4px; } "
            "QPushButton:hover { background-color: #EFF6FF; color: #003D95; border-color: #003D95; }"
        )
        self.btn_esta_sem.clicked.connect(self._ir_esta_semana)

        layout_nav.addWidget(self.btn_ant_sem)
        layout_nav.addWidget(self.lbl_rango_semana)
        layout_nav.addWidget(self.btn_sig_sem)
        layout_nav.addWidget(self.btn_esta_sem)
        fila_tit.addWidget(cont_nav)

        self.btn_nueva_tarea = QPushButton("  + Agregar tarea", card_cabecera)
        self.btn_nueva_tarea.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nueva_tarea.setStyleSheet(
            "QPushButton { background-color: #003D95; color: #FFFFFF; font-weight: 700; "
            "font-size: 12px; border-radius: 7px; padding: 6px 14px; border: none; } "
            "QPushButton:hover { background-color: #002D70; }"
        )
        configurar_boton(self.btn_nueva_tarea, "plus", color="#FFFFFF", tamano=13)
        self.btn_nueva_tarea.clicked.connect(lambda: self.accion_nueva_tarea())
        fila_tit.addWidget(self.btn_nueva_tarea)

        capa_cabecera.addLayout(fila_tit)

        # Fila 2: Filtros + Búsqueda + KPIs en badges píldora
        fila_controles = QHBoxLayout()
        fila_controles.setSpacing(6)

        # Buscador en vivo
        self.txt_buscar = QLineEdit(card_cabecera)
        self.txt_buscar.setPlaceholderText("🔍 Filtrar tareas...")
        self.txt_buscar.setClearButtonEnabled(True)
        self.txt_buscar.setFixedWidth(160)
        self.txt_buscar.setStyleSheet(
            "QLineEdit { background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 6px; "
            "padding: 4px 8px; font-size: 11px; color: #0F172A; } "
            "QLineEdit:focus { border-color: #003D95; background-color: #FFFFFF; }"
        )
        self.txt_buscar.textChanged.connect(lambda _t: self.refrescar())
        fila_controles.addWidget(self.txt_buscar)

        # Filtro Responsable
        self.combo_filtro_resp = QComboBox(card_cabecera)
        self.combo_filtro_resp.setMinimumWidth(130)
        self.combo_filtro_resp.setStyleSheet(
            "QComboBox { background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 6px; "
            "padding: 4px 8px; font-size: 11px; color: #0F172A; } "
            "QComboBox:focus { border-color: #003D95; }"
        )
        self.combo_filtro_resp.currentIndexChanged.connect(lambda _i: self.refrescar())
        fila_controles.addWidget(self.combo_filtro_resp)

        # Filtro Estado
        self.combo_filtro_est = QComboBox(card_cabecera)
        self.combo_filtro_est.setStyleSheet(
            "QComboBox { background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 6px; "
            "padding: 4px 8px; font-size: 11px; color: #0F172A; } "
            "QComboBox:focus { border-color: #003D95; }"
        )
        self.combo_filtro_est.addItem("Todas", "todas")
        self.combo_filtro_est.addItem("Pendientes", "pendientes")
        self.combo_filtro_est.addItem("Completadas", "completadas")
        self.combo_filtro_est.currentIndexChanged.connect(lambda _i: self.refrescar())
        fila_controles.addWidget(self.combo_filtro_est)

        # Toggle Sábado (permite aprovechar más ancho entre semana)
        self.chk_sabado = QCheckBox("Incluir sábado", card_cabecera)
        self.chk_sabado.setStyleSheet(
            "QCheckBox { font-size: 11px; color: #475569; font-weight: 500; margin-left: 4px; }"
        )
        self.chk_sabado.toggled.connect(lambda _c: self.refrescar())
        fila_controles.addWidget(self.chk_sabado)

        fila_controles.addStretch()

        # KPIs en chips píldora
        self.lbl_kpi_total = QLabel(card_cabecera)
        self.lbl_kpi_total.setStyleSheet(
            "background-color: #F1F5F9; color: #334155; border: 1px solid #CBD5E1; "
            "border-radius: 7px; padding: 3px 8px; font-size: 10.5px; font-weight: 600;"
        )
        self.lbl_kpi_pen = QLabel(card_cabecera)
        self.lbl_kpi_pen.setStyleSheet(
            "background-color: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; "
            "border-radius: 7px; padding: 3px 8px; font-size: 10.5px; font-weight: 600;"
        )
        self.lbl_kpi_com = QLabel(card_cabecera)
        self.lbl_kpi_com.setStyleSheet(
            "background-color: #ECFDF5; color: #059669; border: 1px solid #A7F3D0; "
            "border-radius: 7px; padding: 3px 8px; font-size: 10.5px; font-weight: 600;"
        )
        self.lbl_kpi_tiempo = QLabel(card_cabecera)
        self.lbl_kpi_tiempo.setStyleSheet(
            "background-color: #F5F3FF; color: #6D28D9; border: 1px solid #DDD6FE; "
            "border-radius: 7px; padding: 3px 8px; font-size: 10.5px; font-weight: 600;"
        )

        fila_controles.addWidget(self.lbl_kpi_total)
        fila_controles.addWidget(self.lbl_kpi_pen)
        fila_controles.addWidget(self.lbl_kpi_com)
        fila_controles.addWidget(self.lbl_kpi_tiempo)

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
        self.combo_filtro_resp.addItem("👤 Todos los responsables", "")
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
        """Carga y dibuja las columnas del tablero ajustadas con diseño moderno."""
        self.lbl_rango_semana.setText(_formatear_rango_semana(self.fecha_lunes_actual))

        resp_filtro = self.combo_filtro_resp.currentData() or None
        est_filtro = self.combo_filtro_est.currentData() or "todas"
        texto_busqueda = self.txt_buscar.text().strip().lower()
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

        if texto_busqueda:
            items = [
                it for it in items
                if (texto_busqueda in it.titulo.lower()
                    or (it.responsable and texto_busqueda in it.responsable.lower())
                    or (it.descripcion and texto_busqueda in it.descripcion.lower())
                    or (it.categoria and texto_busqueda in it.categoria.nombre.lower()))
            ]

        total_items = len(items)
        completados = sum(1 for it in items if it.completado)
        pendientes = total_items - completados
        min_totales = sum(it.tiempo_estimado_min or 0 for it in items)

        self.lbl_kpi_total.setText(f"📋 {total_items} tareas")
        self.lbl_kpi_pen.setText(f"⏳ {pendientes} pendientes")
        self.lbl_kpi_com.setText(f"✅ {completados} listas")
        self.lbl_kpi_tiempo.setText(f"⏱ {_formatear_est_min(min_totales) or '0m'}")

        # Limpiar columnas previas
        while self.layout_columnas.count():
            item_h = self.layout_columnas.takeAt(0)
            widget = item_h.widget()
            if widget:
                widget.deleteLater()

        # Agrupar ítems por día
        items_por_dia: dict[int | None, list[ItemPlaneacion]] = {None: []}
        for d in range(6):
            items_por_dia[d] = []
        for it in items:
            d_key = it.dia_semana if (it.dia_semana is not None and 0 <= it.dia_semana <= 5) else None
            items_por_dia[d_key].append(it)

        # Detectar si sábado tiene tareas para activarlo si no estaba marcado
        sabado_tiene_items = len(items_por_dia[5]) > 0
        hoy = date.today()
        es_esta_semana = (self.fecha_lunes_actual == inicio_semana(hoy))
        dia_hoy_idx = hoy.weekday() if es_esta_semana and hoy.weekday() <= 5 else None

        mostrar_sabado = self.chk_sabado.isChecked() or sabado_tiene_items or (dia_hoy_idx == 5)
        if sabado_tiene_items and not self.chk_sabado.isChecked():
            self.chk_sabado.blockSignals(True)
            self.chk_sabado.setChecked(True)
            self.chk_sabado.blockSignals(False)

        # Definir columnas
        columnas_def = [
            (0, "Lunes", self.fecha_lunes_actual),
            (1, "Martes", self.fecha_lunes_actual + timedelta(days=1)),
            (2, "Miércoles", self.fecha_lunes_actual + timedelta(days=2)),
            (3, "Jueves", self.fecha_lunes_actual + timedelta(days=3)),
            (4, "Viernes", self.fecha_lunes_actual + timedelta(days=4)),
        ]
        if mostrar_sabado:
            columnas_def.append((5, "Sábado", self.fecha_lunes_actual + timedelta(days=5)))
        columnas_def.append((None, "Sin día fijo", None))

        for dia_idx, titulo_col, fecha_col in columnas_def:
            es_hoy = (dia_idx is not None and dia_idx == dia_hoy_idx)
            col_widget = self._construir_columna(
                dia_idx, titulo_col, fecha_col, items_por_dia[dia_idx], es_hoy=es_hoy
            )
            self.layout_columnas.addWidget(col_widget, 1)

    def _construir_columna(
        self,
        dia_idx: int | None,
        titulo: str,
        fecha_col: date | None,
        items: list[ItemPlaneacion],
        *,
        es_hoy: bool = False,
    ) -> QWidget:
        col_frame = QFrame(self.cont_columnas)
        col_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        col_frame.setMinimumWidth(130)

        # Estilo de columna (resaltado elegante para HOY)
        if es_hoy:
            col_frame.setStyleSheet(
                "QFrame { background-color: #F0F7FF; border: 1.5px solid #003D95; border-radius: 10px; }"
            )
        else:
            col_frame.setStyleSheet(
                "QFrame { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; }"
            )

        layout_col = QVBoxLayout(col_frame)
        layout_col.setContentsMargins(7, 7, 7, 7)
        layout_col.setSpacing(6)

        # Header de la columna
        fila_h = QHBoxLayout()
        fila_h.setSpacing(4)
        fila_h.setContentsMargins(2, 2, 2, 4)

        col_t = QVBoxLayout()
        col_t.setSpacing(1)

        fila_nom = QHBoxLayout()
        fila_nom.setSpacing(4)
        fila_nom.setContentsMargins(0, 0, 0, 0)

        lbl_nombre = QLabel(f"<b>{titulo}</b>", col_frame)
        lbl_nombre.setStyleSheet(
            f"font-size: 12.5px; color: {'#003D95' if es_hoy else '#0F172A'}; background: transparent; border: none;"
        )
        fila_nom.addWidget(lbl_nombre)

        if es_hoy:
            lbl_badge_hoy = QLabel("HOY", col_frame)
            lbl_badge_hoy.setStyleSheet(
                "background-color: #003D95; color: #FFFFFF; font-size: 8.5px; font-weight: 800; "
                "padding: 1px 4px; border-radius: 3px; border: none;"
            )
            fila_nom.addWidget(lbl_badge_hoy)
        fila_nom.addStretch()
        col_t.addLayout(fila_nom)

        sub_txt = f"{fecha_col.day} {_MESES_ES[fecha_col.month - 1][:3]}" if fecha_col else "General"
        lbl_sub = QLabel(sub_txt, col_frame)
        lbl_sub.setStyleSheet("color: #64748B; font-size: 10px; background: transparent; border: none;")
        col_t.addWidget(lbl_sub)
        fila_h.addLayout(col_t, 1)

        # Pill contador de tareas
        lbl_cnt = QLabel(str(len(items)), col_frame)
        if es_hoy:
            lbl_cnt.setStyleSheet(
                "background-color: #003D95; color: #FFFFFF; font-weight: 700; "
                "font-size: 10px; border-radius: 8px; padding: 1px 6px; border: none;"
            )
        else:
            lbl_cnt.setStyleSheet(
                "background-color: #E2E8F0; color: #475569; font-weight: 700; "
                "font-size: 10px; border-radius: 8px; padding: 1px 6px; border: none;"
            )
        fila_h.addWidget(lbl_cnt)

        # Botón rápido "+"
        btn_add = QPushButton(col_frame)
        btn_add.setFixedSize(22, 22)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setToolTip(f"Agregar tarea para {titulo}")
        btn_add.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid transparent; border-radius: 4px; } "
            "QPushButton:hover { background-color: #E2E8F0; border-color: #CBD5E1; }"
        )
        configurar_boton(btn_add, "plus", color="#003D95", tamano=12)
        btn_add.clicked.connect(lambda _c=False, d=dia_idx: self.accion_nueva_tarea(d))
        fila_h.addWidget(btn_add)
        layout_col.addLayout(fila_h)

        # Separador tenue
        linea = QFrame(col_frame)
        linea.setFrameShape(QFrame.Shape.HLine)
        linea.setStyleSheet(
            f"border: none; background-color: {'#BFDBFE' if es_hoy else '#E2E8F0'}; max-height: 1px;"
        )
        layout_col.addWidget(linea)

        # Lista de tarjetas o estado vacío interactivo
        if not items:
            btn_vacio = QPushButton("+ Agregar tarea", col_frame)
            btn_vacio.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_vacio.setToolTip(f"Crear una tarea para {titulo}")
            btn_vacio.setStyleSheet(
                "QPushButton { "
                "  background: transparent; "
                "  border: 1px dashed #CBD5E1; "
                "  border-radius: 7px; "
                "  color: #94A3B8; "
                "  font-size: 11px; "
                "  font-weight: 500; "
                "  padding: 16px 6px; "
                "} "
                "QPushButton:hover { "
                "  background-color: #F1F5F9; "
                "  border-color: #003D95; "
                "  color: #003D95; "
                "}"
            )
            btn_vacio.clicked.connect(lambda _c=False, d=dia_idx: self.accion_nueva_tarea(d))
            layout_col.addWidget(btn_vacio)
        else:
            for it in items:
                tarjeta = TarjetaPlaneacion(
                    it,
                    al_alternar=self.accion_alternar_completado,
                    al_editar=self.accion_editar_tarea,
                    al_eliminar=self.accion_eliminar_tarea,
                    al_pasar_hoy=self.accion_pasar_a_hoy,
                    al_mover_dia=self.accion_mover_dia,
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

    def accion_mover_dia(self, item_id: int, nuevo_dia: int | None) -> None:
        """Mueve una tarea de día con un solo clic y refresca el tablero."""
        with self.bd.sesion() as s:
            ServicioPlaneacion(s).mover_dia(item_id, nuevo_dia)
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
