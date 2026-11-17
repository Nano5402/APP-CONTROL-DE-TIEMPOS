"""Servicio de Inteligencia Artificial para la mascota Utilín (Gente Útil).

Permite que Utilín actúe como un bot interactivo en el escritorio:
1. Conexión local con Ollama (Gemma 2: `gemma2:2b` o `gemma2:9b`).
2. Conexión opcional con Google Gemini / Gemma API (Google AI Studio).
3. Motor de intenciones directas para control de la aplicación:
   - Iniciar, pausar y finalizar actividades por voz/texto.
   - Consultar tareas pendientes del día.
   - Consultar el tablero de planeación semanal.
   - Obtener resumen de tiempo trabajado y productividad en tiempo real.
   - Responder dudas, consejos de trabajo, redacción de copys para flyers y bienestar.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from data.db import BaseDatos
from data.enums import EstadoActividad
from data.models import Actividad, ItemPlaneacion, Jornada
from data.tiempo import ahora
from services.actividades import ServicioActividades
from services.cronometro import ServicioCronometro
from services.planeacion import ServicioPlaneacion, inicio_semana
from services.productividad import ServicioProductividad

_logger = logging.getLogger(__name__)


@dataclass
class RespuestaUtilin:
    """Respuesta generada por Utilín para el usuario."""
    mensaje: str
    accion_ejecutada: str | None = None
    datos_accion: dict[str, Any] | None = None


PROMPT_SISTEMA_UTILIN = """Eres Utilín, la mascota oficial y asistente de inteligencia artificial de Gente Útil.
Trabajas directamente en la aplicación de escritorio 'Control de Tiempos'.
Tu personalidad es alegre, entusiasta, cercana, servicial y motivadora.
Tus respuestas deben ser CONCISAS y breves (máximo 2 a 3 oraciones cortas), porque se mostrarán en un globo de diálogo cómic en el escritorio.
Usa emojis amigables con moderación (🤖, ⏱️, 💼, ✨, 🚀, 👏).
Siempre estás dispuesto a ayudar al colaborador a cuidar su tiempo, organizar su semana y mantener un alto nivel de productividad sin agotarse.
"""


class ServicioUtilinIA:
    """Gestiona las interacciones de lenguaje natural y acciones de Utilín."""

    def __init__(
        self,
        bd: BaseDatos,
        *,
        endpoint_ollama: str = "http://localhost:11434",
        modelo_ollama: str = "gemma2:2b",
        api_key_gemini: str | None = None,
        modelo_gemini: str = "gemini-1.5-flash",
        callback_notificar_cambio: Callable[[], None] | None = None,
    ) -> None:
        self.bd = bd
        self.endpoint_ollama = endpoint_ollama.rstrip("/")
        self.modelo_ollama = modelo_ollama
        self.api_key_gemini = api_key_gemini
        self.modelo_gemini = modelo_gemini
        self.callback_notificar_cambio = callback_notificar_cambio

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
    # Procesamiento de intenciones directas (Acciones en la App)
    # ------------------------------------------------------------------

    def procesar_intencion_directa(self, mensaje_usuario: str) -> RespuestaUtilin | None:
        """Si el usuario pide una acción directa (iniciar, pausar, ver pendientes), la ejecuta al instante."""
        msg = mensaje_usuario.strip().lower()
        msg_limpio = re.sub(r"[¿?¡!,;:\.\"]", "", msg).strip()

        # 1. Iniciar actividad / flyer
        # Ejemplos: "iniciar flyer promocional", "comenzar diseño", "arrancar tarea reunion"
        m_iniciar = re.search(r"^(?:iniciar|comenzar|arranca(?:r)?|inicia)\s+(?:la\s+tarea\s+|el\s+)?(.+)$", msg_limpio)
        if m_iniciar:
            nombre_tarea = m_iniciar.group(1).strip()
            if nombre_tarea:
                return self._accion_iniciar_tarea(nombre_tarea)

        # 2. Pausar actividad en curso
        # Ejemplos: "pausar", "pausa", "voy a almorzar", "pon en pausa"
        if re.search(r"\b(?:pausar|pausa|poner en pausa|pon en pausa|paúsalo|pausalo)\b", msg_limpio):
            return self._accion_pausar_tarea()

        # 3. Finalizar actividad en curso
        # Ejemplos: "finalizar", "terminar", "terminé", "completar", "cerrar tarea"
        if re.search(r"\b(?:finalizar|terminar|terminé|termine|completar|completada|cerrar tarea|listo)\b", msg_limpio):
            return self._accion_finalizar_tarea()

        # 4. Consultar tareas pendientes de hoy
        # Ejemplos: "¿qué tengo hoy?", "mis tareas", "pendientes", "qué hay para hoy"
        if any(kw in msg_limpio for kw in ["que tengo", "qué tengo", "mis tareas", "pendientes", "que hay para hoy", "qué hay para hoy", "tareas de hoy", "tareas para hoy"]):
            return self._accion_consultar_hoy()

        # 5. Consultar resumen de productividad y tiempo
        # Ejemplos: "¿cómo voy?", "resumen", "productividad", "tiempo trabajado", "cuánto he trabajado"
        if any(kw in msg_limpio for kw in ["como voy", "cómo voy", "resumen", "productividad", "cuanto tiempo", "cuánto tiempo", "tiempo trabajado", "horas de hoy"]):
            return self._accion_consultar_productividad()

        # 6. Consultar planeación semanal
        # Ejemplos: "planeación", "planeacion", "semana", "qué tengo esta semana"
        if any(kw in msg_limpio for kw in ["planeacion", "planeación", "tablero", "esta semana", "semana"]):
            return self._accion_consultar_planeacion()

        return None

    def _accion_iniciar_tarea(self, nombre_tarea: str) -> RespuestaUtilin:
        with self.bd.sesion() as s:
            hoy = date.today()
            jornada = s.query(Jornada).filter(Jornada.fecha == hoy).first()
            if not jornada:
                jornada = Jornada(fecha=hoy)
                s.add(jornada)
                s.flush()

            # Buscar si ya existe una tarea con nombre similar hoy
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
                # Crear nueva actividad
                srv_act = ServicioActividades(s)
                nueva_act = srv_act.crear_no_planeada(
                    nombre=nombre_tarea.capitalize(),
                    jornada=jornada,
                    descripcion="Iniciada por Utilín IA",
                )
                srv_cron.iniciar(nueva_act)
                s.commit()
                msg = f"¡Listo! Creé e inicié el cronómetro para «{nombre_tarea.capitalize()}». ¡Mucho éxito! 🚀"

        if self.callback_notificar_cambio:
            self.callback_notificar_cambio()

        return RespuestaUtilin(mensaje=msg, accion_ejecutada="INICIAR_ACTIVIDAD", datos_accion={"tarea": nombre_tarea})

    def _accion_pausar_tarea(self) -> RespuestaUtilin:
        with self.bd.sesion() as s:
            hoy = date.today()
            jornada = s.query(Jornada).filter(Jornada.fecha == hoy).first()
            if not jornada:
                return RespuestaUtilin(mensaje="No tienes ninguna jornada activa hoy. 🤖")

            activa = (
                s.query(Actividad)
                .filter(Actividad.jornada_id == jornada.id, Actividad.estado == EstadoActividad.EN_CURSO.value)
                .first()
            )
            if not activa:
                return RespuestaUtilin(mensaje="No tienes ninguna actividad corriendo en este momento. ☕")

            srv_cron = ServicioCronometro(s)
            srv_cron.pausar(activa, motivo="Pausada desde Utilín IA")
            s.commit()
            nombre = activa.nombre

        if self.callback_notificar_cambio:
            self.callback_notificar_cambio()

        return RespuestaUtilin(
            mensaje=f"He puesto en pausa «{nombre}». ¡Tómate tu tiempo y avísame cuando sigas! ⏸️",
            accion_ejecutada="PAUSAR_ACTIVIDAD",
        )

    def _accion_finalizar_tarea(self) -> RespuestaUtilin:
        with self.bd.sesion() as s:
            hoy = date.today()
            jornada = s.query(Jornada).filter(Jornada.fecha == hoy).first()
            if not jornada:
                return RespuestaUtilin(mensaje="No hay jornada abierta hoy. 🤖")

            activa = (
                s.query(Actividad)
                .filter(Actividad.jornada_id == jornada.id, Actividad.estado == EstadoActividad.EN_CURSO.value)
                .first()
            )
            if not activa:
                return RespuestaUtilin(mensaje="No tienes ninguna tarea en curso para finalizar. ¿Quieres empezar una nueva? ✨")

            srv_cron = ServicioCronometro(s)
            srv_cron.detener(activa)
            s.commit()
            nombre = activa.nombre

        if self.callback_notificar_cambio:
            self.callback_notificar_cambio()

        return RespuestaUtilin(
            mensaje=f"¡Excelente trabajo! 👏 «{nombre}» quedó registrada como finalizada. ¿Qué sigue en tu lista? 🎯",
            accion_ejecutada="FINALIZAR_ACTIVIDAD",
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

        return RespuestaUtilin(mensaje=" ".join(partes), accion_ejecutada="CONSULTAR_HOY")

    def _accion_consultar_productividad(self) -> RespuestaUtilin:
        ctx = self.obtener_resumen_contextual()
        horas = ctx.get("tiempo_trabajado_horas", 0.0)
        prod = ctx.get("porcentaje_productividad", 0.0)

        calif = "¡Vas a un ritmo impresionante!" if prod >= 85 else "¡Vas con buen avance, sigue así!"
        msg = f"Hoy llevas {horas} horas trabajadas con un {prod}% de productividad. {calif} 💼🔥"
        return RespuestaUtilin(mensaje=msg, accion_ejecutada="CONSULTAR_PRODUCTIVIDAD")

    def _accion_consultar_planeacion(self) -> RespuestaUtilin:
        ctx = self.obtener_resumen_contextual()
        total_sem = ctx.get("total_planeadas_semana", 0)
        items = ctx.get("items_semana", [])

        if total_sem == 0:
            return RespuestaUtilin(mensaje="El tablero semanal aún no tiene tareas registradas. Puedes crearlas en la sección de Planeación 📋")

        resumen_items = ", ".join(f"«{it}»" for it in items[:4])
        mas = f" (+{total_sem - 4} más)" if total_sem > 4 else ""
        return RespuestaUtilin(
            mensaje=f"En la planeación de esta semana hay {total_sem} actividades: {resumen_items}{mas}. ¡Organización al 100%! 📅",
            accion_ejecutada="CONSULTAR_PLANEACION",
        )

    # ------------------------------------------------------------------
    # Consulta a LLM (Ollama / Gemma o Google Gemini)
    # ------------------------------------------------------------------

    def consultar(self, mensaje_usuario: str) -> RespuestaUtilin:
        """Punto de entrada principal para interactuar con Utilín."""
        # 1. Probar primero si es una orden directa a la app
        res_directa = self.procesar_intencion_directa(mensaje_usuario)
        if res_directa:
            return res_directa

        ctx = self.obtener_resumen_contextual()
        contexto_str = (
            f"Contexto actual del usuario en Gente Útil:\n"
            f"- Fecha: {ctx['fecha']}\n"
            f"- Tarea en curso: {ctx['actividad_activa'] or 'Ninguna'}\n"
            f"- Tareas pendientes hoy: {', '.join(ctx['actividades_pendientes']) or 'Ninguna'}\n"
            f"- Horas trabajadas hoy: {ctx['tiempo_trabajado_horas']} h (Productividad: {ctx['porcentaje_productividad']}%)\n"
        )

        prompt_completo = (
            f"{PROMPT_SISTEMA_UTILIN}\n\n"
            f"{contexto_str}\n"
            f"El usuario te dice: \"{mensaje_usuario}\"\n"
            f"Responde como Utilín en máximo 2 a 3 oraciones:"
        )

        # 2. Intentar con Ollama local (Gemma 2)
        resp_ollama = self._consultar_ollama(prompt_completo)
        if resp_ollama:
            return RespuestaUtilin(mensaje=resp_ollama)

        # 3. Intentar con Gemini API si está configurada
        if self.api_key_gemini:
            resp_gemini = self._consultar_gemini(prompt_completo)
            if resp_gemini:
                return RespuestaUtilin(mensaje=resp_gemini)

        # 4. Respuesta amigable de contingencia si el modelo aún se está descargando
        return RespuestaUtilin(
            mensaje=(
                "¡Hola! Te escucho con atención. Estoy terminando de cargar mi modelo Gemma local en tu PC. "
                "Mientras tanto, puedes pedirme 'iniciar tarea', 'pausar', 'finalizar' o '¿cómo voy?' y lo haré de inmediato. 🤖✨"
            )
        )

    def _consultar_ollama(self, prompt: str) -> str | None:
        """Envía el prompt a Ollama local (`localhost:11434`)."""
        url = f"{self.endpoint_ollama}/api/generate"
        payload = {
            "model": self.modelo_ollama,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 120,
            },
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "UtilinBot/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    res = data.get("response", "").strip()
                    if res:
                        return res
        except Exception as e:
            _logger.debug("Ollama local no respondió o modelo no listo: %s", e)
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
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 140},
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
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
