# Plan de desarrollo: App local de Control de Tiempos y Productividad

> **Proyecto:** App de escritorio local para registrar, medir y analizar el tiempo de las actividades diarias del equipo de Gente Util.
> **Responsable:** Andrés Santiago Calvete Lesmes
> **Fecha del plan:** 9 de noviembre de 2026
> **Estado:** Planeación cerrada (versión 0.5). Lista para iniciar la Fase 1.
> **Cambios frente a v0.3/v0.4:** WhatsApp se mantiene como canal permanente con el jefe; horario real por día; solicitantes iniciales; revisiones sin alertas; días no laborales; copias de seguridad; inicio con Windows; metas por tiempo (no por cantidad); plantillas y recurrentes; estadísticas; PIN opcional; etapas beta personal → beta de equipo → 1.0.

---

## 1. Contexto y problema

Cada día el equipo tiene una reunión corta en un grupo de WhatsApp con el jefe (Ing. Luis Eduardo), donde cada persona publica las actividades planeadas (ejemplo: flyers de vacantes, imágenes y animaciones de cumpleaños de SIAM, posts de Instagram, investigación y documentación de la app de gestión de tiempos). Al final del día cada uno envía lo realizado.

**Problemas actuales:**
- No hay medición real del tiempo que toma cada actividad.
- Durante el día surgen actividades más importantes que no estaban planeadas y no quedan registradas con claridad.
- No existe un indicador objetivo de productividad ni un historial consultable.
- Los reportes son manuales y por texto.

**Solución propuesta:** una app que funcione 100 % en local en el PC, que mida tiempos con cronómetro por actividad, recuerde al usuario con notificaciones, genere un porcentaje de productividad diario, guarde historial y exporte reportes en PDF.

**Canal con el jefe (decidido en v0.5):** el flujo con WhatsApp **se mantiene**. Por la mañana cada persona envía su plan del día al grupo (con la función de copiar de la app) y al cierre envía el PDF generado. El jefe usa Mac y casi nunca está en la oficina, por lo que **no instala la app**.

---

## 2. Objetivos

### 2.1 Objetivo general
Construir una app de escritorio local, moderna e intuitiva, que permita registrar y medir el tiempo de las actividades laborales diarias y generar reportes de productividad.

### 2.2 Objetivos específicos
1. Planear las actividades del día al iniciar la jornada.
2. Iniciar y finalizar actividades manualmente con un cronómetro.
3. Enviar recordatorios para confirmar que se sigue con la actividad y para finalizarla.
4. Registrar actividades no planeadas ("extras" o urgentes).
5. Calcular un porcentaje de productividad al cierre del día.
6. Guardar un historial completo y consultable.
7. Exportar reportes en PDF (generales y específicos).
8. Documentar completamente el proyecto (código, uso e instalación).

---

## 3. Alcance

### 3.1 Dentro del alcance (v1.0)
- Funcionamiento 100 % local, sin internet y sin servidores externos.
- Solo Windows 10/11 (confirmado: todos los PC del equipo).
- Gestión de actividades del día (planeadas, recurrentes y no planeadas).
- Cronómetro por actividad con pausa, reanudación y finalización.
- Recordatorios de continuidad y de finalización.
- Cierre de jornada con porcentaje de productividad y meta de tiempo efectivo.
- Historial por día, semana y mes.
- Exportación a PDF (resumen general y detalle por actividad).
- Funciones para copiar el plan y el resumen para WhatsApp (permanentes).
- Copias de seguridad (automática, a USB/carpeta y manual).
- Inicio automático con Windows, bandeja del sistema, mini-ventana flotante, atajos de teclado y autocompletado.
- PIN opcional.
- Diseño moderno con varios temas predefinidos y personalizables (claro/oscuro incluidos).
- Interfaz solo en español.
- Documentación completa.

### 3.2 Fuera del alcance (ideas para versiones futuras)
Ver sección 19.

### 3.3 Etapas de entrega
| Etapa | Quién prueba | Contenido |
|---|---|---|
| **Beta personal** | Andrés (uso propio) | Núcleo funcional, paleta neutra, sin logo |
| **Beta de equipo** | Compañeros de Gente Util | Todo lo de la v1.0 salvo logo; aquí se valida la fórmula de productividad con el ingeniero, con datos reales |
| **v1.0** | Todo el equipo | Logo y paleta de Gente Util, documentación e instalador final |

> **Nota:** La app es de uso individual en cada PC (datos independientes). El jefe recibe el plan y el PDF por WhatsApp.

---

## 4. Usuarios y roles

| Rol | Descripción | Necesidades principales |
|---|---|---|
| Colaborador | Cada miembro del equipo que usa la app en su PC (Windows) | Registrar actividades, medir tiempos, ver su productividad |
| Jefe (consulta) | Ing. Luis Eduardo. Usa Mac y no instala la app. Recibe el plan y el PDF por WhatsApp y decide la aprobación de solicitudes de compañeros fuera de la app | Ver el plan de la mañana y el PDF de cierre |
| Solicitantes de actividades extra | Jefe, Dra. Sonia, Dra. Yolanda, Dra. Liliana (principales) y otras personas "importantes" que escriben a un compañero | Su solicitud queda registrada con su prioridad (ver RF-03) |

---

## 5. Requisitos funcionales

### RF-01. Planeación del día
- Al iniciar el día, el usuario crea la lista de actividades planeadas.
- Cada actividad tiene: nombre, categoría (opcional), tiempo estimado (opcional) y prioridad.
- **Categorías libres:** no hay categorías fijas. Cada persona escribe y crea sus propias actividades y categorías (flyers, animaciones, videos, tomar fotos, programar, posts de Instagram, revisar correos, compras, etc.), con **autocompletado** de las usadas antes.
- **Plantillas y recurrentes:** las actividades que se repiten (ej. flyers y animaciones todos los días; creación de posts de Instagram para un compañero) se guardan como plantillas. Al planear el día la app las **propone** y el usuario las acepta, edita o descarta, porque siempre hay variaciones. Si ese día no llega demanda, la tarea simplemente no se crea: no penaliza ni deja registro.
- **Función permanente "Copiar plan para WhatsApp":** genera el listado numerado y editable en el formato que se publica en el grupo.
- **Plan opcional:** se puede trabajar sin plan (ver RF-03).

