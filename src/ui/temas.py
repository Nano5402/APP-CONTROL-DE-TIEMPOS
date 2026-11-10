"""Temas visuales (QSS) modernos de la aplicación (RF-09, RNF-06).

Incluye cuatro paletas cuidadosamente diseñadas:
- ``claro``: Blanco limpio y gris suave con acento azul real.
- ``gente_util``: Identidad corporativa de Gente Util (azul profundo y ámbar cálido).
- ``oscuro``: Modo oscuro grafito de alto confort visual.
- ``pizarra``: Azul pizarra sereno para jornadas largas de diseño.
"""

from __future__ import annotations

from dataclasses import dataclass


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
    "claro": PaletaTema(
        codigo="claro",
        nombre="Claro Moderno",
        fondo_ventana="#F1F5F9",
        fondo_panel="#FFFFFF",
        fondo_hero="#F8FAFC",
        fondo_reloj="#EFF6FF",
        fondo_sidebar="#0F172A",
        texto_principal="#0F172A",
        texto_secundario="#64748B",
        texto_sidebar="#CBD5E1",
        borde="#E2E8F0",
        borde_fuerte="#CBD5E1",
        acento="#2563EB",
        acento_hover="#1D4ED8",
        acento_suave="#DBEAFE",
        exito="#16A34A",
        exito_hover="#15803D",
        advertencia="#D97706",
        advertencia_hover="#B45309",
        peligro="#DC2626",
        peligro_hover="#B91C1C",
        fondo_input="#F8FAFC",
        seleccion_tabla="#DBEAFE",
        texto_seleccion="#1E3A8A",
    ),
    "gente_util": PaletaTema(
        codigo="gente_util",
        nombre="Gente Util (Corporativo)",
        fondo_ventana="#F0F4F8",
        fondo_panel="#FFFFFF",
        fondo_hero="#F8FAFC",
        fondo_reloj="#E6EEF9",
        fondo_sidebar="#00265E",
        texto_principal="#0F172A",
        texto_secundario="#475569",
        texto_sidebar="#E2E8F0",
        borde="#D8E2EE",
        borde_fuerte="#B8C9DE",
        acento="#003D95",
        acento_hover="#002D70",
        acento_suave="#D6E4FA",
        exito="#15803D",
        exito_hover="#166534",
        advertencia="#D97706",
        advertencia_hover="#B45309",
        peligro="#DC2626",
        peligro_hover="#B91C1C",
        fondo_input="#F8FAFC",
        seleccion_tabla="#D6E4FA",
        texto_seleccion="#003D95",
    ),
    "oscuro": PaletaTema(
        codigo="oscuro",
        nombre="Oscuro Grafito",
        fondo_ventana="#0B1120",
        fondo_panel="#151F32",
        fondo_hero="#1E293B",
        fondo_reloj="#0F172A",
        fondo_sidebar="#060B14",
        texto_principal="#F1F5F9",
        texto_secundario="#94A3B8",
        texto_sidebar="#CBD5E1",
        borde="#26354D",
        borde_fuerte="#334155",
        acento="#3B82F6",
        acento_hover="#2563EB",
        acento_suave="#1E3A8A",
        exito="#22C55E",
        exito_hover="#16A34A",
        advertencia="#F59E0B",
        advertencia_hover="#D97706",
        peligro="#EF4444",
        peligro_hover="#DC2626",
        fondo_input="#0F172A",
        seleccion_tabla="#1E3A8A",
        texto_seleccion="#FFFFFF",
    ),
    "pizarra": PaletaTema(
        codigo="pizarra",
        nombre="Azul Pizarra",
        fondo_ventana="#E8F0FE",
        fondo_panel="#FFFFFF",
        fondo_hero="#F5F8FF",
        fondo_reloj="#EEF2FF",
        fondo_sidebar="#1E293B",
        texto_principal="#1E293B",
        texto_secundario="#475569",
        texto_sidebar="#E2E8F0",
        borde="#CBD5E1",
        borde_fuerte="#94A3B8",
        acento="#3730A3",
        acento_hover="#312E81",
        acento_suave="#E0E7FF",
        exito="#15803D",
        exito_hover="#166534",
        advertencia="#B45309",
        advertencia_hover="#92400E",
        peligro="#B91C1C",
        peligro_hover="#991B1B",
        fondo_input="#F8FAFC",
        seleccion_tabla="#E0E7FF",
        texto_seleccion="#1E1B4B",
    ),
}


