"""Lectura y escritura tipada de la tabla ``configuracion`` (clave-valor)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from data.models import Configuracion

_VERDADEROS = {"1", "true", "si", "sí", "yes"}


class RepoConfiguracion:
    """Acceso a los parámetros de la app con conversión de tipos."""

    def __init__(self, s: Session) -> None:
        self.s = s

    def obtener(self, clave: str, defecto: str | None = None) -> str | None:
        fila = self.s.get(Configuracion, clave)
        return fila.valor if fila else defecto

    def obtener_int(self, clave: str, defecto: int = 0) -> int:
        valor = self.obtener(clave)
        try:
            return int(valor) if valor not in (None, "") else defecto
        except ValueError:
            return defecto

    def obtener_float(self, clave: str, defecto: float = 0.0) -> float:
        valor = self.obtener(clave)
        try:
            return float(valor) if valor not in (None, "") else defecto
        except ValueError:
            return defecto

    def obtener_bool(self, clave: str, defecto: bool = False) -> bool:
        valor = self.obtener(clave)
        if valor in (None, ""):
            return defecto
        return valor.strip().lower() in _VERDADEROS

    def guardar(self, clave: str, valor: str | int | float | bool) -> None:
        """Crea o actualiza un parámetro. Los booleanos se guardan como ``"1"``/``"0"``."""
        texto = ("1" if valor else "0") if isinstance(valor, bool) else str(valor)
        fila = self.s.get(Configuracion, clave)
        if fila:
            fila.valor = texto
        else:
            self.s.add(Configuracion(clave=clave, valor=texto))