### RF-02. Control de actividad (cronómetro)
- Botón **Iniciar** sobre una actividad: arranca el cronómetro.
- Solo una actividad activa a la vez.
- Acciones: **Pausar**, **Reanudar**, **Finalizar**.
- Al iniciar otra actividad mientras hay una activa, la app pregunta si se finaliza o se pausa la anterior.
- **Una actividad por pieza:** cuando llegan muchas piezas iguales, cada una es una actividad con su cronómetro ("Flyer 1", "Flyer 2"...), con numeración automática.
- **Botón "Finalizar y empezar siguiente":** cierra la pieza actual y abre la siguiente de la misma categoría, para mantener el máximo de 2 clics aun con muchas piezas.
- **Descripción de la actividad:** cada actividad (sobre todo las extra) lleva una descripción de en qué consistió, para poder evaluar si el tiempo invertido fue justo.

### RF-03. Actividades no planeadas (extras) y prioridades
- Botón rápido **"Actividad extra"**, disponible en cualquier momento, **aunque no exista plan del día**. También se puede iniciar directamente una actividad sin planear; queda marcada como **"no planeada"**.
- La **prioridad la define quien la pide**:

| Solicitante | Prioridad | Regla |
|---|---|---|
| Jefe directo (Ing. Luis Eduardo) | **Máxima** | Se puede iniciar de inmediato |
| Doctoras (Sonia, Yolanda, Liliana) | **Máxima** | Se puede iniciar de inmediato |
| Compañeros | **Mínima** | Queda **bloqueada** hasta que el ingeniero decida |
| Personas "importantes" que escriben a un compañero | Según el caso | Se registra la persona que pidió (ej. "Dr. Pérez"), con aprobación previa del ingeniero marcada |
| Iniciativa propia / planeada | Normal | Flujo habitual |

- **Datos a capturar** al crear una extra: solicitante, motivo de la urgencia, fecha/hora límite, canal de solicitud (WhatsApp, llamada, correo, presencial) y descripción.
- **Aprobación del ingeniero (solicitudes de compañeros o terceros):** la decisión se toma **fuera de la app** (hablándolo con el ingeniero). La actividad se crea *bloqueada* y el usuario marca **"Aprobada"** o **"Rechazada"** según lo que diga el ingeniero, indicando cuándo y por qué canal. Sin aprobación, el botón Iniciar permanece deshabilitado.
- **Solicitantes nuevos:** si la persona importante no existe en la lista, se crea en el momento. La lista de solicitantes es **editable en cada PC**.
- **Interrupción de una actividad en curso:** si llega una de prioridad máxima, la app **pausa completamente** la actividad actual y pregunta; la pausada permanece así hasta terminar la importante.
- Las extras de jefe y doctoras **cuentan como cumplimiento** en la productividad (ver sección 7).
- **Todo es manual:** el usuario elige el estado: *rechazada*, *reasignada*, *aplazada* o *eliminada*.

### RF-03b. Revisiones: reabrir una actividad finalizada
- Cualquier actividad finalizada se puede **reabrir** cuando piden cambios (mínimos o complicados).
- Cada cambio se registra como una **revisión vinculada** ("Flyer 1 → Revisión 1, Revisión 2...") con un **cronómetro nuevo**, sin alterar el tiempo ya registrado de la actividad original.
- Cada revisión pide: **quién pidió el cambio**, **tipo (mínimo o complicado)**, **qué se pidió cambiar** y **motivo** (error propio, cambio de criterio, información nueva).
- La actividad original muestra *"¿Solicitaron cambios? Sí (n)"* y el tiempo total (original + revisiones) con su desglose.
- **Sin alertas por cantidad:** el reporte solo muestra el número de revisiones y sus motivos; la app no juzga, porque muchas veces el origen son errores en la información recibida o cambios sugeridos.

### RF-03c. Actividades reasignadas a otra persona
- Si una actividad ya iniciada es relegada a otra persona, se marca **"Reasignada a [persona]"** con el motivo.
- El **tiempo ya trabajado cuenta para la productividad del día** (ej. 20 min invertidos antes de la reasignación).

### RF-04. Recordatorios y notificaciones
- **Recordatorio de continuidad:** aparece *"¿Sigues con [actividad]?"* según el **tiempo definido por el propio usuario**, ya que cada persona tarda distinto en tareas similares. Valor inicial sugerido: 10 min y repetición cada 10 min.
  - El intervalo se puede **personalizar por usuario, por categoría y por actividad**, y puede basarse en el tiempo estimado.
  - **Estilo del aviso:** ventana emergente al frente + sonido. Si no se responde, el aviso **se repite** y el cronómetro **sigue contando**; queda registrado como "sin respuesta".
  - **Personalizable por persona:** estilo (ventana o notificación de Windows), sonido, volumen y frecuencia de repetición.
  - **Sí:** el cronómetro continúa.
  - **No:** la actividad se marca como **completada**, el cronómetro se detiene y la app ofrece iniciar otra.
  - **Pausar:** para casos como ir al baño, fallas de internet, etc. (con motivo opcional).
- **Recordatorio de finalización:** si la actividad supera el tiempo estimado o el habitual, se recuerda finalizarla.
- **Recordatorio de inicio:** si no hay actividad en curso durante X minutos en horario laboral, avisa *"No tienes ninguna actividad en curso"*.
- **Aviso de almuerzo y de salida** (ver RF-05 y RF-06).
- Todos los intervalos son configurables.

### RF-05. Registro de interrupciones y pausas
- Cada pausa guarda hora de inicio, hora de fin, **tipo** y motivo.
- Tipos de pausa: almuerzo, interrupción por actividad prioritaria, causa externa (internet, generación de imágenes lenta), necesidad personal (baño), fin de jornada, otro.
- El tiempo pausado **no cuenta** como tiempo trabajado, pero queda visible en el reporte.
- **Almuerzo (lunes a viernes, 12:00 m a 1:30 pm):** la app avisa y el usuario pausa; el tiempo de almuerzo no se cuenta.
- **Pausa por fin de jornada:** si una actividad no termina en el horario laboral, se pausa con motivo y el usuario indica el **porcentaje de avance** (ej. 60 %).
  - Ese avance **cuenta para el progreso del día**.
  - La actividad queda **arrastrada (abierta)** y se finaliza al día siguiente en el trabajo o desde casa, registrando hora de reanudación y de finalización.
  - Mientras está pausada **no suma tiempo**.

