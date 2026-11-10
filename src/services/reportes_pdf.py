"""Servicio de generación de reportes ejecutivos en PDF (RF-08, RF-05b, RF-06).

Genera los 4 tipos de PDF definidos en el plan con diseño ejecutivo corporativo
de Gente Util S.A.:
1. **PDF general del día** (laboral): encabezado con el logo oficial de Gente Util S.A.,
   ficha del colaborador, tarjetas KPI con semáforo, barras de sub-indicadores
   (Cumplimiento, Eficiencia, Foco), tabla de actividades con fila de totales,
   detalle de extras, actividades arrastradas, revisiones y pausas.
2. **PDF de día no laboral**: sin porcentaje de productividad, solo tiempo fuera
   de horario y actividades atendidas.
3. **PDF específico**: filtrado por actividad, categoría, solicitante o rango de fechas.
4. **PDF semanal o mensual**: resumen ejecutivo con tabla de evolución de tendencia,
   tiempo por categoría, estimado vs. real, solicitantes y revisiones.
"""

from __future__ import annotations

import base64
import html
from datetime import date, datetime
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


def _color_semaforo(sem: NivelSemaforo) -> tuple[str, str, str]:
    """Devuelve ``(color_texto, color_fondo, color_borde)`` según el nivel del semáforo."""
    return {
        NivelSemaforo.EXCELENTE: ("#15803D", "#F0FDF4", "#86EFAC"),
        NivelSemaforo.ACEPTABLE: ("#B45309", "#FFFBEB", "#FCD34D"),
        NivelSemaforo.POR_MEJORAR: ("#B91C1C", "#FEF2F2", "#FCA5A5"),
        NivelSemaforo.NO_APLICA: ("#475569", "#F8FAFC", "#CBD5E1"),
    }[sem]


_ETIQUETAS_TIPO_ACT = {
    "planeada": "Planeada",
    "extra": "Extra / Urgente",
    "no_planeada": "No planeada",
    "arrastrada": "Arrastrada",
}

_ETIQUETAS_ESTADO_ACT = {
    "completada": ("✓ Completada", "#15803D", "#DCFCE7"),
    "en_curso": ("▶ En curso", "#003D95", "#DBEAFE"),
    "pausada": ("⏸ Pausada", "#B45309", "#FEF3C7"),
    "arrastrada": ("↪ Arrastrada", "#9A3412", "#FFEDD5"),
    "pendiente": ("• Pendiente", "#475569", "#F1F5F9"),
    "aplazada": ("Aplazada", "#64748B", "#F1F5F9"),
    "rechazada": ("Rechazada", "#B91C1C", "#FEE2E2"),
    "eliminada": ("Eliminada", "#64748B", "#F1F5F9"),
}

_ETIQUETAS_PAUSA = {
    "almuerzo": "Almuerzo",
    "bano_hidratacion": "Baño / Hidratación",
    "pausa_activa": "Pausa activa",
    "reunion": "Reunión",
    "urgencia_aprobada": "Atención de urgencia",
    "esperando_insumos": "Esperando insumos / respuesta",
    "falla_tecnica": "Falla técnica / Luz / Internet",
    "fin_jornada": "Cierre / Fin de jornada",
    "personal": "Asunto personal",
    "otro": "Otro motivo",
}

_ETIQUETAS_PRIORIDAD = {
    "maxima": ("MÁXIMA", "#B91C1C"),
    "alta": ("Alta", "#D97706"),
    "media": ("Media", "#003D95"),
    "baja": ("Baja", "#475569"),
}

_ETIQUETAS_APROBACION = {
    "aprobado": "Aprobada",
    "aprobada": "Aprobada",
    "no_requiere": "Directa (Jefe / Doctoras)",
    "no_requerida": "Directa (Jefe / Doctoras)",
    "pendiente": "Pendiente",
    "rechazado": "Rechazada",
    "rechazada": "Rechazada",
}

_ETIQUETAS_MOTIVO_REV = {
    "error_propio": "Ajuste técnico propio",
    "cambio_criterio": "Cambio de criterio del solicitante",
    "info_incompleta": "Información inicial incompleta",
    "ajuste_estilo": "Ajuste de texto o estilo",
    "otro": "Otro",
}


