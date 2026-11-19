"""
seed.py
=======
Datos iniciales para la DB de HurData PIP. Se ejecuta en cada arranque del servidor.

    • Institutos (tabla Directivo): catálogo fijo. Si se cambia un nombre acá,
      se ACTUALIZA en la DB al reiniciar (se identifican por email).
    • Usuarios precargados: solo se insertan si no existen. NO se pisan los que
      ya están, para no deshacer cambios que se hagan desde la app (ej. un cambio
      de rol del admin). Para cambiar uno ya creado, hay que hacerlo en la DB.

Si un rol no es válido, el servidor NO arranca y muestra cuál es el problema.
"""
from passlib.context import CryptContext

from app.api.permisos import ROLES
from app.config import config
from app.db.connection import get_connection

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# (nombre del instituto, email de su dirección). El email es solo para uso interno.
_INSTITUTOS = [
    ("Tecnología e Ingeniería", "ingenieria@unahur.edu.ar"),
    ("Salud Comunitaria",       "saludcomunitaria@unahur.edu.ar"),
    ("Educación",               "educacion@unahur.edu.ar"),
    ("Biotecnología",           "biotecnologia@unahur.edu.ar"),
]

# (usuario, nombre, cargo, role) — role debe ser uno de app/api/permisos.py:ROLES
_USUARIOS = [
    ("docente@unahur.edu.ar",    "Docente",    "Docente",       "docente"),
    ("nodocente@unahur.edu.ar",  "No Docente", "No Docente",    "no_docente"),
    ("directivo@unahur.edu.ar",  "Directivo",  "Directivo",     "directivo"),
    ("admin@unahur.edu.ar",      "Admin",       "Desarrollador", "admin"),
]

_DEFAULT_PASSWORD = config.SEED_DEFAULT_PASSWORD


def _validar_usuarios(usuarios: list[tuple]) -> None:
    """Falla con un mensaje claro si algún usuario del seed tiene un rol inválido."""
    for usuario, _nombre, _cargo, role in usuarios:
        if role not in ROLES:
            raise ValueError(
                f"seed.py: rol '{role}' inválido para {usuario}. "
                f"Usar uno de: {', '.join(ROLES)} (en minúscula, como en app/api/permisos.py)."
            )


def seed_db() -> None:
    """Carga institutos y usuarios iniciales. Idempotente: se puede correr en cada arranque."""
    _validar_usuarios(_USUARIOS)

    conn = get_connection()
    try:
        with conn:
            # Institutos: inserta o actualiza el nombre (el email los identifica)
            for nombre, email in _INSTITUTOS:
                conn.execute(
                    """
                    INSERT INTO Directivo (nombre, email) VALUES (?, ?)
                    ON CONFLICT(email) DO UPDATE SET nombre = excluded.nombre
                    """,
                    (nombre, email),
                )

            # Usuarios: solo los que faltan. El hash se calcula una sola vez y solo si hace falta.
            pendientes = [
                u for u in _USUARIOS
                if conn.execute(
                    "SELECT 1 FROM Usuario WHERE usuario = ?", (u[0],)
                ).fetchone() is None
            ]
            if pendientes:
                password_hash = _pwd_context.hash(_DEFAULT_PASSWORD)
                for usuario, nombre, cargo, role in pendientes:
                    # ON CONFLICT ignora SOLO el duplicado de 'usuario'. A diferencia de
                    # INSERT OR IGNORE, no oculta otros errores (ej. el CHECK del rol).
                    conn.execute(
                        """
                        INSERT INTO Usuario (usuario, nombre, cargo, role, password_hash)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(usuario) DO NOTHING
                        """,
                        (usuario, nombre, cargo, role, password_hash),
                    )
    finally:
        conn.close()

    print("[SEED] Datos iniciales cargados.")
