"""Utilidades para nombres numerados de piezas y revisiones (RF-02, RF-03b)."""

from __future__ import annotations

import re

_PATRON_SUFIJO_NUMERO = re.compile(r"^(?P<base>.*?)(?:\s+(?P<num>\d+))?$")


def separar_base_y_numero(nombre: str) -> tuple[str, int | None]:
    """Separa un nombre como ``'Flyer 3'`` en ``('Flyer', 3)`` o ``('Flyer', None)``."""
    limpio = nombre.strip()
    coincidencia = _PATRON_SUFIJO_NUMERO.match(limpio)
    if not coincidencia:
        return limpio, None
    base = coincidencia.group("base").strip()
    num_txt = coincidencia.group("num")
    if num_txt is not None and base:
        return base, int(num_txt)
    return limpio, None


def siguiente_nombre_pieza(nombre_actual: str, nombres_existentes: list[str]) -> str:
    """Calcula el nombre de la siguiente pieza (ej. ``'Flyer 1'`` → ``'Flyer 2'``).

    Si ``nombre_actual`` no tenía número (ej. ``'Flyer'``) y aún no existe ``'Flyer 2'``,
    devuelve ``'Flyer 2'`` considerando que la pieza actual fue la 1.
    Respeta el mayor número ya usado en la jornada para no repetir nombres.
    """
    base, num_actual = separar_base_y_numero(nombre_actual)
    max_num = num_actual or 1

    for existente in nombres_existentes:
        base_ex, num_ex = separar_base_y_numero(existente)
        if base_ex.lower() == base.lower():
            max_num = max(max_num, num_ex or 1)

    return f"{base} {max_num + 1}"


def nombres_lote_piezas(nombre_base: str, cantidad: int, nombres_existentes: list[str]) -> list[str]:
    """Genera ``cantidad`` nombres numerados consecutivos a partir del último existente."""
    if cantidad < 1:
        raise ValueError("La cantidad de piezas debe ser al menos 1")
    base, num_inicial = separar_base_y_numero(nombre_base)
    if cantidad == 1 and num_inicial is None and not any(
        separar_base_y_numero(x)[0].lower() == base.lower() for x in nombres_existentes
    ):
        return [base]

    max_num = 0
    for existente in nombres_existentes:
        base_ex, num_ex = separar_base_y_numero(existente)
        if base_ex.lower() == base.lower():
            max_num = max(max_num, num_ex or 1)

    inicio = (num_inicial if num_inicial and num_inicial > max_num else max_num + 1)
    return [f"{base} {inicio + i}" for i in range(cantidad)]
