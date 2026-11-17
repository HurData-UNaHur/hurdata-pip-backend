"""
connection.py
=============
Responsabilidad: proveer conexiones SQLite para toda la app.

Patr├│n usado: una conexi├│n NUEVA por cada llamada a get_connection(). Cada request de FastAPI trabaje con su propia conexi├│n y la
cierre al terminar, sin compartir transacciones con otros requests.

Configuraci├│n:
    La ruta al archivo .db se lee de config.DB_PATH.
    Si el directorio no existe, se crea autom├íticamente.

Uso t├¡pico:
    from app.db.connection import get_connection

    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM Carrera").fetchall()
    finally:
        conn.close()   # quien abre la conexi├│n es responsable de cerrarla
"""

import sqlite3
from pathlib import Path

from app.config import config


def get_connection() -> sqlite3.Connection:
    """
    Abre y devuelve una conexi├│n SQLite NUEVA (ya no es singleton).

    Cada conexi├│n se configura con:
        - row_factory = sqlite3.Row  ÔåÆ acceso a columnas por nombre (row["campo"])
        - PRAGMA foreign_keys = ON   ÔåÆ integridad referencial activada
                                       (hay que activarlo en CADA conexi├│n)

    """
    db_path = Path(config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # check_same_thread=False: FastAPI puede abrir la conexi├│n en un thread del
    # pool y usarla en otro. Es seguro porque cada conexi├│n la usa un solo request.
    # timeout=10: si la base est├í ocupada, espera hasta 10 s antes de fallar.
    conn = sqlite3.connect(str(db_path), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # hay que activarlo en CADA conexi├│n
    return conn
