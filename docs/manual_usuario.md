# Manual de Usuario — Control de Tiempos (Gente Util) v1.0

Bienvenido a **Control de Tiempos — Gente Util**, tu herramienta de escritorio **100 % local** para planear el día, medir con cronómetro el tiempo invertido en cada actividad, recibir recordatorios inteligentes, compartir tu plan y resumen por WhatsApp y exportar reportes en PDF.

---

## 1. Instalación y Ejecución (Sin Permisos de Administrador)

Los equipos de la empresa usan cuentas estándar de Windows sin clave de administrador. Por eso la aplicación cuenta con dos modalidades que **no requieren permisos de administrador ni muestran avisos de UAC**:

### Opción A: Instalador por usuario (`.exe`)
1. Ejecuta `Instalador-ControlTiempos-v1.0.0-Usuario.exe`.
2. La aplicación se instalará en tu carpeta personal (`%LOCALAPPDATA%\Programs\ControlTiempos`).
3. Marca la casilla **"Iniciar automáticamente con Windows (minimizada en la bandeja)"** para que arranque sola cada mañana.

### Opción B: Versión Portable (`.zip`)
1. Descomprime `ControlTiempos-Portable-v1.0.0.zip` en cualquier carpeta de tu usuario (por ejemplo, `Documentos\ControlTiemposPortable` o una memoria USB).
2. Haz doble clic en `ControlTiempos.exe` o en `Iniciar_ControlTiempos.bat`.
3. Al existir el archivo `portable.flag`, todos tus datos, copias de seguridad y reportes PDF se guardarán dentro de la subcarpeta `datos\` de esa misma carpeta.

---

## 2. Flujo Diario Paso a Paso

### Paso 1: Al iniciar la mañana (`📋 Planear el día`)
1. Abre la pestaña **📋 Planear el día**.
2. Si tienes **plantillas o actividades recurrentes** para ese día de la semana (por ejemplo, *Flyers de vacantes* o *Historias de redes*), aparecerán sugeridas arriba. Si hoy no hubo demanda de alguna, simplemente no la agregues (así no te afectará el porcentaje).
3. Para agregar una actividad nueva:
   - Escribe el nombre (el **autocompletado** te sugerirá nombres anteriores).
   - Elige o escribe una **Categoría** libre y el **Tiempo estimado (min)**.
   - Si vas a realizar varias piezas iguales (ej. 10 flyers), indica la **Cantidad de piezas (lote)** para crearlas numeradas (`Flyer 1`, `Flyer 2`...) o crea solo una y usa el botón **⏭ Siguiente pieza** mientras trabajas.
4. Haz clic en **📋 Copiar plan para WhatsApp** y pégalo en el grupo o chat con el Ing. Luis Eduardo.

> **¿Y si empiezas a trabajar sin plan previo?**
> En la pestaña **⏱ Hoy** puedes escribir el nombre en *"Inicio rápido (sin plan)"* y pulsar **▶ Empezar ahora**. La actividad quedará marcada como **No planeada** y sumará a tu tiempo efectivo (Foco) y Eficiencia.

---

### Paso 2: Durante el día (`⏱ Hoy` y Mini-ventana flotante)
1. En la tabla de **⏱ Hoy**, selecciona tu actividad y haz clic en **▶ Iniciar / Reanudar** (máximo 2 clics).
2. **Solo puede haber 1 actividad en curso a la vez.**
3. Controles rápidos disponibles:
   - **⏸ Pausar** (`Ctrl+Espacio`): elige el motivo (*Almuerzo*, *Actividad prioritaria*, *Causa externa*, *Necesidad personal* u *Otro*).
     - *Nota importante:* Las pausas por **Causa externa** (ej. corte de luz o caída de internet) se descuentan automáticamente del tiempo exigible de la jornada para no afectar tu Foco.
   - **⏹ Finalizar** (`Ctrl+Shift+F`): detiene el cronómetro y marca la actividad al 100 %.
   - **⏭ Finalizar y empezar siguiente** (`Ctrl+Shift+S`): cierra la pieza actual (`Flyer 1`) e inicia de inmediato la siguiente (`Flyer 2`) con el cronómetro corriendo.
   - **🗗 Mini-widget** (`Ctrl+M`): abre una ventana pequeña siempre visible encima de tus programas de diseño con el reloj en vivo y los botones *Pausar*, *Finalizar* y *Siguiente*.

---

### Paso 3: Recordatorios automáticos
- **«¿Sigues con [actividad]?»**: aparece cada N minutos con ventana al frente y sonido:
  - **✅ Sí, sigo en esto**: reinicia el contador y el cronómetro continúa.
  - **⏹ No, ya terminé**: detiene el cronómetro y finaliza la actividad. Si habías terminado hace unos minutos y olvidaste cerrarla, puedes indicar cuántos minutos descontar ahí mismo.
  - **⏸ Pausar**: abre la pausa con motivo.
  - **Si no estás en el puesto y no respondes**: tras 2 minutos la app registra *"sin respuesta"*, **el cronómetro sigue contando** y vuelve a avisarte.
- **Aviso de tiempo estimado superado**: te notifica cuando superas el estimado de la actividad (o el promedio histórico de esa categoría).
- **Aviso sin actividad en curso**: si estás dentro de tu horario laboral y llevas varios minutos sin cronómetro activo ni pausa de almuerzo, la bandeja del sistema te recuerda iniciar registro.
- **Avisos de almuerzo (12:00 m) y salida (4:45 pm L–V / 12:15 pm Sáb)**.

---

### Paso 4: Actividades Extra y Prioridades (`⚡ Nueva extra`)
Cuando alguien te pida una tarea imprevista durante el día, regístrala en **⚡ Nueva extra**:
1. Selecciona el **Solicitante** (o créalo con el botón `+`):
   - **Ing. Luis Eduardo (Jefe) y Doctoras (Sonia, Yolanda, Liliana)**: tienen **Prioridad Máxima** y **no requieren aprobación**. Al iniciarlas, la actividad que tenías en curso se pausa automáticamente por prioridad. Además, cuentan positivamente en tu **Cumplimiento** del día.
   - **Compañeros y Terceros**: tienen **Prioridad Mínima / Normal** y **quedan bloqueadas (`🔒`)** hasta que consultes al ingeniero por WhatsApp o en persona y registres su decisión con los botones **✔ Aprobar (Ing.)** o **✖ Rechazar (Ing.)** en la pantalla **Hoy**.
2. Indica el **Motivo de la urgencia**, el **Canal** (*WhatsApp*, *Llamada*, *Correo*, *Presencial*), la descripción y, si aplica, la fecha límite.

---

### Paso 5: Revisiones (Reabrir una actividad finalizada) y Reasignaciones
- **🔁 Nueva revisión**: si una actividad ya estaba completada y piden ajustes, selecciónala en **Hoy** y pulsa **🔁 Nueva revisión**.
  - Se crea `Actividad → Revisión 1` con su propio cronómetro sin borrar el tiempo original.
  - Registra quién pidió el cambio, si fue *Mínimo* o *Complicado*, qué se pidió cambiar y el motivo (*Error propio*, *Cambio de criterio* o *Información nueva*).
  - Las revisiones suman a tu tiempo efectivo (Foco) y en el reporte aparece el número de revisiones con sus motivos, sin alertas negativas.
- **↗ Reasignar**: si una actividad pasa a otra persona a mitad de camino, usa **↗ Reasignar**. Queda como *"Reasignada a [persona]"* y el tiempo que ya trabajaste sí te cuenta en el día.
- **✏ Corregir**: si olvidaste iniciar o detener el cronómetro, puedes corregir los datos o tramos desde **Hoy** o **Historial** indicando siempre un **motivo obligatorio** (queda marcado como *Editado* con bitácora de auditoría).

---

### Paso 6: Cierre de Jornada, WhatsApp y Reporte PDF (`🏁 Cierre del día`)
Al llegar la hora de salida:
1. Abre **🏁 Cierre del día**.
2. El **Asistente de cierre** te mostrará las actividades que sigan abiertas para que elijas en cada una:
   - **Finalizar (100 %)**
   - **Arrastrar para continuar mañana** (indicando el `% de avance` y el motivo; no te castigará con 0 % y mañana aparecerá lista para continuarla en la oficina o desde casa).
   - **Aplazar**
3. Haz clic en **🏁 Ejecutar cierre de jornada**. La aplicación:
   - Calcula tu **% de Productividad** (`40 % Cumplimiento + 30 % Eficiencia + 30 % Foco`) y su semáforo (`🟢 Excelente >= 85 %`, `🟡 Aceptable 60–84 %`, `🔴 Por mejorar < 60 %`).
   - Guarda una **copia de seguridad automática** de tu base de datos.
   - Genera y abre automáticamente el **Reporte Diario en PDF**.
4. Haz clic en **💬 Copiar resumen para WhatsApp** y en **📂 Abrir carpeta del PDF** para enviar el cierre al grupo o chat con el jefe.

> **Trabajo fuera de horario o en domingos/festivos:**
> - El tiempo trabajado después de la hora de salida se guarda como **Fuera de horario** (aparece aparte en el resumen y PDF sin distorsionar el porcentaje del día).
> - Si trabajas un domingo o día sin horario, la app crea una **Jornada de día no laboral** (sin porcentaje de productividad) y genera un **PDF de día no laboral** independiente.

---

## 3. Historial, Estadísticas, Reportes PDF y Configuración

- **📅 Historial**: consulta cualquier día, semana, mes o rango de fechas; filtra por categoría, estado, solicitante o tipo; inspecciona tramos, pausas, revisiones y bitácora de ediciones; o corrige registros pasados con motivo.
- **📊 Estadísticas**: visualiza tu gráfico de **tendencia** (por día, semana o mes), tiempo por categoría, estimado vs. real, tiempo por solicitante y conteo de revisiones por motivo.
- **📄 Reportes PDF**: exporta cuando quieras el PDF general de un día, un PDF específico filtrado o el PDF ejecutivo semanal/mensual.
- **⚙ Configuración**:
  - Cambia entre los 4 temas visuales (**Claro Neutro**, **Oscuro Grafito**, **Azul Pizarra** y **Gente Util Corporativo**).
  - Personaliza el logo y color primario para los PDFs.
  - Ajusta intervalos de recordatorios, meta de tiempo efectivo y pesos de la fórmula.
  - Activa o quita el **PIN opcional**.
  - Crea copias de seguridad manuales, copia a una **memoria USB / carpeta externa** o restaura desde un archivo `.db`.

---

## 4. Atajos de Teclado (Opcionales y Personalizables)

Por defecto **todos los atajos de teclado vienen desactivados (vacíos)** para no interferir nunca mientras trabajas en Illustrator, Photoshop, navegador u otros programas.

Si deseas asignarlos a tu gusto:
1. Ve a **⚙ Configuración → 2. Atajos de teclado**.
2. Haz clic sobre el cuadro de la acción que quieras configurar (*Iniciar/Pausar*, *Finalizar*, *Finalizar y empezar siguiente pieza* o *Mostrar/Ocultar Mini-ventana*) y presiona la combinación de teclas que prefieras (por ejemplo `F9` o `Ctrl+Alt+P`).
3. Para quitar un atajo individual pulsa **✖ Quitar**, o usa **🗑 Desactivar / Limpiar todos los atajos** y haz clic en **💾 Guardar configuración general y atajos**.

