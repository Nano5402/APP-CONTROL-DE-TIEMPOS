"""Asistente de cierre de jornada (RF-06).

Flujo del cierre:
1. Lista las actividades abiertas de la jornada (``en_curso``, ``pendiente`` o ``pausada``)
   para que el usuario decida qué hacer con cada una:
   - **Finalizar** (marca ``completada`` al 100 %).
   - **Arrastrar** (pausa con tipo ``fin_jornada``, motivo obligatorio y ``avance_pct``).
   - **Aplazar / Rechazar / Eliminar** (si nunca se empezó o se canceló).
2. Cierra cualquier pausa abierta en la jornada.
3. Calcula el porcentaje de productividad y la meta de tiempo efectivo
   (``ServicioProductividad``) y guarda los valores en ``jornadas``.
4. Ejecuta la copia de seguridad automática diaria (``ServicioBackups``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.enums import EstadoActividad, EstadoJornada, TipoCopia, TipoPausa
from data.models import Actividad, CopiaSeguridad, Jornada, Pausa
from data.tiempo import ahora
from services.actividades import ServicioActividades
from services.backups import ServicioBackups
from services.cronometro import ServicioCronometro
from services.productividad import ResultadoProductividad, ServicioProductividad
from services.reportes_pdf import ServicioReportesPDF
from services.whatsapp import ServicioWhatsApp


class AccionCierreActividad(StrEnum):
    FINALIZAR = "finalizar"
    ARRASTRAR = "arrastrar"
    APLAZAR = "aplazar"


@dataclass(frozen=True)
class DecisionActividadCierre:
    """Decisión tomada por el usuario en el asistente de cierre para una actividad abierta."""

    actividad_id: int
    accion: AccionCierreActividad | str
    motivo: str | None = None
    avance_pct: int | None = None


@dataclass(frozen=True)
class ResultadoCierreJornada:
    """Resultado devuelto al completar el cierre del día."""

    jornada: Jornada
    productividad: ResultadoProductividad
    texto_resumen_whatsapp: str
    copia_seguridad: CopiaSeguridad | None
    ruta_pdf: Path | None = None


class ActividadesAbiertasAlCierreError(RuntimeError):
    """Se lanza si se intenta cerrar la jornada quedando actividades sin resolver."""

    def __init__(self, actividades: list[Actividad]) -> None:
        nombres = ", ".join(a.nombre for a in actividades)
        super().__init__(f"Quedan actividades abiertas sin resolver antes de cerrar: {nombres}")
        self.actividades = actividades


class ServicioCierreJornada:
    """Coordina el asistente de cierre, cálculo de productividad y copia de seguridad."""

    def __init__(self, s: Session, ruta_bd: Path | None = None) -> None:
        self.s = s
        self.cron = ServicioCronometro(s)
        self.srv_act = ServicioActividades(s)
        self.srv_prod = ServicioProductividad(s)
        self.srv_wa = ServicioWhatsApp(s)
        self.srv_backups = ServicioBackups(s, ruta_bd_origen=ruta_bd)
        self.srv_pdf = ServicioReportesPDF(s)

    def actividades_por_resolver(self, jornada: Jornada) -> list[Actividad]:
        """Devuelve las actividades de la jornada que requieren decisión antes de cerrar."""
        estados_abiertos = {
            EstadoActividad.EN_CURSO.value,
            EstadoActividad.PENDIENTE.value,
            EstadoActividad.PAUSADA.value,
        }
        visibles = self.srv_act.listar_visibles_jornada(jornada.id)
        return [a for a in visibles if a.estado in estados_abiertos]

    def aplicar_decisiones(
        self,
        decisiones: list[DecisionActividadCierre],
        *,
        momento: datetime | None = None,
    ) -> None:
        """Aplica las decisiones del asistente de cierre sobre cada actividad abierta."""
        instante = momento or ahora()
        for dec in decisiones:
            act = self.s.get(Actividad, dec.actividad_id)
            if act is None:
                continue
            accion = AccionCierreActividad(dec.accion)

            if accion == AccionCierreActividad.FINALIZAR:
                self.cron.finalizar(act, descripcion=dec.motivo, momento=instante)
            elif accion == AccionCierreActividad.ARRASTRAR:
                if dec.avance_pct is None:
                    raise ValueError(
                        f"Debe indicar el porcentaje de avance para arrastrar '{act.nombre}'"
                    )
                if not dec.motivo or not dec.motivo.strip():
                    raise ValueError(
                        f"Debe indicar el motivo para arrastrar '{act.nombre}' al día siguiente"
                    )
                self.cron.pausar(
                    act,
                    tipo=TipoPausa.FIN_JORNADA,
                    motivo=dec.motivo,
                    avance_pct=dec.avance_pct,
                    momento=instante,
                )
            elif accion == AccionCierreActividad.APLAZAR:
                if act.estado == EstadoActividad.EN_CURSO.value:
                    self.cron.pausar(act, tipo=TipoPausa.OTRO, motivo=dec.motivo, momento=instante)
                self.srv_act.cambiar_estado_manual(
                    act, EstadoActividad.APLAZADA, motivo=dec.motivo
                )

    def cerrar_jornada(
        self,
        jornada: Jornada,
        *,
        decisiones: list[DecisionActividadCierre] | None = None,
        ejecutar_backup: bool = True,
        generar_pdf: bool = True,
        momento: datetime | None = None,
    ) -> ResultadoCierreJornada:
        """Ejecuta el cierre completo de la jornada (RF-06)."""
        instante = momento or ahora()

        if decisiones:
            self.aplicar_decisiones(decisiones, momento=instante)

        abiertas = self.actividades_por_resolver(jornada)
        if abiertas:
            raise ActividadesAbiertasAlCierreError(abiertas)

        # Cierra cualquier pausa abierta de la jornada
        pausas_abiertas = list(
            self.s.scalars(
                select(Pausa).where(
                    Pausa.jornada_id == jornada.id,
                    Pausa.fin.is_(None),
                )
            )
        )
        for p in pausas_abiertas:
            p.fin = max(instante, p.inicio)
        self.s.flush()

        resultado_prod = self.srv_prod.calcular_jornada(jornada)

        jornada.hora_fin = instante
        jornada.tiempo_efectivo_seg = resultado_prod.tiempo_efectivo_seg
        jornada.productividad = resultado_prod.productividad_pct
        jornada.estado = EstadoJornada.CERRADA.value
        self.s.flush()

        resumen_wa = self.srv_wa.generar_texto_resumen(jornada, resultado_prod)

        ruta_pdf = None
        if generar_pdf:
            ruta_pdf = self.srv_pdf.generar_pdf_jornada(jornada)

        copia = None
        if ejecutar_backup:
            copia = self.srv_backups.crear_copia(TipoCopia.AUTOMATICA, momento=instante)

        return ResultadoCierreJornada(
            jornada=jornada,
            productividad=resultado_prod,
            texto_resumen_whatsapp=resumen_wa,
            copia_seguridad=copia,
            ruta_pdf=ruta_pdf,
        )
