"""Configuración del inicio automático con Windows en el espacio del usuario (RF-09, RNF-11).

Regla 6.2 del plan: nunca requiere permisos de administrador (UAC). Se usa la
clave del registro del usuario actual:

    HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run

Cuando está activo, Windows lanza la app con el argumento ``--bandeja`` para que
inicie minimizada en la bandeja del sistema.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Protocol

from config import rutas

RUTA_REGISTRO_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOMBRE_VALOR_RUN = rutas.NOMBRE_APP


class BackendAutostart(Protocol):
    """Abstracción para poder probar sin tocar el registro real de Windows."""

    def leer(self) -> str | None: ...
    def escribir(self, comando: str) -> None: ...
    def eliminar(self) -> None: ...


class BackendWinreg:
    """Implementación real sobre ``HKCU\\...\\Run`` en Windows."""

    def leer(self) -> str | None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUTA_REGISTRO_RUN, 0, winreg.KEY_READ
            ) as clave:
                valor, _ = winreg.QueryValueEx(clave, NOMBRE_VALOR_RUN)
                return str(valor)
        except FileNotFoundError:
            return None

    def escribir(self, comando: str) -> None:
        import winreg

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RUTA_REGISTRO_RUN, 0, winreg.KEY_SET_VALUE
        ) as clave:
            winreg.SetValueEx(clave, NOMBRE_VALOR_RUN, 0, winreg.REG_SZ, comando)

    def eliminar(self) -> None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUTA_REGISTRO_RUN, 0, winreg.KEY_SET_VALUE
            ) as clave:
                winreg.DeleteValue(clave, NOMBRE_VALOR_RUN)
        except FileNotFoundError:
            pass


def construir_comando_autostart(
    *,
    ejecutable: Path | None = None,
    script_main: Path | None = None,
    congelado: bool | None = None,
) -> str:
    """Construye el comando que Windows ejecutará al iniciar sesión.

    - Si la app está empaquetada con PyInstaller (``sys.frozen``), invoca al
      ``.exe`` directamente con ``--bandeja``.
    - En desarrollo, invoca ``pythonw.exe`` (o ``python.exe``) con ``src/main.py --bandeja``.
    """
    es_congelado = getattr(sys, "frozen", False) if congelado is None else congelado
    exe = ejecutable or Path(sys.executable)

    if es_congelado:
        return f'"{exe}" --bandeja'

    pythonw = exe.with_name("pythonw.exe")
    interprete = pythonw if pythonw.exists() else exe
    main_py = script_main or (Path(__file__).resolve().parents[1] / "main.py")
    return f'"{interprete}" "{main_py}" --bandeja'


class ServicioInicioWindows:
    """Activa, desactiva o consulta el inicio automático con Windows."""

    def __init__(self, backend: BackendAutostart | None = None) -> None:
        self.backend: BackendAutostart = backend or BackendWinreg()

    def esta_activo(self) -> bool:
        valor = self.backend.leer()
        return bool(valor and valor.strip())

    def comando_registrado(self) -> str | None:
        return self.backend.leer()

    def activar(self, comando: str | None = None) -> str:
        cmd = comando or construir_comando_autostart()
        self.backend.escribir(cmd)
        return cmd

    def desactivar(self) -> None:
        self.backend.eliminar()

    def sincronizar(self, habilitar: bool, comando: str | None = None) -> bool:
        """Sincroniza el registro con el booleano indicado y devuelve el estado final."""
        if habilitar:
            self.activar(comando)
            return True
        self.desactivar()
        return False


def crear_acceso_directo_lnk(ruta_lnk: Path) -> Path:
    """Crea un acceso directo ``.lnk`` de Windows con el logo corporativo ``icono_app.ico``."""
    es_congelado = getattr(sys, "frozen", False)
    exe = Path(sys.executable).resolve()
    if es_congelado:
        target = str(exe)
        argumentos = ""
        workdir = str(exe.parent)
    else:
        pythonw = exe.with_name("pythonw.exe")
        target = str(pythonw if pythonw.exists() else exe)
        main_py = Path(__file__).resolve().parents[1] / "main.py"
        argumentos = f'"{main_py}"'
        workdir = str(main_py.parents[1])

    ruta_icono = rutas.carpeta_assets() / "icono_app.ico"
    ruta_lnk.parent.mkdir(parents=True, exist_ok=True)

    script_ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{ruta_lnk}'); "
        f"$s.TargetPath = '{target}'; "
        f"$s.Arguments = '{argumentos}'; "
        f"$s.WorkingDirectory = '{workdir}'; "
        f"$s.IconLocation = '{ruta_icono},0'; "
        "$s.Description = 'Control de Tiempos — Gente Util'; "
        "$s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script_ps],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return ruta_lnk


def crear_accesos_directos_usuario() -> list[Path]:
    """Crea el acceso directo con logo en el Escritorio, Menú Inicio y carpeta del proyecto."""
    nombre_lnk = "Control de Tiempos - Gente Util.lnk"
    destinos: list[Path] = []

    escritorio = Path.home() / "Desktop" / nombre_lnk
    destinos.append(escritorio)

    appdata = os.environ.get("APPDATA")
    if appdata:
        menu_inicio = (
            Path(appdata)
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / nombre_lnk
        )
        destinos.append(menu_inicio)

    raiz_proy = Path(__file__).resolve().parents[2] / nombre_lnk
    destinos.append(raiz_proy)

    creados: list[Path] = []
    for d in destinos:
        try:
            crear_acceso_directo_lnk(d)
            creados.append(d)
        except Exception:
            pass
    return creados
