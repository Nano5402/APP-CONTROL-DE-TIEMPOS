# Changelog

## [0.5.0] — 2026-11-09 — Fase 5: interfaz moderna, temas, mini-widget, atajos, autocompletado y PIN

### Agregado
- `ServicioPIN` (`services/seguridad_pin.py`): PIN opcional con PBKDF2-HMAC-SHA256.
- Sistema de temas QSS (`ui/temas.py`): Claro Neutro, Oscuro Grafito y Azul Pizarra.
- `MiniWidgetCronometro` (`ui/mini_widget.py`): mini-ventana flotante siempre encima con cronómetro en vivo y botones Pausar, Finalizar y Siguiente pieza.
- Pantallas operativas completas (`ui/pantallas/`):
  - `PantallaHoy`: cronómetro grande, barra de meta de tiempo efectivo, inicio rápido de no planeadas, tabla del día y botones para Iniciar, Pausar, Finalizar, "Finalizar y empezar siguiente", Aprobar/Rechazar, Revisión, Reasignar y Corregir.
  - `PantallaPlanear`: alta rápida con autocompletado (`QCompleter`), creación de lotes, plantillas propuestas para hoy y "Copiar plan para WhatsApp".
  - `PantallaExtra`: registro de actividades extra con reglas de prioridad y alta rápida de solicitantes.
  - `PantallaCierre`: asistente interactivo de cierre, indicadores de productividad/semáforo y "Copiar resumen para WhatsApp".
  - `PantallaConfiguracion`: perfil, temas, recordatorios, pesos de productividad, plantillas, PIN, copias de seguridad e inicio con Windows.
- Atajos de teclado en `VentanaPrincipal`: `Ctrl+Espacio`, `Ctrl+Shift+F`, `Ctrl+Shift+S` y `Ctrl+M`.
- 77 pruebas automáticas en total.

## [0.4.0] — 2026-11-09 — Fase 4: jornada, productividad, copias de seguridad y WhatsApp

### Agregado
- `ServicioProductividad` (`services/productividad.py`): cálculo de Cumplimiento, Eficiencia, Foco, porcentaje total con pesos configurables (`40/30/30`), reglas especiales (extras de jefe/doctoras, arrastradas con `% de avance`, pausas por causa externa, tiempo fuera de horario, días no laborales sin porcentaje), semáforo (`🟢/🟡/🔴`), meta de tiempo efectivo y datos de referencia por categoría.
- `ServicioBackups` (`services/backups.py`): copias automáticas con rotación, copia a USB/carpeta elegida y restauración manual con verificación de integridad SQLite.
- `ServicioWhatsApp` (`services/whatsapp.py`): generación de texto para "Copiar plan para WhatsApp" y "Copiar resumen para WhatsApp".
- `ServicioCierreJornada` (`services/cierre_jornada.py`): asistente de cierre para resolver actividades abiertas (finalizar, arrastrar con motivo y `% avance`, aplazar), guardar productividad y disparar la copia de seguridad diaria.
- 74 pruebas automáticas en total.

## [0.3.0] — 2026-11-09 — Fase 3: recordatorios, bandeja e inicio con Windows

### Agregado
- Migración `0002`: columna `intervalo_recordatorio_min` en `categorias`.
- `ServicioRecordatorios` (`services/recordatorios.py`): recordatorios de continuidad con jerarquía (`actividad → plantilla → categoría → global`), registro automático de `sin_respuesta` y repetición del aviso manteniendo el cronómetro, recordatorio de finalización (por estimado o promedio histórico), aviso por inactividad en horario laboral, aviso de almuerzo y de salida.
- `ServicioInicioWindows` (`services/inicio_windows.py`): registro en `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` sin permisos de administrador.
- Ventana emergente al frente (`ui/dialogo_recordatorio.py`), sonido configurable (`ui/sonido.py`), bandeja del sistema (`ui/bandeja.py`) y soporte de `--bandeja` en `src/main.py`.
- 68 pruebas automáticas en total.

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
