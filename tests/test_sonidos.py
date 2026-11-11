"""Pruebas del sistema de sonidos de notificación y su configuración personalizable."""

from __future__ import annotations

import wave

from config import rutas
from data.repositorios.configuracion import RepoConfiguracion
from services.recordatorios import AvisoRecordatorio, ServicioRecordatorios, TipoAviso
from ui.sonido import (
    CODIGO_SILENCIO,
    TONOS_DEFECTO_POR_CLAVE,
    TONOS_INTEGRADOS,
    asegurar_tonos_integrados,
    clave_tono_para_aviso,
    eliminar_sonido_personalizado,
    importar_sonido_personalizado,
    limpiar_registro_sonido,
    listar_catalogo_sonidos,
    listar_sonidos_usuario,
    reproducir_tono_aviso,
    resolver_ruta_sonido,
    ultimo_sonido_emitido,
)


def _crear_wav_minimo(ruta) -> None:
    """Genera un archivo WAV PCM válido mínimo para pruebas de importación."""
    with wave.open(str(ruta), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 400)


def test_tonos_integrados_y_resolucion(carpeta_datos):
    carpeta = asegurar_tonos_integrados()
    assert carpeta.exists()

    codigos = [t.codigo for t in TONOS_INTEGRADOS]
    assert codigos == ["gotita", "acorde", "campana", "pulso", "alerta", "brisa"]

    for codigo in codigos:
        ruta = resolver_ruta_sonido(codigo)
        assert ruta is not None
        assert ruta.exists()
        assert ruta.suffix == ".wav"
        assert ruta.stat().st_size > 1000

    assert resolver_ruta_sonido(CODIGO_SILENCIO) is None

    # Si un archivo personalizado desapareció, cae de vuelta al tono por defecto.
    respaldo = resolver_ruta_sonido("custom:desaparecido.wav")
    assert respaldo is not None
    assert respaldo.name == "gotita.wav"

    catalogo = dict(listar_catalogo_sonidos())
    for codigo in codigos:
        assert codigo in catalogo
    assert CODIGO_SILENCIO in catalogo


def test_importar_y_eliminar_sonido_personalizado(carpeta_datos, tmp_path):
    origen_wav = tmp_path / "mi_alarma_celular.wav"
    _crear_wav_minimo(origen_wav)

    origen_mp3 = tmp_path / "ringtone.mp3"
    origen_mp3.write_bytes(b"ID3dummy-mp3-data")

    codigo_wav = importar_sonido_personalizado(origen_wav)
    codigo_mp3 = importar_sonido_personalizado(origen_mp3)

    assert codigo_wav.startswith("custom:")
    assert codigo_mp3.startswith("custom:")

    ruta_wav = resolver_ruta_sonido(codigo_wav)
    ruta_mp3 = resolver_ruta_sonido(codigo_mp3)
    assert ruta_wav is not None and ruta_wav.exists()
    assert ruta_mp3 is not None and ruta_mp3.exists()
    assert ruta_wav.parent == rutas.carpeta_sonidos_usuario()

    usuario = dict(listar_sonidos_usuario())
    assert codigo_wav in usuario
    assert codigo_mp3 in usuario

    assert eliminar_sonido_personalizado(codigo_wav) is True
    assert not ruta_wav.exists()
    assert eliminar_sonido_personalizado(codigo_wav) is False
    assert eliminar_sonido_personalizado("gotita") is False

    invalido = tmp_path / "notas.txt"
    invalido.write_text("hola", encoding="utf-8")
    try:
        importar_sonido_personalizado(invalido)
        raise AssertionError("Debió rechazar extensión no soportada")
    except ValueError:
        pass


def test_clave_tono_para_aviso():
    assert clave_tono_para_aviso(TipoAviso.CONTINUIDAD, False) == "aviso.tono.continuidad"
    assert clave_tono_para_aviso(TipoAviso.CONTINUIDAD, True) == "aviso.tono.repeticion"
    assert clave_tono_para_aviso(TipoAviso.FINALIZACION, False) == "aviso.tono.alerta"
    assert clave_tono_para_aviso(TipoAviso.SIN_ACTIVIDAD, False) == "aviso.tono.alerta"
    assert clave_tono_para_aviso(TipoAviso.ALMUERZO, False) == "aviso.tono.jornada"
    assert clave_tono_para_aviso(TipoAviso.SALIDA, False) == "aviso.tono.jornada"


