"""
validaciones.py
===============
Reglas de correo y contraseña. Es la fuente de verdad: el frontend repite las mismas
reglas solo para avisar al usuario mientras escribe, pero acá se aplican siempre.
"""
import re

MIN_PASSWORD = 8
MAX_PASSWORD = 72  # bcrypt ignora lo que pasa de 72 bytes

# Parte local: letras, números y . _ % + - (empieza con letra o número). Dominio fijo.
_EMAIL_INSTITUCIONAL = re.compile(r"^[a-z0-9][a-z0-9._%+-]*@unahur\.edu\.ar$")


def normalizar_email(valor: str) -> str:
    return valor.strip().lower()


def email_institucional_valido(email: str) -> bool:
    """Espera un correo ya normalizado (ver normalizar_email)."""
    return bool(_EMAIL_INSTITUCIONAL.match(email))


def faltantes_password(password: str) -> list[str]:
    """Lista lo que le falta a una contraseña para cumplir la política. Vacía si cumple."""
    faltan = []
    if len(password) < MIN_PASSWORD:
        faltan.append(f"al menos {MIN_PASSWORD} caracteres")
    if len(password) > MAX_PASSWORD:
        faltan.append(f"como máximo {MAX_PASSWORD} caracteres")
    if not re.search(r"[A-Z]", password):
        faltan.append("una mayúscula")
    if not re.search(r"[a-z]", password):
        faltan.append("una minúscula")
    if not re.search(r"\d", password):
        faltan.append("un número")
    if not re.search(r"[^A-Za-z0-9\s]|_", password):
        faltan.append("un símbolo")
    return faltan


def mensaje_password(password: str) -> str | None:
    """Mensaje de error para el usuario, o None si la contraseña cumple la política."""
    faltan = faltantes_password(password)
    if not faltan:
        return None
    return "La contraseña debe tener " + ", ".join(faltan) + "."
