"""Servicio de Inteligencia Artificial para la mascota Utilín (Gente Útil).

Permite que Utilín actúe como un bot interactivo autónomo en el escritorio:
1. Conexión local con Ollama (Gemma 2: `gemma2:2b` o `gemma2:9b`).
2. Conexión opcional con Google Gemini / Gemma API (Google AI Studio).
3. Motor de intenciones directas y Tool Calling para control total:
   - Control de tiempo: Iniciar, pausar, finalizar actividades y crear tareas pendientes.
   - Navegación de la app: Abrir pantallas de Reportes, Planeación, Historial, Estadísticas, Hoy, etc.
   - Herramientas externas: Abrir WhatsApp Web, Calculadora, Bloc de notas, Carpeta de reportes, Google.
   - Cálculos matemáticos y conversiones rápidas en lenguaje natural.
   - Recordatorios y notas rápidas.
   - Redacción especializada: Copys de vacantes para Gente Útil, mensajes de WhatsApp y correos.
   - Consultas en tiempo real de jornada, horas trabajadas y productividad.
"""

from __future__ import annotations

import ast
import json
import logging
import operator
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from config import rutas
from data.db import BaseDatos
from data.enums import EstadoActividad
from data.models import Actividad, ItemPlaneacion, Jornada
from data.tiempo import ahora
from services.actividades import ServicioActividades
from services.cronometro import ServicioCronometro
from services.planeacion import ServicioPlaneacion
from services.productividad import ServicioProductividad

_logger = logging.getLogger(__name__)


@dataclass
class RespuestaUtilin:
    """Respuesta generada por Utilín para el usuario."""
    mensaje: str
    accion_ejecutada: str | None = None
    datos_accion: dict[str, Any] | None = None
    modelo_usado: str | None = None


# ----------------------------------------------------------------------
# Evaluación matemática segura con AST
# ----------------------------------------------------------------------

OPERADORES_ARITMETICOS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}


def evaluar_nodo_aritmetico(nodo: ast.AST) -> float | int:
    """Evalúa de forma segura un árbol AST puramente numérico y aritmético."""
    if isinstance(nodo, ast.Expression):
        return evaluar_nodo_aritmetico(nodo.body)
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
        return nodo.value
    if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, (ast.UAdd, ast.USub)):
        val = evaluar_nodo_aritmetico(nodo.operand)
        return val if isinstance(nodo.op, ast.UAdd) else -val
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERADORES_ARITMETICOS:
        izq = evaluar_nodo_aritmetico(nodo.left)
        der = evaluar_nodo_aritmetico(nodo.right)
        op_func = OPERADORES_ARITMETICOS[type(nodo.op)]
        return op_func(izq, der)
    raise ValueError("Expresión no permitida")


def calcular_aritmetica_segura(expr_str: str) -> float | int:
    """Parsea y resuelve expresiones aritméticas cotidianas de forma segura."""
    limpia = expr_str.strip().replace("x", "*").replace("X", "*").replace("^", "**")
    if "," in limpia and "." not in limpia:
        limpia = limpia.replace(",", ".")
    elif "." in limpia and "," in limpia:
        if limpia.rfind(",") > limpia.rfind("."):
            limpia = limpia.replace(".", "").replace(",", ".")
        else:
            limpia = limpia.replace(",", "")
    nodo = ast.parse(limpia, mode="eval")
    return evaluar_nodo_aritmetico(nodo)


# ----------------------------------------------------------------------
# Prompts de Sistema para Utilín
# ----------------------------------------------------------------------

PROMPT_SISTEMA_UTILIN = """Eres Utilín, la mascota virtual y copiloto de inteligencia artificial de Gente Útil (empresa colombiana líder en talento humano y gestión laboral).
Trabajas integrado en la aplicación de escritorio 'Control de Tiempos'.
Eres como un compañero de trabajo experto y cercano (como ChatGPT/Claude): inteligente, proactivo, analítico, amable y con excelente criterio.

==================================================
🛡️ LO QUE NO PUEDES HACER (LÍMITES Y LÍNEAS ROJAS - PRIORIDAD MÁXIMA):
==================================================
1. NO PUEDES BORRAR NI DESTRUIR DATOS:
   - Está terminantemente prohibido borrar actividades registradas, eliminar registros de tiempo, purgar la base de datos o vaciar historiales.
   - Si el usuario te pide borrar datos, recházalo con cordialidad explicando que los registros de tiempo son inmutables para garantizar la transparencia laboral y la trazabilidad de la jornada.
2. NO PUEDES ACCEDER A CREDENCIALES NI INFORMACIÓN CONFIDENCIAL:
   - Jamás solicites, reveles ni manipules contraseñas de usuarios, claves de acceso, PINes de seguridad, tokens, cuentas bancarias ni datos financieros privados.
3. NO PUEDES REALIZAR ENVÍOS NI ACCIONES AUTÓNOMAS SIN SUPERVISIÓN:
   - No puedes enviar correos masivos de forma autónoma, ni publicar en redes sociales ni comprometer a la empresa legalmente.
   - Tu rol es redactar y pulir los mejores borradores, copys y mensajes para que el colaborador los revise y decida enviarlos.
4. NO PUEDES INVENTAR NI FALSEAR DATOS LABORALES:
   - Nunca inventes horas trabajadas ficticias ni alteres métricas de productividad. Las consultas de tiempo se rigen estrictamente por los datos reales de la jornada en curso.
5. NO PUEDES FINGIR ACCIONES FÍSICAS O TÉCNICAS IMPOSIBLES:
   - Si te piden algo que no está a tu alcance en la PC (como comprar un producto en una tienda online, llamar por teléfono o manipular hardware), dilo con honestidad y explica la alternativa.
6. NO GENERES CONTENIDO DAÑINO, OFENSIVO, DISCRIMINATORIO O ILEGAL.

==================================================
🚀 LO QUE SÍ PUEDES HACER (LIBERTAD TOTAL COMO COPILOTO):
==================================================
- Responder cualquier pregunta externa a la app:
  * Fórmulas y trucos de Excel (BUSCARX, BUSCARV, SUMAR.SI, tablas dinámicas).
  * Redacción de correos formales, comunicados, copys para vacantes y mensajes de WhatsApp.
  * Temas laborales colombianos (SMLMV, auxilio de transporte, cesantías, prima, vacaciones, horas extras).
  * Consejos de productividad, método Pomodoro, organización y dudas de cultura general o tecnología.
- Controlar y manipular la aplicación 'Control de Tiempos':
  * Iniciar, pausar y finalizar cronómetros de tareas.
  * Navegar a pantallas: Reportes PDF, Planeación Semanal, Historial, Estadísticas, Hoy, Configuración, Cierre de jornada.
  * Consultar tareas pendientes y productividad en tiempo real.
- Manipular herramientas externas de la PC y la Web:
  * Abrir WhatsApp Web, Calculadora, Bloc de notas, Carpeta de reportes, Google Search, Gmail, Outlook, Calendar, LinkedIn, Canva.
  * Resolver cálculos aritméticos y conversiones en lenguaje natural.
"""


