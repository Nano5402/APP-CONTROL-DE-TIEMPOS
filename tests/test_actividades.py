"""Pruebas de categorías, solicitantes, plantillas y creación de actividades (Fase 2)."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import select

from data.enums import (
    CanalSolicitud,
    EstadoActividad,
    EstadoAprobacion,
    MotivoRevision,
    Prioridad,
    Recurrencia,
    TipoActividad,
    TipoRevision,
    TipoSolicitante,
)
from data.models import EdicionLog, Solicitante
from data.repositorios.catalogos import RepoCategorias, RepoPlantillas, RepoSolicitantes
from services.actividades import ServicioActividades

LUNES_8AM = datetime(2026, 11, 9, 8, 0)
DOMINGO_10AM = datetime(2026, 11, 15, 10, 0)


def test_categorias_libres_sin_duplicar_mayusculas(s):
    repo = RepoCategorias(s)
    c1 = repo.obtener_o_crear("Flyers", "#FF0000")
    c2 = repo.obtener_o_crear("flyers")
    assert c1.id == c2.id
    assert [c.nombre for c in repo.listar_activas()] == ["Flyers"]


def test_solicitantes_reglas_de_prioridad_y_aprobacion(s):
    repo = RepoSolicitantes(s)
    comp = repo.crear("Carlos Pérez", TipoSolicitante.COMPANERO)
    assert comp.prioridad_defecto == Prioridad.MINIMA.value
    assert comp.requiere_aprobacion is True

    tercero = repo.crear("Dr. Pérez", TipoSolicitante.TERCERO, prioridad_defecto=Prioridad.MAXIMA)
    assert tercero.prioridad_defecto == Prioridad.MAXIMA.value
    assert tercero.requiere_aprobacion is True


def test_plantillas_recurrentes_propuestas_por_dia(s):
    repo = RepoPlantillas(s)
    p_diaria = repo.crear("Flyers vacantes", recurrencia=Recurrencia.DIARIA)
    p_lmv = repo.crear(
        "Post Instagram",
        recurrencia=Recurrencia.DIAS_SEMANA,
        dias_semana=[0, 2, 4],
    )
    repo.crear("Reporte mensual", recurrencia=Recurrencia.NINGUNA)

    lunes = date(2026, 11, 9)  # weekday 0
    martes = date(2026, 11, 10)  # weekday 1

    assert {p.id for p in repo.propuestas_para_fecha(lunes)} == {p_diaria.id, p_lmv.id}
    assert {p.id for p in repo.propuestas_para_fecha(martes)} == {p_diaria.id}


def test_jornada_laboral_vs_dia_no_laboral(s):
    srv = ServicioActividades(s)
    a_lunes = srv.crear_planeada("Flyer 1", momento=LUNES_8AM)
    assert a_lunes.jornada.es_laboral is True
    assert a_lunes.jornada.duracion_jornada_seg == 7 * 3600 + 45 * 60

    a_dom = srv.crear_no_planeada("Urgencia domingo", momento=DOMINGO_10AM)
    assert a_dom.jornada.es_laboral is False
    assert a_dom.jornada.duracion_jornada_seg == 0
    assert a_dom.jornada.productividad is None


def test_extra_jefe_vs_companero_y_aprobacion_ingeniero(s):
    srv = ServicioActividades(s)
    repo_sol = RepoSolicitantes(s)

    jefe = s.scalar(select(Solicitante).where(Solicitante.nombre == "Ing. Luis Eduardo"))
    extra_jefe = srv.crear_extra(
        "Video institucional",
        jefe,
        motivo_urgencia="Presentación hoy",
        canal_solicitud=CanalSolicitud.WHATSAPP,
        descripcion="Video corto de 30s",
        momento=LUNES_8AM,
    )
    assert extra_jefe.prioridad == Prioridad.MAXIMA.value
    assert extra_jefe.estado == EstadoActividad.PENDIENTE.value
    assert extra_jefe.aprobacion_estado == EstadoAprobacion.NO_REQUERIDA.value

    comp = repo_sol.crear("Compañero Juan", TipoSolicitante.COMPANERO)
    extra_comp = srv.crear_extra(
        "Apoyo diseño",
        comp,
        motivo_urgencia="Entrega interna",
        canal_solicitud=CanalSolicitud.PRESENCIAL,
        descripcion="Ajustar banner",
        momento=LUNES_8AM,
    )
    assert extra_comp.prioridad == Prioridad.MINIMA.value
    assert extra_comp.estado == EstadoActividad.BLOQUEADA.value
    assert extra_comp.aprobacion_estado == EstadoAprobacion.PENDIENTE.value

    # El ingeniero la aprueba por WhatsApp
    srv.registrar_decision_ingeniero(
        extra_comp,
        aprobada=True,
        canal=CanalSolicitud.WHATSAPP,
        momento=LUNES_8AM,
    )
    assert extra_comp.estado == EstadoActividad.PENDIENTE.value
    assert extra_comp.aprobacion_estado == EstadoAprobacion.APROBADA.value


def test_revisiones_vinculadas_y_desglose(s):
    srv = ServicioActividades(s)
    jefe = s.scalar(select(Solicitante).where(Solicitante.nombre == "Ing. Luis Eduardo"))
    orig = srv.crear_planeada("Flyer 1", momento=LUNES_8AM)

    # No se puede crear revisión si aún no está completada
    with pytest.raises(ValueError):
        srv.crear_revision(
            orig,
            solicitante=jefe,
            tipo_revision=TipoRevision.MINIMO,
            que_cambiar="Teléfono",
            motivo=MotivoRevision.INFORMACION_NUEVA,
        )

    orig.estado = EstadoActividad.COMPLETADA.value
    rev1 = srv.crear_revision(
        orig,
        solicitante=jefe,
        tipo_revision=TipoRevision.MINIMO,
        que_cambiar="Corregir número de contacto",
        motivo=MotivoRevision.INFORMACION_NUEVA,
        momento=LUNES_8AM,
    )
    rev2 = srv.crear_revision(
        orig,
        solicitante=jefe,
        tipo_revision=TipoRevision.COMPLICADO,
        que_cambiar="Cambiar paleta y fotos",
        motivo=MotivoRevision.CAMBIO_CRITERIO,
        momento=LUNES_8AM,
    )
    assert rev1.nombre == "Flyer 1 → Revisión 1"
    assert rev2.nombre == "Flyer 1 → Revisión 2"

    desglose = srv.desglose_tiempos(orig)
    assert desglose.solicitaron_cambios is True
    assert desglose.cantidad_revisiones == 2


def test_corregir_actividad_exige_motivo_y_deja_log(s):
    srv = ServicioActividades(s)
    act = srv.crear_planeada("Flyer 1", tiempo_estimado_min=20, momento=LUNES_8AM)

    with pytest.raises(ValueError):
        srv.corregir_actividad(act, motivo="   ", nombre="Flyer 1 editado")

    srv.corregir_actividad(
        act,
        motivo="Olvidé poner el nombre del cargo",
        nombre="Flyer vacante contador",
        tiempo_estimado_min=30,
        momento=LUNES_8AM,
    )
    assert act.editado is True
    assert act.editado_motivo == "Olvidé poner el nombre del cargo"

    logs = list(
        s.scalars(
            select(EdicionLog).where(
                EdicionLog.tabla == "actividades",
                EdicionLog.registro_id == act.id,
            )
        )
    )
    assert {l.campo for l in logs} == {"nombre", "tiempo_estimado_min"}
