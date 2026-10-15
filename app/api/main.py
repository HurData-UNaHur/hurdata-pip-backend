"""
main.py
=======
Punto de entrada de la API REST de HurData PIP.

Para correr en desarrollo:
    uvicorn app.api.main:app --reload

Endpoints disponibles en esta versión:
    GET  /health        → estado de la API y la DB
    POST /upload        → carga un Excel del SIU y ejecuta el pipeline ETL
"""

from contextlib import asynccontextmanager
from pathlib import Path
import shutil
import tempfile

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.db.init_db import init_db
from app.db.connection import get_connection
from app.etl.pipeline import ejecutar_etl


# ---------------------------------------------------------------------------
# Lifespan: se ejecuta al arrancar y al apagar el servidor
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el esquema de la DB al arrancar FastAPI."""
    print("[API] Iniciando servidor HurData PIP...")
    init_db()
    yield
    print("[API] Servidor detenido.")


# ---------------------------------------------------------------------------
# Instancia de la app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="HurData PIP — API",
    description="Backend analítico de gestión académica para la UNAHUR.",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — permite peticiones desde el frontend en desarrollo (Vite: 5173)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Sistema"])
def health_check():
    """
    Verifica que la API y la DB estén operativas.

    Retorna:
        - status: "ok"
        - db_tablas: lista de tablas presentes en la DB
    """
    conn = get_connection()
    tablas = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return {
        "status": "ok",
        "db_tablas": [t["name"] for t in tablas],
    }


@app.post("/upload", tags=["ETL"], status_code=201)
async def upload_excel(archivo: UploadFile = File(...)):
    """
    Recibe un archivo .xlsx del SIU Guaraní, ejecuta el pipeline ETL completo
    (Extract → Transform → Load) y persiste los datos en la DB.

    Args:
        archivo: archivo .xlsx enviado como form-data (campo 'archivo').

    Returns:
        Resumen de la carga con cantidades de materias, comisiones y resultados.

    Errors:
        400: si el archivo no es .xlsx
        500: si el pipeline falla
    """
    # Validar extensión
    if not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Solo se aceptan archivos .xlsx del SIU Guaraní."
        )

    # Guardar en un archivo temporal para que el extractor lo pueda leer
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        shutil.copyfileobj(archivo.file, tmp)
        ruta_tmp = Path(tmp.name)

    try:
        resumen = ejecutar_etl(ruta_excel=ruta_tmp)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en el pipeline ETL: {str(e)}"
        )
    finally:
        ruta_tmp.unlink(missing_ok=True)  # limpiar archivo temporal

    return {
        "message": "Archivo procesado correctamente.",
        "resumen": resumen,
    }
