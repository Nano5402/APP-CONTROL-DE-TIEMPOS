# Registro de decisiones

Cada decisión importante del desarrollo, con su justificación. Las decisiones
de producto tomadas durante la planeación están en la sección 17 del
[plan](plan-app-control-tiempos.md).

---

## Fase 1 — Base del proyecto (2026-11-09)

### D-01. Python 3.14 y PySide6 6.12
El PC de desarrollo tiene Python 3.14. PySide6 6.12, SQLAlchemy 2.1 y Alembic
1.20 lo soportan. El plan pedía 3.11+, así que se cumple.
**Pendiente:** confirmar en la Fase 9 que PyInstaller empaqueta bien con 3.14;
si no, se usa un Python 3.12/3.13 por usuario solo para empaquetar.

### D-02. Datos en `%LOCALAPPDATA%\ControlTiempos`
Carpeta local del usuario (no Roaming): no se sincroniza con perfiles de red y
no requiere administrador. Copias de seguridad en `Documentos\ControlTiempos\Copias`.
Variable `CONTROL_TIEMPOS_DATA_DIR` para pruebas y versión portable.

### D-03. Migraciones con Alembic
Estándar con SQLAlchemy. La app aplica las migraciones sola al arrancar
(`data.db.migrar`), así una versión nueva actualiza la BD sin intervención.
Se usa modo `render_as_batch` (necesario para `ALTER TABLE` en SQLite) y una
convención de nombres de restricciones. Una prueba (`test_migraciones_coinciden_con_modelos`)
falla si se cambia `models.py` sin crear la migración.

### D-04. Hora local de Colombia sin zona horaria
Colombia no tiene horario de verano; guardar hora local simplifica los cálculos
y la lectura directa de la BD. Toda la app obtiene la hora con `data.tiempo.ahora()`.

### D-05. Ajustes al modelo de datos de la sección 9 (aprobados)
1. `pausas.jornada_id` (nuevo) y `pausas.actividad_id` opcional: el almuerzo u
   otras pausas pueden registrarse sin actividad en curso.
2. Tabla nueva `ediciones_log` (tabla, registro, campo, valor anterior/nuevo,
   motivo obligatorio, momento): trazabilidad de correcciones (RF-07).
3. `actividades.creada_en` y `actividades.finalizada_en`.

### D-06. Estado `eliminada` (borrado lógico)
RF-03 menciona "eliminada" como opción manual, pero el modelo no la tenía. Se
agrega como estado para no borrar físicamente actividades ni su tiempo, en línea
con la trazabilidad pedida. La interfaz las ocultará.

### D-07. Enumeraciones como texto ASCII
Valores guardados en minúsculas, sin tildes (`maxima`, `en_curso`, `companero`),
validados con `CHECK` en SQLite. La interfaz muestra la etiqueta con tildes
(`Enum.etiqueta()`).

### D-08. Confiabilidad de SQLite
`journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON` y transacciones
cortas por operación (RNF-04).

### D-09. Datos iniciales
Horario, usuario y solicitantes se cargan **una sola vez**; luego el usuario
los edita y la app no los recrea. Las claves de configuración faltantes se
agregan siempre sin sobrescribir las existentes.

### D-10. Valores provisionales de configuración
- `meta.tiempo_efectivo_pct = 80` (se define en la beta).
- `recordatorio.repetir_sin_respuesta_min = 2` (cada cuánto se repite el aviso
  "¿Sigues con...?" si no se responde; el plan no lo fija).

### D-11. Una jornada por fecha
`jornadas.fecha` es única (un usuario por PC). Una actividad arrastrada
pertenece a la jornada donde se creó; el tiempo de cada día se calcula desde
sus `sesiones_tiempo`. Una pausa pertenece a la jornada donde empezó.

---

## Fase 2 — Núcleo de tiempos (2026-11-09)

### D-12. Piezas repetidas: numeración automática + lotes opcionales
Al planear se puede crear una sola actividad (y usar "Finalizar y empezar
siguiente" para numerar `Flyer 1`, `Flyer 2`… automáticamente) o crear un lote
de N piezas de golpe (`ServicioActividades.crear_lote_piezas`). Si ya existía la
siguiente pieza planeada como `pendiente`, "Finalizar y empezar siguiente" la
reutiliza sin duplicarla.

### D-13. Respuesta "No" en recordatorio de continuidad
Cuando el usuario responde "No" a "¿Sigues con [actividad]?", el cronómetro se
detiene en ese instante y ofrece ajustar minutos hacia atrás si olvidó cerrarla
antes (`ajuste_minutos_menos` en `ServicioCronometro.finalizar`).

### D-14. Corrección desde "Hoy" e "Historial"
Tanto la pantalla "Hoy" como "Historial" usan `corregir_actividad` y
`corregir_sesion_tiempo`, que exigen motivo obligatorio, marcan `editado=True` y
guardan el detalle campo por campo en `ediciones_log`.

### D-15. Corte automático en límites del horario laboral
Si un tramo continuo de cronómetro cruza el inicio/fin de un bloque laboral (por
ejemplo, de 4:30 pm a 5:00 pm siendo las 4:45 pm la hora de salida), al cerrar
la sesión se divide automáticamente en sesiones dentro de horario
(`fuera_horario=False`) y fuera de horario (`fuera_horario=True`). Así el
cálculo de productividad del día es exacto al segundo.