### RF-05b. Trabajo fuera del horario laboral y días no laborales
- Si se retoma o inicia una actividad fuera del horario configurado (noche, domingo, festivo, desde casa), el tiempo se registra como **"fuera de horario"**.
- Ese tiempo **no entra en el porcentaje de productividad**, pero queda visible en historial y PDF.
- **Días no laborales:** no se precargan festivos ni se marcan vacaciones; si no hay trabajo, no se abre nada. Si alguien trabaja ese día (por ejemplo desde casa, porque le piden algo), inicia una actividad y la app **crea una jornada** de ese día, **sin porcentaje**, con solo el tiempo fuera de horario.
- Para esa jornada se genera un **PDF aparte** y el usuario decide si lo envía.

### RF-06. Cierre del día
- Botón **"Cerrar jornada"** y aviso a la hora de salida (lunes a viernes 4:45 pm; sábado 12:15 pm).
- **Asistente de cierre:** recorre cada actividad abierta (finalizar, o pausar con motivo y % de avance).
- Calcula y muestra el **porcentaje de productividad** del día, junto con la **meta de tiempo efectivo** y su barra de progreso.
- Muestra resumen: actividades completadas, pendientes, extras, tiempo efectivo, tiempo en pausas y datos de referencia (ver RF-10).
- Al cerrar el día se **muestra el PDF** automáticamente, con un botón **"Abrir carpeta del PDF"** para adjuntarlo fácilmente en WhatsApp.
- Función permanente **"Copiar resumen para WhatsApp"** con lo realizado al final del día.
- Se ejecuta la **copia de seguridad automática diaria** (RF-09).

### RF-07. Historial
- Consulta por día, semana, mes y rango de fechas.
- Filtros por categoría, estado, solicitante y tipo (planeada / extra / no planeada).
- Vista de detalle de cada día y cada actividad.
- Posibilidad de editar o corregir un registro (por ejemplo cuando se olvidó iniciar o finalizar una actividad), con **motivo obligatorio**, marca visible de "editado" y trazabilidad.

### RF-08. Reportes en PDF
- **PDF general del día:** resumen, porcentaje y semáforo, detalle de extras (solicitante, prioridad, aprobación, tiempo), pausas con motivos, actividades arrastradas y número de revisiones con sus motivos.
- **PDF específico:** por actividad, por categoría, por solicitante o por rango de fechas.
- **PDF semanal y mensual** con gráficos de tendencia.
- **PDF de día no laboral** (solo tiempo fuera de horario, sin porcentaje).
- Logo y colores de Gente Util: **no en la beta**; paleta neutra por ahora y logo antes de la v1.0 (configurable).

### RF-09. Configuración
- **Horario laboral por día de la semana**, con bloques (ver sección 6.1).
- Intervalos de recordatorios.
- Temas: varios predefinidos y personalizables (incluye claro y oscuro).
- Categorías de actividades creadas por cada usuario (con color).
- Lista de solicitantes (editable) y plantillas/recurrentes.
- Estilo, sonido y volumen de los avisos.
- Meta de tiempo efectivo (porcentaje configurable; se define en la beta).
- Pesos de la fórmula de productividad.
- Datos de empresa y usuario para los PDF.
- **PIN opcional:** cada persona lo activa si quiere; la app funciona igual sin él.
- **Copias de seguridad:**
  1. Automática diaria al cerrar la jornada, en una carpeta local.
  2. Botón para copiar a una USB o a una carpeta elegida.
  3. Copia y restauración manual desde Configuración.
- **Inicio automático con Windows:** la app se abre minimizada en la bandeja del sistema y avisa si no hay actividad en curso en horario laboral (se puede desactivar). Se configura **sin permisos de administrador** (carpeta Inicio del usuario o `HKCU`).

### RF-10. Metas diarias y datos de referencia
- **Meta de tiempo efectivo** (porcentaje de la jornada) con barra de progreso. El valor es configurable y se definirá probando en la beta.
- **Nunca hay meta por cantidad de piezas:** la cantidad depende de la demanda (un día llegan 5 flyers, otro 40) y no refleja el esfuerzo.
- **Datos de referencia sin evaluar**, por ejemplo: "hoy hiciste 12 flyers; tu promedio es 25 min por flyer".

### RF-11. Estadísticas
- Productividad por día, semana y mes (línea de tendencia).
- Tiempo por categoría.
- Tiempo estimado vs. real por tipo de actividad.
- Tiempo por solicitante (cuánto trabajo piden el jefe, las doctoras y otros).
- Número de revisiones y sus motivos (error propio, cambio de criterio, información nueva).

### RF-12. Experiencia de uso
- **Mini-ventana flotante** con el cronómetro siempre visible.
- **Atajos de teclado** para iniciar, pausar y finalizar.
- **Autocompletado** de actividades ya usadas.
- Icono en la bandeja del sistema con acceso rápido.

---

## 6. Requisitos no funcionales

| Código | Requisito | Criterio |
|---|---|---|
| RNF-01 | Ejecución 100 % local | Sin conexión a internet ni servicios externos |
| RNF-02 | Privacidad | Datos solo en el PC del usuario |
| RNF-03 | Rendimiento | Inicio de la app en menos de 3 s; consumo mínimo en segundo plano |
| RNF-04 | Confiabilidad | No perder datos si la app se cierra o el PC se apaga (guardado continuo) |
| RNF-05 | Usabilidad | Iniciar una actividad en máximo 2 clics |
| RNF-06 | Diseño | Interfaz moderna y limpia, varios temas, responsive a tamaño de ventana |
| RNF-07 | Mantenibilidad | Código modular, comentado y con pruebas |
| RNF-08 | Documentación | Manual de usuario, documentación técnica y guía de instalación |
| RNF-09 | Compatibilidad | Windows 10/11 (confirmado) |
| RNF-10 | Idioma | Solo español |
| RNF-11 | Instalación sin permisos de administrador | Se instala, se ejecuta, se actualiza y se desinstala con un usuario normal de Windows (ver 6.2) |

### 6.2 Instalación sin permisos de administrador (decidido en v0.5)

