"""
seed.py
=======
Datos iniciales idempotentes para la DB de HurData PIP.
Usar INSERT OR IGNORE para ser seguro ante reinicios.
"""
from passlib.context import CryptContext

from app.config import config
from app.db.connection import get_connection

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_DIRECTIVOS = [
    ("Directivo de Tecnología e Ingeniería", "ingenieria@unahur.edu.ar"),
    ("Directivo de Salud Comunitaria",        "saludcomunitaria@unahur.edu.ar"),
    ("Directivo de Educación",                "educacion@unahur.edu.ar"),
    ("Directivo de Biotecnología",            "biotecnologia@unahur.edu.ar"),
]

_USUARIOS = [
    # (usuario, nombre, cargo, role) — role debe ser uno de app/api/permisos.py:ROLES
    ("docente@unahur.edu.ar",    "Docente",    "Docente",       "docente"),
    ("nodocente@unahur.edu.ar",  "No Docente", "No Docente",    "no_docente"),
    ("directivo@unahur.edu.ar",  "Directivo",  "Directivo",     "directivo"),
    ("admin@unahur.edu.ar",      "Admin",       "Desarrollador", "admin"),
]

_DEFAULT_PASSWORD = config.SEED_DEFAULT_PASSWORD


def seed_db() -> None:
    """Inserta directivos y usuarios iniciales si no existen (idempotente)."""
    conn = get_connection()
    try:
        with conn:
            for nombre, email in _DIRECTIVOS:
                conn.execute(
                    "INSERT OR IGNORE INTO Directivo (nombre, email) VALUES (?, ?)",
                    (nombre, email),
                )

            # Calcula el hash solo si hay algún usuario pendiente de inserción.
            pendientes = [
                u for u in _USUARIOS
                if conn.execute(
                    "SELECT 1 FROM Usuario WHERE usuario = ?", (u[0],)
                ).fetchone() is None
            ]
            if pendientes:
                password_hash = _pwd_context.hash(_DEFAULT_PASSWORD)
                for usuario, nombre, cargo, role in pendientes:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO Usuario (usuario, nombre, cargo, role, password_hash)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (usuario, nombre, cargo, role, password_hash),
                    )
    finally:
        conn.close()

    print("[SEED] Datos iniciales cargados.")
