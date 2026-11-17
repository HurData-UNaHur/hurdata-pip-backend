"""
deps.py
=======
Responsabilidad: dependencias reutilizables de FastAPI (las que se usan con Depends).

    get_db()        → entrega una conexión SQLite por request y la cierra al terminar.
    require_admin() → exige la API key en los endpoints que modifican datos.

Uso típico en un endpoint:
    @router.get("/periodos")
    def periodos(conn=Depends(get_db)):
        return queries.listar_periodos(conn)
"""

import secrets
import sqlite3
from typing import Iterator

from fastapi import Header, HTTPException

from app.config import config
from app.db.connection import get_connection


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

def require_admin(x_api_key: str = Header(default="")) -> None:
    """
    Protege los endpoints que modifican datos (subir, borrar).

    - Si ADMIN_API_KEY está definida en .env: exige el header X-API-Key con ese valor.
    - Si no está definida: modo desarrollo, deja pasar. En producción, SIEMPRE definirla.

    Errors:
        401: si la clave falta o no coincide.
    """
    if not config.ADMIN_API_KEY:
        return  # modo desarrollo: no hay clave configurada

    # compare_digest compara en tiempo constante (evita ataques por tiempo de respuesta)
    if not secrets.compare_digest(x_api_key, config.ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="API key inválida o ausente.")