Los PC del equipo no darán permisos de administrador, por lo que la app se diseña para funcionar **100 % en el espacio del usuario**:

| Aspecto | Decisión |
|---|---|
| Instalador | `.exe` en modo "por usuario" (ej. Inno Setup con `PrivilegesRequired=lowest`); no pide elevación (UAC) |
| Carpeta de instalación | `%LOCALAPPDATA%\Programs\ControlTiempos` (no `Program Files`) |
| Datos y base de datos | `%APPDATA%\ControlTiempos` o `%LOCALAPPDATA%\ControlTiempos` (nunca junto al ejecutable ni en carpetas del sistema) |
| Copias de seguridad automáticas | Carpeta dentro del perfil del usuario (ej. Documentos) |
| Inicio con Windows | Acceso directo en la carpeta Inicio del usuario o clave `HKCU\...\Run` (nunca `HKLM`, servicios ni tareas programadas del sistema) |
| Registro de Windows | Solo `HKCU`, y solo si es necesario |
| Atajos de teclado | Atajos globales de usuario (`RegisterHotKey`), que no requieren administrador |
| Notificaciones | Icono de bandeja y ventanas de Qt, sin servicios del sistema |
| Desinstalación | Entrada de desinstalación por usuario; los datos se conservan salvo que el usuario pida borrarlos |
| Alternativa | Versión **portable** (carpeta `.zip` que se ejecuta desde cualquier carpeta del usuario), por si el instalador es bloqueado |

Cualquier librería, dependencia o función nueva debe revisarse contra esta regla antes de incluirse.

### 6.1 Horario laboral (confirmado)

| Día | Bloque 1 | Almuerzo | Bloque 2 | Duración de la jornada |
|---|---|---|---|---|
| Lunes a viernes | 7:30 am – 12:00 m | 12:00 m – 1:30 pm | 1:30 pm – 4:45 pm | 7 h 45 min |
| Sábado | 9:00 am – 12:15 pm | — | — | 3 h 15 min |
| Domingo y otros | Sin horario | — | — | Todo es "fuera de horario" |

El horario se configura **por día de la semana, con uno o más bloques**. El indicador Foco usa la duración de la jornada del día correspondiente.

---

## 7. Cálculo del porcentaje de productividad

> **Validación:** la fórmula se valida con el ingeniero en la **beta de equipo**, con datos reales y antes de la v1.0. Hasta entonces se usa la propuesta de abajo.

### 7.1 Indicadores base

| Indicador | Fórmula | Qué mide |
|---|---|---|
| **Cumplimiento del plan** | actividades planeadas completadas ÷ actividades planeadas | Si se cumplió lo anunciado en el grupo |
| **Eficiencia de tiempo** | tiempo estimado ÷ tiempo real (máx. 100 %) | Si se tardó lo esperado |
| **Foco** | tiempo efectivo de trabajo ÷ duración de la jornada del día | Cuánto de la jornada se dedicó a actividades registradas |

### 7.2 Fórmula propuesta (v1)

```
Productividad (%) = 0.40 × Cumplimiento + 0.30 × Eficiencia + 0.30 × Foco
```

Ejemplo: Cumplimiento 80 %, Eficiencia 80 %, Foco 77 % → `32 + 24 + 23,1 = 79,1 %` → 🟡 Aceptable.

### 7.3 Reglas especiales
- Las **actividades extra del jefe y de las doctoras** completadas cuentan como cumplimiento (no penalizan por desplazar lo planeado).
- Las extras de compañeros o terceros solo cuentan si el ingeniero las aprobó.
- Las actividades planeadas **pausadas por una prioridad máxima** o **arrastradas al día siguiente con motivo** no se cuentan como incumplidas: aportan su **porcentaje de avance** del día y completan el resto el día que se finalizan.
- Las **recurrentes que no se crean** (sin demanda) no afectan el cálculo.
- Las actividades **no planeadas** suman tiempo efectivo (Foco) pero no entran al denominador del Cumplimiento.
- Los tiempos en pausa con tipo "causa externa" no penalizan el Foco; el almuerzo y el tiempo pausado no cuentan como tiempo trabajado.
- El tiempo **fuera de horario laboral no entra** en el porcentaje del día.
- El tiempo trabajado en una actividad **reasignada** cuenta para el día.
- Las **revisiones** suman tiempo trabajado del día pero **no cuentan como un nuevo cumplimiento** (decidido).
- **Eficiencia sin estimado:** se usa el **promedio histórico** de esa categoría para esa persona; si no hay historial, la actividad no entra en la Eficiencia.
- Los pesos (40/30/30) se pueden cambiar en Configuración.

### 7.4 Semáforo visual
- 🟢 ≥ 85 %: Excelente
- 🟡 60–84 %: Aceptable
- 🔴 < 60 %: Por mejorar

---

## 8. Flujo principal de uso

```
Inicio del día (la app abre sola con Windows, en la bandeja)
   │
   ▼
[Planear actividades: plantillas/recurrentes propuestas + nuevas]
   │
   ▼
[Copiar plan para WhatsApp] ──► se envía al grupo (el jefe lo ve ahí)
   │
   ▼
[Iniciar actividad] ──► cronómetro corriendo
   │
   ├── cada N min ──► "¿Sigues con la actividad?" (ventana + sonido)
   │        ├── Sí ──► continúa
   │        ├── No ──► se completa ──► elegir siguiente actividad
   │        ├── Pausar ──► registrar motivo
   │        └── Sin respuesta ──► se repite; el cronómetro sigue y queda "sin respuesta"
   │
   ├── Actividad extra ──► jefe/doctoras: se inicia ya (pausa la actual y pregunta)
   │                   └─► compañeros/terceros: bloqueada hasta que el usuario
   │                       marque la decisión del ingeniero (aprobada/rechazada)
   │
   ├── Piezas repetidas ──► "Finalizar y empezar siguiente"
   │
   ├── Cambios pedidos ──► reabrir como Revisión (cronómetro nuevo)
   │
   ├── 12:00 m ──► aviso de almuerzo ──► pausa
   │
   ▼
[Aviso de salida] ──► asistente de cierre (finalizar o pausar con motivo y % avance)
   │
   ▼
[Cerrar jornada] ──► % de productividad + meta de tiempo ──► copia de seguridad
   │
   ▼
[Se muestra el PDF] ──► "Abrir carpeta del PDF" ──► se envía por WhatsApp
```

