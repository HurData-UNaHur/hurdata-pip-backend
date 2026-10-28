"""
loader.py
=========
Persiste la estructura jerárquica devuelta por ExcelTransformer en SQLite.
"""

import sqlite3
from app.db.connection import get_connection


# ---------------------------------------------------------------------------
# Helpers privados: upsert de catálogos y dimensiones
# ---------------------------------------------------------------------------

def _get_or_create(conn: sqlite3.Connection, tabla: str, campo: str, valor: str) -> int:
    """Inserta el valor si no existe y devuelve su id en la tabla de catálogo."""
    cursor = conn.cursor()
    cursor.execute(f"INSERT OR IGNORE INTO {tabla} ({campo}) VALUES (?)", (valor,))
    cursor.execute(f"SELECT rowid FROM {tabla} WHERE {campo} = ?", (valor,))
    row = cursor.fetchone()
    return row[0]


def _get_or_create_carrera(conn: sqlite3.Connection, codigo: str, nombre: str) -> int:
    """Upsert de Carrera por código. Devuelve id_carrera."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO Carrera (codigo, nombre) VALUES (?, ?)",
        (codigo, nombre)
    )
    cursor.execute("SELECT id_carrera FROM Carrera WHERE codigo = ?", (codigo,))
    row = cursor.fetchone()
    return row[0]


def _get_or_create_materia(conn: sqlite3.Connection, codigo: str, nombre: str) -> int:
    """Upsert de Materia por código. Devuelve id_materia."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO Materia (codigo, nombre) VALUES (?, ?)",
        (codigo, nombre)
    )
    cursor.execute(
        "UPDATE Materia SET nombre = ? WHERE codigo = ? AND nombre != ?",
        (nombre, codigo, nombre)
    )
    cursor.execute("SELECT id_materia FROM Materia WHERE codigo = ?", (codigo,))
    row = cursor.fetchone()
    return row[0]


def _get_or_create_periodo(conn: sqlite3.Connection, anio: int, cuatrimestre: str) -> int:
    """Upsert de Periodo por (anio, cuatrimestre). Devuelve id_periodo."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO Periodo (anio, cuatrimestre) VALUES (?, ?)",
        (anio, cuatrimestre)
    )
    cursor.execute(
        "SELECT id_periodo FROM Periodo WHERE anio = ? AND cuatrimestre = ?",
        (anio, cuatrimestre)
    )
    row = cursor.fetchone()
    return row[0]


def _link_carrera_materia(conn: sqlite3.Connection, id_carrera: int, id_materia: int) -> None:
    """Inserta la relación Carrera_Materia si no existe."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO Carrera_Materia (id_carrera, id_materia) VALUES (?, ?)",
        (id_carrera, id_materia)
    )


def _get_or_create_comision(
    conn: sqlite3.Connection,
    id_periodo: int,
    id_materia: int,
    id_modalidad: int,
    numero_comision: int,
    nombre_completo: str,
) -> int:
    """Upsert de Comision. Devuelve id_comision."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO Comision
            (id_periodo, id_materia, id_modalidad, numero_comision, nombre_completo)
        VALUES (?, ?, ?, ?, ?)
        """,
        (id_periodo, id_materia, id_modalidad, numero_comision, nombre_completo)
    )
    cursor.execute(
        """
        SELECT id_comision FROM Comision
        WHERE id_periodo = ? AND id_materia = ? AND numero_comision = ?
        """,
        (id_periodo, id_materia, numero_comision)
    )
    row = cursor.fetchone()
    return row[0]


def _upsert_resultado(
    conn: sqlite3.Connection,
    id_comision: int,
    id_estado: int,
    cantidad_alumnos: int,
) -> None:
    """Inserta o actualiza Resultado_Comision."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO Resultado_Comision (id_comision, id_estado, cantidad_alumnos)
        VALUES (?, ?, ?)
        ON CONFLICT(id_comision, id_estado)
        DO UPDATE SET cantidad_alumnos = excluded.cantidad_alumnos
        """,
        (id_comision, id_estado, cantidad_alumnos)
    )


# ---------------------------------------------------------------------------
# Función pública principal
# ---------------------------------------------------------------------------

def cargar_reporte(datos: dict) -> dict:
    conn = get_connection()

    total_comisiones = 0
    total_resultados = 0

    try:
        # Activar Foreign Keys para la sesión
        conn.execute("PRAGMA foreign_keys = ON;")

        # 1. Dimensión temporal
        anio = datos.get("año_academico", 2024)
        cuatrimestre = datos.get("cuatrimestre", "PRIMER CUATRIMESTRE")
        id_periodo = _get_or_create_periodo(conn, anio, cuatrimestre)

        # 2. Dimensión académica — Carrera
        codigo_carrera = datos.get("codigo_carrera", "000")
        nombre_carrera = datos.get("nombre_carrera", "Carrera General")
        id_carrera = _get_or_create_carrera(conn, codigo_carrera, nombre_carrera)

        # 3. Iterar actividades (Materias)
        for actividad in datos.get("actividades", []):
            codigo_materia = actividad.get("codigo_materia")
            nombre_materia = actividad.get("nombre")

            if not codigo_materia or not nombre_materia:
                print(f"[LOADER] ⚠️ Actividad sin código o nombre, se omite: {actividad}")
                continue

            id_materia = _get_or_create_materia(conn, codigo_materia, nombre_materia)
            _link_carrera_materia(conn, id_carrera, id_materia)

            # 4. Iterar comisiones
            for comision in actividad.get("comisiones", []):
                modalidad_nombre = (comision.get("modalidad") or "Presencial").title()
                id_modalidad = _get_or_create(conn, "Modalidad", "nombre", modalidad_nombre)

                numero = comision.get("numero_comision")
                nombre_completo = comision.get("nombre_completo", f"COMISIÓN {numero}")

                if numero is None:
                    print(f"[LOADER] ⚠️ Comisión sin número en '{nombre_materia}', se omite.")
                    continue

                id_comision = _get_or_create_comision(
                    conn, id_periodo, id_materia, id_modalidad, numero, nombre_completo
                )
                total_comisiones += 1

                # 5. Iterar estados → Resultado_Comision
                for estado_data in comision.get("estados", []):
                    estado_nombre = (estado_data.get("estado") or "Sin Condición").title()
                    cantidad = estado_data.get("total_alumnos")

                    if not estado_nombre or cantidad is None:
                        continue

                    id_estado = _get_or_create(conn, "Estado", "nombre", estado_nombre)
                    _upsert_resultado(conn, id_comision, id_estado, cantidad)
                    total_resultados += 1

        conn.commit()
        print(f"[LOADER] ✅ Carga completada — {len(datos.get('actividades', []))} materias, "
              f"{total_comisiones} comisiones, {total_resultados} resultados.")

    except Exception as e:
        conn.rollback()
        print(f"[LOADER] ❌ Error durante la carga, se hizo rollback: {e}")
        raise e
    finally:
        conn.close()

    return {
        "periodo": f"{anio} - {cuatrimestre}",
        "carrera": nombre_carrera,
        "actividades_cargadas": len(datos.get("actividades", [])),
        "comisiones_cargadas": total_comisiones,
        "resultados_cargados": total_resultados,
    }
