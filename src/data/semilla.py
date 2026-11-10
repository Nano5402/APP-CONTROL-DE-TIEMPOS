"""Datos iniciales de la app (horario, solicitantes y configuración por defecto).

Reglas:
- Horario, solicitantes y usuario se cargan **una sola vez** (primer arranque).
  Después el usuario los edita libremente y la app no los vuelve a crear.
- Las claves de configuración que falten se agregan siempre con su valor por
  defecto, pero **nunca** se sobrescribe un valor que el usuario ya cambió.
  Así, versiones nuevas pueden añadir parámetros sin romper nada.
"""

from __future__ import annotations

from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.enums import Prioridad, TipoSolicitante
from data.models import Configuracion, Horario, Solicitante, Usuario

#: Marca en ``configuracion`` que indica que la carga única ya se hizo.
CLAVE_SEMILLA = "sistema.datos_iniciales_cargados"

# Horario confirmado (plan, sección 6.1). (día, bloque, inicio, fin); 0 = lunes.
HORARIO_INICIAL: list[tuple[int, int, time, time]] = [
    *[(dia, 1, time(7, 30), time(12, 0)) for dia in range(5)],
    *[(dia, 2, time(13, 30), time(16, 45)) for dia in range(5)],
    (5, 1, time(9, 0), time(12, 15)),
]

# Solicitantes iniciales (plan, sección 17.1). (nombre, tipo, prioridad, requiere aprobación)
SOLICITANTES_INICIALES: list[tuple[str, TipoSolicitante, Prioridad, bool]] = [
    ("Ing. Luis Eduardo", TipoSolicitante.JEFE, Prioridad.MAXIMA, False),
    ("Dra. Sonia", TipoSolicitante.DOCTORA, Prioridad.MAXIMA, False),
    ("Dra. Yolanda", TipoSolicitante.DOCTORA, Prioridad.MAXIMA, False),
    ("Dra. Liliana", TipoSolicitante.DOCTORA, Prioridad.MAXIMA, False),
]

# Configuración por defecto. Los valores marcados como provisionales se
# ajustan durante la beta (ver docs/decisiones.md).
CONFIGURACION_POR_DEFECTO: dict[str, str] = {
    # Fórmula de productividad (sección 7.2)
    "productividad.peso_cumplimiento": "0.40",
    "productividad.peso_eficiencia": "0.30",
    "productividad.peso_foco": "0.30",
    # Semáforo (sección 7.4)
    "semaforo.verde_min": "85",
    "semaforo.amarillo_min": "60",
    # Meta de tiempo efectivo (RF-10) — provisional, se define en la beta
    "meta.tiempo_efectivo_pct": "80",
    # Recordatorios (RF-04)
    "recordatorio.continuidad_min": "10",
    "recordatorio.repetir_sin_respuesta_min": "2",  # provisional
    "recordatorio.inicio_sin_actividad_min": "10",
    "recordatorio.aviso_almuerzo": "1",
    "recordatorio.aviso_salida": "1",
    # Estilo de los avisos
    "aviso.estilo": "ventana",  # ventana | notificacion
    "aviso.sonido": "1",
    "aviso.volumen": "70",
    # Sistema
    "sistema.inicio_con_windows": "1",
    "sistema.iniciar_minimizada_bandeja": "0",
    # Gráficos y pantalla
    "graficos.resolucion": "1180x740",
    "graficos.modo_ventana": "ventana",
    "graficos.tamano_fuente": "13",
    "graficos.mini_tamano": "normal",
    "graficos.mini_opacidad": "95",
    # Atajos de teclado (RF-12): desactivados (vacíos) por defecto para no interferir
    # mientras el usuario trabaja en otros programas; cada persona los define a su gusto.
    "atajo.iniciar_pausar": "",
    "atajo.finalizar": "",
    "atajo.siguiente_pieza": "",
    "atajo.mini_ventana": "",
    # Copias de seguridad (RF-09)
    "copias.carpeta": "",  # vacío = carpeta por defecto en Documentos
    "copias.conservar": "30",
    # Datos para los PDF
    "empresa.nombre": "Gente Util",
}


def sembrar_datos_iniciales(s: Session) -> None:
    """Carga los datos iniciales que falten. Es seguro llamarla en cada arranque."""
    existentes = set(s.scalars(select(Configuracion.clave)))

    for clave, valor in CONFIGURACION_POR_DEFECTO.items():
        if clave not in existentes:
            s.add(Configuracion(clave=clave, valor=valor))

    if CLAVE_SEMILLA in existentes:
        return

    if s.scalar(select(Usuario.id).limit(1)) is None:
        s.add(Usuario(nombre=""))

    if s.scalar(select(Horario.id).limit(1)) is None:
        for dia, bloque, inicio, fin in HORARIO_INICIAL:
            s.add(Horario(dia_semana=dia, bloque=bloque, hora_inicio=inicio, hora_fin=fin))

    nombres = set(s.scalars(select(Solicitante.nombre)))
    for nombre, tipo, prioridad, requiere in SOLICITANTES_INICIALES:
        if nombre not in nombres:
            s.add(
                Solicitante(
                    nombre=nombre,
                    tipo=tipo.value,
                    prioridad_defecto=prioridad.value,
                    requiere_aprobacion=requiere,
                )
            )

    s.add(Configuracion(clave=CLAVE_SEMILLA, valor="1"))