---

## 9. Modelo de datos (SQLite local)

### Tablas principales

**`usuarios`**
| Campo | Tipo | Nota |
|---|---|---|
| id | INTEGER PK | |
| nombre | TEXT | |
| tema | TEXT | tema elegido |
| pin_hash | TEXT | nulo si no usa PIN |

**`horarios`**
| Campo | Tipo | Nota |
|---|---|---|
| id | INTEGER PK | |
| dia_semana | INTEGER | 0 = lunes ... 6 = domingo |
| bloque | INTEGER | 1, 2... (lunes a viernes tiene 2) |
| hora_inicio | TIME | |
| hora_fin | TIME | |

**`categorias`**
| Campo | Tipo | Nota |
|---|---|---|
| id | INTEGER PK | |
| nombre | TEXT | libre: la crea cada usuario |
| color | TEXT | para la interfaz |

**`solicitantes`**
| Campo | Tipo | Nota |
|---|---|---|
| id | INTEGER PK | |
| nombre | TEXT | ej. Ing. Luis Eduardo, Dra. Sonia, Dr. Pérez |
| tipo | TEXT | jefe / doctora / compañero / tercero |
| prioridad_defecto | TEXT | máxima / mínima / normal |
| requiere_aprobacion | BOOLEAN | verdadero para compañeros y terceros |
| activo | BOOLEAN | permite ocultar sin borrar historial |

**`plantillas`** (actividades frecuentes y recurrentes)
| Campo | Tipo | Nota |
|---|---|---|
| id | INTEGER PK | |
| nombre | TEXT | ej. "Flyers", "Posts de Instagram" |
| categoria_id | INTEGER FK | |
| tiempo_estimado_min | INTEGER | opcional |
| recurrencia | TEXT | diaria / días de la semana / ninguna |
| dias_semana | TEXT | ej. "0,1,2,3,4" |
| intervalo_recordatorio_min | INTEGER | opcional |

**`jornadas`**
| Campo | Tipo | Nota |
|---|---|---|
| id | INTEGER PK | |
| fecha | DATE | única por usuario |
| hora_inicio | DATETIME | |
| hora_fin | DATETIME | |
| es_laboral | BOOLEAN | falso si se abrió en día sin horario |
| duracion_jornada_seg | INTEGER | según el horario del día |
| productividad | REAL | nulo en días no laborales |
| tiempo_efectivo_seg | INTEGER | para la meta |
| estado | TEXT | abierta / cerrada |

**`actividades`**
| Campo | Tipo | Nota |
|---|---|---|
| id | INTEGER PK | |
| jornada_id | INTEGER FK | |
| categoria_id | INTEGER FK | |
| plantilla_id | INTEGER FK | si viene de una plantilla |
| nombre | TEXT | ej. "Flyer 1" |
| tipo | TEXT | planeada / extra / no_planeada |
| solicitante_id | INTEGER FK | quién la pidió (nulo si es propia) |
| prioridad | TEXT | normal / máxima / mínima |
| estado | TEXT | bloqueada / pendiente / en curso / pausada / completada / arrastrada / reasignada / rechazada / aplazada |
| actividad_padre_id | INTEGER FK | si es revisión, apunta a la original |
| es_revision | BOOLEAN | |
| revision_solicitante_id | INTEGER FK | quién pidió el cambio |
| revision_tipo | TEXT | mínimo / complicado |
| revision_que_cambiar | TEXT | |
| revision_motivo | TEXT | error propio / cambio de criterio / información nueva |
| reasignada_a | TEXT | |
| reasignacion_motivo | TEXT | |
| editado | BOOLEAN | |
| editado_motivo | TEXT | obligatorio si editado |
| tiempo_estimado_min | INTEGER | opcional |
| notas | TEXT | opcional |
| descripcion | TEXT | en qué consistió |
| motivo_urgencia | TEXT | solo extras |
| fecha_limite | DATETIME | opcional |
| canal_solicitud | TEXT | WhatsApp / llamada / correo / presencial |
| aprobacion_estado | TEXT | no requerida / pendiente / aprobada / rechazada |
| aprobacion_fecha | DATETIME | cuándo decidió el ingeniero |
| aprobacion_canal | TEXT | por qué canal |
| avance_pct | INTEGER | % de avance al pausar |
| intervalo_recordatorio_min | INTEGER | personalizado |

**`sesiones_tiempo`** (cada tramo de cronómetro)
| Campo | Tipo | Nota |
|---|---|---|
| id | INTEGER PK | |
| actividad_id | INTEGER FK | |
| inicio | DATETIME | |
| fin | DATETIME | |
| duracion_seg | INTEGER | |
| fuera_horario | BOOLEAN | no cuenta en el % |
| lugar | TEXT | oficina / casa |

**`pausas`**
| Campo | Tipo | Nota |
|---|---|---|
| id | INTEGER PK | |
| actividad_id | INTEGER FK | |
| inicio | DATETIME | |
| fin | DATETIME | |
| motivo | TEXT | |
| tipo | TEXT | almuerzo / prioridad / externa / personal / fin de jornada / otro |
| es_externa | BOOLEAN | no penaliza foco |
| avance_pct | INTEGER | solo en pausa de fin de jornada |

**`recordatorios_log`**
| Campo | Tipo | Nota |
|---|---|---|
| id | INTEGER PK | |
| actividad_id | INTEGER FK | |
| momento | DATETIME | |
| respuesta | TEXT | sí / no / pausar / sin respuesta |

**`copias_seguridad`**
| Campo | Tipo | Nota |
|---|---|---|
| id | INTEGER PK | |
| fecha | DATETIME | |
| ruta | TEXT | |
| tipo | TEXT | automática / externa / manual |

**`configuracion`**
| Campo | Tipo | Nota |
|---|---|---|
| clave | TEXT PK | pesos de fórmula, meta de tiempo, sonido, inicio con Windows, etc. |
| valor | TEXT | |

---

## 10. Pantallas y diseño (UI/UX)

