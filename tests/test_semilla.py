"""Pruebas de los datos iniciales (horario, solicitantes, configuración)."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from data.db import BaseDatos
from data.enums import Prioridad, TipoSolicitante
from data.models import Configuracion, Horario, Solicitante, Usuario
from data.semilla import CONFIGURACION_POR_DEFECTO


def test_horario_inicial(s):
    # 5 días × 2 bloques + sábado × 1 bloque
    assert s.scalar(select(func.count()).select_from(Horario)) == 11
    assert s.scalar(select(func.count()).where(Horario.dia_semana == 6)) == 0


def test_solicitantes_iniciales_con_prioridad_maxima(s):
    solicitantes = {x.nombre: x for x in s.scalars(select(Solicitante))}
    assert set(solicitantes) == {"Ing. Luis Eduardo", "Dra. Sonia", "Dra. Yolanda", "Dra. Liliana"}
    assert solicitantes["Ing. Luis Eduardo"].tipo == TipoSolicitante.JEFE
    for x in solicitantes.values():
        assert x.prioridad_defecto == Prioridad.MAXIMA
        assert x.requiere_aprobacion is False
        assert x.activo is True


def test_usuario_unico_creado(s):
    assert s.scalar(select(func.count()).select_from(Usuario)) == 1


def test_configuracion_por_defecto(s):
    for clave, valor in CONFIGURACION_POR_DEFECTO.items():
        assert s.get(Configuracion, clave).valor == valor


def test_no_sobrescribe_cambios_ni_recrea_borrados(carpeta_datos):
    bd = BaseDatos.abrir()
    with bd.sesion() as s:
        s.get(Configuracion, "meta.tiempo_efectivo_pct").valor = "75"
        s.execute(delete(Solicitante).where(Solicitante.nombre == "Dra. Liliana"))
        s.execute(delete(Configuracion).where(Configuracion.clave == "aviso.volumen"))
    bd.cerrar()

    bd = BaseDatos.abrir()
    with bd.sesion() as s:
        assert s.get(Configuracion, "meta.tiempo_efectivo_pct").valor == "75"
        assert s.scalar(select(Solicitante).where(Solicitante.nombre == "Dra. Liliana")) is None
        # Las claves de configuración que falten sí se restauran con su valor por defecto.
        assert s.get(Configuracion, "aviso.volumen").valor == "70"
    bd.cerrar()
