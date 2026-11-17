"""
loader.py
=========
Responsabilidad: tomar el dict jer├írquico producido por ExcelTransformer y
persistirlo en la DB SQLite siguiendo el DER de HurData.

Funci├│n principal:
    cargar_reporte(datos: dict) -> dict

El insert sigue el orden del DER para respetar las FK:
    1. Modalidad    (cat├ílogo)
    2. Estado       (cat├ílogo)
    3. Carrera      (dimensi├│n)
    4. Materia      (dimensi├│n)
    5. Carrera_Materia (relaci├│n)
    6. Periodo      (dimensi├│n temporal)
    7. Comision     (tabla de hechos ÔÇö grupo; ├║nica por per├¡odo + carrera + materia + n├║mero)
    8. Resultado_Comision (tabla de hechos ÔÇö detalle)

Estrategia de duplicados:
    Las dimensiones (Modalidad, Estado, Carrera, Materia, Periodo) usan
    INSERT OR IGNORE + SELECT para resolver el ID, de modo que cargar el mismo
    Excel dos veces no duplica datos.
    Las comisiones de una carrera en un per├¡odo se REEMPLAZAN al recargar: se
    borran las de esa carrera + per├¡odo y se vuelven a cargar (sus resultados se
    borran en cascada). As├¡ un Excel corregido no deja datos viejos, y las dem├ís
    carreras del mismo per├¡odo no se tocan.

Validaci├│n:
    Si el Excel no trae los metadatos m├¡nimos (a├▒o, cuatrimestre, carrera) se
    lanza ValueError: NO se inventan valores por defecto.
"""

import sqlite3

from app.db.connection import get_connection


# ---------------------------------------------------------------------------
# Helpers privados: upsert de cat├ílogos y dimensiones
# ---------------------------------------------------------------------------

def _get_or_create(conn: sqlite3.Connection, tabla: str, campo: str, valor: str) -> int:
    """
    Inserta el valor si no existe y devuelve su id en la tabla de cat├ílogo.
    Funciona para tablas simples con una sola columna significativa (Modalidad, Estado).

    Args:
        conn:   conexi├│n activa
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
    """Upsert de Carrera por c├│digo. Devuelve id_carrera."""
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
    Upsert de Materia por c├│digo.
    Si la materia ya existe con distinto nombre (correcci├│n), actualiza el nombre.
    Devuelve id_materia.
    """
    conn.execute(
        "INSERT OR IGNORE INTO Materia (codigo, nombre) VALUES (?, ?)",
        (codigo, nombre)
    )
    # Si ya exist├¡a con otro nombre, actualizamos (puede pasar si corrigen el Excel)
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
    """Inserta la relaci├│n Carrera_Materia si no existe."""
    conn.execute(
        "INSERT OR IGNORE INTO Carrera_Materia (id_carrera, id_materia) VALUES (?, ?)",
        (id_carrera, id_materia)
    )