### 10.1 Principios de diseño
- Moderno, limpio, mucho espacio en blanco, tipografía legible.
- Varios temas predefinidos y personalizables (incluye claro y oscuro). Paleta neutra hasta tener la de Gente Util.
- Una acción principal por pantalla.
- El cronómetro activo siempre visible (mini-ventana flotante).
- Atajos de teclado para iniciar, pausar y finalizar.

### 10.2 Pantallas

| # | Pantalla | Contenido clave |
|---|---|---|
| 1 | **Hoy** (principal) | Actividades del día, actividad en curso con cronómetro grande, Iniciar/Pausar/Finalizar, "Finalizar y empezar siguiente", barra de meta de tiempo |
| 2 | **Planear día** | Alta rápida, plantillas y recurrentes propuestas, autocompletado, botón copiar para WhatsApp |
| 3 | **Actividad extra** | Formulario rápido: solicitante, motivo, fecha límite, canal; aprobación del ingeniero |
| 4 | **Cierre de jornada** | Asistente de cierre, porcentaje, meta, resumen, copiar para WhatsApp, PDF y abrir carpeta |
| 5 | **Historial** | Calendario, filtros, detalle por día y actividad, revisiones |
| 6 | **Reportes** | Generar PDF general/específico/día no laboral, vista previa |
| 7 | **Estadísticas** | Tendencia, tiempo por categoría, estimado vs. real, por solicitante, revisiones |
| 8 | **Configuración** | Horarios por día, recordatorios, solicitantes, plantillas, categorías, temas, PIN, copias de seguridad, inicio con Windows |

### 10.3 Extras de experiencia
- Mini-widget flotante con cronómetro siempre encima de otras ventanas.
- Icono en la bandeja del sistema con acceso rápido.
- Notificaciones de Windows con botones de respuesta (Sí / No / Pausar).

---

## 11. Arquitectura y tecnología propuesta

### 11.1 Opción recomendada: Python + PySide6 (Qt)

| Capa | Tecnología | Motivo |
|---|---|---|
| Lenguaje | Python 3.11+ | Fácil de generar y mantener con IA |
| Interfaz | PySide6 (Qt) con estilos QSS / QML | Apps de escritorio nativas, system tray y notificaciones |
| Base de datos | SQLite + SQLAlchemy | Local, sin instalación, confiable |
| Notificaciones | Qt system tray + notificaciones de Windows | Recordatorios con botones |
| Gráficos | Matplotlib o pyqtgraph | Estadísticas |
| PDF | ReportLab o WeasyPrint (desde HTML) | Reportes con buen diseño |
| Empaquetado | PyInstaller + instalador por usuario (ej. Inno Setup) | Genera `.exe` instalable **sin permisos de administrador** (ver 6.2) y una versión portable |
| Pruebas | pytest | Lógica de tiempos y productividad |

### 11.2 Alternativa: Tauri (o Electron) + React
- Ventaja: diseño web más flexible. Desventaja: más complejidad (dos lenguajes).

> **Decisión:** Python + PySide6. El sistema operativo (Windows 10/11) está confirmado.

### 11.3 Arquitectura en capas

```
┌─────────────────────────────┐
│   Interfaz (UI / pantallas) │
├─────────────────────────────┤
│   Servicios (lógica)        │  ← cronómetro, recordatorios, productividad,
│                             │    reportes, copias de seguridad, plantillas
├─────────────────────────────┤
│   Repositorios (datos)      │  ← acceso a SQLite
├─────────────────────────────┤
│   Base de datos local       │
└─────────────────────────────┘
```

### 11.4 Estructura de carpetas sugerida

```
control-tiempos/
├── README.md
├── requirements.txt
├── docs/
│   ├── manual_usuario.md
│   ├── documentacion_tecnica.md
│   ├── decisiones.md
│   └── changelog.md
├── src/
│   ├── main.py
│   ├── ui/              # pantallas y componentes
│   ├── services/        # cronometro, recordatorios, productividad, reportes, backups
│   ├── data/            # modelos, repositorios, migraciones
│   ├── reports/         # plantillas PDF
│   ├── assets/          # iconos, fuentes, sonidos (logo llega antes de la 1.0)
│   └── config/
├── tests/
├── backups/
└── build/               # scripts de empaquetado
```

---

## 12. Plan de trabajo por fases

| Fase | Nombre | Entregables | Duración estimada |
|---|---|---|---|
| 0 | Definición | Plan aprobado, decisiones cerradas, tecnología elegida | **Cerrada (v0.5)** |
| 1 | Base del proyecto | Estructura, entorno, base de datos y modelos (incluye horarios por día) | 2–3 días |
| 2 | Núcleo de tiempos | Actividades, cronómetro, pausas, finalizar, revisiones, "finalizar y empezar siguiente" | 4–5 días |
| 3 | Recordatorios | Notificaciones "¿Sigues con...?", finalización, inicio, almuerzo y salida, bandeja del sistema, inicio con Windows | 3–4 días |
| 4 | Jornada y productividad | Cierre del día, asistente de cierre, fórmula, meta de tiempo, copiar plan/resumen para WhatsApp | 3–4 días |
| 5 | Interfaz moderna | Pantallas finales, temas, mini-widget, atajos, autocompletado | 5–7 días |
| 6 | Historial y estadísticas | Calendario, filtros, gráficos (RF-11) | 3–4 días |
| 7 | Reportes PDF | PDF general, específico, semanal, mensual y de día no laboral | 3–4 días |
| 8 | Pruebas y betas | **Beta personal** (Andrés), luego **beta de equipo** con validación de la fórmula con el ingeniero | 5 días + tiempo de uso real |
| 9 | Empaquetado y documentación | Logo y paleta de Gente Util, instalador `.exe` por usuario (sin administrador) y versión portable, manual y documentación técnica → **v1.0** | 3 días |

**Total estimado:** 4–6 semanas con apoyo de IA, más el tiempo de las betas.

---

## 13. Metodología de trabajo con IA

### 13.1 Reglas para guiar al modelo
1. Trabajar **una fase y un módulo a la vez**; no pedir la app completa de una sola vez.
2. Pegar siempre este plan como contexto al inicio de cada sesión nueva.
3. Pedir que cada módulo incluya: código, comentarios, pruebas y actualización de la documentación.
4. Probar cada módulo antes de pasar al siguiente.
5. Guardar el proyecto en Git y hacer un commit por funcionalidad.
6. Mantener `docs/decisiones.md` con cada decisión importante.

