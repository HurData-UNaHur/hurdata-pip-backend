"""
consultas.py
============
Responsabilidad: endpoints de LECTURA (GET) que alimentan los filtros y los
gráficos del frontend.

    GET /api/periodos            → períodos cargados
    GET /api/carreras            → carreras con datos (filtrable por período)
    GET /api/periodos-carreras   → cada combinación período + carrera cargada
    GET /api/datos               → actividades, comisiones y resultados

Cada función solo recibe los parámetros, llama a app/db/queries.py y devuelve
el resultado; el SQL no vive acá.
"""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.api.schemas import CarrerasOut, DatosOut, PeriodosCarrerasOut, PeriodosOut
from app.db import queries

# Todas las rutas de este archivo cuelgan de /api y se agrupan como "Consultas" en /docs
router = APIRouter(prefix="/api", tags=["Consultas"])


# ---------------------------------------------------------------------------
# Filtros del dashboard
# ---------------------------------------------------------------------------

@router.get("/periodos", response_model=PeriodosOut)
def periodos(conn=Depends(get_db)):
    """Períodos cargados, el más reciente primero."""
    return {"periodos": queries.listar_periodos(conn)}


@router.get("/carreras", response_model=CarrerasOut)
def carreras(
    periodo: str | None = Query(None, description="Ej: '2022 - PRIMER CUATRIMESTRE'"),
    conn=Depends(get_db),
):
    """Carreras con datos en el período indicado (o en todos si no se indica)."""
    return {"carreras": queries.listar_carreras(conn, periodo)}


@router.get("/periodos-carreras", response_model=PeriodosCarrerasOut)
def periodos_carreras(conn=Depends(get_db)):
    """Cada combinación período + carrera cargada (equivale a un Excel subido)."""
    return {"periodos": queries.listar_periodos_con_carreras(conn)}


# ---------------------------------------------------------------------------
# Datos del dashboard
# ---------------------------------------------------------------------------

@router.get("/datos", response_model=DatosOut)
def datos(
    periodo: str = Query(..., description="Ej: '2022 - PRIMER CUATRIMESTRE'"),  # obligatorio
    carrera: str | None = Query(None, description="Nombre exacto de la carrera"),
    conn=Depends(get_db),
):
    """Actividades, comisiones y resultados de una carrera en un período."""
    return queries.obtener_datos(conn, periodo, carrera)