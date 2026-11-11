"""Motor gráfico vectorial para generar reportes PDF corporativos con PySide6.

Proporciona un lienzo paginado (`LienzoPDF`) basado en `QPdfWriter` + `QPainter`
con medición exacta de texto a 96 DPI, cabeceras continuas, pie de página con
``Página X de Y``, logotipos SVG/raster, tarjetas redondeadas, tablas con
auto-paginación y repetición de encabezados, y exportación compatible heredada
vía ``renderizar_html_a_pdf``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QLinearGradient,
    QPageSize,
    QPainter,
    QPainterPath,
    QPdfWriter,
    QPen,
    QTextDocument,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ANCHO_CARTA = 816.0  # 8.5 in * 96 DPI
ALTO_CARTA = 1056.0  # 11.0 in * 96 DPI
MARGEN_X = 36.0
ANCHO_CONTENIDO = ANCHO_CARTA - 2.0 * MARGEN_X  # 744.0 px
Y_INICIO_PAG1 = 28.0
Y_INICIO_CONT = 58.0
Y_LIMITE_CONTENIDO = 1004.0
Y_PIE = 1016.0

ComandoDibujo = Callable[[QPainter], None]


@dataclass(frozen=True)
class PaletaPDF:
    """Esquema cromático corporativo y semántico del reporte."""

    primario: QColor
    primario_oscuro: QColor
    primario_suave: QColor
    primario_borde: QColor
    texto: QColor
    texto_sec: QColor
    texto_suave: QColor
    borde: QColor
    superficie: QColor
    fondo_tarjeta: QColor
    pista: QColor
    verde: QColor
    verde_suave: QColor
    azul: QColor
    azul_suave: QColor
    ambar: QColor
    ambar_suave: QColor
    rojo: QColor
    rojo_suave: QColor
    morado: QColor
    morado_suave: QColor
    neutro: QColor
    neutro_suave: QColor

    @classmethod
    def desde_hex(cls, hex_primario: str) -> PaletaPDF:
        """Construye una paleta equilibrada a partir del color corporativo."""
        prim = QColor(hex_primario or "#003D95")
        if not prim.isValid():
            prim = QColor("#003D95")
        oscuro = QColor(prim).darker(155)
        suave = QColor(prim)
        suave.setAlpha(20)
        borde_p = QColor(prim)
        borde_p.setAlpha(72)
        return cls(
            primario=prim,
            primario_oscuro=oscuro,
            primario_suave=suave,
            primario_borde=borde_p,
            texto=QColor("#0F172A"),
            texto_sec=QColor("#475569"),
            texto_suave=QColor("#64748B"),
            borde=QColor("#E2E8F0"),
            superficie=QColor("#FFFFFF"),
            fondo_tarjeta=QColor("#F8FAFC"),
            pista=QColor("#E8EEF5"),
            verde=QColor("#15803D"),
            verde_suave=QColor("#DCFCE7"),
            azul=QColor("#1D4ED8"),
            azul_suave=QColor("#DBEAFE"),
            ambar=QColor("#D97706"),
            ambar_suave=QColor("#FEF3C7"),
            rojo=QColor("#DC2626"),
            rojo_suave=QColor("#FEE2E2"),
            morado=QColor("#7C3AED"),
            morado_suave=QColor("#EDE9FE"),
            neutro=QColor("#64748B"),
            neutro_suave=QColor("#F1F5F9"),
        )


def asegurar_qapplication() -> QApplication:
    """Garantiza una instancia activa de QApplication para renderizar fuentes/PDF."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["control-tiempos-pdf"])
    return app  # type: ignore[return-value]


