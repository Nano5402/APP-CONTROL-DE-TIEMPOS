"""Temas visuales modernos con estética Glassmorphism corporativa (RF-09, RNF-06).

Incluye:
- Soporte e inicialización automática de la fuente tipográfica Montserrat.
- Efecto Glassmorphism refinado: superficies translúcidas (frosted glass),
  resplandores sutiles en bordes superiores, degradados fluidos y sombras suaves.
- Cuatro paletas de color ejecutivas:
  * ``gente_util``: Identidad Gente Util (#003D95) con azul marino profundo y acentos ámbar.
  * ``claro``: Cristal frosted blanco con acentos azul real.
  * ``oscuro``: Glassmorphism grafito y azul medianoche de alto confort visual.
  * ``pizarra``: Slate glass relajante para jornadas extensas de diseño.
"""

from __future__ import annotations

from dataclasses import dataclass


def cargar_fuente_montserrat() -> bool:
    """Carga los archivos TrueType de Montserrat en QFontDatabase si están disponibles."""
    from PySide6.QtGui import QFontDatabase
    from config import rutas

    carpeta = rutas.carpeta_assets() / "fonts"
    cargada = False
    for archivo in ("Montserrat-Variable.ttf", "Montserrat-Italic-Variable.ttf"):
        ruta = carpeta / archivo
        if ruta.is_file():
            id_f = QFontDatabase.addApplicationFont(str(ruta))
            if id_f >= 0:
                cargada = True
    return cargada


@dataclass(frozen=True)
class PaletaTema:
    codigo: str
    nombre: str
    fondo_ventana: str
    fondo_panel: str
    fondo_hero: str
    fondo_reloj: str
    fondo_sidebar: str
    texto_principal: str
    texto_secundario: str
    texto_sidebar: str
    borde: str
    borde_fuerte: str
    acento: str
    acento_hover: str
    acento_suave: str
    exito: str
    exito_hover: str
    advertencia: str
    advertencia_hover: str
    peligro: str
    peligro_hover: str
    fondo_input: str
    seleccion_tabla: str
    texto_seleccion: str


