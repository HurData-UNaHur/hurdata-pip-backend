"""
connection.py
=============
Responsabilidad: proveer conexiones SQLite para toda la app.

Patrón usado: una conexión NUEVA por cada llamada a get_connection(). Cada request de FastAPI trabaje con su propia conexión y la
cierre al terminar, sin compartir transacciones con otros requests.

Configuración:
    La ruta al archivo .db se lee de config.DB_PATH.
    Si el directorio no existe, se crea automáticamente.

Uso típico:
    from app.db.connection import get_connection

    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM Carrera").fetchall()
    finally:
        conn.close()   # quien abre la conexión es responsable de cerrarla
"""

import sqlite3
from pathlib import Path

from app.config import config


def get_connection() -> sqlite3.Connection:
    """
    Abre y devuelve una conexión SQLite NUEVA (ya no es singleton).

    Cada conexión se configura con:
        - row_factory = sqlite3.Row  → acceso a columnas por nombre (row["campo"])
        - PRAGMA foreign_keys = ON   → integridad referencial activada
                                       (hay que activarlo en CADA conexión)

    """
    db_path = Path(config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # check_same_thread=False: FastAPI puede abrir la conexión en un thread del
    # pool y usarla en otro. Es seguro porque cada conexión la usa un solo request.
    # timeout=10: si la base está ocupada, espera hasta 10 s antes de fallar.
    conn = sqlite3.connect(str(db_path), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # hay que activarlo en CADA conexión
    return conn