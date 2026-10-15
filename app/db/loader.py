"""
loader.py
=========
Responsabilidad: tomar el dict jerárquico producido por ExcelTransformer y
persistirlo en la DB SQLite siguiendo el DER de HurData.

Función principal:
    cargar_reporte(datos: dict) -> dict

El insert sigue el orden del DER para respetar las FK:
    1. Modalidad    (catálogo)
    2. Estado       (catálogo)
    3. Carrera      (dimensión)
    4. Materia      (dimensión)
    5. Carrera_Materia (relación)
    6. Periodo      (dimensión temporal)
    7. Comision     (tabla de hechos — grupo)
    8. Resultado_Comision (tabla de hechos — detalle)

Estrategia de duplicados:
    Todas las inserciones usan INSERT OR IGNORE + SELECT para resolver el ID,
    de modo que cargar el mismo Excel dos veces no rompe la DB ni duplica datos.
    Si ya existe un Resultado_Comision para la misma comisión+estado, se actualiza
    la cantidad con INSERT OR REPLACE para reflejar posibles correcciones.
"""

import sqlite3

from app.db.connection import get_connection


# ---------------------------------------------------------------------------
# Helpers privados: upsert de catálogos y dimensiones
# ---------------------------------------------------------------------------

def _get_or_create(conn: sqlite3.Connection, tabla: str, campo: str, valor: str) -> int:
    """
    Inserta el valor si no existe y devuelve su id en la tabla de catálogo.
    Funciona para tablas simples con una sola columna significativa (Modalidad, Estado).

    Args:
        conn:   conexión activa
        tabla:  nombre de la tabla ('Modalidad', 'Estado')
        campo:  nombre de la columna de texto ('nombre')
        valor:  string a insertar/buscar

    Returns:
        int: PK de la fila (nueva o existente)
    """
    conn.execute(
        f"INSERT OR IGNORE INTO {tabla} ({campo}) VALUES (?)", (valor,)
    )
    row = conn.execute(
        f"SELECT rowid FROM {tabla} WHERE {campo} = ?", (valor,)
    ).fetchone()
    return row[0]


def _get_or_create_carrera(conn: sqlite3.Connection, codigo: str, nombre: str) -> int:
    """Upsert de Carrera por código. Devuelve id_carrera."""
    conn.execute(
        "INSERT OR IGNORE INTO Carrera (codigo, nombre) VALUES (?, ?)",
        (codigo, nombre)
    )
    row = conn.execute(
        "SELECT id_carrera FROM Carrera WHERE codigo = ?", (codigo,)
    ).fetchone()
    return row["id_carrera"]


def _get_or_create_materia(conn: sqlite3.Connection, codigo: str, nombre: str) -> int:
    """
    Upsert de Materia por código.
    Si la materia ya existe con distinto nombre (corrección), actualiza el nombre.
    Devuelve id_materia.
    """
    conn.execute(
        "INSERT OR IGNORE INTO Materia (codigo, nombre) VALUES (?, ?)",
        (codigo, nombre)
    )
    # Si ya existía con otro nombre, actualizamos (puede pasar si corrigen el Excel)
    conn.execute(
        "UPDATE Materia SET nombre = ? WHERE codigo = ? AND nombre != ?",
        (nombre, codigo, nombre)
    )
    row = conn.execute(
        "SELECT id_materia FROM Materia WHERE codigo = ?", (codigo,)
    ).fetchone()
    return row["id_materia"]


def _get_or_create_periodo(conn: sqlite3.Connection, anio: int, cuatrimestre: str) -> int:
    """Upsert de Periodo por (anio, cuatrimestre). Devuelve id_periodo."""
    conn.execute(
        "INSERT OR IGNORE INTO Periodo (anio, cuatrimestre) VALUES (?, ?)",
        (anio, cuatrimestre)
    )
    row = conn.execute(
        "SELECT id_periodo FROM Periodo WHERE anio = ? AND cuatrimestre = ?",
        (anio, cuatrimestre)
    ).fetchone()
    return row["id_periodo"]


