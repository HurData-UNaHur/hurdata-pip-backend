
"""
loader.py
=========
Responsabilidad: recibir el diccionario estructurado entregado por ExcelTransformer
e insertar/actualizar los datos en la base de datos SQLite (hurdata.db).
"""

from app.db.connection import get_connection


def obtener_o_crear_id(cursor, tabla: str, col_id: str, col_nombre: str, valor: str) -> int:
    """Helper para obtener el ID de una tabla de catálogo o crearlo si no existe."""
    cursor.execute(f"SELECT {col_id} FROM {tabla} WHERE {col_nombre} = ?", (valor,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(f"INSERT INTO {tabla} ({col_nombre}) VALUES (?)", (valor,))
    return cursor.lastrowid


def cargar_reporte(datos: dict) -> dict:
    """
    Persiste la estructura jerárquica devuelta por ExcelTransformer en SQLite.
    """
    conn = get_connection()
    cursor = conn.cursor()

    total_materias = 0
    total_comisiones = 0
    total_resultados = 0

    try:
        # Activar Foreign Keys para la sesión
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Metadatos del reporte
        anio_academico = datos.get("año_academico") or 2024
        cuatrimestre = datos.get("cuatrimestre") or "PRIMER CUATRIMESTRE"
        nombre_carrera = datos.get("nombre_carrera") or "Licenciatura en Informática"

        # 1. Resolver/Insertar Período
        cursor.execute("""
            SELECT id_periodo FROM Periodo WHERE anio = ? AND cuatrimestre = ?
        """, (anio_academico, cuatrimestre))
        row_p = cursor.fetchone()
        if row_p:
            id_periodo = row_p[0]
        else:
            cursor.execute("""
                INSERT INTO Periodo (anio, cuatrimestre) VALUES (?, ?)
            """, (anio_academico, cuatrimestre))
            id_periodo = cursor.lastrowid

        # 2. Resolver/Insertar Carrera
        cursor.execute("SELECT id_carrera FROM Carrera WHERE nombre = ?", (nombre_carrera,))
        row_c = cursor.fetchone()
        if row_c:
            id_carrera = row_c[0]
        else:
            cursor.execute("INSERT INTO Carrera (codigo, nombre) VALUES (?, ?)", ("000", nombre_carrera))
            id_carrera = cursor.lastrowid

        for actividad in datos.get("actividades", []):
            nombre_materia = actividad.get("nombre")
            codigo_materia = actividad.get("codigo_materia") or "000"

            # 3. Insertar / Obtener Materia
            cursor.execute("SELECT id_materia FROM Materia WHERE codigo = ?", (codigo_materia,))
            row_m = cursor.fetchone()
            if row_m:
                id_materia = row_m[0]
            else:
                cursor.execute("""
                    INSERT INTO Materia (codigo, nombre) VALUES (?, ?)
                """, (codigo_materia, nombre_materia))
                id_materia = cursor.lastrowid
                total_materias += 1

            # Vincular Carrera_Materia
            cursor.execute("""
                INSERT OR IGNORE INTO Carrera_Materia (id_carrera, id_materia) VALUES (?, ?)
            """, (id_carrera, id_materia))

            for comision in actividad.get("comisiones", []):
                num_comision = comision.get("numero_comision") or 1
                modalidad_str = (comision.get("modalidad") or "Presencial").title()
                nombre_completo = comision.get("nombre_completo") or f"COMISIÓN {num_comision}"

                # Resolver Modalidad
                id_modalidad = obtener_o_crear_id(cursor, "Modalidad", "id_modalidad", "nombre", modalidad_str)

                # 4. Insertar / Obtener Comisión
                cursor.execute("""
                    SELECT id_comision FROM Comision 
                    WHERE id_periodo = ? AND id_materia = ? AND numero_comision = ?
                """, (id_periodo, id_materia, num_comision))
                
                row_com = cursor.fetchone()
                if row_com:
                    id_comision = row_com[0]
                else:
                    cursor.execute("""
                        INSERT INTO Comision (id_periodo, id_materia, id_modalidad, numero_comision, nombre_completo)
                        VALUES (?, ?, ?, ?, ?)
                    """, (id_periodo, id_materia, id_modalidad, num_comision, nombre_completo))
                    id_comision = cursor.lastrowid
                    total_comisiones += 1

                # 5. Insertar Resultados por Estado
                for estado_item in comision.get("estados", []):
                    estado_str = (estado_item.get("estado") or "Sin Condición").title()
                    total_alumnos = estado_item.get("total_alumnos") or 0

                    # Resolver Estado
                    id_estado = obtener_o_crear_id(cursor, "Estado", "id_estado", "nombre", estado_str)

                    cursor.execute("""
                        INSERT OR REPLACE INTO Resultado_Comision (id_comision, id_estado, cantidad_alumnos)
                        VALUES (?, ?, ?)
                    """, (id_comision, id_estado, total_alumnos))
                    total_resultados += 1

        conn.commit()
        print(f"[LOAD] Carga completada: {total_materias} materias, {total_comisiones} comisiones, {total_resultados} resultados.")

    except Exception as e:
        conn.rollback()
        print(f"[LOAD ERROR] Error durante la persistencia en la DB: {e}")
        raise e
    finally:
        conn.close()

    return {
        "materias_procesadas": total_materias,
        "comisiones_procesadas": total_comisiones,
        "resultados_guardados": total_resultados
    }