def _logo_img_html(logo_ruta: str | None) -> str:
    """Incrusta el logo oficial en base64 con suavizado de alta calidad y proporción exacta."""
    if not logo_ruta:
        return ""
    p = Path(logo_ruta)
    if not p.is_file():
        return ""
    try:
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
        from PySide6.QtGui import QImage

        img = QImage(str(p))
        if not img.isNull() and img.height() > 0:
            alto = 68
            ancho = max(68, int(round(img.width() * (alto / img.height()))))
            if ancho > 220:
                ancho = 220
                alto = max(40, int(round(img.height() * (ancho / img.width()))))
            # Suavizado bicúbico previo (evita el escalado nearest-neighbor de QTextDocument)
            img_suave = img.scaled(
                ancho,
                alto,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            img_suave.save(buf, "PNG")
            b64 = bytes(ba.toBase64()).decode("ascii")
            return f'<img src="data:image/png;base64,{b64}" width="{ancho}" height="{alto}" />'

        raw = p.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        mime = "image/svg+xml" if p.suffix.lower() == ".svg" else "image/png"
        return f'<img src="data:{mime};base64,{b64}" width="180" height="68" />'
    except Exception:
        uri = p.resolve().as_uri()
        return f'<img src="{uri}" width="180" height="68" />'


def _barra_progreso_html(porcentaje: float | None, color: str = "#003D95") -> str:
    """Dibuja una barra de progreso horizontal compatible con ``QTextDocument``."""
    pct = max(0, min(100, int(round(porcentaje or 0.0))))
    if pct <= 0:
        return (
            '<table width="100%" cellspacing="0" cellpadding="0">'
            '<tr><td bgcolor="#E2E8F0" height="7" style="font-size:1pt;">&nbsp;</td></tr>'
            "</table>"
        )
    if pct >= 100:
        return (
            '<table width="100%" cellspacing="0" cellpadding="0">'
            f'<tr><td bgcolor="{color}" height="7" style="font-size:1pt;">&nbsp;</td></tr>'
            "</table>"
        )
    return (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        f'<td width="{pct}%" bgcolor="{color}" height="7" style="font-size:1pt;">&nbsp;</td>'
        f'<td width="{100 - pct}%" bgcolor="#E2E8F0" height="7" style="font-size:1pt;">&nbsp;</td>'
        "</tr></table>"
    )


def _titulo_seccion_html(numero: str, titulo: str, color_primario: str = "#003D95") -> str:
    """Genera un encabezado de sección corporativo con numeración y barra de acento."""
    return f"""
    <table width="100%" cellspacing="0" cellpadding="0" style="margin-top:14px; margin-bottom:6px;">
      <tr>
        <td width="24" bgcolor="{color_primario}" align="center" valign="middle"
            style="color:#FFFFFF; font-weight:bold; font-size:9pt; padding:4px 0;">
          {_esc(numero)}
        </td>
        <td bgcolor="#F1F5F9" valign="middle"
            style="color:#0F172A; font-weight:bold; font-size:10pt; padding:4px 10px; border-bottom:2px solid {color_primario};">
          {_esc(titulo.upper())}
        </td>
      </tr>
    </table>
    """


def _envolver_html(
    *,
    titulo: str,
    subtitulo: str,
    empresa: str,
    usuario: str,
    cargo_area: str = "",
    cuerpo_html: str,
    color_primario: str = "#003D95",
    logo_ruta: str | None = None,
) -> str:
    logo_html = _logo_img_html(logo_ruta)
    usr_mostrar = _esc(usuario) if usuario else "Sin registrar"
    cargo_mostrar = _esc(cargo_area) if cargo_area else "Diseño y Comunicaciones"
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")

    celda_logo = (
        f'<td width="34%" valign="middle" style="padding:2px 0;">{logo_html}</td>'
        if logo_html
        else f'<td width="34%" valign="middle"><b style="font-size:16pt; color:{color_primario};">{_esc(empresa)}</b></td>'
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 9pt;
    color: #0F172A;
    margin: 0;
    padding: 0;
  }}
  p {{
    margin: 4px 0;
  }}
  table.datos {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 8px;
  }}
  table.datos th {{
    background-color: {color_primario};
    color: #FFFFFF;
    text-align: left;
    padding: 6px 7px;
    font-size: 8.5pt;
    font-weight: bold;
    border: 1px solid {color_primario};
  }}
  table.datos td {{
    padding: 5px 7px;
    font-size: 8.5pt;
    color: #1E293B;
    border: 1px solid #CBD5E1;
  }}
