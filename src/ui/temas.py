"""Temas visuales (QSS) de la aplicación (RF-09, RNF-06).

Paleta neutra, moderna y con amplio espacio en blanco (la paleta corporativa y
el logo de Gente Util se incorporan antes de la v1.0). Incluye tres temas:
- ``claro``: fondo blanco cálido/gris muy suave, acento azul profesional.
- ``oscuro``: fondo grafito oscuro con alto contraste y descanso visual.
- ``pizarra``: tono azul pizarra suave para jornadas largas.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaletaTema:
    codigo: str
    nombre: str
    fondo_ventana: str
    fondo_panel: str
    fondo_sidebar: str
    texto_principal: str
    texto_secundario: str
    texto_sidebar: str
    borde: str
    acento: str
    acento_hover: str
    exito: str
    advertencia: str
    peligro: str
    fondo_input: str


TEMAS: dict[str, PaletaTema] = {
    "claro": PaletaTema(
        codigo="claro",
        nombre="Claro Neutro",
        fondo_ventana="#F8FAFC",
        fondo_panel="#FFFFFF",
        fondo_sidebar="#0F172A",
        texto_principal="#0F172A",
        texto_secundario="#475569",
        texto_sidebar="#E2E8F0",
        borde="#E2E8F0",
        acento="#2563EB",
        acento_hover="#1D4ED8",
        exito="#16A34A",
        advertencia="#D97706",
        peligro="#DC2626",
        fondo_input="#FFFFFF",
    ),
    "oscuro": PaletaTema(
        codigo="oscuro",
        nombre="Oscuro Grafito",
        fondo_ventana="#0B1120",
        fondo_panel="#1E293B",
        fondo_sidebar="#020617",
        texto_principal="#F1F5F9",
        texto_secundario="#94A3B8",
        texto_sidebar="#E2E8F0",
        borde="#334155",
        acento="#3B82F6",
        acento_hover="#60A5FA",
        exito="#22C55E",
        advertencia="#F59E0B",
        peligro="#EF4444",
        fondo_input="#0F172A",
    ),
    "pizarra": PaletaTema(
        codigo="pizarra",
        nombre="Azul Pizarra",
        fondo_ventana="#EFF6FF",
        fondo_panel="#FFFFFF",
        fondo_sidebar="#1E3A8A",
        texto_principal="#1E293B",
        texto_secundario="#475569",
        texto_sidebar="#F8FAFC",
        borde="#BFDBFE",
        acento="#1D4ED8",
        acento_hover="#1E40AF",
        exito="#15803D",
        advertencia="#B45309",
        peligro="#B91C1C",
        fondo_input="#FFFFFF",
    ),
    "gente_util": PaletaTema(
        codigo="gente_util",
        nombre="Gente Util (Corporativo)",
        fondo_ventana="#F4F7FB",
        fondo_panel="#FFFFFF",
        fondo_sidebar="#0F4C81",
        texto_principal="#0F172A",
        texto_secundario="#475569",
        texto_sidebar="#F8FAFC",
        borde="#CBD5E1",
        acento="#0F4C81",
        acento_hover="#0B3B66",
        exito="#15803D",
        advertencia="#D97706",
        peligro="#DC2626",
        fondo_input="#FFFFFF",
    ),
}


def obtener_paleta(codigo: str | None) -> PaletaTema:
    return TEMAS.get(codigo or "claro", TEMAS["claro"])


def generar_qss(codigo: str | None = "claro") -> str:
    """Construye la hoja de estilo QSS completa para el tema indicado."""
    t = obtener_paleta(codigo)
    return f"""
    QMainWindow, QDialog {{
        background-color: {t.fondo_ventana};
        color: {t.texto_principal};
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 13px;
    }}
    QWidget {{
        color: {t.texto_principal};
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 13px;
    }}
    QFrame#sidebar {{
        background-color: {t.fondo_sidebar};
        border: none;
    }}
    QLabel#tituloSidebar {{
        color: #FFFFFF;
        font-size: 16px;
        font-weight: bold;
        padding: 8px 4px;
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
        background-color: rgba(255, 255, 255, 0.10);
    }}
    QPushButton[nav="true"]:checked {{
        background-color: {t.acento};
        color: #FFFFFF;
        font-weight: bold;
    }}
    QFrame[card="true"], QGroupBox {{
        background-color: {t.fondo_panel};
        border: 1px solid {t.borde};
        border-radius: 10px;
        padding: 12px;
    }}
    QGroupBox {{
        margin-top: 10px;
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }}
    QLabel#relojGrande {{
        font-size: 38px;
        font-weight: bold;
        color: {t.acento};
        font-family: "Consolas", "Segoe UI", monospace;
    }}
    QLabel#tituloPantalla {{
        font-size: 20px;
        font-weight: bold;
        color: {t.texto_principal};
    }}
    QLabel#subtitulo {{
        color: {t.texto_secundario};
        font-size: 12px;
    }}
    QPushButton {{
        background-color: {t.acento};
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        padding: 7px 14px;
        font-weight: 600;
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
    QPushButton[rol="advertencia"] {{
        background-color: {t.advertencia};
    }}
    QPushButton[rol="peligro"] {{
        background-color: {t.peligro};
    }}
    QPushButton[rol="secundario"] {{
        background-color: transparent;
        color: {t.texto_principal};
        border: 1px solid {t.borde};
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit, QDateTimeEdit {{
        background-color: {t.fondo_input};
        color: {t.texto_principal};
        border: 1px solid {t.borde};
        border-radius: 6px;
        padding: 6px 8px;
    }}
    QTableWidget {{
        background-color: {t.fondo_panel};
        alternate-background-color: {t.fondo_ventana};
        border: 1px solid {t.borde};
        border-radius: 8px;
        gridline-color: {t.borde};
    }}
    QHeaderView::section {{
        background-color: {t.fondo_ventana};
        color: {t.texto_secundario};
        font-weight: bold;
        border: none;
        border-bottom: 1px solid {t.borde};
        padding: 8px;
    }}
    QProgressBar {{
        border: 1px solid {t.borde};
        border-radius: 6px;
        text-align: center;
        background-color: {t.fondo_ventana};
        height: 18px;
        font-weight: bold;
    }}
    QProgressBar::chunk {{
        background-color: {t.exito};
        border-radius: 5px;
    }}
    """
