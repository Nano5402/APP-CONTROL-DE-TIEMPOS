"""Utilidades de fecha y hora.

Decisión (Fase 1): todas las fechas se guardan en **hora local de Colombia sin
zona horaria**. Colombia no tiene horario de verano, así que no hay saltos de
hora y los cálculos son directos. Toda la app debe obtener la hora actual con
``ahora()`` para que las pruebas puedan simularla.
"""

from __future__ import annotations

from datetime import datetime


def ahora() -> datetime:
    """Hora local actual, sin zona y sin microsegundos."""
    return datetime.now().replace(microsecond=0)
