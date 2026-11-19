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
    7. Comision     (tabla de hechos — grupo; única por período + carrera + materia + número)
    8. Resultado_Comision (tabla de hechos — detalle)

Estrategia de duplicados:
    Las dimensiones (Modalidad, Estado, Carrera, Materia, Periodo) usan
    INSERT OR IGNORE + SELECT para resolver el ID, de modo que cargar el mismo
    Excel dos veces no duplica datos.
    Las comisiones de una carrera en un período se REEMPLAZAN al recargar: se
    borran las de esa carrera + período y se vuelven a cargar (sus resultados se
    borran en cascada). Así un Excel corregido no deja datos viejos, y las demás
    carreras del mismo período no se tocan.

Validación:
    Si el Excel no trae los metadatos mínimos (año, cuatrimestre, carrera) se
    lanza ValueError: NO se inventan valores por defecto.
"""

import sqlite3

from app.db import queries
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
# Validación
# ---------------------------------------------------------------------------

# Metadatos mínimos que debe traer el Excel para poder identificar la carga
_CAMPOS_OBLIGATORIOS = ("año_academico", "cuatrimestre", "codigo_carrera", "nombre_carrera")


def _validar_metadatos(datos: dict) -> None:
    """Falla con ValueError si el Excel no trae lo mínimo. NO inventamos valores."""
    faltan = [c for c in _CAMPOS_OBLIGATORIOS if not datos.get(c)]
    if faltan:
        raise ValueError(
            "El Excel no tiene los datos esperados del SIU. Faltan: " + ", ".join(faltan)
        )
    if not datos.get("actividades"):
        raise ValueError("El Excel no contiene actividades (materias) para cargar.")


# ---------------------------------------------------------------------------
# Función pública principal
# ---------------------------------------------------------------------------

class CargaNoAutorizada(Exception):
    """El período + carrera ya tiene datos de otro usuario y quien sube no puede reemplazarlos."""


# Quién hizo la carga cuando no viene de la API (ej. python -m app.etl.pipeline)
_CARGA_SISTEMA = {
    "usuario": "sistema",
    "nombre_usuario": "Carga por consola",
    "nombre_archivo": "(consola)",
    "autorizar_reemplazo": lambda dueno: True,
}


def cargar_reporte(datos: dict, carga: dict | None = None) -> dict:
    """
    Carga el dict jerárquico producido por ExcelTransformer en la DB SQLite
    y registra la subida en el historial (tabla Carga).

    Args:
        carga: quién sube y qué archivo. Si es None, se registra como carga del sistema.
            {
                "usuario": str,            # email (sub del JWT)
                "nombre_usuario": str,
                "nombre_archivo": str,     # nombre original del .xlsx
                "autorizar_reemplazo": Callable[[str | None], bool],
                    # recibe el email del dueño de los datos que se van a reemplazar
                    # (None si no hay carga registrada) y decide si se permite.
                "esperado": dict | None,   # opcional ('Nueva versión'): id_periodo, id_carrera,
                                           # periodo_label y nombre_carrera de la carga a reemplazar
            }
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
                "periodo": str,                    # ej: "2022 - PRIMER CUATRIMESTRE"
                "nombre_carrera": str,
                "actividades_omitidas": [str],     # nombres de actividades que NO se cargaron
                "actividades_cargadas": int,
                "comisiones_cargadas": int,
                "resultados_cargados": int,
            }

    Raises:
        ValueError: si faltan metadatos obligatorios o el Excel no tiene actividades.
        CargaNoAutorizada: si ya hay datos de otro usuario y no se permite reemplazarlos.
    """
    _validar_metadatos(datos)
    carga = carga or _CARGA_SISTEMA
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

        # 'Nueva versión' de una carga: el Excel tiene que ser del mismo período + carrera.
        # Si no coincide se rechaza (rollback), en vez de crear una carga distinta.
        esperado = carga.get("esperado")
        if esperado and (id_periodo, id_carrera) != (esperado["id_periodo"], esperado["id_carrera"]):
            raise ValueError(
                f"Este Excel es de {anio} - {cuatrimestre} · {datos['nombre_carrera']}, "
                f"pero la carga que querés reemplazar es de "
                f"{esperado['periodo_label']} · {esperado['nombre_carrera']}."
            )

        # Si ya hay datos de esta carrera en este período, solo se reemplazan si
        # quien sube está autorizado (dueño de la carga, directivo o admin).
        ya_hay_datos = conn.execute(
            "SELECT 1 FROM Comision WHERE id_periodo = ? AND id_carrera = ? LIMIT 1",
            (id_periodo, id_carrera),
        ).fetchone() is not None
        dueno = queries.dueno_carga(conn, id_periodo, id_carrera)
        if (ya_hay_datos or dueno) and not carga["autorizar_reemplazo"](dueno):
            raise CargaNoAutorizada(
                "Ese período y carrera ya fueron cargados por otro usuario. "
                "Solo quien lo cargó, un directivo o el admin pueden reemplazarlo."
            )
        queries.dar_de_baja_cargas(conn, "reemplazada", carga["usuario"], id_periodo, id_carrera)

        # Recargar un Excel REEMPLAZA lo que había de esa carrera en ese período
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

            # Saltar actividades sin código o nombre. No se pierden en silencio:
            # quedan listadas en 'actividades_omitidas' del resumen.
            if not codigo_materia or not nombre_materia:
                print(f"[LOADER] ⚠️  Actividad sin código o nombre, se omite: {actividad}")
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
                    print(f"[LOADER] ⚠️  Comisión sin número en '{nombre_materia}', se omite.")
                    continue

                id_comision = _get_or_create_comision(
                    conn, id_periodo, id_carrera, id_materia, id_modalidad, numero, nombre_completo
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

        # ------------------------------------------------------------------
        # 6. Registrar la subida en el historial (misma transacción)
        # ------------------------------------------------------------------
        cur = conn.execute(
            """
            INSERT INTO Carga (fecha, nombre_archivo, usuario, nombre_usuario,
                               id_periodo, id_carrera, periodo_label, nombre_carrera,
                               materias, comisiones, resultados)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                queries.ahora_utc(), carga["nombre_archivo"], carga["usuario"], carga["nombre_usuario"],
                id_periodo, id_carrera, f"{anio} - {cuatrimestre}", datos["nombre_carrera"],
                len(datos.get("actividades", [])) - len(omitidas), total_comisiones, total_resultados,
            ),
        )
        id_carga = cur.lastrowid

        conn.commit()
        print(f"[LOADER] ✅ Carga completada — {len(datos.get('actividades', [])) - len(omitidas)} materias, "
              f"{total_comisiones} comisiones, {total_resultados} resultados.")

    except Exception as e:
        conn.rollback()
        print(f"[LOADER] ❌ Error durante la carga, se hizo rollback: {e}")
        raise
    finally:
        conn.close()  # la conexión ya no es compartida: la cierra quien la abre

    return {
        "id_carga": id_carga,
        "periodo": f"{anio} - {cuatrimestre}",
        "nombre_carrera": datos["nombre_carrera"],
        "actividades_omitidas": omitidas,
        "actividades_cargadas": len(datos.get("actividades", [])) - len(omitidas),
        "comisiones_cargadas": total_comisiones,
        "resultados_cargados": total_resultados,
    }