### 13.2 Prompt inicial sugerido para el modelo

```
Actúa como un ingeniero de software senior y mentor. Vamos a construir, paso a paso,
una app de escritorio LOCAL para Windows 10/11 para control de tiempos y productividad
laboral. Te comparto el plan completo en Markdown (adjunto, versión 0.5).

Reglas:
- Trabaja por fases, siguiendo la sección 12 del plan.
- Antes de escribir código en cada fase, resume qué vas a hacer y pregúntame
  lo que sea ambiguo.
- Entrega código completo, comentado y modular, con pruebas (pytest).
- Documenta todo en la carpeta docs/ al terminar cada módulo.
- Usa Python + PySide6 + SQLite según la sección 11.
- Diseño moderno con varios temas (claro y oscuro incluidos), paleta neutra por ahora.
- Todo debe funcionar sin internet. Interfaz solo en español.

Empecemos por la Fase 1: estructura del proyecto, entorno virtual,
requirements.txt, base de datos y modelos según la sección 9.
```

### 13.3 Plantilla de prompt para cada fase
```
Contexto: [pegar plan + resumen de lo ya construido]
Fase actual: [número y nombre]
Tarea concreta: [módulo específico]
Criterios de aceptación: [de la sección 14]
Entrega: código + pruebas + actualización de docs
```

---

## 14. Criterios de aceptación (v1.0)

- [ ] Puedo planear actividades del día, aceptar plantillas/recurrentes propuestas y copiar el listado para WhatsApp.
- [ ] Puedo trabajar sin plan: las actividades quedan marcadas como "no planeadas".
- [ ] Puedo iniciar una actividad en máximo 2 clics y el cronómetro corre.
- [ ] Con muchas piezas iguales, "Finalizar y empezar siguiente" mantiene el flujo en 2 clics.
- [ ] A los N min aparece "¿Sigues con [actividad]?" y se repite.
- [ ] Si respondo "No", la actividad se completa y el cronómetro se detiene.
- [ ] Si no respondo, la ventana y el sonido se repiten, el cronómetro sigue contando y queda "sin respuesta".
- [ ] Puedo pausar con motivo y el tiempo pausado queda registrado.
- [ ] Puedo registrar extras indicando solicitante, motivo, fecha límite y canal; la prioridad sale del solicitante.
- [ ] Las actividades de compañeros o terceros quedan bloqueadas hasta marcar la decisión del ingeniero (aprobada o rechazada).
- [ ] Puedo crear solicitantes nuevos y editar la lista en mi PC.
- [ ] Al llegar una actividad de prioridad máxima, la actual se pausa por completo y la app me pregunta.
- [ ] Una actividad sin terminar al cierre se pausa con motivo y % de avance, queda arrastrada y se finaliza después (oficina o casa).
- [ ] El tiempo fuera de horario se registra aparte y no entra en el porcentaje del día.
- [ ] En un día sin horario, al iniciar una actividad se crea una jornada sin porcentaje y se genera un PDF aparte.
- [ ] El horario se configura por día de la semana y el Foco usa la duración de la jornada de ese día.
- [ ] Puedo personalizar el intervalo de recordatorios por persona, categoría y actividad.
- [ ] Puedo reabrir una actividad finalizada y registrar una revisión con su propio cronómetro, sin alterar el tiempo original.
- [ ] Cada revisión guarda quién pidió el cambio, tipo, qué se pidió y motivo; el reporte muestra el número de revisiones sin alertas.
- [ ] Puedo marcar una actividad como reasignada y el tiempo ya trabajado cuenta en el día.
- [ ] Puedo corregir un registro solo indicando un motivo, y queda marcado como editado.
- [ ] Puedo crear mis propias categorías y actividades libremente.
- [ ] Veo mi meta de tiempo efectivo con barra de progreso y datos de referencia, sin metas por cantidad.
- [ ] Al cerrar la jornada veo el % de productividad y el resumen, y se muestra el PDF con acceso a su carpeta.
- [ ] El PDF incluye porcentaje y semáforo, detalle de extras (solicitante, prioridad, aprobación, tiempo), pausas con motivos, actividades arrastradas y revisiones.
- [ ] El historial guarda todos los días y permite consultar y filtrar.
- [ ] Las estadísticas muestran tendencia, tiempo por categoría, estimado vs. real, tiempo por solicitante y revisiones con motivos.
- [ ] Hay copia automática diaria, copia a USB/carpeta y copia/restauración manual.
- [ ] La app se abre con Windows en la bandeja y avisa si no hay actividad en curso.
- [ ] Existen mini-ventana flotante, atajos de teclado y autocompletado.
- [ ] El PIN es opcional y la app funciona igual sin él.
- [ ] Si se cierra la app o se apaga el PC, no se pierden datos.
- [ ] Funciona sin internet.
- [ ] Existe manual de usuario y documentación técnica.
- [ ] Hay un instalador `.exe` para los PC del equipo, con logo y paleta de Gente Util.
- [ ] Se instala, se ejecuta, se actualiza y se desinstala **sin permisos de administrador** (sin pedir UAC), y las funciones de inicio con Windows, copias y atajos funcionan igual.
- [ ] Existe una versión portable que se ejecuta desde una carpeta del usuario.

---

## 15. Riesgos y mitigación

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Usuarios olvidan iniciar o finalizar actividades | Datos poco confiables | Recordatorios de inicio/fin, corrección manual con motivo |
| Exceso de notificaciones molesta al usuario | Rechazo de la app | Intervalos configurables, estilo de aviso a elección |
| La fórmula de productividad no convence al jefe | Pérdida de utilidad | Validarla en la beta de equipo con datos reales; pesos configurables |
| Pérdida de datos por cierre inesperado | Pérdida de confianza | Guardado continuo y tres tipos de copia de seguridad |
| Alcance crece demasiado | Retrasos | Congelar v1.0 y pasar ideas nuevas a la sección 19 |
| El código generado por IA tiene errores | Fallos | Pruebas unitarias, revisión y avance por módulos pequeños |
| Una meta por cantidad de piezas castiga la baja demanda | Medición injusta | La meta es solo por tiempo efectivo; la cantidad es dato de referencia |
| El jefe no ve el avance en tiempo real | Menos visibilidad | Se mantiene el flujo por WhatsApp; la vista del jefe queda para el futuro |
| Sin permisos de administrador, el antivirus, SmartScreen o políticas de la empresa (ej. AppLocker) pueden bloquear un `.exe` sin firmar | La app no se instala o no abre | Instalación por usuario, versión portable como alternativa, probar en un PC real del equipo desde la beta personal y, si hace falta, pedir al ingeniero autorizar el ejecutable |

