# Changelog

## [0.2.0] — 2026-11-09 — Fase 2: núcleo de tiempos

### Agregado
- Repositorios de categorías libres, solicitantes (con reglas de prioridad y aprobación) y plantillas recurrentes por día (`data/repositorios/catalogos.py`).
- Repositorio de jornadas con detección automática de días laborales y no laborales (`data/repositorios/jornadas.py`).
- Numeración automática de piezas y generación de lotes (`services/numeracion.py`).
- `ServicioActividades`: actividades planeadas, no planeadas, lotes, desde plantilla, extras con bloqueo/aprobación del ingeniero, revisiones vinculadas (`Revisión 1, 2...`), desglose de tiempos y correcciones manuales con registro en `ediciones_log`.
- `ServicioCronometro`: iniciar (1 activa a la vez, pausa automática ante prioridad máxima), pausar (con % de avance en fin de jornada y soporte de actividades arrastradas), reanudar, finalizar, "finalizar y empezar siguiente", reasignar y corte automático de sesiones al cruzar límites del horario laboral.
- 61 pruebas automáticas en total.

## [0.1.0] — 2026-11-09 — Fase 1: base del proyecto

### Agregado
- Estructura del proyecto, entorno virtual y dependencias (PySide6, SQLAlchemy, Alembic, pytest).
- Modelos de datos completos (sección 9 del plan) con restricciones de integridad.
- Tabla `ediciones_log`, `pausas.jornada_id`, `actividades.creada_en/finalizada_en`, estado `eliminada`.
- Migración inicial de Alembic, aplicada automáticamente al arrancar.
- Datos iniciales: horario laboral, solicitantes (Ing. Luis Eduardo y doctoras) y configuración por defecto.
- Repositorios de configuración y horarios (duración de jornada por día, día laboral, en horario).
- Ventana provisional de verificación y modo `--verificar`.
- 42 pruebas automáticas.
- Documentación: README, documentación técnica, decisiones y changelog.
