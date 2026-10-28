"""
main.py
=======
Punto de entrada de la API REST de HurData PIP.

Para correr en desarrollo:
    uvicorn app.api.main:app --reload

Endpoints disponibles en esta versión:
    GET  /health         → estado de la API y la DB
    GET  /api/datos      → obtiene los datos académicos guardados en SQLite
    POST /upload         → carga un Excel del SIU y ejecuta el pipeline ETL
"""

import sqlite3
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
        "db_tablas": [t[0] for t in tablas],
    }


@app.get("/api/datos", tags=["Consultas"])
def obtener_datos_guardados():
    """
    Retorna la jerarquía exacta esperada por transformarDatosBackend() en React.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='Materia'"
    )
    if not cursor.fetchone():
        conn.close()
        return {"actividades": []}

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            m.codigo as codigo_materia,
            m.nombre as materia_nombre,
            c.id_comision,
            c.numero_comision,
            c.nombre_completo as comision_nombre,
            mod.nombre as modalidad_nombre,
            e.nombre as estado_nombre,
            rc.cantidad_alumnos
        FROM Materia m
        JOIN Comision c ON m.id_materia = c.id_materia
        LEFT JOIN Modalidad mod ON c.id_modalidad = mod.id_modalidad
        LEFT JOIN Resultado_Comision rc ON c.id_comision = rc.id_comision
        LEFT JOIN Estado e ON rc.id_estado = e.id_estado
    """)

    filas = cursor.fetchall()
    conn.close()

    if not filas:
        return {"actividades": []}

    actividades_dict = {}

    for f in filas:
        fila = dict(f)
        codigo = fila.get("codigo_materia") or "000"
        materia_nombre = fila.get("materia_nombre")

        if codigo not in actividades_dict:
            actividades_dict[codigo] = {
                "nombre": materia_nombre,
                "codigo_materia": codigo,
                "comisiones_dict": {}
            }

        com_id = fila.get("id_comision")
        comisiones_dict = actividades_dict[codigo]["comisiones_dict"]

        if com_id not in comisiones_dict:
            comisiones_dict[com_id] = {
                "numero_comision": fila.get("numero_comision"),
                "modalidad": fila.get("modalidad_nombre") or "PRESENCIAL",
                "nombre_completo": fila.get("comision_nombre"),
                "estados": []
            }

        if fila.get("estado_nombre"):
            comisiones_dict[com_id]["estados"].append({
                "estado": fila.get("estado_nombre").title(),
                "total_alumnos": fila.get("cantidad_alumnos", 0)
            })

    actividades = []
    for act in actividades_dict.values():
        act["comisiones"] = list(act["comisiones_dict"].values())
        del act["comisiones_dict"]
        actividades.append(act)

    return {"actividades": actividades}

@app.post("/upload", tags=["ETL"], status_code=201)
async def upload_excel(archivo: UploadFile = File(...)):
    """
    Recibe un archivo .xlsx del SIU Guaraní, ejecuta el pipeline ETL completo
    (Extract → Transform → Load) y persiste los datos en la DB.

    Args:
        archivo: archivo .xlsx enviado como form-data (campo 'archivo').

    Returns:
        Resumen de la carga con cantidades de materias, comisiones y resultados.
    """
    if not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Solo se aceptan archivos .xlsx del SIU Guaraní."
        )

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
        ruta_tmp.unlink(missing_ok=True)

    return {
        "message": "Archivo procesado correctamente.",
        "resumen": resumen,
    }