---

## 16. Documentación requerida

| Documento | Contenido | Cuándo |
|---|---|---|
| `README.md` | Qué es, cómo instalar y ejecutar | Fase 1, se actualiza siempre |
| `docs/manual_usuario.md` | Guía paso a paso con capturas | Fase 9 |
| `docs/documentacion_tecnica.md` | Arquitectura, modelo de datos, módulos | Se actualiza cada fase |
| `docs/decisiones.md` | Decisiones y su justificación | Continuo |
| `docs/changelog.md` | Cambios por versión | Continuo |
| Comentarios en código | Docstrings en funciones y clases | Continuo |

---

## 17. Decisiones

### 17.1 Resueltas

**Hasta v0.3:**
- Cada PC es independiente.
- Recordatorios personalizables por persona, categoría y actividad.
- Prioridad definida por el solicitante (jefe y doctoras = máxima; compañeros = mínima con aprobación).
- Extras de jefe y doctoras cuentan como cumplimiento.
- Actividad interrumpida = pausa completa; sin terminar al cierre = pausa con motivo y % de avance, arrastrada.
- Tiempo fuera de horario se registra aparte y no cuenta en el %.
- Todo es manual (rechazar, reasignar, aplazar, eliminar).
- Reabrir actividades = revisiones vinculadas con cronómetro propio.
- Actividad relegada = "Reasignada a...", el tiempo trabajado cuenta.
- Aviso "¿Sigues con...?" = ventana + sonido, se repite sin respuesta, cronómetro sigue.
- Correcciones con motivo obligatorio y marca de "editado".
- Categorías libres.

**Nuevas en v0.5:**
- **Canal con el jefe:** WhatsApp permanente (plan en la mañana, PDF al cierre). El jefe usa Mac y no instala la app. Vista del jefe y asignación de extras desde la app: feature futura.
- **Aprobación:** el ingeniero decide fuera de la app; el usuario marca aprobada o rechazada.
- **Terceros "importantes":** se registra la persona que pidió, con aprobación del ingeniero marcada.
- **Sistema operativo:** todos Windows 10/11.
- **Horario:** lunes a viernes 7:30–12:00 y 1:30–4:45 pm; sábado 9:00 am–12:15 pm.
- **Revisiones:** suman tiempo trabajado, no un nuevo cumplimiento; sin alertas, solo número y motivos.
- **Solicitantes iniciales:** Ing. Luis Eduardo, Dra. Sonia, Dra. Yolanda, Dra. Liliana; lista editable por PC.
- **Logo y paleta:** después de las betas, antes de la 1.0.
- **Días no laborales:** sin festivos precargados; si se trabaja, jornada sin porcentaje y PDF aparte.
- **Copias de seguridad:** automática diaria, a USB/carpeta y manual.
- **Inicio con Windows:** sí, minimizada en la bandeja.
- **Sin plan:** se permite trabajar sin plan; se marcan "no planeadas".
- **Metas:** tiempo efectivo configurable (se define en la beta) más datos de referencia; nunca por cantidad.
- **Estadísticas:** tendencia, por categoría, estimado vs. real, por solicitante, revisiones y motivos.
- **Plantillas y recurrentes:** se proponen al planear; si no hay demanda, no se crean.
- **Piezas repetidas:** una actividad por pieza con "Finalizar y empezar siguiente".
- **PIN:** opcional.
- **Extras de la beta:** mini-ventana, atajos y autocompletado.
- **Eficiencia sin estimado:** promedio histórico de la categoría; sin historial, no entra.
- **Validación de la fórmula:** en la beta de equipo, con el ingeniero.
- **Idioma:** solo español.
- **Instalación:** sin permisos de administrador (instalador por usuario, datos en el perfil del usuario, inicio con Windows y atajos sin elevación), más versión portable.

### 17.2 Pendientes
1. Definir el valor de la **meta de tiempo efectivo** (probando en la beta).
2. Validar la **fórmula 40/30/30** con el ingeniero (beta de equipo).
3. Entregar **logo y paleta** de Gente Util (antes de la v1.0).
4. Cargar la **lista inicial de compañeros** como solicitantes, y las plantillas de cada persona.

---

## 18. Próximos pasos inmediatos

1. Abrir una conversación o proyecto dedicado y pegar este plan (v0.5) con el prompt de la sección 13.2.
2. Ejecutar la **Fase 1**: estructura, entorno, base de datos y modelos (sección 9) y verificar que funcionan.
3. Avanzar fase por fase, probando y documentando en cada una.
4. Al llegar a la Fase 8: beta personal, luego beta de equipo y validación de la fórmula.

---

## 19. Funciones para después de la v1.0

- **Vista del jefe** (Mac): consultar planes y avances del equipo y **crear y asignar actividades extra** directamente a una persona. Requiere una app o web compatible con Mac y una forma de consolidar los datos del equipo.
- **Consolidación de datos del equipo** (carpeta compartida o exportar/importar).
- Envío automático del plan y del PDF a WhatsApp.
- Precarga de festivos de Colombia y marcado de vacaciones e incapacidades.
- Sincronización en la nube o multiusuario centralizado.
- App móvil.
- Integración con calendario.

---

## 20. Historial de versiones del plan

| Versión | Cambios |
|---|---|
| 0.3 | Solicitantes, prioridades, pausas con avance, fuera de horario, recordatorios personalizables, revisiones, reasignación, categorías libres |
| 0.4 | Aviso con ventana y sonido, correcciones con motivo, temas, consolidación pendiente, WhatsApp transitorio |
| 0.5 | WhatsApp permanente; horario real; solicitantes iniciales; días no laborales; copias de seguridad; inicio con Windows; metas por tiempo; plantillas/recurrentes; estadísticas; PIN opcional; betas; planeación cerrada; instalación sin permisos de administrador |

---

*Documento vivo: se actualiza conforme avance el proyecto.*
