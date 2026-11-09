"""Servicio de generación de reportes en PDF (RF-08, RF-05b, RF-06).

Genera los 4 tipos de PDF definidos en el plan:
1. **PDF general del día** (laboral): resumen, porcentaje y semáforo, actividades
   completadas, detalle de extras (solicitante, prioridad, aprobación, tiempo),
   pausas con motivos, actividades arrastradas y revisiones con sus motivos (sin alertas).
2. **PDF de día no laboral**: sin porcentaje de productividad, solo tiempo fuera
   de horario y actividades atendidas.
3. **PDF específico**: filtrado por actividad, categoría, solicitante o rango de fechas.
4. **PDF semanal o mensual**: resumen ejecutivo con tabla de evolución de tendencia,
   tiempo por categoría, estimado vs. real, solicitantes y revisiones.
"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import rutas
from data.enums import EstadoActividad, TipoActividad
from data.models import Actividad, Jornada, Pausa, Usuario
from data.repositorios.configuracion import RepoConfiguracion
from reports.generador_pdf import renderizar_html_a_pdf
from services.actividades import ServicioActividades
from services.estadisticas import ServicioEstadisticas
from services.historial import FiltrosHistorial, ServicioHistorial
from services.productividad import NivelSemaforo, ServicioProductividad
from services.whatsapp import formatear_duracion_corta


def _esc(texto: object) -> str:
    return html.escape("" if texto is None else str(texto))


def _color_semaforo(sem: NivelSemaforo) -> str:
    return {
        NivelSemaforo.EXCELENTE: "#16A34A",
        NivelSemaforo.ACEPTABLE: "#D97706",
        NivelSemaforo.POR_MEJORAR: "#DC2626",
        NivelSemaforo.NO_APLICA: "#64748B",
    }[sem]


def _envolver_html(
    *,
    titulo: str,
    subtitulo: str,
    empresa: str,
    usuario: str,
    cuerpo_html: str,
    color_primario: str = "#1E3A8A",
    logo_ruta: str | None = None,
) -> str:
    logo_html = ""
    if logo_ruta and Path(logo_ruta).is_file():
        uri = Path(logo_ruta).resolve().as_uri()
        logo_html = f'<img src="{uri}" height="42" style="margin-right:12px;" />'

    usr_txt = f"Colaborador: <b>{_esc(usuario)}</b>" if usuario else ""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
    color: #0F172A;
  }}
  h1 {{
    font-size: 16pt;
    color: {color_primario};
    margin: 0 0 4px 0;
  }}
  h2 {{
    font-size: 12pt;
    color: {color_primario};
    border-bottom: 1px solid #CBD5E1;
    padding-bottom: 3px;
    margin-top: 14px;
    margin-bottom: 6px;
  }}
  .meta {{
    color: #475569;
    font-size: 9pt;
    margin-bottom: 12px;
  }}
  .kpi-box {{
    border: 1px solid #CBD5E1;
    background-color: #F8FAFC;
    padding: 10px;
    margin-bottom: 12px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 10px;
  }}
  th {{
    background-color: #E2E8F0;
    color: #1E293B;
    text-align: left;
    padding: 5px 6px;
    font-size: 9pt;
    border: 1px solid #CBD5E1;
  }}
  td {{
    padding: 5px 6px;
    font-size: 9pt;
    border: 1px solid #CBD5E1;
  }}
  .pie {{
    color: #64748B;
    font-size: 8pt;
    margin-top: 18px;
    border-top: 1px solid #E2E8F0;
    padding-top: 6px;
  }}
</style>
</head>
<body>
  <div>{logo_html}<h1>{_esc(titulo)}</h1></div>
  <div class="meta">Empresa: <b>{_esc(empresa)}</b> &nbsp;|&nbsp; {usr_txt} &nbsp;|&nbsp; {_esc(subtitulo)}</div>
  {cuerpo_html}
  <div class="pie">Generado localmente por {rutas.NOMBRE_VISIBLE} v{rutas.VERSION}</div>
</body>
</html>"""


