"""
consultas.py
============
Responsabilidad: endpoints de LECTURA (GET) que alimentan los filtros y los
gráficos del frontend.

    GET /api/periodos            → períodos cargados
    GET /api/carreras            → carreras con datos (filtrable por período)
    GET /api/periodos-carreras   → cada combinación período + carrera cargada (requiere login)
    GET /api/datos               → actividades, comisiones y resultados
    GET /api/evolucion           → totales por período de una carrera o materia

Cada función solo recibe los parámetros, llama a app/db/queries.py y devuelve
el resultado; el SQL no vive acá.
"""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db, get_usuario_actual
from app.api.permisos import puede_modificar_carga
from app.api.schemas import CarrerasOut, DatosOut, EvolucionOut, PeriodosCarrerasOut, PeriodosOut
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
def periodos_carreras(conn=Depends(get_db), usuario: dict = Depends(get_usuario_actual)):
    """
    Cada combinación período + carrera cargada (equivale a un Excel subido).
    Requiere login: indica quién la cargó y si el usuario actual puede borrarla.
    """
    filas = queries.listar_periodos_con_carreras(conn)
    for f in filas:
        f["puede_borrar"] = puede_modificar_carga(usuario, f.pop("dueno"))  # el email no se expone
    return {"periodos": filas}


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


# ---------------------------------------------------------------------------
# Evolución entre períodos
# ---------------------------------------------------------------------------

@router.get("/evolucion", response_model=EvolucionOut)
def evolucion(
    carrera: str = Query(..., description="Nombre exacto de la carrera"),
    materia: str | None = Query(None, description="Código de materia (ej. '004'). Sin valor: toda la carrera"),
    conn=Depends(get_db),
):
    """
    Totales por estado en cada período de una carrera (o de una materia), del más
    viejo al más nuevo. Público, como /api/datos: lo usa también el modo invitado.
    """
    return queries.evolucion(conn, carrera, materia)
