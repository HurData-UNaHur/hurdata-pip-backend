import os
from dotenv import load_dotenv

# Carga las variables físicas del archivo .env al entorno de Python
load_dotenv()

class Config:
    # Busca la variable, y si el archivo .env falla, usa el string por defecto
    EXCEL_SIU_FILENAME = os.getenv("EXCEL_SIU_FILENAME", "estadisticas de fin de cursada.xlsx")

config = Config()