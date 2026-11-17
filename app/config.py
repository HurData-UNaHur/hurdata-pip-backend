import os
from pathlib import Path
from dotenv import load_dotenv

# Carga las variables físicas del archivo .env al entorno de Python
load_dotenv()

# Raíz del proyecto (directorio que contiene /app, /files, etc.)
_BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    # Nombre del Excel del SIU Guaraní en /files
    EXCEL_SIU_FILENAME: str = os.getenv(
        "EXCEL_SIU_FILENAME",
        "estadisticas de fin de cursada.xlsx"
    )

    # Ruta absoluta al archivo SQLite.
    # Se puede sobreescribir con DB_PATH en .env (útil para tests o producción).
    DB_PATH: str = os.getenv(
        "DB_PATH",
        str(_BASE_DIR / "hurdata.db")
    )

    # Orígenes del frontend que pueden llamar a la API (CORS), separados por coma.
    # Por defecto, el servidor de desarrollo de Vite. En producción, definirlo en .env.
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if o.strip()
    ]

    # Clave para los endpoints que modifican datos (subir, borrar).
    # Si se define en .env, esos endpoints exigen el header X-API-Key.
    # Si queda vacía, no se exige (modo desarrollo). En producción, SIEMPRE definirla.
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "")

    # Tamaño máximo (en MB) de un Excel subido por /upload.
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "10"))


config = Config()