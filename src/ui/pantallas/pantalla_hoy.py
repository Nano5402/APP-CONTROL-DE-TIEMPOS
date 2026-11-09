"""Pantalla 1: Hoy (principal) — RF-02, RF-03, RF-03b, RF-03c, RF-07, RF-10.

Contiene:
- Tarjeta superior de **Actividad en curso** con cronómetro grande (`HH:MM:SS`) y
  botones directos: **Iniciar**, **Pausar**, **Reanudar**, **Finalizar** y
  **"Finalizar y empezar siguiente"** (flujo en máximo 2 clics).
- Barra de progreso de **Meta de tiempo efectivo del día** y datos de referencia.
- Alta rápida de **actividad no planeada** para empezar en 1 clic sin plan previo.
- Tabla de actividades del día (más las arrastradas pendientes de días anteriores)
  con botones de acción para **Aprobar/Rechazar (ingeniero)**, **Revisión**,
  **Reasignar** y **Corregir registro**.
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
from data.enums import EstadoActividad, EstadoAprobacion, TipoActividad
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
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Encabezado
        fila_enc = QHBoxLayout()
        lbl_tit = QLabel("Hoy — Control de Actividades", self)
        lbl_tit.setObjectName("tituloPantalla")
        self.lbl_resumen_dia = QLabel("", self)
        self.lbl_resumen_dia.setObjectName("subtitulo")
        fila_enc.addWidget(lbl_tit)
        fila_enc.addStretch()
        fila_enc.addWidget(self.lbl_resumen_dia)
        layout.addLayout(fila_enc)

        # Tarjeta de cronómetro activo y controles en 1 clic
        card_cron = QFrame(self)
        card_cron.setProperty("card", True)
        capa_cron = QHBoxLayout(card_cron)

        col_info = QVBoxLayout()
        self.lbl_activa_titulo = QLabel("Ninguna actividad en curso", self)
        self.lbl_activa_titulo.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.lbl_activa_detalle = QLabel(
            "Selecciona una actividad de la lista y pulsa Iniciar (o escribe una rápida abajo).",
            self,
        )
        self.lbl_activa_detalle.setObjectName("subtitulo")
        col_info.addWidget(self.lbl_activa_titulo)
        col_info.addWidget(self.lbl_activa_detalle)

        self.lbl_reloj = QLabel("00:00:00", self)
        self.lbl_reloj.setObjectName("relojGrande")

        col_botones = QHBoxLayout()
        self.btn_iniciar = QPushButton("▶ Iniciar / Reanudar", self)
        self.btn_pausar = QPushButton("⏸ Pausar", self)
        self.btn_pausar.setProperty("rol", "advertencia")
        self.btn_finalizar = QPushButton("⏹ Finalizar", self)
        self.btn_finalizar.setProperty("rol", "exito")
        self.btn_siguiente = QPushButton("⏭ Finalizar y empezar siguiente", self)

        self.btn_iniciar.clicked.connect(self.accion_iniciar_seleccionada)
        self.btn_pausar.clicked.connect(self.accion_pausar_activa)
        self.btn_finalizar.clicked.connect(self.accion_finalizar_activa)
        self.btn_siguiente.clicked.connect(self.accion_finalizar_y_siguiente)

        col_botones.addWidget(self.btn_iniciar)
        col_botones.addWidget(self.btn_pausar)
        col_botones.addWidget(self.btn_finalizar)
        col_botones.addWidget(self.btn_siguiente)

        col_izq = QVBoxLayout()
        col_izq.addLayout(col_info)
        col_izq.addLayout(col_botones)

        capa_cron.addLayout(col_izq, 1)
        capa_cron.addWidget(self.lbl_reloj, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(card_cron)

        # Barra de meta de tiempo efectivo + datos de referencia
        card_meta = QFrame(self)
        card_meta.setProperty("card", True)
        capa_meta = QHBoxLayout(card_meta)
        self.lbl_meta = QLabel("Meta de tiempo efectivo:", self)
        self.barra_meta = QProgressBar(self)
        self.barra_meta.setRange(0, 100)
        self.lbl_referencia = QLabel("", self)
        self.lbl_referencia.setObjectName("subtitulo")
        capa_meta.addWidget(self.lbl_meta)
        capa_meta.addWidget(self.barra_meta, 1)
        capa_meta.addWidget(self.lbl_referencia)
        layout.addWidget(card_meta)

        # Inicio rápido de actividad no planeada (trabajar sin plan previo)
        fila_rapida = QHBoxLayout()
        self.txt_no_planeada = QLineEdit(self)
        self.txt_no_planeada.setPlaceholderText(
            "Iniciar actividad rápida no planeada (escribe el nombre y pulsa Enter)..."
        )
        self.txt_no_planeada.returnPressed.connect(self.accion_iniciar_no_planeada_rapida)
        self.btn_no_planeada = QPushButton("+ Iniciar no planeada ya", self)
        self.btn_no_planeada.clicked.connect(self.accion_iniciar_no_planeada_rapida)
        fila_rapida.addWidget(self.txt_no_planeada, 1)
        fila_rapida.addWidget(self.btn_no_planeada)
        layout.addLayout(fila_rapida)

        # Tabla de actividades del día
        self.tabla = QTableWidget(0, 7, self)
        self.tabla.setHorizontalHeaderLabels(
            [
                "Actividad",
                "Tipo / Solicitante",
                "Prioridad",
                "Estado",
                "Estimado",
                "Tiempo total",
                "Cambios / Notas",
            ]
        )
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.itemDoubleClicked.connect(lambda _item: self.accion_iniciar_seleccionada())
        layout.addWidget(self.tabla, 1)

        # Barra inferior de acciones secundarias sobre la fila seleccionada
        fila_sec = QHBoxLayout()
        self.btn_aprobacion = QPushButton("✔/✖ Decisión ingeniero (bloqueada)", self)
        self.btn_aprobacion.setProperty("rol", "secundario")
        self.btn_revision = QPushButton("🔄 Reabrir como Revisión", self)
        self.btn_revision.setProperty("rol", "secundario")
        self.btn_reasignar = QPushButton("👤 Reasignar a compañero", self)
        self.btn_reasignar.setProperty("rol", "secundario")
        self.btn_corregir = QPushButton("✏ Corregir tiempo / datos", self)
        self.btn_corregir.setProperty("rol", "secundario")
        self.btn_eliminar = QPushButton("🗑 Eliminar", self)
        self.btn_eliminar.setProperty("rol", "secundario")

        self.btn_aprobacion.clicked.connect(self.accion_decision_ingeniero)
        self.btn_revision.clicked.connect(self.accion_crear_revision)
        self.btn_reasignar.clicked.connect(self.accion_reasignar)
        self.btn_corregir.clicked.connect(self.accion_corregir)
        self.btn_eliminar.clicked.connect(self.accion_eliminar)

        fila_sec.addWidget(self.btn_aprobacion)
        fila_sec.addWidget(self.btn_revision)
        fila_sec.addWidget(self.btn_reasignar)
        fila_sec.addWidget(self.btn_corregir)
        fila_sec.addStretch()
        fila_sec.addWidget(self.btn_eliminar)
        layout.addLayout(fila_sec)

        self.refrescar()

    # ------------------------------------------------------------------
    # Refresco y reloj en vivo
    # ------------------------------------------------------------------

    def actividad_seleccionada_id(self) -> int | None:
        fila = self.tabla.currentRow()
        if fila < 0:
            return None
        item = self.tabla.item(fila, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def actualizar_reloj_en_vivo(self) -> tuple[str | None, int]:
        """Actualiza únicamente el contador de segundos en vivo y devuelve ``(nombre, seg)``."""
        with self.bd.sesion() as s:
            cron = ServicioCronometro(s)
            activa = cron.actividad_en_curso()
            if activa is None:
                self.lbl_reloj.setText("00:00:00")
                self.btn_pausar.setEnabled(False)
                self.btn_finalizar.setEnabled(False)
                self.btn_siguiente.setEnabled(False)
                return None, 0

            seg = cron.segundos_trabajados(activa)
            self.lbl_reloj.setText(formatear_reloj_hms(seg))
            self.lbl_activa_titulo.setText(f"En curso: {activa.nombre}")
            cat_txt = activa.categoria.nombre if activa.categoria else "Sin categoría"
            self.lbl_activa_detalle.setText(
                f"Categoría: {cat_txt} · Prioridad: {activa.prioridad}"
            )
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

            self.tabla.setRowCount(len(todas))
            fila_seleccionar = -1

            for i, act in enumerate(todas):
                desglose = srv_act.desglose_tiempos(act)
                if act.id == id_previo:
                    fila_seleccionar = i

                nombre_mostrar = act.nombre + (" ★" if act.editado else "")
                it_nom = QTableWidgetItem(nombre_mostrar)
                it_nom.setData(Qt.ItemDataRole.UserRole, act.id)

                sol_txt = f" ({act.solicitante.nombre})" if act.solicitante else ""
                it_tipo = QTableWidgetItem(f"{act.tipo}{sol_txt}")
                it_prio = QTableWidgetItem(act.prioridad)

                est_txt = act.estado
                if (
                    act.estado == EstadoActividad.BLOQUEADA.value
                    or act.aprobacion_estado == EstadoAprobacion.PENDIENTE.value
                ):
                    est_txt = "🔒 Bloqueada (esperando ing.)"
                it_estado = QTableWidgetItem(est_txt)

                it_est_min = QTableWidgetItem(
                    f"{act.tiempo_estimado_min} min" if act.tiempo_estimado_min else "—"
                )
                it_tiempo = QTableWidgetItem(formatear_reloj_hms(desglose.segundos_total))

                cambios_txt = (
                    f"¿Cambios? Sí ({desglose.cantidad_revisiones})"
                    if desglose.solicitaron_cambios
                    else "No"
                )
                if act.reasignada_a:
                    cambios_txt = f"Reasignada a {act.reasignada_a}"
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
            self.lbl_meta.setText(f"Tiempo efectivo: {ef_min} / {meta_min} min")
            if res_prod.datos_referencia:
                self.lbl_referencia.setText(res_prod.datos_referencia[0].mensaje)
            else:
                self.lbl_referencia.setText("")

            if res_prod.productividad_pct is not None:
                self.lbl_resumen_dia.setText(
                    f"{res_prod.semaforo.emoji()} Productividad parcial: {res_prod.productividad_pct:.1f}%"
                )
            else:
                self.lbl_resumen_dia.setText("⚪ Día no laboral (solo registro de tiempo)")

        self.actualizar_reloj_en_vivo()
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
