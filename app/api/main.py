"""
main.py
=======
Punto de entrada de la API REST de HurData PIP.

Para correr en desarrollo:
    uvicorn app.api.main:app --reload

Endpoints disponibles en esta versión:
    GET    /health                      → estado de la API y la DB
    GET    /api/periodos                → períodos cargados
    GET    /api/carreras                → carreras con datos (filtrable por período)
    GET    /api/periodos-carreras       → cada combinación período + carrera cargada
    GET    /api/datos                   → actividades, comisiones y resultados
    POST   /upload                      → carga un Excel del SIU y ejecuta el pipeline ETL
    DELETE /api/periodos/{id}           → borra un período (o una carrera dentro de él)
    DELETE /api/limpiar-db              → vacía la base de datos
    POST   /api/login                   → login, devuelve un JWT
    GET    /api/institutos              → institutos para el registro (sin emails)
    GET    /api/cargas                  → historial de Excel cargados

Los endpoints viven en app/api/routers/ (consultas.py y admin.py);
este archivo solo arma la app y los enchufa.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_db
from app.api.auth import validate_secret_key
from app.api.routers import admin, cargas, consultas, usuarios
from app.api.routers import auth as auth_router
from app.config import config
from app.db.init_db import init_db
from app.db.seed import seed_db

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
    seed_db()
    validate_secret_key()   # falla rápido si JWT_SECRET_KEY no está configurada
    yield
    print("[API] Servidor detenido.")


# ---------------------------------------------------------------------------
# Instancia de la app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="HurData PIP — API",
    description="Backend analítico de gestión académica para la UNAHUR.",
    version="0.2.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — permite peticiones desde el frontend (orígenes definidos en config)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,                     # ej: Vite dev server (5173)
    allow_methods=["GET", "POST", "DELETE"],               # solo los métodos que usamos
    allow_headers=["Content-Type", "Authorization"],           # Authorization: Bearer JWT
)

# ---------------------------------------------------------------------------
# Routers: cada uno agrupa endpoints relacionados
# ---------------------------------------------------------------------------

app.include_router(consultas.router)   # GET  → lectura (públicos)
app.include_router(admin.router)       # POST/DELETE → modifican datos (protegidos)
app.include_router(auth_router.router) # POST /api/login, GET /api/institutos
app.include_router(usuarios.router)   # gestión de cuentas e historial de solicitudes
app.include_router(cargas.router)      # GET /api/cargas (historial, según permisos)


# ---------------------------------------------------------------------------
# Endpoints propios de la app
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Sistema"])
def health_check(conn=Depends(get_db)):
    """
    Verifica que la API y la DB estén operativas.

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