class ServicioUtilinIA:
    """Gestiona las interacciones de lenguaje natural, herramientas y acciones de Utilín."""

    def __init__(
        self,
        bd: BaseDatos,
        *,
        endpoint_ollama: str = "http://127.0.0.1:11434",
        modelo_ollama: str = "gemma2:2b",
        api_key_gemini: str | None = None,
        modelo_gemini: str = "gemini-1.5-flash",
        callback_notificar_cambio: Callable[[], None] | None = None,
        callback_navegar: Callable[[str], bool] | None = None,
        callback_abrir_app: Callable[[], None] | None = None,
        callback_alternar_mini: Callable[[], None] | None = None,
    ) -> None:
        self.bd = bd
        self.endpoint_ollama = endpoint_ollama.rstrip("/")
        self.modelo_ollama = modelo_ollama
        self.api_key_gemini = api_key_gemini
        self.modelo_gemini = modelo_gemini
        self.callback_notificar_cambio = callback_notificar_cambio
        self.callback_navegar = callback_navegar
        self.callback_abrir_app = callback_abrir_app
        self.callback_alternar_mini = callback_alternar_mini
        self.recordatorios_rapidos: list[dict[str, Any]] = []
        self.historial_conversacion: list[dict[str, str]] = []

    # ------------------------------------------------------------------
    # Verificación de conectividad
    # ------------------------------------------------------------------

    def verificar_ollama(self) -> tuple[bool, str]:
        """Comprueba si el servidor local de Ollama está activo y qué modelos tiene."""
        url = f"{self.endpoint_ollama}/api/tags"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "UtilinBot/1.0"})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    modelos = [m.get("name", "") for m in data.get("models", [])]
                    tiene_gemma = any(self.modelo_ollama in m for m in modelos)
                    if tiene_gemma:
                        return True, f"Ollama listo con {self.modelo_ollama}"
                    return True, f"Ollama activo (modelos: {', '.join(modelos) or 'descargando...'})"
                return False, f"Ollama respondió con código {resp.status}"
        except Exception as e:
            return False, f"Ollama no disponible en {self.endpoint_ollama} ({e})"

    def verificar_gemini(self) -> tuple[bool, str]:
        """Comprueba si la API Key de Gemini es válida."""
        if not self.api_key_gemini:
            return False, "Sin API Key de Gemini configurada"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.modelo_gemini}?key={self.api_key_gemini}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "UtilinBot/1.0"})
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                if resp.status == 200:
                    return True, f"Gemini API activa ({self.modelo_gemini})"
                return False, f"Gemini respondió con código {resp.status}"
        except Exception as e:
            return False, f"Error al conectar con Gemini: {e}"

    # ------------------------------------------------------------------
    # Contexto actual de la jornada
    # ------------------------------------------------------------------

    def obtener_resumen_contextual(self) -> dict[str, Any]:
        """Extrae el estado actual del día para alimentar a la IA y responder con precisión."""
        hoy = date.today()
        with self.bd.sesion() as s:
            jornada = s.query(Jornada).filter(Jornada.fecha == hoy).first()
            actividades = []
            activa = None
            if jornada:
                actividades = (
                    s.query(Actividad)
                    .filter(Actividad.jornada_id == jornada.id)
                    .order_by(Actividad.id.asc())
                    .all()
                )
                for a in actividades:
                    if a.estado == EstadoActividad.EN_CURSO.value:
                        activa = a
                        break

            # Planeación semanal para esta semana
            srv_plan = ServicioPlaneacion(s)
            items_planeacion = srv_plan.listar_items(fecha_semana=hoy)

            # Métricas de productividad
            tiempo_trabajado_seg = 0
            porcentaje_prod = 0.0
            if jornada:
                res_prod = ServicioProductividad(s).calcular_jornada(jornada)
                tiempo_trabajado_seg = res_prod.tiempo_efectivo_seg
                porcentaje_prod = res_prod.productividad_pct or 0.0

            return {
                "fecha": hoy.strftime("%d/%m/%Y"),
                "actividad_activa": activa.nombre if activa else None,
                "actividad_activa_id": activa.id if activa else None,
                "total_actividades_hoy": len(actividades),
                "actividades_pendientes": [
                    a.nombre
                    for a in actividades
                    if a.estado
                    in (
                        EstadoActividad.PENDIENTE.value,
                        EstadoActividad.PAUSADA.value,
                        EstadoActividad.BLOQUEADA.value,
                    )
                ],
                "actividades_completadas": [
                    a.nombre
                    for a in actividades
                    if a.estado == EstadoActividad.COMPLETADA.value
                ],
                "tiempo_trabajado_horas": round(tiempo_trabajado_seg / 3600.0, 1),
                "porcentaje_productividad": round(porcentaje_prod, 1),
                "total_planeadas_semana": len(items_planeacion),
                "items_semana": [it.nombre for it in items_planeacion[:8]],
            }

    # ------------------------------------------------------------------
    # Motor de Intenciones Directas y Herramientas (Capa 1: Ultra Rápida)
    # ------------------------------------------------------------------

    def procesar_intencion_directa(self, mensaje_usuario: str) -> RespuestaUtilin | None:
        """Clasifica y ejecuta órdenes directas y guardrails en <10 ms sin esperar inferencia del LLM."""
        msg = mensaje_usuario.strip()
        msg_limpio = re.sub(r"[¿?¡!;:\"]", "", msg.lower()).strip()

        # ==============================================================
        # GUARDRAILS DE SEGURIDAD (LO QUE UTILÍN NO PUEDE HACER)
        # ==============================================================

        # GUARDRAIL 1: Bloqueo de acciones destructivas (borrado de datos / historial / BD / archivos)
        if re.search(
            r"\b(?:borra(?:r)?|elimina(?:r)?|destru(?:ir)?|purgar|limpia(?:r)?|formatea(?:r)?)\s+"
            r"(?:todas?\s+|mis?\s+|los?\s+|las?\s+|el\s+|la\s+)*"
            r"(?:base de datos|registros?|horas?|jornadas?|actividades?|historial|tiempos?|archivos?|disco)\b",
            msg_limpio,
        ):
            return RespuestaUtilin(
                mensaje=(
                    "🛡️🔒 Como Utilín y copiloto de Gente Útil, por políticas de seguridad estrictas "
                    "no puedo borrar ni alterar destructivamente registros de tiempo, actividades pasadas "
                    "ni la base de datos. Tus registros son inmutables y están protegidos para asegurar "
                    "la transparencia laboral y la trazabilidad de tu jornada. ¿Deseas pausar, finalizar o registrar una nueva tarea?"
                ),
                accion_ejecutada="BLOQUEO_SEGURIDAD",
                modelo_usado="guardrail",
            )

        # GUARDRAIL 2: Bloqueo de solicitud de contraseñas, claves, PINs o credenciales
        if re.search(r"\b(?:contraseñas?|claves?|passwords?|pin(?:es)?|credenciales?|tarjetas?|tokens?)\b", msg_limpio) and \
           re.search(r"\b(?:dame|dime|cu[aá]l es|revela|mostrar|ver|ens[eé][ñn]ame|sacar|obtener|hackea|roba)\b", msg_limpio):
            return RespuestaUtilin(
                mensaje=(
                    "🔐✨ Por estrictas políticas de privacidad y seguridad digital, no tengo acceso a contraseñas, "
                    "PINs de seguridad ni credenciales privadas, ni puedo revelarlas. ¡Tu seguridad siempre es lo primero! "
                    "¿Hay alguna tarea, duda o cálculo en el que pueda apoyarte hoy?"
                ),
                accion_ejecutada="BLOQUEO_SEGURIDAD",
                modelo_usado="guardrail",
            )

        # GUARDRAIL 3: Bloqueo de envíos autónomos o compras no supervisadas
        if re.search(r"\b(?:env[ií]a(?:r)?\s+(?:correos?|emails?|mensajes?)\s+(?:masivos?|solo|autom[aá]tico)|compra(?:r)?\s+(?:en|por)\s+(?:amazon|mercado\s*libre))\b", msg_limpio):
            return RespuestaUtilin(
                mensaje=(
                    "✉️✨ No realizo envíos masivos ni transacciones de forma 100% autónoma sin supervisión humana. "
                    "Lo que sí puedo hacer con mucho gusto es redactarte el borrador perfecto para que tú lo revises y envíes con un clic."
                ),
                accion_ejecutada="BLOQUEO_SEGURIDAD",
                modelo_usado="guardrail",
            )

        # 1. Navegación de Pantallas de la App en lenguaje natural
        # Ejemplos: "puedes abrir los reportes?", "ábreme la planeación por favor", "quiero ver las estadísticas", "vamos a hoy"
        m_pantalla = re.search(
            r"\b(?:abre|abrir|[aá]breme|puedes abrir|me abres|ll[eé]vame a|ir a|vamos a|mostrar|mu[eé]strame|ver|pasar a)\s+"
            r"(?:los\s+|la\s+|el\s+)?(?:pantalla\s+(?:de\s+)?|secci[oó]n\s+(?:de\s+)?|pesta[ñn]a\s+(?:de\s+)?)?"
            r"(reportes?|planeaci[oó]n|historial|estad[ií]sticas?|m[eé]tricas?|cron[oó]metro|hoy|configuraci[oó]n|ajustes|planear|cierre|actividad extra)\b",
            msg_limpio,
        )
        if m_pantalla:
            return self._accion_abrir_pantalla(m_pantalla.group(1))

        if msg_limpio in ("reportes", "planeacion", "planeación", "historial", "estadisticas", "estadísticas", "configuracion", "configuración"):
            return self._accion_abrir_pantalla(msg_limpio)

        # 2. Abrir o restaurar la Ventana Principal
        if re.search(r"\b(?:abre la app|[aá]breme la app|abrir la app|mostrar app|abre el programa|restaurar|maximizar|muestra la ventana|abrir ventana|abre ventana|abrir aplicaci[oó]n|abre la aplicaci[oó]n)\b", msg_limpio):
            return self._accion_abrir_app()

        # 3. Alternar Mini Widget Flotante
        if re.search(r"\b(?:mini widget|mini ventana|widget flotante|abrir mini|ocultar mini|pasa a mini|modo mini)\b", msg_limpio):
            return self._accion_alternar_mini()

        # 4. Pausar actividad en curso (muy flexible en lenguaje natural)
        # Ejemplos: "pausar", "voy a almorzar", "salgo a comer", "para el tiempo", "ponle pausa", "un cafecito", "un break"
        if re.search(
            r"\b(?:pausar|pausa|pa[uú]salo|pa[uú]same|ponle pausa|poner en pausa|pon en pausa|"
            r"almorzar|almuerzo|a almorzar|comer algo|a comer|voy a comer|voy a almorzar|desayunar|cenar|"
            r"un tinto|un caf[eé]|un cafecito|al ba[ñn]o|un break|un descanso|receso|pausate|paro|parar|"
            r"para el tiempo|pausa el tiempo|pausa el reloj|para el reloj|det[eé]n el tiempo|det[eé]n el cron[oó]metro|"
            r"detener el tiempo|detener el reloj)\b",
            msg_limpio,
        ):
            return self._accion_pausar_tarea()

        # 5. Finalizar actividad en curso
        # Ejemplos: "finalizar", "ya terminé", "ya acabé", "terminamos", "dar por terminada", "listo acabé", "cerrar tarea"
        if re.search(
            r"\b(?:finalizar|finaliza|final[ií]zala|terminar|termina|termin[eé]|ya termin[eé]|ya acab[eé]|acab[eé]|"
            r"completar|completada|dar por terminada|dar por finalizada|cerrar tarea|cerrar la tarea|listo|acabamos|terminamos)\b",
            msg_limpio,
        ):
            return self._accion_finalizar_tarea()

        # 6. Iniciar / Reanudar Tarea (con cronómetro)
        # Ejemplos: "quiero empezar a trabajar en la nómina", "vamos a diseñar el flyer", "iníciame selección", "arranca reunión"
        m_iniciar = re.search(
            r"\b(?:quiero\s+(?:empezar|iniciar|comenzar|ponerme a)|"
            r"voy a\s+(?:empezar|iniciar|comenzar|ponerme a)|"
            r"vamos a\s+(?:empezar|iniciar|comenzar)|"
            r"empecemos\s+(?:con|a)?|ponme a|iniciar|inicia|in[ií]ciame|arranca(?:r)?|arr[aá]ncame|"
            r"empieza|empezar|a trabajar en|trabajar en|reanudar|reanuda|seguir con|sigue con|cronometra(?:r)?)\s+"
            r"(?:la\s+tarea\s+(?:de\s+)?|el\s+trabajo\s+(?:de\s+)?|a\s+trabajar\s+en\s+|en\s+|a\s+|con\s+)?"
            r"(.+)",
            msg,
            re.IGNORECASE,
        )
        if m_iniciar:
            nombre_tarea = m_iniciar.group(1).strip()
            nombre_tarea = re.sub(r"\b(?:por\s+favor|porfa|gracias)\b", "", nombre_tarea, flags=re.IGNORECASE).strip()
            if nombre_tarea and len(nombre_tarea) > 1:
                return self._accion_iniciar_tarea(nombre_tarea)

        # Acciones directas como "vamos a diseñar el flyer", "voy a redactar un contrato"
        m_accion_directa = re.search(
            r"\b(?:voy a|vamos a|quiero)\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ0-9]+){1,6})\b",
            msg,
            re.IGNORECASE,
        )
        if m_accion_directa:
            candidata = m_accion_directa.group(1).strip()
            if not any(kw in candidata.lower() for kw in ["almorzar", "comer", "salir", "abrir", "reportes", "planeacion", "whatsapp", "calculadora", "ver"]):
                candidata = re.sub(r"\b(?:por\s+favor|porfa|gracias)\b", "", candidata, flags=re.IGNORECASE).strip()
                if len(candidata.split()) >= 2:
                    return self._accion_iniciar_tarea(candidata)

        # 7. Herramientas del Sistema / Externas
        # 7.1 WhatsApp Web
        if re.search(r"\b(?:whatsapp|wasap|wpp)\b", msg_limpio):
            return self._accion_abrir_herramienta("whatsapp")

        # 7.2 Calculadora de Windows
        if re.search(r"\b(?:calculadora|calc)\b", msg_limpio) and not re.search(r"\b(?:cu[aá]nto|resuelve|\d+)\b", msg_limpio):
            return self._accion_abrir_herramienta("calculadora")

        # 7.3 Bloc de notas
        if re.search(r"\b(?:bloc de notas|notepad|abrir notas|tomar nota)\b", msg_limpio):
            return self._accion_abrir_herramienta("bloc_notas")

        # 7.4 Carpeta de reportes / descargas
        if re.search(r"\b(?:carpeta de reportes|mis reportes|carpeta de descargas|mis archivos|abrir descargas|mis pdfs|d[oó]nde est[aá]n mis reportes|d[oó]nde se guardan los reportes)\b", msg_limpio):
            return self._accion_abrir_herramienta("carpeta_reportes")

        # 7.5 Búsqueda en Google
        m_google = re.search(r"^(?:busca(?:r)? en google|googlea|buscar|busca)\s+(.+)$", msg_limpio)
        if m_google:
            query = m_google.group(1).strip()
            if query not in ("en google", "google"):
                return self._accion_abrir_herramienta("google", argumento=query)
        if msg_limpio in ("abre google", "abrir google", "google"):
            return self._accion_abrir_herramienta("google", argumento="")

        # 7.6 Correo Web (Gmail / Outlook)
        if re.search(r"\b(?:abre|abrir|ir a)\s+(?:mi\s+)?(?:gmail|correo|email|outlook)\b", msg_limpio) or msg_limpio in ("gmail", "correo", "outlook"):
            if "outlook" in msg_limpio:
                return self._accion_abrir_herramienta("outlook")
            return self._accion_abrir_herramienta("gmail")

        # 7.7 Calendario
        if re.search(r"\b(?:abre|abrir|ir a)\s+(?:el\s+)?calendario\b", msg_limpio) or msg_limpio in ("calendario", "calendar"):
            return self._accion_abrir_herramienta("calendar")

        # 7.8 CompuTrabajo
        if re.search(r"\b(?:abre|abrir|ir a)\s+computrabajo\b", msg_limpio) or msg_limpio == "computrabajo":
            return self._accion_abrir_herramienta("computrabajo")

        # 7.9 Enlaces conocidos (Canva, LinkedIn, YouTube)
        m_enlace = re.search(r"\b(?:abre|abrir|ir a)\s+(canva|linkedin|youtube)\b", msg_limpio)
        if m_enlace:
            return self._accion_abrir_herramienta(m_enlace.group(1))

        # 8. Cálculo Matemático Rápido y Seguro
        m_calc = re.search(r"(?:cu[aá]nto es|calcula(?:r)?|cu[aá]nto da|resuelve)\s+([\d\s\+\-\*\/\^\(\)\.\,\%]+)", msg_limpio)
        if m_calc:
            return self._accion_calcular(m_calc.group(1))

        if re.match(r"^\s*[\d\.\,]+\s*[\+\-\*\/]\s*[\d\.\,]+", msg_limpio):
            return self._accion_calcular(msg_limpio)

        # 9. Crear Tarea Pendiente
        m_crear = re.search(
            r"\b(?:agrega(?:r)?|anota(?:r)?|crea(?:r)?|a[ñn]adir?|nueva tarea|nuevo pendiente)\s+(?:la\s+tarea\s+|una\s+tarea\s+|el\s+pendiente\s+|pendiente\s+)?(.+)",
            msg,
            re.IGNORECASE,
        )
        if m_crear:
            tarea = re.sub(r"\b(?:por\s+favor|porfa|gracias)\b", "", m_crear.group(1), flags=re.IGNORECASE).strip()
            if tarea:
                return self._accion_crear_tarea(tarea)

        # 10. Recordatorio Rápido
        m_rec = re.search(
            r"\b(?:recu[eé]rdame|recordatorio|anota recordatorio|ponme recordatorio)\s+(.+)",
            msg,
            re.IGNORECASE,
        )
        if m_rec:
            return self._accion_crear_recordatorio(m_rec.group(1))

        # 11. Consultar tareas pendientes de hoy
        if any(kw in msg_limpio for kw in ["que tengo", "qué tengo", "mis tareas", "pendientes", "que hay para hoy", "qué hay para hoy", "tareas de hoy", "tareas para hoy", "que hago", "qué hago", "que estoy haciendo", "qué estoy haciendo", "cual es mi tarea", "cuál es mi tarea"]):
            return self._accion_consultar_hoy()

        # 12. Consultar resumen de productividad y tiempo
        if any(kw in msg_limpio for kw in ["como voy", "cómo voy", "resumen", "productividad", "cuanto tiempo", "cuánto tiempo", "tiempo trabajado", "horas de hoy", "mi rendimiento", "cuantas horas llevo", "cuántas horas llevo"]):
            return self._accion_consultar_productividad()

        # 13. Consultar planeación semanal
        if any(kw in msg_limpio for kw in ["planeacion", "planeación", "tablero", "esta semana", "semana"]):
            return self._accion_consultar_planeacion()

        # 14. Ayuda y Capacidades
        if re.search(r"\b(?:qui[eé]n eres|qui[eé]n eres t[uú]|qu[eé] puedes hacer|qu[eé] sabes hacer|c[oó]mo funcionas|ayuda|para qu[eé] sirves)\b", msg_limpio):
            return self._accion_ayuda_capacidades()

        # 15. Saludos cordiales
        if re.search(r"^(?:hola|buenos d[ií]as|buenas tardes|buenas noches|hey|qu[eé] tal|c[oó]mo est[aá]s)\b", msg_limpio):
            ctx = self.obtener_resumen_contextual()
            act = ctx.get("actividad_activa")
            extra = f" Estás en: «{act}» ⏱️" if act else " ¿Qué tarea iniciamos hoy? 🚀"
            return RespuestaUtilin(
                mensaje=f"¡Hola! 👋 ¡Con toda la energía para tu jornada en Gente Útil!{extra}",
                modelo_usado="directo",
            )

        # 16. Agradecimiento y felicitación
        if re.search(r"\b(?:muchas gracias|gracias util[ií]n|gracias|te lo agradezco|un crack|genial|excelente|perfecto)\b", msg_limpio):
            return RespuestaUtilin(
                mensaje="¡Con el mayor de los gustos! Siempre listo para apoyarte en lo que necesites. ✨🙌",
                modelo_usado="directo",
            )

        return None

    def _accion_ayuda_capacidades(self) -> RespuestaUtilin:
        return RespuestaUtilin(
            mensaje=(
                "¡Soy Utilín, tu copiloto de IA en Gente Útil! 🤖✨\n\n"
                "🛡️ LO QUE NO PUEDO HACER (Líneas rojas y seguridad):\n"
                "• ❌ Borrar actividades, eliminar tiempos o alterar la base de datos (tus registros son inmutables y sagrados para trazabilidad laboral).\n"
                "• ❌ Acceder, pedir o revelar contraseñas, PINs de seguridad ni claves financieras.\n"
                "• ❌ Enviar correos masivos o hacer compras/pagos de forma autónoma (te genero borradores listos para que los revises).\n"
                "• ❌ Inventar horas trabajadas o falsear métricas de productividad.\n\n"
                "🚀 LO QUE SÍ PUEDO HACER (Libertad total como copiloto):\n"
                "• 💡 Responder dudas externas: Fórmulas de Excel (BUSCARX, SUMAR.SI), leyes laborales colombianas, redacción de correos formales y vacantes.\n"
                "• ⏱️ Manejar la app: Iniciar, pausar y terminar tareas, reportes PDF, planeación, estadísticas e historial.\n"
                "• 🛠️ Abrir herramientas: Calculadora, Bloc de notas, WhatsApp Web, Gmail, Outlook, Calendar, CompuTrabajo, Canva, Google.\n"
                "• 🧮 Resolver cálculos matemáticos y conversar amigablemente sobre productividad."
            ),
            modelo_usado="directo",
        )

    # ------------------------------------------------------------------
    # Implementación de Acciones Concretas
    # ------------------------------------------------------------------

    def _accion_iniciar_tarea(self, nombre_tarea: str) -> RespuestaUtilin:
        with self.bd.sesion() as s:
            hoy = date.today()
            jornada = s.query(Jornada).filter(Jornada.fecha == hoy).first()
            if not jornada:
                jornada = Jornada(fecha=hoy)
                s.add(jornada)
                s.flush()

            act = (
                s.query(Actividad)
                .filter(
                    Actividad.jornada_id == jornada.id,
                    Actividad.nombre.ilike(f"%{nombre_tarea}%"),
                    Actividad.estado != EstadoActividad.COMPLETADA.value,
                )
                .first()
            )

            srv_cron = ServicioCronometro(s)
            if act:
                srv_cron.iniciar(act)
                s.commit()
                msg = f"¡De una! He reanudado el cronómetro de «{act.nombre}». ¡A darle con toda! ⏱️"
            else:
                srv_act = ServicioActividades(s)
                nueva_act = srv_act.crear_no_planeada(
                    nombre=nombre_tarea.strip().capitalize(),
                    jornada=jornada,
                    descripcion="Iniciada por Utilín IA",
                )
                srv_cron.iniciar(nueva_act)
                s.commit()
                msg = f"¡Listo! Creé e inicié el cronómetro para «{nombre_tarea.strip().capitalize()}». ¡Mucho éxito! 🚀"

        if self.callback_notificar_cambio:
            self.callback_notificar_cambio()

        return RespuestaUtilin(
            mensaje=msg,
            accion_ejecutada="INICIAR_ACTIVIDAD",
            datos_accion={"tarea": nombre_tarea},
            modelo_usado="directo",
        )

    def _accion_pausar_tarea(self) -> RespuestaUtilin:
        with self.bd.sesion() as s:
            hoy = date.today()
            jornada = s.query(Jornada).filter(Jornada.fecha == hoy).first()
            if not jornada:
                return RespuestaUtilin(mensaje="No tienes ninguna jornada activa hoy. 🤖", modelo_usado="directo")

            activa = (
                s.query(Actividad)
                .filter(Actividad.jornada_id == jornada.id, Actividad.estado == EstadoActividad.EN_CURSO.value)
                .first()
            )
            if not activa:
                return RespuestaUtilin(mensaje="No tienes ninguna actividad corriendo en este momento. ☕", modelo_usado="directo")

            srv_cron = ServicioCronometro(s)
            srv_cron.pausar(activa, motivo="Pausada desde Utilín IA")
            s.commit()
            nombre = activa.nombre

        if self.callback_notificar_cambio:
            self.callback_notificar_cambio()

        return RespuestaUtilin(
            mensaje=f"He puesto en pausa «{nombre}». ¡Tómate un respiro y avísame cuando sigas! ⏸️",
            accion_ejecutada="PAUSAR_ACTIVIDAD",
            modelo_usado="directo",
        )

    def _accion_finalizar_tarea(self) -> RespuestaUtilin:
        with self.bd.sesion() as s:
            hoy = date.today()
            jornada = s.query(Jornada).filter(Jornada.fecha == hoy).first()
            if not jornada:
                return RespuestaUtilin(mensaje="No hay jornada abierta hoy. 🤖", modelo_usado="directo")

            activa = (
                s.query(Actividad)
                .filter(Actividad.jornada_id == jornada.id, Actividad.estado == EstadoActividad.EN_CURSO.value)
                .first()
            )
            if not activa:
                return RespuestaUtilin(mensaje="No tienes ninguna tarea en curso para finalizar. ¿Quieres empezar una nueva? ✨", modelo_usado="directo")

            srv_cron = ServicioCronometro(s)
            srv_cron.detener(activa)
            s.commit()
            nombre = activa.nombre

        if self.callback_notificar_cambio:
            self.callback_notificar_cambio()

        return RespuestaUtilin(
            mensaje=f"¡Excelente trabajo! 👏 «{nombre}» quedó registrada como finalizada. ¿Qué sigue en tu lista? 🎯",
            accion_ejecutada="FINALIZAR_ACTIVIDAD",
            modelo_usado="directo",
        )

    def _accion_abrir_pantalla(self, nombre_pantalla: str) -> RespuestaUtilin:
        p = nombre_pantalla.strip().lower()
        mapa_nombres = {
            "reportes": "Reportes PDF 📄",
            "planeacion": "Planeación Semanal 📅",
            "historial": "Historial de Actividades 📜",
            "estadisticas": "Estadísticas y Métricas 📊",
            "hoy": "Hoy · Cronómetro ⏱️",
            "configuracion": "Configuración del Sistema ⚙️",
            "planear": "Planear el Día 📋",
            "extra": "Actividad Extra ⚡",
            "cierre": "Cierre de Jornada 🏁",
        }
        pantalla_norm = p
        if p in ("reporte", "reportes"):
            pantalla_norm = "reportes"
        elif p in ("planeacion", "planeación", "semana"):
            pantalla_norm = "planeacion"
        elif p in ("historial", "historico", "histórico"):
            pantalla_norm = "historial"
        elif p in ("estadisticas", "estadísticas", "metricas", "métricas"):
            pantalla_norm = "estadisticas"
        elif p in ("hoy", "cronometro", "cronómetro", "principal"):
            pantalla_norm = "hoy"
        elif p in ("configuracion", "configuración", "config", "ajustes"):
            pantalla_norm = "configuracion"
        elif p in ("planear", "plan"):
            pantalla_norm = "planear"
        elif p in ("extra", "actividad extra", "nueva_actividad"):
            pantalla_norm = "extra"
        elif p in ("cierre", "cerrar_jornada"):
            pantalla_norm = "cierre"

        exito = False
        if self.callback_navegar:
            exito = self.callback_navegar(pantalla_norm)

        etiqueta = mapa_nombres.get(pantalla_norm, pantalla_norm.capitalize())
        if exito:
            msg = f"¡Listo! Te he abierto la sección de {etiqueta}. 🚀"
        else:
            msg = f"Accediendo a {etiqueta}. Si la ventana está minimizada, ábrela desde el botón 'Abrir app'. 💻"

        return RespuestaUtilin(
            mensaje=msg,
            accion_ejecutada="ABRIR_PANTALLA",
            datos_accion={"pantalla": pantalla_norm},
            modelo_usado="directo",
        )

    def _accion_abrir_app(self) -> RespuestaUtilin:
        if self.callback_abrir_app:
            self.callback_abrir_app()
        return RespuestaUtilin(
            mensaje="¡Aquí tienes la aplicación en pantalla! 💻✨",
            accion_ejecutada="ABRIR_APP",
            modelo_usado="directo",
        )

    def _accion_alternar_mini(self) -> RespuestaUtilin:
        if self.callback_alternar_mini:
            self.callback_alternar_mini()
        return RespuestaUtilin(
            mensaje="¡He alternado la mini-ventana flotante de cronómetro! ⏱️",
            accion_ejecutada="MINI_VENTANA",
            modelo_usado="directo",
        )

    def _accion_abrir_herramienta(self, herramienta: str, argumento: str = "") -> RespuestaUtilin:
        herramienta = herramienta.lower().strip()
        msg = ""
        datos = {"herramienta": herramienta, "argumento": argumento}

        if herramienta in ("whatsapp", "wpp", "wasap"):
            webbrowser.open("https://web.whatsapp.com")
            msg = "¡Abriendo WhatsApp Web en tu navegador! 💬📱"
        elif herramienta in ("calculadora", "calc"):
            if os.name == "nt":
                subprocess.Popen("calc.exe", shell=True)
            else:
                subprocess.Popen(["gnome-calculator"], shell=False)
            msg = "¡Abriendo la calculadora de Windows! 🧮✨"
        elif herramienta in ("bloc_notas", "notepad", "notas"):
            if os.name == "nt":
                subprocess.Popen("notepad.exe", shell=True)
            else:
                subprocess.Popen(["gedit"], shell=False)
            msg = "¡Abriendo el Bloc de notas! 📝"
        elif herramienta in ("carpeta_reportes", "reportes_carpeta", "descargas", "archivos"):
            try:
                ruta_exp = rutas.carpeta_exportaciones()
                ruta_exp.mkdir(parents=True, exist_ok=True)
                if os.name == "nt":
                    os.startfile(str(ruta_exp))
                else:
                    subprocess.Popen(["xdg-open", str(ruta_exp)])
                msg = "¡Abriendo tu carpeta de reportes y exportaciones! 📁"
            except Exception as e:
                msg = f"No pude abrir la carpeta: {e} 📂"
        elif herramienta in ("google", "buscar"):
            query = argumento or "Gente Util Colombia"
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            webbrowser.open(url)
            msg = f"¡Buscando «{query}» en Google! 🔍🌐"
        elif herramienta == "canva":
            webbrowser.open("https://www.canva.com")
            msg = "¡Abriendo Canva en tu navegador! 🎨✨"
        elif herramienta == "linkedin":
            webbrowser.open("https://www.linkedin.com")
            msg = "¡Abriendo LinkedIn en tu navegador! 💼🌐"
        elif herramienta == "youtube":
            webbrowser.open("https://www.youtube.com")
            msg = "¡Abriendo YouTube! 🎬"
        elif herramienta in ("gmail", "correo", "email"):
            webbrowser.open("https://mail.google.com")
            msg = "¡Abriendo Gmail en tu navegador! ✉️📬"
        elif herramienta in ("outlook", "hotmail"):
            webbrowser.open("https://outlook.office.com")
            msg = "¡Abriendo Microsoft Outlook en tu navegador! 📧💼"
        elif herramienta in ("calendar", "calendario"):
            webbrowser.open("https://calendar.google.com")
            msg = "¡Abriendo Google Calendar en tu navegador! 📅✨"
        elif herramienta in ("computrabajo",):
            webbrowser.open("https://co.computrabajo.com")
            msg = "¡Abriendo CompuTrabajo Colombia en tu navegador! 💼🔍"
        elif herramienta == "url" and argumento:
            url = argumento if argumento.startswith("http") else f"https://{argumento}"
            webbrowser.open(url)
            msg = f"¡Abriendo enlace {url}! 🌐"
        else:
            msg = f"No reconozco la herramienta «{herramienta}», pero estoy aprendiendo nuevas funciones. 🤖"

        return RespuestaUtilin(mensaje=msg, accion_ejecutada="ABRIR_HERRAMIENTA", datos_accion=datos, modelo_usado="directo")

    def _accion_calcular(self, expresion: str) -> RespuestaUtilin:
        try:
            res = calcular_aritmetica_segura(expresion)
            if isinstance(res, float):
                if res.is_integer():
                    res_str = f"{int(res):,}".replace(",", ".")
                else:
                    res_str = f"{res:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
            else:
                res_str = f"{res:,}".replace(",", ".")
            return RespuestaUtilin(
                mensaje=f"El resultado de {expresion.strip()} es {res_str}. 🧮✨",
                accion_ejecutada="CALCULAR",
                datos_accion={"expresion": expresion, "resultado": res},
                modelo_usado="directo",
            )
        except Exception as e:
            return RespuestaUtilin(
                mensaje=f"No pude calcular «{expresion}»: {e}. Prueba con operaciones como + - * /. 🤖",
                modelo_usado="directo",
            )

    def _accion_crear_tarea(self, nombre_tarea: str) -> RespuestaUtilin:
        with self.bd.sesion() as s:
            hoy = date.today()
            jornada = s.query(Jornada).filter(Jornada.fecha == hoy).first()
            if not jornada:
                jornada = Jornada(fecha=hoy)
                s.add(jornada)
                s.flush()

            srv_act = ServicioActividades(s)
            nueva = srv_act.crear_no_planeada(
                nombre=nombre_tarea.strip().capitalize(),
                jornada=jornada,
                descripcion="Creada por Utilín IA",
            )
            nueva.estado = EstadoActividad.PENDIENTE.value
            s.commit()

        if self.callback_notificar_cambio:
            self.callback_notificar_cambio()

        return RespuestaUtilin(
            mensaje=f"¡Anotado! Agregué «{nombre_tarea.strip().capitalize()}» a tus tareas de hoy. 📋✅",
            accion_ejecutada="CREAR_TAREA",
            datos_accion={"tarea": nombre_tarea},
            modelo_usado="directo",
        )

    def _accion_crear_recordatorio(self, texto: str) -> RespuestaUtilin:
        item = {"texto": texto.strip(), "hora": ahora().strftime("%H:%M")}
        self.recordatorios_rapidos.append(item)
        return RespuestaUtilin(
            mensaje=f"¡Listo! Guardé tu recordatorio: «{texto.strip()}». 🔔📌",
            accion_ejecutada="CREAR_RECORDATORIO",
            datos_accion=item,
            modelo_usado="directo",
        )

    def _accion_consultar_hoy(self) -> RespuestaUtilin:
        ctx = self.obtener_resumen_contextual()
        pendientes = ctx.get("actividades_pendientes", [])
        activa = ctx.get("actividad_activa")

        partes = []
        if activa:
            partes.append(f"Ahora mismo estás en: «{activa}» ⏱️.")
        else:
            partes.append("No tienes tarea corriendo ahora mismo.")

        if pendientes:
            cant = len(pendientes)
            primeras = ", ".join(f"«{p}»" for p in pendientes[:3])
            mas = f" y {cant - 3} más" if cant > 3 else ""
            partes.append(f"Tienes {cant} pendiente(s): {primeras}{mas}.")
        else:
            partes.append("¡No tienes tareas pendientes para hoy! 🎉")

        return RespuestaUtilin(mensaje=" ".join(partes), accion_ejecutada="CONSULTAR_HOY", modelo_usado="directo")

    def _accion_consultar_productividad(self) -> RespuestaUtilin:
        ctx = self.obtener_resumen_contextual()
        horas = ctx.get("tiempo_trabajado_horas", 0.0)
        prod = ctx.get("porcentaje_productividad", 0.0)

        calif = "¡Vas a un ritmo impresionante!" if prod >= 85 else "¡Vas con buen avance, sigue así!"
        msg = f"Hoy llevas {horas} horas trabajadas con un {prod}% de productividad. {calif} 💼🔥"
        return RespuestaUtilin(mensaje=msg, accion_ejecutada="CONSULTAR_PRODUCTIVIDAD", modelo_usado="directo")

    def _accion_consultar_planeacion(self) -> RespuestaUtilin:
        ctx = self.obtener_resumen_contextual()
        total_sem = ctx.get("total_planeadas_semana", 0)
        items = ctx.get("items_semana", [])

        if total_sem == 0:
            return RespuestaUtilin(mensaje="El tablero semanal aún no tiene tareas registradas. Puedes crearlas en la sección de Planeación 📋", modelo_usado="directo")

        resumen_items = ", ".join(f"«{it}»" for it in items[:4])
        mas = f" (+{total_sem - 4} más)" if total_sem > 4 else ""
        return RespuestaUtilin(
            mensaje=f"En la planeación de esta semana hay {total_sem} actividades: {resumen_items}{mas}. ¡Organización al 100%! 📅",
            accion_ejecutada="CONSULTAR_PLANEACION",
            modelo_usado="directo",
        )

    # ------------------------------------------------------------------
    # Ejecutor de Acciones Detectadas por LLM
    # ------------------------------------------------------------------

    def _ejecutar_accion_parseada(self, tipo_accion: str, parametro: str = "") -> tuple[str | None, str, dict[str, Any] | None]:
        """Ejecuta una acción estructurada devuelta por el modelo LLM."""
        tipo = tipo_accion.upper().strip()
        p = parametro.strip()

        if tipo == "INICIAR_ACTIVIDAD":
            res = self._accion_iniciar_tarea(p or "Nueva Actividad")
            return res.accion_ejecutada, res.mensaje, res.datos_accion
        if tipo == "PAUSAR_ACTIVIDAD":
            res = self._accion_pausar_tarea()
            return res.accion_ejecutada, res.mensaje, res.datos_accion
        if tipo == "FINALIZAR_ACTIVIDAD":
            res = self._accion_finalizar_tarea()
            return res.accion_ejecutada, res.mensaje, res.datos_accion
        if tipo == "ABRIR_PANTALLA":
            res = self._accion_abrir_pantalla(p or "hoy")
            return res.accion_ejecutada, res.mensaje, res.datos_accion
        if tipo == "ABRIR_HERRAMIENTA":
            res = self._accion_abrir_herramienta(p or "whatsapp")
            return res.accion_ejecutada, res.mensaje, res.datos_accion
        if tipo == "CREAR_TAREA":
            res = self._accion_crear_tarea(p or "Tarea pendiente")
            return res.accion_ejecutada, res.mensaje, res.datos_accion
        if tipo == "CONSULTAR_HOY":
            res = self._accion_consultar_hoy()
            return res.accion_ejecutada, res.mensaje, res.datos_accion
        if tipo == "CONSULTAR_PRODUCTIVIDAD":
            res = self._accion_consultar_productividad()
            return res.accion_ejecutada, res.mensaje, res.datos_accion
        if tipo == "CONSULTAR_PLANEACION":
            res = self._accion_consultar_planeacion()
            return res.accion_ejecutada, res.mensaje, res.datos_accion

        return None, "", None

    # ------------------------------------------------------------------
    # Consulta a LLM (Ollama / Gemma o Google Gemini)
    # ------------------------------------------------------------------

    def consultar(self, mensaje_usuario: str) -> RespuestaUtilin:
        """Punto de entrada principal para interactuar con Utilín."""
        # 1. Probar primero si es una orden directa en lenguaje natural (Capa 1: <10 ms)
        res_directa = self.procesar_intencion_directa(mensaje_usuario)
        if res_directa:
            self._registrar_en_historial(mensaje_usuario, res_directa.mensaje)
            return res_directa

        ctx = self.obtener_resumen_contextual()
        contexto_str = (
            f"Contexto actual del usuario en Gente Útil:\n"
            f"- Fecha: {ctx['fecha']}\n"
            f"- Tarea en curso: {ctx['actividad_activa'] or 'Ninguna'}\n"
            f"- Tareas pendientes hoy: {', '.join(ctx['actividades_pendientes']) or 'Ninguna'}\n"
            f"- Horas trabajadas hoy: {ctx['tiempo_trabajado_horas']} h (Productividad: {ctx['porcentaje_productividad']}%)\n"
        )

        instruccion_herramientas = (
            "Si el usuario te da una orden o pide realizar una acción en la app o PC, incluye al inicio de tu respuesta:\n"
            "- [ACCION:INICIAR_ACTIVIDAD:nombre_tarea]\n"
            "- [ACCION:PAUSAR_ACTIVIDAD]\n"
            "- [ACCION:FINALIZAR_ACTIVIDAD]\n"
            "- [ACCION:ABRIR_PANTALLA:reportes|planeacion|historial|estadisticas|hoy|configuracion]\n"
            "- [ACCION:ABRIR_HERRAMIENTA:whatsapp|calculadora|bloc_notas|carpeta_reportes]\n"
            "- [ACCION:CREAR_TAREA:nombre_tarea]\n"
            "Si pide redactar copys de vacantes, mensajes o conversar, responde con calidad, profesionalismo y cercanía."
        )

        prompt_few_shots = (
            "Ejemplos de cómo debes responder si el usuario pide una acción:\n"
            "Usuario: \"puedes abrir los reportes?\"\n"
            "Utilín: [ACCION:ABRIR_PANTALLA:reportes] ¡Claro que sí! Abriendo tus reportes PDF. 📄✨\n\n"
            "Usuario: \"voy a salir a almorzar, pausa el reloj\"\n"
            "Utilín: [ACCION:PAUSAR_ACTIVIDAD] ¡Buen provecho! He pausado tu actividad en curso. 🍽️⏸️\n\n"
            "Usuario: \"quiero empezar a trabajar en la nómina\"\n"
            "Utilín: [ACCION:INICIAR_ACTIVIDAD:Nómina] ¡Listo! Cronómetro iniciado para la nómina. ⏱️🚀\n\n"
            "Usuario: \"ya terminé con esto\"\n"
            "Utilín: [ACCION:FINALIZAR_ACTIVIDAD] ¡Excelente trabajo! Tarea finalizada. 🎉✅\n\n"
            "Usuario: \"ábreme la planeación porfa\"\n"
            "Utilín: [ACCION:ABRIR_PANTALLA:planeacion] ¡De una! Abriendo tu planeación semanal. 📅✨\n\n"
            "Usuario: \"abre whatsapp que voy a escribirle a un candidato\"\n"
            "Utilín: [ACCION:ABRIR_HERRAMIENTA:whatsapp] ¡Abriendo WhatsApp Web! 💬📱\n"
        )

        historial_str = ""
        if self.historial_conversacion:
            bloques_h = []
            for h in self.historial_conversacion[-6:]:
                rol_str = "Usuario" if h["rol"] == "user" else "Utilín"
                bloques_h.append(f"{rol_str}: {h['texto']}")
            historial_str = "Historial reciente del chat:\n" + "\n".join(bloques_h) + "\n\n"

        prompt_completo = (
            f"{PROMPT_SISTEMA_UTILIN}\n\n"
            f"{contexto_str}\n\n"
            f"{instruccion_herramientas}\n\n"
            f"{prompt_few_shots}\n\n"
            f"{historial_str}"
            f"Usuario: \"{mensaje_usuario}\"\n"
            f"Utilín:"
        )

        # 2. Intentar con Ollama local (Gemma 2:2B)
        resp_ollama = self._consultar_ollama(prompt_completo)
        if resp_ollama:
            res_llm = self._procesar_salida_llm(resp_ollama, modelo=f"ollama:{self.modelo_ollama}")
            self._registrar_en_historial(mensaje_usuario, res_llm.mensaje)
            return res_llm

        # 3. Intentar con Gemini API si está configurada
        if self.api_key_gemini:
            resp_gemini = self._consultar_gemini(prompt_completo)
            if resp_gemini:
                res_gemini = self._procesar_salida_llm(resp_gemini, modelo=f"gemini:{self.modelo_gemini}")
                self._registrar_en_historial(mensaje_usuario, res_gemini.mensaje)
                return res_gemini

        # 4. Respuesta amigable de contingencia
        res_cont = RespuestaUtilin(
            mensaje=(
                "¡Hola! Te escucho con atención. Puedo iniciar o pausar tus tareas, abrir Reportes, "
                "Planeación, WhatsApp Web, Calculadora, redactar copys o resolver cálculos. ¿Qué necesitas hoy? 🤖✨"
            ),
            modelo_usado="contingencia",
        )
        self._registrar_en_historial(mensaje_usuario, res_cont.mensaje)
        return res_cont

    def _registrar_en_historial(self, mensaje_usuario: str, mensaje_utilin: str) -> None:
        """Almacena el turno en memoria conversacional (hasta 12 intercambios)."""
        self.historial_conversacion.append({"rol": "user", "texto": mensaje_usuario.strip()})
        self.historial_conversacion.append({"rol": "utilin", "texto": mensaje_utilin.strip()})
        if len(self.historial_conversacion) > 12:
            self.historial_conversacion = self.historial_conversacion[-12:]

    def limpiar_historial(self) -> None:
        """Reinicia la memoria conversacional de Utilín."""
        self.historial_conversacion.clear()

    def _procesar_salida_llm(self, texto_llm: str, modelo: str) -> RespuestaUtilin:
        """Extrae posibles etiquetas de acción [ACCION:...] o JSON de la respuesta del LLM."""
        # 1. Buscar etiqueta [ACCION:TIPO:PARAM]
        m_tag = re.search(r"\[ACCION:([A-Z_]+)(?::([^\]]+))?\]", texto_llm)
        if m_tag:
            tipo = m_tag.group(1).strip()
            param = m_tag.group(2).strip() if m_tag.group(2) else ""
            acc_ej, msg_acc, datos = self._ejecutar_accion_parseada(tipo, param)

            # Limpiar etiqueta del texto
            texto_limpio = re.sub(r"\[ACCION:[^\]]+\]", "", texto_llm)
            texto_limpio = re.sub(r"\*\*\s*\*\*", "", texto_limpio).strip()

            if msg_acc and texto_limpio:
                mensaje_final = f"{msg_acc} {texto_limpio}"
            elif texto_limpio:
                mensaje_final = texto_limpio
            else:
                mensaje_final = msg_acc

            return RespuestaUtilin(
                mensaje=mensaje_final,
                accion_ejecutada=acc_ej,
                datos_accion=datos,
                modelo_usado=modelo,
            )

        # 2. Buscar bloque JSON {"accion": "..."}
        m_json = re.search(r'\{\s*"accion"\s*:\s*"([^"]+)"(?:,\s*"[^"]+"\s*:\s*"([^"]*)")?[^}]*\}', texto_llm, re.DOTALL)
        if m_json:
            try:
                bloque = re.search(r'\{[^{}]*"accion"[^{}]*\}', texto_llm, re.DOTALL)
                if bloque:
                    data = json.loads(bloque.group(0))
                    tipo = data.get("accion", "").strip()
                    param = data.get("tarea") or data.get("pantalla") or data.get("herramienta") or data.get("parametro") or ""
                    acc_ej, msg_acc, datos = self._ejecutar_accion_parseada(tipo, param)
                    texto_limpio = re.sub(r'\{[^{}]*"accion"[^{}]*\}', "", texto_llm, flags=re.DOTALL).strip()
                    if msg_acc and texto_limpio:
                        mensaje_final = f"{msg_acc} {texto_limpio}"
                    elif texto_limpio:
                        mensaje_final = texto_limpio
                    else:
                        mensaje_final = msg_acc
                    return RespuestaUtilin(
                        mensaje=mensaje_final,
                        accion_ejecutada=acc_ej,
                        datos_accion=datos,
                        modelo_usado=modelo,
                    )
            except Exception:
                pass

        # 3. Fallback inteligente: si el LLM prometió una acción en su texto pero omitió el tag
        texto_lower = texto_llm.lower()
        if re.search(r"\b(?:abriendo|te abro|vamos a abrir|accediendo a)\s+(?:la\s+secci[oó]n\s+de\s+|la\s+pantalla\s+de\s+)?reportes", texto_lower):
            acc_ej, msg_acc, datos = self._ejecutar_accion_parseada("ABRIR_PANTALLA", "reportes")
            return RespuestaUtilin(mensaje=texto_llm.strip(), accion_ejecutada=acc_ej, datos_accion=datos, modelo_usado=modelo)

        if re.search(r"\b(?:abriendo|te abro|vamos a abrir|accediendo a)\s+(?:la\s+secci[oó]n\s+de\s+|la\s+pantalla\s+de\s+)?planeaci[oó]n", texto_lower):
            acc_ej, msg_acc, datos = self._ejecutar_accion_parseada("ABRIR_PANTALLA", "planeacion")
            return RespuestaUtilin(mensaje=texto_llm.strip(), accion_ejecutada=acc_ej, datos_accion=datos, modelo_usado=modelo)

        if re.search(r"\b(?:abriendo|te abro|vamos a abrir|accediendo a)\s+(?:la\s+secci[oó]n\s+de\s+|la\s+pantalla\s+de\s+)?estad[ií]sticas", texto_lower):
            acc_ej, msg_acc, datos = self._ejecutar_accion_parseada("ABRIR_PANTALLA", "estadisticas")
            return RespuestaUtilin(mensaje=texto_llm.strip(), accion_ejecutada=acc_ej, datos_accion=datos, modelo_usado=modelo)

        if re.search(r"\b(?:abriendo|te abro|vamos a abrir|accediendo a)\s+(?:la\s+secci[oó]n\s+de\s+|la\s+pantalla\s+de\s+)?historial", texto_lower):
            acc_ej, msg_acc, datos = self._ejecutar_accion_parseada("ABRIR_PANTALLA", "historial")
            return RespuestaUtilin(mensaje=texto_llm.strip(), accion_ejecutada=acc_ej, datos_accion=datos, modelo_usado=modelo)

        if re.search(r"\b(?:abriendo|te abro|accediendo a)\s+(?:el\s+)?whatsapp", texto_lower):
            acc_ej, msg_acc, datos = self._ejecutar_accion_parseada("ABRIR_HERRAMIENTA", "whatsapp")
            return RespuestaUtilin(mensaje=texto_llm.strip(), accion_ejecutada=acc_ej, datos_accion=datos, modelo_usado=modelo)

        if re.search(r"\b(?:abriendo|te abro)\s+(?:la\s+)?calculadora", texto_lower):
            acc_ej, msg_acc, datos = self._ejecutar_accion_parseada("ABRIR_HERRAMIENTA", "calculadora")
            return RespuestaUtilin(mensaje=texto_llm.strip(), accion_ejecutada=acc_ej, datos_accion=datos, modelo_usado=modelo)

        if re.search(r"\b(?:abriendo|te abro)\s+(?:el\s+)?bloc de notas", texto_lower):
            acc_ej, msg_acc, datos = self._ejecutar_accion_parseada("ABRIR_HERRAMIENTA", "bloc_notas")
            return RespuestaUtilin(mensaje=texto_llm.strip(), accion_ejecutada=acc_ej, datos_accion=datos, modelo_usado=modelo)

        if re.search(r"\b(?:he pausado|actividad pausada|pausando la actividad|puesta en pausa)\b", texto_lower):
            acc_ej, msg_acc, datos = self._ejecutar_accion_parseada("PAUSAR_ACTIVIDAD", "")
            return RespuestaUtilin(mensaje=texto_llm.strip(), accion_ejecutada=acc_ej, datos_accion=datos, modelo_usado=modelo)

        if re.search(r"\b(?:tarea finalizada|actividad finalizada|he finalizado la tarea|completada con éxito)\b", texto_lower):
            acc_ej, msg_acc, datos = self._ejecutar_accion_parseada("FINALIZAR_ACTIVIDAD", "")
            return RespuestaUtilin(mensaje=texto_llm.strip(), accion_ejecutada=acc_ej, datos_accion=datos, modelo_usado=modelo)

        # 4. Respuesta conversacional o redacción directa
        return RespuestaUtilin(mensaje=texto_llm.strip(), modelo_usado=modelo)

    def _consultar_ollama(self, prompt: str) -> str | None:
        """Envía el prompt a Ollama local (`localhost:11434`) con timeout ampliado a 35s."""
        url = f"{self.endpoint_ollama}/api/generate"
        payload = {
            "model": self.modelo_ollama,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.55,
                "top_p": 0.9,
                "num_predict": 350,
            },
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "UtilinBot/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=35.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    res = data.get("response", "").strip()
                    if res:
                        return res
        except Exception as e:
            _logger.debug("Ollama local no respondió: %s", e)
        return None

    def _consultar_gemini(self, prompt: str) -> str | None:
        """Envía el prompt a Google Gemini API como alternativa cloud rápida."""
        if not self.api_key_gemini:
            return None
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.modelo_gemini}:generateContent?key={self.api_key_gemini}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.6, "maxOutputTokens": 500},
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    cands = data.get("candidates", [])
                    if cands:
                        parts = cands[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
        except Exception as e:
            _logger.debug("Error en Gemini API: %s", e)
        return None
