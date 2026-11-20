"""Pruebas unitarias para el servicio de inteligencia artificial de Utilín."""

from datetime import date
from unittest.mock import patch

from data.enums import EstadoActividad
from data.models import Actividad
from services.ia_utilin import ServicioUtilinIA, calcular_aritmetica_segura


def test_ia_utilin_verificaciones(bd):
    srv = ServicioUtilinIA(bd)
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


def test_ia_utilin_navegacion_pantallas(bd):
    pantalla_solicitada = None

    def on_navegar(pantalla: str) -> bool:
        nonlocal pantalla_solicitada
        pantalla_solicitada = pantalla
        return True

    srv = ServicioUtilinIA(bd, callback_navegar=on_navegar)

    res_rep = srv.consultar("Abre los reportes")
    assert res_rep.accion_ejecutada == "ABRIR_PANTALLA"
    assert res_rep.datos_accion["pantalla"] == "reportes"
    assert pantalla_solicitada == "reportes"

    res_plan = srv.consultar("ir a planeacion")
    assert res_plan.accion_ejecutada == "ABRIR_PANTALLA"
    assert res_plan.datos_accion["pantalla"] == "planeacion"
    assert pantalla_solicitada == "planeacion"

    res_hist = srv.consultar("ver historial")
    assert res_hist.accion_ejecutada == "ABRIR_PANTALLA"
    assert res_hist.datos_accion["pantalla"] == "historial"
    assert pantalla_solicitada == "historial"


def test_ia_utilin_herramientas_externas(bd):
    srv = ServicioUtilinIA(bd)

    with patch("webbrowser.open") as mock_browser:
        res_wpp = srv.consultar("abre whatsapp")
        assert res_wpp.accion_ejecutada == "ABRIR_HERRAMIENTA"
        assert res_wpp.datos_accion["herramienta"] == "whatsapp"
        mock_browser.assert_called_with("https://web.whatsapp.com")

        res_google = srv.consultar("busca en google convocatoria gente util")
        assert res_google.accion_ejecutada == "ABRIR_HERRAMIENTA"
        assert "convocatoria gente util" in res_google.datos_accion["argumento"]
        mock_browser.assert_called()

    with patch("subprocess.Popen") as mock_popen:
        res_calc = srv.consultar("abre la calculadora")
        assert res_calc.accion_ejecutada == "ABRIR_HERRAMIENTA"
        assert res_calc.datos_accion["herramienta"] == "calculadora"

        res_notes = srv.consultar("abre bloc de notas")
        assert res_notes.accion_ejecutada == "ABRIR_HERRAMIENTA"
        assert res_notes.datos_accion["herramienta"] == "bloc_notas"


def test_ia_utilin_calculo_y_recordatorios(bd):
    srv = ServicioUtilinIA(bd)

    # Cálculo seguro
    res_calc = srv.consultar("cuánto es 1850000 / 30")
    assert res_calc.accion_ejecutada == "CALCULAR"
    assert round(res_calc.datos_accion["resultado"], 2) == 61666.67
    assert "61.666" in res_calc.mensaje or "61,666" in res_calc.mensaje

    # Crear tarea pendiente
    res_tarea = srv.consultar("agrega tarea enviar contratos de Cali")
    assert res_tarea.accion_ejecutada == "CREAR_TAREA"
    with bd.sesion() as s:
        act = s.query(Actividad).filter(Actividad.nombre.ilike("%contratos de cali%")).first()
        assert act is not None
        assert act.estado == EstadoActividad.PENDIENTE.value

    # Crear recordatorio
    res_rec = srv.consultar("recuérdame llamar a la doctora Lina a las 3")
    assert res_rec.accion_ejecutada == "CREAR_RECORDATORIO"
    assert "doctora Lina" in res_rec.mensaje
    assert len(srv.recordatorios_rapidos) == 1


def test_ia_utilin_procesar_salida_llm(bd):
    srv = ServicioUtilinIA(bd)

    # Etiqueta de acción en respuesta de LLM
    salida_tag = "[ACCION:INICIAR_ACTIVIDAD:Revisión de nóminas] ¡Con mucho gusto! Ya inicié el cronómetro."
    res = srv._procesar_salida_llm(salida_tag, "ollama:gemma2:2b")
    assert res.accion_ejecutada == "INICIAR_ACTIVIDAD"
    assert "revisión de nóminas" in res.mensaje.lower()

    # Formato JSON de acción en respuesta de LLM
    salida_json = '{"accion": "ABRIR_PANTALLA", "pantalla": "reportes"}'
    res_json = srv._procesar_salida_llm(salida_json, "ollama:gemma2:2b")
    assert res_json.accion_ejecutada == "ABRIR_PANTALLA"
    assert res_json.datos_accion["pantalla"] == "reportes"


def test_ia_utilin_contingencia_amigable(bd):
    srv = ServicioUtilinIA(bd, endpoint_ollama="http://127.0.0.1:99999")
    res = srv.consultar("Dime algo motivacional")
    assert res.mensaje is not None
    assert "Utilín" in res.mensaje or "Reportes" in res.mensaje