TEMAS: dict[str, PaletaTema] = {
    "gente_util": PaletaTema(
        codigo="gente_util",
        nombre="Gente Util (Corporativo Glass)",
        fondo_ventana="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F0F4FA, stop:0.45 #E5EEF9, stop:1 #D9E5F5)",
        fondo_panel="rgba(255, 255, 255, 0.78)",
        fondo_hero="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255, 255, 255, 0.95), stop:1 rgba(235, 244, 255, 0.84))",
        fondo_reloj="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(230, 240, 255, 0.95), stop:1 rgba(210, 228, 254, 0.75))",
        fondo_sidebar="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #002255, stop:0.5 #001A44, stop:1 #00102E)",
        texto_principal="#0F172A",
        texto_secundario="#475569",
        texto_sidebar="#E2E8F0",
        borde="rgba(255, 255, 255, 0.90)",
        borde_fuerte="rgba(180, 200, 225, 0.60)",
        acento="#003D95",
        acento_hover="#002D70",
        acento_suave="rgba(0, 61, 149, 0.12)",
        exito="#15803D",
        exito_hover="#166534",
        advertencia="#D97706",
        advertencia_hover="#B45309",
        peligro="#DC2626",
        peligro_hover="#B91C1C",
        fondo_input="rgba(255, 255, 255, 0.88)",
        seleccion_tabla="rgba(0, 61, 149, 0.14)",
        texto_seleccion="#003D95",
    ),
    "claro": PaletaTema(
        codigo="claro",
        nombre="Claro Moderno Glass",
        fondo_ventana="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F4F7FB, stop:0.5 #E8EFF8, stop:1 #DDE7F5)",
        fondo_panel="rgba(255, 255, 255, 0.76)",
        fondo_hero="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255, 255, 255, 0.94), stop:1 rgba(240, 246, 255, 0.82))",
        fondo_reloj="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(235, 244, 255, 0.95), stop:1 rgba(215, 232, 254, 0.75))",
        fondo_sidebar="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0F172A, stop:0.6 #0B1222, stop:1 #060913)",
        texto_principal="#0F172A",
        texto_secundario="#64748B",
        texto_sidebar="#CBD5E1",
        borde="rgba(255, 255, 255, 0.85)",
        borde_fuerte="rgba(180, 200, 225, 0.55)",
        acento="#2563EB",
        acento_hover="#1D4ED8",
        acento_suave="rgba(37, 99, 235, 0.12)",
        exito="#16A34A",
        exito_hover="#15803D",
        advertencia="#D97706",
        advertencia_hover="#B45309",
        peligro="#DC2626",
        peligro_hover="#B91C1C",
        fondo_input="rgba(255, 255, 255, 0.88)",
        seleccion_tabla="rgba(37, 99, 235, 0.14)",
        texto_seleccion="#1D4ED8",
    ),
    "oscuro": PaletaTema(
        codigo="oscuro",
        nombre="Oscuro Grafito Glass",
        fondo_ventana="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0B132B, stop:0.5 #101B3B, stop:1 #080D1D)",
        fondo_panel="rgba(19, 29, 53, 0.74)",
        fondo_hero="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(26, 40, 72, 0.85), stop:1 rgba(15, 24, 45, 0.75))",
        fondo_reloj="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(13, 21, 40, 0.95), stop:1 rgba(9, 15, 30, 0.85))",
        fondo_sidebar="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #070B16, stop:0.6 #050811, stop:1 #020408)",
        texto_principal="#F1F5F9",
        texto_secundario="#94A3B8",
        texto_sidebar="#CBD5E1",
        borde="rgba(255, 255, 255, 0.10)",
        borde_fuerte="rgba(255, 255, 255, 0.18)",
        acento="#3B82F6",
        acento_hover="#2563EB",
        acento_suave="rgba(59, 130, 246, 0.18)",
        exito="#22C55E",
        exito_hover="#16A34A",
        advertencia="#F59E0B",
        advertencia_hover="#D97706",
        peligro="#EF4444",
        peligro_hover="#DC2626",
        fondo_input="rgba(15, 23, 42, 0.80)",
        seleccion_tabla="rgba(59, 130, 246, 0.28)",
        texto_seleccion="#FFFFFF",
    ),
    "pizarra": PaletaTema(
        codigo="pizarra",
        nombre="Azul Pizarra Glass",
        fondo_ventana="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EAF0F8, stop:0.5 #DFE8F5, stop:1 #D3DFEF)",
        fondo_panel="rgba(255, 255, 255, 0.75)",
        fondo_hero="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255, 255, 255, 0.94), stop:1 rgba(238, 242, 255, 0.82))",
        fondo_reloj="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(238, 242, 255, 0.95), stop:1 rgba(224, 231, 255, 0.75))",
        fondo_sidebar="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1E293B, stop:0.6 #141C2B, stop:1 #0B1019)",
        texto_principal="#1E293B",
        texto_secundario="#475569",
        texto_sidebar="#E2E8F0",
        borde="rgba(255, 255, 255, 0.85)",
        borde_fuerte="rgba(148, 163, 184, 0.50)",
        acento="#3730A3",
        acento_hover="#312E81",
        acento_suave="rgba(55, 48, 163, 0.12)",
        exito="#15803D",
        exito_hover="#166534",
        advertencia="#B45309",
        advertencia_hover="#92400E",
        peligro="#B91C1C",
        peligro_hover="#991B1B",
        fondo_input="rgba(255, 255, 255, 0.88)",
        seleccion_tabla="rgba(55, 48, 163, 0.14)",
        texto_seleccion="#1E1B4B",
    ),
}


def obtener_paleta(codigo: str | None) -> PaletaTema:
    return TEMAS.get(codigo or "gente_util", TEMAS["gente_util"])