def _link_carrera_materia(conn: sqlite3.Connection, id_carrera: int, id_materia: int) -> None:
    """Inserta la relación Carrera_Materia si no existe."""
    conn.execute(
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
    """
    Upsert de Comision por (id_periodo, id_materia, numero_comision).
    Devuelve id_comision.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO Comision
            (id_periodo, id_materia, id_modalidad, numero_comision, nombre_completo)
        VALUES (?, ?, ?, ?, ?)
        """,
        (id_periodo, id_materia, id_modalidad, numero_comision, nombre_completo)
    )
    row = conn.execute(
        """
        SELECT id_comision FROM Comision
        WHERE id_periodo = ? AND id_materia = ? AND numero_comision = ?
        """,
        (id_periodo, id_materia, numero_comision)
    ).fetchone()
    return row["id_comision"]


def _upsert_resultado(
    conn: sqlite3.Connection,
    id_comision: int,
    id_estado: int,
    cantidad_alumnos: int,
) -> None:
    """
    Inserta o actualiza Resultado_Comision.
    Si la misma comisión+estado ya existe (recarga del mismo Excel), actualiza
    la cantidad para reflejar correcciones en el reporte original.
    """
    conn.execute(
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
    """
    Carga el dict jerárquico producido por ExcelTransformer en la DB SQLite.

    Args:
        datos: dict con estructura:
            {
                "año_academico": int,
                "cuatrimestre":  str,
                "codigo_carrera": str,
                "nombre_carrera": str,
                "actividades": [
                    {
                        "nombre": str,
                        "codigo_materia": str,
                        "comisiones": [
                            {
                                "numero_comision": int,
                                "modalidad": str,
                                "nombre_completo": str,
                                "estados": [
                                    {"estado": str, "total_alumnos": int, ...}
                                ]
                            }
                        ]
                    }
                ]
            }

    Returns:
        dict con un resumen de la carga:
            {
                "periodo": str,
                "carrera": str,
                "actividades_cargadas": int,
                "comisiones_cargadas": int,
                "resultados_cargados": int,
            }
    """
    conn = get_connection()

    # Contadores para el resumen final
    total_comisiones = 0
    total_resultados = 0

    try:
        # ------------------------------------------------------------------
        # 1. Dimensión temporal
        # ------------------------------------------------------------------
        anio = datos["año_academico"]
        cuatrimestre = datos["cuatrimestre"]
        id_periodo = _get_or_create_periodo(conn, anio, cuatrimestre)

        # ------------------------------------------------------------------
        # 2. Dimensión académica — Carrera
        # ------------------------------------------------------------------
        id_carrera = _get_or_create_carrera(
            conn,
            datos["codigo_carrera"],
            datos["nombre_carrera"]
        )

        # ------------------------------------------------------------------
        # 3. Iterar actividades (Materias)
        # ------------------------------------------------------------------
        for actividad in datos.get("actividades", []):
            codigo_materia = actividad.get("codigo_materia")
            nombre_materia = actividad.get("nombre")

            # Saltar actividades con datos incompletos (no deberían ocurrir)
            if not codigo_materia or not nombre_materia:
                print(f"[LOADER] ⚠️  Actividad sin código o nombre, se omite: {actividad}")
                continue

            id_materia = _get_or_create_materia(conn, codigo_materia, nombre_materia)
            _link_carrera_materia(conn, id_carrera, id_materia)

            # --------------------------------------------------------------
            # 4. Iterar comisiones
            # --------------------------------------------------------------
            for comision in actividad.get("comisiones", []):
                modalidad_nombre = comision.get("modalidad") or "Sin Modalidad"
                id_modalidad = _get_or_create(conn, "Modalidad", "nombre", modalidad_nombre)

                numero = comision.get("numero_comision")
                nombre_completo = comision.get("nombre_completo", "")

                if numero is None:
                    print(f"[LOADER] ⚠️  Comisión sin número en '{nombre_materia}', se omite.")
                    continue

                id_comision = _get_or_create_comision(
                    conn, id_periodo, id_materia, id_modalidad, numero, nombre_completo
                )
                total_comisiones += 1

                # ----------------------------------------------------------
                # 5. Iterar estados → Resultado_Comision
                # ----------------------------------------------------------
                for estado_data in comision.get("estados", []):
                    estado_nombre = estado_data.get("estado")
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
        raise

    return {
        "periodo": f"{anio} - {cuatrimestre}",
        "carrera": datos["nombre_carrera"],
        "actividades_cargadas": len(datos.get("actividades", [])),
        "comisiones_cargadas": total_comisiones,
        "resultados_cargados": total_resultados,
    }
