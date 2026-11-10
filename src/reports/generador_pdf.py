"""Renderizado de HTML estilizado a archivos PDF usando `QPdfWriter` + `QTextDocument` (RF-08).

No requiere internet ni librerías nativas externas; funciona con cualquier
usuario estándar de Windows y soporta tablas ejecutivas, colores corporativos
e incrustación nítida del logo oficial de Gente Util S.A.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def renderizar_html_a_pdf(html: str, ruta_destino: Path | str) -> Path:
    """Convierte un documento HTML en un archivo PDF en ``ruta_destino``."""
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])

    destino = Path(ruta_destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    # Si el archivo PDF anterior está abierto y bloqueado por un visor externo en Windows,
    # escribimos en un nombre con marca de hora para que nunca falle al hacer clic.
    if destino.exists():
        try:
            with open(destino, "ab"):
                pass
        except OSError:
            from datetime import datetime

            marca = datetime.now().strftime("%H%M%S")
            destino = destino.with_name(f"{destino.stem}_{marca}{destino.suffix}")

    writer = QPdfWriter(str(destino))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
    writer.setPageMargins(QMarginsF(12.0, 12.0, 12.0, 12.0), QPageLayout.Unit.Millimeter)
    # 96 DPI alinea 1:1 las unidades lógicas de CSS/HTML (px/pt) con la página PDF
    # manteniendo texto y bordes vectoriales y el logo PNG en alta resolución.
    writer.setResolution(96)

    doc = QTextDocument()
    doc.setDocumentMargin(4.0)
    doc.setHtml(html)
    doc.print_(writer)
    return destino


def abrir_archivo_pdf(ruta: Path | str) -> bool:
    """Abre el archivo PDF con el visor predeterminado del sistema (salvo en pruebas headless)."""
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return False
    p = Path(ruta)
    if not p.is_file():
        return False
    try:
        if sys.platform == "win32":
            os.startfile(str(p))  # type: ignore[attr-defined]
            return True
    except Exception:
        pass
    return False


def abrir_carpeta_contenedora(ruta: Path | str) -> bool:
    """Abre la carpeta donde está guardado el PDF para arrastrarlo fácilmente a WhatsApp (RF-06)."""
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return False
    p = Path(ruta)
    carpeta = p.parent if p.is_file() else p
    if not carpeta.exists():
        return False
    try:
        if sys.platform == "win32":
            if p.is_file():
                subprocess.Popen(["explorer", "/select,", str(p)])
            else:
                os.startfile(str(carpeta))  # type: ignore[attr-defined]
            return True
    except Exception:
        pass
    return False
