"""Pruebas del inicio automático con Windows sin permisos de administrador (RF-09, RNF-11)."""

from __future__ import annotations

from pathlib import Path

from services.inicio_windows import ServicioInicioWindows, construir_comando_autostart


class BackendMemoria:
    def __init__(self) -> None:
        self.valor: str | None = None

    def leer(self) -> str | None:
        return self.valor

    def escribir(self, comando: str) -> None:
        self.valor = comando

    def eliminar(self) -> None:
        self.valor = None


def test_construir_comando_autostart_desarrollo_y_empaquetado():
    cmd_dev = construir_comando_autostart(
        ejecutable=Path(r"C:\App\.venv\Scripts\python.exe"),
        script_main=Path(r"C:\App\src\main.py"),
        congelado=False,
    )
    assert "--bandeja" in cmd_dev
    assert "main.py" in cmd_dev

    cmd_exe = construir_comando_autostart(
        ejecutable=Path(r"C:\Users\Usuario\AppData\Local\Programs\ControlTiempos\ControlTiempos.exe"),
        congelado=True,
    )
    assert cmd_exe.endswith('ControlTiempos.exe" --bandeja')


def test_activar_desactivar_y_sincronizar_autostart():
    backend = BackendMemoria()
    srv = ServicioInicioWindows(backend)

    assert srv.esta_activo() is False
    cmd = srv.activar('"C:\\ControlTiempos.exe" --bandeja')
    assert srv.esta_activo() is True
    assert srv.comando_registrado() == cmd

    srv.sincronizar(False)
    assert srv.esta_activo() is False

    srv.sincronizar(True, cmd)
    assert srv.esta_activo() is True
