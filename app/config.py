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


config = Config()