"""
connection.py
=============
Responsabilidad: proveer una conexión SQLite para la app.

Configuración:
    La ruta al archivo .db se lee de config.DB_PATH.
    Si el directorio no existe, se crea automáticamente.

Uso típico:
    from app.db.connection import get_connection

    conn = get_connection()
    rows = conn.execute("SELECT * FROM Carrera").fetchall()
"""


import sqlite3
from pathlib import Path

from app.config import config


def get_connection() -> sqlite3.Connection:
    """
    Devuelve una nueva conexión a la base de datos SQLite.
    Cada llamada crea un objeto de conexión independiente para no
    caer en errores de conexiones cerradas (Cannot operate on a closed database).
    """
    db_path = Path(config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")

    return conn


def close_connection() -> None:
    """Función de compatibilidad."""
    pass