def obtener_paleta(codigo: str | None) -> PaletaTema:
    return TEMAS.get(codigo or "claro", TEMAS["claro"])


def generar_qss(codigo: str | None = "claro", *, tamano_fuente_px: int = 13) -> str:
    """Construye la hoja de estilo QSS completa para el tema y escala indicados."""
    t = obtener_paleta(codigo)
    f_base = max(11, min(20, int(tamano_fuente_px)))
    f_sub = max(10, f_base - 1)
    f_tit = f_base + 9
    f_reloj = f_base + 27
    return f"""
    QMainWindow, QDialog {{
        background-color: {t.fondo_ventana};
        color: {t.texto_principal};
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: {f_base}px;
    }}
    QWidget {{
        color: {t.texto_principal};
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: {f_base}px;
    }}
    /* Pestañas segmentadas (Configuración, etc.) */
    QTabWidget::pane {{
        background-color: transparent;
        border: none;
        margin-top: 8px;
    }}
    QTabBar::tab {{
        background-color: {t.fondo_panel};
        color: {t.texto_secundario};
        border: 1px solid {t.borde_fuerte};
        border-radius: 8px;
        padding: 9px 16px;
        margin-right: 6px;
        font-weight: 600;
    }}
    QTabBar::tab:hover {{
        color: {t.texto_principal};
        border-color: {t.acento};
    }}
    QTabBar::tab:selected {{
        background-color: {t.acento};
        color: #FFFFFF;
        border-color: {t.acento};
        font-weight: bold;
    }}
    /* Barra lateral */
    QFrame#sidebar {{
        background-color: {t.fondo_sidebar};
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }}
    QFrame#marcaSidebar {{
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 10px;
        padding: 10px;
    }}
    QLabel#tituloSidebar {{
        color: #FFFFFF;
        font-size: 16px;
        font-weight: bold;
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
        font-weight: bold;
        letter-spacing: 1px;
        padding: 10px 8px 2px 8px;
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
        border-radius: 8px;
        border: none;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton[nav="true"]:hover {{
        background-color: rgba(255, 255, 255, 0.09);
        color: #FFFFFF;
    }}
    QPushButton[nav="true"]:checked {{
        background-color: {t.acento};
        color: #FFFFFF;
        font-weight: bold;
    }}
    /* Tarjetas y contenedores */
    QFrame[card="true"], QGroupBox {{
        background-color: {t.fondo_panel};
        border: 1px solid {t.borde};
        border-radius: 12px;
        padding: 14px;
    }}
    QFrame#heroCronometro {{
        background-color: {t.fondo_panel};
        border: 2px solid {t.acento};
        border-radius: 14px;
        padding: 16px;
    }}
    QFrame#cajaReloj {{
        background-color: {t.fondo_reloj};
        border: 1px solid {t.borde_fuerte};
        border-radius: 12px;
        padding: 10px 18px;
    }}
    QLabel#relojGrande {{
        font-size: {f_reloj}px;
        font-weight: bold;
        color: {t.acento};
        font-family: "Cascadia Mono", "Consolas", "Segoe UI", monospace;
        background: transparent;
    }}
    QLabel#relojMini {{
        font-size: {f_base + 7}px;
        font-weight: bold;
        color: {t.acento};
        font-family: "Cascadia Mono", "Consolas", "Segoe UI", monospace;
        background: transparent;
    }}
    QLabel#bannerInfo {{
        background-color: {t.fondo_reloj};
        color: {t.texto_principal};
        border: 1px solid {t.borde_fuerte};
        border-radius: 8px;
        padding: 9px 14px;
        font-weight: 500;
    }}
    QLabel#badgeActiva {{
        background-color: {t.acento_suave};
        color: {t.acento};
        font-size: 11px;
        font-weight: bold;
        border-radius: 6px;
        padding: 3px 8px;
    }}
    QLabel#tituloPantalla {{
        font-size: {f_tit}px;
        font-weight: bold;
        color: {t.texto_principal};
    }}
    QLabel#subtitulo {{
        color: {t.texto_secundario};
        font-size: {f_sub}px;
    }}
    /* Botones */
    QPushButton {{
        background-color: {t.acento};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 600;
        min-height: 18px;
    }}
    QPushButton:hover {{
        background-color: {t.acento_hover};
    }}
    QPushButton:disabled {{
        background-color: {t.borde};
        color: {t.texto_secundario};
    }}
    QPushButton[rol="exito"] {{
        background-color: {t.exito};
    }}
    QPushButton[rol="exito"]:hover {{
        background-color: {t.exito_hover};
    }}
    QPushButton[rol="advertencia"] {{
        background-color: {t.advertencia};
    }}
    QPushButton[rol="advertencia"]:hover {{
        background-color: {t.advertencia_hover};
    }}
    QPushButton[rol="peligro"] {{
        background-color: {t.peligro};
    }}
    QPushButton[rol="peligro"]:hover {{
        background-color: {t.peligro_hover};
    }}
    QPushButton[rol="secundario"] {{
        background-color: {t.fondo_panel};
        color: {t.texto_principal};
        border: 1px solid {t.borde_fuerte};
    }}
    QPushButton[rol="secundario"]:hover {{
        background-color: {t.fondo_ventana};
        border: 1px solid {t.acento};
    }}
    /* Entradas de formulario */
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QTimeEdit, QDateEdit, QDateTimeEdit, QKeySequenceEdit {{
        background-color: {t.fondo_input};
        color: {t.texto_principal};
        border: 1px solid {t.borde_fuerte};
        border-radius: 8px;
        padding: 7px 10px;
        min-height: 20px;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
    QSpinBox:focus, QDateEdit:focus, QDateTimeEdit:focus, QKeySequenceEdit:focus {{
        border: 2px solid {t.acento};
        background-color: {t.fondo_panel};
    }}
    /* Tablas */
    QTableWidget, QListWidget {{
        background-color: {t.fondo_panel};
        alternate-background-color: {t.fondo_hero};
        border: 1px solid {t.borde};
        border-radius: 10px;
        gridline-color: {t.borde};
        selection-background-color: {t.seleccion_tabla};
        selection-color: {t.texto_seleccion};
        outline: none;
    }}
    QTableWidget::item {{
        padding: 6px 8px;
        border-bottom: 1px solid {t.borde};
    }}
    QTableWidget::item:selected, QListWidget::item:selected {{
        background-color: {t.seleccion_tabla};
        color: {t.texto_seleccion};
        font-weight: 600;
    }}
    QHeaderView::section {{
        background-color: {t.fondo_hero};
        color: {t.texto_secundario};
        font-weight: bold;
        font-size: 12px;
        border: none;
        border-bottom: 2px solid {t.borde_fuerte};
        padding: 10px 8px;
    }}
    /* Barra de progreso */
    QProgressBar {{
        border: 1px solid {t.borde_fuerte};
        border-radius: 8px;
        text-align: center;
        background-color: {t.fondo_input};
        height: 22px;
        font-weight: bold;
        color: {t.texto_principal};
    }}
    QProgressBar::chunk {{
        background-color: {t.exito};
        border-radius: 7px;
    }}
    /* Barras de desplazamiento delgadas */
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