def _get_or_create_comision(
    conn: sqlite3.Connection,
    id_periodo: int,
    id_carrera: int,
    id_materia: int,
    id_modalidad: int,
    numero_comision: int,
    nombre_completo: str,
) -> int:
    """
    Upsert de Comision por (id_periodo, id_carrera, id_materia, numero_comision).
    Devuelve id_comision.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO Comision
            (id_periodo, id_carrera, id_materia, id_modalidad, numero_comision, nombre_completo)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (id_periodo, id_carrera, id_materia, id_modalidad, numero_comision, nombre_completo),
    )
    row = conn.execute(
        """
        SELECT id_comision FROM Comision
        WHERE id_periodo = ? AND id_carrera = ? AND id_materia = ? AND numero_comision = ?
        """,
        (id_periodo, id_carrera, id_materia, numero_comision),
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
    Si la misma comisi├│n+estado ya existe (recarga del mismo Excel), actualiza
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
# Validaci├│n
# ---------------------------------------------------------------------------

# Metadatos m├¡nimos que debe traer el Excel para poder identificar la carga
_CAMPOS_OBLIGATORIOS = ("a├▒o_academico", "cuatrimestre", "codigo_carrera", "nombre_carrera")


def _validar_metadatos(datos: dict) -> None:
    """Falla con ValueError si el Excel no trae lo m├¡nimo. NO inventamos valores."""
    faltan = [c for c in _CAMPOS_OBLIGATORIOS if not datos.get(c)]
    if faltan:
        raise ValueError(
            "El Excel no tiene los datos esperados del SIU. Faltan: " + ", ".join(faltan)
        )
    if not datos.get("actividades"):
        raise ValueError("El Excel no contiene actividades (materias) para cargar.")


# ---------------------------------------------------------------------------
# Funci├│n p├║blica principal
# ---------------------------------------------------------------------------

def cargar_reporte(datos: dict) -> dict:
    """
    Carga el dict jer├írquico producido por ExcelTransformer en la DB SQLite.

    Args:
        datos: dict con estructura:
            {
                "a├▒o_academico": int,
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
                "periodo": str,                    # ej: "2022 - PRIMER CUATRIMESTRE"
                "nombre_carrera": str,
                "actividades_omitidas": [str],     # nombres de actividades que NO se cargaron
                "actividades_cargadas": int,
                "comisiones_cargadas": int,
                "resultados_cargados": int,
            }

    Raises:
        ValueError: si faltan metadatos obligatorios o el Excel no tiene actividades.
    """
    _validar_metadatos(datos)
    conn = get_connection()

    # Contadores para el resumen final
    total_comisiones = 0
    total_resultados = 0

    try:
        # ------------------------------------------------------------------
        # 1. Dimensi├│n temporal
        # ------------------------------------------------------------------
        anio = datos["a├▒o_academico"]
        cuatrimestre = datos["cuatrimestre"]
        id_periodo = _get_or_create_periodo(conn, anio, cuatrimestre)

        # ------------------------------------------------------------------
        # 2. Dimensi├│n acad├®mica ÔÇö Carrera
        # ------------------------------------------------------------------
        id_carrera = _get_or_create_carrera(
            conn,
            datos["codigo_carrera"],
            datos["nombre_carrera"]
        )

        # Recargar un Excel REEMPLAZA lo que hab├¡a de esa carrera en ese per├¡odo
        # (borra comisiones; los resultados se van en cascada). No toca otras carreras.
        conn.execute(
            "DELETE FROM Comision WHERE id_periodo = ? AND id_carrera = ?",
            (id_periodo, id_carrera),
        )

        # ------------------------------------------------------------------
        # 3. Iterar actividades (Materias)
        # ------------------------------------------------------------------
        omitidas: list[str] = []  # actividades que no se pudieron cargar
        for actividad in datos.get("actividades", []):
            codigo_materia = actividad.get("codigo_materia")
            nombre_materia = actividad.get("nombre")

            # Saltar actividades sin c├│digo o nombre. No se pierden en silencio:
            # quedan listadas en 'actividades_omitidas' del resumen.
            if not codigo_materia or not nombre_materia:
                print(f"[LOADER] ÔÜá´©Å  Actividad sin c├│digo o nombre, se omite: {actividad}")
                omitidas.append(actividad.get("nombre") or "(sin nombre)")
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
                    print(f"[LOADER] ÔÜá´©Å  Comisi├│n sin n├║mero en '{nombre_materia}', se omite.")
                    continue

                id_comision = _get_or_create_comision(
                    conn, id_periodo, id_carrera, id_materia, id_modalidad, numero, nombre_completo
                )
                total_comisiones += 1

                # ----------------------------------------------------------
                # 5. Iterar estados ÔåÆ Resultado_Comision
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
        print(f"[LOADER] Ô£à Carga completada ÔÇö {len(datos.get('actividades', [])) - len(omitidas)} materias, "
              f"{total_comisiones} comisiones, {total_resultados} resultados.")

    except Exception as e:
        conn.rollback()
        print(f"[LOADER] ÔØî Error durante la carga, se hizo rollback: {e}")
        raise
    finally:
        conn.close()  # la conexi├│n ya no es compartida: la cierra quien la abre

    return {
        "periodo": f"{anio} - {cuatrimestre}",
        "nombre_carrera": datos["nombre_carrera"],
        "actividades_omitidas": omitidas,
        "actividades_cargadas": len(datos.get("actividades", [])) - len(omitidas),
        "comisiones_cargadas": total_comisiones,
        "resultados_cargados": total_resultados,
    }