class ServicioReportesPDF:
    """Genera y guarda los reportes PDF de la aplicación."""

    def __init__(self, s: Session, carpeta_salida: Path | None = None) -> None:
        self.s = s
        self.config = RepoConfiguracion(s)
        self.srv_act = ServicioActividades(s)
        self.srv_prod = ServicioProductividad(s)
        self.srv_hist = ServicioHistorial(s)
        self.srv_est = ServicioEstadisticas(s)
        self.carpeta = carpeta_salida or rutas.carpeta_reportes()

    def _datos_cabecera(self) -> tuple[str, str, str, str | None]:
        usr = self.s.scalar(select(Usuario).limit(1))
        nombre_usr = usr.nombre.strip() if usr and usr.nombre else ""
        empresa = self.config.obtener("empresa.nombre", "Gente Util") or "Gente Util"
        color = self.config.obtener("empresa.color_primario", "#0F4C81") or "#0F4C81"
        logo = self.config.obtener("empresa.logo_ruta", None)
        if not logo or not Path(logo).is_file():
            defecto = rutas.ruta_logo_por_defecto()
            logo = str(defecto) if defecto.is_file() else None
        return empresa, nombre_usr, color, logo

    # ------------------------------------------------------------------
    # 1. PDF general del día y 4. PDF de día no laboral (RF-08, RF-05b)
    # ------------------------------------------------------------------

    def generar_pdf_jornada(
        self, jornada: Jornada, *, ruta_destino: Path | str | None = None
    ) -> Path:
        """Genera el PDF de cierre de ``jornada`` (laboral o día no laboral)."""
        if not jornada.es_laboral:
            return self.generar_pdf_dia_no_laboral(jornada, ruta_destino=ruta_destino)

        res = self.srv_prod.calcular_jornada(jornada)
        empresa, usuario, color_emp, logo = self._datos_cabecera()

        visibles = self.srv_act.listar_visibles_jornada(jornada.id)
        principales = [a for a in visibles if not a.es_revision]
        extras = [a for a in principales if a.tipo == TipoActividad.EXTRA.value]
        arrastradas = [
            a for a in principales if a.estado == EstadoActividad.ARRASTRADA.value
        ]
        revisiones = [a for a in visibles if a.es_revision]
        pausas = list(
            self.s.scalars(
                select(Pausa)
                .where(Pausa.jornada_id == jornada.id)
                .order_by(Pausa.inicio)
            )
        )

        color_sem = _color_semaforo(res.semaforo)
        prod_txt = f"{res.productividad_pct:.1f}%" if res.productividad_pct is not None else "N/A"
        c_txt = f"{res.cumplimiento_pct:.1f}%" if res.cumplimiento_pct is not None else "N/A"
        e_txt = f"{res.eficiencia_pct:.1f}%" if res.eficiencia_pct is not None else "N/A"
        f_txt = f"{res.foco_pct:.1f}%" if res.foco_pct is not None else "N/A"

        secciones: list[str] = [
            f"""
            <div class="kpi-box">
              <div style="font-size:13pt; font-weight:bold; color:{color_sem};">
                Productividad del día: {prod_txt} — {_esc(res.semaforo.etiqueta())}
              </div>
              <div style="margin-top:4px;">
                <b>Cumplimiento:</b> {c_txt} &nbsp;|&nbsp;
                <b>Eficiencia:</b> {e_txt} &nbsp;|&nbsp;
                <b>Foco:</b> {f_txt}
              </div>
              <div style="margin-top:4px;">
                <b>Tiempo efectivo:</b> {formatear_duracion_corta(res.tiempo_efectivo_seg)}
                (Meta: {formatear_duracion_corta(res.meta_tiempo_seg)} — {res.progreso_meta_pct:.0f}%) &nbsp;|&nbsp;
                <b>En pausas:</b> {formatear_duracion_corta(res.tiempo_pausas_seg)} &nbsp;|&nbsp;
                <b>Fuera de horario:</b> {formatear_duracion_corta(res.tiempo_fuera_horario_seg)}
              </div>
            </div>
            """
        ]

        # Tabla general de actividades del día
        secciones.append("<h2>Actividades de la jornada</h2>")
        secciones.append(self._tabla_actividades_html(principales))

        # Detalle de actividades extra
        if extras:
            secciones.append("<h2>Detalle de actividades extra</h2>")
            filas_ex = []
            for ex in extras:
                des = self.srv_act.desglose_tiempos(ex)
                sol = ex.solicitante.nombre if ex.solicitante else "—"
                filas_ex.append(
                    f"<tr>"
                    f"<td>{_esc(ex.nombre)}</td>"
                    f"<td>{_esc(sol)}</td>"
                    f"<td>{_esc(ex.prioridad)}</td>"
                    f"<td>{_esc(ex.aprobacion_estado)} ({_esc(ex.aprobacion_canal or '—')})</td>"
                    f"<td>{_esc(ex.motivo_urgencia or '—')}</td>"
                    f"<td>{formatear_duracion_corta(des.segundos_total)}</td>"
                    f"</tr>"
                )
            secciones.append(
                "<table><thead><tr>"
                "<th>Actividad extra</th><th>Solicitante</th><th>Prioridad</th>"
                "<th>Aprobación</th><th>Motivo urgencia</th><th>Tiempo</th>"
                "</tr></thead><tbody>" + "".join(filas_ex) + "</tbody></table>"
            )

        # Actividades arrastradas
        if arrastradas:
            secciones.append("<h2>Actividades arrastradas para continuar</h2>")
            filas_arr = [
                f"<tr><td>{_esc(a.nombre)}</td><td>{a.avance_pct or 0}%</td>"
                f"<td>{_esc(a.pausas[-1].motivo if a.pausas else a.notas or '—')}</td></tr>"
                for a in arrastradas
            ]
            secciones.append(
                "<table><thead><tr><th>Actividad</th><th>% Avance</th><th>Motivo</th></tr></thead>"
                "<tbody>" + "".join(filas_arr) + "</tbody></table>"
            )

        # Revisiones y sus motivos (sin alertas punitivas)
        secciones.append(f"<h2>Revisiones realizadas ({len(revisiones)})</h2>")
        if revisiones:
            filas_rev = []
            for rv in revisiones:
                sol_r = rv.revision_solicitante.nombre if rv.revision_solicitante else "—"
                seg_r = sum(s.duracion_seg for s in rv.sesiones)
                filas_rev.append(
                    f"<tr>"
                    f"<td>{_esc(rv.nombre)}</td>"
                    f"<td>{_esc(sol_r)}</td>"
                    f"<td>{_esc(rv.revision_tipo or '—')}</td>"
                    f"<td>{_esc(rv.revision_motivo or '—')}</td>"
                    f"<td>{_esc(rv.revision_que_cambiar or '—')}</td>"
                    f"<td>{formatear_duracion_corta(seg_r)}</td>"
                    f"</tr>"
                )
            secciones.append(
                "<table><thead><tr>"
                "<th>Revisión</th><th>Solicitante</th><th>Tipo</th>"
                "<th>Motivo</th><th>Cambio solicitado</th><th>Tiempo</th>"
                "</tr></thead><tbody>" + "".join(filas_rev) + "</tbody></table>"
            )
        else:
            secciones.append("<p>No se registraron revisiones en esta jornada.</p>")

        # Pausas e interrupciones
        if pausas:
            secciones.append("<h2>Pausas e interrupciones</h2>")
            filas_p = []
            for p in pausas:
                dur_p = (
                    formatear_duracion_corta(int((p.fin - p.inicio).total_seconds()))
                    if p.fin
                    else "abierta"
                )
                act_nom = p.actividad.nombre if p.actividad else "Jornada general"
                filas_p.append(
                    f"<tr><td>{_esc(p.tipo)}</td><td>{_esc(act_nom)}</td>"
                    f"<td>{p.inicio:%H:%M} – {p.fin.strftime('%H:%M') if p.fin else ''} ({dur_p})</td>"
                    f"<td>{_esc(p.motivo or '—')}</td></tr>"
                )
            secciones.append(
                "<table><thead><tr><th>Tipo</th><th>Actividad</th><th>Horario / Duración</th><th>Motivo</th></tr></thead>"
                "<tbody>" + "".join(filas_p) + "</tbody></table>"
            )

        html_doc = _envolver_html(
            titulo=f"Reporte Diario de Productividad — {jornada.fecha:%d/%m/%Y}",
            subtitulo=f"Fecha: {jornada.fecha:%d/%m/%Y}",
            empresa=empresa,
            usuario=usuario,
            cuerpo_html="\n".join(secciones),
            color_primario=color_emp,
            logo_ruta=logo,
        )

        destino = (
            Path(ruta_destino)
            if ruta_destino
            else self.carpeta / f"reporte_diario_{jornada.fecha:%Y%m%d}.pdf"
        )
        return renderizar_html_a_pdf(html_doc, destino)

    def generar_pdf_dia_no_laboral(
        self, jornada: Jornada, *, ruta_destino: Path | str | None = None
    ) -> Path:
        """Genera el PDF aparte para trabajo en día no laboral, sin porcentaje (RF-05b, RF-08)."""
        res = self.srv_prod.calcular_jornada(jornada)
        empresa, usuario, color_emp, logo = self._datos_cabecera()
        visibles = [
            a for a in self.srv_act.listar_visibles_jornada(jornada.id) if not a.es_revision
        ]

        cuerpo = f"""
        <div class="kpi-box">
          <b>Jornada en día no laboral ({jornada.fecha:%d/%m/%Y})</b><br/>
          Tiempo total trabajado fuera de horario:
          <b>{formatear_duracion_corta(res.tiempo_fuera_horario_seg)}</b><br/>
          <i>(De acuerdo con las reglas del equipo, las jornadas en días sin horario no calculan porcentaje de productividad).</i>
        </div>
        <h2>Actividades realizadas</h2>
        {self._tabla_actividades_html(visibles)}
        """

        html_doc = _envolver_html(
            titulo=f"Reporte de Día No Laboral — {jornada.fecha:%d/%m/%Y}",
            subtitulo=f"Fecha: {jornada.fecha:%d/%m/%Y} (Fuera de horario)",
            empresa=empresa,
            usuario=usuario,
            cuerpo_html=cuerpo,
            color_primario=color_emp,
            logo_ruta=logo,
        )
        destino = (
            Path(ruta_destino)
            if ruta_destino
            else self.carpeta / f"reporte_dia_no_laboral_{jornada.fecha:%Y%m%d}.pdf"
        )
        return renderizar_html_a_pdf(html_doc, destino)

    # ------------------------------------------------------------------
    # 2. PDF específico (por actividad, categoría, solicitante o fechas)
    # ------------------------------------------------------------------

    def generar_pdf_especifico(
        self,
        filtros: FiltrosHistorial,
        *,
        titulo_filtro: str = "Reporte específico",
        ruta_destino: Path | str | None = None,
    ) -> Path:
        empresa, usuario, color_emp, logo = self._datos_cabecera()
        actividades = [
            a for a in self.srv_hist.buscar_actividades(filtros) if not a.es_revision
        ]
        total_seg = sum(self.srv_act.desglose_tiempos(a).segundos_total for a in actividades)

        cuerpo = f"""
        <div class="kpi-box">
          <b>Filtro aplicado:</b> {_esc(titulo_filtro)}<br/>
          <b>Periodo:</b> {filtros.fecha_desde:%d/%m/%Y} al {filtros.fecha_hasta:%d/%m/%Y} &nbsp;|&nbsp;
          <b>Actividades encontradas:</b> {len(actividades)} &nbsp;|&nbsp;
          <b>Tiempo acumulado:</b> {formatear_duracion_corta(total_seg)}
        </div>
        <h2>Detalle de actividades</h2>
        {self._tabla_actividades_html(actividades, incluir_fecha=True)}
        """
        html_doc = _envolver_html(
            titulo=titulo_filtro,
            subtitulo=f"{filtros.fecha_desde:%d/%m/%Y} – {filtros.fecha_hasta:%d/%m/%Y}",
            empresa=empresa,
            usuario=usuario,
            cuerpo_html=cuerpo,
            color_primario=color_emp,
            logo_ruta=logo,
        )
        destino = (
            Path(ruta_destino)
            if ruta_destino
            else self.carpeta
            / f"reporte_especifico_{filtros.fecha_desde:%Y%m%d}_{filtros.fecha_hasta:%Y%m%d}.pdf"
        )
        return renderizar_html_a_pdf(html_doc, destino)

    # ------------------------------------------------------------------
    # 3. PDF semanal y mensual con tendencia
    # ------------------------------------------------------------------

    def generar_pdf_periodo(
        self,
        fecha_desde: date,
        fecha_hasta: date,
        *,
        etiqueta_periodo: str = "Semanal / Mensual",
        ruta_destino: Path | str | None = None,
    ) -> Path:
        empresa, usuario, color_emp, logo = self._datos_cabecera()
        est = self.srv_est.calcular(fecha_desde, fecha_hasta)

        prom_prod = (
            round(
                sum(p.productividad_pct for p in est.tendencia_diaria)
                / len(est.tendencia_diaria),
                1,
            )
            if est.tendencia_diaria
            else None
        )
        total_ef = sum(p.tiempo_efectivo_seg for p in est.tendencia_diaria)

        filas_tend = [
            f"<tr><td>{_esc(p.etiqueta)}</td><td>{p.productividad_pct:.1f}%</td>"
            f"<td>{formatear_duracion_corta(p.tiempo_efectivo_seg)}</td></tr>"
            for p in est.tendencia_diaria
        ]
        filas_cat = [
            f"<tr><td>{_esc(c.categoria_nombre)}</td><td>{c.cantidad_actividades}</td>"
            f"<td>{formatear_duracion_corta(c.segundos)}</td></tr>"
            for c in est.por_categoria
        ]
        filas_sol = [
            f"<tr><td>{_esc(s.solicitante_nombre)}</td><td>{s.cantidad_solicitudes}</td>"
            f"<td>{formatear_duracion_corta(s.segundos)}</td></tr>"
            for s in est.por_solicitante
        ]

        prom_txt = f"{prom_prod:.1f}%" if prom_prod is not None else "Sin jornadas laborales"
        cuerpo = f"""
        <div class="kpi-box">
          <b>Productividad promedio del periodo:</b> {prom_txt} &nbsp;|&nbsp;
          <b>Tiempo efectivo total:</b> {formatear_duracion_corta(total_ef)} &nbsp;|&nbsp;
          <b>Revisiones en el periodo:</b> {est.revisiones.total_revisiones}
        </div>
        <h2>Evolución diaria de productividad (Tendencia)</h2>
        <table><thead><tr><th>Día</th><th>Productividad</th><th>Tiempo efectivo</th></tr></thead>
        <tbody>{''.join(filas_tend) or '<tr><td colspan="3">Sin registros</td></tr>'}</tbody></table>

        <h2>Tiempo por categoría</h2>
        <table><thead><tr><th>Categoría</th><th>Actividades</th><th>Tiempo total</th></tr></thead>
        <tbody>{''.join(filas_cat) or '<tr><td colspan="3">Sin registros</td></tr>'}</tbody></table>

        <h2>Tiempo por solicitante</h2>
        <table><thead><tr><th>Solicitante</th><th>Solicitudes</th><th>Tiempo total</th></tr></thead>
        <tbody>{''.join(filas_sol) or '<tr><td colspan="3">Sin registros</td></tr>'}</tbody></table>
        """

        html_doc = _envolver_html(
            titulo=f"Reporte {etiqueta_periodo} — {fecha_desde:%d/%m/%Y} al {fecha_hasta:%d/%m/%Y}",
            subtitulo=f"Periodo: {fecha_desde:%d/%m/%Y} – {fecha_hasta:%d/%m/%Y}",
            empresa=empresa,
            usuario=usuario,
            cuerpo_html=cuerpo,
            color_primario=color_emp,
            logo_ruta=logo,
        )
        destino = (
            Path(ruta_destino)
            if ruta_destino
            else self.carpeta / f"reporte_periodo_{fecha_desde:%Y%m%d}_{fecha_hasta:%Y%m%d}.pdf"
        )
        return renderizar_html_a_pdf(html_doc, destino)

    # ------------------------------------------------------------------
    # Auxiliares HTML
    # ------------------------------------------------------------------

    def _tabla_actividades_html(
        self, actividades: list[Actividad], *, incluir_fecha: bool = False
    ) -> str:
        if not actividades:
            return "<p>No hay actividades registradas.</p>"

        col_fecha = "<th>Fecha</th>" if incluir_fecha else ""
        filas: list[str] = []
        for a in actividades:
            des = self.srv_act.desglose_tiempos(a)
            cat = a.categoria.nombre if a.categoria else "—"
            sol = f" ({a.solicitante.nombre})" if a.solicitante else ""
            est_min = f"{a.tiempo_estimado_min} min" if a.tiempo_estimado_min else "—"
            cambios = f"Sí ({des.cantidad_revisiones})" if des.solicitaron_cambios else "No"
            edit_marca = " [Editado]" if a.editado else ""
            td_fecha = (
                f"<td>{a.jornada.fecha:%d/%m/%Y}</td>"
                if incluir_fecha and a.jornada
                else ("<td>—</td>" if incluir_fecha else "")
            )
            filas.append(
                f"<tr>"
                f"{td_fecha}"
                f"<td><b>{_esc(a.nombre)}</b>{edit_marca}<br/>"
                f"<span style='color:#475569;'>{_esc(a.descripcion or '')}</span></td>"
                f"<td>{_esc(cat)}</td>"
                f"<td>{_esc(a.tipo)}{_esc(sol)}</td>"
                f"<td>{_esc(a.estado)}</td>"
                f"<td>{est_min}</td>"
                f"<td>{formatear_duracion_corta(des.segundos_total)}</td>"
                f"<td>{cambios}</td>"
                f"</tr>"
            )
        return (
            f"<table><thead><tr>{col_fecha}"
            "<th>Actividad / Descripción</th><th>Categoría</th><th>Tipo / Solicitante</th>"
            "<th>Estado</th><th>Estimado</th><th>Tiempo real</th><th>¿Cambios?</th>"
            "</tr></thead><tbody>" + "".join(filas) + "</tbody></table>"
        )
