"""Herramientas de soporte para la Fase 8 (Beta personal y Beta de equipo).

Incluye:
- ``simular_pesos_formula``: recalcula Cumplimiento, Eficiencia, Foco y el
  porcentaje total de un rango de fechas con pesos alternativos (sin modificar
  la base de datos), ideal para la sesión de validación de la fórmula 40/30/30
  con el Ing. Luis Eduardo.
- ``exportar_informe_validacion_beta``: genera un informe Markdown con la
  comparativa de pesos, el desglose diario y el estado de salud de la BD.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from config.rutas import carpeta_reportes
from data.models import Jornada
from services.productividad import NivelSemaforo, ServicioProductividad


@dataclass
class ComparacionDiaFormula:
    """Resultado de un día al comparar los pesos actuales contra pesos propuestos."""

    fecha: date
    cumplimiento_pct: float | None
    eficiencia_pct: float | None
    foco_pct: float | None
    total_actual_pct: float | None
    semaforo_actual: str
    total_propuesto_pct: float | None
    semaforo_propuesto: str


class ServicioBeta:
    """Utilidades para validar la fórmula de productividad durante la beta."""

    def __init__(self, sesion: Session) -> None:
        self._s = sesion
        self._prod = ServicioProductividad(sesion)

    @staticmethod
    def _combinar_con_pesos(
        cumplimiento: float | None,
        eficiencia: float | None,
        foco: float | None,
        peso_c: float,
        peso_e: float,
        peso_f: float,
    ) -> float:
        """Combina los sub-indicadores disponibles normalizando los pesos."""
        componentes: list[tuple[float, float]] = []
        if cumplimiento is not None:
            componentes.append((cumplimiento, peso_c))
        if eficiencia is not None:
            componentes.append((eficiencia, peso_e))
        if foco is not None:
            componentes.append((foco, peso_f))
        peso_activo = sum(p for _, p in componentes)
        if peso_activo <= 0:
            return 0.0
        return round(sum(v * (p / peso_activo) for v, p in componentes), 1)

    @staticmethod
    def _semaforo_por_pct(pct: float) -> NivelSemaforo:
        if pct >= 85.0:
            return NivelSemaforo.EXCELENTE
        if pct >= 60.0:
            return NivelSemaforo.ACEPTABLE
        return NivelSemaforo.POR_MEJORAR

    def simular_pesos_formula(
        self,
        desde: date,
        hasta: date,
        *,
        peso_cumplimiento: float,
        peso_eficiencia: float,
        peso_foco: float,
    ) -> list[ComparacionDiaFormula]:
        """Compara el % actual de cada jornada laboral con otra combinación de pesos."""
        jornadas = list(
            self._s.scalars(
                select(Jornada)
                .where(
                    Jornada.fecha >= desde,
                    Jornada.fecha <= hasta,
                    Jornada.es_laboral.is_(True),
                )
                .order_by(Jornada.fecha)
            )
        )
        salida: list[ComparacionDiaFormula] = []
        for j in jornadas:
            res = self._prod.calcular_jornada(j)
            if not res.es_laboral:
                continue
            propuesto = self._combinar_con_pesos(
                res.cumplimiento_pct,
                res.eficiencia_pct,
                res.foco_pct,
                peso_cumplimiento,
                peso_eficiencia,
                peso_foco,
            )
            sem_prop = self._semaforo_por_pct(propuesto)
            salida.append(
                ComparacionDiaFormula(
                    fecha=j.fecha,
                    cumplimiento_pct=res.cumplimiento_pct,
                    eficiencia_pct=res.eficiencia_pct,
                    foco_pct=res.foco_pct,
                    total_actual_pct=res.productividad_pct,
                    semaforo_actual=res.semaforo.value,
                    total_propuesto_pct=propuesto,
                    semaforo_propuesto=sem_prop.value,
                )
            )
        return salida

    def exportar_informe_validacion_beta(
        self,
        desde: date,
        hasta: date,
        *,
        peso_cumplimiento: float = 40.0,
        peso_eficiencia: float = 30.0,
        peso_foco: float = 30.0,
        ruta_destino: Path | None = None,
    ) -> Path:
        """Exporta un archivo Markdown con el análisis de la fórmula en el periodo."""
        comparaciones = self.simular_pesos_formula(
            desde,
            hasta,
            peso_cumplimiento=peso_cumplimiento,
            peso_eficiencia=peso_eficiencia,
            peso_foco=peso_foco,
        )
        lineas = [
            "# Informe de Validación de Fórmula (Beta — Gente Util)",
            "",
            f"- **Periodo evaluado:** {desde.isoformat()} a {hasta.isoformat()}",
            (
                f"- **Pesos simulados:** Cumplimiento {peso_cumplimiento:.0f} % · "
                f"Eficiencia {peso_eficiencia:.0f} % · Foco {peso_foco:.0f} %"
            ),
            "",
            "| Fecha | Cumplimiento | Eficiencia | Foco | % Actual | % Simulado | Semáforo Simulado |",
            "|---|---|---|---|---|---|---|",
        ]
        for c in comparaciones:
            cump = f"{c.cumplimiento_pct:.1f} %" if c.cumplimiento_pct is not None else "—"
            efic = f"{c.eficiencia_pct:.1f} %" if c.eficiencia_pct is not None else "—"
            foco = f"{c.foco_pct:.1f} %" if c.foco_pct is not None else "—"
            act = f"{c.total_actual_pct:.1f} %" if c.total_actual_pct is not None else "—"
            prop = f"{c.total_propuesto_pct:.1f} %" if c.total_propuesto_pct is not None else "—"
            lineas.append(
                f"| {c.fecha.isoformat()} | {cump} | {efic} | {foco} | "
                f"{act} | {prop} | {c.semaforo_propuesto} |"
            )

        destino = ruta_destino or (
            carpeta_reportes() / f"validacion_beta_{desde.isoformat()}_{hasta.isoformat()}.md"
        )
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        return destino
