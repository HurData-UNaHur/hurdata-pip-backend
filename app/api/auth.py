"""
auth.py
=======
Lógica de autenticación JWT para HurData PIP.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import config

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def validate_secret_key() -> str:
    if not config.JWT_SECRET_KEY:
        raise ValueError(
            "JWT_SECRET_KEY no está definida en .env. "
            "Generá una con: openssl rand -hex 32"
        )
    return config.JWT_SECRET_KEY


def crear_token(data: dict) -> str:
    """Genera un JWT firmado con HS256, con expiración de ACCESS_TOKEN_EXPIRE_MINUTES."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, validate_secret_key(), algorithm=ALGORITHM)


def verificar_token(token: str) -> dict:
    """Decodifica y valida el JWT. Lanza HTTPException 401 si es inválido o expirado."""
    try:
        payload = jwt.decode(token, validate_secret_key(), algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado.")


def verificar_password(plain: str, hashed: str) -> bool:
    """Verifica una contraseña contra su hash bcrypt."""
    return _pwd_context.verify(plain, hashed)


def hashear_password(plain: str) -> str:
    """Genera el hash bcrypt de una contraseña."""
    return _pwd_context.hash(plain)