def _resolver_ruta_escribible(ruta: Path) -> Path:
    """Crea la carpeta destino y devuelve una ruta alternativa si la original está bloqueada."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if ruta.exists():
        try:
            with ruta.open("r+b"):
                pass
        except PermissionError:
            sello = datetime.now().strftime("%Y%m%d_%H%M%S")
            return ruta.with_name(f"{ruta.stem}_{sello}.pdf")
    return ruta


def fuente_pdf(
    tam_pt: float,
    peso: QFont.Weight = QFont.Weight.Normal,
    italic: bool = False,
) -> QFont:
    """Crea una fuente estática nítida compatible con el motor QPdfWriter."""
    f = QFont("Segoe UI")
    f.setPointSizeF(tam_pt)
    f.setWeight(peso)
    f.setItalic(italic)
    return f


def _imagen_referencia_96dpi() -> QImage:
    """Dispositivo de referencia a 96 DPI para métricas idénticas a QPdfWriter."""
    img = QImage(1, 1, QImage.Format.Format_ARGB32)
    dpm = round(96.0 / 0.0254)
    img.setDotsPerMeterX(dpm)
    img.setDotsPerMeterY(dpm)
    return img


class LienzoPDF:
    """Compositor paginado multi-página sobre QPdfWriter en tamaño Carta."""

    def __init__(
        self,
        ruta_destino: Path | str,
        titulo_doc: str,
        empresa: str,
        subtitulo_continuacion: str = "",
        color_primario: str = "#003D95",
        emitido_texto: str = "",
    ) -> None:
        asegurar_qapplication()
        self.ruta_objetivo = Path(ruta_destino)
        self.titulo_doc = titulo_doc
        self.empresa = empresa or "Control de Tiempos"
        self.subtitulo_continuacion = subtitulo_continuacion
        self.paleta = PaletaPDF.desde_hex(color_primario)
        self.emitido_texto = emitido_texto or datetime.now().strftime("%d/%m/%Y %H:%M")

        self._ref = _imagen_referencia_96dpi()
        self._paginas: list[list[ComandoDibujo]] = [[]]
        self.y = Y_INICIO_PAG1

    # ------------------------------------------------------------------
    # Métricas y paginación
    # ------------------------------------------------------------------

    @property
    def ancho(self) -> float:
        return ANCHO_CONTENIDO

    @property
    def x_inicio(self) -> float:
        return MARGEN_X

    @property
    def espacio_restante(self) -> float:
        return max(0.0, Y_LIMITE_CONTENIDO - self.y)

    def metricas(self, fuente: QFont) -> QFontMetricsF:
        """Devuelve QFontMetricsF calibrado a los 96 DPI del PDF."""
        return QFontMetricsF(fuente, self._ref)

    def medir_texto(
        self,
        texto: str,
        ancho_max: float,
        fuente: QFont,
        interlineado: float = 1.0,
    ) -> float:
        """Calcula el alto exacto de ``texto`` envuelto dentro de ``ancho_max``."""
        if not texto:
            return 0.0
        flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)
        rect = self.metricas(fuente).boundingRect(
            QRectF(0.0, 0.0, max(12.0, ancho_max), 4000.0),
            flags,
            texto,
        )
        return float(rect.height()) * interlineado + 2.0

    def agregar_cmd(self, fn: ComandoDibujo) -> None:
        """Encola una primitiva de dibujo en la página activa."""
        self._paginas[-1].append(fn)

    def nueva_pagina(self) -> None:
        """Abre una página nueva y reposiciona el cursor debajo de la cabecera continua."""
        self._paginas.append([])
        self.y = Y_INICIO_CONT

    def asegurar_espacio(self, alto_necesario: float) -> bool:
        """Salta a una nueva página si ``alto_necesario`` excede el límite inferior."""
        if self.y + alto_necesario > Y_LIMITE_CONTENIDO and self._paginas[-1]:
            self.nueva_pagina()
            return True
        return False

    def avanzar(self, delta: float) -> None:
        self.y += delta

    # ------------------------------------------------------------------
    # Primitivas vectoriales reutilizables
    # ------------------------------------------------------------------

    def dibujar_rect_redondeado(
        self,
        rect: QRectF,
        rx: float,
        fondo: QColor | None = None,
        borde: QColor | None = None,
        grosor_borde: float = 1.0,
    ) -> None:
        r = QRectF(rect)
        f = QColor(fondo) if fondo is not None else None
        b = QColor(borde) if borde is not None else None

        def _draw(p: QPainter, _r: QRectF = r, _rx: float = rx, _f: QColor | None = f, _b: QColor | None = b, _w: float = grosor_borde) -> None:
            p.save()
            if _b is not None:
                p.setPen(QPen(_b, _w))
            else:
                p.setPen(Qt.PenStyle.NoPen)
            if _f is not None:
                p.setBrush(_f)
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(_r, _rx, _rx)
            p.restore()

        self.agregar_cmd(_draw)

    def dibujar_linea(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: QColor,
        grosor: float = 1.0,
        punteada: bool = False,
    ) -> None:
        c = QColor(color)

        def _draw(p: QPainter, _x1: float = x1, _y1: float = y1, _x2: float = x2, _y2: float = y2, _c: QColor = c, _g: float = grosor, _pt: bool = punteada) -> None:
            p.save()
            pen = QPen(_c, _g)
            if _pt:
                pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawLine(QRectF(_x1, _y1, 0, 0).topLeft(), QRectF(_x2, _y2, 0, 0).topLeft())
            p.restore()

        self.agregar_cmd(_draw)

    def dibujar_texto(
        self,
        rect: QRectF,
        texto: str,
        fuente: QFont,
        color: QColor,
        alineacion: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        envolver: bool = True,
    ) -> None:
        r = QRectF(rect)
        f = QFont(fuente)
        c = QColor(color)
        t = str(texto)
        flags = int(alineacion)
        if envolver:
            flags |= int(Qt.TextFlag.TextWordWrap)

        def _draw(p: QPainter, _r: QRectF = r, _f: QFont = f, _c: QColor = c, _t: str = t, _fl: int = flags) -> None:
            p.save()
            p.setFont(_f)
            p.setPen(_c)
            p.drawText(_r, _fl, _t)
            p.restore()

        self.agregar_cmd(_draw)

    def dibujar_pill(
        self,
        x: float,
        y: float,
        texto: str,
        fondo: QColor,
        texto_color: QColor,
        borde: QColor | None = None,
        tam_pt: float = 7.6,
        pad_x: float = 8.0,
        alto: float = 19.0,
    ) -> float:
        """Dibuja una insignia redondeada compacta y devuelve su ancho total."""
        f = fuente_pdf(tam_pt, QFont.Weight.DemiBold)
        tw = self.metricas(f).horizontalAdvance(texto)
        ancho = tw + 2.0 * pad_x
        rect = QRectF(x, y, ancho, alto)
        self.dibujar_rect_redondeado(rect, alto / 2.0, fondo=fondo, borde=borde, grosor_borde=0.8)
        self.dibujar_texto(
            rect,
            texto,
            f,
            texto_color,
            alineacion=Qt.AlignmentFlag.AlignCenter,
            envolver=False,
        )
        return ancho

    def dibujar_seccion(self, titulo: str, subtitulo: str = "", alto_min_siguiente: float = 54.0) -> None:
        """Título de sección con acento vertical corporativo (protegido contra huérfanos)."""
        self.asegurar_espacio(26.0 + alto_min_siguiente)
        x = MARGEN_X
        y = self.y
        f_tit = fuente_pdf(11.0, QFont.Weight.Bold)
        tit_w = self.metricas(f_tit).horizontalAdvance(titulo)

        # Pastilla vertical izquierda
        self.dibujar_rect_redondeado(QRectF(x, y + 2.0, 4.0, 15.0), 2.0, fondo=self.paleta.primario)
        self.dibujar_texto(
            QRectF(x + 10.0, y, min(480.0, tit_w + 16.0), 20.0),
            titulo,
            f_tit,
            self.paleta.texto,
            envolver=False,
        )

        # Subtítulo a la derecha o línea extensora elegante
        linea_x = x + 16.0 + min(480.0, tit_w)
        if subtitulo:
            f_sub = fuente_pdf(7.8, QFont.Weight.Normal)
            sub_w = self.metricas(f_sub).horizontalAdvance(subtitulo) + 6.0
            self.dibujar_texto(
                QRectF(MARGEN_X + ANCHO_CONTENIDO - sub_w, y + 2.0, sub_w, 16.0),
                subtitulo,
                f_sub,
                self.paleta.texto_suave,
                alineacion=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                envolver=False,
            )
            fin_linea = MARGEN_X + ANCHO_CONTENIDO - sub_w - 10.0
        else:
            fin_linea = MARGEN_X + ANCHO_CONTENIDO

        if fin_linea > linea_x + 16.0:
            self.dibujar_linea(linea_x, y + 10.5, fin_linea, y + 10.5, self.paleta.borde, 1.0)

        self.avanzar(24.0)

    # ------------------------------------------------------------------
    # Bloques estructurales comunes (Hero, Metadatos, Tablas, Firmas)
    # ------------------------------------------------------------------

    def _cargar_logo(self, ruta_logo: str | None) -> tuple[str, Path | None]:
        if not ruta_logo:
            return ("", None)
        p = Path(ruta_logo)
        if not p.exists():
            return ("", None)
        # Preferimos SVG si existe un SVG hermano del PNG por defecto
        if p.suffix.lower() == ".png":
            hermano_svg = p.with_suffix(".svg")
            if hermano_svg.exists():
                return ("svg", hermano_svg)
        if p.suffix.lower() == ".svg":
            return ("svg", p)
        return ("raster", p)

    def dibujar_cabecera_hero(
        self,
        eyebrow: str,
        titulo: str,
        subtitulo: str,
        estado_badge: str,
        horario_texto: str = "",
        ruta_logo: str | None = None,
    ) -> None:
        """Dibuja el banner corporativo superior con logotipo y ficha de emisión."""
        y0 = self.y
        pal = self.paleta
        tipo_logo, path_logo = self._cargar_logo(ruta_logo)

        x_tit = MARGEN_X + (152.0 if path_logo else 20.0)
        w_tit = (MARGEN_X + ANCHO_CONTENIDO - 216.0) - x_tit
        f_eye = fuente_pdf(7.6, QFont.Weight.Bold)
        tam_tit = 15.0
        f_tit = fuente_pdf(tam_tit, QFont.Weight.Bold)
        if self.metricas(f_tit).horizontalAdvance(titulo) > w_tit * 0.96:
            tam_tit = 12.8
            f_tit = fuente_pdf(tam_tit, QFont.Weight.Bold)
        f_sub = fuente_pdf(8.8, QFont.Weight.Normal)

        alto_tit = self.medir_texto(titulo, w_tit, f_tit)
        y_tit = y0 + 27.0
        y_sub = max(y0 + 54.0, y_tit + alto_tit + 4.0)
        h = max(96.0, (y_sub - y0) + 26.0)
        rect_hero = QRectF(MARGEN_X, y0, ANCHO_CONTENIDO, h)

        def _draw_banner(
            p: QPainter,
            _r: QRectF = QRectF(rect_hero),
            _p1: QColor = pal.primario,
            _p2: QColor = pal.primario_oscuro,
            _tipo_l: str = tipo_logo,
            _path_l: Path | None = path_logo,
        ) -> None:
            p.save()
            grad = QLinearGradient(_r.topLeft(), _r.bottomRight())
            grad.setColorAt(0.0, _p1)
            grad.setColorAt(1.0, _p2)
            path = QPainterPath()
            path.addRoundedRect(_r, 12.0, 12.0)
            p.setClipPath(path)
            p.fillPath(path, grad)

            # Acento geométrico sutil en el fondo del banner
            acento = QColor(255, 255, 255, 16)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(acento)
            p.drawEllipse(QRectF(_r.right() - 180, _r.top() - 75, 230, 230))
            p.drawEllipse(QRectF(_r.right() - 90, _r.bottom() - 55, 150, 150))

            # Tarjeta blanca contenedora del logo para máximo contraste
            if _path_l is not None:
                box_logo = QRectF(_r.left() + 14.0, _r.top() + (_r.height() - 68.0) / 2.0, 124.0, 68.0)
                p.setBrush(QColor("#FFFFFF"))
                p.drawRoundedRect(box_logo, 9.0, 9.0)
                inner = box_logo.adjusted(8.0, 8.0, -8.0, -8.0)
                if _tipo_l == "svg":
                    ren = QSvgRenderer(str(_path_l))
                    if ren.isValid():
                        sz = QSizeF(ren.defaultSize())
                        if sz.width() > 0 and sz.height() > 0:
                            esc = min(inner.width() / sz.width(), inner.height() / sz.height())
                            w_r = sz.width() * esc
                            h_r = sz.height() * esc
                            dest = QRectF(
                                inner.center().x() - w_r / 2.0,
                                inner.center().y() - h_r / 2.0,
                                w_r,
                                h_r,
                            )
                            ren.render(p, dest)
                else:
                    img = QImage(str(_path_l))
                    if not img.isNull():
                        esc = min(inner.width() / img.width(), inner.height() / img.height())
                        w_r = img.width() * esc
                        h_r = img.height() * esc
                        dest = QRectF(
                            inner.center().x() - w_r / 2.0,
                            inner.center().y() - h_r / 2.0,
                            w_r,
                            h_r,
                        )
                        p.drawImage(dest, img)
            p.restore()

        self.agregar_cmd(_draw_banner)

        self.dibujar_texto(
            QRectF(x_tit, y0 + 12.0, w_tit, 14.0),
            eyebrow.upper(),
            f_eye,
            QColor("#BFDBFE"),
            envolver=False,
        )
        self.dibujar_texto(
            QRectF(x_tit, y_tit, w_tit, alto_tit + 4.0),
            titulo,
            f_tit,
            QColor("#FFFFFF"),
            envolver=True,
        )
        self.dibujar_texto(
            QRectF(x_tit, y_sub, w_tit, 18.0),
            subtitulo,
            f_sub,
            QColor("#E0F2FE"),
            envolver=False,
        )

        # Panel translúcido derecho
        box_der = QRectF(MARGEN_X + ANCHO_CONTENIDO - 204.0, y0 + 12.0, 190.0, 72.0)
        self.dibujar_rect_redondeado(
            box_der,
            9.0,
            fondo=QColor(255, 255, 255, 30),
            borde=QColor(255, 255, 255, 78),
            grosor_borde=1.0,
        )
        # Insignia estado
        self.dibujar_pill(
            box_der.left() + 10.0,
            box_der.top() + 8.0,
            estado_badge.upper(),
            fondo=QColor(255, 255, 255, 235),
            texto_color=pal.primario_oscuro,
            tam_pt=7.2,
            pad_x=8.0,
            alto=17.0,
        )
        f_meta_der = fuente_pdf(7.4, QFont.Weight.Normal)
        if horario_texto:
            self.dibujar_texto(
                QRectF(box_der.left() + 10.0, box_der.top() + 29.0, 170.0, 24.0),
                horario_texto,
                f_meta_der,
                QColor("#F8FAFC"),
            )
        self.dibujar_texto(
            QRectF(box_der.left() + 10.0, box_der.bottom() - 18.0, 170.0, 14.0),
            f"Emitido: {self.emitido_texto}",
            fuente_pdf(7.1, QFont.Weight.DemiBold),
            QColor("#DBEAFE"),
            envolver=False,
        )
        self.y = y0 + h + 8.0

    def dibujar_tira_metadatos(self, campos: list[tuple[str, str]]) -> None:
        """Tira horizontal limpia de ficha técnica con separadores verticales."""
        if not campos:
            return
        y0 = self.y
        h = 40.0
        rect = QRectF(MARGEN_X, y0, ANCHO_CONTENIDO, h)
        self.dibujar_rect_redondeado(
            rect,
            8.0,
            fondo=self.paleta.fondo_tarjeta,
            borde=self.paleta.borde,
            grosor_borde=1.0,
        )
        col_w = ANCHO_CONTENIDO / len(campos)
        f_lbl = fuente_pdf(6.9, QFont.Weight.Bold)
        f_val = fuente_pdf(8.6, QFont.Weight.DemiBold)
        for idx, (lbl, val) in enumerate(campos):
            cx = MARGEN_X + idx * col_w
            if idx > 0:
                self.dibujar_linea(cx, y0 + 8.0, cx, y0 + h - 8.0, self.paleta.borde, 1.0)
            self.dibujar_texto(
                QRectF(cx + 12.0, y0 + 5.0, col_w - 22.0, 12.0),
                lbl.upper(),
                f_lbl,
                self.paleta.texto_suave,
                envolver=False,
            )
            self.dibujar_texto(
                QRectF(cx + 12.0, y0 + 18.0, col_w - 22.0, 18.0),
                val,
                f_val,
                self.paleta.texto,
                envolver=False,
            )
        self.y = y0 + h + 12.0

    def dibujar_nota_vacia(self, texto: str) -> None:
        """Tarjeta sutil cuando no existen registros en una sección opcional."""
        self.asegurar_espacio(34.0)
        rect = QRectF(MARGEN_X, self.y, ANCHO_CONTENIDO, 28.0)
        self.dibujar_rect_redondeado(
            rect,
            7.0,
            fondo=self.paleta.fondo_tarjeta,
            borde=self.paleta.borde,
            grosor_borde=1.0,
        )
        self.dibujar_texto(
            rect.adjusted(14.0, 0.0, -14.0, 0.0),
            texto,
            fuente_pdf(8.3, QFont.Weight.Normal, italic=True),
            self.paleta.texto_suave,
            alineacion=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            envolver=False,
        )
        self.y += 38.0

    def dibujar_tabla_paginada(
        self,
        columnas: list[tuple[str, float, Qt.AlignmentFlag]],
        filas: list[list[str]],
        fila_totales: list[str] | None = None,
        tam_pt: float = 8.0,
    ) -> None:
        """Renderiza una tabla limpia con repetición de encabezados al cambiar de página.

        Cada fila se mide previamente para impedir cortes de línea entre páginas y
        evitar que las cabeceras se partan a mitad de palabra.
        """
        if not filas:
            return

        f_head = fuente_pdf(7.6, QFont.Weight.Bold)
        f_body = fuente_pdf(tam_pt, QFont.Weight.Normal)
        f_body_bold = fuente_pdf(tam_pt, QFont.Weight.DemiBold)
        f_tot = fuente_pdf(tam_pt, QFont.Weight.Bold)
        pad_x = 8.0
        pad_y = 6.0
        h_head = 25.0

        def _pintar_encabezado(y_pos: float) -> float:
            r_hdr = QRectF(MARGEN_X, y_pos, ANCHO_CONTENIDO, h_head)
            self.dibujar_rect_redondeado(
                r_hdr,
                6.0,
                fondo=self.paleta.neutro_suave,
                borde=self.paleta.borde,
                grosor_borde=1.0,
            )
            cx = MARGEN_X
            for tit, w_col, alig in columnas:
                self.dibujar_texto(
                    QRectF(cx + pad_x, y_pos, w_col - 2.0 * pad_x, h_head),
                    tit,
                    f_head,
                    QColor("#334155"),
                    alineacion=alig | Qt.AlignmentFlag.AlignVCenter,
                    envolver=False,
                )
                cx += w_col
            return y_pos + h_head + 2.0

        alto_tot_est = (
            max(25.0, self._alto_fila(fila_totales, columnas, f_tot, pad_x, pad_y))
            if fila_totales
            else 0.0
        )

        # Al menos el encabezado + primera fila deben caber juntos
        primera_h = self._alto_fila(filas[0], columnas, f_body, pad_x, pad_y)
        extra_si_unica = alto_tot_est + 6.0 if len(filas) == 1 and fila_totales else 0.0
        self.asegurar_espacio(h_head + primera_h + extra_si_unica + 6.0)
        self.y = _pintar_encabezado(self.y)

        for idx, fila in enumerate(filas):
            alto_f = self._alto_fila(fila, columnas, f_body, pad_x, pad_y)
            es_ultima = idx == len(filas) - 1
            alto_requerido = alto_f + (alto_tot_est + 6.0 if es_ultima and fila_totales else 0.0)
            if self.y + alto_requerido > Y_LIMITE_CONTENIDO:
                self.nueva_pagina()
                self.y = _pintar_encabezado(self.y)

            r_row = QRectF(MARGEN_X, self.y, ANCHO_CONTENIDO, alto_f)
            if idx % 2 == 1:
                self.dibujar_rect_redondeado(r_row, 4.0, fondo=QColor("#FAFCFF"))
            self.dibujar_linea(
                MARGEN_X + 2.0,
                self.y + alto_f,
                MARGEN_X + ANCHO_CONTENIDO - 2.0,
                self.y + alto_f,
                QColor("#EDF2F7"),
                0.8,
            )

            cx = MARGEN_X
            for c_idx, ((_, w_col, alig), celda) in enumerate(zip(columnas, fila)):
                fuente_celda = f_body_bold if c_idx == 0 else f_body
                color_celda = self.paleta.texto if c_idx == 0 else self.paleta.texto_sec
                self.dibujar_texto(
                    QRectF(cx + pad_x, self.y + pad_y, w_col - 2.0 * pad_x, alto_f - 2.0 * pad_y),
                    celda,
                    fuente_celda,
                    color_celda,
                    alineacion=alig | Qt.AlignmentFlag.AlignTop,
                    envolver=True,
                )
                cx += w_col
            self.y += alto_f

        if fila_totales:
            alto_t = max(25.0, self._alto_fila(fila_totales, columnas, f_tot, pad_x, pad_y))
            if self.y + alto_t > Y_LIMITE_CONTENIDO:
                self.nueva_pagina()
                self.y = _pintar_encabezado(self.y)
            r_tot = QRectF(MARGEN_X, self.y + 2.0, ANCHO_CONTENIDO, alto_t)
            self.dibujar_rect_redondeado(
                r_tot,
                6.0,
                fondo=self.paleta.primario_suave,
                borde=self.paleta.primario_borde,
                grosor_borde=1.0,
            )
            cx = MARGEN_X
            for (_, w_col, alig), celda in zip(columnas, fila_totales):
                self.dibujar_texto(
                    QRectF(cx + pad_x, r_tot.top() + pad_y, w_col - 2.0 * pad_x, alto_t - 2.0 * pad_y),
                    celda,
                    f_tot,
                    self.paleta.primario_oscuro,
                    alineacion=alig | Qt.AlignmentFlag.AlignVCenter,
                    envolver=True,
                )
                cx += w_col
            self.y = r_tot.bottom() + 4.0

        self.avanzar(10.0)

    def _alto_fila(
        self,
        fila: list[str],
        columnas: list[tuple[str, float, Qt.AlignmentFlag]],
        fuente: QFont,
        pad_x: float,
        pad_y: float,
    ) -> float:
        max_h = 15.0
        for (_, w_col, _), celda in zip(columnas, fila):
            h = self.medir_texto(celda, w_col - 2.0 * pad_x, fuente)
            if h > max_h:
                max_h = h
        return max(24.0, max_h + 2.0 * pad_y)

    def dibujar_firmas(self, usuario_nombre: str, nota_extra: str = "Dirección / Supervisión") -> None:
        """Bloque de firmas de cierre protegido para no partirse entre páginas."""
        self.asegurar_espacio(78.0)
        y0 = self.y + 8.0
        col_w = (ANCHO_CONTENIDO - 48.0) / 2.0
        f_nom = fuente_pdf(8.3, QFont.Weight.DemiBold)
        f_rol = fuente_pdf(7.4, QFont.Weight.Normal)

        for i, (linea_sup, linea_inf) in enumerate(
            [
                ("Elaborado y reportado por", usuario_nombre),
                ("Revisado / Visto bueno", nota_extra),
            ]
        ):
            bx = MARGEN_X + i * (col_w + 48.0)
            self.dibujar_linea(bx + 10.0, y0 + 34.0, bx + col_w - 10.0, y0 + 34.0, QColor("#94A3B8"), 1.0)
            self.dibujar_texto(
                QRectF(bx, y0 + 38.0, col_w, 15.0),
                linea_inf,
                f_nom,
                self.paleta.texto,
                alineacion=Qt.AlignmentFlag.AlignCenter,
                envolver=False,
            )
            self.dibujar_texto(
                QRectF(bx, y0 + 53.0, col_w, 14.0),
                linea_sup,
                f_rol,
                self.paleta.texto_suave,
                alineacion=Qt.AlignmentFlag.AlignCenter,
                envolver=False,
            )
        self.y = y0 + 70.0

    # ------------------------------------------------------------------
    # Emisión final sobre QPdfWriter
    # ------------------------------------------------------------------

    def _dibujar_cromo_pagina(self, p: QPainter, num_pag: int, total_pags: int) -> None:
        pal = self.paleta
        if num_pag > 1:
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(pal.primario)
            p.drawRect(QRectF(MARGEN_X, 20.0, 26.0, 3.0))
            p.setFont(fuente_pdf(8.0, QFont.Weight.Bold))
            p.setPen(pal.texto)
            p.drawText(
                QRectF(MARGEN_X + 34.0, 14.0, 380.0, 16.0),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                f"{self.empresa} · {self.titulo_doc}",
            )
            if self.subtitulo_continuacion:
                p.setFont(fuente_pdf(7.8, QFont.Weight.Normal))
                p.setPen(pal.texto_suave)
                p.drawText(
                    QRectF(MARGEN_X + 414.0, 14.0, ANCHO_CONTENIDO - 414.0, 16.0),
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                    self.subtitulo_continuacion,
                )
            p.setPen(QPen(pal.borde, 0.9))
            p.drawLine(
                QRectF(MARGEN_X, 38.0, 0, 0).topLeft(),
                QRectF(MARGEN_X + ANCHO_CONTENIDO, 38.0, 0, 0).topLeft(),
            )
            p.restore()

        # Pie de página uniforme con numeración exacta X de Y
        p.save()
        p.setPen(QPen(pal.borde, 0.9))
        p.drawLine(
            QRectF(MARGEN_X, Y_PIE - 4.0, 0, 0).topLeft(),
            QRectF(MARGEN_X + ANCHO_CONTENIDO, Y_PIE - 4.0, 0, 0).topLeft(),
        )
        p.setFont(fuente_pdf(7.4, QFont.Weight.Normal))
        p.setPen(pal.texto_suave)
        p.drawText(
            QRectF(MARGEN_X, Y_PIE + 2.0, 310.0, 16.0),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            f"{self.empresa} · Control de Tiempos",
        )
        p.drawText(
            QRectF(MARGEN_X + 310.0, Y_PIE + 2.0, 220.0, 16.0),
            int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter),
            f"Emitido: {self.emitido_texto}",
        )
        p.setFont(fuente_pdf(7.6, QFont.Weight.DemiBold))
        p.setPen(pal.texto_sec)
        p.drawText(
            QRectF(MARGEN_X + 540.0, Y_PIE + 2.0, ANCHO_CONTENIDO - 540.0, 16.0),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            f"Página {num_pag} de {total_pags}",
        )
        p.restore()

    def finalizar(self) -> Path:
        """Renderiza todas las páginas acumuladas a disco en el archivo PDF."""
        destino = _resolver_ruta_escribible(self.ruta_objetivo)
        writer = QPdfWriter(str(destino))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
        writer.setPageMargins(QMarginsF(0.0, 0.0, 0.0, 0.0))
        writer.setResolution(96)
        writer.setTitle(self.titulo_doc)
        writer.setCreator(f"{self.empresa} · Control de Tiempos")

        painter = QPainter()
        if not painter.begin(writer):
            sello = datetime.now().strftime("%Y%m%d_%H%M%S")
            destino = destino.with_name(f"{destino.stem}_{sello}.pdf")
            writer = QPdfWriter(str(destino))
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
            writer.setPageMargins(QMarginsF(0.0, 0.0, 0.0, 0.0))
            writer.setResolution(96)
            writer.setTitle(self.titulo_doc)
            if not painter.begin(writer):
                raise OSError(f"No fue posible inicializar la escritura del PDF en {destino}")

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        total = len(self._paginas)
        try:
            for idx, comandos in enumerate(self._paginas):
                if idx > 0:
                    writer.newPage()
                for cmd in comandos:
                    cmd(painter)
                self._dibujar_cromo_pagina(painter, idx + 1, total)
        finally:
            painter.end()

        return destino


def renderizar_html_a_pdf(html: str, ruta_destino: Path | str) -> Path:
    """Convierte HTML a archivo PDF Carta (compatibilidad con flujos auxiliares)."""
    asegurar_qapplication()
    destino = _resolver_ruta_escribible(Path(ruta_destino))

    writer = QPdfWriter(str(destino))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
    writer.setPageMargins(QMarginsF(14, 14, 14, 16))
    writer.setResolution(150)

    doc = QTextDocument()
    doc.setHtml(html)
    doc.print_(writer)
    return destino


def abrir_archivo_pdf(ruta: Path | str) -> None:
    """Abre el archivo PDF con el visor predeterminado del sistema operativo."""
    ruta_p = Path(ruta).resolve()
    if not ruta_p.exists():
        return
    if sys.platform.startswith("win"):
        os.startfile(str(ruta_p))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(ruta_p)])
    else:
        subprocess.Popen(["xdg-open", str(ruta_p)])


def abrir_carpeta_contenedora(ruta: Path | str) -> None:
    """Abre en el explorador la carpeta donde se guardó el PDF."""
    ruta_p = Path(ruta).resolve()
    carpeta = ruta_p if ruta_p.is_dir() else ruta_p.parent
    if not carpeta.exists():
        return
    if sys.platform.startswith("win"):
        if ruta_p.is_file():
            subprocess.Popen(["explorer", "/select,", str(ruta_p)])
        else:
            os.startfile(str(carpeta))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(carpeta)])
    else:
        subprocess.Popen(["xdg-open", str(carpeta)])
