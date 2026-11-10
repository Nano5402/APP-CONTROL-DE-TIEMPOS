"""Pantalla 1: Hoy (principal) — RF-02, RF-03, RF-03b, RF-03c, RF-07, RF-10.

Diseño guiado y contextual:
- Si **no hay actividad en curso**, muestra únicamente el botón grande
  **▶ Iniciar / Reanudar** (ocultando Pausar, Finalizar y Siguiente para no confundir).
- Si **hay una actividad en curso**, muestra los botones **⏸ Pausar**, **⏹ Finalizar**
  y **⏭ Terminar esta y empezar siguiente**.
- En la barra inferior de la tabla, los botones especiales (**✔/✖ Decisión ingeniero**
  y **🔄 Reabrir como Revisión**) solo aparecen cuando la actividad seleccionada
  realmente aplica (bloqueada o completada).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from data.db import BaseDatos
from data.enums import EstadoActividad, EstadoAprobacion, Prioridad, TipoActividad
from data.models import Actividad, Solicitante
from data.repositorios.catalogos import RepoSolicitantes
from data.repositorios.jornadas import RepoJornadas
from services.actividades import ServicioActividades
from services.cronometro import (
    AccionSobreActiva,
    ActividadBloqueadaError,
    ActividadYaEnCursoError,
    ServicioCronometro,
)
from services.productividad import ServicioProductividad
from ui.dialogos import (
    DialogoAprobacionIngeniero,
    DialogoCorregirActividad,
    DialogoPausa,
    DialogoReasignar,
    DialogoRevision,
)
from ui.mini_widget import formatear_reloj_hms


def _etiqueta_estado_visual(act: Actividad) -> str:
    if (
        act.estado == EstadoActividad.BLOQUEADA.value
        or act.aprobacion_estado == EstadoAprobacion.PENDIENTE.value
    ):
        return "🔒 Bloqueada (esperando ing.)"
    mapa = {
        EstadoActividad.EN_CURSO.value: "🟢 En curso",
        EstadoActividad.PAUSADA.value: "🟠 Pausada",
        EstadoActividad.COMPLETADA.value: "✔ Completada",
        EstadoActividad.PENDIENTE.value: "⏳ Pendiente",
        EstadoActividad.ARRASTRADA.value: "🟣 Arrastrada",
        EstadoActividad.REASIGNADA.value: "↗ Reasignada",
        EstadoActividad.RECHAZADA.value: "✖ Rechazada",
        EstadoActividad.APLAZADA.value: "📅 Aplazada",
    }
    return mapa.get(act.estado, act.estado)


def _etiqueta_prioridad_visual(prioridad: str) -> str:
    mapa = {
        Prioridad.MAXIMA.value: "🔴 Máxima",
        Prioridad.NORMAL.value: "🔵 Normal",
        Prioridad.MINIMA.value: "⚪ Mínima",
    }
    return mapa.get(prioridad, prioridad)


def _etiqueta_tipo_visual(act: Actividad) -> str:
    mapa = {
        TipoActividad.PLANEADA.value: "📋 Planeada",
        TipoActividad.EXTRA.value: "⚡ Extra",
        TipoActividad.NO_PLANEADA.value: "💡 No planeada",
    }
    base = mapa.get(act.tipo, act.tipo)
    if act.solicitante:
        return f"{base} · {act.solicitante.nombre}"
    return base


class PantallaHoy(QWidget):
    """Pantalla operativa principal del día."""

    def __init__(
        self,
        bd: BaseDatos,
        *,
        al_cambiar_estado: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bd = bd
        self.al_cambiar_estado = al_cambiar_estado

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        # Encabezado
        fila_enc = QHBoxLayout()
        lbl_tit = QLabel("Hoy — Panel de Actividades", self)
        lbl_tit.setObjectName("tituloPantalla")
        self.lbl_resumen_dia = QLabel("", self)
        self.lbl_resumen_dia.setStyleSheet("font-size: 13px; font-weight: 600;")
        fila_enc.addWidget(lbl_tit)
        fila_enc.addStretch()
        fila_enc.addWidget(self.lbl_resumen_dia)
        layout.addLayout(fila_enc)

        # Tarjeta Hero de cronómetro activo y controles contextuales
        card_cron = QFrame(self)
        card_cron.setObjectName("heroCronometro")
        capa_cron = QHBoxLayout(card_cron)
        capa_cron.setSpacing(18)

        col_info = QVBoxLayout()
        col_info.setSpacing(4)

        fila_badge = QHBoxLayout()
        self.lbl_badge_activa = QLabel("⚪ SIN ACTIVIDAD EN CURSO", self)
        self.lbl_badge_activa.setObjectName("badgeActiva")
        fila_badge.addWidget(self.lbl_badge_activa)
        fila_badge.addStretch()
        col_info.addLayout(fila_badge)

        self.lbl_activa_titulo = QLabel("Ninguna actividad en curso", self)
        self.lbl_activa_titulo.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.lbl_activa_detalle = QLabel(
            "Elige una actividad de la tabla de abajo y pulsa «Iniciar», o escribe una rápida.",
            self,
        )
        self.lbl_activa_detalle.setObjectName("subtitulo")
        col_info.addWidget(self.lbl_activa_titulo)
        col_info.addWidget(self.lbl_activa_detalle)

        col_botones = QHBoxLayout()
        col_botones.setSpacing(8)
        self.btn_iniciar = QPushButton("▶  Iniciar / Reanudar seleccionada", self)
        self.btn_pausar = QPushButton("⏸  Pausar", self)
        self.btn_pausar.setProperty("rol", "advertencia")
        self.btn_finalizar = QPushButton("⏹  Ya terminé (Finalizar)", self)
        self.btn_finalizar.setProperty("rol", "exito")
        self.btn_siguiente = QPushButton("⏭  Terminar esta y empezar siguiente pieza", self)

        for b in (self.btn_iniciar, self.btn_pausar, self.btn_finalizar, self.btn_siguiente):
            b.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_iniciar.clicked.connect(self.accion_iniciar_seleccionada)
        self.btn_pausar.clicked.connect(self.accion_pausar_activa)
        self.btn_finalizar.clicked.connect(self.accion_finalizar_activa)
        self.btn_siguiente.clicked.connect(self.accion_finalizar_y_siguiente)

        col_botones.addWidget(self.btn_iniciar)
        col_botones.addWidget(self.btn_pausar)
        col_botones.addWidget(self.btn_finalizar)
        col_botones.addWidget(self.btn_siguiente)
        col_botones.addStretch()

        col_izq = QVBoxLayout()
        col_izq.setSpacing(10)
        col_izq.addLayout(col_info)
        col_izq.addLayout(col_botones)

        # Caja estilizada del reloj digital
        caja_reloj = QFrame(card_cron)
        caja_reloj.setObjectName("cajaReloj")
        col_reloj = QVBoxLayout(caja_reloj)
        col_reloj.setContentsMargins(16, 8, 16, 8)
        col_reloj.setSpacing(2)
        lbl_cap_reloj = QLabel("CRONÓMETRO", caja_reloj)
        lbl_cap_reloj.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_cap_reloj.setStyleSheet("font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        self.lbl_reloj = QLabel("00:00:00", caja_reloj)
        self.lbl_reloj.setObjectName("relojGrande")
        self.lbl_reloj.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col_reloj.addWidget(lbl_cap_reloj)
        col_reloj.addWidget(self.lbl_reloj)

        capa_cron.addLayout(col_izq, 1)
        capa_cron.addWidget(caja_reloj, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(card_cron)

        # Fila combinada: Meta de tiempo efectivo + Inicio rápido sin plan
        card_meta = QFrame(self)
        card_meta.setProperty("card", True)
        capa_meta = QVBoxLayout(card_meta)
        capa_meta.setContentsMargins(12, 10, 12, 10)
        capa_meta.setSpacing(8)

        fila_barra = QHBoxLayout()
        self.lbl_meta = QLabel("Meta de tiempo efectivo:", self)
        self.lbl_meta.setStyleSheet("font-weight: 600;")
        self.barra_meta = QProgressBar(self)
        self.barra_meta.setRange(0, 100)
        self.lbl_referencia = QLabel("", self)
        self.lbl_referencia.setObjectName("subtitulo")
        fila_barra.addWidget(self.lbl_meta)
        fila_barra.addWidget(self.barra_meta, 1)
        fila_barra.addWidget(self.lbl_referencia)
        capa_meta.addLayout(fila_barra)

        fila_rapida = QHBoxLayout()
        lbl_rap = QLabel("💡 Empezar algo rápido (sin planear):", self)
        lbl_rap.setStyleSheet("font-weight: 600;")
        self.txt_no_planeada = QLineEdit(self)
        self.txt_no_planeada.setPlaceholderText(
            "Escribe qué vas a hacer ahora mismo y pulsa Enter..."
        )
        self.txt_no_planeada.returnPressed.connect(self.accion_iniciar_no_planeada_rapida)
        self.btn_no_planeada = QPushButton("▶ Empezar ya", self)
        self.btn_no_planeada.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_no_planeada.clicked.connect(self.accion_iniciar_no_planeada_rapida)
        fila_rapida.addWidget(lbl_rap)
        fila_rapida.addWidget(self.txt_no_planeada, 1)
        fila_rapida.addWidget(self.btn_no_planeada)
        capa_meta.addLayout(fila_rapida)

        layout.addWidget(card_meta)

        # Guía amistosa cuando aún no hay actividades en el día
        self.lbl_guia_vacia = QLabel(
            "👋 Aún no tienes actividades en tu lista de hoy. Ve a «📋 Planear el día» en el menú izquierdo "
            "para armar tu plan de la mañana, o escribe arriba en «Empezar algo rápido».",
            self,
        )
        self.lbl_guia_vacia.setWordWrap(True)
        self.lbl_guia_vacia.setStyleSheet(
            "background-color: #EFF6FF; color: #1E3A8A; border: 1px solid #BFDBFE; "
            "border-radius: 8px; padding: 10px 14px; font-weight: 500;"
        )
        layout.addWidget(self.lbl_guia_vacia)

        # Tabla de actividades del día
        self.tabla = QTableWidget(0, 7, self)
        self.tabla.setHorizontalHeaderLabels(
            [
                "Actividad (doble clic para iniciar)",
                "Tipo / Solicitante",
                "Prioridad",
                "Estado",
                "Estimado",
                "Tiempo real",
                "Revisiones / Notas",
            ]
        )
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setShowGrid(False)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(38)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.itemDoubleClicked.connect(lambda _item: self.accion_iniciar_seleccionada())
        self.tabla.itemSelectionChanged.connect(self._actualizar_acciones_segun_seleccion)
        layout.addWidget(self.tabla, 1)

        # Barra inferior contextual: solo muestra lo que aplica a la fila seleccionada
        fila_sec = QHBoxLayout()
        fila_sec.setSpacing(8)
        self.lbl_acciones_fila = QLabel("Opciones de la actividad seleccionada:", self)
        self.lbl_acciones_fila.setObjectName("subtitulo")

        self.btn_aprobacion = QPushButton("✔/✖  Aprobar / Rechazar (Ingeniero)", self)
        self.btn_aprobacion.setProperty("rol", "advertencia")
        self.btn_revision = QPushButton("🔄  Pidieron cambios (Nueva revisión)", self)
        self.btn_revision.setProperty("rol", "secundario")
        self.btn_reasignar = QPushButton("↗  Pasar a otro compañero", self)
        self.btn_reasignar.setProperty("rol", "secundario")
        self.btn_corregir = QPushButton("✏  Corregir tiempo o nombre", self)
        self.btn_corregir.setProperty("rol", "secundario")
        self.btn_eliminar = QPushButton("🗑  Quitar de la lista", self)
        self.btn_eliminar.setProperty("rol", "secundario")

        for b in (
            self.btn_aprobacion,
            self.btn_revision,
            self.btn_reasignar,
            self.btn_corregir,
            self.btn_eliminar,
        ):
            b.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_aprobacion.clicked.connect(self.accion_decision_ingeniero)
        self.btn_revision.clicked.connect(self.accion_crear_revision)
        self.btn_reasignar.clicked.connect(self.accion_reasignar)
        self.btn_corregir.clicked.connect(self.accion_corregir)
        self.btn_eliminar.clicked.connect(self.accion_eliminar)

        fila_sec.addWidget(self.lbl_acciones_fila)
        fila_sec.addWidget(self.btn_aprobacion)
        fila_sec.addWidget(self.btn_revision)
        fila_sec.addWidget(self.btn_reasignar)
        fila_sec.addWidget(self.btn_corregir)
        fila_sec.addStretch()
        fila_sec.addWidget(self.btn_eliminar)
        layout.addLayout(fila_sec)

        self.refrescar()

    # ------------------------------------------------------------------
    # Refresco, botones contextuales y reloj en vivo
    # ------------------------------------------------------------------

    def actividad_seleccionada_id(self) -> int | None:
        fila = self.tabla.currentRow()
        if fila < 0:
            return None
        item = self.tabla.item(fila, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _actualizar_acciones_segun_seleccion(self) -> None:
        """Muestra u oculta botones según el estado de la fila seleccionada."""
        act_id = self.actividad_seleccionada_id()
        if act_id is None:
            self.lbl_acciones_fila.setVisible(False)
            self.btn_aprobacion.setVisible(False)
            self.btn_revision.setVisible(False)
            self.btn_reasignar.setVisible(False)
            self.btn_corregir.setVisible(False)
            self.btn_eliminar.setVisible(False)
            return

        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is None:
                return
            es_bloqueada = (
                act.estado == EstadoActividad.BLOQUEADA.value
                or act.aprobacion_estado == EstadoAprobacion.PENDIENTE.value
            )
            raiz = act.actividad_padre or act
            es_completada = raiz.estado == EstadoActividad.COMPLETADA.value
            en_curso = act.estado == EstadoActividad.EN_CURSO.value
            es_pausada = act.estado in (
                EstadoActividad.PAUSADA.value,
                EstadoActividad.ARRASTRADA.value,
            )
            nombre_corto = act.nombre if len(act.nombre) <= 28 else act.nombre[:27] + "…"

        self.lbl_acciones_fila.setVisible(True)
        self.btn_aprobacion.setVisible(es_bloqueada)
        self.btn_revision.setVisible(es_completada)
        self.btn_reasignar.setVisible(not es_completada)
        self.btn_corregir.setVisible(True)
        self.btn_eliminar.setVisible(not en_curso)

        if en_curso:
            self.btn_iniciar.setVisible(False)
        else:
            self.btn_iniciar.setVisible(True)
            verbo = "Reanudar" if es_pausada else "Iniciar"
            self.btn_iniciar.setText(f"▶  {verbo} «{nombre_corto}»")

    def actualizar_reloj_en_vivo(self) -> tuple[str | None, int]:
        """Actualiza el cronómetro en vivo y muestra solo los controles pertinentes."""
        with self.bd.sesion() as s:
            cron = ServicioCronometro(s)
            activa = cron.actividad_en_curso()
            if activa is None:
                self.lbl_reloj.setText("00:00:00")
                self.lbl_badge_activa.setText("⚪ SIN ACTIVIDAD EN CURSO")
                self.lbl_activa_titulo.setText("Ninguna actividad en curso")
                self.lbl_activa_detalle.setText(
                    "Selecciona una actividad de la tabla y pulsa el botón azul «▶ Iniciar» (o haz doble clic)."
                )
                self.btn_pausar.setVisible(False)
                self.btn_finalizar.setVisible(False)
                self.btn_siguiente.setVisible(False)
                self.btn_pausar.setEnabled(False)
                self.btn_finalizar.setEnabled(False)
                self.btn_siguiente.setEnabled(False)
                self.btn_iniciar.setVisible(self.tabla.rowCount() > 0)
                return None, 0

            seg = cron.segundos_trabajados(activa)
            self.lbl_reloj.setText(formatear_reloj_hms(seg))
            self.lbl_badge_activa.setText("🟢 EN CURSO AHORA")
            self.lbl_activa_titulo.setText(activa.nombre)
            cat_txt = activa.categoria.nombre if activa.categoria else "Sin categoría"
            self.lbl_activa_detalle.setText(
                f"Categoría: {cat_txt}  ·  Prioridad: {_etiqueta_prioridad_visual(activa.prioridad)}"
            )
            self.btn_pausar.setVisible(True)
            self.btn_finalizar.setVisible(True)
            self.btn_siguiente.setVisible(True)
            self.btn_pausar.setEnabled(True)
            self.btn_finalizar.setEnabled(True)
            self.btn_siguiente.setEnabled(True)
            return activa.nombre, seg

    def refrescar(self) -> None:
        """Recarga la tabla de actividades de hoy y la barra de progreso."""
        id_previo = self.actividad_seleccionada_id()

        with self.bd.sesion() as s:
            jornada = RepoJornadas(s).obtener_o_crear()
            srv_act = ServicioActividades(s)
            srv_prod = ServicioProductividad(s)

            arrastradas = srv_act.listar_arrastradas_pendientes(jornada.fecha)
            propias = srv_act.listar_visibles_jornada(jornada.id)
            todas = arrastradas + [a for a in propias if a not in arrastradas]

            res_prod = srv_prod.calcular_jornada(jornada)

            self.lbl_guia_vacia.setVisible(len(todas) == 0)
            self.tabla.setRowCount(len(todas))
            fila_seleccionar = -1

            for i, act in enumerate(todas):
                desglose = srv_act.desglose_tiempos(act)
                if act.id == id_previo:
                    fila_seleccionar = i

                nombre_mostrar = act.nombre + (" ★" if act.editado else "")
                it_nom = QTableWidgetItem(nombre_mostrar)
                it_nom.setData(Qt.ItemDataRole.UserRole, act.id)

                it_tipo = QTableWidgetItem(_etiqueta_tipo_visual(act))
                it_prio = QTableWidgetItem(_etiqueta_prioridad_visual(act.prioridad))
                it_estado = QTableWidgetItem(_etiqueta_estado_visual(act))

                it_est_min = QTableWidgetItem(
                    f"{act.tiempo_estimado_min} min" if act.tiempo_estimado_min else "—"
                )
                it_est_min.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                it_tiempo = QTableWidgetItem(formatear_reloj_hms(desglose.segundos_total))
                it_tiempo.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                cambios_txt = (
                    f"🔁 {desglose.cantidad_revisiones} rev."
                    if desglose.solicitaron_cambios
                    else "—"
                )
                if act.reasignada_a:
                    cambios_txt = f"↗ A: {act.reasignada_a}"
                it_cambios = QTableWidgetItem(cambios_txt)

                self.tabla.setItem(i, 0, it_nom)
                self.tabla.setItem(i, 1, it_tipo)
                self.tabla.setItem(i, 2, it_prio)
                self.tabla.setItem(i, 3, it_estado)
                self.tabla.setItem(i, 4, it_est_min)
                self.tabla.setItem(i, 5, it_tiempo)
                self.tabla.setItem(i, 6, it_cambios)

            if fila_seleccionar >= 0:
                self.tabla.selectRow(fila_seleccionar)
            elif todas:
                self.tabla.selectRow(0)

            self.barra_meta.setValue(int(round(res_prod.progreso_meta_pct)))
            ef_min = res_prod.tiempo_efectivo_seg // 60
            meta_min = res_prod.meta_tiempo_seg // 60
            self.lbl_meta.setText(f"⏱ Tiempo efectivo hoy: {ef_min} / {meta_min} min")
            if res_prod.datos_referencia:
                self.lbl_referencia.setText(res_prod.datos_referencia[0].mensaje)
            else:
                self.lbl_referencia.setText("")

            if res_prod.productividad_pct is not None:
                self.lbl_resumen_dia.setText(
                    f"{res_prod.semaforo.emoji()} Productividad parcial: {res_prod.productividad_pct:.1f}% ({res_prod.semaforo.etiqueta()})"
                )
            else:
                self.lbl_resumen_dia.setText("⚪ Día no laboral (solo registro de tiempo)")

        self.actualizar_reloj_en_vivo()
        self._actualizar_acciones_segun_seleccion()
        if self.al_cambiar_estado:
            self.al_cambiar_estado()

    # ------------------------------------------------------------------
    # Acciones de cronómetro y gestión
    # ------------------------------------------------------------------

    def accion_iniciar_seleccionada(self) -> None:
        act_id = self.actividad_seleccionada_id()
        if act_id is None:
            QMessageBox.information(self, "Selecciona una actividad", "Elige una fila de la tabla.")
            return

        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is None:
                return
            cron = ServicioCronometro(s)
            try:
                cron.iniciar(act)
            except ActividadBloqueadaError as exc:
                QMessageBox.warning(self, "Actividad bloqueada", str(exc))
                return
            except ActividadYaEnCursoError as exc:
                resp = QMessageBox.question(
                    self,
                    "Ya hay una actividad en curso",
                    f"«{exc.actividad_activa.nombre}» está en curso.\n\n"
                    "¿Deseas FINALIZARLA antes de iniciar la nueva?\n"
                    "(Elige «No» para dejarla PAUSADA o «Cancelar» para no cambiar).",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel,
                )
                if resp == QMessageBox.StandardButton.Cancel:
                    return
                accion = (
                    AccionSobreActiva.FINALIZAR
                    if resp == QMessageBox.StandardButton.Yes
                    else AccionSobreActiva.PAUSAR
                )
                cron.iniciar(act, accion_sobre_activa=accion)
            except ValueError as exc:
                QMessageBox.warning(self, "No se puede iniciar", str(exc))
                return

        self.refrescar()

    def accion_iniciar_no_planeada_rapida(self) -> None:
        nombre = self.txt_no_planeada.text().strip()
        if not nombre:
            return
        with self.bd.sesion() as s:
            srv_act = ServicioActividades(s)
            cron = ServicioCronometro(s)
            act = srv_act.crear_no_planeada(nombre)
            cron.iniciar(act, accion_sobre_activa=AccionSobreActiva.PAUSAR)
        self.txt_no_planeada.clear()
        self.refrescar()

    def accion_pausar_activa(self) -> None:
        with self.bd.sesion() as s:
            cron = ServicioCronometro(s)
            activa = cron.actividad_en_curso()
            if activa is None:
                return
            nombre = activa.nombre

        dlg = DialogoPausa(nombre, self)
        if dlg.exec() != DialogoPausa.DialogCode.Accepted:
            return

        with self.bd.sesion() as s:
            cron = ServicioCronometro(s)
            activa = cron.actividad_en_curso()
            if activa is not None:
                cron.pausar(
                    activa,
                    tipo=dlg.tipo_pausa,
                    motivo=dlg.motivo or None,
                    avance_pct=dlg.avance_pct,
                )
        self.refrescar()

    def accion_finalizar_activa(self) -> None:
        with self.bd.sesion() as s:
            cron = ServicioCronometro(s)
            activa = cron.actividad_en_curso()
            if activa is None:
                return
            cron.finalizar(activa)
        self.refrescar()

    def accion_finalizar_y_siguiente(self) -> None:
        with self.bd.sesion() as s:
            cron = ServicioCronometro(s)
            activa = cron.actividad_en_curso()
            if activa is None:
                return
            cron.finalizar_y_empezar_siguiente(activa)
        self.refrescar()

    def accion_decision_ingeniero(self) -> None:
        act_id = self.actividad_seleccionada_id()
        if act_id is None:
            return
        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is None:
                return
            nombre = act.nombre

        dlg = DialogoAprobacionIngeniero(nombre, self)
        if dlg.exec() != DialogoAprobacionIngeniero.DialogCode.Accepted:
            return

        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is not None:
                ServicioActividades(s).registrar_decision_ingeniero(
                    act, aprobada=dlg.aprobada, canal=dlg.canal
                )
        self.refrescar()

    def accion_crear_revision(self) -> None:
        act_id = self.actividad_seleccionada_id()
        if act_id is None:
            return
        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is None:
                return
            raiz = act.actividad_padre or act
            if raiz.estado != EstadoActividad.COMPLETADA.value:
                QMessageBox.information(
                    self,
                    "Actividad no completada",
                    "Solo puedes crear una revisión sobre una actividad ya finalizada.",
                )
                return
            solicitantes = RepoSolicitantes(s).listar_activos()
            nombre_raiz = raiz.nombre

        dlg = DialogoRevision(nombre_raiz, solicitantes, self)
        if dlg.exec() != DialogoRevision.DialogCode.Accepted:
            return

        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            sol = s.get(Solicitante, dlg.solicitante_id)
            if act and sol:
                rev = ServicioActividades(s).crear_revision(
                    act,
                    solicitante=sol,
                    tipo_revision=dlg.tipo_revision,
                    que_cambiar=dlg.que_cambiar,
                    motivo=dlg.motivo_revision,
                )
                ServicioCronometro(s).iniciar(
                    rev, accion_sobre_activa=AccionSobreActiva.PAUSAR
                )
        self.refrescar()

    def accion_reasignar(self) -> None:
        act_id = self.actividad_seleccionada_id()
        if act_id is None:
            return
        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is None:
                return
            nombre = act.nombre

        dlg = DialogoReasignar(nombre, self)
        if dlg.exec() != DialogoReasignar.DialogCode.Accepted:
            return

        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is not None:
                ServicioCronometro(s).reasignar(act, persona=dlg.persona, motivo=dlg.motivo)
        self.refrescar()

    def accion_corregir(self) -> None:
        act_id = self.actividad_seleccionada_id()
        if act_id is None:
            return
        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is None:
                return
            dlg = DialogoCorregirActividad(act, self)
            if dlg.exec() != DialogoCorregirActividad.DialogCode.Accepted:
                return
            srv_act = ServicioActividades(s)
            srv_act.corregir_actividad(
                act,
                motivo=dlg.motivo,
                nombre=dlg.nuevo_nombre,
                tiempo_estimado_min=dlg.nuevo_estimado,
                descripcion=dlg.nueva_descripcion,
            )
            if act.sesiones and dlg.nuevo_inicio and dlg.nuevo_fin:
                srv_act.corregir_sesion_tiempo(
                    act.sesiones[-1],
                    motivo=dlg.motivo,
                    nuevo_inicio=dlg.nuevo_inicio,
                    nuevo_fin=dlg.nuevo_fin,
                )
        self.refrescar()

    def accion_eliminar(self) -> None:
        act_id = self.actividad_seleccionada_id()
        if act_id is None:
            return
        with self.bd.sesion() as s:
            act = s.get(Actividad, act_id)
            if act is None:
                return
            try:
                ServicioActividades(s).cambiar_estado_manual(
                    act, EstadoActividad.ELIMINADA, motivo="Eliminada por el usuario"
                )
            except ValueError as exc:
                QMessageBox.warning(self, "No se puede eliminar", str(exc))
                return
        self.refrescar()
