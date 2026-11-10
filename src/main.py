"""Punto de entrada de la app de Control de Tiempos.

Ejecutar (desde la raíz del proyecto, con el entorno virtual):

    .\\.venv\\Scripts\\python.exe src\\main.py              # abre la app
    .\\.venv\\Scripts\\python.exe src\\main.py --verificar  # revisa la BD sin interfaz
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Garantiza que el paquete src esté en sys.path incluso cuando Windows inicia
# la aplicación desde HKCU\...\Run con directorio de trabajo en C:\Windows\System32.
_CARPETA_SRC = str(Path(__file__).resolve().parent)
if _CARPETA_SRC not in sys.path:
    sys.path.insert(0, _CARPETA_SRC)

from config import rutas  # noqa: E402
from data.db import BaseDatos  # noqa: E402


def configurar_logs() -> None:
    """Registra eventos en ``%LOCALAPPDATA%\\ControlTiempos\\logs\\app.log`` (rotativo)."""
    manejador = RotatingFileHandler(
        rutas.carpeta_logs() / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[manejador])


def verificar(bd: BaseDatos) -> None:
    """Imprime un resumen del estado de la base de datos (útil para soporte)."""
    from sqlalchemy import func, inspect, select

    from data.models import Base

    print(f"{rutas.NOMBRE_VISIBLE} v{rutas.VERSION}")
    print(f"Base de datos: {bd.motor.url.database}")
    tablas = inspect(bd.motor).get_table_names()
    with bd.sesion() as s:
        for tabla in Base.metadata.sorted_tables:
            estado = "OK" if tabla.name in tablas else "FALTA"
            total = s.scalar(select(func.count()).select_from(tabla)) if estado == "OK" else "-"
            print(f"  {tabla.name:<20} {estado:<6} {total} registros")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=rutas.NOMBRE_VISIBLE)
    parser.add_argument("--verificar", action="store_true", help="revisa la BD y termina")
    parser.add_argument(
        "--bandeja",
        action="store_true",
        help="indica arranque desde el inicio automático de Windows",
    )
    args = parser.parse_args(argv)

    configurar_logs()
    log = logging.getLogger("main")
    log.info("Iniciando %s v%s", rutas.NOMBRE_VISIBLE, rutas.VERSION)

    bd = BaseDatos.abrir()
    try:
        if args.verificar:
            verificar(bd)
            return 0

        from PySide6.QtWidgets import QApplication, QMessageBox

        from data.repositorios.configuracion import RepoConfiguracion
        from services.inicio_windows import ServicioInicioWindows
        from services.seguridad_pin import ServicioPIN
        from ui.bandeja import CoordinadorRecordatoriosUI, IconoBandeja, crear_icono_app
        from ui.dialogos import DialogoPIN
        from ui.ventana_principal import VentanaPrincipal

        with bd.sesion() as s:
            cfg = RepoConfiguracion(s)
            autostart_activo = cfg.obtener_bool("sistema.inicio_con_windows", True)
            iniciar_oculta = cfg.obtener_bool("sistema.iniciar_minimizada_bandeja", False)
            requiere_pin = ServicioPIN(s).tiene_pin()

        # Asegura que el registro HKCU\...\Run esté siempre sincronizado en el PC real
        if not os.environ.get(rutas.ENV_DATA_DIR):
            try:
                ServicioInicioWindows().sincronizar(autostart_activo)
            except Exception as exc:
                log.warning("No se pudo sincronizar el inicio automático con Windows: %s", exc)

        app = QApplication(sys.argv)
        app.setApplicationName(rutas.NOMBRE_VISIBLE)
        app.setWindowIcon(crear_icono_app())
        app.setQuitOnLastWindowClosed(False)

        ocultar_ventana_al_arrancar = bool(args.bandeja and iniciar_oculta)

        # Si el usuario configuró un PIN opcional y se va a mostrar la ventana, solicitarlo
        if requiere_pin and not ocultar_ventana_al_arrancar:
            dlg_pin = DialogoPIN()
            if dlg_pin.exec() != DialogoPIN.DialogCode.Accepted:
                return 0
            with bd.sesion() as s:
                if not ServicioPIN(s).verificar(dlg_pin.pin):
                    QMessageBox.critical(None, "PIN incorrecto", "El PIN ingresado no es válido.")
                    return 1

        ventana = VentanaPrincipal(bd)
        bandeja = IconoBandeja(ventana)
        bandeja.show()

        coordinador = CoordinadorRecordatoriosUI(bd, ventana, bandeja)
        coordinador.iniciar()
        ventana.coordinador_recordatorios = coordinador

        if not ocultar_ventana_al_arrancar:
            ventana.show()
            ventana.raise_()
            ventana.activateWindow()
        elif bandeja.isSystemTrayAvailable():
            bandeja.showMessage(
                rutas.NOMBRE_VISIBLE,
                "La aplicación está activa en la bandeja del sistema.",
            )

        return app.exec()
    finally:
        bd.cerrar()


if __name__ == "__main__":
    sys.exit(main())
