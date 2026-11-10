"""Ventana principal moderna con navegación lateral, temas QSS, atajos de teclado
personalizables (desactivados por defecto) y sincronización con el mini-widget flotante.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
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
from ui.mini_widget import MiniWidgetCronometro, formatear_reloj_hms
from ui.pantallas.pantalla_cierre import PantallaCierre
from ui.pantallas.pantalla_configuracion import PantallaConfiguracion
from ui.pantallas.pantalla_estadisticas import PantallaEstadisticas
from ui.pantallas.pantalla_extra import PantallaExtra
from ui.pantallas.pantalla_historial import PantallaHistorial
from ui.pantallas.pantalla_hoy import PantallaHoy
from ui.pantallas.pantalla_planear import PantallaPlanear
from ui.pantallas.pantalla_reportes import PantallaReportes
from ui.temas import generar_qss


class VentanaPrincipal(QMainWindow):
    """Ventana principal de Control de Tiempos con barra lateral y páginas."""

    def __init__(self, bd: BaseDatos) -> None:
        super().__init__()
        self.bd = bd
        self.coordinador_recordatorios = None
        self._atajos_activos: list[QShortcut] = []

        self.setWindowTitle(f"{rutas.NOMBRE_VISIBLE} — Gente Util v{rutas.VERSION}")
        icono_corporativo = crear_icono_app()
        self.setWindowIcon(icono_corporativo)
        self.resize(1180, 740)

        # Mini-widget flotante siempre visible
        self.mini_widget = MiniWidgetCronometro(
            al_pausar=self._atajo_pausar,
            al_finalizar=self._atajo_finalizar,
            al_siguiente_pieza=self._atajo_siguiente_pieza,
        )
        self.mini_widget.setWindowIcon(icono_corporativo)

        contenedor = QWidget(self)
        layout_raiz = QHBoxLayout(contenedor)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        # Barra lateral de navegación
        sidebar = QFrame(contenedor)
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(242)
        col_nav = QVBoxLayout(sidebar)
        col_nav.setContentsMargins(14, 16, 14, 16)
        col_nav.setSpacing(4)

        # Bloque de marca corporativa mostrando literalmente el logo oficial de Gente Util S.A.
        marca = QFrame(sidebar)
        marca.setObjectName("marcaSidebar")
        col_marca = QVBoxLayout(marca)
        col_marca.setContentsMargins(6, 6, 6, 6)
        col_marca.setSpacing(2)

        lbl_logo = QLabel(marca)
        lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ruta_logo_oficial = rutas.carpeta_assets() / "logo_gente_util.png"
        if ruta_logo_oficial.is_file():
            pix_logo = QPixmap(str(ruta_logo_oficial)).scaled(
                192,
                73,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            lbl_logo.setPixmap(pix_logo)
        lbl_logo.setStyleSheet("background: transparent;")
        col_marca.addWidget(lbl_logo)
        col_nav.addWidget(marca)

        # Indicador de estado en vivo en la barra lateral
        self.lbl_estado_sidebar = QLabel("⚪ Sin actividad en curso", sidebar)
        self.lbl_estado_sidebar.setObjectName("chipEstadoSidebar")
        self.lbl_estado_sidebar.setWordWrap(True)
        col_nav.addWidget(self.lbl_estado_sidebar)

        self.grupo_nav = QButtonGroup(self)
        self.grupo_nav.setExclusive(True)

        lbl_sec_op = QLabel("OPERACIÓN DIARIA", sidebar)
        lbl_sec_op.setObjectName("seccionSidebar")
        col_nav.addWidget(lbl_sec_op)

        self.btn_nav_hoy = self._crear_boton_nav("🏠   Hoy · Cronómetro", 0, sidebar)
        self.btn_nav_planear = self._crear_boton_nav("📋   Planear el día", 1, sidebar)
        self.btn_nav_extra = self._crear_boton_nav("⚡   Actividad extra", 2, sidebar)
        self.btn_nav_cierre = self._crear_boton_nav("🏁   Cierre de jornada", 3, sidebar)
        for b in (
            self.btn_nav_hoy,
            self.btn_nav_planear,
            self.btn_nav_extra,
            self.btn_nav_cierre,
        ):
            col_nav.addWidget(b)

        lbl_sec_an = QLabel("ANÁLISIS Y REPORTES", sidebar)
        lbl_sec_an.setObjectName("seccionSidebar")
        col_nav.addWidget(lbl_sec_an)

        self.btn_nav_historial = self._crear_boton_nav("🗂   Historial", 4, sidebar)
        self.btn_nav_reportes = self._crear_boton_nav("📄   Reportes PDF", 5, sidebar)
        self.btn_nav_estadisticas = self._crear_boton_nav("📈   Estadísticas", 6, sidebar)
        for b in (
            self.btn_nav_historial,
            self.btn_nav_reportes,
            self.btn_nav_estadisticas,
        ):
            col_nav.addWidget(b)

        lbl_sec_sis = QLabel("SISTEMA", sidebar)
        lbl_sec_sis.setObjectName("seccionSidebar")
        col_nav.addWidget(lbl_sec_sis)

        self.btn_nav_config = self._crear_boton_nav("⚙   Configuración", 7, sidebar)
        col_nav.addWidget(self.btn_nav_config)

        col_nav.addStretch()

        self.btn_toggle_mini = QPushButton("🪟  Abrir Mini-ventana", sidebar)
        self.btn_toggle_mini.setCheckable(True)
        self.btn_toggle_mini.setCursor(Qt.CursorShape.PointingHandCursor)
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
            bd, al_cambiar_plan=self._al_actualizar_datos, parent=self.paginas
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

        layout_raiz.addWidget(sidebar)
        layout_raiz.addWidget(self.paginas, 1)
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

    def _crear_boton_nav(self, texto: str, indice: int, parent: QWidget) -> QPushButton:
        btn = QPushButton(texto, parent)
        btn.setCheckable(True)
        btn.setProperty("nav", True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.grupo_nav.addButton(btn, indice)
        return btn

    def cambiar_pagina(self, indice: int) -> None:
        self.paginas.setCurrentIndex(indice)
        widget = self.paginas.currentWidget()
        if hasattr(widget, "refrescar"):
            widget.refrescar()

    def aplicar_tema(self, codigo_tema: str, *, tamano_fuente_px: int = 13) -> None:
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
            tema_actual = usr.tema if usr and usr.tema else "gente_util"
            cfg = RepoConfiguracion(s)
            resolucion = cfg.obtener("graficos.resolucion", "1180x740") or "1180x740"
            modo_ventana = cfg.obtener("graficos.modo_ventana", "ventana") or "ventana"
            tam_fuente = cfg.obtener_int("graficos.tamano_fuente", 13)
            mini_tamano = cfg.obtener("graficos.mini_tamano", "normal") or "normal"
            mini_opacidad = cfg.obtener_int("graficos.mini_opacidad", 95)

        self.aplicar_tema(tema_actual, tamano_fuente_px=tam_fuente)
        self.mini_widget.aplicar_preferencias_visuales(mini_tamano, mini_opacidad)

        try:
            ancho_s, alto_s = resolucion.lower().split("x")
            ancho, alto = max(900, int(ancho_s)), max(620, int(alto_s))
        except Exception:
            ancho, alto = 1180, 740

        if modo_ventana == "pantalla_completa":
            if self.isVisible():
                self.showFullScreen()
            else:
                self.setWindowState(Qt.WindowState.WindowFullScreen)
        elif modo_ventana == "maximizada":
            if self.isVisible():
                self.showMaximized()
            else:
                self.setWindowState(Qt.WindowState.WindowMaximized)
        else:
            if self.isMaximized() or self.isFullScreen():
                self.showNormal()
            else:
                self.setWindowState(Qt.WindowState.WindowNoState)
            self.resize(ancho, alto)

    def mostrar_ocultar_mini_widget(self, visible: bool) -> None:
        self.btn_toggle_mini.blockSignals(True)
        self.btn_toggle_mini.setChecked(visible)
        self.btn_toggle_mini.setText(
            "🪟  Ocultar Mini-ventana" if visible else "🪟  Abrir Mini-ventana"
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
        if nombre:
            corto = nombre if len(nombre) <= 22 else nombre[:21] + "…"
            self.lbl_estado_sidebar.setText(f"🟢 {corto}\n⏱ {formatear_reloj_hms(seg)}")
        else:
            self.lbl_estado_sidebar.setText("⚪ Sin actividad en curso")

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
                "Atajos de teclado: desactivados\n(puedes asignarlos en ⚙ Configuración)"
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
