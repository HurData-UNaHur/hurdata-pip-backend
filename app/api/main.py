"""
main.py
=======
Punto de entrada de la API REST de HurData PIP.

Para correr en desarrollo:
    uvicorn app.api.main:app --reload

Endpoints disponibles en esta versión:
    GET  /health        → estado de la API y la DB
    GET  /api/periodos   → obtiene la lista de períodos dinámicos
    GET  /api/carreras   → obtiene la lista de carreras guardadas en SQLite
    GET  /api/datos     → obtiene los datos académicos guardados en SQLite (soporta filtros ?periodo=...&carrera=...)
    POST /upload        → carga un Excel del SIU y ejecuta el pipeline ETL
"""

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
import shutil
import tempfile
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
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
    """Verifica que la API y la DB estén operativas."""
    conn = get_connection()
    tablas = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return {
        "status": "ok",
        "db_tablas": [t[0] for t in tablas],
    }


@app.get("/api/carreras", tags=["Consultas"])
def obtener_carreras_disponibles(
    periodo: Optional[str] = Query(None, description="Filtro opcional por período")
):
    """
    Retorna la lista de carreras guardadas en SQLite para un período dado.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        if periodo:
            query = """
                SELECT DISTINCT car.id_carrera, car.nombre 
                FROM Carrera car
                JOIN Carrera_Materia cm ON car.id_carrera = cm.id_carrera
                JOIN Comision c ON cm.id_materia = c.id_materia
                JOIN Periodo p ON c.id_periodo = p.id_periodo
                WHERE (p.anio || ' - ' || p.cuatrimestre) = ? OR p.label = ?
                ORDER BY car.nombre ASC
            """
            cursor.execute(query, (periodo, periodo))
        else:
            cursor.execute("SELECT DISTINCT id_carrera, nombre FROM Carrera ORDER BY nombre ASC")

        filas = cursor.fetchall()
        conn.close()

        # Limpiar prefijos numéricos de SIU si existen (ej. "(023) Licenciatura..." -> "Licenciatura...")
        carreras = []
        for f in filas:
            nombre_raw = f["nombre"]
            carreras.append({"id": f["id_carrera"], "nombre": nombre_raw})

        return {"carreras": carreras}
    except Exception as e:
        conn.close()
        print(f"[ERROR /api/carreras]: {e}")
        return {"carreras": []}


@app.get("/api/datos", tags=["Consultas"])
def obtener_datos_guardados(
    periodo: Optional[str] = Query(None, description="Filtro por período lectivo"),
    carrera: Optional[str] = Query(None, description="Filtro por carrera")
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Materia'")
    if not cursor.fetchone():
        conn.close()
        return {"actividades": [], "nombre_carrera": "", "carreras_disponibles": []}

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. BÚSQUEDA DE TODAS LAS CARRERAS EXISTENTES EN ESTE PERÍODO
    query_carreras = """
        SELECT DISTINCT car.nombre 
        FROM Carrera car
        JOIN Carrera_Materia cm ON car.id_carrera = cm.id_carrera
        JOIN Comision c ON cm.id_materia = c.id_materia
        JOIN Periodo p ON c.id_periodo = p.id_periodo
    """
    params_carreras = []
    if periodo:
        query_carreras += " WHERE (p.anio || ' - ' || p.cuatrimestre) = ? OR p.label = ?"
        params_carreras.extend([periodo, periodo])

    cursor.execute(query_carreras, params_carreras)
    filas_carreras = cursor.fetchall()
    carreras_periodo = [r["nombre"] for r in filas_carreras]

    # Si la consulta por JOIN dio vacía, buscar directo en Carrera
    if not carreras_periodo:
        cursor.execute("SELECT DISTINCT nombre FROM Carrera")
        carreras_periodo = [r["nombre"] for r in cursor.fetchall()]

    carrera_target = carrera if (carrera and carrera.strip()) else None

    # 2. BÚSQUEDA DE MATERIAS Y COMISIONES DE LA CARRERA SELECCIONADA
    query = """
        SELECT 
            m.codigo as codigo_materia,
            m.nombre as materia_nombre,
            c.id_comision,
            c.numero_comision,
            c.nombre_completo as comision_nombre,
            p.anio as anio_academico,
            p.cuatrimestre as cuatrimestre_nombre,
            p.label as label_periodo,
            mod.nombre as modalidad_nombre,
            e.nombre as estado_nombre,
            rc.cantidad_alumnos,
            car.nombre as carrera_nombre
        FROM Materia m
        JOIN Comision c ON m.id_materia = c.id_materia
        JOIN Periodo p ON c.id_periodo = p.id_periodo
        LEFT JOIN Carrera_Materia cm ON m.id_materia = cm.id_materia
        LEFT JOIN Carrera car ON cm.id_carrera = car.id_carrera
        LEFT JOIN Modalidad mod ON c.id_modalidad = mod.id_modalidad
        LEFT JOIN Resultado_Comision rc ON c.id_comision = rc.id_comision
        LEFT JOIN Estado e ON rc.id_estado = e.id_estado
        WHERE 1=1
    """

    params = []
    if periodo:
        query += " AND ((p.anio || ' - ' || p.cuatrimestre) = ? OR p.label = ?)"
        params.extend([periodo, periodo])
        
    if carrera_target:
        query += " AND (car.nombre = ? OR car.nombre LIKE ?)"
        params.extend([carrera_target, f"%{carrera_target}%"])

    cursor.execute(query, params)
    filas = cursor.fetchall()
    conn.close()

    if not filas:
        return {
            "actividades": [], 
            "nombre_carrera": carrera_target or (carreras_periodo[0] if carreras_periodo else ""),
            "carreras_disponibles": carreras_periodo
        }

    actividades_dict = {}
    nombre_carrera_detectado = None

    for f in filas:
        fila = dict(f)
        if not nombre_carrera_detectado and fila.get("carrera_nombre"):
            nombre_carrera_detectado = fila.get("carrera_nombre")

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
            label_p = fila.get("label_periodo") or f"{fila.get('anio_academico')} - {fila.get('cuatrimestre_nombre')}"
            comisiones_dict[com_id] = {
                "numero_comision": fila.get("numero_comision"),
                "modalidad": fila.get("modalidad_nombre") or "PRESENCIAL",
                "nombre_completo": fila.get("comision_nombre"),
                "periodo_lectivo": label_p,
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

    carrera_final = nombre_carrera_detectado or carrera_target or (carreras_periodo[0] if carreras_periodo else "")

    return {
        "nombre_carrera": carrera_final,
        "carreras_disponibles": carreras_periodo,
        "actividades": actividades
    }


@app.get("/api/periodos", tags=["Consultas"])
def obtener_periodos_disponibles():
    """
    Retorna los períodos cargados en SQLite formateados para el selector del frontend.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT DISTINCT id_periodo, anio, cuatrimestre, label
            FROM Periodo
            ORDER BY anio DESC, cuatrimestre ASC
        """)
        filas = cursor.fetchall()
        conn.close()

        resultado = []
        for f in filas:
            dict_f = dict(f)
            if not dict_f.get("label"):
                dict_f["label"] = f"{dict_f['anio']} - {dict_f['cuatrimestre']}"
            resultado.append(dict_f)

        return {"periodos": resultado}
    except Exception as e:
        conn.close()
        print(f"[ERROR /api/periodos]: {e}")
        return {"periodos": []}
    
    
@app.post("/upload", tags=["ETL"], status_code=201)
async def upload_excel(archivo: UploadFile = File(...)):
    """
    Recibe un archivo .xlsx del SIU Guaraní y ejecuta el pipeline ETL.
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