"""Valores permitidos (enumeraciones) para los campos de texto del modelo.

Se guardan en la base de datos como TEXT en minúsculas, sin tildes ni espacios
(ej. ``"maxima"``, ``"en_curso"``) para evitar problemas de codificación y
comparaciones. La interfaz se encarga de mostrarlos con tildes (``etiqueta()``).
"""

from __future__ import annotations

from enum import StrEnum


class _EnumEtiquetado(StrEnum):
    """Enum de texto con una etiqueta legible en español para la interfaz."""

    @classmethod
    def valores(cls) -> list[str]:
        return [m.value for m in cls]

    def etiqueta(self) -> str:
        return _ETIQUETAS.get(self.value, self.value.replace("_", " ").capitalize())


class TipoSolicitante(_EnumEtiquetado):
    JEFE = "jefe"
    DOCTORA = "doctora"
    COMPANERO = "companero"
    TERCERO = "tercero"


class Prioridad(_EnumEtiquetado):
    MAXIMA = "maxima"
    NORMAL = "normal"
    MINIMA = "minima"


class TipoActividad(_EnumEtiquetado):
    PLANEADA = "planeada"
    EXTRA = "extra"
    NO_PLANEADA = "no_planeada"


class EstadoActividad(_EnumEtiquetado):
    BLOQUEADA = "bloqueada"
    PENDIENTE = "pendiente"
    EN_CURSO = "en_curso"
    PAUSADA = "pausada"
    COMPLETADA = "completada"
    ARRASTRADA = "arrastrada"
    REASIGNADA = "reasignada"
    RECHAZADA = "rechazada"
    APLAZADA = "aplazada"
    #: Borrado lógico: se oculta en la interfaz pero conserva el historial.
    ELIMINADA = "eliminada"


class EstadoAprobacion(_EnumEtiquetado):
    NO_REQUERIDA = "no_requerida"
    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"


class CanalSolicitud(_EnumEtiquetado):
    WHATSAPP = "whatsapp"
    LLAMADA = "llamada"
    CORREO = "correo"
    PRESENCIAL = "presencial"


class TipoRevision(_EnumEtiquetado):
    MINIMO = "minimo"
    COMPLICADO = "complicado"


class MotivoRevision(_EnumEtiquetado):
    ERROR_PROPIO = "error_propio"
    CAMBIO_CRITERIO = "cambio_criterio"
    INFORMACION_NUEVA = "informacion_nueva"


class TipoPausa(_EnumEtiquetado):
    ALMUERZO = "almuerzo"
    PRIORIDAD = "prioridad"
    EXTERNA = "externa"
    PERSONAL = "personal"
    FIN_JORNADA = "fin_jornada"
    OTRO = "otro"


class RespuestaRecordatorio(_EnumEtiquetado):
    SI = "si"
    NO = "no"
    PAUSAR = "pausar"
    SIN_RESPUESTA = "sin_respuesta"


class EstadoJornada(_EnumEtiquetado):
    ABIERTA = "abierta"
    CERRADA = "cerrada"


class Recurrencia(_EnumEtiquetado):
    NINGUNA = "ninguna"
    DIARIA = "diaria"
    DIAS_SEMANA = "dias_semana"


class TipoCopia(_EnumEtiquetado):
    AUTOMATICA = "automatica"
    EXTERNA = "externa"
    MANUAL = "manual"


class Lugar(_EnumEtiquetado):
    OFICINA = "oficina"
    CASA = "casa"


# Etiquetas con tildes para la interfaz (solo las que no salen bien de forma automática).
_ETIQUETAS: dict[str, str] = {
    "companero": "Compañero",
    "maxima": "Máxima",
    "minima": "Mínima",
    "no_planeada": "No planeada",
    "en_curso": "En curso",
    "no_requerida": "No requerida",
    "whatsapp": "WhatsApp",
    "llamada": "Llamada",
    "minimo": "Mínimo",
    "cambio_criterio": "Cambio de criterio",
    "informacion_nueva": "Información nueva",
    "fin_jornada": "Fin de jornada",
    "externa": "Causa externa",
    "personal": "Necesidad personal",
    "prioridad": "Actividad prioritaria",
    "si": "Sí",
    "dias_semana": "Días de la semana",
    "automatica": "Automática",
}