def test_reproducir_tono_aviso_telemetria(carpeta_datos, tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    limpiar_registro_sonido()

    reproducir_tono_aviso(habilitado=False, tono="campana", volumen=80)
    assert ultimo_sonido_emitido() is None

    reproducir_tono_aviso(habilitado=True, tono=CODIGO_SILENCIO, volumen=80)
    assert ultimo_sonido_emitido() is None

    reproducir_tono_aviso(habilitado=True, tono="campana", volumen=150)
    reg = ultimo_sonido_emitido()
    assert reg is not None
    assert reg["tono"] == "campana"
    assert reg["volumen"] == 100
    assert reg["ruta"] is not None and reg["ruta"].endswith("campana.wav")

    reproducir_tono_aviso(habilitado=True, es_repeticion=True, tono=None, volumen=-10)
    reg2 = ultimo_sonido_emitido()
    assert reg2 is not None
    assert reg2["tono"] == "alerta"
    assert reg2["volumen"] == 0
    assert reg2["es_repeticion"] is True


def test_coordinador_usa_tono_y_volumen_configurados(bd, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui.bandeja import CoordinadorRecordatoriosUI
    from ui.ventana_principal import VentanaPrincipal

    with bd.sesion() as s:
        repo = RepoConfiguracion(s)
        repo.guardar("aviso.sonido", "true")
        repo.guardar("aviso.volumen", "45")
        repo.guardar("aviso.estilo", "notificacion")
        repo.guardar("aviso.tono.alerta", "pulso")

    _app = QApplication.instance() or QApplication([])
    ventana = VentanaPrincipal(bd)
    limpiar_registro_sonido()

    aviso = AvisoRecordatorio(
        tipo=TipoAviso.FINALIZACION,
        titulo="Tiempo cumplido",
        mensaje="La actividad superó el estimado.",
    )
    monkeypatch.setattr(ServicioRecordatorios, "evaluar", lambda self: [aviso])

    coordinador = CoordinadorRecordatoriosUI(bd, ventana)
    emitidos = coordinador.verificar_ahora()

    assert len(emitidos) == 1
    reg = ultimo_sonido_emitido()
    assert reg is not None
    assert reg["tono"] == "pulso"
    assert reg["volumen"] == 45
    assert reg["ruta"] is not None and reg["ruta"].endswith("pulso.wav")

    ventana.close()


def test_pantalla_configuracion_sonidos_personalizados(bd, tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    from ui.ventana_principal import VentanaPrincipal

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    _app = QApplication.instance() or QApplication([])
    ventana = VentanaPrincipal(bd)
    cfg = ventana.pantalla_config
    cfg.refrescar()

    assert cfg.tabs_config.count() == 5
    assert "Notificaciones" in cfg.tabs_config.tabText(2)
    assert cfg.chk_sonido.isChecked() is True
    assert cfg.slider_volumen.value() == 70
    for clave, defecto in TONOS_DEFECTO_POR_CLAVE.items():
        assert cfg.combos_tonos[clave].currentData() == defecto

    # Importar sonido personalizado y recargar combos como hace la UI
    archivo_usuario = tmp_path / "tono_personal.wav"
    _crear_wav_minimo(archivo_usuario)
    codigo_custom = importar_sonido_personalizado(archivo_usuario)
    cfg._recargar_combos_tonos()

    combo_cont = cfg.combos_tonos["aviso.tono.continuidad"]
    idx_custom = combo_cont.findData(codigo_custom)
    assert idx_custom >= 0
    combo_cont.setCurrentIndex(idx_custom)

    cfg.slider_volumen.setValue(88)
    limpiar_registro_sonido()
    cfg._probar_tono_de_clave("aviso.tono.continuidad")
    reg = ultimo_sonido_emitido()
    assert reg is not None
    assert reg["tono"] == codigo_custom
    assert reg["volumen"] == 88

    # Aplicar mismo tono a todas las notificaciones
    cfg._accion_aplicar_tono_a_todos()
    for combo in cfg.combos_tonos.values():
        assert combo.currentData() == codigo_custom

    idx_ventana = cfg.combo_estilo_aviso.findData("ventana")
    assert idx_ventana >= 0
    cfg.combo_estilo_aviso.setCurrentIndex(idx_ventana)
    cfg.chk_aviso_almuerzo.setChecked(False)

    cfg.accion_guardar_general()

    with bd.sesion() as s:
        repo = RepoConfiguracion(s)
        assert repo.obtener("aviso.volumen") == "88"
        assert repo.obtener("aviso.estilo") == "ventana"
        assert repo.obtener("recordatorio.aviso_almuerzo") == "0"
        assert repo.obtener_bool("recordatorio.aviso_almuerzo") is False
        for clave in TONOS_DEFECTO_POR_CLAVE:
            assert repo.obtener(clave) == codigo_custom

    ventana.close()
