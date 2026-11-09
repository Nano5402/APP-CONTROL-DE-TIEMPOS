"""Icono en la bandeja del sistema y coordinador periódico de recordatorios (RF-04, RF-12).

Incluye:
- ``IconoBandeja``: icono en el system tray de Windows con menú contextual para
  mostrar/ocultar la ventana principal, pausar/reanudar rápido y salir.
- ``CoordinadorRecordatoriosUI``: conecta un ``QTimer`` con ``ServicioRecordatorios``
  y muestra la ventana emergente al frente (o notificación de Windows) junto con
  el sonido configurado.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMainWindow, QMenu, QSystemTrayIcon

from config import rutas
from data.db import BaseDatos
from data.models import Actividad
from data.repositorios.configuracion import RepoConfiguracion
from services.recordatorios import AvisoRecordatorio, ServicioRecordatorios, TipoAviso
from ui.dialogo_recordatorio import DialogoRecordatorio
from ui.sonido import reproducir_tono_aviso


def crear_icono_app() -> QIcon:
    """Genera un icono limpio en memoria (reloj azul neutro) sin depender de archivos externos."""
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#2563EB"))
    p.setPen(QColor("#1E40AF"))
    p.drawEllipse(4, 4, 56, 56)
    p.setPen(QColor("#FFFFFF"))
    p.drawLine(32, 32, 32, 16)
    p.drawLine(32, 32, 46, 32)
    p.end()
    return QIcon(pix)


class IconoBandeja(QSystemTrayIcon):
    """Icono en la bandeja del sistema con acceso rápido a la ventana."""

    def __init__(self, ventana: QMainWindow) -> None:
        super().__init__(crear_icono_app(), ventana)
        self.ventana = ventana
        self.setToolTip(rutas.NOMBRE_VISIBLE)

        menu = QMenu()
        self.accion_mostrar = QAction("Abrir Control de Tiempos", menu)
        self.accion_mostrar.triggered.connect(self.mostrar_ventana)
        menu.addAction(self.accion_mostrar)

        menu.addSeparator()
        self.accion_salir = QAction("Salir por completo", menu)
        self.accion_salir.triggered.connect(self._salir)
        menu.addAction(self.accion_salir)

        self.setContextMenu(menu)
        self.activated.connect(self._al_activar)

    def mostrar_ventana(self) -> None:
        self.ventana.showNormal()
        self.ventana.raise_()
        self.ventana.activateWindow()

    def _al_activar(self, razon: QSystemTrayIcon.ActivationReason) -> None:
        if razon in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.mostrar_ventana()

    def _salir(self) -> None:
        from PySide6.QtWidgets import QApplication

        self.hide()
        QApplication.quit()


class CoordinadorRecordatoriosUI(QObject):
    """Evalúa periódicamente los recordatorios y lanza el aviso visual + sonoro."""

    def __init__(
        self,
        bd: BaseDatos,
        ventana: QMainWindow,
        bandeja: IconoBandeja | None = None,
        *,
        intervalo_chequeo_ms: int = 15_000,
    ) -> None:
        super().__init__(ventana)
        self.bd = bd
        self.ventana = ventana
        self.bandeja = bandeja
        self._dialogo_abierto: DialogoRecordatorio | None = None
        self._estado_recordatorios = ServicioRecordatorios.__new__(ServicioRecordatorios)
        self._estado_recordatorios._momento_aviso_continuidad_abierto = None
        self._estado_recordatorios._actividad_aviso_continuidad_id = None
        self._estado_recordatorios._finalizacion_notificada_ids = set()
        self._estado_recordatorios._almuerzo_notificado_fecha = None
        self._estado_recordatorios._salida_notificada_fecha = None
        self._estado_recordatorios._ultimo_aviso_sin_actividad = None

        self.timer = QTimer(self)
        self.timer.setInterval(intervalo_chequeo_ms)
        self.timer.timeout.connect(self.verificar_ahora)

    def _vincular_servicio(self, s) -> ServicioRecordatorios:
        srv = ServicioRecordatorios(s)
        srv._momento_aviso_continuidad_abierto = (
            self._estado_recordatorios._momento_aviso_continuidad_abierto
        )
        srv._actividad_aviso_continuidad_id = (
            self._estado_recordatorios._actividad_aviso_continuidad_id
        )
        srv._finalizacion_notificada_ids = self._estado_recordatorios._finalizacion_notificada_ids
        srv._almuerzo_notificado_fecha = self._estado_recordatorios._almuerzo_notificado_fecha
        srv._salida_notificada_fecha = self._estado_recordatorios._salida_notificada_fecha
        srv._ultimo_aviso_sin_actividad = self._estado_recordatorios._ultimo_aviso_sin_actividad
        return srv

    def _guardar_estado(self, srv: ServicioRecordatorios) -> None:
        self._estado_recordatorios._momento_aviso_continuidad_abierto = (
            srv._momento_aviso_continuidad_abierto
        )
        self._estado_recordatorios._actividad_aviso_continuidad_id = (
            srv._actividad_aviso_continuidad_id
        )
        self._estado_recordatorios._finalizacion_notificada_ids = srv._finalizacion_notificada_ids
        self._estado_recordatorios._almuerzo_notificado_fecha = srv._almuerzo_notificado_fecha
        self._estado_recordatorios._salida_notificada_fecha = srv._salida_notificada_fecha
        self._estado_recordatorios._ultimo_aviso_sin_actividad = srv._ultimo_aviso_sin_actividad

    def iniciar(self) -> None:
        self.timer.start()

    def detener(self) -> None:
        self.timer.stop()

    def verificar_ahora(self) -> list[AvisoRecordatorio]:
        """Ejecuta una pasada de evaluación y presenta los avisos resultantes."""
        with self.bd.sesion() as s:
            cfg = RepoConfiguracion(s)
            sonido_on = cfg.obtener_bool("aviso.sonido", True)
            estilo = cfg.obtener("aviso.estilo", "ventana") or "ventana"

            srv = self._vincular_servicio(s)
            avisos = srv.evaluar()
            self._guardar_estado(srv)

        for aviso in avisos:
            reproducir_tono_aviso(
                habilitado=sonido_on,
                es_repeticion=aviso.es_repeticion_sin_respuesta,
            )
            if estilo == "notificacion" and self.bandeja and self.bandeja.isSystemTrayAvailable():
                self.bandeja.showMessage(aviso.titulo, aviso.mensaje)
                if aviso.tipo == TipoAviso.CONTINUIDAD:
                    self._mostrar_dialogo_continuidad(aviso)
            else:
                self._mostrar_dialogo_continuidad(aviso)

        return avisos

    def _mostrar_dialogo_continuidad(self, aviso: AvisoRecordatorio) -> None:
        if self._dialogo_abierto is not None and self._dialogo_abierto.isVisible():
            self._dialogo_abierto.raise_()
            self._dialogo_abierto.activateWindow()
            return

        dlg = DialogoRecordatorio(aviso, self.ventana)
        self._dialogo_abierto = dlg
        dlg.finished.connect(lambda _res, d=dlg, a=aviso: self._al_cerrar_dialogo(d, a))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _al_cerrar_dialogo(self, dlg: DialogoRecordatorio, aviso: AvisoRecordatorio) -> None:
        self._dialogo_abierto = None
        if aviso.tipo != TipoAviso.CONTINUIDAD or aviso.actividad_id is None:
            return
        if dlg.respuesta_elegida is None:
            return

        with self.bd.sesion() as s:
            act = s.get(Actividad, aviso.actividad_id)
            if act is None:
                return
            srv = self._vincular_servicio(s)
            srv.responder_continuidad(
                act,
                dlg.respuesta_elegida,
                motivo_pausa=dlg.motivo_ingresado or None,
                tipo_pausa=dlg.tipo_pausa_seleccionado,
                ajuste_minutos_menos=dlg.ajuste_minutos,
                motivo_ajuste=dlg.motivo_ingresado or None,
            )
            self._guardar_estado(srv)