</style>
</head>
<body>
  <!-- CABECERA CORPORATIVA GENTE UTIL S.A. -->
  <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:6px;">
    <tr>
      {celda_logo}
      <td width="66%" align="right" valign="middle">
        <div style="font-size:8pt; font-weight:bold; color:{color_primario}; letter-spacing:0.5px;">
          SISTEMA DE GESTIÓN Y CONTROL DE TIEMPOS
        </div>
        <div style="font-size:14pt; font-weight:bold; color:#0F172A; margin-top:2px;">
          {_esc(titulo)}
        </div>
        <div style="font-size:9pt; color:#475569; margin-top:2px;">
          {_esc(subtitulo)}
        </div>
      </td>
    </tr>
  </table>

  <!-- LÍNEA INSTITUCIONAL -->
  <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:8px;">
    <tr>
      <td width="78%" bgcolor="{color_primario}" height="3" style="font-size:1pt;">&nbsp;</td>
      <td width="22%" bgcolor="#D97706" height="3" style="font-size:1pt;">&nbsp;</td>
    </tr>
  </table>

  <!-- FICHA DE IDENTIFICACIÓN DEL REPORTE -->
  <table width="100%" cellspacing="0" cellpadding="6"
         style="background-color:#F8FAFC; border:1px solid #CBD5E1; margin-bottom:10px;">
    <tr>
      <td width="28%" style="border-right:1px solid #E2E8F0; font-size:8.5pt;">
        <span style="color:#64748B; font-size:7.5pt; font-weight:bold;">EMPRESA</span><br/>
        <b style="color:#0F172A;">{_esc(empresa)}</b>
      </td>
      <td width="28%" style="border-right:1px solid #E2E8F0; font-size:8.5pt;">
        <span style="color:#64748B; font-size:7.5pt; font-weight:bold;">COLABORADOR</span><br/>
        <b style="color:#0F172A;">{usr_mostrar}</b>
      </td>
      <td width="24%" style="border-right:1px solid #E2E8F0; font-size:8.5pt;">
        <span style="color:#64748B; font-size:7.5pt; font-weight:bold;">CARGO / ÁREA</span><br/>
        <span style="color:#1E293B;">{cargo_mostrar}</span>
      </td>
      <td width="20%" style="font-size:8.5pt;">
        <span style="color:#64748B; font-size:7.5pt; font-weight:bold;">EMISIÓN</span><br/>
        <span style="color:#1E293B;">{fecha_emision}</span>
      </td>
    </tr>
  </table>

  {cuerpo_html}

  <!-- BLOQUE DE FIRMAS Y PIE DE PÁGINA -->
  <table width="100%" cellspacing="0" cellpadding="0" style="margin-top:22px;">
    <tr>
      <td width="44%" align="center" style="padding-top:18px; border-top:1px solid #94A3B8; font-size:8pt; color:#334155;">
        <b>{usr_mostrar}</b><br/>
        <span style="color:#64748B;">Colaborador · {cargo_mostrar}</span>
      </td>
      <td width="12%">&nbsp;</td>
      <td width="44%" align="center" style="padding-top:18px; border-top:1px solid #94A3B8; font-size:8pt; color:#334155;">
        <b>Jefatura / Supervisión Inmediata</b><br/>
        <span style="color:#64748B;">{_esc(empresa)}</span>
      </td>
    </tr>
  </table>

  <table width="100%" cellspacing="0" cellpadding="0" style="margin-top:12px; border-top:1px solid #E2E8F0;">
    <tr>
      <td style="padding-top:5px; font-size:7.5pt; color:#64748B;">
        Documento generado localmente por <b>{rutas.NOMBRE_VISIBLE} v{rutas.VERSION}</b> — {_esc(empresa)}
      </td>
      <td align="right" style="padding-top:5px; font-size:7.5pt; color:#64748B;">
        Emitido el {fecha_emision}
      </td>
    </tr>
  </table>
