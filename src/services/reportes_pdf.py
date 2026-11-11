"""Generación de reportes PDF corporativos elegantes y gráficos (RF-08, RF-10).

Cuatro modalidades unificadas sobre ``LienzoPDF``:
1. Reporte diario laboral (productividad, tiempo efectivo en jornada, línea de tiempo y tablas).
2. Reporte de día no laboral (registro de trabajo fuera de horario).
3. Reporte específico con filtros (rango de fechas, categoría, solicitante o tipo).
4. Reporte periódico Semanal o Mensual (tendencia diaria, comparativos y desviación).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import rutas
from data.enums import (
    EstadoActividad,
    MotivoRevision,
    Prioridad,
    TipoActividad,
    TipoRevision,
)
from data.models import Actividad, Horario, Jornada, SesionTiempo, Usuario
from data.repositorios.configuracion import RepoConfiguracion
from data.repositorios.horarios import RepoHorarios
from data.tiempo import ahora
from reports.generador_pdf import (
    ANCHO_CONTENIDO,
    MARGEN_X,
    LienzoPDF,
    PaletaPDF,
)
from reports.graficos_pdf import (
    BloqueHorarioTimeline,
    ItemBarraHorizontal,
    ItemEstimadoRealGrafico,
    PuntoTendenciaGrafico,
    SegmentoTimeline,
    color_por_nivel_pct,
    dibujar_barras_horizontales,
    dibujar_card_kpi_donut,
    dibujar_card_kpi_jornada,
    dibujar_card_kpi_metrica,
    dibujar_card_subindicadores,
    dibujar_desglose_revisiones,
    dibujar_estimado_vs_real,
    dibujar_tendencia_vertical,
    dibujar_timeline_jornada,
)
from services.actividades import ServicioActividades
from services.estadisticas import ServicioEstadisticas
from services.historial import FiltrosHistorial, ServicioHistorial
from services.productividad import NivelSemaforo, ServicioProductividad
from services.whatsapp import formatear_duracion_corta

_DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
_DIAS_CORTOS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
_MESES_ES = [
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]

_ETIQUETAS_MOTIVO_REV = {e.value: e.etiqueta() for e in MotivoRevision}
_ETIQUETAS_TIPO_REV = {e.value: e.etiqueta() for e in TipoRevision}
_ETIQUETAS_ESTADO = {e.value: e.etiqueta() for e in EstadoActividad}
_ETIQUETAS_PRIORIDAD = {e.value: e.etiqueta() for e in Prioridad}
_ETIQUETAS_TIPO_ACT = {e.value: e.etiqueta() for e in TipoActividad}


@dataclass(frozen=True)
class _DatosCabecera:
    """Metadatos corporativos y del colaborador para la portada del reporte."""

    usuario: str
    cargo: str
    area: str
    empresa: str
    color_primario: str
    ruta_logo: str | None
    emitido: str


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    """Devuelve '1 elemento' o 'N elementos' según gramática en español."""
    if plural is None:
        plural = singular + ("es" if singular[-1:] in "dlrnzj" else "s")
    return f"{n} {singular if n == 1 else plural}"


def _fecha_larga_es(f: date) -> str:
    return f"{_DIAS_ES[f.weekday()]}, {f.day} de {_MESES_ES[f.month]} de {f.year}"


def _etiqueta_tipo(tipo: str) -> str:
    return _ETIQUETAS_TIPO_ACT.get(tipo, tipo.replace("_", " ").capitalize())


def _etiqueta_estado(act: Actividad) -> str:
    if act.estado == EstadoActividad.ARRASTRADA.value:
        return f"Arrastrada ({act.avance_pct or 0}%)"
    if act.estado in _ETIQUETAS_ESTADO:
        return _ETIQUETAS_ESTADO[act.estado]
    return act.estado.replace("_", " ").capitalize()


def _etiqueta_prioridad(prio: str) -> str:
    return _ETIQUETAS_PRIORIDAD.get(prio, prio.capitalize())


def _colores_semaforo(semaforo: NivelSemaforo, pal: PaletaPDF) -> tuple[QColor, QColor, QColor]:
    """Devuelve ``(fondo_pill, texto_pill, arco)`` acorde con el semáforo."""
    mapa = {
        NivelSemaforo.EXCELENTE: (pal.verde_suave, pal.verde, pal.verde),
        NivelSemaforo.ACEPTABLE: (pal.ambar_suave, pal.ambar, pal.ambar),
        NivelSemaforo.POR_MEJORAR: (pal.rojo_suave, pal.rojo, pal.rojo),
        NivelSemaforo.NO_APLICA: (pal.neutro_suave, pal.neutro, pal.neutro),
    }
    return mapa.get(semaforo, (pal.neutro_suave, pal.neutro, pal.neutro))


def _color_sesion(act: Actividad, pal: PaletaPDF) -> QColor:
    if act.es_revision:
        return pal.rojo
    if act.tipo == TipoActividad.PLANEADA.value:
        return pal.azul
    if act.tipo == TipoActividad.EXTRA.value:
        return pal.ambar
    return pal.morado


def _minutos_dia(dt: datetime) -> float:
    return dt.hour * 60.0 + dt.minute + dt.second / 60.0


def _etiqueta_horario_bloques(bloques: list[Horario]) -> str:
    if not bloques:
        return "Día sin horario programado"
    partes = [f"{b.hora_inicio:%H:%M}–{b.hora_fin:%H:%M}" for b in bloques]
    return "Horario: " + " · ".join(partes)


def _cargar_cabecera(s: Session) -> _DatosCabecera:
    usuario = s.scalars(select(Usuario).limit(1)).first()
    cfg = RepoConfiguracion(s)
    nombre_usr = (usuario.nombre or "").strip() if usuario else ""
    cargo_cfg = (cfg.obtener("usuario.cargo", "") or "").strip()
    area_cfg = (cfg.obtener("usuario.area", "") or "").strip()
    logo_cfg = cfg.obtener("empresa.logo_ruta", "") or ""
    ruta_logo = Path(logo_cfg) if logo_cfg and Path(logo_cfg).exists() else rutas.ruta_logo_por_defecto()
    return _DatosCabecera(
        usuario=nombre_usr or "Colaborador",
        cargo=cargo_cfg or "Sin especificar",
        area=area_cfg or "Sin especificar",
        empresa=cfg.obtener("empresa.nombre", "Gente Util") or "Gente Util",
        color_primario=cfg.obtener("empresa.color_primario", "#003D95") or "#003D95",
        ruta_logo=str(ruta_logo) if ruta_logo and ruta_logo.exists() else None,
        emitido=ahora().strftime("%d/%m/%Y %H:%M"),
    )


def _limpiar_nombre_archivo(texto: str) -> str:
    limpio = "".join(c if c.isalnum() or c in "-_" else "_" for c in texto.lower())
    return limpio[:40].strip("_") or "reporte"


class ServicioReportesPDF:
    """Construye los 4 tipos de reporte PDF corporativos listos para dirección."""

    def __init__(self, s: Session) -> None:
        self.s = s
        self.srv_act = ServicioActividades(s)
        self.srv_hist = ServicioHistorial(s)
        self.srv_prod = ServicioProductividad(s)
        self.srv_est = ServicioEstadisticas(s)

    # ------------------------------------------------------------------
    # Recolección de datos gráficos auxiliares
    # ------------------------------------------------------------------

    def _construir_timeline_dia(
        self,
        jornada: Jornada,
        actividades: list[Actividad],
        pal: PaletaPDF,
    ) -> tuple[list[BloqueHorarioTimeline], list[SegmentoTimeline], str]:
        bloques_bd = RepoHorarios(self.s).bloques_del_dia(jornada.fecha.weekday())
        bloques = [
            BloqueHorarioTimeline(
                inicio_min=b.hora_inicio.hour * 60 + b.hora_inicio.minute,
                fin_min=b.hora_fin.hour * 60 + b.hora_fin.minute,
            )
            for b in bloques_bd
        ]

        segmentos: list[SegmentoTimeline] = []
        inicios_sesion: list[datetime] = []
        fines_sesion: list[datetime] = []
        conteo_ses = 0

        act_ids = {a.id: a for a in actividades}
        inicio_dia = datetime.combine(jornada.fecha, time.min)
        fin_dia = datetime.combine(jornada.fecha, time.max)
        sesiones = list(
            self.s.scalars(
                select(SesionTiempo)
                .where(SesionTiempo.inicio >= inicio_dia, SesionTiempo.inicio <= fin_dia)
                .order_by(SesionTiempo.inicio.asc())
            )
        )
        for ses in sesiones:
            act = act_ids.get(ses.actividad_id) or self.s.get(Actividad, ses.actividad_id)
            if act is None or act.estado == EstadoActividad.ELIMINADA.value:
                continue
            ini_dt = ses.inicio
            fin_dt = ses.fin or ini_dt
            if fin_dt < ini_dt:
                fin_dt = ini_dt
            inicios_sesion.append(ini_dt)
            fines_sesion.append(fin_dt)
            conteo_ses += 1
            segmentos.append(
                SegmentoTimeline(
                    inicio_min=_minutos_dia(ini_dt),
                    fin_min=max(_minutos_dia(ini_dt) + 2.0, _minutos_dia(fin_dt)),
                    etiqueta=act.nombre,
                    color=_color_sesion(act, pal),
                    es_pausa=False,
                    es_fuera_horario=bool(ses.fuera_horario),
                )
            )

        if inicios_sesion:
            primera = min(inicios_sesion).strftime("%H:%M")
            ultima = max(fines_sesion).strftime("%H:%M")
            resumen = (
                f"Primera actividad: {primera}  ·  Última actividad: {ultima}  ·  "
                f"{_plural(conteo_ses, 'sesión', 'sesiones')}"
            )
        else:
            resumen = "No se registraron sesiones activas durante la jornada"

        return bloques, segmentos, resumen

    def _tiempos_directos_actividad(
        self,
        act: Actividad,
        *,
        solo_fecha: date | None = None,
    ) -> tuple[int, int, int, int]:
        """Devuelve ``(seg_directo, seg_fuera_horario, cant_revs_hijas, seg_revs_hijas)``.

        Evita duplicar el tiempo de la tarea raíz sobre sus filas de revisión hijas.
        """
        consulta = select(SesionTiempo).where(SesionTiempo.actividad_id == act.id)
        if solo_fecha is not None:
            consulta = consulta.where(
                SesionTiempo.inicio >= datetime.combine(solo_fecha, time.min),
                SesionTiempo.inicio <= datetime.combine(solo_fecha, time.max),
            )
        sesiones = list(self.s.scalars(consulta))
        seg_dir = sum(s.duracion_seg for s in sesiones)
        seg_fh = sum(s.duracion_seg for s in sesiones if s.fuera_horario)

        if act.es_revision:
            return seg_dir, seg_fh, 0, 0

        revs = list(
            self.s.scalars(
                select(Actividad).where(
                    Actividad.actividad_padre_id == act.id,
                    Actividad.estado != EstadoActividad.ELIMINADA.value,
                )
            )
        )
        seg_rev = 0
        for r in revs:
            q_rev = select(SesionTiempo).where(SesionTiempo.actividad_id == r.id)
            if solo_fecha is not None:
                q_rev = q_rev.where(
                    SesionTiempo.inicio >= datetime.combine(solo_fecha, time.min),
                    SesionTiempo.inicio <= datetime.combine(solo_fecha, time.max),
                )
            seg_rev += sum(sr.duracion_seg for sr in self.s.scalars(q_rev))
        return seg_dir, seg_fh, len(revs), seg_rev

    def _agrupar_categorias_actividades(
        self,
        actividades: list[Actividad],
        pal: PaletaPDF,
        *,
        solo_fecha: date | None = None,
    ) -> list[ItemBarraHorizontal]:
        """Agrupa segundos directos invertidos por categoría sin duplicar revisiones."""
        totales: dict[str, tuple[int, int, QColor]] = {}
        for act in actividades:
            seg, _, _, _ = self._tiempos_directos_actividad(act, solo_fecha=solo_fecha)
            if seg <= 0:
                continue
            cat_nom = act.categoria.nombre if act.categoria else "Sin categoría"
            cat_hex = act.categoria.color if act.categoria and act.categoria.color else None
            col = QColor(cat_hex) if cat_hex else pal.primario
            if not col.isValid():
                col = pal.primario
            prev_seg, prev_cnt, prev_col = totales.get(cat_nom, (0, 0, col))
            totales[cat_nom] = (prev_seg + seg, prev_cnt + 1, prev_col)

        gran_total = sum(v[0] for v in totales.values()) or 1
        salida: list[ItemBarraHorizontal] = []
        for nom, (seg, cnt, col) in sorted(totales.items(), key=lambda x: x[1][0], reverse=True):
            pct = seg / gran_total * 100.0
            salida.append(
                ItemBarraHorizontal(
                    etiqueta=nom,
                    valor=float(seg),
                    texto_valor=f"{formatear_duracion_corta(seg)} ({pct:.0f}%)",
                    color=col,
                    subetiqueta=f"{cnt} act.",
                )
            )
        return salida

    def _revisiones_jornada(self, jornada_id: int) -> list[Actividad]:
        return list(
            self.s.scalars(
                select(Actividad)
                .where(
                    Actividad.jornada_id == jornada_id,
                    Actividad.es_revision.is_(True),
                    Actividad.estado != EstadoActividad.ELIMINADA.value,
                )
                .order_by(Actividad.creada_en.asc())
            )
        )

    # ------------------------------------------------------------------
    # Tablas compartidas (Actividades y Revisiones)
    # ------------------------------------------------------------------

    def _dibujar_tabla_actividades_dia(
        self,
        lienzo: LienzoPDF,
        actividades: list[Actividad],
        titulo_seccion: str,
        *,
        con_fecha: bool = False,
        solo_fecha: date | None = None,
    ) -> None:
        if not actividades:
            lienzo.dibujar_seccion(titulo_seccion, alto_min_siguiente=38.0)
            lienzo.dibujar_nota_vacia("No se registraron actividades en esta sección.")
            return

        filas: list[list[str]] = []
        total_seg_global = 0
        total_revs_global = 0

        for act in actividades:
            seg_dir, seg_fh, cant_revs, seg_revs = self._tiempos_directos_actividad(
                act, solo_fecha=solo_fecha
            )
            total_seg_global += seg_dir
            total_revs_global += cant_revs

            cat = act.categoria.nombre if act.categoria else "Sin categoría"
            sol = act.solicitante.nombre if act.solicitante else "Iniciativa propia"

            detalles_nom = [act.nombre]
            if act.descripcion:
                desc_corta = act.descripcion.strip()
                if len(desc_corta) > 130:
                    desc_corta = desc_corta[:127] + "..."
                detalles_nom.append(desc_corta)
            detalles_nom.append(f"Solicita: {sol} · Prioridad {_etiqueta_prioridad(act.prioridad)}")
            if act.es_revision:
                detalles_nom.append("↩ Actividad de revisión / devolución")

            est_txt = _etiqueta_estado(act)
            nota_est = (act.motivo_urgencia or act.reasignacion_motivo or act.notas or "").strip()
            if nota_est:
                mot_corto = nota_est[:52] + "..." if len(nota_est) > 55 else nota_est
                est_txt = f"{est_txt}\n{mot_corto}"

            tiempo_lineas = [formatear_duracion_corta(seg_dir)]
            if seg_fh > 0:
                tiempo_lineas.append(f"Extra: {formatear_duracion_corta(seg_fh)}")
            if act.tiempo_estimado_min:
                tiempo_lineas.append(f"Est: {act.tiempo_estimado_min} min")

            cambios_txt = f"{cant_revs} rev." if cant_revs > 0 else "Sin cambios"
            if seg_revs > 0:
                cambios_txt += f"\n({formatear_duracion_corta(seg_revs)})"

            tipo_cat_txt = f"{cat}\n[{_etiqueta_tipo(act.tipo)}]"

            if con_fecha:
                fecha_txt = act.jornada.fecha.strftime("%d/%m/%Y") if act.jornada else "—"
                filas.append(
                    [
                        fecha_txt,
                        "\n".join(detalles_nom),
                        tipo_cat_txt,
                        est_txt,
                        "\n".join(tiempo_lineas),
                    ]
                )
            else:
                filas.append(
                    [
                        "\n".join(detalles_nom),
                        tipo_cat_txt,
                        est_txt,
                        "\n".join(tiempo_lineas),
                        cambios_txt,
                    ]
                )

        if con_fecha:
            # 744 px exactos: 72 + 312 + 132 + 116 + 112 = 744
            columnas = [
                ("Fecha", 72.0, Qt.AlignmentFlag.AlignLeft),
                ("Actividad y detalle", 312.0, Qt.AlignmentFlag.AlignLeft),
                ("Categoría y Tipo", 132.0, Qt.AlignmentFlag.AlignLeft),
                ("Estado", 116.0, Qt.AlignmentFlag.AlignLeft),
                ("Tiempo", 112.0, Qt.AlignmentFlag.AlignRight),
            ]
            fila_totales = [
                "Total",
                _plural(len(actividades), "actividad registrada", "actividades registradas"),
                "—",
                "—",
                formatear_duracion_corta(total_seg_global),
            ]
        else:
            # 744 px exactos: 304 + 128 + 106 + 110 + 96 = 744
            columnas = [
                ("Actividad y detalle", 304.0, Qt.AlignmentFlag.AlignLeft),
                ("Categoría y Tipo", 128.0, Qt.AlignmentFlag.AlignLeft),
                ("Estado", 106.0, Qt.AlignmentFlag.AlignLeft),
                ("Tiempo", 110.0, Qt.AlignmentFlag.AlignRight),
                ("Cambios", 96.0, Qt.AlignmentFlag.AlignRight),
            ]
            fila_totales = [
                f"Total ({_plural(len(actividades), 'actividad', 'actividades')})",
                "—",
                "—",
                formatear_duracion_corta(total_seg_global),
                f"{total_revs_global} rev.",
            ]

        lienzo.dibujar_seccion(
            titulo_seccion,
            subtitulo=f"{_plural(len(actividades), 'registro')} · {formatear_duracion_corta(total_seg_global)}",
            alto_min_siguiente=78.0,
        )
        lienzo.dibujar_tabla_paginada(columnas, filas, fila_totales=fila_totales)

    def _dibujar_resumen_destacados_dia(
        self,
        lienzo: LienzoPDF,
        extras: list[Actividad],
        arrastradas_pend: list[Actividad],
        fecha_dia: date,
    ) -> None:
        """Tabla compacta sin duplicación de extras y pendientes/arrastradas del día."""
        if not extras and not arrastradas_pend:
            return
        filas: list[list[str]] = []
        vistos: set[tuple[str, int]] = set()
        for act in extras:
            vistos.add(("extra", act.id))
            seg_dir, _, _, _ = self._tiempos_directos_actividad(act, solo_fecha=fecha_dia)
            sol = act.solicitante.nombre if act.solicitante else "Iniciativa propia"
            filas.append(
                [
                    "Extra atendida",
                    act.nombre,
                    f"{sol} · {_etiqueta_estado(act)}",
                    formatear_duracion_corta(seg_dir),
                ]
            )
        for act in arrastradas_pend:
            seg_dir, _, _, _ = self._tiempos_directos_actividad(act, solo_fecha=fecha_dia)
            nota = (act.notas or act.motivo_urgencia or "Continúa en próxima jornada").strip()
            filas.append(
                [
                    _etiqueta_estado(act),
                    act.nombre,
                    nota[:85] + "..." if len(nota) > 88 else nota,
                    formatear_duracion_corta(seg_dir),
                ]
            )

        # 128 + 250 + 266 + 100 = 744 px
        columnas = [
            ("Situación", 128.0, Qt.AlignmentFlag.AlignLeft),
            ("Actividad", 250.0, Qt.AlignmentFlag.AlignLeft),
            ("Solicitante / Seguimiento", 266.0, Qt.AlignmentFlag.AlignLeft),
            ("Tiempo", 100.0, Qt.AlignmentFlag.AlignRight),
        ]
        lienzo.dibujar_seccion(
            "Extras y seguimiento de cierre",
            subtitulo=_plural(len(filas), "destacado"),
            alto_min_siguiente=78.0,
        )
        lienzo.dibujar_tabla_paginada(columnas, filas, tam_pt=7.8)

    def _dibujar_seccion_revisiones(
        self, lienzo: LienzoPDF, revisiones: list[Actividad], *, solo_fecha: date | None = None
    ) -> None:
        if not revisiones:
            return
        filas: list[list[str]] = []
        total_seg = 0
        for r in revisiones:
            seg_dir, _, _, _ = self._tiempos_directos_actividad(r, solo_fecha=solo_fecha)
            total_seg += seg_dir
            sol = (
                r.revision_solicitante.nombre
                if r.revision_solicitante
                else (r.solicitante.nombre if r.solicitante else "—")
            )
            tipo_lbl = _ETIQUETAS_TIPO_REV.get(r.revision_tipo or "", r.revision_tipo or "—")
            mot_lbl = _ETIQUETAS_MOTIVO_REV.get(r.revision_motivo or "", r.revision_motivo or "—")
            comentario = (r.revision_que_cambiar or r.descripcion or r.notas or "—").strip()
            filas.append(
                [
                    r.nombre,
                    f"{tipo_lbl}\n{mot_lbl}",
                    sol,
                    formatear_duracion_corta(seg_dir),
                    comentario,
                ]
            )
        # 200 + 128 + 126 + 96 + 194 = 744 px ("Tiempo" tiene 96 px: imposible partirse)
        columnas = [
            ("Actividad", 200.0, Qt.AlignmentFlag.AlignLeft),
            ("Tipo / Motivo", 128.0, Qt.AlignmentFlag.AlignLeft),
            ("Solicitante", 126.0, Qt.AlignmentFlag.AlignLeft),
            ("Tiempo", 96.0, Qt.AlignmentFlag.AlignRight),
            ("Observación", 194.0, Qt.AlignmentFlag.AlignLeft),
        ]
        totales = [
            f"Total ({_plural(len(revisiones), 'revisión', 'revisiones')})",
            "—",
            "—",
            formatear_duracion_corta(total_seg),
            "—",
        ]
        lienzo.dibujar_seccion(
            "Revisiones y devoluciones",
            subtitulo=f"{_plural(len(revisiones), 'ajuste')} · {formatear_duracion_corta(total_seg)}",
            alto_min_siguiente=78.0,
        )
        lienzo.dibujar_tabla_paginada(columnas, filas, fila_totales=totales)

    # ------------------------------------------------------------------
    # 1. Reporte Diario Laboral
    # ------------------------------------------------------------------

    def generar_pdf_jornada(
        self,
        jornada: Jornada,
        ruta_destino: Path | str | None = None,
    ) -> Path:
        """Genera el reporte PDF diario (delega a no laboral si aplica)."""
        if not jornada.es_laboral or jornada.duracion_jornada_seg <= 0:
            return self.generar_pdf_dia_no_laboral(jornada, ruta_destino=ruta_destino)

        cab = _cargar_cabecera(self.s)
        res = self.srv_prod.calcular_jornada(jornada)
        actividades = self.srv_act.listar_visibles_jornada(jornada.id)
        revisiones = self._revisiones_jornada(jornada.id)
        bloques_bd = RepoHorarios(self.s).bloques_del_dia(jornada.fecha.weekday())

        destino = (
            Path(ruta_destino)
            if ruta_destino
            else rutas.carpeta_reportes() / f"Reporte_Diario_{jornada.fecha:%Y-%m-%d}.pdf"
        )
        lienzo = LienzoPDF(
            destino,
            titulo_doc="Reporte Diario de Productividad",
            empresa=cab.empresa,
            subtitulo_continuacion=_fecha_larga_es(jornada.fecha),
            color_primario=cab.color_primario,
            emitido_texto=cab.emitido,
        )
        pal = lienzo.paleta

        # 1. Banner corporativo + ficha colaborador
        lienzo.dibujar_cabecera_hero(
            eyebrow=f"{cab.empresa} · Gestión de Productividad",
            titulo="Reporte Diario de Productividad",
            subtitulo=_fecha_larga_es(jornada.fecha),
            estado_badge=jornada.estado.upper(),
            horario_texto=_etiqueta_horario_bloques(bloques_bd),
            ruta_logo=cab.ruta_logo,
        )
        lienzo.dibujar_tira_metadatos(
            [
                ("Colaborador", cab.usuario),
                ("Cargo", cab.cargo),
                ("Área", cab.area),
                ("Jornada programada", formatear_duracion_corta(res.duracion_jornada_seg)),
            ]
        )

        # 2. Fila de 4 tarjetas KPI gráficas (SIN "Meta: 6h17min")
        y_kpi = lienzo.y
        gap = 10.0
        w_card = (ANCHO_CONTENIDO - 3.0 * gap) / 4.0
        h_card = 114.0

        f_sem, t_sem, arc_sem = _colores_semaforo(res.semaforo, pal)
        dibujar_card_kpi_donut(
            lienzo,
            QRectF(MARGEN_X, y_kpi, w_card, h_card),
            eyebrow="Productividad",
            pct=res.productividad_pct,
            etiqueta_badge=res.semaforo.etiqueta(),
            fondo_badge=f_sem,
            texto_badge=t_sem,
            subtitulo="Índice ponderado de desempeño diario.",
            color_arco=arc_sem,
        )

        ef_seg = res.tiempo_efectivo_seg
        pct_jor = (
            (ef_seg / res.duracion_jornada_seg * 100.0)
            if res.duracion_jornada_seg > 0
            else 0.0
        )
        faltante_seg = max(0, res.duracion_jornada_seg - ef_seg)
        sub_ef_2 = (
            f"Faltante en horario: {formatear_duracion_corta(faltante_seg)}"
            if faltante_seg > 0
            else "Horario laboral cubierto"
        )
        dibujar_card_kpi_jornada(
            lienzo,
            QRectF(MARGEN_X + (w_card + gap), y_kpi, w_card, h_card),
            efectivo_txt=formatear_duracion_corta(ef_seg),
            jornada_txt=formatear_duracion_corta(res.duracion_jornada_seg),
            pct_cobertura=pct_jor,
            efectivo_seg=ef_seg,
            jornada_seg=res.duracion_jornada_seg,
            sublinea_1="Solo trabajo activo (sin pausas)",
            sublinea_2=sub_ef_2,
        )

        comp_tot = sum(1 for a in actividades if a.estado == EstadoActividad.COMPLETADA.value)
        rev_comp = sum(
            1
            for a in actividades
            if a.es_revision and a.estado == EstadoActividad.COMPLETADA.value
        )
        total_prog = max(len(actividades), res.planeadas_total)
        sub_tipos = (
            f"{res.planeadas_completadas} plan. · {res.extras_completadas} extra · "
            f"{res.no_planeadas_completadas} no plan."
            + (f" · {rev_comp} rev." if rev_comp > 0 else "")
        )
        dibujar_card_kpi_metrica(
            lienzo,
            QRectF(MARGEN_X + 2.0 * (w_card + gap), y_kpi, w_card, h_card),
            eyebrow="Actividades",
            valor=f"{comp_tot} / {total_prog}",
            color_acento=pal.verde,
            sublinea_1=sub_tipos,
            sublinea_2=f"{res.arrastradas} arrastradas · {res.pendientes} pendientes",
            barra_segmentos=[
                (float(res.planeadas_completadas), pal.azul),
                (float(res.extras_completadas), pal.ambar),
                (float(res.no_planeadas_completadas), pal.morado),
                (float(rev_comp), pal.rojo),
            ],
            barra_total=float(max(total_prog, comp_tot, 1)),
        )

        trabajado_tot_seg = res.tiempo_trabajado_total_seg
        dibujar_card_kpi_metrica(
            lienzo,
            QRectF(MARGEN_X + 3.0 * (w_card + gap), y_kpi, w_card, h_card),
            eyebrow="Tiempo trabajado total",
            valor=formatear_duracion_corta(trabajado_tot_seg),
            color_acento=pal.morado,
            sublinea_1=f"En horario: {formatear_duracion_corta(ef_seg)}",
            sublinea_2=f"Fuera de horario: {formatear_duracion_corta(res.tiempo_fuera_horario_seg)}",
            barra_segmentos=[
                (float(ef_seg), pal.primario),
                (float(res.tiempo_fuera_horario_seg), pal.morado),
            ],
            barra_total=float(max(trabajado_tot_seg, 1)),
        )
        lienzo.y = y_kpi + h_card + 12.0

        # 3. Fila analítica: Subindicadores (izq) + Línea de tiempo Gantt (der)
        w_c = round(RepoConfiguracion(self.s).obtener_float("productividad.peso_cumplimiento", 0.40) * 100)
        w_e = round(RepoConfiguracion(self.s).obtener_float("productividad.peso_eficiencia", 0.30) * 100)
        w_f = round(RepoConfiguracion(self.s).obtener_float("productividad.peso_foco", 0.30) * 100)
        nota_pesos = f"Pesos: Cumpl. {w_c}% · Efic. {w_e}% · Foco {w_f}%"
        if res.eficiencia_pct is None:
            nota_pesos += " (Efic. se pondera al tener estimados)."

        y_ana = lienzo.y
        h_ana = 174.0
        dibujar_card_subindicadores(
            lienzo,
            QRectF(MARGEN_X, y_ana, 248.0, h_ana),
            cumplimiento_pct=res.cumplimiento_pct,
            eficiencia_pct=res.eficiencia_pct,
            foco_pct=res.foco_pct,
            nota_pesos=nota_pesos,
        )
        bloques_tl, segs_tl, resumen_tl = self._construir_timeline_dia(
            jornada, actividades, pal
        )
        dibujar_timeline_jornada(
            lienzo,
            QRectF(MARGEN_X + 260.0, y_ana, ANCHO_CONTENIDO - 260.0, h_ana),
            bloques=bloques_tl,
            segmentos=segs_tl,
            resumen_pie=resumen_tl,
        )
        lienzo.y = y_ana + h_ana + 12.0

        # 4. Gráfico de distribución por categoría (compacto)
        items_cat = self._agrupar_categorias_actividades(
            actividades, pal, solo_fecha=jornada.fecha
        )
        if items_cat:
            est_h = 48.0 + min(6, len(items_cat)) * 26.0
            lienzo.asegurar_espacio(est_h + 10.0)
            usado_cat = dibujar_barras_horizontales(
                lienzo,
                QRectF(MARGEN_X, lienzo.y, ANCHO_CONTENIDO, est_h),
                titulo="Distribución de tiempo por categoría",
                items=items_cat,
                max_items=6,
            )
            lienzo.y += usado_cat + 14.0

        # 5. Tablas detalladas auto-paginadas (sin duplicar tiempos ni repetir tablas)
        self._dibujar_tabla_actividades_dia(
            lienzo,
            actividades,
            "Detalle de actividades del día",
            solo_fecha=jornada.fecha,
        )

        extras = [a for a in actividades if a.tipo == TipoActividad.EXTRA.value]
        arrastradas_pend = [
            a
            for a in actividades
            if a.estado in (EstadoActividad.ARRASTRADA.value, EstadoActividad.PENDIENTE.value)
        ]
        self._dibujar_resumen_destacados_dia(lienzo, extras, arrastradas_pend, jornada.fecha)

        self._dibujar_seccion_revisiones(lienzo, revisiones, solo_fecha=jornada.fecha)

        # 6. Firmas
        lienzo.dibujar_firmas(cab.usuario)
        return lienzo.finalizar()

    # ------------------------------------------------------------------
    # 2. Reporte Día No Laboral
    # ------------------------------------------------------------------

    def generar_pdf_dia_no_laboral(
        self,
        jornada: Jornada,
        ruta_destino: Path | str | None = None,
    ) -> Path:
        """Genera el reporte para sábado no laboral, domingo o festivo."""
        cab = _cargar_cabecera(self.s)
        res = self.srv_prod.calcular_jornada(jornada)
        actividades = self.srv_act.listar_visibles_jornada(jornada.id)

        destino = (
            Path(ruta_destino)
            if ruta_destino
            else rutas.carpeta_reportes() / f"Reporte_no_laboral_{jornada.fecha:%Y-%m-%d}.pdf"
        )
        lienzo = LienzoPDF(
            destino,
            titulo_doc="Registro de Día No Laboral",
            empresa=cab.empresa,
            subtitulo_continuacion=_fecha_larga_es(jornada.fecha),
            color_primario=cab.color_primario,
            emitido_texto=cab.emitido,
        )
        pal = lienzo.paleta

        lienzo.dibujar_cabecera_hero(
            eyebrow=f"{cab.empresa} · Registro Extraordinario",
            titulo="Registro de Día No Laboral",
            subtitulo=_fecha_larga_es(jornada.fecha),
            estado_badge="NO LABORAL",
            horario_texto="Sin porcentaje de productividad aplicable",
            ruta_logo=cab.ruta_logo,
        )
        lienzo.dibujar_tira_metadatos(
            [
                ("Colaborador", cab.usuario),
                ("Cargo", cab.cargo),
                ("Área", cab.area),
                ("Clasificación", "Trabajo fuera de horario"),
            ]
        )

        # 3 tarjetas KPI ejecutivas
        y_kpi = lienzo.y
        gap = 12.0
        w3 = (ANCHO_CONTENIDO - 2.0 * gap) / 3.0
        h3 = 100.0
        completadas = sum(
            1 for a in actividades if a.estado == EstadoActividad.COMPLETADA.value
        )
        dibujar_card_kpi_metrica(
            lienzo,
            QRectF(MARGEN_X, y_kpi, w3, h3),
            eyebrow="Tiempo fuera de horario",
            valor=formatear_duracion_corta(res.tiempo_fuera_horario_seg),
            color_acento=pal.primario,
            sublinea_1="Todo el tiempo trabajado en días no",
            sublinea_2="laborales se contabiliza como extra.",
        )
        dibujar_card_kpi_metrica(
            lienzo,
            QRectF(MARGEN_X + (w3 + gap), y_kpi, w3, h3),
            eyebrow="Actividades registradas",
            valor=str(len(actividades)),
            color_acento=pal.verde,
            sublinea_1=f"Completadas: {completadas}",
            sublinea_2=f"En seguimiento: {len(actividades) - completadas}",
        )
        dibujar_card_kpi_metrica(
            lienzo,
            QRectF(MARGEN_X + 2.0 * (w3 + gap), y_kpi, w3, h3),
            eyebrow="Estado de la jornada",
            valor=jornada.estado.upper(),
            color_acento=pal.azul,
            sublinea_1="Solo tiempo trabajado activo",
            sublinea_2="Las pausas no se contabilizan",
        )
        lienzo.y = y_kpi + h3 + 12.0

        # Línea de tiempo + categorías
        bloques_tl, segs_tl, resumen_tl = self._construir_timeline_dia(
            jornada, actividades, pal
        )
        if segs_tl:
            dibujar_timeline_jornada(
                lienzo,
                QRectF(MARGEN_X, lienzo.y, ANCHO_CONTENIDO, 168.0),
                bloques=bloques_tl,
                segmentos=segs_tl,
                resumen_pie=resumen_tl,
            )
            lienzo.y += 180.0

        items_cat = self._agrupar_categorias_actividades(
            actividades, pal, solo_fecha=jornada.fecha
        )
        if items_cat:
            est_h = 48.0 + min(6, len(items_cat)) * 26.0
            lienzo.asegurar_espacio(est_h + 10.0)
            usado = dibujar_barras_horizontales(
                lienzo,
                QRectF(MARGEN_X, lienzo.y, ANCHO_CONTENIDO, est_h),
                titulo="Tiempo por categoría en día no laboral",
                items=items_cat,
            )
            lienzo.y += usado + 12.0

        self._dibujar_tabla_actividades_dia(
            lienzo,
            actividades,
            "Actividades registradas",
            solo_fecha=jornada.fecha,
        )
        lienzo.dibujar_firmas(cab.usuario)
        return lienzo.finalizar()

    # ------------------------------------------------------------------
    # 3. Reporte Específico por Filtros
    # ------------------------------------------------------------------

    def generar_pdf_especifico(
        self,
        filtros: FiltrosHistorial,
        titulo_filtro: str = "Reporte específico",
        ruta_destino: Path | str | None = None,
    ) -> Path:
        """Genera un reporte filtrado por fecha, categoría, solicitante o tipo."""
        cab = _cargar_cabecera(self.s)
        actividades = self.srv_hist.buscar_actividades(filtros)

        rango_txt = "Todo el historial disponible"
        if filtros.fecha_desde and filtros.fecha_hasta:
            rango_txt = f"{filtros.fecha_desde:%d/%m/%Y} al {filtros.fecha_hasta:%d/%m/%Y}"
        elif filtros.fecha_desde:
            rango_txt = f"Desde {filtros.fecha_desde:%d/%m/%Y}"
        elif filtros.fecha_hasta:
            rango_txt = f"Hasta {filtros.fecha_hasta:%d/%m/%Y}"

        seg_totales = 0
        seg_fuera = 0
        completadas = 0
        por_estado: dict[str, int] = {}
        for a in actividades:
            seg_dir, seg_fh, _, _ = self._tiempos_directos_actividad(a)
            seg_totales += seg_dir
            seg_fuera += seg_fh
            if a.estado == EstadoActividad.COMPLETADA.value:
                completadas += 1
            est_lbl = _ETIQUETAS_ESTADO.get(a.estado, a.estado)
            por_estado[est_lbl] = por_estado.get(est_lbl, 0) + 1

        destino = (
            Path(ruta_destino)
            if ruta_destino
            else rutas.carpeta_reportes()
            / f"Reporte_Especifico_{_limpiar_nombre_archivo(titulo_filtro)}_{ahora():%Y%m%d}.pdf"
        )
        lienzo = LienzoPDF(
            destino,
            titulo_doc=titulo_filtro,
            empresa=cab.empresa,
            subtitulo_continuacion=rango_txt,
            color_primario=cab.color_primario,
            emitido_texto=cab.emitido,
        )
        pal = lienzo.paleta

        lienzo.dibujar_cabecera_hero(
            eyebrow=f"{cab.empresa} · Consulta Filtrada",
            titulo=titulo_filtro,
            subtitulo=f"Período consultado: {rango_txt}",
            estado_badge="FILTRADO",
            horario_texto=f"{len(actividades)} actividades encontradas",
            ruta_logo=cab.ruta_logo,
        )
        lienzo.dibujar_tira_metadatos(
            [
                ("Colaborador", cab.usuario),
                ("Cargo", cab.cargo),
                ("Período", rango_txt),
                ("Tipo filtro", _etiqueta_tipo(filtros.tipo) if filtros.tipo else "Todos"),
            ]
        )

        # 3 KPIs de síntesis
        y_kpi = lienzo.y
        gap = 12.0
        w3 = (ANCHO_CONTENIDO - 2.0 * gap) / 3.0
        h3 = 100.0
        pct_comp = (completadas / len(actividades) * 100.0) if actividades else 0.0
        dibujar_card_kpi_metrica(
            lienzo,
            QRectF(MARGEN_X, y_kpi, w3, h3),
            eyebrow="Tiempo total acumulado",
            valor=formatear_duracion_corta(seg_totales),
            color_acento=pal.primario,
            sublinea_1=f"En horario: {formatear_duracion_corta(max(0, seg_totales - seg_fuera))}",
            sublinea_2=f"Fuera de horario: {formatear_duracion_corta(seg_fuera)}",
        )
        dibujar_card_kpi_metrica(
            lienzo,
            QRectF(MARGEN_X + (w3 + gap), y_kpi, w3, h3),
            eyebrow="Actividades encontradas",
            valor=str(len(actividades)),
            color_acento=pal.verde,
            sublinea_1=f"Completadas: {completadas} ({pct_comp:.0f}%)",
            sublinea_2=f"Otros estados: {len(actividades) - completadas}",
        )
        prom_seg = int(seg_totales / len(actividades)) if actividades else 0
        dibujar_card_kpi_metrica(
            lienzo,
            QRectF(MARGEN_X + 2.0 * (w3 + gap), y_kpi, w3, h3),
            eyebrow="Promedio por actividad",
            valor=formatear_duracion_corta(prom_seg),
            color_acento=pal.morado,
            sublinea_1="Cálculo sobre sesiones acumuladas",
            sublinea_2="del conjunto filtrado.",
        )
        lienzo.y = y_kpi + h3 + 12.0

        # Fila gráfica: Categorías + Estados
        items_cat = self._agrupar_categorias_actividades(actividades, pal)
        items_est = [
            ItemBarraHorizontal(
                etiqueta=est,
                valor=float(cnt),
                texto_valor=f"{cnt} act.",
                color=pal.verde if "Complet" in est else (pal.ambar if "Arras" in est else pal.azul),
            )
            for est, cnt in sorted(por_estado.items(), key=lambda x: x[1], reverse=True)
        ]
        if items_cat or items_est:
            n_max = max(len(items_cat[:5]), len(items_est[:5]), 1)
            h_est = 46.0 + n_max * 26.0
            lienzo.asegurar_espacio(h_est + 10.0)
            y_g = lienzo.y
            w2 = (ANCHO_CONTENIDO - 12.0) / 2.0
            h_u1 = dibujar_barras_horizontales(
                lienzo,
                QRectF(MARGEN_X, y_g, w2, h_est),
                titulo="Tiempo por categoría",
                items=items_cat,
                max_items=5,
            )
            h_u2 = dibujar_barras_horizontales(
                lienzo,
                QRectF(MARGEN_X + w2 + 12.0, y_g, w2, h_est),
                titulo="Distribución por estado",
                items=items_est,
                max_items=5,
            )
            lienzo.y = y_g + max(h_u1, h_u2) + 14.0

        self._dibujar_tabla_actividades_dia(
            lienzo,
            actividades,
            "Actividades incluidas en el reporte",
            con_fecha=True,
        )
        lienzo.dibujar_firmas(cab.usuario)
        return lienzo.finalizar()

    # ------------------------------------------------------------------
    # 4. Reporte Periódico (Semanal / Mensual)
    # ------------------------------------------------------------------

    def generar_pdf_periodo(
        self,
        desde: date,
        hasta: date,
        etiqueta_periodo: str = "Semanal",
        ruta_destino: Path | str | None = None,
    ) -> Path:
        """Genera un reporte consolidado Semanal o Mensual altamente gráfico."""
        cab = _cargar_cabecera(self.s)
        stats = self.srv_est.calcular(desde, hasta)
        jornadas_rango = list(
            self.s.scalars(
                select(Jornada)
                .where(Jornada.fecha >= desde, Jornada.fecha <= hasta)
                .order_by(Jornada.fecha.asc())
            )
        )
        resultados_dia = [(j, self.srv_prod.calcular_jornada(j)) for j in jornadas_rango]

        tiempo_ef_total = sum(r.tiempo_efectivo_seg for _, r in resultados_dia)
        tiempo_fh_total = sum(r.tiempo_fuera_horario_seg for _, r in resultados_dia)
        total_trabajado_periodo = tiempo_ef_total + tiempo_fh_total
        prods_lab = [
            r.productividad_pct
            for _, r in resultados_dia
            if r.es_laboral and r.productividad_pct is not None
        ]
        prod_prom = round(sum(prods_lab) / len(prods_lab), 1) if prods_lab else None
        dias_lab = sum(1 for _, r in resultados_dia if r.es_laboral)
        sem_prom = self.srv_prod.clasificar_semaforo(prod_prom)
        rango_txt = f"{desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"

        destino = (
            Path(ruta_destino)
            if ruta_destino
            else rutas.carpeta_reportes()
            / f"Reporte_{etiqueta_periodo}_{desde:%Y-%m-%d}_al_{hasta:%Y-%m-%d}.pdf"
        )
        lienzo = LienzoPDF(
            destino,
            titulo_doc=f"Reporte {etiqueta_periodo} de Productividad",
            empresa=cab.empresa,
            subtitulo_continuacion=rango_txt,
            color_primario=cab.color_primario,
            emitido_texto=cab.emitido,
        )
        pal = lienzo.paleta

        # 1. Banner + Ficha
        lienzo.dibujar_cabecera_hero(
            eyebrow=f"{cab.empresa} · Consolidado {etiqueta_periodo}",
            titulo=f"Reporte {etiqueta_periodo} de Productividad",
            subtitulo=f"Período del {rango_txt}",
            estado_badge=etiqueta_periodo.upper(),
            horario_texto=f"{len(resultados_dia)} días registrados",
            ruta_logo=cab.ruta_logo,
        )
        lienzo.dibujar_tira_metadatos(
            [
                ("Colaborador", cab.usuario),
                ("Cargo", cab.cargo),
                ("Área", cab.area),
                ("Jornadas evaluadas", f"{dias_lab} laborales / {len(resultados_dia)} totales"),
            ]
        )

        # 2. Fila de 4 tarjetas KPI ejecutivas
        y_kpi = lienzo.y
        gap = 10.0
        w_card = (ANCHO_CONTENIDO - 3.0 * gap) / 4.0
        h_card = 114.0

        f_sem, t_sem, arc_sem = _colores_semaforo(sem_prom, pal)
        dibujar_card_kpi_donut(
            lienzo,
            QRectF(MARGEN_X, y_kpi, w_card, h_card),
            eyebrow="Productividad prom.",
            pct=prod_prom,
            etiqueta_badge=sem_prom.etiqueta(),
            fondo_badge=f_sem,
            texto_badge=t_sem,
            subtitulo=f"Promedio en {dias_lab} días laborales del período.",
            color_arco=arc_sem,
        )

        dibujar_card_kpi_metrica(
            lienzo,
            QRectF(MARGEN_X + (w_card + gap), y_kpi, w_card, h_card),
            eyebrow="Tiempo trabajado",
            valor=formatear_duracion_corta(total_trabajado_periodo),
            color_acento=pal.primario,
            sublinea_1=f"En jornada: {formatear_duracion_corta(tiempo_ef_total)}",
            sublinea_2=f"Fuera horario: {formatear_duracion_corta(tiempo_fh_total)}",
            barra_segmentos=[
                (float(tiempo_ef_total), pal.verde),
                (float(tiempo_fh_total), pal.morado),
            ],
            barra_total=float(max(total_trabajado_periodo, 1)),
        )

        acts_tot = sum(s.cantidad_solicitudes for s in stats.por_solicitante)
        revs_tot = stats.revisiones.total_revisiones
        dibujar_card_kpi_metrica(
            lienzo,
            QRectF(MARGEN_X + 2.0 * (w_card + gap), y_kpi, w_card, h_card),
            eyebrow="Carga atendida",
            valor=f"{acts_tot} act.",
            color_acento=pal.azul,
            sublinea_1=f"{len(stats.por_categoria)} categorías activas",
            sublinea_2=f"{len(stats.por_solicitante)} solicitantes distintos",
        )

        dibujar_card_kpi_metrica(
            lienzo,
            QRectF(MARGEN_X + 3.0 * (w_card + gap), y_kpi, w_card, h_card),
            eyebrow="Revisiones / Ajustes",
            valor=f"{revs_tot}",
            color_acento=pal.rojo if revs_tot > 0 else pal.verde,
            sublinea_1=f"Tiempo en rev.: {formatear_duracion_corta(stats.revisiones.segundos_totales)}",
            sublinea_2=(
                "Sin devoluciones registradas"
                if revs_tot == 0
                else "Ver desglose por motivo abajo"
            ),
        )
        lienzo.y = y_kpi + h_card + 12.0

        # 3. Gráfico vertical de tendencia diaria con umbrales 85% y 60%
        puntos_g: list[PuntoTendenciaGrafico] = []
        for j, res_d in resultados_dia:
            col_pt = color_por_nivel_pct(res_d.productividad_pct, lienzo)
            puntos_g.append(
                PuntoTendenciaGrafico(
                    fecha_corta=f"{_DIAS_CORTOS_ES[j.fecha.weekday()]} {j.fecha:%d}",
                    dia_corto=_DIAS_CORTOS_ES[j.fecha.weekday()],
                    productividad_pct=res_d.productividad_pct,
                    tiempo_texto=formatear_duracion_corta(
                        res_d.tiempo_efectivo_seg + res_d.tiempo_fuera_horario_seg
                    ),
                    color=col_pt,
                )
            )
        dibujar_tendencia_vertical(
            lienzo,
            puntos=puntos_g,
            titulo=f"Tendencia diaria de productividad ({etiqueta_periodo.lower()})",
        )

        # 4. Fila de gráficos comparativos: Categorías + Solicitantes
        tot_cat_seg = sum(c.segundos for c in stats.por_categoria) or 1
        items_cat = [
            ItemBarraHorizontal(
                etiqueta=c.categoria_nombre,
                valor=float(c.segundos),
                texto_valor=f"{formatear_duracion_corta(c.segundos)} ({c.segundos / tot_cat_seg * 100.0:.0f}%)",
                color=QColor(c.color) if QColor(c.color).isValid() else pal.primario,
                subetiqueta=f"{c.cantidad_actividades} act.",
            )
            for c in stats.por_categoria
        ]
        items_sol = [
            ItemBarraHorizontal(
                etiqueta=sol.solicitante_nombre,
                valor=float(sol.segundos),
                texto_valor=formatear_duracion_corta(sol.segundos),
                color=pal.azul if sol.tipo_solicitante == "jefe" else (pal.verde if sol.tipo_solicitante == "propia" else pal.morado),
                subetiqueta=f"{sol.cantidad_solicitudes} sol.",
            )
            for sol in stats.por_solicitante
        ]
        n_bars = max(len(items_cat[:6]), len(items_sol[:6]), 1)
        h_bars = 48.0 + n_bars * 26.0
        lienzo.asegurar_espacio(h_bars + 10.0)
        y_b = lienzo.y
        w2 = (ANCHO_CONTENIDO - 12.0) / 2.0
        hu1 = dibujar_barras_horizontales(
            lienzo,
            QRectF(MARGEN_X, y_b, w2, h_bars),
            titulo="Tiempo por categoría",
            items=items_cat,
            max_items=6,
        )
        hu2 = dibujar_barras_horizontales(
            lienzo,
            QRectF(MARGEN_X + w2 + 12.0, y_b, w2, h_bars),
            titulo="Tiempo por solicitante",
            items=items_sol,
            max_items=6,
        )
        lienzo.y = y_b + max(hu1, hu2) + 12.0

        # 5. Fila de insights: Estimado vs Real (izq) + Desglose de Revisiones (der)
        items_est_real = [
            ItemEstimadoRealGrafico(
                grupo=er.grupo,
                cantidad=er.cantidad,
                estimado_min=er.estimado_promedio_min,
                real_min=er.real_promedio_min,
            )
            for er in stats.estimado_vs_real
        ]
        h_comp = max(136.0, 58.0 + min(6, max(1, len(items_est_real))) * 31.0)
        lienzo.asegurar_espacio(h_comp + 12.0)
        y_ins = lienzo.y
        h_er = dibujar_estimado_vs_real(
            lienzo,
            QRectF(MARGEN_X, y_ins, w2, h_comp),
            items=items_est_real,
        )
        motivos_lst = [
            (_ETIQUETAS_MOTIVO_REV.get(k, k.replace("_", " ").capitalize()), v)
            for k, v in sorted(stats.revisiones.por_motivo.items(), key=lambda x: x[1], reverse=True)
        ]
        tipos_lst = [
            (_ETIQUETAS_TIPO_REV.get(k, k.replace("_", " ").capitalize()), v)
            for k, v in sorted(stats.revisiones.por_tipo.items(), key=lambda x: x[1], reverse=True)
        ]
        h_rev = dibujar_desglose_revisiones(
            lienzo,
            QRectF(MARGEN_X + w2 + 12.0, y_ins, w2, h_comp),
            total_revisiones=stats.revisiones.total_revisiones,
            tiempo_txt=formatear_duracion_corta(stats.revisiones.segundos_totales),
            por_motivo=motivos_lst,
            por_tipo=tipos_lst,
        )
        lienzo.y = y_ins + max(h_er, h_rev) + 14.0

        # 6. Tabla detallada por jornada
        if resultados_dia:
            filas_tend: list[list[str]] = []
            for j, res_d in resultados_dia:
                f_txt = f"{_DIAS_CORTOS_ES[j.fecha.weekday()]} {j.fecha:%d/%m/%Y}"
                tipo_j = "Laboral" if res_d.es_laboral else "No laboral"
                c_txt = f"{res_d.cumplimiento_pct:.1f}%" if res_d.cumplimiento_pct is not None else "—"
                e_txt = f"{res_d.eficiencia_pct:.1f}%" if res_d.eficiencia_pct is not None else "—"
                k_txt = f"{res_d.foco_pct:.1f}%" if res_d.foco_pct is not None else "—"
                g_txt = f"{res_d.productividad_pct:.1f}%" if res_d.productividad_pct is not None else "No apl."
                ef_txt = formatear_duracion_corta(res_d.tiempo_efectivo_seg)
                fh_txt = formatear_duracion_corta(res_d.tiempo_fuera_horario_seg)
                filas_tend.append(
                    [f_txt, tipo_j, c_txt, e_txt, k_txt, g_txt, ef_txt, fh_txt]
                )
            # 124 + 86 + 68 + 68 + 68 + 78 + 126 + 126 = 744 px
            cols_tend = [
                ("Fecha", 124.0, Qt.AlignmentFlag.AlignLeft),
                ("Jornada", 86.0, Qt.AlignmentFlag.AlignLeft),
                ("Cumpl.", 68.0, Qt.AlignmentFlag.AlignRight),
                ("Efic.", 68.0, Qt.AlignmentFlag.AlignRight),
                ("Foco", 68.0, Qt.AlignmentFlag.AlignRight),
                ("Global", 78.0, Qt.AlignmentFlag.AlignRight),
                ("En jornada", 126.0, Qt.AlignmentFlag.AlignRight),
                ("Fuera de horario", 126.0, Qt.AlignmentFlag.AlignRight),
            ]
            prom_txt = f"{prod_prom:.1f}%" if prod_prom is not None else "—"
            tot_tend = [
                f"Resumen ({len(resultados_dia)} días)",
                f"{dias_lab} lab.",
                "—",
                "—",
                "—",
                prom_txt,
                formatear_duracion_corta(tiempo_ef_total),
                formatear_duracion_corta(tiempo_fh_total),
            ]
            lienzo.dibujar_seccion(
                "Desglose detallado por día",
                subtitulo=rango_txt,
                alto_min_siguiente=78.0,
            )
            lienzo.dibujar_tabla_paginada(cols_tend, filas_tend, fila_totales=tot_tend, tam_pt=7.8)

        lienzo.dibujar_firmas(cab.usuario)
        return lienzo.finalizar()
