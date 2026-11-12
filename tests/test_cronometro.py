"""Pruebas del servicio de cronómetro, pausas, tramos fuera de horario y flujo de piezas."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from data.enums import (
    CanalSolicitud,
    EstadoActividad,
    Lugar,
    MotivoRevision,
    TipoPausa,
    TipoRevision,
    TipoSolicitante,
)
from data.models import Solicitante
from data.repositorios.catalogos import RepoSolicitantes
from services.actividades import ServicioActividades
from services.cronometro import (
    AccionSobreActiva,
    ActividadBloqueadaError,
    ActividadYaEnCursoError,
    ServicioCronometro,
)


def test_iniciar_pausar_reanudar_finalizar(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)

    a = srv_act.crear_planeada("Flyer 1", momento=datetime(2026, 11, 9, 8, 0))
    cron.iniciar(a, momento=datetime(2026, 11, 9, 8, 0))
    assert cron.actividad_en_curso() == a
    assert cron.segundos_trabajados(a, momento_actual=datetime(2026, 11, 9, 8, 15)) == 900

    pausa = cron.pausar(
        a,
        tipo=TipoPausa.PERSONAL,
        motivo="Baño",
        momento=datetime(2026, 11, 9, 8, 20),
    )
    assert a.estado == EstadoActividad.PAUSADA.value
    assert pausa.fin is None
    assert cron.actividad_en_curso() is None
    assert cron.segundos_trabajados(a, momento_actual=datetime(2026, 11, 9, 8, 25)) == 1200

    cron.reanudar(a, momento=datetime(2026, 11, 9, 8, 25))
    assert pausa.fin == datetime(2026, 11, 9, 8, 25)
    assert a.estado == EstadoActividad.EN_CURSO.value

    cron.finalizar(a, descripcion="Flyer listo", momento=datetime(2026, 11, 9, 8, 40))
    assert a.estado == EstadoActividad.COMPLETADA.value
    assert a.avance_pct == 100
    assert cron.segundos_trabajados(a) == 1200 + 900  # 20 min + 15 min = 35 min


def test_solo_una_activa_a_la_vez_y_urgencia_pausa_automaticamente(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)

    a1 = srv_act.crear_planeada("Flyer 1", momento=datetime(2026, 11, 9, 9, 0))
    a2 = srv_act.crear_planeada("Flyer 2", momento=datetime(2026, 11, 9, 9, 0))
    cron.iniciar(a1, momento=datetime(2026, 11, 9, 9, 0))

    # Iniciar otra normal sin indicar acción lanza error para que la UI pregunte
    with pytest.raises(ActividadYaEnCursoError) as exc:
        cron.iniciar(a2, momento=datetime(2026, 11, 9, 9, 10))
    assert exc.value.actividad_activa == a1

    # Si llega una extra de prioridad máxima (Dra. Sonia), detiene a1 limpiamente como pendiente
    dra = s.scalar(select(Solicitante).where(Solicitante.nombre == "Dra. Sonia"))
    urgente = srv_act.crear_extra(
        "Comunicado urgente",
        dra,
        motivo_urgencia="Reunión gerencia",
        canal_solicitud=CanalSolicitud.LLAMADA,
        descripcion="Imagen para enviar ya",
        momento=datetime(2026, 11, 9, 9, 15),
    )
    cron.iniciar(urgente, momento=datetime(2026, 11, 9, 9, 15))
    assert a1.estado == EstadoActividad.PENDIENTE.value
    assert len(a1.pausas) == 0
    assert cron.actividad_en_curso() == urgente


def test_actividad_bloqueada_no_puede_iniciar_hasta_aprobacion(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    comp = RepoSolicitantes(s).crear("Compañera Ana", TipoSolicitante.COMPANERO)

    extra = srv_act.crear_extra(
        "Tarjeta",
        comp,
        motivo_urgencia="Cliente",
        canal_solicitud=CanalSolicitud.WHATSAPP,
        descripcion="Tarjeta digital",
        momento=datetime(2026, 11, 9, 10, 0),
    )
    with pytest.raises(ActividadBloqueadaError):
        cron.iniciar(extra, momento=datetime(2026, 11, 9, 10, 1))

    srv_act.registrar_decision_ingeniero(
        extra,
        aprobada=True,
        canal=CanalSolicitud.PRESENCIAL,
        momento=datetime(2026, 11, 9, 10, 5),
    )
    cron.iniciar(extra, momento=datetime(2026, 11, 9, 10, 5))
    assert cron.actividad_en_curso() == extra


def test_finalizar_y_empezar_siguiente_crea_o_usa_lote(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)

    # Caso 1: se creó solo 1 actividad y llegan más piezas sobre la marcha
    f1 = srv_act.crear_planeada(
        "Flyer 1",
        tiempo_estimado_min=20,
        momento=datetime(2026, 11, 9, 8, 0),
    )
    cron.iniciar(f1, momento=datetime(2026, 11, 9, 8, 0))
    f2 = cron.finalizar_y_empezar_siguiente(f1, momento=datetime(2026, 11, 9, 8, 18))

    assert f1.estado == EstadoActividad.COMPLETADA.value
    assert f2.nombre == "Flyer 2"
    assert f2.estado == EstadoActividad.EN_CURSO.value
    assert f2.tiempo_estimado_min == 20

    # Caso 2: si ya existía "Flyer 3" planeada pendiente, la reutiliza sin duplicarla
    f3_planeada = srv_act.crear_planeada("Flyer 3", momento=datetime(2026, 11, 9, 8, 0))
    f3_activa = cron.finalizar_y_empezar_siguiente(f2, momento=datetime(2026, 11, 9, 8, 35))
    assert f3_activa.id == f3_planeada.id
    assert f3_activa.estado == EstadoActividad.EN_CURSO.value


def test_finalizar_y_empezar_siguiente_pasa_a_la_siguiente_pendiente_sin_numerar(s):
    """Si la actividad no termina en número (ej. 'Depuración'), inicia la siguiente pendiente ('Flyers')
    y nunca inventa 'Depuración 2' ni 'Depuración 3'."""
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)

    depuracion = srv_act.crear_planeada(
        "Depuración código app control de gestión de tiempos",
        momento=datetime(2026, 11, 9, 8, 0),
    )
    flyers = srv_act.crear_planeada(
        "Flyers",
        momento=datetime(2026, 11, 9, 8, 0),
    )

    cron.iniciar(depuracion, momento=datetime(2026, 11, 9, 8, 0))
    cand, nombre_sug = cron.siguiente_actividad_sugerida(depuracion)
    assert cand == flyers
    assert nombre_sug == "Flyers"

    sig = cron.finalizar_y_empezar_siguiente(depuracion, momento=datetime(2026, 11, 9, 9, 0))
    assert depuracion.estado == EstadoActividad.COMPLETADA.value
    assert sig.id == flyers.id
    assert flyers.estado == EstadoActividad.EN_CURSO.value

    # Ahora 'Flyers' es la última y tampoco tiene número al final: no debe inventar 'Flyers 2'
    cand_2, nombre_sug_2 = cron.siguiente_actividad_sugerida(flyers)
    assert cand_2 is None
    assert nombre_sug_2 is None

    cron.finalizar_y_empezar_siguiente(flyers, momento=datetime(2026, 11, 9, 9, 30))
    assert flyers.estado == EstadoActividad.COMPLETADA.value
    assert cron.actividad_en_curso() is None
    assert len(srv_act.listar_visibles_jornada(depuracion.jornada_id)) == 2


def test_tramo_que_cruza_salida_se_divide_en_horario_y_fuera_de_horario(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)

    # Lunes: el bloque 2 termina a las 16:45. Trabaja de 16:30 a 17:00 (15 min dentro + 15 min fuera)
    act = srv_act.crear_planeada("Animación SIAM", momento=datetime(2026, 11, 9, 16, 30))
    cron.iniciar(act, momento=datetime(2026, 11, 9, 16, 30))
    cron.finalizar(act, momento=datetime(2026, 11, 9, 17, 0))

    assert len(act.sesiones) == 2
    assert cron.segundos_trabajados(act, incluir_fuera_horario=True) == 1800
    assert cron.segundos_trabajados(act, incluir_fuera_horario=False) == 900


def test_pausa_fin_de_jornada_arrastra_actividad_y_continua_al_dia_siguiente(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)

    act = srv_act.crear_planeada("Edición de video", momento=datetime(2026, 11, 9, 16, 0))
    cron.iniciar(act, momento=datetime(2026, 11, 9, 16, 0))

    # A las 16:45 no alcanzó a terminar: pausa con 60 % de avance
    with pytest.raises(ValueError):
        cron.pausar(act, tipo=TipoPausa.FIN_JORNADA, momento=datetime(2026, 11, 9, 16, 45))

    cron.pausar(
        act,
        tipo=TipoPausa.FIN_JORNADA,
        motivo="Falta renderizar",
        avance_pct=60,
        momento=datetime(2026, 11, 9, 16, 45),
    )
    assert act.estado == EstadoActividad.ARRASTRADA.value
    assert act.avance_pct == 60

    # Al día siguiente aparece como arrastrada pendiente y se finaliza desde casa
    arrastradas = srv_act.listar_arrastradas_pendientes(datetime(2026, 11, 10, 7, 30).date())
    assert arrastradas == [act]

    cron.reanudar(act, lugar=Lugar.CASA, momento=datetime(2026, 11, 10, 7, 30))
    cron.finalizar(act, momento=datetime(2026, 11, 10, 8, 0))
    assert act.estado == EstadoActividad.COMPLETADA.value
    assert act.avance_pct == 100
    assert cron.segundos_trabajados(act) == 45 * 60 + 30 * 60


def test_revision_suma_en_desglose_sin_alterar_original_y_reasignacion_conserva_tiempo(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    jefe = s.scalar(select(Solicitante).where(Solicitante.nombre == "Ing. Luis Eduardo"))

    orig = srv_act.crear_planeada("Post Instagram", momento=datetime(2026, 11, 9, 9, 0))
    cron.iniciar(orig, momento=datetime(2026, 11, 9, 9, 0))
    cron.finalizar(orig, momento=datetime(2026, 11, 9, 9, 25))  # 25 min

    rev = srv_act.crear_revision(
        orig,
        solicitante=jefe,
        tipo_revision=TipoRevision.MINIMO,
        que_cambiar="Cambiar fecha del evento",
        motivo=MotivoRevision.CAMBIO_CRITERIO,
        momento=datetime(2026, 11, 9, 10, 0),
    )
    cron.iniciar(rev, momento=datetime(2026, 11, 9, 10, 0))
    cron.finalizar(rev, momento=datetime(2026, 11, 9, 10, 10))  # 10 min

    desglose = srv_act.desglose_tiempos(orig)
    assert desglose.segundos_original == 25 * 60
    assert desglose.segundos_revisiones == 10 * 60
    assert desglose.segundos_total == 35 * 60

    # Otra actividad iniciada y luego reasignada a un compañero conserva los 20 min trabajados
    otra = srv_act.crear_planeada("Catálogo PDF", momento=datetime(2026, 11, 9, 11, 0))
    cron.iniciar(otra, momento=datetime(2026, 11, 9, 11, 0))
    cron.reasignar(
        otra,
        persona="Laura Gómez",
        motivo="Se repartió la carga del proyecto",
        momento=datetime(2026, 11, 9, 11, 20),
    )
    assert otra.estado == EstadoActividad.REASIGNADA.value
    assert otra.reasignada_a == "Laura Gómez"
    assert cron.segundos_trabajados(otra) == 20 * 60


def test_corregir_sesion_tiempo_y_cambiar_activa_finalizando(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)

    a1 = srv_act.crear_planeada("Tarea 1", momento=datetime(2026, 11, 9, 8, 0))
    a2 = srv_act.crear_planeada("Tarea 2", momento=datetime(2026, 11, 9, 8, 0))
    cron.iniciar(a1, momento=datetime(2026, 11, 9, 8, 0))
    cron.iniciar(
        a2,
        accion_sobre_activa=AccionSobreActiva.FINALIZAR,
        momento=datetime(2026, 11, 9, 8, 30),
    )
    assert a1.estado == EstadoActividad.COMPLETADA.value
    assert a2.estado == EstadoActividad.EN_CURSO.value

    # Corrige la sesión de a1 porque olvidó detenerla a las 8:20
    sesion = a1.sesiones[0]
    srv_act.corregir_sesion_tiempo(
        sesion,
        motivo="Terminé a las 8:20 pero olvidé dar clic en finalizar",
        nuevo_fin=datetime(2026, 11, 9, 8, 20),
        momento=datetime(2026, 11, 9, 9, 0),
    )
    assert sesion.duracion_seg == 20 * 60
    assert a1.editado is True


def test_flujo_flyers_dinamicos_encadenados(s):
    """Verifica que los flyers se numeren incrementalmente sobre la marcha (Flyer 1 -> Flyer 2 -> Flyer 3...)."""
    from data.repositorios.catalogos import RepoCategorias
    from data.repositorios.jornadas import RepoJornadas

    jornada = RepoJornadas(s).obtener_o_crear(datetime(2026, 11, 10).date())
    cat_flyers = RepoCategorias(s).obtener_o_crear("Flyers", "#003D95")
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)

    # Inicialmente el siguiente sugerido es Flyer 1
    assert cron.siguiente_nombre_flyer_del_dia(jornada.id) == "Flyer 1"

    # Inicia Flyer 1
    f1 = srv_act.crear_planeada("Flyer 1", categoria_id=cat_flyers.id, momento=datetime(2026, 11, 10, 8, 0))
    cron.iniciar(f1, momento=datetime(2026, 11, 10, 8, 0))
    assert cron.es_actividad_flyer(f1) is True
    assert cron.siguiente_nombre_flyer_del_dia(jornada.id) == "Flyer 2"

    # Termina Flyer 1 e inicia Flyer 2 en 1 clic
    f2 = cron.finalizar_e_iniciar_otro_flyer(f1, momento=datetime(2026, 11, 10, 8, 25))
    assert f1.estado == EstadoActividad.COMPLETADA.value
    assert f2.nombre == "Flyer 2"
    assert f2.estado == EstadoActividad.EN_CURSO.value
    assert f2.categoria_id == cat_flyers.id
    assert cron.siguiente_nombre_flyer_del_dia(jornada.id) == "Flyer 3"

    # Termina Flyer 2 e inicia Flyer 3 en 1 clic
    f3 = cron.finalizar_e_iniciar_otro_flyer(f2, momento=datetime(2026, 11, 10, 8, 50))
    assert f2.estado == EstadoActividad.COMPLETADA.value
    assert f3.nombre == "Flyer 3"
    assert f3.estado == EstadoActividad.EN_CURSO.value

    # Termina Flyer 3 normalmente (sin iniciar otro)
    cron.finalizar(f3, momento=datetime(2026, 11, 10, 9, 15))
    assert f3.estado == EstadoActividad.COMPLETADA.value
    assert cron.actividad_en_curso() is None
    # El siguiente nuevo flyer sería el 4
    assert cron.siguiente_nombre_flyer_del_dia(jornada.id) == "Flyer 4"


def test_flujo_flyers_no_consecutivos_con_otras_tareas(s):
    """Verifica el caso donde se hace un flyer, no envían más, se hace otra tarea y más tarde envían el siguiente."""
    from data.repositorios.catalogos import RepoCategorias
    from data.repositorios.jornadas import RepoJornadas

    jornada = RepoJornadas(s).obtener_o_crear(datetime(2026, 11, 10).date())
    cat_flyers = RepoCategorias(s).obtener_o_crear("Flyers", "#003D95")
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)

    # 1. Llega un flyer temprano (Flyer 1)
    f1 = srv_act.crear_planeada("Flyer 1", categoria_id=cat_flyers.id, momento=datetime(2026, 11, 10, 8, 0))
    cron.iniciar(f1, momento=datetime(2026, 11, 10, 8, 0))
    cron.finalizar(f1, momento=datetime(2026, 11, 10, 8, 20))
    assert f1.estado == EstadoActividad.COMPLETADA.value
    assert cron.actividad_en_curso() is None

    # 2. No han enviado más flyers: hace otra actividad distinta
    otra = srv_act.crear_planeada("Diseño de banner web", momento=datetime(2026, 11, 10, 8, 30))
    cron.iniciar(otra, momento=datetime(2026, 11, 10, 8, 30))
    cron.finalizar(otra, momento=datetime(2026, 11, 10, 9, 30))
    assert cron.actividad_en_curso() is None

    # 3. Dos horas después envían el segundo flyer: el sistema calcula automáticamente 'Flyer 2'
    sig_nombre = cron.siguiente_nombre_flyer_del_dia(jornada.id)
    assert sig_nombre == "Flyer 2"

    f2 = srv_act.crear_planeada(sig_nombre, categoria_id=cat_flyers.id, momento=datetime(2026, 11, 10, 11, 0))
    cron.iniciar(f2, momento=datetime(2026, 11, 10, 11, 0))
    assert f2.nombre == "Flyer 2"
    assert cron.actividad_en_curso() == f2

    # 4. Termina Flyer 2 y detiene el reloj
    cron.finalizar(f2, momento=datetime(2026, 11, 10, 11, 25))
    assert cron.actividad_en_curso() is None
    assert cron.siguiente_nombre_flyer_del_dia(jornada.id) == "Flyer 3"

