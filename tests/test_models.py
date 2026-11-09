"""Pruebas de los modelos: relaciones y restricciones de integridad."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from data.enums import EstadoActividad, TipoActividad, TipoPausa
from data.models import Actividad, EdicionLog, Jornada, Pausa, SesionTiempo
from data.repositorios.configuracion import RepoConfiguracion


@pytest.fixture
def jornada(s):
    j = Jornada(fecha=date(2026, 11, 9), duracion_jornada_seg=27900)
    s.add(j)
    s.flush()
    return j


def _actividad(jornada, **kw) -> Actividad:
    return Actividad(jornada=jornada, nombre=kw.pop("nombre", "Flyer 1"), **kw)


def test_actividad_con_sesiones_y_pausas(s, jornada):
    a = _actividad(jornada)
    a.sesiones.append(
        SesionTiempo(inicio=datetime(2026, 11, 9, 8), fin=datetime(2026, 11, 9, 8, 25), duracion_seg=1500)
    )
    s.add(a)
    s.add(Pausa(jornada=jornada, actividad=a, inicio=datetime(2026, 11, 9, 8, 25), tipo=TipoPausa.PERSONAL))
    s.flush()

    assert a.estado == EstadoActividad.PENDIENTE
    assert a.tipo == TipoActividad.PLANEADA
    assert a.creada_en is not None
    assert sum(x.duracion_seg for x in a.sesiones) == 1500
    assert len(a.pausas) == 1


def test_pausa_sin_actividad_para_almuerzo(s, jornada):
    s.add(Pausa(jornada=jornada, inicio=datetime(2026, 11, 9, 12), tipo=TipoPausa.ALMUERZO))
    s.flush()
    assert len(jornada.pausas) == 1


def test_revision_vinculada_a_original(s, jornada):
    original = _actividad(jornada, estado=EstadoActividad.COMPLETADA)
    s.add(original)
    s.flush()
    revision = _actividad(jornada, nombre="Flyer 1 → Revisión 1", es_revision=True, actividad_padre=original)
    s.add(revision)
    s.flush()
    assert original.revisiones == [revision]


def test_borrar_actividad_borra_sus_sesiones(s, jornada):
    a = _actividad(jornada)
    a.sesiones.append(SesionTiempo(inicio=datetime(2026, 11, 9, 8)))
    s.add(a)
    s.flush()
    s.delete(a)
    s.flush()
    assert s.scalars(select(SesionTiempo)).all() == []


@pytest.mark.parametrize(
    "datos",
    [
        {"estado": "inventado"},
        {"prioridad": "urgentisima"},
        {"avance_pct": 150},
        {"editado": True},  # editado sin motivo
        {"editado": True, "editado_motivo": "   "},
        {"es_revision": True},  # revisión sin actividad original
    ],
)
def test_restricciones_de_actividad(s, jornada, datos):
    s.add(_actividad(jornada, **datos))
    with pytest.raises(IntegrityError):
        s.flush()
    s.rollback()


def test_una_jornada_por_fecha(s, jornada):
    s.add(Jornada(fecha=jornada.fecha))
    with pytest.raises(IntegrityError):
        s.flush()
    s.rollback()


def test_llave_foranea_activa(s):
    s.add(Actividad(jornada_id=9999, nombre="Huérfana"))
    with pytest.raises(IntegrityError):
        s.flush()
    s.rollback()


def test_edicion_log_exige_motivo(s):
    s.add(EdicionLog(tabla="actividades", registro_id=1, campo="nombre", motivo=" "))
    with pytest.raises(IntegrityError):
        s.flush()
    s.rollback()


def test_repo_configuracion(s):
    repo = RepoConfiguracion(s)
    assert repo.obtener_float("productividad.peso_cumplimiento") == pytest.approx(0.40)
    assert repo.obtener_int("recordatorio.continuidad_min") == 10
    assert repo.obtener_bool("sistema.inicio_con_windows") is True
    assert repo.obtener_int("no.existe", 7) == 7

    repo.guardar("sistema.inicio_con_windows", False)
    repo.guardar("nueva.clave", 3.5)
    assert repo.obtener_bool("sistema.inicio_con_windows") is False
    assert repo.obtener_float("nueva.clave") == 3.5
