"""Pruebas del servicio y la pantalla de Planeación Semanal colaborativa."""

from datetime import date

import pytest
from PySide6.QtWidgets import QApplication

from data.models import Categoria, ItemPlaneacion
from services.planeacion import ServicioPlaneacion, inicio_semana
from ui.pantallas.pantalla_planeacion import PantallaPlaneacion, TarjetaPlaneacion, _formatear_est_min


def test_inicio_semana():
    # 2026-11-12 es jueves -> inicio_semana debe ser lunes 2026-11-09
    jueves = date(2026, 11, 12)
    lunes = inicio_semana(jueves)
    assert lunes == date(2026, 11, 9)
    assert lunes.weekday() == 0


def test_formatear_est_min():
    assert _formatear_est_min(None) == ""
    assert _formatear_est_min(0) == ""
    assert _formatear_est_min(45) == "45m"
    assert _formatear_est_min(60) == "1h"
    assert _formatear_est_min(90) == "1h 30m"
    assert _formatear_est_min(125) == "2h 5m"


def test_crear_y_listar_items_planeacion(s):
    srv = ServicioPlaneacion(s)
    lunes = date(2026, 11, 16)

    cat = Categoria(nombre="Social Media", color="#10B981")
    s.add(cat)
    s.flush()

    item1 = srv.crear_item(
        "Flyer 1 lanzamiento",
        responsable="Santiago",
        fecha_semana=lunes,
        dia_semana=0,  # Lunes
        categoria_id=cat.id,
        tiempo_estimado_min=45,
    )
    item2 = srv.crear_item(
        "Video promocional",
        responsable="Andrés",
        fecha_semana=lunes,
        dia_semana=1,  # Martes
    )

    items = srv.listar_items(lunes)
    assert len(items) == 2
    assert items[0].titulo == "Flyer 1 lanzamiento"
    assert items[0].responsable == "Santiago"

    # Filtrar por responsable
    items_sant = srv.listar_items(lunes, responsable="Santiago")
    assert len(items_sant) == 1
    assert items_sant[0].titulo == "Flyer 1 lanzamiento"


def test_alternar_completado_y_mover_dia(s):
    srv = ServicioPlaneacion(s)
    lunes = date(2026, 11, 16)
    item = srv.crear_item("Auditoría de activos", fecha_semana=lunes, dia_semana=0)

    assert item.completado is False
    res = srv.alternar_completado(item.id)
    assert res is True
    assert item.completado is True
    assert item.completado_en is not None

    # Mover al miércoles (2)
    srv.mover_dia(item.id, 2)
    assert item.dia_semana == 2


def test_pasar_a_plan_hoy(s):
    srv = ServicioPlaneacion(s)
    lunes = date(2026, 11, 16)
    item = srv.crear_item(
        "Campaña Black Friday",
        responsable="Equipo Diseño",
        fecha_semana=lunes,
        tiempo_estimado_min=60,
    )

    act = srv.pasar_a_plan_hoy(item.id)
    assert act.nombre == "Campaña Black Friday"
    assert act.tiempo_estimado_min == 60
    assert "Responsable: Equipo Diseño" in act.notas


def test_pantalla_planeacion_ui_completa(bd):
    app = QApplication.instance() or QApplication([])

    with bd.sesion() as s:
        srv = ServicioPlaneacion(s)
        lunes = inicio_semana()
        srv.crear_item(
            "Diseño de pendón",
            responsable="Santiago",
            fecha_semana=lunes,
            dia_semana=0,
            tiempo_estimado_min=90,
        )
        srv.crear_item(
            "Revisión de textos",
            responsable="Catalina",
            fecha_semana=lunes,
            dia_semana=1,
            tiempo_estimado_min=30,
        )

    pantalla = PantallaPlaneacion(bd)
    pantalla.resize(1180, 740)
    pantalla.show()
    app.processEvents()

    assert "tareas" in pantalla.lbl_kpi_total.text()
    assert pantalla.layout_columnas.count() >= 6

    # Prueba de búsqueda en vivo
    pantalla.txt_buscar.setText("pendón")
    app.processEvents()
    assert "1" in pantalla.lbl_kpi_total.text()

    pantalla.txt_buscar.clear()
    app.processEvents()
    assert "2" in pantalla.lbl_kpi_total.text()

    # Prueba de inclusión de sábado
    pantalla.chk_sabado.setChecked(True)
    app.processEvents()
    assert pantalla.layout_columnas.count() == 7

    # Prueba de navegación de semana
    sem_actual = pantalla.fecha_lunes_actual
    pantalla._semana_siguiente()
    assert pantalla.fecha_lunes_actual > sem_actual
    pantalla._ir_esta_semana()
    assert pantalla.fecha_lunes_actual == sem_actual

    pantalla.close()
