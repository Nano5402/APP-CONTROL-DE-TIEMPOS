"""Gestión del PIN opcional de privacidad en el PC del usuario (RF-09).

Usa ``hashlib.pbkdf2_hmac`` (librería estándar de Python) con sal aleatoria para
guardar el PIN en ``usuarios.pin_hash`` sin texto plano. Si ``pin_hash`` es ``None``
o vacío, la app abre directamente sin pedir PIN.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models import Usuario

_ITERACIONES = 120_000


def generar_hash_pin(pin: str) -> str:
    """Devuelve ``sal_hex$hash_hex`` para el PIN indicado."""
    limpio = pin.strip()
    if len(limpio) < 4 or not limpio.isdigit():
        raise ValueError("El PIN debe tener al menos 4 dígitos numéricos")
    sal = secrets.token_hex(16)
    derivado = hashlib.pbkdf2_hmac(
        "sha256", limpio.encode("utf-8"), bytes.fromhex(sal), _ITERACIONES
    ).hex()
    return f"{sal}${derivado}"


def verificar_hash_pin(pin: str, pin_hash: str | None) -> bool:
    """Comprueba si ``pin`` coincide con ``pin_hash``."""
    if not pin_hash:
        return True
    try:
        sal, esperado = pin_hash.split("$", 1)
        calculado = hashlib.pbkdf2_hmac(
            "sha256", pin.strip().encode("utf-8"), bytes.fromhex(sal), _ITERACIONES
        ).hex()
        return hmac.compare_digest(calculado, esperado)
    except Exception:
        return False


class ServicioPIN:
    """Configura, desactiva o verifica el PIN del usuario local."""

    def __init__(self, s: Session) -> None:
        self.s = s

    def _usuario(self) -> Usuario:
        usr = self.s.scalar(select(Usuario).limit(1))
        if usr is None:
            usr = Usuario(nombre="")
            self.s.add(usr)
            self.s.flush()
        return usr

    def tiene_pin(self) -> bool:
        usr = self._usuario()
        return bool(usr.pin_hash and usr.pin_hash.strip())

    def establecer_pin(self, nuevo_pin: str) -> None:
        usr = self._usuario()
        usr.pin_hash = generar_hash_pin(nuevo_pin)
        self.s.flush()

    def desactivar_pin(self) -> None:
        usr = self._usuario()
        usr.pin_hash = None
        self.s.flush()

    def verificar(self, pin_ingresado: str) -> bool:
        usr = self._usuario()
        return verificar_hash_pin(pin_ingresado, usr.pin_hash)