</body>
</html>"""


class ServicioReportesPDF:
    """Genera y guarda los reportes PDF ejecutivos de la aplicación."""

    def __init__(self, s: Session, carpeta_salida: Path | None = None) -> None:
        self.s = s
        self.config = RepoConfiguracion(s)
        self.srv_act = ServicioActividades(s)
        self.srv_prod = ServicioProductividad(s)
        self.srv_hist = ServicioHistorial(s)
        self.srv_est = ServicioEstadisticas(s)
        self.carpeta = carpeta_salida or rutas.carpeta_reportes()

    def _datos_cabecera(self) -> tuple[str, str, str, str, str | None]:
        usr = self.s.scalar(select(Usuario).limit(1))
        nombre_usr = usr.nombre.strip() if usr and usr.nombre else ""
        partes_cargo = [
            p.strip()
            for p in ((usr.rol if usr else "") or "", (usr.area if usr else "") or "")
            if p and p.strip()
        ]
        cargo_area = " · ".join(partes_cargo) if partes_cargo else "Diseño y Comunicaciones"
        empresa = (
            self.config.obtener("empresa.nombre", "Gente Util S.A.") or "Gente Util S.A."
        )
        color = self.config.obtener("empresa.color_primario", "#003D95") or "#003D95"
        logo = self.config.obtener("empresa.logo_ruta", None)
        defecto = rutas.ruta_logo_por_defecto()
        if (
            not logo
            or not Path(logo).is_file()
            or Path(logo).name == "logo_gente_util.svg"
        ):
            logo = str(defecto) if defecto.is_file() else None
        return empresa, nombre_usr, cargo_area, color, logo

    # ------------------------------------------------------------------
    # 1. PDF general del día y 4. PDF de día no laboral (RF-08, RF-05b)
    # ------------------------------------------------------------------

    def generar_pdf_jornada(
        self, jornada: Jornada, *, ruta_destino: Path | str | None = None
    ) -> Path:
        """Genera el PDF ejecutivo de cierre de ``jornada`` (laboral o día no laboral)."""
        if not jornada.es_laboral:
            return self.generar_pdf_dia_no_laboral(jornada, ruta_destino=ruta_destino)

        res = self.srv_prod.calcular_jornada(jornada)
        empresa, usuario, cargo_area, color_emp, logo = self._datos_cabecera()

        visibles = self.srv_act.listar_visibles_jornada(jornada.id)
        principales = [a for a in visibles if not a.es_revision]
        completadas = [
            a for a in principales if a.estado == EstadoActividad.COMPLETADA.value
        ]
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

        col_sem_txt, col_sem_bg, col_sem_borde = _color_semaforo(res.semaforo)
        prod_txt = (
            f"{res.productividad_pct:.1f}%"
            if res.productividad_pct is not None
            else "N/A"
        )
        c_txt = (
            f"{res.cumplimiento_pct:.1f}%"
            if res.cumplimiento_pct is not None
            else "N/A"
        )
        e_txt = (
            f"{res.eficiencia_pct:.1f}%"
            if res.eficiencia_pct is not None
            else "N/A"
        )
        f_txt = f"{res.foco_pct:.1f}%" if res.foco_pct is not None else "N/A"

        secciones: list[str] = [
            # Tarjetas KPI Ejecutivas (4 columnas)
            f"""
            <table width="100%" cellspacing="0" cellpadding="8" style="margin-bottom:10px;">
              <tr>
                <td width="27%" valign="top"
                    style="background-color:{col_sem_bg}; border:2px solid {col_sem_borde};">
                  <div style="font-size:7.5pt; font-weight:bold; color:{col_sem_txt};">
                    PRODUCTIVIDAD DEL DÍA
                  </div>
                  <div style="font-size:18pt; font-weight:bold; color:{col_sem_txt}; margin:2px 0;">
                    {prod_txt}
                  </div>
                  <div style="font-size:8.5pt; font-weight:bold; color:{col_sem_txt};">
                    {_esc(res.semaforo.etiqueta().upper())}
                  </div>
                </td>
                <td width="2%" style="border:none;">&nbsp;</td>
                <td width="25%" valign="top"
                    style="background-color:#F8FAFC; border:1px solid #CBD5E1;">
                  <div style="font-size:7.5pt; font-weight:bold; color:#475569;">
                    TIEMPO EFECTIVO
                  </div>
                  <div style="font-size:14pt; font-weight:bold; color:{color_emp}; margin:3px 0;">
                    {formatear_duracion_corta(res.tiempo_efectivo_seg)}
                  </div>
                  <div style="font-size:8pt; color:#475569;">
                    Meta: <b>{formatear_duracion_corta(res.meta_tiempo_seg)}</b> ({res.progreso_meta_pct:.0f}%)
                  </div>
                </td>
                <td width="2%" style="border:none;">&nbsp;</td>
                <td width="22%" valign="top"
                    style="background-color:#F8FAFC; border:1px solid #CBD5E1;">
                  <div style="font-size:7.5pt; font-weight:bold; color:#475569;">
                    ACTIVIDADES
                  </div>
                  <div style="font-size:14pt; font-weight:bold; color:#0F172A; margin:3px 0;">
                    {len(completadas)} / {len(principales)}
                  </div>
                  <div style="font-size:8pt; color:#475569;">
                    Extras: <b>{len(extras)}</b> · Arrastradas: <b>{len(arrastradas)}</b>
                  </div>
                </td>
                <td width="2%" style="border:none;">&nbsp;</td>
                <td width="20%" valign="top"
                    style="background-color:#F8FAFC; border:1px solid #CBD5E1;">
                  <div style="font-size:7.5pt; font-weight:bold; color:#475569;">
                    PAUSAS Y EXTRAS
                  </div>
                  <div style="font-size:11pt; font-weight:bold; color:#0F172A; margin:3px 0;">
                    Pausas: {formatear_duracion_corta(res.tiempo_pausas_seg)}
                  </div>
                  <div style="font-size:8pt; color:#475569;">
                    Fuera hor.: <b>{formatear_duracion_corta(res.tiempo_fuera_horario_seg)}</b>
                  </div>
                </td>
              </tr>
            </table>
            """,
            # Desglose visual de los 3 sub-indicadores de la fórmula (40 / 30 / 30)
            f"""
            <table width="100%" cellspacing="0" cellpadding="6"
                   style="background-color:#FFFFFF; border:1px solid #CBD5E1; margin-bottom:10px;">
              <tr>
                <td width="33%" style="border-right:1px solid #E2E8F0;">
                  <div style="font-size:8pt; color:#334155; margin-bottom:3px;">
                    <b>1. Cumplimiento del plan</b> (peso 40%): <b style="color:{color_emp};">{c_txt}</b>
                  </div>
                  {_barra_progreso_html(res.cumplimiento_pct, color_emp)}
                </td>
                <td width="33%" style="border-right:1px solid #E2E8F0;">
                  <div style="font-size:8pt; color:#334155; margin-bottom:3px;">
                    <b>2. Eficiencia vs. estimado</b> (peso 30%): <b style="color:#0284C7;">{e_txt}</b>
                  </div>
                  {_barra_progreso_html(res.eficiencia_pct, "#0284C7")}
                </td>
                <td width="34%">
                  <div style="font-size:8pt; color:#334155; margin-bottom:3px;">
                    <b>3. Foco en jornada</b> (peso 30%): <b style="color:#15803D;">{f_txt}</b>
                  </div>
                  {_barra_progreso_html(res.foco_pct, "#15803D")}
                </td>
              </tr>
            </table>
            """,
        ]

        # 1. Tabla general de actividades del día
        secciones.append(
            _titulo_seccion_html("1", "Actividades de la jornada", color_emp)
        )
        secciones.append(self._tabla_actividades_html(principales))

        idx_sec = 2

        # 2. Detalle de actividades extra
        if extras:
            secciones.append(
                _titulo_seccion_html(
                    str(idx_sec), "Detalle de actividades extra y urgencias", color_emp
                )
            )
            idx_sec += 1
            filas_ex = []
            for i, ex in enumerate(extras):
                bg = "#FFFFFF" if i % 2 == 0 else "#F8FAFC"
                des = self.srv_act.desglose_tiempos(ex)
                sol = ex.solicitante.nombre if ex.solicitante else "—"
                prio_txt, prio_col = _ETIQUETAS_PRIORIDAD.get(
                    ex.prioridad or "media", (ex.prioridad or "Media", "#003D95")
                )
                aprob_txt = _ETIQUETAS_APROBACION.get(
                    ex.aprobacion_estado or "", ex.aprobacion_estado or "—"
                )
                canal_txt = f" ({ex.aprobacion_canal})" if ex.aprobacion_canal else ""
                filas_ex.append(
                    f'<tr style="background-color:{bg};">'
                    f"<td><b>{_esc(ex.nombre)}</b></td>"
                    f"<td>{_esc(sol)}</td>"
                    f'<td><b style="color:{prio_col};">{_esc(prio_txt)}</b></td>'
                    f"<td>{_esc(aprob_txt)}{_esc(canal_txt)}</td>"
                    f"<td>{_esc(ex.motivo_urgencia or '—')}</td>"
                    f'<td align="right"><b>{formatear_duracion_corta(des.segundos_total)}</b></td>'
                    f"</tr>"
                )
            secciones.append(
                '<table class="datos" width="100%" cellspacing="0" cellpadding="6"><thead><tr>'
                "<th>Actividad extra</th><th>Solicitante</th><th>Prioridad</th>"
                "<th>Aprobación</th><th>Motivo / Contexto</th><th>Tiempo real</th>"
                "</tr></thead><tbody>" + "".join(filas_ex) + "</tbody></table>"
            )

        # 3. Actividades arrastradas
        if arrastradas:
            secciones.append(
                _titulo_seccion_html(
                    str(idx_sec),
                    "Actividades arrastradas para la siguiente jornada",
                    color_emp,
                )
            )
            idx_sec += 1
            filas_arr = []
            for i, a in enumerate(arrastradas):
                bg = "#FFFFFF" if i % 2 == 0 else "#F8FAFC"
                motivo_arr = a.pausas[-1].motivo if a.pausas else (a.notas or "—")
                filas_arr.append(
                    f'<tr style="background-color:{bg};">'
                    f"<td><b>{_esc(a.nombre)}</b></td>"
                    f'<td width="18%" align="center"><b style="color:#B45309;">{a.avance_pct or 0}%</b></td>'
                    f"<td>{_esc(motivo_arr)}</td>"
                    f"</tr>"
                )
            secciones.append(
                '<table class="datos" width="100%" cellspacing="0" cellpadding="6"><thead><tr>'
                "<th>Actividad</th><th>% de Avance</th><th>Justificación / Motivo de arrastre</th>"
                "</tr></thead><tbody>" + "".join(filas_arr) + "</tbody></table>"
            )

        # 4. Revisiones y sus motivos
        secciones.append(
            _titulo_seccion_html(
                str(idx_sec),
                f"Revisiones y ajustes solicitados ({len(revisiones)})",
                color_emp,
            )
        )
        idx_sec += 1
        if revisiones:
            filas_rev = []
            for i, rv in enumerate(revisiones):
                bg = "#FFFFFF" if i % 2 == 0 else "#F8FAFC"
                sol_r = rv.revision_solicitante.nombre if rv.revision_solicitante else "—"
                seg_r = sum(s.duracion_seg for s in rv.sesiones)
                mot_r = _ETIQUETAS_MOTIVO_REV.get(
                    rv.revision_motivo or "", rv.revision_motivo or "—"
                )
                filas_rev.append(
                    f'<tr style="background-color:{bg};">'
                    f"<td><b>{_esc(rv.nombre)}</b></td>"
                    f"<td>{_esc(sol_r)}</td>"
                    f"<td>{_esc((rv.revision_tipo or '—').capitalize())}</td>"
                    f"<td>{_esc(mot_r)}</td>"
                    f"<td>{_esc(rv.revision_que_cambiar or '—')}</td>"
                    f'<td align="right"><b>{formatear_duracion_corta(seg_r)}</b></td>'
                    f"</tr>"
                )
            secciones.append(
                '<table class="datos" width="100%" cellspacing="0" cellpadding="6"><thead><tr>'
                "<th>Pieza / Actividad</th><th>Solicitante</th><th>Magnitud</th>"
                "<th>Causa</th><th>Detalle del ajuste</th><th>Tiempo</th>"
                "</tr></thead><tbody>" + "".join(filas_rev) + "</tbody></table>"
            )
        else:
            secciones.append(
                '<p style="color:#475569; font-style:italic;">No se registraron revisiones ni reprocesos durante esta jornada.</p>'
            )

        # 5. Pausas e interrupciones
        if pausas:
            secciones.append(
                _titulo_seccion_html(
                    str(idx_sec), "Registro de pausas e interrupciones", color_emp
                )
            )
            filas_p = []
            for i, p in enumerate(pausas):
                bg = "#FFFFFF" if i % 2 == 0 else "#F8FAFC"
                dur_p = (
                    formatear_duracion_corta(int((p.fin - p.inicio).total_seconds()))
                    if p.fin
                    else "En curso"
                )
                act_nom = p.actividad.nombre if p.actividad else "Jornada general"
                tipo_p = _ETIQUETAS_PAUSA.get(p.tipo, p.tipo)
                horario_p = f"{p.inicio:%H:%M} – {p.fin.strftime('%H:%M') if p.fin else '...'}"
                filas_p.append(
                    f'<tr style="background-color:{bg};">'
                    f"<td><b>{_esc(tipo_p)}</b></td>"
                    f"<td>{_esc(act_nom)}</td>"
                    f"<td>{horario_p} ({dur_p})</td>"
                    f"<td>{_esc(p.motivo or '—')}</td>"
                    f"</tr>"
                )
            secciones.append(
                '<table class="datos" width="100%" cellspacing="0" cellpadding="6"><thead><tr>'
                "<th>Tipo de pausa</th><th>Actividad asociada</th><th>Horario y duración</th><th>Observación / Motivo</th>"
                "</tr></thead><tbody>" + "".join(filas_p) + "</tbody></table>"
            )

        html_doc = _envolver_html(
            titulo="Reporte Diario de Productividad y Tiempos",
            subtitulo=f"Jornada laboral del {jornada.fecha:%d/%m/%Y}",
            empresa=empresa,
            usuario=usuario,
            cargo_area=cargo_area,
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
        empresa, usuario, cargo_area, color_emp, logo = self._datos_cabecera()
        visibles = [
            a
            for a in self.srv_act.listar_visibles_jornada(jornada.id)
            if not a.es_revision
        ]

        cuerpo = f"""
        <table width="100%" cellspacing="0" cellpadding="10"
               style="background-color:#EFF6FF; border:1px solid #93C5FD; margin-bottom:10px;">
          <tr>
            <td>
              <div style="font-size:10pt; font-weight:bold; color:{color_emp};">
                REGISTRO DE APOYO EN DÍA NO LABORAL ({jornada.fecha:%d/%m/%Y})
              </div>
              <div style="margin-top:4px; font-size:9pt; color:#1E293B;">
                Tiempo total invertido fuera de horario habitual:
                <b style="color:{color_emp}; font-size:11pt;">{formatear_duracion_corta(res.tiempo_fuera_horario_seg)}</b>
              </div>
              <div style="margin-top:3px; font-size:8pt; color:#475569; font-style:italic;">
                Nota: Conforme a los lineamientos de medición, el trabajo en días no laborales se reporta como tiempo adicional y no genera calificación porcentual de productividad.
              </div>
            </td>
          </tr>
        </table>
        {_titulo_seccion_html("1", "Actividades atendidas", color_emp)}
        {self._tabla_actividades_html(visibles)}
        """

        html_doc = _envolver_html(
            titulo="Reporte de Actividades en Día No Laboral",
            subtitulo=f"Fecha: {jornada.fecha:%d/%m/%Y} · Registro fuera de horario",
            empresa=empresa,
            usuario=usuario,
            cargo_area=cargo_area,
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
        titulo_filtro: str = "Reporte específico de actividades",
        ruta_destino: Path | str | None = None,
    ) -> Path:
        empresa, usuario, cargo_area, color_emp, logo = self._datos_cabecera()
        actividades = [
            a for a in self.srv_hist.buscar_actividades(filtros) if not a.es_revision
        ]
        total_seg = sum(
            self.srv_act.desglose_tiempos(a).segundos_total for a in actividades
        )
        completadas = sum(
            1 for a in actividades if a.estado == EstadoActividad.COMPLETADA.value
        )

        cuerpo = f"""
        <table width="100%" cellspacing="0" cellpadding="8"
               style="background-color:#F8FAFC; border:1px solid #CBD5E1; margin-bottom:10px;">
          <tr>
            <td width="36%" style="border-right:1px solid #E2E8F0;">
              <span style="font-size:7.5pt; color:#64748B; font-weight:bold;">CRITERIO / FILTRO</span><br/>
              <b style="font-size:9.5pt; color:{color_emp};">{_esc(titulo_filtro)}</b>
            </td>
            <td width="26%" style="border-right:1px solid #E2E8F0;">
              <span style="font-size:7.5pt; color:#64748B; font-weight:bold;">PERIODO CONSULTADO</span><br/>
              <b>{filtros.fecha_desde:%d/%m/%Y} al {filtros.fecha_hasta:%d/%m/%Y}</b>
            </td>
            <td width="18%" style="border-right:1px solid #E2E8F0;">
              <span style="font-size:7.5pt; color:#64748B; font-weight:bold;">ACTIVIDADES</span><br/>
              <b>{len(actividades)}</b> ({completadas} compl.)
            </td>
            <td width="20%">
              <span style="font-size:7.5pt; color:#64748B; font-weight:bold;">TIEMPO ACUMULADO</span><br/>
              <b style="font-size:10.5pt; color:{color_emp};">{formatear_duracion_corta(total_seg)}</b>
            </td>
          </tr>
        </table>
        {_titulo_seccion_html("1", "Detalle de actividades encontradas", color_emp)}
        {self._tabla_actividades_html(actividades, incluir_fecha=True)}
        """
        html_doc = _envolver_html(
            titulo=titulo_filtro,
            subtitulo=f"Periodo del {filtros.fecha_desde:%d/%m/%Y} al {filtros.fecha_hasta:%d/%m/%Y}",
            empresa=empresa,
            usuario=usuario,
            cargo_area=cargo_area,
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
        empresa, usuario, cargo_area, color_emp, logo = self._datos_cabecera()
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

        filas_tend = []
        for i, p in enumerate(est.tendencia_diaria):
            bg = "#FFFFFF" if i % 2 == 0 else "#F8FAFC"
            col_p = (
                "#15803D"
                if p.productividad_pct >= 85
                else ("#B45309" if p.productividad_pct >= 60 else "#B91C1C")
            )
            filas_tend.append(
                f'<tr style="background-color:{bg};">'
                f"<td><b>{_esc(p.etiqueta)}</b></td>"
                f'<td width="22%" align="center"><b style="color:{col_p};">{p.productividad_pct:.1f}%</b></td>'
                f'<td width="38%">{_barra_progreso_html(p.productividad_pct, col_p)}</td>'
                f'<td width="20%" align="right"><b>{formatear_duracion_corta(p.tiempo_efectivo_seg)}</b></td>'
                f"</tr>"
            )

        filas_cat = [
            f'<tr style="background-color:{"#FFFFFF" if i % 2 == 0 else "#F8FAFC"};">'
            f"<td><b>{_esc(c.categoria_nombre)}</b></td>"
            f'<td align="center">{c.cantidad_actividades}</td>'
            f'<td align="right"><b>{formatear_duracion_corta(c.segundos)}</b></td></tr>'
            for i, c in enumerate(est.por_categoria)
        ]
        filas_sol = [
            f'<tr style="background-color:{"#FFFFFF" if i % 2 == 0 else "#F8FAFC"};">'
            f"<td><b>{_esc(s.solicitante_nombre)}</b></td>"
            f'<td align="center">{s.cantidad_solicitudes}</td>'
            f'<td align="right"><b>{formatear_duracion_corta(s.segundos)}</b></td></tr>'
            for i, s in enumerate(est.por_solicitante)
        ]

        prom_txt = (
            f"{prom_prod:.1f}%" if prom_prod is not None else "Sin jornadas cerradas"
        )
        cuerpo = f"""
        <table width="100%" cellspacing="0" cellpadding="8"
               style="background-color:#F8FAFC; border:1px solid #CBD5E1; margin-bottom:10px;">
          <tr>
            <td width="34%" style="border-right:1px solid #E2E8F0;">
              <span style="font-size:7.5pt; color:#64748B; font-weight:bold;">PRODUCTIVIDAD PROMEDIO</span><br/>
              <b style="font-size:14pt; color:{color_emp};">{prom_txt}</b>
            </td>
            <td width="33%" style="border-right:1px solid #E2E8F0;">
              <span style="font-size:7.5pt; color:#64748B; font-weight:bold;">TIEMPO EFECTIVO ACUMULADO</span><br/>
              <b style="font-size:14pt; color:#0F172A;">{formatear_duracion_corta(total_ef)}</b>
            </td>
            <td width="33%">
              <span style="font-size:7.5pt; color:#64748B; font-weight:bold;">REVISIONES EN EL PERIODO</span><br/>
              <b style="font-size:14pt; color:#0F172A;">{est.revisiones.total_revisiones}</b>
            </td>
          </tr>
        </table>

        {_titulo_seccion_html("1", "Evolución diaria de productividad (Tendencia)", color_emp)}
        <table class="datos" width="100%" cellspacing="0" cellpadding="6"><thead><tr><th>Jornada</th><th>Productividad</th><th>Nivel alcanzado</th><th>Tiempo efectivo</th></tr></thead>
        <tbody>{''.join(filas_tend) or '<tr><td colspan="4">Sin registros en el periodo</td></tr>'}</tbody></table>

        {_titulo_seccion_html("2", "Distribución de tiempo por categoría", color_emp)}
        <table class="datos" width="100%" cellspacing="0" cellpadding="6"><thead><tr><th>Categoría de trabajo</th><th>Actividades</th><th>Tiempo invertido</th></tr></thead>
        <tbody>{''.join(filas_cat) or '<tr><td colspan="3">Sin registros en el periodo</td></tr>'}</tbody></table>

        {_titulo_seccion_html("3", "Tiempo invertido por solicitante", color_emp)}
        <table class="datos" width="100%" cellspacing="0" cellpadding="6"><thead><tr><th>Solicitante / Área</th><th>Solicitudes atendidas</th><th>Tiempo invertido</th></tr></thead>
        <tbody>{''.join(filas_sol) or '<tr><td colspan="3">Sin registros en el periodo</td></tr>'}</tbody></table>
        """

        html_doc = _envolver_html(
            titulo=f"Reporte Consolidado {etiqueta_periodo}",
            subtitulo=f"Periodo evaluado: {fecha_desde:%d/%m/%Y} al {fecha_hasta:%d/%m/%Y}",
            empresa=empresa,
            usuario=usuario,
            cargo_area=cargo_area,
            cuerpo_html=cuerpo,
            color_primario=color_emp,
            logo_ruta=logo,
        )
        destino = (
            Path(ruta_destino)
            if ruta_destino
            else self.carpeta
            / f"reporte_periodo_{fecha_desde:%Y%m%d}_{fecha_hasta:%Y%m%d}.pdf"
        )
        return renderizar_html_a_pdf(html_doc, destino)

    # ------------------------------------------------------------------
    # Auxiliares HTML
    # ------------------------------------------------------------------

    def _tabla_actividades_html(
        self, actividades: list[Actividad], *, incluir_fecha: bool = False
    ) -> str:
        if not actividades:
            return '<p style="color:#475569; font-style:italic;">No hay actividades registradas en este bloque.</p>'

        col_fecha = "<th>Fecha</th>" if incluir_fecha else ""
        filas: list[str] = []
        total_estimado_min = 0
        total_real_seg = 0

        for i, a in enumerate(actividades):
            bg = "#FFFFFF" if i % 2 == 0 else "#F8FAFC"
            des = self.srv_act.desglose_tiempos(a)
            total_real_seg += des.segundos_total
            if a.tiempo_estimado_min:
                total_estimado_min += int(a.tiempo_estimado_min)

            cat = a.categoria.nombre if a.categoria else "General"
            tipo_legible = _ETIQUETAS_TIPO_ACT.get(a.tipo, a.tipo.capitalize())
            sol = f"<br/><span style='color:#475569; font-size:7.5pt;'>Solicita: {_esc(a.solicitante.nombre)}</span>" if a.solicitante else ""
            est_txt, est_col, _est_bg = _ETIQUETAS_ESTADO_ACT.get(
                a.estado, (a.estado.capitalize(), "#334155", "#F1F5F9")
            )
            est_min = f"{a.tiempo_estimado_min} min" if a.tiempo_estimado_min else "—"
            cambios = (
                f'<b style="color:#B45309;">Sí ({des.cantidad_revisiones})</b>'
                if des.solicitaron_cambios
                else '<span style="color:#64748B;">No</span>'
            )
            edit_marca = (
                ' <span style="color:#64748B; font-size:7.5pt;">[Editado]</span>'
                if a.editado
                else ""
            )
            desc_html = (
                f"<br/><span style='color:#475569; font-size:8pt;'>{_esc(a.descripcion)}</span>"
                if a.descripcion and a.descripcion.strip()
                else ""
            )
            td_fecha = (
                f"<td>{a.jornada.fecha:%d/%m/%Y}</td>"
                if incluir_fecha and a.jornada
                else ("<td>—</td>" if incluir_fecha else "")
            )
            filas.append(
                f'<tr style="background-color:{bg};">'
                f"{td_fecha}"
                f"<td><b>{_esc(a.nombre)}</b>{edit_marca}{desc_html}</td>"
                f"<td>{_esc(cat)}</td>"
                f"<td><b>{_esc(tipo_legible)}</b>{sol}</td>"
                f'<td><b style="color:{est_col};">{_esc(est_txt)}</b></td>'
                f'<td align="right">{est_min}</td>'
                f'<td align="right"><b>{formatear_duracion_corta(des.segundos_total)}</b></td>'
                f'<td align="center">{cambios}</td>'
                f"</tr>"
            )

        colspan_tot = 5 if incluir_fecha else 4
        est_tot_str = (
            formatear_duracion_corta(total_estimado_min * 60)
            if total_estimado_min > 0
            else "—"
        )
        fila_total = (
            f'<tr style="background-color:#E2E8F0; font-weight:bold;">'
            f'<td colspan="{colspan_tot}" align="right">TOTALES ({len(actividades)} actividades):</td>'
            f'<td align="right"><b>{est_tot_str}</b></td>'
            f'<td align="right"><b style="color:#003D95;">{formatear_duracion_corta(total_real_seg)}</b></td>'
            f"<td>&nbsp;</td>"
            f"</tr>"
        )

        return (
            f'<table class="datos" width="100%" cellspacing="0" cellpadding="6"><thead><tr>{col_fecha}'
            "<th>Actividad y descripción</th><th>Categoría</th><th>Origen / Solicitante</th>"
            "<th>Estado</th><th>Estimado</th><th>Tiempo real</th><th>Revisiones</th>"
            "</tr></thead><tbody>" + "".join(filas) + fila_total + "</tbody></table>"
        )
