"""
main.py
=======
Punto de entrada de la API REST de HurData PIP.

Para correr en desarrollo:
    uvicorn app.api.main:app --reload

Endpoints disponibles en esta versi├│n:
    GET    /health                      ÔåÆ estado de la API y la DB
    GET    /api/periodos                ÔåÆ per├¡odos cargados
    GET    /api/carreras                ÔåÆ carreras con datos (filtrable por per├¡odo)
    GET    /api/periodos-carreras       ÔåÆ cada combinaci├│n per├¡odo + carrera cargada
    GET    /api/datos                   ÔåÆ actividades, comisiones y resultados
    POST   /upload                      ÔåÆ carga un Excel del SIU y ejecuta el pipeline ETL
    DELETE /api/periodos/{id}           ÔåÆ borra un per├¡odo (o una carrera dentro de ├®l)
    DELETE /api/limpiar-db              ÔåÆ vac├¡a la base de datos

Los endpoints viven en app/api/routers/ (consultas.py y admin.py);
este archivo solo arma la app y los enchufa.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_db
from app.api.routers import admin, consultas
from app.config import config
from app.db.init_db import init_db

# Muestra en consola los logs (incluidos los errores internos del ETL)
logging.basicConfig(level=logging.INFO)


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
    title="HurData PIP ÔÇö API",
    description="Backend anal├¡tico de gesti├│n acad├®mica para la UNAHUR.",
    version="0.2.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS ÔÇö permite peticiones desde el frontend (or├¡genes definidos en config)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,                     # ej: Vite dev server (5173)
    allow_methods=["GET", "POST", "DELETE"],               # solo los m├®todos que usamos
    allow_headers=["Content-Type", "X-API-Key"],           # X-API-Key: ver app/api/deps.py
)

# ---------------------------------------------------------------------------
# Routers: cada uno agrupa endpoints relacionados
# ---------------------------------------------------------------------------

app.include_router(consultas.router)   # GET  ÔåÆ lectura (p├║blicos)
app.include_router(admin.router)       # POST/DELETE ÔåÆ modifican datos (protegidos)


# ---------------------------------------------------------------------------
# Endpoints propios de la app
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Sistema"])
def health_check(conn=Depends(get_db)):
    """
    Verifica que la API y la DB est├®n operativas.

    Retorna:
        - status: "ok"
        - db_tablas: lista de tablas presentes en la DB
    """
    tablas = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return {
        "status": "ok",
        "db_tablas": [t["name"] for t in tablas],
    }
