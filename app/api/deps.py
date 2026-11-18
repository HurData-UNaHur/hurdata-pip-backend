"""
deps.py
=======
Dependencias reutilizables de FastAPI.

    get_db()        → entrega una conexión SQLite por request y la cierra al terminar.
    require_admin() → valida el Bearer JWT y retorna el payload.

Uso típico en un endpoint:
    @router.get("/periodos")
    def periodos(conn=Depends(get_db)):
        return queries.listar_periodos(conn)
"""

import sqlite3
from typing import Iterator

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.api.auth import verificar_token
from app.db.connection import get_connection

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")


# ---------------------------------------------------------------------------
# Conexión a la base de datos
# ---------------------------------------------------------------------------

def get_db() -> Iterator[sqlite3.Connection]:
    """
    Entrega una conexión SQLite propia para el request en curso.

    Es un generador: FastAPI ejecuta hasta el 'yield' antes del endpoint y el
    'finally' después de responder, aunque el endpoint haya fallado. Así cada
    request usa su propia conexión y siempre se cierra.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()  # siempre se cierra, incluso si hubo una excepción


# ---------------------------------------------------------------------------
# Autorización de endpoints que modifican datos
# ---------------------------------------------------------------------------

def require_admin(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Valida el Bearer JWT y verifica que el usuario tenga role 'admin'.
    Lanza 401 si el token es inválido y 403 si el usuario no tiene permisos.

    Los endpoints protegidos esperan el header:
        Authorization: Bearer <token>
    """
    from fastapi import HTTPException, status
    payload = verificar_token(token)
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés permisos para realizar esta acción.",
        )
    return payload
