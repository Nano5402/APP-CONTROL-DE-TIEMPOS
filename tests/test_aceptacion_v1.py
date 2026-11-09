"""Pruebas integrales de aceptación (Fase 8 — Sección 14 del plan v0.5).

Recorre de principio a fin los criterios de aceptación de un ciclo laboral
real para Andrés y el equipo de Gente Util.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from data.db import BaseDatos
from data.enums import (
    CanalSolicitud,
    EstadoActividad,
    EstadoAprobacion,
    MotivoRevision,
    Prioridad,
    Recurrencia,
    RespuestaRecordatorio,
    TipoActividad,
    TipoPausa,
    TipoRevision,
    TipoSolicitante,
)
from data.models import Actividad, EdicionLog, RecordatorioLog
from data.repositorios.catalogos import RepoCategorias, RepoPlantillas, RepoSolicitantes
from data.repositorios.jornadas import RepoJornadas
from services.actividades import ServicioActividades
from services.backups import ServicioBackups
from services.beta_herramientas import ServicioBeta
from services.cierre_jornada import (
    AccionCierreActividad,
    DecisionActividadCierre,
    ServicioCierreJornada,
)
from services.cronometro import ServicioCronometro
from services.estadisticas import ServicioEstadisticas
from services.historial import FiltrosHistorial, ServicioHistorial
from services.productividad import ServicioProductividad
from services.recordatorios import ServicioRecordatorios, TipoAviso
from services.reportes_pdf import ServicioReportesPDF
from services.whatsapp import ServicioWhatsApp


def test_ciclo_completo_aceptacion_v1(
    bd: BaseDatos, carpeta_datos: Path, monkeypatch
) -> None:
    """Simula dos jornadas laborales y un domingo no laboral cumpliendo la sección 14."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    bd_pruebas = bd
    lunes = date(2026, 11, 9)
    martes = date(2026, 11, 10)
    domingo = date(2026, 11, 15)

    # 1. Planeación matutina del lunes + plantillas + lote + copiar plan WhatsApp
    with bd_pruebas.sesion() as s:
        jornada_lunes = RepoJornadas(s).obtener_o_crear(lunes, datetime(2026, 11, 9, 7, 30))
        cat_diseno = RepoCategorias(s).obtener_o_crear(
            "Diseño Gráfico", intervalo_recordatorio_min=15
        )
        cat_web = RepoCategorias(s).obtener_o_crear("Actualización Web")
        plantilla = RepoPlantillas(s).crear(
            "Publicar historia matutina",
            categoria_id=cat_diseno.id,
            tiempo_estimado_min=20,
            recurrencia=Recurrencia.DIAS_SEMANA,
            dias_semana=[0, 1, 2, 3, 4],
            intervalo_recordatorio_min=10,
        )
        propuestas = RepoPlantillas(s).propuestas_para_fecha(lunes)
        assert any(p.id == plantilla.id for p in propuestas)

        srv_act = ServicioActividades(s)
        acts_plantilla = srv_act.crear_desde_plantilla(
            plantilla, jornada=jornada_lunes, momento=datetime(2026, 11, 9, 7, 30)
        )
        act_plantilla = acts_plantilla[0]

        lote_flyers = srv_act.crear_lote_piezas(
            "Flyer promoción",
            2,
            jornada=jornada_lunes,
            categoria_id=cat_diseno.id,
            tiempo_estimado_min=30,
            momento=datetime(2026, 11, 9, 7, 30),
        )
        act_web = srv_act.crear_planeada(
            "Banner home web",
            jornada=jornada_lunes,
            categoria_id=cat_web.id,
            tiempo_estimado_min=60,
            momento=datetime(2026, 11, 9, 7, 30),
        )
        act_reasignable = srv_act.crear_planeada(
            "Catálogo impreso",
            jornada=jornada_lunes,
            categoria_id=cat_diseno.id,
            tiempo_estimado_min=45,
            momento=datetime(2026, 11, 9, 7, 30),
        )
        texto_plan = ServicioWhatsApp(s).generar_texto_plan(jornada_lunes)
        assert "Flyer promoción 1" in texto_plan
        assert "Publicar historia matutina" in texto_plan

        id_plantilla_act = act_plantilla.id
        id_flyer_1 = lote_flyers[0].id
        id_flyer_2 = lote_flyers[1].id
        id_web = act_web.id
        id_reasignable = act_reasignable.id
        id_cat_diseno = cat_diseno.id

    # 2. Ejecución con cronómetro, piezas repetidas ("Finalizar y empezar siguiente")
    #    y recordatorios de continuidad ("sin_respuesta" y luego "No" con ajuste)
    with bd_pruebas.sesion() as s:
        cron = ServicioCronometro(s)
        rec = ServicioRecordatorios(s)

        a_plant = s.get(Actividad, id_plantilla_act)
        a_f1 = s.get(Actividad, id_flyer_1)
        a_f2 = s.get(Actividad, id_flyer_2)

        cron.iniciar(a_plant, momento=datetime(2026, 11, 9, 7, 30))
        cron.finalizar(a_plant, momento=datetime(2026, 11, 9, 7, 50))

        cron.iniciar(a_f1, momento=datetime(2026, 11, 9, 7, 50))
        sig_act = cron.finalizar_y_empezar_siguiente(
            a_f1, momento=datetime(2026, 11, 9, 8, 20)
        )
        assert sig_act.id == id_flyer_2

        # En Flyer 2 (categoría con intervalo de 15 min): a las 8:36 salta aviso de continuidad
        avisos_1 = rec.evaluar(momento=datetime(2026, 11, 9, 8, 36))
        assert any(a.tipo == TipoAviso.CONTINUIDAD and a.actividad_id == id_flyer_2 for a in avisos_1)

        # Pasan 3 min sin respuesta -> registra "sin_respuesta", cronómetro sigue y repite aviso
        avisos_2 = rec.evaluar(momento=datetime(2026, 11, 9, 8, 39))
        assert any(a.es_repeticion_sin_respuesta for a in avisos_2)

        # A las 8:55 responde "No" con ajuste de 5 min menos -> finaliza a las 8:50
        rec.responder_continuidad(
            a_f2,
            RespuestaRecordatorio.NO,
            ajuste_minutos_menos=5,
            motivo_ajuste="Había terminado hace 5 min",
            momento=datetime(2026, 11, 9, 8, 55),
        )
        assert a_f2.estado == EstadoActividad.COMPLETADA.value

    # 3. Actividad sin plan ("no planeada"), pausa por causa externa y extras (compañero vs jefe)
    with bd_pruebas.sesion() as s:
        srv_act = ServicioActividades(s)
        cron = ServicioCronometro(s)
        repo_sol = RepoSolicitantes(s)
        jornada_lunes = RepoJornadas(s).obtener_o_crear(lunes)

        no_plan = srv_act.crear_no_planeada(
            "Exportar logos solicitados en pasillo",
            jornada=jornada_lunes,
            categoria_id=id_cat_diseno,
            momento=datetime(2026, 11, 9, 8, 55),
        )
        assert no_plan.tipo == TipoActividad.NO_PLANEADA.value
        cron.iniciar(no_plan, momento=datetime(2026, 11, 9, 8, 55))
        cron.finalizar(no_plan, momento=datetime(2026, 11, 9, 9, 10))

        # Solicitante compañero -> prioridad mínima y bloqueada hasta decisión del ingeniero
        companero = repo_sol.crear("Carlos (Compañero)", TipoSolicitante.COMPANERO)
        extra_comp = srv_act.crear_extra(
            "Ajuste firma correo Carlos",
            companero,
            motivo_urgencia="Cambió teléfono",
            canal_solicitud=CanalSolicitud.WHATSAPP,
            descripcion="Actualizar número en firma PNG",
            jornada=jornada_lunes,
            categoria_id=id_cat_diseno,
            tiempo_estimado_min=15,
            momento=datetime(2026, 11, 9, 9, 10),
        )
        assert extra_comp.prioridad == Prioridad.MINIMA.value
        assert extra_comp.aprobacion_estado == EstadoAprobacion.PENDIENTE.value
        srv_act.registrar_decision_ingeniero(
            extra_comp,
            aprobada=True,
            canal=CanalSolicitud.WHATSAPP,
            momento=datetime(2026, 11, 9, 9, 10),
        )
        cron.iniciar(extra_comp, momento=datetime(2026, 11, 9, 9, 10))
        cron.finalizar(extra_comp, momento=datetime(2026, 11, 9, 9, 25))

        # Inicia Banner home web (9:25) y sufre caída de internet de 9:40 a 10:10 (causa externa)
        a_web = s.get(Actividad, id_web)
        cron.iniciar(a_web, momento=datetime(2026, 11, 9, 9, 25))
        cron.pausar(
            a_web,
            tipo=TipoPausa.EXTERNA,
            motivo="Se cayó el internet de la oficina",
            momento=datetime(2026, 11, 9, 9, 40),
        )
        cron.reanudar(a_web, momento=datetime(2026, 11, 9, 10, 10))

        # A las 10:30 llega extra urgente del Ing. Luis Eduardo -> pausa automática de Banner web
        jefe = next(
            sol for sol in repo_sol.listar_activos() if sol.tipo == TipoSolicitante.JEFE.value
        )
        extra_jefe = srv_act.crear_extra(
            "Presentación urgente gerencia",
            jefe,
            motivo_urgencia="Reunión junta",
            canal_solicitud=CanalSolicitud.PRESENCIAL,
            descripcion="Preparar slides de indicadores",
            jornada=jornada_lunes,
            categoria_id=id_cat_diseno,
            tiempo_estimado_min=45,
            momento=datetime(2026, 11, 9, 10, 30),
        )
        assert extra_jefe.prioridad == Prioridad.MAXIMA.value
        cron.iniciar(extra_jefe, momento=datetime(2026, 11, 9, 10, 30))
        assert a_web.estado == EstadoActividad.PAUSADA.value
        cron.finalizar(extra_jefe, momento=datetime(2026, 11, 9, 11, 15))
        id_extra_jefe = extra_jefe.id

        # Trabaja 30 min en Catálogo impreso y luego se reasigna a otro diseñador
        a_reasig = s.get(Actividad, id_reasignable)
        cron.iniciar(a_reasig, momento=datetime(2026, 11, 9, 11, 15))
        cron.reasignar(
            a_reasig,
            persona="Laura (Diseño)",
            motivo="Se repartió carga del catálogo",
            momento=datetime(2026, 11, 9, 11, 45),
        )
        assert a_reasig.estado == EstadoActividad.REASIGNADA.value

        # Reapertura como Revisión 1 de la presentación del jefe (1:30 pm a 1:50 pm)
        rev_1 = srv_act.crear_revision(
            extra_jefe,
            solicitante=jefe,
            tipo_revision=TipoRevision.MINIMO,
            que_cambiar="Agregar diapositiva de presupuesto",
            motivo=MotivoRevision.INFORMACION_NUEVA,
            jornada=jornada_lunes,
            momento=datetime(2026, 11, 9, 13, 30),
        )
        cron.iniciar(rev_1, momento=datetime(2026, 11, 9, 13, 30))
        cron.finalizar(rev_1, momento=datetime(2026, 11, 9, 13, 50))

        # Corrección manual con motivo obligatorio -> queda en ediciones_log
        a_f1 = s.get(Actividad, id_flyer_1)
        srv_act.corregir_actividad(
            a_f1,
            motivo="Se ajustó estimado acordado en reunión",
            tiempo_estimado_min=35,
            momento=datetime(2026, 11, 9, 14, 0),
        )

    # 4. Cierre de jornada del lunes: Banner web queda al 60 % (arrastrada), backup y PDF
    with bd_pruebas.sesion() as s:
        jornada_lunes = RepoJornadas(s).obtener_o_crear(lunes)
        cierre = ServicioCierreJornada(s)
        res_cierre = cierre.cerrar_jornada(
            jornada_lunes,
            decisiones=[
                DecisionActividadCierre(
                    actividad_id=id_web,
                    accion=AccionCierreActividad.ARRASTRAR,
                    avance_pct=60,
                    motivo="Pendiente fotografías del cliente",
                )
            ],
            momento=datetime(2026, 11, 9, 16, 45),
        )
        assert res_cierre.productividad.productividad_pct is not None
        assert res_cierre.productividad.tiempo_pausas_externas_seg == 30 * 60
        assert res_cierre.copia_seguridad is not None
        assert Path(res_cierre.copia_seguridad.ruta).exists()
        assert "Productividad del día:" in res_cierre.texto_resumen_whatsapp
        assert res_cierre.ruta_pdf is not None and res_cierre.ruta_pdf.exists()

    # 5. Martes: continúa la actividad arrastrada y hace un tramo fuera de horario (5:00 pm a 5:30 pm)
    with bd_pruebas.sesion() as s:
        cron = ServicioCronometro(s)
        a_web = s.get(Actividad, id_web)
        cron.iniciar(a_web, momento=datetime(2026, 11, 10, 8, 0))
        cron.pausar(
            a_web,
            tipo=TipoPausa.OTRO,
            motivo="Espera visto bueno final",
            momento=datetime(2026, 11, 10, 8, 30),
        )
        # Termina desde casa fuera del horario laboral (5:00 pm a 5:30 pm)
        cron.iniciar(a_web, momento=datetime(2026, 11, 10, 17, 0))
        cron.finalizar(a_web, momento=datetime(2026, 11, 10, 17, 30))

        jornada_martes = RepoJornadas(s).obtener_o_crear(martes)
        prod_martes = ServicioProductividad(s).calcular_jornada(jornada_martes)
        assert prod_martes.tiempo_fuera_horario_seg == 30 * 60
        assert prod_martes.tiempo_efectivo_seg == 30 * 60

    # 6. Domingo (día no laboral): jornada sin porcentaje y PDF de día no laboral
    with bd_pruebas.sesion() as s:
        srv_act = ServicioActividades(s)
        cron = ServicioCronometro(s)
        jornada_dom = RepoJornadas(s).obtener_o_crear(domingo, datetime(2026, 11, 15, 10, 0))
        act_dom = srv_act.crear_no_planeada(
            "Soporte evento dominical",
            jornada=jornada_dom,
            categoria_id=id_cat_diseno,
            momento=datetime(2026, 11, 15, 10, 0),
        )
        cron.iniciar(act_dom, momento=datetime(2026, 11, 15, 10, 0))
        cron.finalizar(act_dom, momento=datetime(2026, 11, 15, 11, 0))

        prod_dom = ServicioProductividad(s).calcular_jornada(jornada_dom)
        assert prod_dom.es_laboral is False
        assert prod_dom.productividad_pct is None

        pdf_dom = ServicioReportesPDF(s).generar_pdf_dia_no_laboral(jornada_dom)
        assert pdf_dom.exists() and pdf_dom.stat().st_size > 1000

    # 7. Historial, Estadísticas, Reportes PDF específicos/semanales y Simulador Beta
    with bd_pruebas.sesion() as s:
        hist = ServicioHistorial(s)
        filas = hist.buscar_actividades(FiltrosHistorial(fecha_desde=lunes, fecha_hasta=domingo))
        assert len(filas) >= 7
        detalle_f1 = hist.detalle_actividad(id_flyer_1)
        assert detalle_f1 is not None and len(detalle_f1.ediciones) >= 1

        est = ServicioEstadisticas(s).calcular(lunes, martes)
        assert est.revisiones.total_revisiones == 1
        assert len(est.por_categoria) >= 2

        rep = ServicioReportesPDF(s)
        pdf_esp = rep.generar_pdf_especifico(
            FiltrosHistorial(fecha_desde=lunes, fecha_hasta=martes, categoria_id=id_cat_diseno),
            titulo_filtro="Diseño Gráfico en Beta",
        )
        pdf_sem = rep.generar_pdf_periodo(lunes, martes, etiqueta_periodo="Semana Beta")
        assert pdf_esp.exists() and pdf_sem.exists()

        # Herramienta de validación de fórmula con el ingeniero (Fase 8)
        beta = ServicioBeta(s)
        comp = beta.simular_pesos_formula(
            lunes,
            martes,
            peso_cumplimiento=50.0,
            peso_eficiencia=25.0,
            peso_foco=25.0,
        )
        assert len(comp) == 2
        informe_md = beta.exportar_informe_validacion_beta(lunes, martes)
        assert informe_md.exists()
        assert "Informe de Validación de Fórmula" in informe_md.read_text(encoding="utf-8")

        # Verificar persistencia y copias de seguridad
        copias = ServicioBackups(s).listar_copias()
        assert len(copias) >= 1
        assert s.query(EdicionLog).count() >= 1
        assert s.query(RecordatorioLog).count() >= 2
