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


def migrar(conn) -> None:
    """
    Agrega a Usuario las columnas nuevas en bases creadas con un esquema anterior
    (CREATE TABLE IF NOT EXISTS no modifica tablas que ya existen). Es idempotente.
    """
    columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(Usuario)")}
    if "id_directivo" not in columnas:
        conn.execute("ALTER TABLE Usuario ADD COLUMN id_directivo INTEGER REFERENCES Directivo(id_directivo)")
        # Las cuentas creadas por solicitud conservan el instituto que eligieron
        conn.execute(
            """
            UPDATE Usuario SET id_directivo = (
                SELECT s.id_directivo FROM Solicitud_Registro s
                WHERE s.email = Usuario.usuario AND s.estado = 'aprobada'
            )
            """
        )
    if "intentos_password" not in columnas:
        conn.execute("ALTER TABLE Usuario ADD COLUMN intentos_password INTEGER NOT NULL DEFAULT 0")
    if "activo" not in columnas:
        conn.execute("ALTER TABLE Usuario ADD COLUMN activo INTEGER NOT NULL DEFAULT 1")
    if "bloqueo_password_hasta" not in columnas:
        conn.execute("ALTER TABLE Usuario ADD COLUMN bloqueo_password_hasta TEXT")

def init_db() -> None:
    """
    Lee schema.sql y ejecuta todas sus sentencias contra la DB configurada.
    Si las tablas ya existen, no hace nada (IF NOT EXISTS).
    """
    schema_path = Path(__file__).parent / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")

    conn = get_connection()
    try:
        conn.execute("PRAGMA journal_mode = WAL") 
        conn.executescript(sql)
        migrar(conn)
        conn.commit()
    finally:
        conn.close()  

    print("[DB] Esquema inicializado correctamente.")


if __name__ == "__main__":
    init_db()
    print("[DB] Tablas disponibles:")
    conn = get_connection()
    try:
        tablas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for t in tablas:
            print(f"  • {t['name']}")
    finally:
        conn.close()
