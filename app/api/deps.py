"""
deps.py
=======
Dependencias reutilizables de FastAPI.

    get_db()                 → entrega una conexión SQLite por request y la cierra al terminar.
    get_usuario_actual()     → valida el Bearer JWT y devuelve el payload (401 si no es válido).
    require_permiso(permiso) → además exige ese permiso (403 si el rol no lo tiene).

Uso típico en un endpoint:
    @router.get("/periodos")
    def periodos(conn=Depends(get_db)):
        return queries.listar_periodos(conn)
"""

import sqlite3
from typing import Iterator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.api.auth import verificar_token
from app.api.permisos import permisos_de
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

def get_usuario_actual(token: str = Depends(oauth2_scheme), conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """
    Valida el Bearer JWT y devuelve su payload con los permisos del rol.
    Lanza 401 si el token falta, es inválido o expiró.

    Los permisos se recalculan desde el rol (app/api/permisos.py) y no se toman
    del token, así un cambio en la matriz aplica también a tokens ya emitidos.

    Los endpoints protegidos esperan el header:
        Authorization: Bearer <token>
    """
    payload = verificar_token(token)
    # El rol y el estado de la cuenta se leen de la base en cada request: revocar un acceso o cambiar
    # un rol rige de inmediato, aunque el token todavía no haya vencido.
    cuenta = conn.execute(
        "SELECT role, activo FROM Usuario WHERE usuario = ?", (payload.get("sub"),)
    ).fetchone()
    if cuenta is None or not cuenta["activo"]:
        raise HTTPException(status_code=401, detail="La cuenta no existe o fue desactivada.")
    payload["role"] = cuenta["role"]
    payload["permisos"] = permisos_de(payload.get("role"))
    return payload


def require_permiso(permiso: str):
    """
    Devuelve una dependencia que exige un permiso. Uso:
        @router.post("/upload")
        def upload(usuario=Depends(require_permiso(CARGAR))): ...

    Errors:
        401: token ausente, inválido o expirado.
        403: el rol del usuario no tiene ese permiso.
    """
    def _dependencia(usuario: dict = Depends(get_usuario_actual)) -> dict:
        if permiso not in usuario["permisos"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés permisos para realizar esta acción.",
            )
        return usuario

    return _dependencia
