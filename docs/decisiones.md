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

---

## Fase 3 — Recordatorios, bandeja e inicio con Windows (2026-11-09)

### D-16. Jerarquía del intervalo de continuidad y migración 0002
Se agregó `intervalo_recordatorio_min` a `categorias` (migración `0002`) para
evaluar el intervalo con la prioridad `actividad → plantilla → categoría → global`
(RF-04).

### D-17. Repetición sin respuesta en "¿Sigues con [actividad]?"
Si el diálogo de continuidad queda sin respuesta durante
`recordatorio.repetir_sin_respuesta_min` (2 min por defecto), `ServicioRecordatorios`
inserta automáticamente un registro `sin_respuesta` en `recordatorios_log`,
mantiene el cronómetro corriendo y vuelve a disparar el aviso con un tono más
agudo.

### D-18. Inicio con Windows en `HKCU\...\Run` con `--bandeja`
Para cumplir la regla 6.2 (sin permisos de administrador), `ServicioInicioWindows`
escribe únicamente en `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`
pasando el argumento `--bandeja`, con lo que la app abre minimizada en el system
tray y empieza a evaluar el horario laboral.

---

## Fase 4 — Jornada, productividad, copias de seguridad y WhatsApp (2026-11-09)

### D-19. Ponderación cuando falta un sub-indicador en el día
Si en un día laboral una persona trabaja únicamente con actividades sin estimado
y sin historial previo en su categoría (por lo que `eficiencia_pct` es `None`),
o sin plan previo (`cumplimiento_pct` es `None`), la fórmula normaliza los pesos
sobre los indicadores presentes en lugar de asignar `0 %`, para no castigar
injustamente al colaborador.

### D-20. Copias de seguridad en caliente con `sqlite3.Connection.backup`
En lugar de copiar el archivo `.db` con `shutil.copy` (que en modo WAL podría
omitir páginas del `-wal`), `ServicioBackups` usa la API nativa de respaldo de
SQLite con `contextlib.closing` (para liberar inmediatamente el descriptor de
archivo en Windows) y valida con `PRAGMA integrity_check` antes de restaurar.

---

## Fase 5 — Interfaz moderna, temas, mini-widget, atajos, autocompletado y PIN (2026-11-09)

### D-21. Hash de PIN con `hashlib.pbkdf2_hmac`
El PIN opcional se almacena en `usuarios.pin_hash` como `sal_hex$hash_hex` usando
PBKDF2-HMAC-SHA256 con 120.000 iteraciones (librería estándar, sin dependencias
externas). Si no hay PIN configurado, la app abre directamente; si inicia con
`--bandeja`, tampoco bloquea el arranque en segundo plano.

### D-22. Tres temas predefinidos QSS y mini-widget sincronizado cada segundo
`ui/temas.py` define tres paletas neutras (**Claro Neutro**, **Oscuro Grafito**,
**Azul Pizarra**) aplicables en caliente tanto a `VentanaPrincipal` como a
`MiniWidgetCronometro`. Un `QTimer` de 1 s mantiene sincronizados ambos relojes.

---

## Fase 6 — Historial y estadísticas (2026-11-09)

### D-23. Gráficos vectoriales nativos con `QPainter`
Para cumplir el requisito de inicio en `< 3 s` (RNF-03) y evitar dependencias
pesadas que inflan el ejecutable, el gráfico de tendencia de productividad
(`GraficoTendenciaWidget`) se dibuja de forma vectorial con `QPainter` de Qt,
mostrando guías del semáforo (60 % y 85 %) y soportando vista diaria, semanal y
mensual.

---

## Fase 7 — Reportes PDF (2026-11-09)

### D-24. Motor PDF nativo con `QPdfWriter` + `QTextDocument`
En lugar de usar bibliotecas externas con binarios del sistema (como `wkhtmltopdf`
o `WeasyPrint`, que requieren GTK/Pango e instalación global), `reports/generador_pdf.py`
usa `QPdfWriter` y `QTextDocument` de `PySide6.QtGui`. No requiere permisos de
administrador ni dependencias adicionales y genera PDFs A4 multi-página con tablas,
encabezado de **Gente Util** y semáforo visual.

---

## Fase 8 — Pruebas integrales y herramientas de Beta (2026-11-09)

### D-25. Simulador no destructivo de pesos para la Beta de equipo
Para la sesión de validación de la fórmula 40/30/30 con el Ing. Luis Eduardo
(sección 12 y 17.2 del plan), `ServicioBeta` (`services/beta_herramientas.py`)
recalcula Cumplimiento, Eficiencia y Foco en cualquier rango de fechas con pesos
alternativos sin alterar los valores históricos guardados en `jornadas`, y
exporta una tabla comparativa en Markdown.


