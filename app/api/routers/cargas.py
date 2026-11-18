"""
cargas.py
=========
Responsabilidad: consultar el historial de Excel cargados (tabla Carga).

    GET /api/cargas?estado=...   → historial de cargas          (cargas:ver)

Alcance según permisos (app/api/permisos.py):
    • cargas:ver_todas (Admin, Directivo) → todas las cargas.
    • cargas:ver       (Docente)          → solo las que subió él.
    • sin permiso      (No Docente)       → 403.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.api import permisos as P
from app.api.deps import get_db, require_permiso
from app.api.schemas import CargasOut
from app.db import queries

router = APIRouter(prefix="/api", tags=["Historial de cargas"])


@router.get("/cargas", response_model=CargasOut)
def historial_cargas(
    estado: Literal["activa", "reemplazada", "borrada"] | None = Query(
        None, description="Filtrar por estado. Sin valor: todas."
    ),
    conn=Depends(get_db),
    usuario: dict = Depends(require_permiso(P.VER_CARGAS)),
):
    """Historial de Excel cargados, el más reciente primero."""
    solo_de = None if P.VER_TODAS_LAS_CARGAS in usuario["permisos"] else usuario["sub"]
    return {
        "cargas": queries.listar_cargas(conn, usuario=solo_de, estado=estado),
        "ve_todas": solo_de is None,
    }
