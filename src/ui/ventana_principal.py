"""Ventana principal moderna con navegación lateral, temas QSS, atajos de teclado
y sincronización con el mini-widget flotante (Fase 5 — sección 10 del plan).
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from config import rutas
from data.db import BaseDatos
from data.models import Usuario
from ui.mini_widget import MiniWidgetCronometro
from ui.pantallas.pantalla_cierre import PantallaCierre
from ui.pantallas.pantalla_configuracion import PantallaConfiguracion
from ui.pantallas.pantalla_estadisticas import PantallaEstadisticas
from ui.pantallas.pantalla_extra import PantallaExtra
from ui.pantallas.pantalla_historial import PantallaHistorial
from ui.pantallas.pantalla_hoy import PantallaHoy
from ui.pantallas.pantalla_planear import PantallaPlanear
from ui.temas import generar_qss


class VentanaPrincipal(QMainWindow):
    """Ventana principal de Control de Tiempos con barra lateral y páginas."""

    def __init__(self, bd: BaseDatos) -> None:
        super().__init__()
        self.bd = bd
        self.coordinador_recordatorios = None

        self.setWindowTitle(f"{rutas.NOMBRE_VISIBLE} — v{rutas.VERSION}")
        self.resize(1120, 700)

        # Mini-widget flotante siempre visible
        self.mini_widget = MiniWidgetCronometro(
            al_pausar=self._atajo_pausar,
            al_finalizar=self._atajo_finalizar,
            al_siguiente_pieza=self._atajo_siguiente_pieza,
        )

        contenedor = QWidget(self)
        layout_raiz = QHBoxLayout(contenedor)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        # Barra lateral de navegación
        sidebar = QFrame(contenedor)
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        col_nav = QVBoxLayout(sidebar)
        col_nav.setContentsMargins(14, 18, 14, 18)
        col_nav.setSpacing(6)

        lbl_app = QLabel("⏱ Control de Tiempos", sidebar)
        lbl_app.setObjectName("tituloSidebar")
        col_nav.addWidget(lbl_app)

        self.grupo_nav = QButtonGroup(self)
        self.grupo_nav.setExclusive(True)

        self.btn_nav_hoy = self._crear_boton_nav("🏠  Hoy (Cronómetro)", 0, sidebar)
        self.btn_nav_planear = self._crear_boton_nav("📋  Planear día", 1, sidebar)
        self.btn_nav_extra = self._crear_boton_nav("⚡  Actividad extra", 2, sidebar)
        self.btn_nav_cierre = self._crear_boton_nav("🔒  Cierre de jornada", 3, sidebar)
        self.btn_nav_historial = self._crear_boton_nav("🗂  Historial", 4, sidebar)
        self.btn_nav_estadisticas = self._crear_boton_nav("📈  Estadísticas", 5, sidebar)
        self.btn_nav_config = self._crear_boton_nav("⚙  Configuración", 6, sidebar)

        for b in (
            self.btn_nav_hoy,
            self.btn_nav_planear,
            self.btn_nav_extra,
            self.btn_nav_cierre,
            self.btn_nav_historial,
            self.btn_nav_estadisticas,
            self.btn_nav_config,
        ):
            col_nav.addWidget(b)

        col_nav.addStretch()

        self.btn_toggle_mini = QPushButton("🪟 Mini-ventana (Ctrl+M)", sidebar)
        self.btn_toggle_mini.setCheckable(True)
        self.btn_toggle_mini.toggled.connect(self.mostrar_ocultar_mini_widget)
        col_nav.addWidget(self.btn_toggle_mini)

        lbl_atajos = QLabel(
            "Atajos:\n"
            "Ctrl+Espacio: Iniciar/Pausar\n"
            "Ctrl+Shift+F: Finalizar\n"
            "Ctrl+Shift+S: Fin + Siguiente\n"
            "Ctrl+M: Mini-ventana",
            sidebar,
        )
        lbl_atajos.setStyleSheet("color: #94A3B8; font-size: 11px; padding-top: 6px;")
        col_nav.addWidget(lbl_atajos)

        # Contenedor de páginas
        self.paginas = QStackedWidget(contenedor)
        self.pantalla_hoy = PantallaHoy(
            bd, al_cambiar_estado=self._sincronizar_vistas, parent=self.paginas
        )
        self.pantalla_planear = PantallaPlanear(
            bd, al_cambiar_plan=self._al_actualizar_datos, parent=self.paginas
        )
        self.pantalla_extra = PantallaExtra(
            bd, al_crear_extra=self._ir_a_hoy_y_refrescar, parent=self.paginas
        )
        self.pantalla_cierre = PantallaCierre(
            bd, al_cerrar_jornada=self._al_actualizar_datos, parent=self.paginas
        )
        self.pantalla_historial = PantallaHistorial(bd, parent=self.paginas)
        self.pantalla_estadisticas = PantallaEstadisticas(bd, parent=self.paginas)
        self.pantalla_config = PantallaConfiguracion(
            bd, al_cambiar_tema=self.aplicar_tema, parent=self.paginas
        )

        self.paginas.addWidget(self.pantalla_hoy)
        self.paginas.addWidget(self.pantalla_planear)
        self.paginas.addWidget(self.pantalla_extra)
        self.paginas.addWidget(self.pantalla_cierre)
        self.paginas.addWidget(self.pantalla_historial)
        self.paginas.addWidget(self.pantalla_estadisticas)
        self.paginas.addWidget(self.pantalla_config)

        layout_raiz.addWidget(sidebar)
        layout_raiz.addWidget(self.paginas, 1)
        self.setCentralWidget(contenedor)

        self.grupo_nav.idClicked.connect(self.cambiar_pagina)
        self.btn_nav_hoy.setChecked(True)

        # Atajos de teclado (RF-12)
        self._configurar_atajos()

        # Temporizador de 1 segundo para el cronómetro en vivo y el mini-widget
        self.timer_reloj = QTimer(self)
        self.timer_reloj.setInterval(1000)
        self.timer_reloj.timeout.connect(self._tick_reloj)
        self.timer_reloj.start()

        # Aplicar el tema guardado por el usuario
        with self.bd.sesion() as s:
            usr = s.scalar(select(Usuario).limit(1))
            tema_inicial = usr.tema if usr and usr.tema else "claro"
        self.aplicar_tema(tema_inicial)

    def _crear_boton_nav(self, texto: str, indice: int, parent: QWidget) -> QPushButton:
        btn = QPushButton(texto, parent)
        btn.setCheckable(True)
        btn.setProperty("nav", True)
        self.grupo_nav.addButton(btn, indice)
        return btn

    def cambiar_pagina(self, indice: int) -> None:
        self.paginas.setCurrentIndex(indice)
        widget = self.paginas.currentWidget()
        if hasattr(widget, "refrescar"):
            widget.refrescar()

    def aplicar_tema(self, codigo_tema: str) -> None:
        qss = generar_qss(codigo_tema)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)
        else:
            self.setStyleSheet(qss)
        self.mini_widget.setStyleSheet(qss)

    def mostrar_ocultar_mini_widget(self, visible: bool) -> None:
        self.btn_toggle_mini.blockSignals(True)
        self.btn_toggle_mini.setChecked(visible)
        self.btn_toggle_mini.blockSignals(False)
        if visible:
            self._tick_reloj()
            self.mini_widget.show()
            self.mini_widget.raise_()
        else:
            self.mini_widget.hide()

    def _tick_reloj(self) -> None:
        if not hasattr(self, "pantalla_hoy"):
            return
        nombre, seg = self.pantalla_hoy.actualizar_reloj_en_vivo()
        self.mini_widget.actualizar_estado(nombre, seg)

    def _sincronizar_vistas(self) -> None:
        self._tick_reloj()

    def _al_actualizar_datos(self) -> None:
        self.pantalla_hoy.refrescar()

    def _ir_a_hoy_y_refrescar(self) -> None:
        self.btn_nav_hoy.setChecked(True)
        self.cambiar_pagina(0)

    # ------------------------------------------------------------------
    # Atajos de teclado (RF-12)
    # ------------------------------------------------------------------

    def _configurar_atajos(self) -> None:
        sc_iniciar_pausar = QShortcut(QKeySequence("Ctrl+Space"), self)
        sc_iniciar_pausar.activated.connect(self._atajo_iniciar_o_pausar)

        sc_finalizar = QShortcut(QKeySequence("Ctrl+Shift+F"), self)
        sc_finalizar.activated.connect(self._atajo_finalizar)

        sc_siguiente = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        sc_siguiente.activated.connect(self._atajo_siguiente_pieza)

        sc_mini = QShortcut(QKeySequence("Ctrl+M"), self)
        sc_mini.activated.connect(
            lambda: self.mostrar_ocultar_mini_widget(not self.mini_widget.isVisible())
        )

    def _atajo_iniciar_o_pausar(self) -> None:
        nombre, _ = self.pantalla_hoy.actualizar_reloj_en_vivo()
        if nombre:
            self.pantalla_hoy.accion_pausar_activa()
        else:
            self.pantalla_hoy.accion_iniciar_seleccionada()

    def _atajo_pausar(self) -> None:
        self.pantalla_hoy.accion_pausar_activa()

    def _atajo_finalizar(self) -> None:
        self.pantalla_hoy.accion_finalizar_activa()

    def _atajo_siguiente_pieza(self) -> None:
        self.pantalla_hoy.accion_finalizar_y_siguiente()
