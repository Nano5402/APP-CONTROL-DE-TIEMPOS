"""Reproducción y personalización de sonidos de notificación (estilo teléfono) (RF-04).

Soluciona las limitaciones del viejo ``winsound.Beep`` (silenciado en audífonos
Bluetooth por su latencia de activación y sin control de volumen ni tonos):

- Incluye 6 tonos agradables estilo smartphone en formato WAV (44.1 kHz) con
  pre-activación suave de flujo audio para que audífonos inalámbricos (ej. AirPods)
  y parlantes reproduzcan siempre el aviso completo desde la primera nota.
- Reproduce mediante ``PySide6.QtMultimedia`` (``QMediaPlayer`` + ``QAudioOutput``)
  soportando ``.mp3``, ``.wav``, ``.ogg``, ``.m4a``, ``.aac``, ``.flac`` y ``.wma``,
  con ajuste real de volumen (0–100 %) y selección automática del dispositivo de
  salida activo en Windows.
- Permite a cada usuario importar y asignar sus propios archivos de audio por tipo
  de notificación, guardando una copia portátil en ``carpeta_datos()/sonidos``.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import struct
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import rutas

EXTENSIONES_AUDIO_SOPORTADAS: tuple[str, ...] = (
    ".mp3",
    ".wav",
    ".ogg",
    ".m4a",
    ".aac",
    ".flac",
    ".wma",
)

FILTRO_ARCHIVOS_AUDIO = (
    "Archivos de audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac *.wma);;"
    "Todos los archivos (*.*)"
)


@dataclass(frozen=True)
class DefinicionTono:
    codigo: str
    etiqueta: str
    descripcion: str
    notas: tuple[tuple[float, float, float], ...]  # (freq_hz, inicio_s, duracion_s)


TONOS_INTEGRADOS: tuple[DefinicionTono, ...] = (
    DefinicionTono(
        codigo="gotita",
        etiqueta="Gotita Cristalina (Predeterminado)",
        descripcion="Doble nota limpia y fresca estilo marimba",
        notas=((783.99, 0.00, 0.30), (1046.50, 0.14, 0.50)),
    ),
    DefinicionTono(
        codigo="acorde",
        etiqueta="Acorde Ejecutivo",
        descripcion="Trino ascendente de 4 notas tipo teléfono moderno",
        notas=(
            (523.25, 0.00, 0.28),
            (659.25, 0.11, 0.32),
            (783.99, 0.22, 0.40),
            (1046.50, 0.33, 0.58),
        ),
    ),
    DefinicionTono(
        codigo="campana",
        etiqueta="Campana Suave",
        descripcion="Timbre cristalino con armónicos suaves",
        notas=((880.00, 0.00, 0.88), (1318.51, 0.02, 0.72)),
    ),
    DefinicionTono(
        codigo="pulso",
        etiqueta="Pulso Moderno",
        descripcion="Doble toque rítmico discreto para oficina",
        notas=(
            (698.46, 0.00, 0.22),
            (698.46, 0.17, 0.22),
            (932.33, 0.34, 0.45),
        ),
    ),
    DefinicionTono(
        codigo="alerta",
        etiqueta="Aviso Enérgico",
        descripcion="Secuencia clara ideal cuando falta respuesta o es hora de salida",
        notas=(
            (987.77, 0.00, 0.20),
            (1174.66, 0.16, 0.20),
            (1318.51, 0.32, 0.34),
            (1318.51, 0.54, 0.48),
        ),
    ),
    DefinicionTono(
        codigo="brisa",
        etiqueta="Brisa Zen",
        descripcion="Dos notas cálidas y relajadas",
        notas=((440.00, 0.00, 0.46), (554.37, 0.19, 0.65)),
    ),
)

CODIGO_SILENCIO = "silencio"

TONOS_DEFECTO_POR_CLAVE: dict[str, str] = {
    "aviso.tono.continuidad": "gotita",
    "aviso.tono.repeticion": "alerta",
    "aviso.tono.alerta": "acorde",
    "aviso.tono.jornada": "campana",
}

_MAPA_INTEGRADOS: dict[str, DefinicionTono] = {t.codigo: t for t in TONOS_INTEGRADOS}


def _escribir_wav_melodia(
    ruta_destino: Path,
    notas: tuple[tuple[float, float, float], ...],
    *,
    frecuencia_muestreo: int = 44100,
) -> Path:
    """Genera un archivo WAV PCM de 16 bits claro, armónico y amigable con Bluetooth."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    preroll_s = 0.065  # 65 ms de flujo audio suave para despertar audífonos Bluetooth sin cortar la nota
    duracion_melodia = max((ini + dur for _, ini, dur in notas), default=0.5)
    total_s = preroll_s + duracion_melodia + 0.04
    total_muestras = int(total_s * frecuencia_muestreo)

    muestras = [0.0] * total_muestras

    # Pre-activación ultra suave casi inaudible (-50 dB) para evitar cortes de inicio
    n_pre = int(preroll_s * frecuencia_muestreo)
    for i in range(n_pre):
        envolvente_pre = min(1.0, i / max(1, int(0.02 * frecuencia_muestreo)))
        muestras[i] += 0.003 * envolvente_pre * math.sin(2.0 * math.pi * 190.0 * (i / frecuencia_muestreo))

    for freq, inicio_s, dur_s in notas:
        idx_ini = int((preroll_s + inicio_s) * frecuencia_muestreo)
        n_nota = int(dur_s * frecuencia_muestreo)
        n_ataque = max(1, int(0.008 * frecuencia_muestreo))
        for k in range(n_nota):
            idx = idx_ini + k
            if idx >= total_muestras:
                break
            t = k / frecuencia_muestreo
            ataque = min(1.0, k / n_ataque)
            decaimento = math.exp(-4.6 * (k / max(1, n_nota)))
            onda = (
                0.76 * math.sin(2.0 * math.pi * freq * t)
                + 0.19 * math.sin(2.0 * math.pi * (freq * 2.0) * t)
                + 0.05 * math.sin(2.0 * math.pi * (freq * 3.0) * t)
            )
            muestras[idx] += onda * ataque * decaimento

    pico = max((abs(m) for m in muestras), default=1.0)
    escala = (0.85 * 32767.0) / max(pico, 1e-6)
    pcm = bytearray()
    for m in muestras:
        val = max(-32767, min(32767, int(m * escala)))
        pcm.extend(struct.pack("<h", val))

    with wave.open(str(ruta_destino), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(frecuencia_muestreo)
        wav.writeframes(bytes(pcm))
    return ruta_destino


def asegurar_tonos_integrados() -> Path:
    """Garantiza que todos los archivos WAV integrados existan y los devuelve."""
    carpeta = rutas.carpeta_sonidos_integrados()
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
    except Exception:
        carpeta = rutas.carpeta_datos() / "sonidos_base"
        carpeta.mkdir(parents=True, exist_ok=True)

    for tono in TONOS_INTEGRADOS:
        archivo = carpeta / f"{tono.codigo}.wav"
        if not archivo.is_file():
            try:
                _escribir_wav_melodia(archivo, tono.notas)
            except Exception:
                pass
    return carpeta


def listar_sonidos_usuario() -> list[tuple[str, str]]:
    """Lista los tonos personalizados subidos por el usuario como ``(codigo, etiqueta)``."""
    carpeta = rutas.carpeta_sonidos_usuario()
    resultado: list[tuple[str, str]] = []
    if not carpeta.is_dir():
        return resultado
    for p in sorted(carpeta.iterdir(), key=lambda x: x.name.lower()):
        if p.is_file() and p.suffix.lower() in EXTENSIONES_AUDIO_SOPORTADAS:
            nombre_limpio = p.stem.replace("_", " ").replace("-", " ").strip()
            resultado.append((f"custom:{p.name}", f"Mi audio: {nombre_limpio or p.name}"))
    return resultado


def listar_catalogo_sonidos() -> list[tuple[str, str]]:
    """Retorna todo el catálogo seleccionable: integrados + personalizados + silencio."""
    items: list[tuple[str, str]] = [(t.codigo, t.etiqueta) for t in TONOS_INTEGRADOS]
    items.extend(listar_sonidos_usuario())
    items.append((CODIGO_SILENCIO, "Silencio (solo aviso visual)"))
    return items


def importar_sonido_personalizado(ruta_origen: str | Path) -> str:
    """Copia un archivo de audio del usuario a la carpeta segura de la app y devuelve su código."""
    origen = Path(ruta_origen)
    if not origen.is_file():
        raise FileNotFoundError(f"No se encontró el archivo de audio: {origen}")
    ext = origen.suffix.lower()
    if ext not in EXTENSIONES_AUDIO_SOPORTADAS:
        raise ValueError(
            f"Formato de audio no compatible ({ext}). Usa {', '.join(EXTENSIONES_AUDIO_SOPORTADAS)}."
        )

    carpeta = rutas.carpeta_sonidos_usuario()
    base_segura = re.sub(r"[^A-Za-z0-9._-]+", "_", origen.stem).strip("_") or "tono_personalizado"
    destino = carpeta / f"{base_segura}{ext}"

    # Si ya existe otro archivo con el mismo nombre, evitar colisión salvo que tenga el mismo tamaño
    if destino.exists() and destino.stat().st_size != origen.stat().st_size:
        contador = 1
        while destino.exists():
            destino = carpeta / f"{base_segura}_{contador}{ext}"
            contador += 1

    if not destino.exists() or destino.resolve() != origen.resolve():
        shutil.copy2(origen, destino)
    return f"custom:{destino.name}"


def eliminar_sonido_personalizado(codigo_tono: str) -> bool:
    """Elimina un archivo de tono personalizado importado por el usuario."""
    if not codigo_tono.startswith("custom:"):
        return False
    nombre = codigo_tono.removeprefix("custom:")
    objetivo = rutas.carpeta_sonidos_usuario() / nombre
    if objetivo.is_file():
        try:
            objetivo.unlink()
            return True
        except Exception:
            return False
    return False


def resolver_ruta_sonido(codigo_o_ruta: str | None) -> Path | None:
    """Resuelve el código configurado (``gotita``, ``custom:...`` o ruta directa) a un archivo real."""
    val = (codigo_o_ruta or "").strip() or "gotita"
    if val == CODIGO_SILENCIO:
        return None

    if val.startswith("custom:"):
        nombre = val.removeprefix("custom:")
        candidato = rutas.carpeta_sonidos_usuario() / nombre
        if candidato.is_file():
            return candidato
        # Si fue eliminado externamente, cae limpiamente al tono predeterminado
        val = "gotita"

    if val in _MAPA_INTEGRADOS:
        carpeta = asegurar_tonos_integrados()
        archivo = carpeta / f"{val}.wav"
        if archivo.is_file():
            return archivo
        # Respaldo dinámico en carpeta de datos del usuario
        respaldo = rutas.carpeta_datos() / "sonidos_cache" / f"{val}.wav"
        if not respaldo.is_file():
            _escribir_wav_melodia(respaldo, _MAPA_INTEGRADOS[val].notas)
        return respaldo

    ruta_directa = Path(val)
    if ruta_directa.is_file():
        return ruta_directa

    # Respaldo final al tono predeterminado
    carpeta = asegurar_tonos_integrados()
    archivo = carpeta / "gotita.wav"
    if archivo.is_file():
        return archivo
    return None


def clave_tono_para_aviso(tipo_aviso: Any, es_repeticion: bool = False) -> str:
    """Devuelve la clave de configuración del tono que corresponde a un aviso."""
    if es_repeticion:
        return "aviso.tono.repeticion"
    nombre_tipo = getattr(tipo_aviso, "value", str(tipo_aviso or "")).lower()
    if nombre_tipo in ("finalizacion", "sin_actividad"):
        return "aviso.tono.alerta"
    if nombre_tipo in ("almuerzo", "salida"):
        return "aviso.tono.jornada"
    return "aviso.tono.continuidad"


class _GestorAudio:
    """Mantiene una instancia viva de ``QMediaPlayer`` para reproducir cualquier audio sin cortes."""

    def __init__(self) -> None:
        self._player = None
        self._audio_output = None

    def _asegurar_reproductor(self) -> tuple[Any, Any] | tuple[None, None]:
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
            from PySide6.QtWidgets import QApplication
        except Exception:
            return None, None

        app = QApplication.instance()
        if app is None:
            return None, None

        if self._player is None or self._audio_output is None:
            self._audio_output = QAudioOutput(QMediaDevices.defaultAudioOutput(), app)
            self._player = QMediaPlayer(app)
            self._player.setAudioOutput(self._audio_output)
        return self._player, self._audio_output

    def reproducir(self, ruta: Path, *, volumen: int = 70) -> bool:
        player, output = self._asegurar_reproductor()
        if player is None or output is None:
            return False

        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QMediaDevices

            dispositivo = QMediaDevices.defaultAudioOutput()
            if not dispositivo.isNull():
                output.setDevice(dispositivo)

            vol_norm = max(0.0, min(1.0, float(volumen) / 100.0))
            output.setVolume(vol_norm)

            player.stop()
            player.setSource(QUrl.fromLocalFile(str(ruta.resolve())))
            player.play()
            return True
        except Exception:
            return False

    def detener(self) -> None:
        try:
            if self._player is not None:
                self._player.stop()
        except Exception:
            pass


_GESTOR_AUDIO = _GestorAudio()
_ULTIMO_EVENTO_SONIDO: dict[str, Any] | None = None


def ultimo_sonido_emitido() -> dict[str, Any] | None:
    """Devuelve información del último sonido solicitado (útil para pruebas automatizadas)."""
    return _ULTIMO_EVENTO_SONIDO


def limpiar_registro_sonido() -> None:
    global _ULTIMO_EVENTO_SONIDO
    _ULTIMO_EVENTO_SONIDO = None


def detener_sonidos() -> None:
    """Detiene cualquier sonido en reproducción de forma segura."""
    _GESTOR_AUDIO.detener()
    try:
        if sys.platform == "win32":
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:
        pass


def reproducir_tono_aviso(
    *,
    habilitado: bool = True,
    es_repeticion: bool = False,
    tono: str | None = None,
    volumen: int = 70,
) -> None:
    """Emite el sonido del recordatorio o vista previa con soporte multimedia y respaldo seguro."""
    global _ULTIMO_EVENTO_SONIDO

    if not habilitado:
        return

    tono_elegido = (tono or "").strip() or ("alerta" if es_repeticion else "gotita")
    if tono_elegido == CODIGO_SILENCIO:
        return

    ruta = resolver_ruta_sonido(tono_elegido)
    vol_seguro = max(0, min(100, int(volumen)))
    _ULTIMO_EVENTO_SONIDO = {
        "tono": tono_elegido,
        "ruta": str(ruta) if ruta else None,
        "volumen": vol_seguro,
        "es_repeticion": es_repeticion,
    }

    if vol_seguro == 0:
        return

    # En pruebas / entornos sin pantalla nunca reproducir audio físico por los parlantes
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen" or os.environ.get("PYTEST_CURRENT_TEST"):
        return

    if ruta is not None and _GESTOR_AUDIO.reproducir(ruta, volumen=vol_seguro):
        return

    # Respaldo nativo en Windows para archivos WAV si QtMultimedia no pudo iniciar
    try:
        if sys.platform == "win32" and ruta is not None and ruta.suffix.lower() == ".wav":
            import winsound

            winsound.PlaySound(str(ruta), winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
    except Exception:
        pass

    try:
        from PySide6.QtWidgets import QApplication

        QApplication.beep()
    except Exception:
        pass
