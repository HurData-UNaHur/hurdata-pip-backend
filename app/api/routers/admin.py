"""
admin.py
========
Responsabilidad: endpoints que MODIFICAN datos. Todo este router exige la API key
(ver app/api/deps.py: require_admin).

    POST   /upload                  → carga un Excel del SIU (pipeline ETL completo)
    DELETE /api/periodos/{id}       → borra un período, o una carrera dentro de él
    DELETE /api/limpiar-db          → vacía toda la base de datos
"""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.api.deps import get_db, require_admin
from app.api.schemas import MensajeOut
from app.config import config
from app.db import queries
from app.etl.pipeline import ejecutar_etl

# Logger para registrar errores internos sin mostrárselos al cliente
log = logging.getLogger("hurdata")

# 'dependencies' se aplica a TODOS los endpoints de este router
router = APIRouter(tags=["Administración"], dependencies=[Depends(require_admin)])

# Los primeros 4 bytes de todo .xlsx (un .xlsx es un archivo zip)
_XLSX_MAGIC = b"PK\x03\x04"


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------

@router.post("/upload", tags=["ETL"], status_code=201)
def upload_excel(archivo: UploadFile = File(...)):
    """
    Recibe un archivo .xlsx del SIU Guaraní, ejecuta el pipeline ETL completo
    (Extract → Transform → Load) y persiste los datos en la DB.

    Args:
        archivo: archivo .xlsx enviado como form-data (campo 'archivo').

    Returns:
        Resumen de la carga con cantidades de materias, comisiones y resultados.

    Errors:
        400: si el archivo no es un .xlsx válido
        413: si el archivo supera MAX_UPLOAD_MB
        422: si el Excel no tiene el formato esperado del SIU
        500: si el pipeline falla por un error interno
    """
    # `def` (no `async def`): FastAPI lo corre en un thread aparte y no bloquea
    # al resto de la API mientras pandas y SQLite trabajan.

    # Validar extensión
    if not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Solo se aceptan archivos .xlsx del SIU Guaraní.")

    # Validar contenido: un .xlsx es un zip, así que empieza con estos 4 bytes
    if archivo.file.read(4) != _XLSX_MAGIC:
        raise HTTPException(400, "El archivo no es un .xlsx válido.")
    archivo.file.seek(0)  # volver al inicio para poder copiarlo completo

    limite = config.MAX_UPLOAD_MB * 1024 * 1024
    ruta_tmp: Path | None = None
    try:
        # Guardar en un archivo temporal para que el extractor lo pueda leer,
        # copiando por bloques de 1 MB para poder cortar si supera el límite
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            ruta_tmp = Path(tmp.name)
            copiado = 0
            while chunk := archivo.file.read(1024 * 1024):
                copiado += len(chunk)
                if copiado > limite:
                    raise HTTPException(413, f"El archivo supera {config.MAX_UPLOAD_MB} MB.")
                tmp.write(chunk)

        resumen = ejecutar_etl(ruta_excel=ruta_tmp)
    except HTTPException:
        raise                                    # ya tiene su código y mensaje
    except ValueError as e:                      # Excel con formato inesperado
        raise HTTPException(422, str(e))
    except Exception:                            # bug nuestro: detalle al log, mensaje genérico al cliente
        log.exception("Falló el ETL")
        raise HTTPException(500, "Error interno al procesar el archivo.")
    finally:
        if ruta_tmp:
            ruta_tmp.unlink(missing_ok=True)     # limpiar archivo temporal

    return {
        "message": "Archivo procesado correctamente.",
        "resumen": resumen,
    }


# ---------------------------------------------------------------------------
# Borrado de datos
# ---------------------------------------------------------------------------

@router.delete("/api/periodos/{id_periodo}", response_model=MensajeOut)
def eliminar_periodo(
    id_periodo: int,
    id_carrera: int | None = Query(None),   # opcional: si falta, se borra el período entero
    conn=Depends(get_db),
):
    """
    Borra los datos de un período.

    Args:
        id_periodo: id del período a borrar.
        id_carrera: si se indica, borra solo esa carrera dentro del período.

    Errors:
        404: si el período no existe.
    """
    periodo = queries.obtener_periodo(conn, id_periodo)
    if periodo is None:
        raise HTTPException(404, f"No existe el período con id {id_periodo}.")

    queries.borrar_periodo(conn, id_periodo, id_carrera)
    return {"message": f"Datos del período '{periodo['label']}' eliminados."}


@router.delete("/api/limpiar-db", response_model=MensajeOut)
def limpiar_db(conn=Depends(get_db)):
    """Vacía todas las tablas de la base de datos (acción destructiva)."""
    queries.vaciar_base(conn)
    return {"message": "Base de datos reiniciada con éxito."}