"""Pruebas unitarias para el servicio de inteligencia artificial de Utilín."""

from datetime import date

from data.enums import EstadoActividad
from data.models import Actividad
from services.ia_utilin import ServicioUtilinIA


def test_ia_utilin_verificaciones(bd):
    srv = ServicioUtilinIA(bd)
    # Verificar que el método no lance excepciones
    ok, msg = srv.verificar_ollama()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)

    ok_g, msg_g = srv.verificar_gemini()
    assert ok_g is False  # Sin API key


def test_ia_utilin_acciones_directas(bd):
    cambio_notificado = False

    def on_cambio():
        nonlocal cambio_notificado
        cambio_notificado = True

    srv = ServicioUtilinIA(bd, callback_notificar_cambio=on_cambio)

    # 1. Iniciar nueva tarea
    res_ini = srv.consultar("Iniciar diseño de flyer vacantes")
    assert res_ini.accion_ejecutada == "INICIAR_ACTIVIDAD"
    assert "flyer vacantes" in res_ini.mensaje.lower()
    assert cambio_notificado is True

    # Comprobar que se creó en la BD
    with bd.sesion() as s:
        act = s.query(Actividad).filter(Actividad.nombre.ilike("%flyer vacantes%")).first()
        assert act is not None
        assert act.estado == EstadoActividad.EN_CURSO.value

    # 2. Consultar hoy
    res_hoy = srv.consultar("¿Qué tengo para hoy?")
    assert res_hoy.accion_ejecutada == "CONSULTAR_HOY"
    assert "flyer vacantes" in res_hoy.mensaje.lower()

    # 3. Pausar tarea
    res_pausa = srv.consultar("Pausa la tarea porfa")
    assert res_pausa.accion_ejecutada == "PAUSAR_ACTIVIDAD"
    assert "pausa" in res_pausa.mensaje.lower()

    # Comprobar estado en BD
    with bd.sesion() as s:
        act = s.query(Actividad).filter(Actividad.nombre.ilike("%flyer vacantes%")).first()
        assert act.estado == EstadoActividad.PAUSADA.value

    # 4. Reanudar / iniciar de nuevo
    srv.consultar("Arranca flyer vacantes")
    with bd.sesion() as s:
        act = s.query(Actividad).filter(Actividad.nombre.ilike("%flyer vacantes%")).first()
        assert act.estado == EstadoActividad.EN_CURSO.value

    # 5. Finalizar tarea
    res_fin = srv.consultar("Finalizar")
    assert res_fin.accion_ejecutada == "FINALIZAR_ACTIVIDAD"
    assert "finalizada" in res_fin.mensaje.lower()

    # 6. Consultar productividad
    res_prod = srv.consultar("¿Cómo voy hoy de productividad?")
    assert res_prod.accion_ejecutada == "CONSULTAR_PRODUCTIVIDAD"
    assert "productividad" in res_prod.mensaje.lower()


def test_ia_utilin_contingencia_amigable(bd):
    srv = ServicioUtilinIA(bd, endpoint_ollama="http://127.0.0.1:99999")
    # Pregunta libre sin coincidencia de comando directo
    res = srv.consultar("Cuéntame un chiste")
    assert res.mensaje is not None
    assert "Utilín" in res.mensaje or "Gemma" in res.mensaje
