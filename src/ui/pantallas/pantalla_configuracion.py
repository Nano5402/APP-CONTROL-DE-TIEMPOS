"""Pantalla 8: Configuración segmentada por pestañas — RF-09, RF-12.

Organizada en 5 segmentos claros para que nadie se pierda:
1. 🖥️ Gráficos y Pantalla: tema visual, resolución de la ventana, modo de pantalla
   (ventana normal, maximizada o pantalla completa), tamaño de texto/escala de interfaz
   y tamaño/transparencia de la mini-ventana flotante.
2. 👤 General y Sistema: datos de usuario, empresa, logo/color para PDF e inicio
   automático al encender el portátil.
3. ⏱ Recordatorios y Productividad: intervalos de avisos, sonido, meta de tiempo
   efectivo y pesos de la fórmula.
4. ⌨ Atajos y Plantillas: atajos de teclado opcionales (desactivados por defecto)
   y creación de actividades recurrentes.
5. 🔒 Seguridad y Copias: PIN opcional de acceso y respaldos en carpeta/USB.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from data.db import BaseDatos
from data.enums import Recurrencia, TipoCopia
from data.models import Usuario
from data.repositorios.catalogos import RepoCategorias, RepoPlantillas
from data.repositorios.configuracion import RepoConfiguracion
from services.backups import ServicioBackups
from services.inicio_windows import ServicioInicioWindows, crear_accesos_directos_usuario
from services.seguridad_pin import ServicioPIN
from ui.iconos import configurar_boton, obtener_icono
from ui.sonido import (
    FILTRO_ARCHIVOS_AUDIO,
    TONOS_DEFECTO_POR_CLAVE,
    eliminar_sonido_personalizado,
    importar_sonido_personalizado,
    listar_catalogo_sonidos,
    listar_sonidos_usuario,
    reproducir_tono_aviso,
)
from ui.temas import TEMAS

RESOLUCIONES_DISPONIBLES: list[tuple[str, str]] = [
    ("1024 × 680 — Compacta (Portátiles pequeños)", "1024x680"),
    ("1180 × 740 — Estándar (Recomendada)", "1180x740"),
    ("1280 × 800 — Amplia HD", "1280x800"),
    ("1366 × 768 — Portátil panorámico", "1366x768"),
    ("1440 × 900 — Escritorio Plus", "1440x900"),
    ("1600 × 960 — Monitor grande", "1600x960"),
]

MODOS_VENTANA: list[tuple[str, str]] = [
    ("Ventana normal (con bordes de Windows)", "ventana"),
    ("Ventana sin bordes (limpia y estética)", "sin_bordes"),
    ("Pantalla completa (inmersiva — F11)", "pantalla_completa"),
    ("Maximizada (ajustada a la pantalla)", "maximizada"),
]

ESCALAS_FUENTE: list[tuple[str, int]] = [
    ("Pequeña (90 % — 12 px, más contenido en pantalla)", 12),
    ("Normal (100 % — 13 px, recomendada)", 13),
    ("Grande (115 % — 15 px, lectura más cómoda)", 15),
    ("Extra grande (130 % — 17 px, máxima visibilidad)", 17),
]

TAMANOS_MINI: list[tuple[str, str]] = [
    ("Compacta (350 × 126 px)", "compacta"),
    ("Normal (384 × 136 px)", "normal"),
    ("Grande (420 × 148 px)", "grande"),
]

ESTILOS_AVISO: list[tuple[str, str]] = [
    ("Ventana emergente + Notificación de Windows (Recomendado)", "ambos"),
    ("Solo ventana emergente al frente", "ventana"),
    ("Solo notificación en bandeja de Windows", "notificacion"),
]

EVENTOS_SONIDO: list[tuple[str, str, str]] = [
    (
        "aviso.tono.continuidad",
        "Seguimiento periódico («¿Sigues con...?»)",
        "Suena cada ciertos minutos mientras trabajas en una actividad",
    ),
    (
        "aviso.tono.repeticion",
        "Recordatorio urgente (sin respuesta)",
        "Se repite cuando no respondes el aviso en el tiempo de espera",
    ),
    (
        "aviso.tono.alerta",
        "Tiempo estimado alcanzado / Sin actividad",
        "Avisa si excediste el tiempo estimado o estás sin tarea activa",
    ),
    (
        "aviso.tono.jornada",
        "Hora de almuerzo y Salida",
        "Marca el descanso de mediodía y el cierre de la jornada laboral",
    ),
]


class PantallaConfiguracion(QWidget):
    """Pantalla de configuración general dividida en segmentos por pestañas."""

    def __init__(
        self,
        bd: BaseDatos,
        *,
        al_cambiar_tema: Callable[[str], None] | None = None,
        al_cambiar_atajos: Callable[[], None] | None = None,
        al_cambiar_graficos: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bd = bd
        self.al_cambiar_tema = al_cambiar_tema
        self.al_cambiar_atajos = al_cambiar_atajos
        self.al_cambiar_graficos = al_cambiar_graficos

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        lbl_tit = QLabel("Configuración y Personalización", self)
        lbl_tit.setObjectName("tituloPantalla")
        lbl_sub = QLabel(
            "Elige una pestaña según lo que quieras ajustar y pulsa «Guardar cambios» abajo.",
            self,
        )
        lbl_sub.setObjectName("subtitulo")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_tit)
        layout.addWidget(lbl_sub)

        self.tabs_config = QTabWidget(self)
        self.tabs_config.setUsesScrollButtons(True)
        self.tabs_config.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs_config.addTab(
            self._envolver_scroll(self._construir_tab_graficos()),
            obtener_icono("palette", color="#003D95", tamano=16),
            "Gráficos y Pantalla",
        )
        self.tabs_config.addTab(
            self._envolver_scroll(self._construir_tab_general()),
            obtener_icono("user", color="#003D95", tamano=16),
            "General y Sistema",
        )
        self.tabs_config.addTab(
            self._envolver_scroll(self._construir_tab_recordatorios()),
            obtener_icono("bell", color="#003D95", tamano=16),
            "Notificaciones y Sonidos",
        )
        self.tabs_config.addTab(
            self._envolver_scroll(self._construir_tab_atajos_y_plantillas()),
            obtener_icono("keyboard", color="#003D95", tamano=16),
            "Atajos y Plantillas",
        )
        self.tabs_config.addTab(
            self._envolver_scroll(self._construir_tab_seguridad()),
            obtener_icono("database", color="#003D95", tamano=16),
            "Seguridad y Copias",
        )
        layout.addWidget(self.tabs_config, 1)

        # Barra inferior fija para guardar desde cualquier pestaña
        barra_inf = QFrame(self)
        barra_inf.setProperty("card", True)
        fila_inf = QHBoxLayout(barra_inf)
        fila_inf.setContentsMargins(12, 8, 12, 8)
        lbl_info_guardar = QLabel(
            "Los cambios de resolución, escala de letra, recordatorios y atajos se aplican al instante.",
            barra_inf,
        )
        lbl_info_guardar.setWordWrap(True)
        lbl_info_guardar.setObjectName("subtitulo")
        self.btn_guardar_cfg = QPushButton("  Guardar y aplicar configuración", barra_inf)
        self.btn_guardar_cfg.setProperty("rol", "exito")
        self.btn_guardar_cfg.setProperty("compact", True)
        self.btn_guardar_cfg.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_guardar_cfg, "save")
        self.btn_guardar_cfg.clicked.connect(self.accion_guardar_general)
        fila_inf.addWidget(lbl_info_guardar, 1)
        fila_inf.addWidget(self.btn_guardar_cfg)
        layout.addWidget(barra_inf)

        self.refrescar()

    # ------------------------------------------------------------------
    # Construcción de los 5 segmentos (pestañas)
    # ------------------------------------------------------------------

    def _envolver_scroll(self, contenido: QWidget) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(contenido)
        return scroll

    def _construir_tab_graficos(self) -> QWidget:
        pag = QWidget(self)
        col = QVBoxLayout(pag)
        col.setContentsMargins(4, 8, 4, 4)
        col.setSpacing(12)

        card_pantalla = QFrame(pag)
        card_pantalla.setProperty("card", True)
        self.form_graficos_pantalla = QFormLayout(card_pantalla)
        self.form_graficos_pantalla.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self.form_graficos_pantalla.setSpacing(12)
        self.form_graficos_pantalla.addRow(
            QLabel("<b>Apariencia, Resolución de Ventana y Escala Visual</b>")
        )

        self.combo_tema = QComboBox(card_pantalla)
        for cod, paleta in TEMAS.items():
            self.combo_tema.addItem(paleta.nombre, cod)

        self.combo_modo_ventana = QComboBox(card_pantalla)
        for etq, valor in MODOS_VENTANA:
            self.combo_modo_ventana.addItem(etq, valor)
        self.combo_modo_ventana.currentIndexChanged.connect(
            self._actualizar_visibilidad_resolucion
        )

        self.combo_resolucion = QComboBox(card_pantalla)
        for etq, valor in RESOLUCIONES_DISPONIBLES:
            self.combo_resolucion.addItem(etq, valor)

        self.combo_tamano_fuente = QComboBox(card_pantalla)
        for etq, px in ESCALAS_FUENTE:
            self.combo_tamano_fuente.addItem(etq, px)

        self.form_graficos_pantalla.addRow("Tema de colores:", self.combo_tema)
        self.form_graficos_pantalla.addRow("Modo de visualización:", self.combo_modo_ventana)
        self.form_graficos_pantalla.addRow("Resolución de la ventana:", self.combo_resolucion)
        self.form_graficos_pantalla.addRow("Tamaño de letra e interfaz:", self.combo_tamano_fuente)
        col.addWidget(card_pantalla)

        card_mini = QFrame(pag)
        card_mini.setProperty("card", True)
        form_m = QFormLayout(card_mini)
        form_m.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form_m.setSpacing(12)
        form_m.addRow(QLabel("<b>Mini-ventana flotante del cronómetro</b>"))

        self.combo_mini_tamano = QComboBox(card_mini)
        for etq, val in TAMANOS_MINI:
            self.combo_mini_tamano.addItem(etq, val)

        self.spin_mini_opacidad = QSpinBox(card_mini)
        self.spin_mini_opacidad.setRange(60, 100)
        self.spin_mini_opacidad.setSingleStep(5)
        self.spin_mini_opacidad.setSuffix(" % (100 % = sólida, menor = semitransparente)")

        form_m.addRow("Tamaño de la mini-ventana:", self.combo_mini_tamano)
        form_m.addRow("Opacidad / transparencia:", self.spin_mini_opacidad)
        col.addWidget(card_mini)

        col.addStretch()
        return pag

    def _construir_tab_general(self) -> QWidget:
        pag = QWidget(self)
        col = QVBoxLayout(pag)
        col.setContentsMargins(4, 8, 4, 4)
        col.setSpacing(12)

        card_gen = QFrame(pag)
        card_gen.setProperty("card", True)
        form_gen = QFormLayout(card_gen)
        form_gen.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form_gen.setSpacing(12)
        form_gen.addRow(QLabel("<b>Datos del Usuario y Reportes Corporativos</b>"))

        self.txt_usuario = QLineEdit(card_gen)
        self.txt_usuario.setPlaceholderText("Escribe tu nombre completo (reportes PDF y WhatsApp)")
        self.txt_usuario.setToolTip(
            "Nombre usado en encabezados y firmas de reportes PDF y resúmenes de WhatsApp"
        )
        self.txt_cargo = QLineEdit(card_gen)
        self.txt_cargo.setPlaceholderText("Ej. Analista, Coordinador, Desarrollador, Auxiliar...")
        self.txt_cargo.setToolTip("Cargo o puesto mostrado en los reportes PDF")
        self.txt_area = QLineEdit(card_gen)
        self.txt_area.setPlaceholderText("Ej. Operaciones, Administración, Tecnología...")
        self.txt_area.setToolTip("Área o departamento mostrado en los reportes PDF")
        self.txt_empresa = QLineEdit(card_gen)
        self.txt_color_empresa = QLineEdit(card_gen)
        self.txt_color_empresa.setPlaceholderText("#003D95")
        self.txt_logo_ruta = QLineEdit(card_gen)
        self.txt_logo_ruta.setPlaceholderText("Automático (logo corporativo Gente Util)")
        self.btn_elegir_logo = QPushButton("Elegir imagen...", card_gen)
        self.btn_elegir_logo.setProperty("rol", "secundario")
        self.btn_elegir_logo.setProperty("compact", True)
        self.btn_elegir_logo.clicked.connect(self.accion_elegir_logo)

        fila_logo = QHBoxLayout()
        fila_logo.addWidget(self.txt_logo_ruta, 1)
        fila_logo.addWidget(self.btn_elegir_logo)

        form_gen.addRow("Nombre completo (reportes):", self.txt_usuario)
        form_gen.addRow("Cargo / puesto:", self.txt_cargo)
        form_gen.addRow("Área / departamento:", self.txt_area)
        form_gen.addRow("Empresa:", self.txt_empresa)
        form_gen.addRow("Color primario en reportes PDF:", self.txt_color_empresa)
        form_gen.addRow("Logo para reportes PDF:", fila_logo)
        col.addWidget(card_gen)

        card_win = QFrame(pag)
        card_win.setProperty("card", True)
        col_win = QVBoxLayout(card_win)
        col_win.setSpacing(8)
        col_win.addWidget(QLabel("<b>Arranque con Windows</b>"))

        def _agregar_check_con_ayuda(titulo: str, ayuda: str) -> QCheckBox:
            chk = QCheckBox(titulo, card_win)
            col_win.addWidget(chk)
            lbl_ay = QLabel(ayuda, card_win)
            lbl_ay.setObjectName("subtitulo")
            lbl_ay.setWordWrap(True)
            lbl_ay.setStyleSheet("padding-left: 24px; font-size: 12px;")
            col_win.addWidget(lbl_ay)
            return chk

        self.chk_autostart = _agregar_check_con_ayuda(
            "Iniciar automáticamente al encender el portátil",
            "Abre el control de tiempos al iniciar sesión en Windows.",
        )
        self.chk_iniciar_oculta = _agregar_check_con_ayuda(
            "Arrancar oculta en la bandeja del reloj",
            "Desmarca esta opción para que la ventana principal aparezca en pantalla al iniciar.",
        )
        self.chk_minimizar_al_cerrar = _agregar_check_con_ayuda(
            "Mantener en segundo plano al pulsar la «X»",
            "Si está desmarcado, cerrar la ventana cierra la aplicación por completo.",
        )

        fila_acceso = QHBoxLayout()
        self.btn_crear_acceso_directo = QPushButton(
            "  Crear acceso directo en Escritorio y Menú", card_win
        )
        self.btn_crear_acceso_directo.setProperty("rol", "secundario")
        self.btn_crear_acceso_directo.setProperty("compact", True)
        self.btn_crear_acceso_directo.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_crear_acceso_directo, "external-link", color="#0F172A")
        self.btn_crear_acceso_directo.clicked.connect(self.accion_crear_accesos_directos)
        fila_acceso.addWidget(self.btn_crear_acceso_directo)
        fila_acceso.addStretch()
        col_win.addLayout(fila_acceso)
        col.addWidget(card_win)

        col.addStretch()
        return pag

    def _construir_tab_recordatorios(self) -> QWidget:
        pag = QWidget(self)
        col = QVBoxLayout(pag)
        col.setContentsMargins(4, 8, 4, 4)
        col.setSpacing(12)

        # 1. Tarjeta principal estilo teléfono: Personalizar Sonidos y Volumen
        card_tonos = QFrame(pag)
        card_tonos.setProperty("card", True)
        col_tonos = QVBoxLayout(card_tonos)
        col_tonos.setSpacing(10)

        lbl_tonos_tit = QLabel("<b>Sonidos de Notificación Personalizables (estilo teléfono)</b>", card_tonos)
        lbl_tonos_sub = QLabel(
            "Elige un tono distinto para cada tipo de aviso o sube tus propios archivos (.mp3, .wav, .ogg, .m4a).",
            card_tonos,
        )
        lbl_tonos_sub.setObjectName("subtitulo")
        lbl_tonos_sub.setWordWrap(True)
        col_tonos.addWidget(lbl_tonos_tit)
        col_tonos.addWidget(lbl_tonos_sub)

        # Interruptor maestro + toolbar separada para audios personalizados (evita recortes)
        self.chk_sonido = QCheckBox("Activar sonidos en las notificaciones", card_tonos)
        col_tonos.addWidget(self.chk_sonido)

        fila_audio_maestro = QHBoxLayout()
        fila_audio_maestro.setSpacing(8)

        self.btn_subir_sonido = QPushButton("  Subir audio propio...", card_tonos)
        self.btn_subir_sonido.setProperty("compact", True)
        self.btn_subir_sonido.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_subir_sonido, "folder-open", color="#FFFFFF")
        self.btn_subir_sonido.clicked.connect(lambda: self._accion_subir_audio(None))

        self.btn_aplicar_todos_tonos = QPushButton("Usar tono 1 para todos", card_tonos)
        self.btn_aplicar_todos_tonos.setProperty("rol", "secundario")
        self.btn_aplicar_todos_tonos.setProperty("compact", True)
        self.btn_aplicar_todos_tonos.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_aplicar_todos_tonos.clicked.connect(self._accion_aplicar_tono_a_todos)

        self.btn_eliminar_sonido_custom = QPushButton("  Quitar audio...", card_tonos)
        self.btn_eliminar_sonido_custom.setProperty("rol", "secundario")
        self.btn_eliminar_sonido_custom.setProperty("compact", True)
        self.btn_eliminar_sonido_custom.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_eliminar_sonido_custom, "trash", color="#0F172A")
        self.btn_eliminar_sonido_custom.clicked.connect(self._accion_eliminar_audio_custom)

        fila_audio_maestro.addWidget(self.btn_subir_sonido)
        fila_audio_maestro.addWidget(self.btn_aplicar_todos_tonos)
        fila_audio_maestro.addWidget(self.btn_eliminar_sonido_custom)
        fila_audio_maestro.addStretch()
        col_tonos.addLayout(fila_audio_maestro)

        fila_vol = QHBoxLayout()
        fila_vol.setSpacing(10)
        lbl_vol = QLabel("<b>Volumen:</b>", card_tonos)
        self.slider_volumen = QSlider(Qt.Orientation.Horizontal, card_tonos)
        self.slider_volumen.setRange(0, 100)
        self.slider_volumen.setValue(70)
        self.lbl_volumen_val = QLabel("70 %", card_tonos)
        self.lbl_volumen_val.setMinimumWidth(48)
        self.lbl_volumen_val.setStyleSheet("font-weight: 700;")
        self.slider_volumen.valueChanged.connect(
            lambda v: self.lbl_volumen_val.setText(f"{v} %")
        )

        self.btn_probar_volumen = QPushButton("  Probar", card_tonos)
        self.btn_probar_volumen.setProperty("rol", "secundario")
        self.btn_probar_volumen.setProperty("compact", True)
        self.btn_probar_volumen.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_probar_volumen, "volume-2", color="#0F172A")
        self.btn_probar_volumen.clicked.connect(
            lambda: self._probar_tono_de_clave("aviso.tono.continuidad")
        )

        fila_vol.addWidget(lbl_vol)
        fila_vol.addWidget(self.slider_volumen, 1)
        fila_vol.addWidget(self.lbl_volumen_val)
        fila_vol.addWidget(self.btn_probar_volumen)
        col_tonos.addLayout(fila_vol)

        # Lista de filas estilo ajustes de notificaciones del móvil
        self.combos_tonos: dict[str, QComboBox] = {}
        for clave, titulo_ev, desc_ev in EVENTOS_SONIDO:
            fila_box = QFrame(card_tonos)
            fila_box.setStyleSheet(
                "QFrame { background-color: rgba(255, 255, 255, 0.45); "
                "border: 1px solid rgba(180, 200, 225, 0.45); border-radius: 10px; }"
            )
            fila_ev = QHBoxLayout(fila_box)
            fila_ev.setContentsMargins(12, 8, 12, 8)
            fila_ev.setSpacing(8)

            col_info = QVBoxLayout()
            col_info.setSpacing(2)
            lbl_e_tit = QLabel(f"<b>{titulo_ev}</b>", fila_box)
            lbl_e_tit.setStyleSheet("border: none; background: transparent;")
            lbl_e_tit.setWordWrap(True)
            lbl_e_desc = QLabel(desc_ev, fila_box)
            lbl_e_desc.setObjectName("subtitulo")
            lbl_e_desc.setStyleSheet("border: none; background: transparent;")
            lbl_e_desc.setWordWrap(True)
            col_info.addWidget(lbl_e_tit)
            col_info.addWidget(lbl_e_desc)

            combo = QComboBox(fila_box)
            combo.setMinimumWidth(210)
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            combo.activated.connect(lambda _idx, c=clave: self._probar_tono_de_clave(c))
            self.combos_tonos[clave] = combo

            btn_play = QPushButton("  Probar", fila_box)
            btn_play.setProperty("rol", "secundario")
            btn_play.setProperty("compact", True)
            btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_play.setToolTip(f"Escuchar vista previa de «{titulo_ev}»")
            configurar_boton(btn_play, "volume-2", color="#003D95", tamano=14)
            btn_play.clicked.connect(lambda _c=False, k=clave: self._probar_tono_de_clave(k))

            btn_subir_ev = QPushButton("", fila_box)
            btn_subir_ev.setProperty("rol", "secundario")
            btn_subir_ev.setProperty("compact", True)
            btn_subir_ev.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_subir_ev.setToolTip(f"Elegir archivo .mp3 / .wav del computador para «{titulo_ev}»")
            configurar_boton(btn_subir_ev, "folder-open", color="#0F172A", tamano=15)
            btn_subir_ev.clicked.connect(lambda _c=False, k=clave: self._accion_subir_audio(k))

            fila_ev.addLayout(col_info, 1)
            fila_ev.addWidget(combo)
            fila_ev.addWidget(btn_play)
            fila_ev.addWidget(btn_subir_ev)
            col_tonos.addWidget(fila_box)

        col.addWidget(card_tonos)

        # 2. Modo de entrega y frecuencia de recordatorios
        card_rec = QFrame(pag)
        card_rec.setProperty("card", True)
        form_rec = QFormLayout(card_rec)
        form_rec.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form_rec.setSpacing(12)
        form_rec.addRow(QLabel("<b>Modo de Notificación e Intervalos</b>"))

        self.combo_estilo_aviso = QComboBox(card_rec)
        for etiqueta, codigo in ESTILOS_AVISO:
            self.combo_estilo_aviso.addItem(etiqueta, codigo)

        self.spin_rec_cont = QSpinBox(card_rec)
        self.spin_rec_cont.setRange(1, 180)
        self.spin_rec_cont.setSuffix(" min")

        self.spin_rec_rep = QSpinBox(card_rec)
        self.spin_rec_rep.setRange(1, 60)
        self.spin_rec_rep.setSuffix(" min")

        self.spin_rec_inact = QSpinBox(card_rec)
        self.spin_rec_inact.setRange(1, 120)
        self.spin_rec_inact.setSuffix(" min")

        fila_hor_avisos = QHBoxLayout()
        self.chk_aviso_almuerzo = QCheckBox("Avisar a la hora de almuerzo", card_rec)
        self.chk_aviso_salida = QCheckBox("Avisar a la hora de salida", card_rec)
        fila_hor_avisos.addWidget(self.chk_aviso_almuerzo)
        fila_hor_avisos.addWidget(self.chk_aviso_salida)
        fila_hor_avisos.addStretch()

        form_rec.addRow("Cómo mostrar las notificaciones:", self.combo_estilo_aviso)
        form_rec.addRow("Preguntar «¿Sigues con...?» cada:", self.spin_rec_cont)
        form_rec.addRow("Repetir aviso si no respondes cada:", self.spin_rec_rep)
        form_rec.addRow("Sin actividad tras:", self.spin_rec_inact)
        form_rec.addRow("Recordatorios de horario:", fila_hor_avisos)
        col.addWidget(card_rec)

        card_prod = QFrame(pag)
        card_prod.setProperty("card", True)
        form_prod = QFormLayout(card_prod)
        form_prod.setSpacing(12)
        form_prod.addRow(QLabel("<b>Pesos de Productividad y Referencia de Jornada</b>"))

        self.spin_meta_pct = QSpinBox(card_prod)
        self.spin_meta_pct.setRange(10, 100)
        self.spin_meta_pct.setSuffix(" % de la jornada")

        self.spin_peso_c = QSpinBox(card_prod)
        self.spin_peso_c.setRange(0, 100)
        self.spin_peso_c.setSuffix(" %")
        self.spin_peso_e = QSpinBox(card_prod)
        self.spin_peso_e.setRange(0, 100)
        self.spin_peso_e.setSuffix(" %")
        self.spin_peso_f = QSpinBox(card_prod)
        self.spin_peso_f.setRange(0, 100)
        self.spin_peso_f.setSuffix(" %")

        fila_pesos = QHBoxLayout()
        fila_pesos.addWidget(QLabel("Cumplimiento:"))
        fila_pesos.addWidget(self.spin_peso_c)
        fila_pesos.addWidget(QLabel("Eficiencia:"))
        fila_pesos.addWidget(self.spin_peso_e)
        fila_pesos.addWidget(QLabel("Foco:"))
        fila_pesos.addWidget(self.spin_peso_f)

        form_prod.addRow("Jornada de referencia (% efectivo):", self.spin_meta_pct)
        form_prod.addRow("Pesos de la fórmula (suman 100 %):", fila_pesos)
        col.addWidget(card_prod)

        col.addStretch()
        return pag

    def _construir_tab_atajos_y_plantillas(self) -> QWidget:
        pag = QWidget(self)
        col = QVBoxLayout(pag)
        col.setContentsMargins(4, 8, 4, 4)
        col.setSpacing(12)

        card_atajos = QFrame(pag)
        card_atajos.setProperty("card", True)
        form_atajos = QFormLayout(card_atajos)
        form_atajos.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form_atajos.setSpacing(10)
        lbl_atajos_tit = QLabel(
            "<b>Atajos de teclado opcionales</b> "
            "(desactivados por defecto para no interferir con otros programas)",
            card_atajos,
        )
        lbl_atajos_tit.setWordWrap(True)
        form_atajos.addRow(lbl_atajos_tit)

        self.key_iniciar_pausar = QKeySequenceEdit(card_atajos)
        self.key_finalizar = QKeySequenceEdit(card_atajos)
        self.key_siguiente = QKeySequenceEdit(card_atajos)
        self.key_mini = QKeySequenceEdit(card_atajos)

        form_atajos.addRow(
            "Iniciar / Detener actividad:",
            self._fila_key_edit(self.key_iniciar_pausar),
        )
        form_atajos.addRow(
            "Finalizar actividad en curso:",
            self._fila_key_edit(self.key_finalizar),
        )
        form_atajos.addRow(
            "Terminar y seguir con la siguiente:",
            self._fila_key_edit(self.key_siguiente),
        )
        form_atajos.addRow(
            "Mostrar / Ocultar Mini-ventana:",
            self._fila_key_edit(self.key_mini),
        )

        self.btn_limpiar_atajos = QPushButton(
            "  Desactivar / Limpiar todos los atajos", card_atajos
        )
        self.btn_limpiar_atajos.setProperty("rol", "secundario")
        configurar_boton(self.btn_limpiar_atajos, "trash", color="#0F172A")
        self.btn_limpiar_atajos.clicked.connect(self.accion_limpiar_todos_los_atajos)
        form_atajos.addRow("", self.btn_limpiar_atajos)
        col.addWidget(card_atajos)

        card_plant = QFrame(pag)
        card_plant.setProperty("card", True)
        form_plant = QFormLayout(card_plant)
        form_plant.setSpacing(10)
        form_plant.addRow(
            QLabel("<b>Crear plantilla o actividad recurrente para las mañanas</b>")
        )

        self.txt_plant_nombre = QLineEdit(card_plant)
        self.txt_plant_nombre.setPlaceholderText("Ej. Flyers vacantes, Posts de Instagram...")
        self.txt_plant_cat = QLineEdit(card_plant)
        self.txt_plant_cat.setPlaceholderText("Categoría (opcional)")
        self.spin_plant_est = QSpinBox(card_plant)
        self.spin_plant_est.setRange(0, 480)
        self.spin_plant_est.setSuffix(" min")
        self.combo_plant_rec = QComboBox(card_plant)
        self.combo_plant_rec.addItem("Diaria (todos los días)", Recurrencia.DIARIA.value)
        self.combo_plant_rec.addItem("Lunes a viernes", Recurrencia.DIAS_SEMANA.value)
        self.combo_plant_rec.addItem("Manual (sin recurrencia)", Recurrencia.NINGUNA.value)

        self.btn_crear_plant = QPushButton("  Guardar plantilla", card_plant)
        self.btn_crear_plant.setProperty("rol", "exito")
        configurar_boton(self.btn_crear_plant, "plus")
        self.btn_crear_plant.clicked.connect(self.accion_crear_plantilla)

        form_plant.addRow("Nombre de la plantilla:", self.txt_plant_nombre)
        form_plant.addRow("Categoría:", self.txt_plant_cat)
        form_plant.addRow("Tiempo estimado:", self.spin_plant_est)
        form_plant.addRow("Frecuencia:", self.combo_plant_rec)
        form_plant.addRow("", self.btn_crear_plant)
        col.addWidget(card_plant)

        col.addStretch()
        return pag

    def _construir_tab_seguridad(self) -> QWidget:
        pag = QWidget(self)
        col = QVBoxLayout(pag)
        col.setContentsMargins(4, 8, 4, 4)
        col.setSpacing(12)

        card_pin = QFrame(pag)
        card_pin.setProperty("card", True)
        col_pin = QVBoxLayout(card_pin)
        col_pin.setSpacing(10)
        col_pin.addWidget(QLabel("<b>PIN Opcional de Acceso</b>"))
        lbl_pin_ayuda = QLabel(
            "Si compartes el portátil con otras personas, puedes activar un PIN numérico al abrir la aplicación.",
            card_pin,
        )
        lbl_pin_ayuda.setWordWrap(True)
        lbl_pin_ayuda.setObjectName("subtitulo")
        col_pin.addWidget(lbl_pin_ayuda)

        fila_pin = QHBoxLayout()
        self.txt_nuevo_pin = QLineEdit(card_pin)
        self.txt_nuevo_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_nuevo_pin.setPlaceholderText("Escribe un PIN de 4 o más dígitos")
        self.btn_ver_nuevo_pin = QPushButton("Ver", card_pin)
        self.btn_ver_nuevo_pin.setProperty("rol", "secundario")
        self.btn_ver_nuevo_pin.setProperty("compact", True)
        self.btn_ver_nuevo_pin.setCheckable(True)
        self.btn_ver_nuevo_pin.setMinimumWidth(84)
        self.btn_ver_nuevo_pin.toggled.connect(
            lambda v: (
                self.txt_nuevo_pin.setEchoMode(
                    QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password
                ),
                self.btn_ver_nuevo_pin.setText("Ocultar" if v else "Ver"),
            )
        )
        self.btn_fijar_pin = QPushButton("Establecer PIN", card_pin)
        self.btn_fijar_pin.setProperty("compact", True)
        self.btn_quitar_pin = QPushButton("Desactivar PIN", card_pin)
        self.btn_quitar_pin.setProperty("rol", "secundario")
        self.btn_quitar_pin.setProperty("compact", True)
        self.btn_fijar_pin.clicked.connect(self.accion_establecer_pin)
        self.btn_quitar_pin.clicked.connect(self.accion_quitar_pin)
        fila_pin.addWidget(self.txt_nuevo_pin, 1)
        fila_pin.addWidget(self.btn_ver_nuevo_pin)
        fila_pin.addWidget(self.btn_fijar_pin)
        fila_pin.addWidget(self.btn_quitar_pin)
        col_pin.addLayout(fila_pin)
        col.addWidget(card_pin)

        card_bak = QFrame(pag)
        card_bak.setProperty("card", True)
        col_bak = QVBoxLayout(card_bak)
        col_bak.setSpacing(10)
        col_bak.addWidget(QLabel("<b>Copias de Seguridad y Restauración</b>"))
        lbl_bak_ayuda = QLabel(
            "La aplicación guarda una copia automática cada vez que cierras jornada. "
            "También puedes crear una copia manual ahora o llevarla en una memoria USB.",
            card_bak,
        )
        lbl_bak_ayuda.setObjectName("subtitulo")
        lbl_bak_ayuda.setWordWrap(True)
        col_bak.addWidget(lbl_bak_ayuda)

        fila_bak = QHBoxLayout()
        self.btn_backup_manual = QPushButton("  Crear copia de respaldo", card_bak)
        self.btn_backup_manual.setProperty("compact", True)
        configurar_boton(self.btn_backup_manual, "archive")
        self.btn_backup_usb = QPushButton("  Exportar a USB o carpeta", card_bak)
        self.btn_backup_usb.setProperty("rol", "secundario")
        self.btn_backup_usb.setProperty("compact", True)
        configurar_boton(self.btn_backup_usb, "share", color="#0F172A")
        self.btn_restaurar = QPushButton("  Restaurar copia (.db)", card_bak)
        self.btn_restaurar.setProperty("rol", "advertencia")
        self.btn_restaurar.setProperty("compact", True)
        configurar_boton(self.btn_restaurar, "refresh-cw")

        self.btn_backup_manual.clicked.connect(self.accion_copia_manual)
        self.btn_backup_usb.clicked.connect(self.accion_copia_usb)
        self.btn_restaurar.clicked.connect(self.accion_restaurar)

        fila_bak.addWidget(self.btn_backup_manual)
        fila_bak.addWidget(self.btn_backup_usb)
        fila_bak.addWidget(self.btn_restaurar)
        fila_bak.addStretch()
        col_bak.addLayout(fila_bak)
        col.addWidget(card_bak)

        col.addStretch()
        return pag

    def _actualizar_visibilidad_resolucion(self) -> None:
        es_ventana = self.combo_modo_ventana.currentData() in ("ventana", "sin_bordes")
        self.form_graficos_pantalla.setRowVisible(self.combo_resolucion, es_ventana)

    def _fila_key_edit(self, editor: QKeySequenceEdit) -> QWidget:
        cont = QWidget(self)
        fila = QHBoxLayout(cont)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(6)
        btn_limpiar = QPushButton("  Quitar", cont)
        btn_limpiar.setProperty("rol", "secundario")
        btn_limpiar.setProperty("compact", True)
        configurar_boton(btn_limpiar, "x", color="#0F172A", tamano=12)
        btn_limpiar.clicked.connect(editor.clear)
        fila.addWidget(editor, 1)
        fila.addWidget(btn_limpiar)
        return cont

    def accion_limpiar_todos_los_atajos(self) -> None:
        self.key_iniciar_pausar.clear()
        self.key_finalizar.clear()
        self.key_siguiente.clear()
        self.key_mini.clear()

    # ------------------------------------------------------------------
    # Carga y guardado de configuración
    # ------------------------------------------------------------------

    def refrescar(self) -> None:
        with self.bd.sesion() as s:
            usr = s.scalar(select(Usuario).limit(1))
            cfg = RepoConfiguracion(s)

            self.txt_usuario.setText((usr.nombre or "").strip() if usr else "")
            self.txt_cargo.setText((cfg.obtener("usuario.cargo", "") or "").strip())
            self.txt_area.setText((cfg.obtener("usuario.area", "") or "").strip())
            self.txt_empresa.setText(cfg.obtener("empresa.nombre", "Gente Util") or "Gente Util")
            self.txt_color_empresa.setText(
                cfg.obtener("empresa.color_primario", "#003D95") or "#003D95"
            )
            self.txt_logo_ruta.setText(cfg.obtener("empresa.logo_ruta", "") or "")

            tema_actual = usr.tema if usr and usr.tema else "gente_util"
            idx_t = self.combo_tema.findData(tema_actual)
            if idx_t >= 0:
                self.combo_tema.setCurrentIndex(idx_t)

            resolucion = cfg.obtener("graficos.resolucion", "1180x740") or "1180x740"
            idx_r = self.combo_resolucion.findData(resolucion)
            if idx_r >= 0:
                self.combo_resolucion.setCurrentIndex(idx_r)

            modo_v = cfg.obtener("graficos.modo_ventana", "ventana") or "ventana"
            idx_m = self.combo_modo_ventana.findData(modo_v)
            if idx_m >= 0:
                self.combo_modo_ventana.setCurrentIndex(idx_m)
            self._actualizar_visibilidad_resolucion()

            tam_fuente = cfg.obtener_int("graficos.tamano_fuente", 13)
            idx_f = self.combo_tamano_fuente.findData(tam_fuente)
            if idx_f >= 0:
                self.combo_tamano_fuente.setCurrentIndex(idx_f)

            mini_tam = cfg.obtener("graficos.mini_tamano", "normal") or "normal"
            idx_mt = self.combo_mini_tamano.findData(mini_tam)
            if idx_mt >= 0:
                self.combo_mini_tamano.setCurrentIndex(idx_mt)

            self.spin_mini_opacidad.setValue(cfg.obtener_int("graficos.mini_opacidad", 95))

            self.chk_autostart.setChecked(cfg.obtener_bool("sistema.inicio_con_windows", True))
            self.chk_iniciar_oculta.setChecked(
                cfg.obtener_bool("sistema.iniciar_minimizada_bandeja", False)
            )
            self.chk_minimizar_al_cerrar.setChecked(
                cfg.obtener_bool("sistema.minimizar_al_cerrar", False)
            )

            self.key_iniciar_pausar.setKeySequence(
                QKeySequence(cfg.obtener("atajo.iniciar_pausar", "") or "")
            )
            self.key_finalizar.setKeySequence(
                QKeySequence(cfg.obtener("atajo.finalizar", "") or "")
            )
            self.key_siguiente.setKeySequence(
                QKeySequence(cfg.obtener("atajo.siguiente_pieza", "") or "")
            )
            self.key_mini.setKeySequence(
                QKeySequence(cfg.obtener("atajo.mini_ventana", "") or "")
            )

            self.spin_rec_cont.setValue(cfg.obtener_int("recordatorio.continuidad_min", 10))
            self.spin_rec_rep.setValue(
                cfg.obtener_int("recordatorio.repetir_sin_respuesta_min", 2)
            )
            self.spin_rec_inact.setValue(
                cfg.obtener_int("recordatorio.inicio_sin_actividad_min", 10)
            )
            self.chk_sonido.setChecked(cfg.obtener_bool("aviso.sonido", True))
            volumen = cfg.obtener_int("aviso.volumen", 70)
            self.slider_volumen.setValue(max(0, min(100, volumen)))
            self.lbl_volumen_val.setText(f"{self.slider_volumen.value()} %")

            estilo = cfg.obtener("aviso.estilo", "ambos") or "ambos"
            idx_e = self.combo_estilo_aviso.findData(estilo)
            if idx_e >= 0:
                self.combo_estilo_aviso.setCurrentIndex(idx_e)

            self.chk_aviso_almuerzo.setChecked(cfg.obtener_bool("recordatorio.aviso_almuerzo", True))
            self.chk_aviso_salida.setChecked(cfg.obtener_bool("recordatorio.aviso_salida", True))

            seleccion_tonos = {
                clave: (cfg.obtener(clave, defecto) or defecto)
                for clave, defecto in TONOS_DEFECTO_POR_CLAVE.items()
            }
            self._recargar_combos_tonos(seleccion_tonos)

            self.spin_meta_pct.setValue(int(cfg.obtener_float("meta.tiempo_efectivo_pct", 100)))

            self.spin_peso_c.setValue(
                int(round(cfg.obtener_float("productividad.peso_cumplimiento", 0.40) * 100))
            )
            self.spin_peso_e.setValue(
                int(round(cfg.obtener_float("productividad.peso_eficiencia", 0.30) * 100))
            )
            self.spin_peso_f.setValue(
                int(round(cfg.obtener_float("productividad.peso_foco", 0.30) * 100))
            )

    def accion_guardar_general(self) -> None:
        suma_pesos = (
            self.spin_peso_c.value() + self.spin_peso_e.value() + self.spin_peso_f.value()
        )
        if suma_pesos != 100:
            QMessageBox.warning(
                self,
                "Pesos de fórmula",
                f"Los tres pesos deben sumar 100 % (actualmente suman {suma_pesos} %).",
            )
            return

        tema = str(self.combo_tema.currentData())
        resolucion = str(self.combo_resolucion.currentData())
        modo_ventana = str(self.combo_modo_ventana.currentData())
        tam_fuente = int(self.combo_tamano_fuente.currentData())
        mini_tamano = str(self.combo_mini_tamano.currentData())
        mini_opacidad = int(self.spin_mini_opacidad.value())

        autostart = self.chk_autostart.isChecked()
        iniciar_oculta = self.chk_iniciar_oculta.isChecked()

        with self.bd.sesion() as s:
            usr = s.scalar(select(Usuario).limit(1))
            nombre_usuario = self.txt_usuario.text().strip()
            if usr is None:
                usr = Usuario(nombre=nombre_usuario, tema=tema)
                s.add(usr)
            else:
                usr.nombre = nombre_usuario
                usr.tema = tema

            cfg = RepoConfiguracion(s)
            cfg.guardar("usuario.cargo", self.txt_cargo.text().strip())
            cfg.guardar("usuario.area", self.txt_area.text().strip())
            cfg.guardar("empresa.nombre", self.txt_empresa.text().strip() or "Gente Util")
            cfg.guardar(
                "empresa.color_primario", self.txt_color_empresa.text().strip() or "#003D95"
            )
            cfg.guardar("empresa.logo_ruta", self.txt_logo_ruta.text().strip())

            cfg.guardar("graficos.resolucion", resolucion)
            cfg.guardar("graficos.modo_ventana", modo_ventana)
            cfg.guardar("graficos.tamano_fuente", tam_fuente)
            cfg.guardar("graficos.mini_tamano", mini_tamano)
            cfg.guardar("graficos.mini_opacidad", mini_opacidad)

            cfg.guardar("sistema.inicio_con_windows", autostart)
            cfg.guardar("sistema.iniciar_minimizada_bandeja", iniciar_oculta)
            cfg.guardar(
                "sistema.minimizar_al_cerrar", self.chk_minimizar_al_cerrar.isChecked()
            )

            cfg.guardar(
                "atajo.iniciar_pausar", self.key_iniciar_pausar.keySequence().toString()
            )
            cfg.guardar("atajo.finalizar", self.key_finalizar.keySequence().toString())
            cfg.guardar(
                "atajo.siguiente_pieza", self.key_siguiente.keySequence().toString()
            )
            cfg.guardar("atajo.mini_ventana", self.key_mini.keySequence().toString())

            cfg.guardar("recordatorio.continuidad_min", int(self.spin_rec_cont.value()))
            cfg.guardar(
                "recordatorio.repetir_sin_respuesta_min", int(self.spin_rec_rep.value())
            )
            cfg.guardar(
                "recordatorio.inicio_sin_actividad_min", int(self.spin_rec_inact.value())
            )
            cfg.guardar("aviso.sonido", self.chk_sonido.isChecked())
            cfg.guardar("aviso.volumen", int(self.slider_volumen.value()))
            cfg.guardar(
                "aviso.estilo", str(self.combo_estilo_aviso.currentData() or "ambos")
            )
            cfg.guardar("recordatorio.aviso_almuerzo", self.chk_aviso_almuerzo.isChecked())
            cfg.guardar("recordatorio.aviso_salida", self.chk_aviso_salida.isChecked())
            for clave, combo in self.combos_tonos.items():
                cfg.guardar(clave, str(combo.currentData() or TONOS_DEFECTO_POR_CLAVE[clave]))

            cfg.guardar("meta.tiempo_efectivo_pct", int(self.spin_meta_pct.value()))
            cfg.guardar(
                "productividad.peso_cumplimiento",
                f"{self.spin_peso_c.value() / 100.0:.2f}",
            )
            cfg.guardar(
                "productividad.peso_eficiencia",
                f"{self.spin_peso_e.value() / 100.0:.2f}",
            )
            cfg.guardar(
                "productividad.peso_foco",
                f"{self.spin_peso_f.value() / 100.0:.2f}",
            )

        try:
            ServicioInicioWindows().sincronizar(autostart)
        except Exception:
            pass

        if self.al_cambiar_graficos:
            self.al_cambiar_graficos()
        elif self.al_cambiar_tema:
            self.al_cambiar_tema(tema)

        if self.al_cambiar_atajos:
            self.al_cambiar_atajos()

        QMessageBox.information(
            self,
            "Configuración aplicada",
            "Los cambios de gráficos, pantalla y preferencias se aplicaron correctamente.",
        )

    def accion_elegir_logo(self) -> None:
        archivo, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar logo de la empresa",
            "",
            "Imágenes (*.svg *.png *.jpg *.jpeg)",
        )
        if archivo:
            self.txt_logo_ruta.setText(archivo)

    def accion_crear_accesos_directos(self) -> None:
        creados = crear_accesos_directos_usuario()
        if creados:
            rutas_txt = "\n".join(f"• {r}" for r in creados)
            QMessageBox.information(
                self,
                "Accesos directos creados",
                "Se crearon los accesos directos con el logo de la app en:\n\n"
                f"{rutas_txt}\n\n"
                "Para anclarla a la barra de tareas: abre la app desde ese icono, "
                "haz clic derecho sobre su icono en la barra de tareas y elige «Anclar a la barra de tareas».",
            )
        else:
            QMessageBox.warning(
                self, "Aviso", "No se pudieron crear los accesos directos automáticamente."
            )

    def accion_crear_plantilla(self) -> None:
        nombre = self.txt_plant_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Nombre requerido", "Escribe el nombre de la plantilla.")
            return
        cat_txt = self.txt_plant_cat.text().strip()
        est = int(self.spin_plant_est.value()) or None
        rec = str(self.combo_plant_rec.currentData())
        dias = [0, 1, 2, 3, 4] if rec == Recurrencia.DIAS_SEMANA.value else None

        with self.bd.sesion() as s:
            cat_id = RepoCategorias(s).obtener_o_crear(cat_txt).id if cat_txt else None
            RepoPlantillas(s).crear(
                nombre,
                categoria_id=cat_id,
                tiempo_estimado_min=est,
                recurrencia=rec,
                dias_semana=dias,
            )

        self.txt_plant_nombre.clear()
        QMessageBox.information(
            self, "Plantilla creada", f"La plantilla «{nombre}» se propondrá al planear el día."
        )

    def accion_establecer_pin(self) -> None:
        pin = self.txt_nuevo_pin.text().strip()
        try:
            with self.bd.sesion() as s:
                ServicioPIN(s).establecer_pin(pin)
        except ValueError as exc:
            QMessageBox.warning(self, "PIN inválido", str(exc))
            return
        self.txt_nuevo_pin.clear()
        QMessageBox.information(self, "PIN activo", "El PIN quedó activado para este PC.")

    def accion_quitar_pin(self) -> None:
        with self.bd.sesion() as s:
            ServicioPIN(s).desactivar_pin()
        self.txt_nuevo_pin.clear()
        QMessageBox.information(self, "PIN desactivado", "La app ya no pedirá PIN al abrir.")

    def accion_copia_manual(self) -> None:
        with self.bd.sesion() as s:
            copia = ServicioBackups(s).crear_copia(TipoCopia.MANUAL)
            ruta = copia.ruta
        QMessageBox.information(self, "Copia creada", f"Copia guardada en:\n{ruta}")

    def accion_copia_usb(self) -> None:
        carpeta = QFileDialog.getExistingDirectory(
            self, "Elegir USB o carpeta para la copia de seguridad"
        )
        if not carpeta:
            return
        with self.bd.sesion() as s:
            copia = ServicioBackups(s).copiar_a_carpeta_externa(carpeta)
            ruta = copia.ruta
        QMessageBox.information(self, "Copia en carpeta/USB", f"Copia guardada en:\n{ruta}")

    def accion_restaurar(self) -> None:
        archivo, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo de copia de seguridad (.db)",
            "",
            "Base de datos SQLite (*.db)",
        )
        if not archivo:
            return
        with self.bd.sesion() as s:
            try:
                ServicioBackups(s).restaurar_desde_archivo(archivo)
            except Exception as exc:
                QMessageBox.warning(self, "Archivo inválido", str(exc))
                return
        QMessageBox.information(
            self,
            "Copia restaurada",
            "Los datos fueron restaurados correctamente.",
        )

    # ------------------------------------------------------------------
    # Personalización de sonidos de notificación (estilo teléfono)
    # ------------------------------------------------------------------

    def _recargar_combos_tonos(
        self, seleccion_por_clave: dict[str, str] | None = None
    ) -> None:
        catalogo = listar_catalogo_sonidos()
        personalizados = listar_sonidos_usuario()
        self.btn_eliminar_sonido_custom.setEnabled(len(personalizados) > 0)

        for clave, combo in self.combos_tonos.items():
            objetivo = (
                seleccion_por_clave.get(clave)
                if seleccion_por_clave is not None
                else combo.currentData()
            ) or TONOS_DEFECTO_POR_CLAVE[clave]

            combo.blockSignals(True)
            combo.clear()
            for cod, etiq in catalogo:
                combo.addItem(etiq, cod)
            idx = combo.findData(objetivo)
            if idx < 0:
                idx = combo.findData(TONOS_DEFECTO_POR_CLAVE[clave])
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def _probar_tono_de_clave(self, clave: str) -> None:
        combo = self.combos_tonos.get(clave)
        if combo is None:
            return
        codigo_tono = str(combo.currentData() or TONOS_DEFECTO_POR_CLAVE[clave])
        reproducir_tono_aviso(
            habilitado=True,
            es_repeticion=(clave == "aviso.tono.repeticion"),
            tono=codigo_tono,
            volumen=int(self.slider_volumen.value()),
        )

    def _accion_subir_audio(self, clave_destino: str | None = None) -> None:
        archivo, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo de sonido personalizado",
            "",
            FILTRO_ARCHIVOS_AUDIO,
        )
        if not archivo:
            return

        try:
            codigo = importar_sonido_personalizado(archivo)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "No se pudo importar el audio",
                str(exc),
            )
            return

        actuales = {
            c: str(cb.currentData() or TONOS_DEFECTO_POR_CLAVE[c])
            for c, cb in self.combos_tonos.items()
        }
        if clave_destino and clave_destino in actuales:
            actuales[clave_destino] = codigo
        else:
            actuales["aviso.tono.continuidad"] = codigo

        self._recargar_combos_tonos(actuales)

        reproducir_tono_aviso(
            habilitado=True,
            tono=codigo,
            volumen=int(self.slider_volumen.value()),
        )

    def _accion_aplicar_tono_a_todos(self) -> None:
        combo_ref = self.combos_tonos.get("aviso.tono.continuidad")
        if combo_ref is None:
            return
        codigo = str(combo_ref.currentData() or "gotita")
        for combo in self.combos_tonos.values():
            idx = combo.findData(codigo)
            if idx >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(idx)
                combo.blockSignals(False)
        self._probar_tono_de_clave("aviso.tono.continuidad")

    def _accion_eliminar_audio_custom(self) -> None:
        personalizados = listar_sonidos_usuario()
        if not personalizados:
            QMessageBox.information(
                self,
                "Sin audios personalizados",
                "Aún no has subido archivos de sonido propios.",
            )
            return

        etiquetas = [etiq for _, etiq in personalizados]
        elegida, ok = QInputDialog.getItem(
            self,
            "Quitar audio personalizado",
            "Elige el sonido personalizado que deseas borrar:",
            etiquetas,
            0,
            False,
        )
        if not ok:
            return
        idx = etiquetas.index(elegida)
        codigo_a_borrar = personalizados[idx][0]
        if eliminar_sonido_personalizado(codigo_a_borrar):
            actuales = {
                c: (
                    TONOS_DEFECTO_POR_CLAVE[c]
                    if str(cb.currentData()) == codigo_a_borrar
                    else str(cb.currentData() or TONOS_DEFECTO_POR_CLAVE[c])
                )
                for c, cb in self.combos_tonos.items()
            }
            self._recargar_combos_tonos(actuales)
