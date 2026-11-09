"""Reproducción de sonido para los recordatorios (RF-04).

Funciona 100 % local y sin permisos especiales. En Windows usa ``winsound``
para emitir un tono agradable (o ``QApplication.beep()`` como respaldo). En
pruebas o cuando ``aviso.sonido = 0`` no emite sonido.
"""

from __future__ import annotations

import os
import sys


def reproducir_tono_aviso(*, habilitado: bool = True, es_repeticion: bool = False) -> None:
    """Emite el sonido del recordatorio si está habilitado y no es entorno headless."""
    if not habilitado:
        return
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return

    try:
        if sys.platform == "win32":
            import winsound

            frecuencia = 880 if es_repeticion else 660
            winsound.Beep(frecuencia, 180)
            return
    except Exception:
        pass

    try:
        from PySide6.QtWidgets import QApplication

        QApplication.beep()
    except Exception:
        pass
