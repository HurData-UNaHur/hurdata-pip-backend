"""
init_db.py
==========
Responsabilidad: crear todas las tablas de la DB ejecutando schema.sql.

Se puede invocar:
    • Al arrancar FastAPI (lifespan startup).
    • Manualmente desde la terminal:  python -m app.db.init_db

Es idempotente gracias a los CREATE TABLE IF NOT EXISTS del schema.
"""

from pathlib import Path

from app.db.connection import get_connection


def init_db() -> None:
    """
    Lee schema.sql y ejecuta todas sus sentencias contra la DB configurada.
    Si las tablas ya existen, no hace nada (IF NOT EXISTS).
    """
    schema_path = Path(__file__).parent / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")

    conn = get_connection()
    conn.executescript(sql)
    conn.commit()

    print("[DB] Esquema inicializado correctamente.")


if __name__ == "__main__":
    init_db()
    print("[DB] Tablas disponibles:")
    conn = get_connection()
    tablas = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    for t in tablas:
        print(f"  • {t['name']}")
