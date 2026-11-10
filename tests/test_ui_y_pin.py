"""Pruebas de PIN opcional, temas QSS, mini-widget y pantallas de la Fase 5."""

from __future__ import annotations

import pytest

from data.enums import EstadoActividad
from services.seguridad_pin import ServicioPIN, generar_hash_pin, verificar_hash_pin
from ui.temas import TEMAS, generar_qss


def test_pin_hash_y_servicio(s):
    with pytest.raises(ValueError):
        generar_hash_pin("12")
    with pytest.raises(ValueError):
        generar_hash_pin("abcd")

    h = generar_hash_pin("2580")
    assert verificar_hash_pin("2580", h) is True
    assert verificar_hash_pin("9999", h) is False

    srv = ServicioPIN(s)
    assert srv.tiene_pin() is False
    assert srv.verificar("cualquiera") is True

    srv.establecer_pin("1470")
    assert srv.tiene_pin() is True
    assert srv.verificar("1470") is True
    assert srv.verificar("0000") is False

    srv.desactivar_pin()
    assert srv.tiene_pin() is False


def test_generar_qss_todos_los_temas():
    for codigo, paleta in TEMAS.items():
        qss = generar_qss(codigo)
        assert paleta.acento in qss
        assert "QMainWindow" in qss


def test_ventana_principal_pantallas_y_mini_widget_offscreen(bd, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui.ventana_principal import VentanaPrincipal

    _app = QApplication.instance() or QApplication([])
    ventana = VentanaPrincipal(bd)
    ventana.show()

    # 1. Planear una actividad desde PantallaPlanear
    ventana.cambiar_pagina(1)
    ventana.pantalla_planear.txt_nombre.setText("Flyer 1")
    ventana.pantalla_planear.txt_categoria.setText("Flyers")
    ventana.pantalla_planear.spin_estimado.setValue(25)
    ventana.pantalla_planear.accion_agregar_planeada()

    # 2. Volver a Hoy, iniciar y usar "Finalizar y empezar siguiente"
    ventana.cambiar_pagina(0)
    assert ventana.pantalla_hoy.tabla.rowCount() == 1
    ventana.pantalla_hoy.tabla.selectRow(0)
    ventana.pantalla_hoy.accion_iniciar_seleccionada()

    nombre_activo, _ = ventana.pantalla_hoy.actualizar_reloj_en_vivo()
    assert nombre_activo == "Flyer 1"

    # Por defecto no hay ningún atajo de teclado activo (evita activaciones accidentales)
    assert len(ventana._atajos_activos) == 0
    assert "desactivados" in ventana.lbl_atajos.text()

    # Mostrar mini-widget y verificar que se sincroniza con la actividad activa
    ventana.mostrar_ocultar_mini_widget(True)
    assert "Flyer 1" in ventana.mini_widget.lbl_actividad.text()
    assert ventana.mini_widget.btn_siguiente.isEnabled() is True

    # Personalizar un atajo y recargar en caliente, luego limpiar todos
    from data.repositorios.configuracion import RepoConfiguracion

    with bd.sesion() as s:
        RepoConfiguracion(s).guardar("atajo.finalizar", "F9")
    ventana.recargar_atajos()
    assert len(ventana._atajos_activos) == 1
    assert "F9" in ventana.lbl_atajos.text()

    ventana.pantalla_config.refrescar()
    ventana.pantalla_config.accion_limpiar_todos_los_atajos()
    with bd.sesion() as s:
        RepoConfiguracion(s).guardar("atajo.finalizar", "")
    ventana.recargar_atajos()
    assert len(ventana._atajos_activos) == 0

    # Finalizar y empezar siguiente pieza desde Hoy
    ventana.pantalla_hoy.accion_finalizar_y_siguiente()
    assert ventana.pantalla_hoy.tabla.rowCount() == 2
    nombre_activo_2, _ = ventana.pantalla_hoy.actualizar_reloj_en_vivo()
    assert nombre_activo_2 == "Flyer 2"

    # Finalizar la segunda pieza
    ventana.pantalla_hoy.accion_finalizar_activa()
    nombre_activo_3, _ = ventana.pantalla_hoy.actualizar_reloj_en_vivo()
    assert nombre_activo_3 is None

    # 3. Cambiar a Cierre de jornada y verificar que las dos están completadas
    ventana.cambiar_pagina(3)
    assert ventana.pantalla_cierre.tabla_abiertas.rowCount() == 0
    assert "Flyer 1" in ventana.pantalla_cierre.txt_resumen_wa.toPlainText()
    assert "Flyer 2" in ventana.pantalla_cierre.txt_resumen_wa.toPlainText()

    # 4. Cambiar de tema en vivo
    ventana.aplicar_tema("oscuro")
    ventana.mostrar_ocultar_mini_widget(False)
    ventana.close()
