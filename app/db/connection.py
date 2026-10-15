"""
connection.py
=============
Responsabilidad: proveer una conexión SQLite reutilizable para toda la app.

Patrón usado: módulo singleton — la conexión se crea una sola vez al importar
y se reutiliza en todas las llamadas a get_connection().

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

_connection: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    """
    Devuelve la conexión SQLite singleton.

    La primera llamada abre el archivo y configura:
        - row_factory = sqlite3.Row  → acceso a columnas por nombre (row["campo"])
        - PRAGMA foreign_keys = ON   → integridad referencial activada
        - PRAGMA journal_mode = WAL  → mejor concurrencia para lecturas simultáneas
    """
    global _connection

    if _connection is None:
        db_path = Path(config.DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        _connection = sqlite3.connect(str(db_path), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON")
        _connection.execute("PRAGMA journal_mode = WAL")

        print(f"[DB] Conexión abierta: {db_path}")

    return _connection


def close_connection() -> None:
    """Cierra la conexión si está abierta. Útil en tests y shutdown de FastAPI."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
        print("[DB] Conexión cerrada.")
