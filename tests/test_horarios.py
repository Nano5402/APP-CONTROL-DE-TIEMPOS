"""Pruebas del horario laboral por día (sección 6.1 del plan)."""

from __future__ import annotations

from datetime import date, datetime, time

import pytest

from data.repositorios.horarios import RepoHorarios

LUNES = date(2026, 11, 9)
SABADO = date(2026, 11, 14)
DOMINGO = date(2026, 11, 15)


@pytest.fixture
def repo(s):
    return RepoHorarios(s)


def test_duracion_jornada(repo):
    assert repo.duracion_jornada_seg(LUNES) == 7 * 3600 + 45 * 60  # 7 h 45 min
    assert repo.duracion_jornada_seg(SABADO) == 3 * 3600 + 15 * 60  # 3 h 15 min
    assert repo.duracion_jornada_seg(DOMINGO) == 0


def test_dias_laborales(repo):
    assert repo.es_dia_laboral(LUNES)
    assert repo.es_dia_laboral(SABADO)
    assert not repo.es_dia_laboral(DOMINGO)


@pytest.mark.parametrize(
    ("momento", "esperado"),
    [
        (datetime(2026, 11, 9, 7, 29), False),
        (datetime(2026, 11, 9, 7, 30), True),
        (datetime(2026, 11, 9, 12, 0), False),  # inicio del almuerzo
        (datetime(2026, 11, 9, 12, 45), False),  # almuerzo
        (datetime(2026, 11, 9, 13, 30), True),
        (datetime(2026, 11, 9, 16, 44), True),
        (datetime(2026, 11, 9, 16, 45), False),  # hora de salida
        (datetime(2026, 11, 14, 10, 0), True),  # sábado
        (datetime(2026, 11, 14, 12, 15), False),
        (datetime(2026, 11, 15, 10, 0), False),  # domingo
    ],
)
def test_esta_en_horario(repo, momento, esperado):
    assert repo.esta_en_horario(momento) is esperado


def test_reemplazar_dia(repo):
    repo.reemplazar_dia(6, [(time(8, 0), time(10, 0))])  # domingo con horario
    assert repo.duracion_jornada_seg(DOMINGO) == 2 * 3600
    repo.reemplazar_dia(5, [])  # sábado sin horario
    assert not repo.es_dia_laboral(SABADO)


def test_reemplazar_dia_ordena_y_numera_bloques(repo):
    repo.reemplazar_dia(0, [(time(14, 0), time(17, 0)), (time(8, 0), time(12, 0))])
    bloques = repo.bloques_del_dia(0)
    assert [(b.bloque, b.hora_inicio) for b in bloques] == [(1, time(8, 0)), (2, time(14, 0))]


@pytest.mark.parametrize(
    "bloques",
    [
        [(time(10, 0), time(9, 0))],
        [(time(8, 0), time(12, 0)), (time(11, 0), time(14, 0))],
    ],
)
def test_reemplazar_dia_rechaza_bloques_invalidos(repo, bloques):
    with pytest.raises(ValueError):
        repo.reemplazar_dia(0, bloques)
