"""Pruebas de numeración automática de piezas y lotes (RF-02)."""

from __future__ import annotations

import pytest

from services.numeracion import (
    nombres_lote_piezas,
    separar_base_y_numero,
    siguiente_nombre_pieza,
)


def test_separar_base_y_numero():
    assert separar_base_y_numero("Flyer 1") == ("Flyer", 1)
    assert separar_base_y_numero("Post de Instagram 12") == ("Post de Instagram", 12)
    assert separar_base_y_numero("Animación cumpleaños") == ("Animación cumpleaños", None)


def test_siguiente_nombre_pieza_con_y_sin_numero():
    assert siguiente_nombre_pieza("Flyer 1", ["Flyer 1"]) == "Flyer 2"
    assert siguiente_nombre_pieza("Flyer", ["Flyer"]) == "Flyer 2"
    assert siguiente_nombre_pieza("Flyer 2", ["Flyer 1", "Flyer 2", "Flyer 4"]) == "Flyer 5"


def test_nombres_lote_piezas():
    assert nombres_lote_piezas("Flyer", 1, []) == ["Flyer"]
    assert nombres_lote_piezas("Flyer", 3, []) == ["Flyer 1", "Flyer 2", "Flyer 3"]
    assert nombres_lote_piezas("Flyer", 2, ["Flyer 1", "Flyer 2"]) == ["Flyer 3", "Flyer 4"]


def test_nombres_lote_piezas_cantidad_invalida():
    with pytest.raises(ValueError):
        nombres_lote_piezas("Flyer", 0, [])
