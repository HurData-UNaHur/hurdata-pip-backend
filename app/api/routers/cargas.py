"""
cargas.py
=========
Responsabilidad: consultar el historial de Excel cargados (tabla Carga).

    GET /api/cargas?estado=...   → historial de cargas          (cargas:ver)
    GET /api/carga-activa        → de qué Excel salen los datos (requiere login)

Alcance según permisos (app/api/permisos.py):
    • cargas:ver_todas (Admin, Directivo) → todas las cargas.
    • cargas:ver       (Docente)          → solo las que subió él.
    • sin permiso      (No Docente)       → 403.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.api import permisos as P
from app.api.deps import get_db, get_usuario_actual, require_permiso
from app.api.schemas import CargaActivaOut, CargasOut
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
    """
    Historial de Excel cargados, el más reciente primero.

    Cada fila indica 'puede_borrar': solo las cargas ACTIVAS se pueden borrar,
    y con la regla de dueño (app/api/permisos.py: puede_modificar_carga).
    Para borrar se usa DELETE /api/periodos/{id_periodo}?id_carrera=...
    """
    solo_de = None if P.VER_TODAS_LAS_CARGAS in usuario["permisos"] else usuario["sub"]
    cargas = queries.listar_cargas(conn, usuario=solo_de, estado=estado)
    for c in cargas:
        dueno = c.pop("dueno")  # el email no se expone
        c["puede_borrar"] = c["estado"] == "activa" and P.puede_modificar_carga(usuario, dueno)
    return {"cargas": cargas, "ve_todas": solo_de is None}


@router.get("/carga-activa", response_model=CargaActivaOut)
def carga_activa(
    periodo: str = Query(..., description="Ej: '2022 - PRIMER CUATRIMESTRE'"),
    carrera: str = Query(..., description="Nombre exacto de la carrera"),
    conn=Depends(get_db),
    usuario: dict = Depends(get_usuario_actual),
):
    """
    De qué Excel salen los datos de un período + carrera (archivo, quién y cuándo).
    Requiere login: el modo invitado no ve quién cargó cada Excel.
    """
    return {"carga": queries.carga_activa_por_label(conn, periodo, carrera)}
