# Changelog

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
