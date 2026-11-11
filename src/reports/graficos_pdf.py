"""Componentes gráficos vectoriales para reportes PDF ejecutivos.

Todos los gráficos pintan primitivas vectoriales directamente sobre ``LienzoPDF``
(anillos KPI, barras apiladas, línea de tiempo cronológica de la jornada,
barras horizontales comparativas, columnas de tendencia diaria con umbrales y
comparativo estimado vs. real), adaptándose a anchos y conjuntos de datos
variables sin solapamiento de etiquetas.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
)

from reports.generador_pdf import ANCHO_CONTENIDO, MARGEN_X, LienzoPDF, fuente_pdf


@dataclass(frozen=True)
class BloqueHorarioTimeline:
    """Bloque de horario laboral expresado en minutos desde medianoche."""

    inicio_min: int
    fin_min: int


@dataclass(frozen=True)
class SegmentoTimeline:
    """Segmento cronológico (sesión de trabajo o pausa) para la línea de tiempo."""

    inicio_min: float
    fin_min: float
    etiqueta: str
    color: QColor
    es_pausa: bool = False
    es_fuera_horario: bool = False


@dataclass(frozen=True)
class ItemBarraHorizontal:
    """Elemento de gráfico de barras horizontales proporcionales."""

    etiqueta: str
    valor: float
    texto_valor: str
    color: QColor
    subetiqueta: str = ""


@dataclass(frozen=True)
class PuntoTendenciaGrafico:
    """Punto diario para el gráfico de columnas de tendencia."""

    fecha_corta: str
    dia_corto: str
    productividad_pct: float | None
    tiempo_texto: str
    color: QColor


@dataclass(frozen=True)
class ItemEstimadoRealGrafico:
    """Par comparativo estimado vs. real promedio en minutos."""

    grupo: str
    cantidad: int
    estimado_min: float
    real_min: float


def color_por_nivel_pct(pct: float | None, lienzo: LienzoPDF) -> QColor:
    """Color semántico consistente con los umbrales de productividad."""
    if pct is None:
        return lienzo.paleta.neutro
    if pct >= 85.0:
        return lienzo.paleta.verde
    if pct >= 60.0:
        return lienzo.paleta.ambar
    return lienzo.paleta.rojo


def _formato_hora_min(minutos: float) -> str:
    m_tot = max(0, min(24 * 60, int(round(minutos))))
    return f"{m_tot // 60:02d}:{m_tot % 60:02d}"


def _dibujar_barra_apilada(
    lienzo: LienzoPDF,
    rect: QRectF,
    segmentos: list[tuple[float, QColor]],
    total_ref: float,
    color_pista: QColor,
) -> None:
    """Dibuja una barra de progreso multi-segmento con extremos redondeados."""
    r_trk = QRectF(rect)
    rx = r_trk.height() / 2.0
    lienzo.dibujar_rect_redondeado(r_trk, rx, fondo=color_pista)
    if total_ref <= 0.0:
        return

    segs_copy = [(max(0.0, float(v)), QColor(c)) for v, c in segmentos if v > 0]
    if not segs_copy:
        return

    def _draw(p: QPainter, _r: QRectF = r_trk, _rx: float = rx, _segs: list[tuple[float, QColor]] = segs_copy, _tot: float = float(total_ref)) -> None:
        p.save()
        from PySide6.QtGui import QPainterPath

        clip = QPainterPath()
        clip.addRoundedRect(_r, _rx, _rx)
        p.setClipPath(clip)
        p.setPen(Qt.PenStyle.NoPen)
        cx = _r.left()
        usado_max = _r.width()
        for val, col in _segs:
            w = min(usado_max - (cx - _r.left()), _r.width() * (val / _tot))
            if w <= 0.0:
                continue
            p.setBrush(col)
            p.drawRect(QRectF(cx, _r.top(), w, _r.height()))
            cx += w
        p.restore()

    lienzo.agregar_cmd(_draw)


# ======================================================================
# 1. Tarjetas KPI superiores (Diario, No laboral y Período)
# ======================================================================


def dibujar_card_kpi_donut(
    lienzo: LienzoPDF,
    rect: QRectF,
    eyebrow: str,
    pct: float | None,
    etiqueta_badge: str,
    fondo_badge: QColor,
    texto_badge: QColor,
    subtitulo: str,
    color_arco: QColor | None = None,
) -> None:
    """Tarjeta KPI con anillo/donut vectorial de progreso y badge semántico."""
    pal = lienzo.paleta
    col_arc = QColor(color_arco) if color_arco else color_por_nivel_pct(pct, lienzo)
    lienzo.dibujar_rect_redondeado(
        rect,
        10.0,
        fondo=pal.superficie,
        borde=pal.borde,
        grosor_borde=1.0,
    )
    # Franja superior de acento
    lienzo.dibujar_rect_redondeado(
        QRectF(rect.left() + 10.0, rect.top(), rect.width() - 20.0, 3.0),
        1.5,
        fondo=col_arc,
    )

    lienzo.dibujar_texto(
        QRectF(rect.left() + 12.0, rect.top() + 9.0, rect.width() - 24.0, 12.0),
        eyebrow.upper(),
        fuente_pdf(6.9, QFont.Weight.Bold),
        pal.texto_suave,
        envolver=False,
    )

    # Anillo SVG/vectorial a la izquierda
    tam_ring = 58.0
    ring_rect = QRectF(rect.left() + 12.0, rect.top() + 28.0, tam_ring, tam_ring)
    pct_clamp = max(0.0, min(100.0, float(pct))) if pct is not None else 0.0

    def _draw_ring(
        p: QPainter,
        _rr: QRectF = ring_rect,
        _pct: float = pct_clamp,
        _has: bool = pct is not None,
        _c_arc: QColor = QColor(col_arc),
        _c_trk: QColor = QColor(pal.pista),
    ) -> None:
        p.save()
        inset = 5.0
        arc_box = _rr.adjusted(inset, inset, -inset, -inset)
        pen_trk = QPen(_c_trk, 6.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen_trk)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(arc_box)
        if _has and _pct > 0.0:
            pen_arc = QPen(_c_arc, 6.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen_arc)
            # 12 en punto = 90 deg * 16; horario = negativo
            p.drawArc(arc_box, 90 * 16, -int(round((_pct / 100.0) * 360.0 * 16.0)))
        p.restore()

    lienzo.agregar_cmd(_draw_ring)

    centro_txt = f"{pct:.1f}%" if pct is not None else "N/A"
    lienzo.dibujar_texto(
        ring_rect,
        centro_txt,
        fuente_pdf(10.0 if len(centro_txt) <= 5 else 9.0, QFont.Weight.Bold),
        col_arc if pct is not None else pal.neutro,
        alineacion=Qt.AlignmentFlag.AlignCenter,
        envolver=False,
    )

    # Columna derecha dentro de la tarjeta
    dx = ring_rect.right() + 10.0
    dw = rect.right() - dx - 10.0
    lienzo.dibujar_pill(
        dx,
        rect.top() + 31.0,
        etiqueta_badge,
        fondo=fondo_badge,
        texto_color=texto_badge,
        tam_pt=7.1,
        pad_x=7.0,
        alto=18.0,
    )
    lienzo.dibujar_texto(
        QRectF(dx, rect.top() + 55.0, dw, 44.0),
        subtitulo,
        fuente_pdf(7.4, QFont.Weight.Normal),
        pal.texto_sec,
        envolver=True,
    )


def dibujar_card_kpi_jornada(
    lienzo: LienzoPDF,
    rect: QRectF,
    efectivo_txt: str,
    jornada_txt: str,
    pct_cobertura: float,
    efectivo_seg: int,
    jornada_seg: int,
    sublinea_1: str,
    sublinea_2: str = "",
) -> None:
    """Tarjeta KPI dedicada al tiempo efectivo trabajado durante la jornada laboral."""
    pal = lienzo.paleta
    lienzo.dibujar_rect_redondeado(
        rect,
        10.0,
        fondo=pal.superficie,
        borde=pal.borde,
        grosor_borde=1.0,
    )
    lienzo.dibujar_rect_redondeado(
        QRectF(rect.left() + 10.0, rect.top(), rect.width() - 20.0, 3.0),
        1.5,
        fondo=pal.primario,
    )
    lienzo.dibujar_texto(
        QRectF(rect.left() + 12.0, rect.top() + 9.0, rect.width() - 24.0, 12.0),
        "TIEMPO EN JORNADA",
        fuente_pdf(6.9, QFont.Weight.Bold),
        pal.texto_suave,
        envolver=False,
    )

    # Valor principal + chip de % cobertura
    chip_txt = f"{min(999, round(pct_cobertura))}%"
    f_chip = fuente_pdf(7.1, QFont.Weight.Bold)
    w_chip = lienzo.metricas(f_chip).horizontalAdvance(chip_txt) + 12.0
    lienzo.dibujar_texto(
        QRectF(rect.left() + 12.0, rect.top() + 26.0, rect.width() - 28.0 - w_chip, 24.0),
        efectivo_txt,
        fuente_pdf(14.0, QFont.Weight.Bold),
        pal.texto,
        envolver=False,
    )
    lienzo.dibujar_pill(
        rect.right() - 12.0 - w_chip,
        rect.top() + 28.0,
        chip_txt,
        fondo=pal.azul_suave,
        texto_color=pal.azul,
        tam_pt=7.1,
        pad_x=6.0,
        alto=17.0,
    )

    # Barra de progreso efectivo sobre el horario programado (sin sumar pausas)
    bar_rect = QRectF(rect.left() + 12.0, rect.top() + 56.0, rect.width() - 24.0, 7.0)
    base_ref = float(max(jornada_seg, efectivo_seg, 1))
    _dibujar_barra_apilada(
        lienzo,
        bar_rect,
        [(float(efectivo_seg), pal.verde)],
        base_ref,
        pal.pista,
    )

    lienzo.dibujar_texto(
        QRectF(rect.left() + 12.0, rect.top() + 68.0, rect.width() - 24.0, 15.0),
        f"Jornada total: {jornada_txt}",
        fuente_pdf(7.4, QFont.Weight.DemiBold),
        pal.texto_sec,
        envolver=False,
    )
    lienzo.dibujar_texto(
        QRectF(rect.left() + 12.0, rect.top() + 83.0, rect.width() - 24.0, 26.0),
        f"{sublinea_1}\n{sublinea_2}" if sublinea_2 else sublinea_1,
        fuente_pdf(7.2, QFont.Weight.Normal),
        pal.texto_suave,
        envolver=True,
    )


def dibujar_card_kpi_metrica(
    lienzo: LienzoPDF,
    rect: QRectF,
    eyebrow: str,
    valor: str,
    color_acento: QColor,
    sublinea_1: str,
    sublinea_2: str = "",
    barra_segmentos: list[tuple[float, QColor]] | None = None,
    barra_total: float = 0.0,
) -> None:
    """Tarjeta KPI uniforme con acento superior, barra opcional y dos sublíneas."""
    pal = lienzo.paleta
    lienzo.dibujar_rect_redondeado(
        rect,
        10.0,
        fondo=pal.superficie,
        borde=pal.borde,
        grosor_borde=1.0,
    )
    lienzo.dibujar_rect_redondeado(
        QRectF(rect.left() + 10.0, rect.top(), rect.width() - 20.0, 3.0),
        1.5,
        fondo=color_acento,
    )
    lienzo.dibujar_texto(
        QRectF(rect.left() + 12.0, rect.top() + 9.0, rect.width() - 24.0, 12.0),
        eyebrow.upper(),
        fuente_pdf(6.9, QFont.Weight.Bold),
        pal.texto_suave,
        envolver=False,
    )
    lienzo.dibujar_texto(
        QRectF(rect.left() + 12.0, rect.top() + 26.0, rect.width() - 24.0, 24.0),
        valor,
        fuente_pdf(14.0, QFont.Weight.Bold),
        pal.texto,
        envolver=False,
    )

    y_sub = rect.top() + 56.0
    if barra_segmentos is not None:
        bar_rect = QRectF(rect.left() + 12.0, y_sub, rect.width() - 24.0, 7.0)
        _dibujar_barra_apilada(lienzo, bar_rect, barra_segmentos, barra_total, pal.pista)
        y_sub += 13.0

    texto_sub = f"{sublinea_1}\n{sublinea_2}" if sublinea_2 else sublinea_1
    lienzo.dibujar_texto(
        QRectF(rect.left() + 12.0, y_sub, rect.width() - 24.0, rect.bottom() - y_sub - 6.0),
        texto_sub,
        fuente_pdf(7.3, QFont.Weight.Normal),
        pal.texto_sec,
        envolver=True,
    )


# ======================================================================
# 2. Subindicadores y Línea de Tiempo de la Jornada
# ======================================================================


def dibujar_card_subindicadores(
    lienzo: LienzoPDF,
    rect: QRectF,
    cumplimiento_pct: float | None,
    eficiencia_pct: float | None,
    foco_pct: float | None,
    nota_pesos: str,
) -> None:
    """Tarjeta izquierda con barras de progreso horizontales para C, E y F."""
    pal = lienzo.paleta
    lienzo.dibujar_rect_redondeado(rect, 10.0, fondo=pal.superficie, borde=pal.borde, grosor_borde=1.0)
    lienzo.dibujar_texto(
        QRectF(rect.left() + 14.0, rect.top() + 12.0, rect.width() - 28.0, 18.0),
        "Indicadores de productividad",
        fuente_pdf(9.2, QFont.Weight.Bold),
        pal.texto,
        envolver=False,
    )

    filas = [
        ("Cumplimiento del plan", cumplimiento_pct),
        ("Eficiencia (est. vs real)", eficiencia_pct),
        ("Foco en horario", foco_pct),
    ]
    y_curr = rect.top() + 40.0
    w_bar = rect.width() - 28.0
    for nombre, val in filas:
        col = color_por_nivel_pct(val, lienzo)
        val_txt = f"{val:.1f} %" if val is not None else "N/A"
        lienzo.dibujar_texto(
            QRectF(rect.left() + 14.0, y_curr, w_bar - 48.0, 14.0),
            nombre,
            fuente_pdf(7.8, QFont.Weight.DemiBold),
            pal.texto_sec,
            envolver=False,
        )
        lienzo.dibujar_texto(
            QRectF(rect.right() - 62.0, y_curr, 48.0, 14.0),
            val_txt,
            fuente_pdf(8.0, QFont.Weight.Bold),
            col,
            alineacion=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            envolver=False,
        )
        bar_r = QRectF(rect.left() + 14.0, y_curr + 17.0, w_bar, 7.0)
        _dibujar_barra_apilada(
            lienzo,
            bar_r,
            [(min(100.0, float(val)) if val is not None else 0.0, col)],
            100.0,
            pal.pista,
        )
        y_curr += 34.0

    lienzo.dibujar_texto(
        QRectF(rect.left() + 14.0, rect.bottom() - 26.0, w_bar, 18.0),
        nota_pesos,
        fuente_pdf(7.0, QFont.Weight.Normal),
        pal.texto_suave,
        envolver=True,
    )


def dibujar_timeline_jornada(
    lienzo: LienzoPDF,
    rect: QRectF,
    bloques: list[BloqueHorarioTimeline],
    segmentos: list[SegmentoTimeline],
    resumen_pie: str,
) -> None:
    """Tarjeta con línea de tiempo cronológica (horario programado y sesiones activas)."""
    pal = lienzo.paleta
    lienzo.dibujar_rect_redondeado(rect, 10.0, fondo=pal.superficie, borde=pal.borde, grosor_borde=1.0)
    lienzo.dibujar_texto(
        QRectF(rect.left() + 14.0, rect.top() + 12.0, rect.width() - 140.0, 18.0),
        "Línea de tiempo cronológica",
        fuente_pdf(9.2, QFont.Weight.Bold),
        pal.texto,
        envolver=False,
    )

    # Rango visible en minutos desde 00:00
    puntos_min: list[float] = []
    for b in bloques:
        puntos_min.extend([float(b.inicio_min), float(b.fin_min)])
    for s in segmentos:
        puntos_min.extend([s.inicio_min, s.fin_min])

    if not puntos_min:
        t_min, t_max = 7.0 * 60.0, 17.0 * 60.0
    else:
        raw_min = min(puntos_min)
        raw_max = max(puntos_min)
        if raw_max - raw_min < 60.0:
            raw_max = raw_min + 60.0
        # Redondear a múltiplos de 30 minutos para ticks limpios
        t_min = float(max(0, (int(raw_min) // 30) * 30))
        t_max = float(min(24 * 60, ((int(raw_max) + 29) // 30) * 30))
        if t_max <= t_min:
            t_max = t_min + 60.0

    rango_txt = f"{_formato_hora_min(t_min)} – {_formato_hora_min(t_max)}"
    f_chip = fuente_pdf(7.2, QFont.Weight.DemiBold)
    w_chip = lienzo.metricas(f_chip).horizontalAdvance(rango_txt) + 14.0
    lienzo.dibujar_pill(
        rect.right() - 14.0 - w_chip,
        rect.top() + 11.0,
        rango_txt,
        fondo=pal.neutro_suave,
        texto_color=pal.texto_sec,
        tam_pt=7.2,
        pad_x=7.0,
        alto=18.0,
    )

    track = QRectF(rect.left() + 16.0, rect.top() + 42.0, rect.width() - 32.0, 48.0)
    span = t_max - t_min

    def _x_de_min(m: float) -> float:
        prop = max(0.0, min(1.0, (m - t_min) / span))
        return track.left() + prop * track.width()

    # Fondo base fuera de horario
    lienzo.dibujar_rect_redondeado(track, 6.0, fondo=QColor("#F3F4F6"), borde=pal.borde, grosor_borde=0.8)

    # Franjas azules de bloques horarios programados
    for b in bloques:
        bx1 = _x_de_min(float(b.inicio_min))
        bx2 = _x_de_min(float(b.fin_min))
        if bx2 > bx1 + 1.0:
            lienzo.dibujar_rect_redondeado(
                QRectF(bx1, track.top() + 1.0, bx2 - bx1, track.height() - 2.0),
                4.0,
                fondo=QColor("#EFF6FF"),
                borde=QColor("#BFDBFE"),
                grosor_borde=0.8,
            )

    # Bloques de sesiones de trabajo activas
    if not segmentos:
        lienzo.dibujar_texto(
            track,
            "Sin sesiones registradas en este día",
            fuente_pdf(8.0, QFont.Weight.Normal, italic=True),
            pal.texto_suave,
            alineacion=Qt.AlignmentFlag.AlignCenter,
            envolver=False,
        )
    else:
        for seg in segmentos:
            sx1 = _x_de_min(seg.inicio_min)
            sx2 = _x_de_min(seg.fin_min)
            w_seg = max(3.0, sx2 - sx1)
            if sx1 + w_seg > track.right():
                sx1 = max(track.left(), track.right() - w_seg)
            if seg.es_pausa:
                seg_r = QRectF(sx1, track.top() + 30.0, w_seg, 12.0)
                lienzo.dibujar_rect_redondeado(seg_r, 3.0, fondo=seg.color)
            else:
                seg_r = QRectF(sx1, track.top() + 6.0, w_seg, 20.0)
                borde_seg = pal.morado if seg.es_fuera_horario else None
                lienzo.dibujar_rect_redondeado(
                    seg_r,
                    4.0,
                    fondo=seg.color,
                    borde=borde_seg,
                    grosor_borde=1.1 if borde_seg else 0.0,
                )

    # Eje de horas sin colisión
    y_eje = track.bottom() + 4.0
    paso_min = 60 if span <= 8 * 60 else (120 if span <= 14 * 60 else 180)
    primero = ((int(t_min) + paso_min - 1) // paso_min) * paso_min
    ticks = [int(t_min)]
    t_curr = primero
    while t_curr < t_max:
        if t_curr - ticks[-1] >= 45 and t_max - t_curr >= 45:
            ticks.append(t_curr)
        t_curr += paso_min
    if int(t_max) - ticks[-1] >= 40:
        ticks.append(int(t_max))

    f_tick = fuente_pdf(6.9, QFont.Weight.Normal)
    for idx_t, tk in enumerate(ticks):
        tx = _x_de_min(float(tk))
        lienzo.dibujar_linea(tx, track.bottom(), tx, y_eje + 3.0, QColor("#CBD5E1"), 0.9)
        w_tk = 36.0
        alig_tk = Qt.AlignmentFlag.AlignCenter
        rx_tk = tx - w_tk / 2.0
        if idx_t == 0:
            rx_tk = tx
            alig_tk = Qt.AlignmentFlag.AlignLeft
        elif idx_t == len(ticks) - 1:
            rx_tk = tx - w_tk
            alig_tk = Qt.AlignmentFlag.AlignRight
        lienzo.dibujar_texto(
            QRectF(rx_tk, y_eje + 3.0, w_tk, 13.0),
            _formato_hora_min(tk),
            f_tick,
            pal.texto_suave,
            alineacion=alig_tk,
            envolver=False,
        )

    # Leyenda de colores compacta en 1 fila
    leyenda = [
        ("Horario", QColor("#93C5FD")),
        ("Planeada", pal.azul),
        ("Extra", pal.ambar),
        ("No plan.", pal.morado),
        ("Revisión", pal.rojo),
    ]
    lx = rect.left() + 16.0
    ly = y_eje + 22.0
    f_leg = fuente_pdf(7.0, QFont.Weight.DemiBold)
    for nom_l, col_l in leyenda:
        lienzo.dibujar_rect_redondeado(QRectF(lx, ly + 3.0, 8.0, 8.0), 2.5, fondo=col_l)
        tw = lienzo.metricas(f_leg).horizontalAdvance(nom_l)
        lienzo.dibujar_texto(
            QRectF(lx + 11.0, ly, tw + 4.0, 14.0),
            nom_l,
            f_leg,
            pal.texto_sec,
            envolver=False,
        )
        lx += tw + 22.0

    # Resumen inferior
    lienzo.dibujar_texto(
        QRectF(rect.left() + 16.0, rect.bottom() - 24.0, rect.width() - 32.0, 16.0),
        resumen_pie,
        fuente_pdf(7.3, QFont.Weight.Normal),
        pal.texto_suave,
        envolver=False,
    )


# ======================================================================
# 3. Gráficos comparativos (Barras horizontales, Tendencia, Estimado vs Real, Revisiones)
# ======================================================================


def dibujar_barras_horizontales(
    lienzo: LienzoPDF,
    rect: QRectF,
    titulo: str,
    items: list[ItemBarraHorizontal],
    mensaje_vacio: str = "Sin datos suficientes en este periodo",
    max_items: int = 7,
) -> float:
    """Dibuja una tarjeta de barras horizontales dentro de ``rect`` y devuelve su alto usado."""
    pal = lienzo.paleta
    visibles = items[:max_items]
    n_rows = max(1, len(visibles))
    alto_real = 42.0 + n_rows * 26.0 + 6.0 if visibles else 76.0
    card_r = QRectF(rect.left(), rect.top(), rect.width(), max(rect.height(), alto_real))
    lienzo.dibujar_rect_redondeado(card_r, 10.0, fondo=pal.superficie, borde=pal.borde, grosor_borde=1.0)
    lienzo.dibujar_texto(
        QRectF(card_r.left() + 14.0, card_r.top() + 11.0, card_r.width() - 28.0, 18.0),
        titulo,
        fuente_pdf(9.2, QFont.Weight.Bold),
        pal.texto,
        envolver=False,
    )

    if not visibles:
        lienzo.dibujar_texto(
            card_r.adjusted(14.0, 32.0, -14.0, -10.0),
            mensaje_vacio,
            fuente_pdf(8.0, QFont.Weight.Normal, italic=True),
            pal.texto_suave,
            alineacion=Qt.AlignmentFlag.AlignCenter,
            envolver=False,
        )
        return card_r.height()

    max_val = max(it.valor for it in visibles) or 1.0
    y_curr = card_r.top() + 38.0
    w_in = card_r.width() - 28.0

    for it in visibles:
        # Punto de color + nombre a la izquierda + valor derecho
        lienzo.dibujar_rect_redondeado(QRectF(card_r.left() + 14.0, y_curr + 3.0, 7.0, 7.0), 3.5, fondo=it.color)
        w_lbl = w_in * 0.56
        lienzo.dibujar_texto(
            QRectF(card_r.left() + 26.0, y_curr, w_lbl, 14.0),
            it.etiqueta,
            fuente_pdf(7.8, QFont.Weight.DemiBold),
            pal.texto,
            envolver=False,
        )
        txt_der = f"{it.texto_valor}" + (f" · {it.subetiqueta}" if it.subetiqueta else "")
        lienzo.dibujar_texto(
            QRectF(card_r.left() + 26.0 + w_lbl, y_curr, w_in - 12.0 - w_lbl, 14.0),
            txt_der,
            fuente_pdf(7.6, QFont.Weight.DemiBold),
            pal.texto_sec,
            alineacion=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            envolver=False,
        )
        bar_r = QRectF(card_r.left() + 14.0, y_curr + 16.0, w_in, 6.5)
        _dibujar_barra_apilada(lienzo, bar_r, [(it.valor, it.color)], max_val, pal.pista)
        y_curr += 26.0

    return card_r.height()


def dibujar_tendencia_vertical(
    lienzo: LienzoPDF,
    puntos: list[PuntoTendenciaGrafico],
    titulo: str = "Tendencia diaria de productividad",
) -> None:
    """Gráfico de columnas verticales por día con líneas guía de 85 % y 60 %."""
    alto_card = 196.0
    lienzo.asegurar_espacio(alto_card + 10.0)
    pal = lienzo.paleta
    card = QRectF(MARGEN_X, lienzo.y, ANCHO_CONTENIDO, alto_card)
    lienzo.dibujar_rect_redondeado(card, 10.0, fondo=pal.superficie, borde=pal.borde, grosor_borde=1.0)

    lienzo.dibujar_texto(
        QRectF(card.left() + 14.0, card.top() + 11.0, 380.0, 18.0),
        titulo,
        fuente_pdf(9.4, QFont.Weight.Bold),
        pal.texto,
        envolver=False,
    )
    # Leyenda de umbrales arriba a la derecha
    lienzo.dibujar_pill(
        card.right() - 210.0,
        card.top() + 10.0,
        "≥ 85 % Excelente",
        fondo=pal.verde_suave,
        texto_color=pal.verde,
        tam_pt=6.9,
        pad_x=7.0,
        alto=17.0,
    )
    lienzo.dibujar_pill(
        card.right() - 106.0,
        card.top() + 10.0,
        "≥ 60 % Aceptable",
        fondo=pal.ambar_suave,
        texto_color=pal.ambar,
        tam_pt=6.9,
        pad_x=7.0,
        alto=17.0,
    )

    if not puntos:
        lienzo.dibujar_texto(
            card.adjusted(14.0, 38.0, -14.0, -12.0),
            "Sin jornadas registradas en el período seleccionado",
            fuente_pdf(8.3, QFont.Weight.Normal, italic=True),
            pal.texto_suave,
            alineacion=Qt.AlignmentFlag.AlignCenter,
            envolver=False,
        )
        lienzo.y = card.bottom() + 12.0
        return

    plot = QRectF(card.left() + 42.0, card.top() + 46.0, card.width() - 58.0, 106.0)
    # Líneas horizontales de referencia
    f_ejey = fuente_pdf(6.8, QFont.Weight.Normal)
    for nivel, col_l, punteada in [
        (100, pal.borde, False),
        (85, QColor("#86EFAC"), True),
        (60, QColor("#FCD34D"), True),
        (0, QColor("#CBD5E1"), False),
    ]:
        py = plot.bottom() - (nivel / 100.0) * plot.height()
        lienzo.dibujar_linea(plot.left(), py, plot.right(), py, col_l, 0.9, punteada=punteada)
        lienzo.dibujar_texto(
            QRectF(card.left() + 8.0, py - 7.0, 30.0, 14.0),
            f"{nivel}%",
            f_ejey,
            pal.texto_suave,
            alineacion=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            envolver=False,
        )

    n = len(puntos)
    slot_w = plot.width() / n
    bar_w = max(8.0, min(38.0, slot_w * 0.58))
    modo_denso = n > 14

    for idx, pt in enumerate(puntos):
        cx = plot.left() + (idx + 0.5) * slot_w
        bx = cx - bar_w / 2.0
        if pt.productividad_pct is None:
            # Día no laboral: marca sutil en la base
            stub = QRectF(bx, plot.bottom() - 8.0, bar_w, 8.0)
            lienzo.dibujar_rect_redondeado(stub, 3.0, fondo=pal.neutro_suave, borde=QColor("#CBD5E1"), grosor_borde=0.7)
            if not modo_denso:
                lienzo.dibujar_texto(
                    QRectF(cx - 24.0, plot.bottom() - 23.0, 48.0, 13.0),
                    "No lab.",
                    fuente_pdf(6.5, QFont.Weight.Normal),
                    pal.texto_suave,
                    alineacion=Qt.AlignmentFlag.AlignCenter,
                    envolver=False,
                )
        else:
            pct_val = max(0.0, min(100.0, pt.productividad_pct))
            bh = max(4.0, (pct_val / 100.0) * plot.height())
            by = plot.bottom() - bh
            bar_r = QRectF(bx, by, bar_w, bh)
            col_b = QColor(pt.color)

            def _draw_col(p: QPainter, _r: QRectF = bar_r, _c: QColor = col_b) -> None:
                p.save()
                grad = QLinearGradient(_r.topLeft(), _r.bottomLeft())
                grad.setColorAt(0.0, _c)
                grad.setColorAt(1.0, _c.lighter(128))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(grad)
                p.drawRoundedRect(_r, 4.0, 4.0)
                p.restore()

            lienzo.agregar_cmd(_draw_col)
            txt_pct = f"{pct_val:.0f}%" if modo_denso else f"{pct_val:.1f}%"
            lienzo.dibujar_texto(
                QRectF(cx - 24.0, max(plot.top() - 14.0, by - 15.0), 48.0, 13.0),
                txt_pct,
                fuente_pdf(6.6 if modo_denso else 7.2, QFont.Weight.Bold),
                col_b,
                alineacion=Qt.AlignmentFlag.AlignCenter,
                envolver=False,
            )

        # Etiqueta inferior (día + fecha + tiempo)
        etq_x = pt.fecha_corta[:2] if modo_denso else pt.fecha_corta
        lienzo.dibujar_texto(
            QRectF(cx - slot_w / 2.0, plot.bottom() + 4.0, slot_w, 13.0),
            etq_x,
            fuente_pdf(6.7 if modo_denso else 7.3, QFont.Weight.DemiBold),
            pal.texto_sec,
            alineacion=Qt.AlignmentFlag.AlignCenter,
            envolver=False,
        )
        if not modo_denso:
            lienzo.dibujar_texto(
                QRectF(cx - slot_w / 2.0, plot.bottom() + 17.0, slot_w, 12.0),
                pt.tiempo_texto,
                fuente_pdf(6.6, QFont.Weight.Normal),
                pal.texto_suave,
                alineacion=Qt.AlignmentFlag.AlignCenter,
                envolver=False,
            )

    lienzo.y = card.bottom() + 12.0


def dibujar_estimado_vs_real(
    lienzo: LienzoPDF,
    rect: QRectF,
    items: list[ItemEstimadoRealGrafico],
) -> float:
    """Tarjeta comparativa de barras gemelas: tiempo estimado vs. real promedio."""
    pal = lienzo.paleta
    visibles = items[:6]
    n = max(1, len(visibles))
    alto_calc = 58.0 + n * 31.0 if visibles else 82.0
    card = QRectF(rect.left(), rect.top(), rect.width(), max(rect.height(), alto_calc))
    lienzo.dibujar_rect_redondeado(card, 10.0, fondo=pal.superficie, borde=pal.borde, grosor_borde=1.0)
    lienzo.dibujar_texto(
        QRectF(card.left() + 14.0, card.top() + 11.0, card.width() - 180.0, 18.0),
        "Estimado vs. Real promedio",
        fuente_pdf(9.2, QFont.Weight.Bold),
        pal.texto,
        envolver=False,
    )
    # Mini leyenda
    lienzo.dibujar_rect_redondeado(QRectF(card.right() - 168.0, card.top() + 14.0, 9.0, 9.0), 2.5, fondo=QColor("#94A3B8"))
    lienzo.dibujar_texto(QRectF(card.right() - 155.0, card.top() + 11.0, 56.0, 14.0), "Estimado", fuente_pdf(7.0, QFont.Weight.DemiBold), pal.texto_sec, envolver=False)
    lienzo.dibujar_rect_redondeado(QRectF(card.right() - 95.0, card.top() + 14.0, 9.0, 9.0), 2.5, fondo=pal.azul)
    lienzo.dibujar_texto(QRectF(card.right() - 82.0, card.top() + 11.0, 68.0, 14.0), "Real prom.", fuente_pdf(7.0, QFont.Weight.DemiBold), pal.texto_sec, envolver=False)

    if not visibles:
        lienzo.dibujar_texto(
            card.adjusted(14.0, 34.0, -14.0, -10.0),
            "Sin actividades con tiempo estimado en este rango",
            fuente_pdf(8.0, QFont.Weight.Normal, italic=True),
            pal.texto_suave,
            alineacion=Qt.AlignmentFlag.AlignCenter,
            envolver=False,
        )
        return card.height()

    max_min = max(max(it.estimado_min, it.real_min) for it in visibles) or 1.0
    y_curr = card.top() + 38.0
    w_in = card.width() - 28.0
    for it in visibles:
        desv = ((it.real_min - it.estimado_min) / it.estimado_min * 100.0) if it.estimado_min > 0 else 0.0
        col_real = pal.ambar if desv > 10.0 else pal.azul
        lienzo.dibujar_texto(
            QRectF(card.left() + 14.0, y_curr, w_in * 0.56, 13.0),
            f"{it.grupo} ({it.cantidad})",
            fuente_pdf(7.7, QFont.Weight.DemiBold),
            pal.texto,
            envolver=False,
        )
        signo = "+" if desv > 0 else ""
        res_txt = f"Est {it.estimado_min:.0f}m · Real {it.real_min:.0f}m ({signo}{desv:.0f}%)"
        lienzo.dibujar_texto(
            QRectF(card.left() + 14.0 + w_in * 0.50, y_curr, w_in * 0.50, 13.0),
            res_txt,
            fuente_pdf(7.3, QFont.Weight.DemiBold),
            col_real,
            alineacion=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            envolver=False,
        )
        _dibujar_barra_apilada(
            lienzo,
            QRectF(card.left() + 14.0, y_curr + 15.0, w_in, 5.0),
            [(it.estimado_min, QColor("#94A3B8"))],
            max_min,
            pal.pista,
        )
        _dibujar_barra_apilada(
            lienzo,
            QRectF(card.left() + 14.0, y_curr + 21.5, w_in, 5.0),
            [(it.real_min, col_real)],
            max_min,
            pal.pista,
        )
        y_curr += 31.0
    return card.height()


def _dibujar_pills_envueltos(
    lienzo: LienzoPDF,
    x_izq: float,
    y_ini: float,
    x_der_max: float,
    items: list[tuple[str, int]],
    fondo: QColor,
    texto_color: QColor,
) -> float:
    """Dibuja etiquetas tipo pill en filas con salto automático de línea y devuelve Y final."""
    px = x_izq
    py = y_ini
    f_pill = fuente_pdf(7.1, QFont.Weight.DemiBold)
    for etq, cnt in items:
        txt_p = f"{etq}: {cnt}"
        w_est = lienzo.metricas(f_pill).horizontalAdvance(txt_p) + 14.0
        if px > x_izq and px + w_est > x_der_max:
            px = x_izq
            py += 22.0
        w_p = lienzo.dibujar_pill(
            px,
            py,
            txt_p,
            fondo=fondo,
            texto_color=texto_color,
            tam_pt=7.1,
            pad_x=7.0,
            alto=18.0,
        )
        px += w_p + 6.0
    return py + 22.0


def dibujar_desglose_revisiones(
    lienzo: LienzoPDF,
    rect: QRectF,
    total_revisiones: int,
    tiempo_txt: str,
    por_motivo: list[tuple[str, int]],
    por_tipo: list[tuple[str, int]],
) -> float:
    """Tarjeta gráfica de devoluciones y revisiones por motivo y tipo."""
    pal = lienzo.paleta
    card = QRectF(rect.left(), rect.top(), rect.width(), max(rect.height(), 132.0))
    lienzo.dibujar_rect_redondeado(card, 10.0, fondo=pal.superficie, borde=pal.borde, grosor_borde=1.0)
    lienzo.dibujar_texto(
        QRectF(card.left() + 14.0, card.top() + 11.0, card.width() - 28.0, 18.0),
        "Revisiones y devoluciones",
        fuente_pdf(9.2, QFont.Weight.Bold),
        pal.texto,
        envolver=False,
    )

    if total_revisiones <= 0:
        lienzo.dibujar_pill(
            card.left() + 14.0,
            card.top() + 44.0,
            "0 revisiones registradas",
            fondo=pal.verde_suave,
            texto_color=pal.verde,
            tam_pt=7.8,
        )
        lienzo.dibujar_texto(
            QRectF(card.left() + 14.0, card.top() + 72.0, card.width() - 28.0, 32.0),
            "Excelente calidad de entrega sin retrabajos en el período.",
            fuente_pdf(7.8, QFont.Weight.Normal),
            pal.texto_sec,
            envolver=True,
        )
        return card.height()

    lienzo.dibujar_texto(
        QRectF(card.left() + 14.0, card.top() + 34.0, card.width() - 28.0, 22.0),
        f"{total_revisiones} revisiones · {tiempo_txt} invertidos",
        fuente_pdf(10.5, QFont.Weight.Bold),
        pal.rojo,
        envolver=False,
    )

    y_c = card.top() + 62.0
    if por_tipo:
        lienzo.dibujar_texto(
            QRectF(card.left() + 14.0, y_c, card.width() - 28.0, 13.0),
            "POR TIPO",
            fuente_pdf(6.8, QFont.Weight.Bold),
            pal.texto_suave,
            envolver=False,
        )
        y_c = _dibujar_pills_envueltos(
            lienzo,
            card.left() + 14.0,
            y_c + 15.0,
            card.right() - 14.0,
            por_tipo[:6],
            pal.rojo_suave,
            pal.rojo,
        ) + 4.0

    if por_motivo:
        lienzo.dibujar_texto(
            QRectF(card.left() + 14.0, y_c, card.width() - 28.0, 13.0),
            "POR MOTIVO",
            fuente_pdf(6.8, QFont.Weight.Bold),
            pal.texto_suave,
            envolver=False,
        )
        y_c = _dibujar_pills_envueltos(
            lienzo,
            card.left() + 14.0,
            y_c + 15.0,
            card.right() - 14.0,
            por_motivo[:6],
            pal.ambar_suave,
            pal.ambar,
        )

    return max(card.height(), y_c - card.top() + 8.0)
