"""Ventana provisional de la Fase 1.

Solo confirma que la app arranca, que la base de datos quedó lista y muestra
el horario y los solicitantes cargados. Se reemplaza por la pantalla "Hoy" en
las fases siguientes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget
from sqlalchemy import select

from config import rutas
from data.db import BaseDatos
from data.models import Solicitante
from data.repositorios.horarios import RepoHorarios

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


class VentanaPrincipal(QMainWindow):
    """Ventana de verificación de la base del proyecto."""

    def __init__(self, bd: BaseDatos) -> None:
        super().__init__()
        self.setWindowTitle(f"{rutas.NOMBRE_VISIBLE} — v{rutas.VERSION} (Fase 1)")
        self.resize(560, 480)

        with bd.sesion() as s:
            repo = RepoHorarios(s)
            lineas_horario = []
            for dia, nombre in enumerate(DIAS):
                bloques = repo.bloques_del_dia(dia)
                texto = (
                    "  ·  ".join(f"{b.hora_inicio:%H:%M}–{b.hora_fin:%H:%M}" for b in bloques)
                    if bloques
                    else "Sin horario (fuera de horario)"
                )
                lineas_horario.append(f"<b>{nombre}:</b> {texto}")
            solicitantes = [
                f"{x.nombre} ({x.tipo}, prioridad {x.prioridad_defecto})"
                for x in s.scalars(select(Solicitante).order_by(Solicitante.id))
            ]

        html = (
            "<h2>Base del proyecto lista ✔</h2>"
            f"<p>Datos en: <code>{bd.motor.url.database}</code></p>"
            "<h3>Horario laboral</h3>" + "<br>".join(lineas_horario) +
            "<h3>Solicitantes iniciales</h3>" + "<br>".join(solicitantes)
        )
        etiqueta = QLabel(html)
        etiqueta.setTextFormat(Qt.TextFormat.RichText)
        etiqueta.setWordWrap(True)
        etiqueta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        contenedor = QWidget()
        capa = QVBoxLayout(contenedor)
        capa.setContentsMargins(24, 24, 24, 24)
        capa.addWidget(etiqueta)
        capa.addStretch()
        self.setCentralWidget(contenedor)
