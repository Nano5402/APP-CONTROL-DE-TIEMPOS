"""Ventana principal moderna con navegación lateral, temas QSS, atajos de teclado
personalizables (desactivados por defecto) y sincronización con el mini-widget flotante.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QKeySequence, QMouseEvent, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from config import rutas
from data.db import BaseDatos
from data.models import Usuario
from data.repositorios.configuracion import RepoConfiguracion
from ui.bandeja import crear_icono_app
from ui.iconos import configurar_boton, obtener_icono
from ui.mini_widget import MiniWidgetCronometro, formatear_reloj_hms
from ui.pantallas.pantalla_cierre import PantallaCierre
from ui.pantallas.pantalla_configuracion import PantallaConfiguracion
from ui.pantallas.pantalla_estadisticas import PantallaEstadisticas
from ui.pantallas.pantalla_extra import PantallaExtra
from ui.pantallas.pantalla_historial import PantallaHistorial
from ui.pantallas.pantalla_hoy import PantallaHoy
from ui.pantallas.pantalla_planear import PantallaPlanear
from ui.pantallas.pantalla_reportes import PantallaReportes
from ui.temas import TEMAS, generar_qss


class BarraTituloSuperior(QFrame):
    """Barra de título superior limpia y minimalista para el modo ventana sin bordes (Frameless).

    Ofrece:
    - Arrastre fluido de la ventana con el ratón.
    - Doble clic para maximizar / restaurar.
    - Indicador sutil de actividad en curso o en espera.
    - Controles de minimizar, maximizar/restaurar y cerrar.
    """

    def __init__(self, ventana: VentanaPrincipal) -> None:
        super().__init__(ventana)
        self.ventana = ventana
        self._pos_arrastre: QPoint | None = None
        self.setObjectName("barraTitulo")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(10)

        # 1. Identidad corporativa
        self.lbl_logo = QLabel(self)
        pix = crear_icono_app().pixmap(18, 18)
        self.lbl_logo.setPixmap(pix)

        self.lbl_titulo = QLabel("Gente Útil — Control de Tiempos", self)
        self.lbl_titulo.setObjectName("tituloBarraApp")

        self.lbl_status_header = QLabel("○ En espera", self)
        self.lbl_status_header.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 11px;")

        layout.addWidget(self.lbl_logo)
        layout.addWidget(self.lbl_titulo)
        layout.addSpacing(6)
        layout.addWidget(self.lbl_status_header)

        layout.addStretch(1)

        # 2. Botones de ventana (Minimizar, Maximizar/Restaurar, Cerrar)
        self.btn_min = QPushButton("—", self)
        self.btn_min.setObjectName("btnMinimizar")
        self.btn_min.setToolTip("Minimizar")
        self.btn_min.clicked.connect(self.ventana.showMinimized)

        self.btn_max = QPushButton("🗖", self)
        self.btn_max.setObjectName("btnMaximizar")
        self.btn_max.setToolTip("Maximizar")
        self.btn_max.clicked.connect(self.ventana.alternar_maximizar)

        self.btn_close = QPushButton("✕", self)
        self.btn_close.setObjectName("btnCerrar")
        self.btn_close.setToolTip("Cerrar")
        self.btn_close.clicked.connect(self.ventana.close)

        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(b)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pos_arrastre = event.globalPosition().toPoint() - self.ventana.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pos_arrastre is not None and event.buttons() == Qt.MouseButton.LeftButton:
            if not self.ventana.isMaximized() and not self.ventana.isFullScreen():
                self.ventana.move(event.globalPosition().toPoint() - self._pos_arrastre)
                event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._pos_arrastre = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.ventana.alternar_maximizar()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def actualizar_icono_maximizar(self) -> None:
        if self.ventana.isMaximized():
            self.btn_max.setText("❐")
            self.btn_max.setToolTip("Restaurar tamaño")
        else:
            self.btn_max.setText("🗖")
            self.btn_max.setToolTip("Maximizar")

    def actualizar_estado(self, nombre_activo: str | None, segundos: int) -> None:
        if nombre_activo:
            corto = nombre_activo if len(nombre_activo) <= 24 else nombre_activo[:23] + "…"
            self.lbl_status_header.setText(f"● {corto}")
            self.lbl_status_header.setStyleSheet("color: #00DF81; font-weight: 700; font-size: 11px;")
        else:
            self.lbl_status_header.setText("○ En espera")
            self.lbl_status_header.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 11px;")


class VentanaPrincipal(QMainWindow):
    """Ventana principal de Control de Tiempos con barra lateral y páginas."""

    def __init__(self, bd: BaseDatos) -> None:
        super().__init__()
        self.bd = bd
        self.coordinador_recordatorios = None
        self.icono_bandeja = None
        self._atajos_activos: list[QShortcut] = []
        self._resolucion_configurada = "1180x740"
        self._modo_ventana_actual = "ventana"

        self.setWindowTitle(f"{rutas.NOMBRE_VISIBLE} — Gente Util v{rutas.VERSION}")
        icono_corporativo = crear_icono_app()
        self.setWindowIcon(icono_corporativo)
        self.resize(1180, 740)

        # Atajos globales de pantalla completa (F11 y Escape)
        self.atajo_f11 = QShortcut(QKeySequence("F11"), self)
        self.atajo_f11.activated.connect(self.alternar_pantalla_completa)
        self.atajo_esc = QShortcut(QKeySequence("Escape"), self)
        self.atajo_esc.activated.connect(self._salir_pantalla_completa_si_activa)

        # Mini-widget flotante siempre visible
        self.mini_widget = MiniWidgetCronometro(
            al_pausar=self._atajo_pausar,
            al_finalizar=self._atajo_finalizar,
            al_siguiente_pieza=self._atajo_siguiente_pieza,
        )
        self.mini_widget.setWindowIcon(icono_corporativo)

        contenedor = QWidget(self)
        layout_raiz = QVBoxLayout(contenedor)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        # Barra de título superior estilo lanzador (Epic Games / Frameless)
        self.barra_titulo = BarraTituloSuperior(self)
        layout_raiz.addWidget(self.barra_titulo)

        layout_cuerpo = QHBoxLayout()
        layout_cuerpo.setContentsMargins(0, 0, 0, 0)
        layout_cuerpo.setSpacing(0)

        # Barra lateral de navegación
        sidebar = QFrame(contenedor)
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)
        col_nav = QVBoxLayout(sidebar)
        col_nav.setContentsMargins(12, 12, 12, 12)
        col_nav.setSpacing(4)

        # Bloque de marca corporativa
        marca = QFrame(sidebar)
        marca.setObjectName("marcaSidebar")
        col_marca = QVBoxLayout(marca)
        col_marca.setContentsMargins(10, 8, 10, 8)
        col_marca.setSpacing(2)
        lbl_app = QLabel("GENTE UTIL", marca)
        lbl_app.setObjectName("tituloSidebar")
        lbl_sub = QLabel(f"Control de Tiempos · v{rutas.VERSION}", marca)
        lbl_sub.setObjectName("subtituloSidebar")
        col_marca.addWidget(lbl_app)
        col_marca.addWidget(lbl_sub)
        col_nav.addWidget(marca)

        # Indicador de estado en vivo en la barra lateral
        self.lbl_estado_sidebar = QLabel("Sin actividad en curso", sidebar)
        self.lbl_estado_sidebar.setObjectName("chipEstadoSidebar")
        self.lbl_estado_sidebar.setWordWrap(True)
        col_nav.addWidget(self.lbl_estado_sidebar)

        self.grupo_nav = QButtonGroup(self)
        self.grupo_nav.setExclusive(True)

        scroll_nav = QScrollArea(sidebar)
        scroll_nav.setWidgetResizable(True)
        scroll_nav.setFrameShape(QFrame.Shape.NoFrame)
        scroll_nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_nav.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }")
        cont_nav_btns = QWidget(scroll_nav)
        col_btns = QVBoxLayout(cont_nav_btns)
        col_btns.setContentsMargins(0, 2, 0, 2)
        col_btns.setSpacing(3)

        lbl_sec_op = QLabel("OPERACIÓN DIARIA", cont_nav_btns)
        lbl_sec_op.setObjectName("seccionSidebar")
        col_btns.addWidget(lbl_sec_op)

        self.btn_nav_hoy = self._crear_boton_nav("Hoy · Cronómetro", 0, "clock", cont_nav_btns)
        self.btn_nav_planear = self._crear_boton_nav("Planear el día", 1, "clipboard", cont_nav_btns)
        self.btn_nav_extra = self._crear_boton_nav("Actividad extra", 2, "zap", cont_nav_btns)
        self.btn_nav_cierre = self._crear_boton_nav("Cierre de jornada", 3, "flag", cont_nav_btns)
        for b in (
            self.btn_nav_hoy,
            self.btn_nav_planear,
            self.btn_nav_extra,
            self.btn_nav_cierre,
        ):
            col_btns.addWidget(b)

        lbl_sec_an = QLabel("ANÁLISIS Y REPORTES", cont_nav_btns)
        lbl_sec_an.setObjectName("seccionSidebar")
        col_btns.addWidget(lbl_sec_an)

        self.btn_nav_historial = self._crear_boton_nav("Historial", 4, "archive", cont_nav_btns)
        self.btn_nav_reportes = self._crear_boton_nav("Reportes PDF", 5, "file-text", cont_nav_btns)
        self.btn_nav_estadisticas = self._crear_boton_nav("Estadísticas", 6, "bar-chart", cont_nav_btns)
        for b in (
            self.btn_nav_historial,
            self.btn_nav_reportes,
            self.btn_nav_estadisticas,
        ):
            col_btns.addWidget(b)

        lbl_sec_sis = QLabel("SISTEMA", cont_nav_btns)
        lbl_sec_sis.setObjectName("seccionSidebar")
        col_btns.addWidget(lbl_sec_sis)

        self.btn_nav_config = self._crear_boton_nav("Configuración", 7, "settings", cont_nav_btns)
        col_btns.addWidget(self.btn_nav_config)
        col_btns.addStretch()

        scroll_nav.setWidget(cont_nav_btns)
        col_nav.addWidget(scroll_nav, 1)

        self.btn_toggle_mini = QPushButton("  Mini-ventana flotante", sidebar)
        self.btn_toggle_mini.setCheckable(True)
        self.btn_toggle_mini.setProperty("compact", True)
        self.btn_toggle_mini.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(self.btn_toggle_mini, "window", color="#CBD5E1", tamano=15)
        self.btn_toggle_mini.toggled.connect(self.mostrar_ocultar_mini_widget)
        col_nav.addWidget(self.btn_toggle_mini)

        self.lbl_atajos = QLabel("", sidebar)
        self.lbl_atajos.setWordWrap(True)
        self.lbl_atajos.setStyleSheet("color: #94A3B8; font-size: 11px; padding: 6px 4px 0 4px;")
        col_nav.addWidget(self.lbl_atajos)

        # Contenedor de páginas
        self.paginas = QStackedWidget(contenedor)
        self.pantalla_hoy = PantallaHoy(
            bd, al_cambiar_estado=self._sincronizar_vistas, parent=self.paginas
        )
        self.pantalla_planear = PantallaPlanear(
            bd,
            al_cambiar_plan=self._al_actualizar_datos,
            al_ir_a_hoy=self._ir_a_hoy_y_refrescar,
            parent=self.paginas,
        )
        self.pantalla_extra = PantallaExtra(
            bd, al_crear_extra=self._ir_a_hoy_y_refrescar, parent=self.paginas
        )
        self.pantalla_cierre = PantallaCierre(
            bd, al_cerrar_jornada=self._al_actualizar_datos, parent=self.paginas
        )
        self.pantalla_historial = PantallaHistorial(bd, parent=self.paginas)
        self.pantalla_reportes = PantallaReportes(bd, parent=self.paginas)
        self.pantalla_estadisticas = PantallaEstadisticas(bd, parent=self.paginas)
        self.pantalla_config = PantallaConfiguracion(
            bd,
            al_cambiar_tema=self.aplicar_tema,
            al_cambiar_atajos=self.recargar_atajos,
            al_cambiar_graficos=self.aplicar_graficos,
            parent=self.paginas,
        )

        self.paginas.addWidget(self.pantalla_hoy)
        self.paginas.addWidget(self.pantalla_planear)
        self.paginas.addWidget(self.pantalla_extra)
        self.paginas.addWidget(self.pantalla_cierre)
        self.paginas.addWidget(self.pantalla_historial)
        self.paginas.addWidget(self.pantalla_reportes)
        self.paginas.addWidget(self.pantalla_estadisticas)
        self.paginas.addWidget(self.pantalla_config)

        # Evita que etiquetas largas fuercen un ancho mínimo mayor a la pantalla del portátil
        self.paginas.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        self.paginas.setMinimumSize(640, 440)
        self.setMinimumSize(900, 580)
        for lbl in self.paginas.findChildren(QLabel):
            if len(lbl.text()) > 32:
                lbl.setWordWrap(True)

        layout_cuerpo.addWidget(sidebar)
        layout_cuerpo.addWidget(self.paginas, 1)
        layout_raiz.addLayout(layout_cuerpo, 1)
        self.setCentralWidget(contenedor)

        self.grupo_nav.idClicked.connect(self.cambiar_pagina)
        self.btn_nav_hoy.setChecked(True)

        # Atajos de teclado personalizados (desactivados por defecto)
        self.recargar_atajos()

        # Temporizador de 1 segundo para el cronómetro en vivo y el mini-widget
        self.timer_reloj = QTimer(self)
        self.timer_reloj.setInterval(1000)
        self.timer_reloj.timeout.connect(self._tick_reloj)
        self.timer_reloj.start()

        # Aplicar el tema, resolución y preferencias gráficas guardadas por el usuario
        self.aplicar_graficos()
        self._tick_reloj()

    def _crear_boton_nav(
        self, texto: str, indice: int, icono_nombre: str, parent: QWidget
    ) -> QPushButton:
        btn = QPushButton(f"  {texto}", parent)
        btn.setCheckable(True)
        btn.setProperty("nav", True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        configurar_boton(btn, icono_nombre, color="#CBD5E1", tamano=17)
        self.grupo_nav.addButton(btn, indice)
        return btn

    def cambiar_pagina(self, indice: int) -> None:
        self.paginas.setCurrentIndex(indice)
        widget = self.paginas.currentWidget()
        if hasattr(widget, "refrescar"):
            widget.refrescar()

    def aplicar_tema(self, codigo_tema: str, *, tamano_fuente_px: int = 13) -> None:
        self._tema_actual = codigo_tema
        qss = generar_qss(codigo_tema, tamano_fuente_px=tamano_fuente_px)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)
        else:
            self.setStyleSheet(qss)
        self.mini_widget.setStyleSheet(qss)

    def aplicar_graficos(self) -> None:
        """Aplica tema, tamaño de letra, resolución, modo de ventana y mini-ventana."""
        with self.bd.sesion() as s:
            usr = s.scalar(select(Usuario).limit(1))
            tema_actual = usr.tema if usr and usr.tema and usr.tema in TEMAS else "gente_util"
            cfg = RepoConfiguracion(s)
            resolucion = cfg.obtener("graficos.resolucion", "1180x740") or "1180x740"
            modo_ventana = cfg.obtener("graficos.modo_ventana", "ventana") or "ventana"
            tam_fuente = cfg.obtener_int("graficos.tamano_fuente", 13)
            mini_tamano = cfg.obtener("graficos.mini_tamano", "normal") or "normal"
            mini_opacidad = cfg.obtener_int("graficos.mini_opacidad", 95)

        self._resolucion_configurada = resolucion
        self.aplicar_tema(tema_actual, tamano_fuente_px=tam_fuente)
        self.mini_widget.aplicar_preferencias_visuales(mini_tamano, mini_opacidad)
        self.cambiar_modo_ventana(modo_ventana, guardar=False)

    def _aplicar_tamano_configurado(self) -> None:
        try:
            ancho_s, alto_s = (self._resolucion_configurada or "1180x740").lower().split("x")
            ancho, alto = max(900, int(ancho_s)), max(580, int(alto_s))
        except Exception:
            ancho, alto = 1180, 740
        self.resize(ancho, alto)

    def cambiar_modo_ventana(self, modo: str, guardar: bool = True) -> None:
        """Aplica y conmuta los modos configurados: 'ventana', 'sin_bordes', 'pantalla_completa' o 'maximizada'."""
        self._modo_ventana_actual = modo
        if guardar:
            with self.bd.sesion() as s:
                RepoConfiguracion(s).guardar("graficos.modo_ventana", modo)

        was_visible = self.isVisible()

        if modo == "pantalla_completa":
            if hasattr(self, "barra_titulo"):
                self.barra_titulo.setVisible(False)
            self.showFullScreen()
        elif modo == "sin_bordes":
            if self.isFullScreen():
                self.showNormal()
            flags = self.windowFlags()
            if not (flags & Qt.WindowType.FramelessWindowHint):
                self.setWindowFlags(flags | Qt.WindowType.FramelessWindowHint)
            if hasattr(self, "barra_titulo"):
                self.barra_titulo.setVisible(True)
                self.barra_titulo.actualizar_icono_maximizar()
            if was_visible:
                self.show()
            self._aplicar_tamano_configurado()
        elif modo == "maximizada":
            flags = self.windowFlags()
            if flags & Qt.WindowType.FramelessWindowHint:
                self.setWindowFlags(flags & ~Qt.WindowType.FramelessWindowHint)
            if self.isFullScreen():
                self.showNormal()
            if hasattr(self, "barra_titulo"):
                self.barra_titulo.setVisible(False)
            self.showMaximized()
        else:  # "ventana"
            flags = self.windowFlags()
            if flags & Qt.WindowType.FramelessWindowHint:
                self.setWindowFlags(flags & ~Qt.WindowType.FramelessWindowHint)
            if hasattr(self, "barra_titulo"):
                self.barra_titulo.setVisible(False)
            if self.isFullScreen() or self.isMaximized():
                self.showNormal()
            elif was_visible:
                self.show()
            self._aplicar_tamano_configurado()

    def alternar_maximizar(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        elif self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        if hasattr(self, "barra_titulo"):
            self.barra_titulo.actualizar_icono_maximizar()

    def alternar_pantalla_completa(self) -> None:
        if self.isFullScreen():
            with self.bd.sesion() as s:
                previo = RepoConfiguracion(s).obtener("graficos.modo_ventana", "ventana") or "ventana"
                if previo == "pantalla_completa":
                    previo = "ventana"
            self.cambiar_modo_ventana(previo)
        else:
            self.cambiar_modo_ventana("pantalla_completa")

    def _salir_pantalla_completa_si_activa(self) -> None:
        if self.isFullScreen():
            self.alternar_pantalla_completa()

    def mostrar_ocultar_mini_widget(self, visible: bool) -> None:
        self.btn_toggle_mini.blockSignals(True)
        self.btn_toggle_mini.setChecked(visible)
        self.btn_toggle_mini.setText(
            "  Ocultar Mini-ventana" if visible else "  Mini-ventana flotante"
        )
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
        self.mini_widget.actualizar_estado(
            nombre, seg, self.pantalla_hoy.nombre_siguiente_sugerido
        )
        if hasattr(self, "barra_titulo"):
            self.barra_titulo.actualizar_estado(nombre, seg)
        if nombre:
            corto = nombre if len(nombre) <= 22 else nombre[:21] + "…"
            self.lbl_estado_sidebar.setText(f"EN CURSO:\n{corto}\n{formatear_reloj_hms(seg)}")
        else:
            self.lbl_estado_sidebar.setText("Sin actividad en curso")

    def _sincronizar_vistas(self) -> None:
        self._tick_reloj()

    def _al_actualizar_datos(self) -> None:
        self.pantalla_hoy.refrescar()

    def _ir_a_hoy_y_refrescar(self) -> None:
        self.btn_nav_hoy.setChecked(True)
        self.cambiar_pagina(0)

    # ------------------------------------------------------------------
    # Atajos de teclado personalizables (RF-12)
    # ------------------------------------------------------------------

    def recargar_atajos(self) -> None:
        """Limpia y vuelve a registrar únicamente los atajos que el usuario haya definido."""
        for sc in self._atajos_activos:
            sc.setEnabled(False)
            sc.setKey(QKeySequence())
            sc.deleteLater()
        self._atajos_activos.clear()

        with self.bd.sesion() as s:
            cfg = RepoConfiguracion(s)
            k_ini = (cfg.obtener("atajo.iniciar_pausar", "") or "").strip()
            k_fin = (cfg.obtener("atajo.finalizar", "") or "").strip()
            k_sig = (cfg.obtener("atajo.siguiente_pieza", "") or "").strip()
            k_mini = (cfg.obtener("atajo.mini_ventana", "") or "").strip()

        resumen_lineas: list[str] = []

        def _registrar(secuencia_txt: str, etiqueta: str, callback) -> None:
            if not secuencia_txt:
                return
            seq = QKeySequence(secuencia_txt)
            if seq.isEmpty():
                return
            sc = QShortcut(seq, self)
            sc.activated.connect(callback)
            self._atajos_activos.append(sc)
            resumen_lineas.append(f"{seq.toString()}: {etiqueta}")

        _registrar(k_ini, "Iniciar/Pausar", self._atajo_iniciar_o_pausar)
        _registrar(k_fin, "Finalizar", self._atajo_finalizar)
        _registrar(k_sig, "Fin + Siguiente", self._atajo_siguiente_pieza)
        _registrar(
            k_mini,
            "Mini-ventana",
            lambda: self.mostrar_ocultar_mini_widget(not self.mini_widget.isVisible()),
        )

        if resumen_lineas:
            self.lbl_atajos.setText("Atajos activos:\n" + "\n".join(resumen_lineas))
        else:
            self.lbl_atajos.setText(
                "Atajos de teclado: desactivados\n(puedes asignarlos en Configuración)"
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

    # ------------------------------------------------------------------
    # Cierre seguro de la aplicación (evita procesos y sonidos zombis)
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Maneja el evento de cierre al hacer clic en la «X».

        Si la opción 'minimizar_al_cerrar' no está activa (por defecto),
        cierra y finaliza la aplicación por completo, deteniendo timers,
        avisos sonoros y ocultando el icono de la bandeja.
        """
        from data.repositorios.configuracion import RepoConfiguracion
        from services.cronometro import ServicioCronometro

        with self.bd.sesion() as s:
            cfg = RepoConfiguracion(s)
            minimizar_al_cerrar = cfg.obtener_bool("sistema.minimizar_al_cerrar", False)
            cron = ServicioCronometro(s)
            activa = cron.actividad_en_curso()

        # Si el usuario configuró explícitamente mantener en segundo plano
        if (
            minimizar_al_cerrar
            and hasattr(self, "icono_bandeja")
            and self.icono_bandeja
            and self.icono_bandeja.isSystemTrayAvailable()
        ):
            event.ignore()
            self.hide()
            self.icono_bandeja.showMessage(
                rutas.NOMBRE_VISIBLE,
                "La aplicación sigue activa en la bandeja del reloj. Para salir por completo, clic derecho y «Salir por completo».",
            )
            return

        # Si hay una actividad en curso con el cronómetro corriendo
        if activa is not None:
            from PySide6.QtWidgets import QMessageBox

            msg = QMessageBox(self)
            msg.setWindowTitle("Actividad en curso")
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setText(f"Tienes la actividad «{activa.nombre}» en curso.")
            msg.setInformativeText(
                "¿Deseas pausar la actividad y salir por completo, o minimizar la app en la bandeja del reloj?"
            )
            btn_salir = msg.addButton(
                "Pausar y Salir por completo", QMessageBox.ButtonRole.AcceptRole
            )
            btn_min = msg.addButton(
                "Minimizar a la bandeja", QMessageBox.ButtonRole.ActionRole
            )
            btn_cancel = msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
            msg.setDefaultButton(btn_salir)
            msg.exec()

            clic = msg.clickedButton()
            if clic == btn_cancel:
                event.ignore()
                return
            if clic == btn_min:
                event.ignore()
                self.hide()
                if (
                    hasattr(self, "icono_bandeja")
                    and self.icono_bandeja
                    and self.icono_bandeja.isSystemTrayAvailable()
                ):
                    self.icono_bandeja.showMessage(
                        rutas.NOMBRE_VISIBLE,
                        "El cronómetro sigue activo en segundo plano en la bandeja del reloj.",
                    )
                return

            # Si eligió salir por completo con actividad en curso, la pausamos de forma limpia
            with self.bd.sesion() as s:
                cron = ServicioCronometro(s)
                activa_ahora = cron.actividad_en_curso()
                if activa_ahora is not None:
                    cron.pausar(activa_ahora, motivo="Cierre de la aplicación")

        # Cierre definitivo: detener timers, audio, ocultar bandeja y cerrar proceso
        from ui.sonido import detener_sonidos

        if hasattr(self, "coordinador_recordatorios") and self.coordinador_recordatorios:
            self.coordinador_recordatorios.detener()
        if hasattr(self, "timer_reloj") and self.timer_reloj:
            self.timer_reloj.stop()
        detener_sonidos()
        if hasattr(self, "mini_widget") and self.mini_widget:
            self.mini_widget.close()
        if hasattr(self, "icono_bandeja") and self.icono_bandeja:
            self.icono_bandeja.hide()

        event.accept()
        QApplication.quit()