def generar_qss(codigo: str | None = "gente_util", *, tamano_fuente_px: int = 13) -> str:
    """Construye la hoja de estilo QSS completa con tipografía Montserrat y efecto Glassmorphism."""
    t = obtener_paleta(codigo)
    f_base = max(11, min(20, int(tamano_fuente_px)))
    f_sub = max(10, f_base - 1)
    f_tit = f_base + 9
    f_reloj = f_base + 26

    fuente_familia = '"Montserrat", -apple-system, "Segoe UI", Arial, sans-serif'
    fuente_reloj = '"Montserrat", "Cascadia Mono", "Segoe UI", monospace'

    return f"""
    QMainWindow, QDialog {{
        background: {t.fondo_ventana};
        color: {t.texto_principal};
        font-family: {fuente_familia};
        font-size: {f_base}px;
    }}
    QWidget {{
        color: {t.texto_principal};
        font-family: {fuente_familia};
        font-size: {f_base}px;
    }}
    /* Pestañas segmentadas en estilo cápsula de vidrio */
    QTabWidget::pane {{
        background-color: transparent;
        border: none;
        margin-top: 10px;
    }}
    QTabBar::tab {{
        background-color: {t.fondo_panel};
        color: {t.texto_secundario};
        border: 1px solid {t.borde_fuerte};
        border-top: 1.5px solid {t.borde};
        border-radius: 10px;
        padding: 9px 18px;
        margin-right: 8px;
        font-weight: 600;
        font-family: {fuente_familia};
    }}
    QTabBar::tab:hover {{
        color: {t.texto_principal};
        border-color: {t.acento};
    }}
    QTabBar::tab:selected {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t.acento_hover}, stop:1 {t.acento});
        color: #FFFFFF;
        border: 1px solid {t.acento};
        font-weight: 700;
    }}
    /* Barra lateral Glassmorphism */
    QFrame#sidebar {{
        background: {t.fondo_sidebar};
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }}
    QFrame#marcaSidebar {{
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 12px;
        padding: 12px;
    }}
    QLabel#tituloSidebar {{
        color: #FFFFFF;
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 0.5px;
        background: transparent;
    }}
    QLabel#subtituloSidebar {{
        color: #94A3B8;
        font-size: 11px;
        font-weight: 600;
        background: transparent;
    }}
    QLabel#seccionSidebar {{
        color: #64748B;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.2px;
        padding: 12px 10px 4px 10px;
        background: transparent;
    }}
    QLabel#chipEstadoSidebar {{
        background-color: rgba(255, 255, 255, 0.07);
        color: #E2E8F0;
        border-radius: 8px;
        padding: 7px 10px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton[nav="true"] {{
        background-color: transparent;
        color: {t.texto_sidebar};
        text-align: left;
        padding: 10px 14px;
        border-radius: 9px;
        border: 1px solid transparent;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton[nav="true"]:hover {{
        background-color: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.12);
        color: #FFFFFF;
    }}
    QPushButton[nav="true"]:checked {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0056D2, stop:1 {t.acento});
        border-left: 3px solid #60A5FA;
        color: #FFFFFF;
        font-weight: 700;
    }}
    /* Tarjetas y Paneles Glassmorphism */
    QFrame[card="true"], QGroupBox {{
        background-color: {t.fondo_panel};
        border: 1px solid {t.borde_fuerte};
        border-top: 1.5px solid {t.borde};
        border-radius: 14px;
        padding: 16px;
    }}
    QFrame#heroCronometro {{
        background: {t.fondo_hero};
        border: 1.5px solid rgba(0, 61, 149, 0.28);
        border-top: 1.5px solid rgba(255, 255, 255, 0.95);
        border-radius: 16px;
        padding: 18px;
    }}
    QFrame#cajaReloj {{
        background: {t.fondo_reloj};
        border: 1px solid rgba(0, 61, 149, 0.20);
        border-top: 1.5px solid rgba(255, 255, 255, 0.90);
        border-radius: 14px;
        padding: 12px 22px;
    }}
    QLabel#relojGrande {{
        font-size: {f_reloj}px;
        font-weight: 800;
        color: {t.acento};
        font-family: {fuente_reloj};
        letter-spacing: 2px;
        background: transparent;
    }}
    QLabel#relojMini {{
        font-size: {f_base + 8}px;
        font-weight: 800;
        color: {t.acento};
        font-family: {fuente_reloj};
        letter-spacing: 1px;
        background: transparent;
    }}
    QLabel#bannerInfo {{
        background-color: {t.fondo_reloj};
        color: {t.texto_principal};
        border: 1px solid {t.borde_fuerte};
        border-radius: 10px;
        padding: 10px 16px;
        font-weight: 500;
    }}
    QLabel#badgeActiva {{
        background-color: {t.acento_suave};
        color: {t.acento};
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        border: 1px solid rgba(0, 61, 149, 0.25);
        border-radius: 8px;
        padding: 4px 10px;
    }}
    QLabel#tituloPantalla {{
        font-size: {f_tit}px;
        font-weight: 700;
        color: {t.texto_principal};
        letter-spacing: -0.2px;
    }}
    QLabel#subtitulo {{
        color: {t.texto_secundario};
        font-size: {f_sub}px;
        font-weight: 500;
    }}
    /* Botones profesionales sin aspecto plano */
    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t.acento_hover}, stop:1 {t.acento});
        color: #FFFFFF;
        border: 1px solid rgba(255, 255, 255, 0.22);
        border-radius: 9px;
        padding: 9px 18px;
        font-weight: 600;
        font-family: {fuente_familia};
        min-height: 20px;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #186BE5, stop:1 {t.acento});
        border-color: rgba(255, 255, 255, 0.45);
    }}
    QPushButton:disabled {{
        background: {t.borde_fuerte};
        color: {t.texto_secundario};
        border: none;
    }}
    QPushButton[rol="exito"] {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t.exito_hover}, stop:1 {t.exito});
        border: 1px solid rgba(255, 255, 255, 0.22);
    }}
    QPushButton[rol="exito"]:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #22C55E, stop:1 {t.exito});
        border-color: rgba(255, 255, 255, 0.45);
    }}
    QPushButton[rol="advertencia"] {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t.advertencia_hover}, stop:1 {t.advertencia});
        border: 1px solid rgba(255, 255, 255, 0.22);
    }}
    QPushButton[rol="advertencia"]:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F59E0B, stop:1 {t.advertencia});
        border-color: rgba(255, 255, 255, 0.45);
    }}
    QPushButton[rol="peligro"] {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t.peligro_hover}, stop:1 {t.peligro});
        border: 1px solid rgba(255, 255, 255, 0.22);
    }}
    QPushButton[rol="peligro"]:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #EF4444, stop:1 {t.peligro});
        border-color: rgba(255, 255, 255, 0.45);
    }}
    QPushButton[rol="secundario"] {{
        background-color: {t.fondo_panel};
        color: {t.texto_principal};
        border: 1px solid {t.borde_fuerte};
        border-top: 1.5px solid {t.borde};
    }}
    QPushButton[rol="secundario"]:hover {{
        background-color: #FFFFFF;
        border-color: {t.acento};
        color: {t.acento};
    }}
    /* Entradas de formulario Glass */
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QTimeEdit, QDateEdit, QDateTimeEdit, QKeySequenceEdit {{
        background-color: {t.fondo_input};
        color: {t.texto_principal};
        border: 1px solid {t.borde_fuerte};
        border-radius: 9px;
        padding: 8px 12px;
        min-height: 22px;
        font-family: {fuente_familia};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
    QSpinBox:focus, QDateEdit:focus, QDateTimeEdit:focus, QKeySequenceEdit:focus {{
        border: 1.5px solid {t.acento};
        background-color: #FFFFFF;
    }}
    /* Tablas Glassmorphism */
    QTableWidget, QListWidget {{
        background-color: {t.fondo_panel};
        alternate-background-color: {t.fondo_hero};
        border: 1px solid {t.borde_fuerte};
        border-top: 1.5px solid {t.borde};
        border-radius: 12px;
        gridline-color: rgba(226, 232, 240, 0.6);
        selection-background-color: {t.seleccion_tabla};
        selection-color: {t.texto_seleccion};
        outline: none;
        font-family: {fuente_familia};
    }}
    QTableWidget::item {{
        padding: 7px 10px;
        border-bottom: 1px solid rgba(226, 232, 240, 0.5);
    }}
    QTableWidget::item:selected, QListWidget::item:selected {{
        background-color: {t.seleccion_tabla};
        color: {t.texto_seleccion};
        font-weight: 600;
    }}
    QHeaderView::section {{
        background-color: {t.fondo_hero};
        color: {t.texto_secundario};
        font-weight: 700;
        font-size: 11px;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        border: none;
        border-bottom: 2px solid {t.borde_fuerte};
        padding: 11px 10px;
        font-family: {fuente_familia};
    }}
    /* Barra de progreso */
    QProgressBar {{
        border: 1px solid {t.borde_fuerte};
        border-radius: 8px;
        text-align: center;
        background-color: {t.fondo_input};
        height: 22px;
        font-weight: 700;
        color: {t.texto_principal};
        font-family: {fuente_familia};
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {t.exito}, stop:1 #34D399);
        border-radius: 7px;
    }}
    /* Barras de desplazamiento */
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.borde_fuerte};
        min-height: 28px;
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """
