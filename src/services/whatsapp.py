"""Generación de textos listos para pegar en el grupo de WhatsApp con el jefe (RF-01, RF-06).

Incluye:
- ``generar_texto_plan_whatsapp``: listado numerado de las actividades planeadas
  de la mañana (incluyendo arrastradas del día anterior si las hay).
- ``generar_texto_resumen_whatsapp``: resumen de cierre del día con lo realizado,
  extras atendidas, arrastradas y el porcentaje de productividad.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.enums import EstadoActividad, TipoActividad
from data.models import Actividad, Jornada, Usuario
from services.actividades import ServicioActividades
from services.productividad import ResultadoProductividad, ServicioProductividad


def formatear_duracion_corta(segundos: int) -> str:
    """Convierte segundos en formato legible como ``1 h 25 min`` o ``25 min``."""
    total_min = max(0, int(round(segundos / 60)))
    horas, minutos = divmod(total_min, 60)
    if horas and minutos:
        return f"{horas} h {minutos} min"
    if horas:
        return f"{horas} h"
    return f"{minutos} min"


class ServicioWhatsApp:
    """Construye los mensajes de plan matutino y resumen de cierre para WhatsApp."""

    def __init__(self, s: Session) -> None:
        self.s = s
        self.srv_act = ServicioActividades(s)
        self.srv_prod = ServicioProductividad(s)

    def _nombre_usuario(self) -> str:
        usr = self.s.scalar(select(Usuario).limit(1))
        return usr.nombre.strip() if usr and usr.nombre and usr.nombre.strip() else ""

    def generar_texto_plan(self, jornada: Jornada) -> str:
        """Genera el texto numerado de 'Copiar plan para WhatsApp' (RF-01)."""
        nombre = self._nombre_usuario()
        encabezado = f"📋 *Plan del día ({jornada.fecha:%d/%m/%Y})*"
        if nombre:
            encabezado += f" — *{nombre}*"

        actividades = [
            a
            for a in self.srv_act.listar_visibles_jornada(jornada.id)
            if a.tipo == TipoActividad.PLANEADA.value and not a.es_revision
        ]
        arrastradas = self.srv_act.listar_arrastradas_pendientes(jornada.fecha)

        lineas = [encabezado, ""]
        num = 1
        for arr in arrastradas:
            avance = f" (avance previo: {arr.avance_pct}%)" if arr.avance_pct else ""
            lineas.append(f"{num}. {arr.nombre}{avance} [Continuación]")
            num += 1

        for act in actividades:
            est = f" ({act.tiempo_estimado_min} min est.)" if act.tiempo_estimado_min else ""
            cat = f" [{act.categoria.nombre}]" if act.categoria else ""
            lineas.append(f"{num}. {act.nombre}{cat}{est}")
            num += 1

        if num == 1:
            lineas.append("(Sin actividades planeadas registradas aún)")

        return "\n".join(lineas)

    def generar_texto_resumen(
        self,
        jornada: Jornada,
        resultado: ResultadoProductividad | None = None,
    ) -> str:
        """Genera el texto de 'Copiar resumen para WhatsApp' al final del día (RF-06)."""
        res = resultado or self.srv_prod.calcular_jornada(jornada)
        nombre = self._nombre_usuario()

        encabezado = f"✅ *Resumen de jornada ({jornada.fecha:%d/%m/%Y})*"
        if nombre:
            encabezado += f" — *{nombre}*"

        lineas = [encabezado, ""]

        visibles = self.srv_act.listar_visibles_jornada(jornada.id)
        completadas = [
            a
            for a in visibles
            if a.estado == EstadoActividad.COMPLETADA.value and not a.es_revision
        ]
        arrastradas = [
            a for a in visibles if a.estado == EstadoActividad.ARRASTRADA.value
        ]

        if completadas:
            lineas.append("*Actividades completadas:*")
            for idx, act in enumerate(completadas, start=1):
                desglose = self.srv_act.desglose_tiempos(act)
                dur = formatear_duracion_corta(desglose.segundos_total)
                etiqueta_extra = ""
                if act.tipo == TipoActividad.EXTRA.value and act.solicitante:
                    etiqueta_extra = f" [Extra - {act.solicitante.nombre}]"
                elif act.tipo == TipoActividad.NO_PLANEADA.value:
                    etiqueta_extra = " [No planeada]"
                rev_txt = (
                    f" (+{desglose.cantidad_revisiones} rev.)"
                    if desglose.solicitaron_cambios
                    else ""
                )
                lineas.append(f"{idx}. {act.nombre}{etiqueta_extra} — {dur}{rev_txt}")
            lineas.append("")

        if arrastradas:
            lineas.append("*En progreso para continuar:*")
            for act in arrastradas:
                av = f"{act.avance_pct or 0}%"
                lineas.append(f"• {act.nombre} (avance: {av})")
            lineas.append("")

        lineas.append(f"⏱ *Tiempo efectivo:* {formatear_duracion_corta(res.tiempo_efectivo_seg)}")
        if res.tiempo_fuera_horario_seg > 0:
            lineas.append(
                f"🌙 *Tiempo fuera de horario:* {formatear_duracion_corta(res.tiempo_fuera_horario_seg)}"
            )

        if res.es_laboral and res.productividad_pct is not None:
            lineas.append(
                f"{res.semaforo.emoji()} *Productividad del día:* {res.productividad_pct:.1f}% "
                f"({res.semaforo.etiqueta()})"
            )
        else:
            lineas.append("⚪ *Jornada en día no laboral* (solo registro de tiempo)")

        return "\n".join(lineas)


def copiar_al_portapapeles(texto: str) -> bool:
    """Copia ``texto`` al portapapeles del sistema usando Qt si hay instancia activa."""
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            QApplication.clipboard().setText(texto)
            return True
    except Exception:
        pass
    return False
