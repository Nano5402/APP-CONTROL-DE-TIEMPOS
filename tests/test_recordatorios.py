"""Pruebas del motor de recordatorios, respuestas y avisos de jornada (Fase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from data.enums import EstadoActividad, RespuestaRecordatorio, TipoPausa
from data.models import RecordatorioLog
from data.repositorios.catalogos import RepoCategorias, RepoPlantillas
from services.actividades import ServicioActividades
from services.cronometro import ServicioCronometro
from services.recordatorios import ServicioRecordatorios, TipoAviso


def test_jerarquia_intervalo_recordatorio(s):
    srv_act = ServicioActividades(s)
    srv_rec = ServicioRecordatorios(s)

    cat = RepoCategorias(s).obtener_o_crear("Videos", intervalo_recordatorio_min=25)
    plant = RepoPlantillas(s).crear(
        "Edición reel",
        categoria_id=cat.id,
        intervalo_recordatorio_min=15,
    )

    # 1. Sin categoría ni plantilla → global (10 min)
    a_global = srv_act.crear_planeada("Tarea general", momento=datetime(2026, 11, 9, 8, 0))
    assert srv_rec.intervalo_continuidad_min(a_global) == 10

    # 2. Con categoría → 25 min
    a_cat = srv_act.crear_planeada(
        "Video institucional",
        categoria_id=cat.id,
        momento=datetime(2026, 11, 9, 8, 0),
    )
    assert srv_rec.intervalo_continuidad_min(a_cat) == 25

    # 3. Con plantilla → 15 min (prioridad sobre categoría)
    a_plant = srv_act.crear_desde_plantilla(plant, momento=datetime(2026, 11, 9, 8, 0))[0]
    assert srv_rec.intervalo_continuidad_min(a_plant) == 15

    # 4. Personalizado en la actividad → 5 min (máxima prioridad)
    a_act = srv_act.crear_planeada(
        "Corrección urgente",
        categoria_id=cat.id,
        plantilla_id=plant.id,
        intervalo_recordatorio_min=5,
        momento=datetime(2026, 11, 9, 8, 0),
    )
    assert srv_rec.intervalo_continuidad_min(a_act) == 5


def test_continuidad_sin_respuesta_repite_y_respuestas_si_no_pausar(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    srv_rec = ServicioRecordatorios(s)

    act = srv_act.crear_planeada(
        "Flyer 1",
        intervalo_recordatorio_min=10,
        momento=datetime(2026, 11, 9, 8, 0),
    )
    cron.iniciar(act, momento=datetime(2026, 11, 9, 8, 0))

    # A los 9 min aún no dispara
    assert srv_rec.evaluar(datetime(2026, 11, 9, 8, 9)) == []

    # A los 10 min lanza "¿Sigues con Flyer 1?"
    avisos_10 = srv_rec.evaluar(datetime(2026, 11, 9, 8, 10))
    assert len(avisos_10) == 1
    assert avisos_10[0].tipo == TipoAviso.CONTINUIDAD
    assert avisos_10[0].es_repeticion_sin_respuesta is False

    # Si no responde tras 2 min (8:12), registra "sin_respuesta", cronómetro sigue y repite aviso
    avisos_12 = srv_rec.evaluar(datetime(2026, 11, 9, 8, 12))
    assert len(avisos_12) == 1
    assert avisos_12[0].es_repeticion_sin_respuesta is True
    assert act.estado == EstadoActividad.EN_CURSO.value

    logs = list(s.scalars(select(RecordatorioLog).where(RecordatorioLog.actividad_id == act.id)))
    assert len(logs) == 1
    assert logs[0].respuesta == RespuestaRecordatorio.SIN_RESPUESTA.value

    # Responde "Sí" a las 8:13 → continúa y vuelve a preguntar 10 min después (8:23)
    srv_rec.responder_continuidad(act, RespuestaRecordatorio.SI, momento=datetime(2026, 11, 9, 8, 13))
    assert srv_rec.evaluar(datetime(2026, 11, 9, 8, 20)) == []
    avisos_23 = srv_rec.evaluar(datetime(2026, 11, 9, 8, 23))
    assert len(avisos_23) == 1

    # Responde "Pausar" por ir al baño
    srv_rec.responder_continuidad(
        act,
        RespuestaRecordatorio.PAUSAR,
        motivo_pausa="Baño",
        tipo_pausa=TipoPausa.PERSONAL,
        momento=datetime(2026, 11, 9, 8, 23),
    )
    assert act.estado == EstadoActividad.PAUSADA.value

    # Reanuda a las 8:30 y a las 8:40 responde "No" descontando 2 min
    cron.reanudar(act, momento=datetime(2026, 11, 9, 8, 30))
    srv_rec.responder_continuidad(
        act,
        RespuestaRecordatorio.NO,
        ajuste_minutos_menos=2,
        motivo_ajuste="Terminé hace 2 minutos",
        momento=datetime(2026, 11, 9, 8, 40),
    )
    assert act.estado == EstadoActividad.COMPLETADA.value
    assert act.finalizada_en == datetime(2026, 11, 9, 8, 38)
    assert act.editado is True


def test_recordatorio_finalizacion_solo_con_estimado_explicito_y_persiste_en_reinicio(s):
    srv_act = ServicioActividades(s)
    cron = ServicioCronometro(s)
    srv_rec = ServicioRecordatorios(s)
    cat = RepoCategorias(s).obtener_o_crear("Posts")

    # Actividad previa completada en 58 min en la misma categoría
    previa = srv_act.crear_planeada(
        "Post previo",
        categoria_id=cat.id,
        momento=datetime(2026, 11, 8, 9, 0),
    )
    cron.iniciar(previa, momento=datetime(2026, 11, 8, 9, 0))
    cron.finalizar(previa, momento=datetime(2026, 11, 8, 9, 58))

    # 1. Nueva actividad SIN tiempo estimado en la misma categoría:
    # nunca debe inventar el promedio histórico (58 min) ni avisar finalización
    sin_est = srv_act.crear_planeada(
        "Post sin estimado",
        categoria_id=cat.id,
        intervalo_recordatorio_min=180,
        momento=datetime(2026, 11, 9, 8, 0),
    )
    assert srv_rec.tiempo_referencia_min(sin_est) is None

    cron.iniciar(sin_est, momento=datetime(2026, 11, 9, 8, 0))
    assert srv_rec.evaluar(datetime(2026, 11, 9, 9, 0)) == []  # > 58 min reales sin aviso
    cron.finalizar(sin_est, momento=datetime(2026, 11, 9, 9, 5))

    # 2. Actividad CON tiempo estimado explícito de 20 min: avisa una única vez, incluso tras reiniciar
    con_est = srv_act.crear_planeada(
        "Post con estimado",
        categoria_id=cat.id,
        tiempo_estimado_min=20,
        intervalo_recordatorio_min=180,
        momento=datetime(2026, 11, 9, 9, 10),
    )
    assert srv_rec.tiempo_referencia_min(con_est) == 20

    cron.iniciar(con_est, momento=datetime(2026, 11, 9, 9, 10))
    assert srv_rec.evaluar(datetime(2026, 11, 9, 9, 29)) == []

    avisos = srv_rec.evaluar(datetime(2026, 11, 9, 9, 30))
    assert [a.tipo for a in avisos] == [TipoAviso.FINALIZACION]
    assert "estimado: 20 min" in avisos[0].mensaje
    # No se repite en la misma sesión
    assert srv_rec.evaluar(datetime(2026, 11, 9, 9, 35)) == []

    # Al simular un reinicio de la app (nueva instancia del servicio), NO vuelve a salir
    srv_rec_reinicio = ServicioRecordatorios(s)
    assert srv_rec_reinicio.evaluar(datetime(2026, 11, 9, 9, 40)) == []

    # Si el usuario sube el estimado explícito a 40 min, vuelve a avisar una sola vez al alcanzarlo
    con_est.tiempo_estimado_min = 40
    s.flush()
    avisos_nuevo = srv_rec_reinicio.evaluar(datetime(2026, 11, 9, 9, 50))
    assert [a.tipo for a in avisos_nuevo] == [TipoAviso.FINALIZACION]
    assert "estimado: 40 min" in avisos_nuevo[0].mensaje
    assert ServicioRecordatorios(s).evaluar(datetime(2026, 11, 9, 9, 55)) == []


def test_almuerzo_y_salida_no_repiten_tras_reinicio_mismo_dia(s):
    srv_rec = ServicioRecordatorios(s)
    assert [a.tipo for a in srv_rec.evaluar(datetime(2026, 11, 9, 12, 5))] == [TipoAviso.ALMUERZO]
    assert [a.tipo for a in srv_rec.evaluar(datetime(2026, 11, 9, 16, 50))] == [TipoAviso.SALIDA]

    # Simula reinicio el mismo día
    srv_reinicio = ServicioRecordatorios(s)
    assert srv_reinicio.evaluar(datetime(2026, 11, 9, 12, 10)) == []
    assert srv_reinicio.evaluar(datetime(2026, 11, 9, 16, 55)) == []


def test_avisos_sin_actividad_almuerzo_y_salida(s):
    srv_rec = ServicioRecordatorios(s)
    cron = ServicioCronometro(s)

    # Lunes 7:40 am (10 min después de iniciar el bloque de las 7:30 am sin actividad)
    avisos_manana = srv_rec.evaluar(datetime(2026, 11, 9, 7, 40))
    assert [a.tipo for a in avisos_manana] == [TipoAviso.SIN_ACTIVIDAD]

    # Lunes 12:00 m → aviso de almuerzo (y no avisa "sin actividad" porque está fuera de bloque)
    avisos_almuerzo = srv_rec.evaluar(datetime(2026, 11, 9, 12, 0))
    assert [a.tipo for a in avisos_almuerzo] == [TipoAviso.ALMUERZO]

    # Si deja abierta la pausa de almuerzo hasta la 1:45 pm, no molesta con "sin actividad"
    cron.pausar(None, tipo=TipoPausa.ALMUERZO, momento=datetime(2026, 11, 9, 12, 0))
    assert srv_rec.evaluar(datetime(2026, 11, 9, 13, 45)) == []
    cron.cerrar_pausa_jornada(momento=datetime(2026, 11, 9, 13, 45))

    # Lunes 4:45 pm → aviso de salida
    avisos_salida = srv_rec.evaluar(datetime(2026, 11, 9, 16, 45))
    assert [a.tipo for a in avisos_salida] == [TipoAviso.SALIDA]


def test_dialogo_recordatorio_ui_offscreen( monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from services.recordatorios import AvisoRecordatorio
    from ui.dialogo_recordatorio import DialogoRecordatorio

    _app = QApplication.instance() or QApplication([])
    aviso = AvisoRecordatorio(
        tipo=TipoAviso.CONTINUIDAD,
        titulo="¿Sigues con la actividad?",
        mensaje="¿Sigues trabajando en «Flyer 1»?",
        actividad_id=1,
        actividad_nombre="Flyer 1",
    )
    dlg = DialogoRecordatorio(aviso)
    dlg.spin_ajuste_min.setValue(3)
    dlg.txt_motivo.setText("Olvidé parar")
    dlg.btn_no.click()

    assert dlg.respuesta_elegida == RespuestaRecordatorio.NO
    assert dlg.ajuste_minutos == 3
    assert dlg.motivo_ingresado == "Olvidé parar"


def test_coordinador_no_avisa_sin_estimado_ni_repite_finalizacion_al_reiniciar(bd, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMainWindow

    from data.repositorios.configuracion import RepoConfiguracion
    from data.tiempo import ahora
    from ui.bandeja import CoordinadorRecordatoriosUI

    _app = QApplication.instance() or QApplication([])
    ventana = QMainWindow()

    t_ref = ahora()
    with bd.sesion() as sesion:
        cfg = RepoConfiguracion(sesion)
        cfg.guardar("aviso.sonido", False)
        cfg.guardar("aviso.estilo", "notificacion")
        cfg.guardar("recordatorio.aviso_almuerzo", False)
        cfg.guardar("recordatorio.aviso_salida", False)

        cat = RepoCategorias(sesion).obtener_o_crear("Piezas")
        srv_act = ServicioActividades(sesion)
        cron = ServicioCronometro(sesion)

        prev = srv_act.crear_planeada("Previa 58m", categoria_id=cat.id, momento=t_ref - timedelta(days=1))
        cron.iniciar(prev, momento=t_ref - timedelta(days=1, minutes=58))
        cron.finalizar(prev, momento=t_ref - timedelta(days=1))

        sin_est = srv_act.crear_planeada(
            "Tarea sin estimado",
            categoria_id=cat.id,
            intervalo_recordatorio_min=300,
            momento=t_ref - timedelta(minutes=70),
        )
        cron.iniciar(sin_est, momento=t_ref - timedelta(minutes=70))

    coord1 = CoordinadorRecordatoriosUI(bd, ventana)
    avisos_sin_est = [a for a in coord1.verificar_ahora() if a.tipo == TipoAviso.FINALIZACION]
    assert avisos_sin_est == []

    # Ahora con estimado explícito de 15 min: avisa 1 vez y no repite al reiniciar coordinador
    with bd.sesion() as sesion:
        cron = ServicioCronometro(sesion)
        activa_prev = cron.actividad_en_curso()
        if activa_prev is not None:
            cron.finalizar(activa_prev, momento=t_ref - timedelta(minutes=30))
        cat = RepoCategorias(sesion).obtener_o_crear("Piezas")
        con_est = ServicioActividades(sesion).crear_planeada(
            "Tarea con estimado",
            categoria_id=cat.id,
            tiempo_estimado_min=15,
            intervalo_recordatorio_min=300,
            momento=t_ref - timedelta(minutes=25),
        )
        cron.iniciar(con_est, momento=t_ref - timedelta(minutes=25))

    avisos_1 = [a for a in coord1.verificar_ahora() if a.tipo == TipoAviso.FINALIZACION]
    assert len(avisos_1) == 1
    assert "estimado: 15 min" in avisos_1[0].mensaje

    # Simula cerrar y volver a abrir la aplicación (nuevo CoordinadorRecordatoriosUI sin estado en RAM)
    coord2 = CoordinadorRecordatoriosUI(bd, ventana)
    avisos_2 = [a for a in coord2.verificar_ahora() if a.tipo == TipoAviso.FINALIZACION]
    assert avisos_2 == []
    ventana.close()
