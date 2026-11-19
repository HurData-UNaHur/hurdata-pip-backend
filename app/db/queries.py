"""
queries.py
==========
Responsabilidad: concentrar TODO el SQL de lectura y borrado que usa la API.

Cada función recibe una conexión ya abierta (la entrega app/api/deps.py) y
devuelve estructuras simples de Python (dicts y listas), sin saber nada de HTTP.
Así se pueden probar sin levantar el servidor y los routers quedan muy chicos.

Funciones de lectura (las usa app/api/routers/consultas.py):
    listar_periodos(conn)
    listar_carreras(conn, periodo)
    listar_periodos_con_carreras(conn)
    obtener_datos(conn, periodo, carrera)

Funciones de borrado (las usa app/api/routers/admin.py):
    obtener_periodo(conn, id_periodo)
    borrar_periodo(conn, id_periodo, id_carrera, borrado_por)
    vaciar_base(conn, borrado_por)

Historial y dueño de cargas (tabla Carga):
    dueno_carga(conn, id_periodo, id_carrera)
    carreras_con_datos(conn, id_periodo)
    dar_de_baja_cargas(conn, estado, por, id_periodo, id_carrera)

Nota sobre el modelo:
    Una Comision pertenece a un período Y a una carrera (columna id_carrera).
    Por eso los listados parten de Comision: es la tabla que dice qué carrera
    tiene datos en qué período.
"""

import sqlite3
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Lectura: listados para los filtros del frontend
# ---------------------------------------------------------------------------

def listar_periodos(conn: sqlite3.Connection) -> list[dict]:
    """
    Devuelve todos los períodos cargados, del más reciente al más antiguo.

    Retorna:
        [{"id_periodo": int, "anio": int, "cuatrimestre": str, "label": str}, ...]
        ej. label: '2022 - PRIMER CUATRIMESTRE'
    """
    # Orden descendente en ambas columnas: el frontend selecciona periodos[0]
    # por defecto, así que el primero debe ser el más reciente.
    rows = conn.execute(
        """
        SELECT id_periodo, anio, cuatrimestre, label
        FROM Periodo
        ORDER BY anio DESC, cuatrimestre DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def listar_carreras(conn: sqlite3.Connection, periodo: str | None) -> list[dict]:
    """
    Devuelve las carreras que tienen datos cargados.

    Args:
        periodo: label del período (ej. '2022 - PRIMER CUATRIMESTRE'). Si es None,
                 devuelve las carreras de todos los períodos.

    Retorna:
        [{"id": int, "nombre": str}, ...] ordenado por nombre.
    """
    sql = """
        SELECT DISTINCT car.id_carrera AS id, car.nombre
        FROM Comision c
        JOIN Carrera car ON car.id_carrera = c.id_carrera
        JOIN Periodo p   ON p.id_periodo   = c.id_periodo
    """
    params: tuple = ()

    # El filtro por período es opcional: solo se agrega si nos lo pidieron.
    # El valor va como parámetro (?) y nunca pegado al texto del SQL.
    if periodo:
        sql += " WHERE p.label = ?"
        params = (periodo,)

    sql += " ORDER BY car.nombre"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def listar_periodos_con_carreras(conn: sqlite3.Connection) -> list[dict]:
    """
    Devuelve cada combinación período + carrera que tiene datos
    (equivale a un Excel cargado). Se usa en el modal de gestión de datos.

    Retorna:
        [{"id_periodo": int, "id_carrera": int, "label": str, "nombre_carrera": str,
          "cargado_por": str | None,   # nombre de quien hizo la carga activa
          "dueno": str | None}, ...]   # email del dueño (uso interno, el router no lo expone)
    """
    rows = conn.execute(
        """
        SELECT DISTINCT p.id_periodo, car.id_carrera, p.label, car.nombre AS nombre_carrera,
               cg.nombre_usuario AS cargado_por, cg.usuario AS dueno
        FROM Comision c
        JOIN Periodo p   ON p.id_periodo   = c.id_periodo
        JOIN Carrera car ON car.id_carrera = c.id_carrera
        LEFT JOIN Carga cg ON cg.id_periodo = c.id_periodo
                          AND cg.id_carrera = c.id_carrera
                          AND cg.estado = 'activa'
        ORDER BY p.anio DESC, p.cuatrimestre DESC, car.nombre
        """
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Dueño de cada carga (tabla Carga, ver schema.sql)
# ---------------------------------------------------------------------------

def carga_activa_por_label(conn: sqlite3.Connection, periodo: str, carrera: str) -> dict | None:
    """
    Carga ACTIVA de un período (label) + carrera (nombre exacto): de qué Excel
    salen los datos que muestra el dashboard. None si no hay.
    Se busca por los ids actuales de Periodo y Carrera, no por el texto guardado en Carga.
    """
    row = conn.execute(
        """
        SELECT cg.id_carga, cg.fecha, cg.nombre_archivo, cg.nombre_usuario AS cargado_por
        FROM Carga cg
        JOIN Periodo p   ON p.id_periodo   = cg.id_periodo
        JOIN Carrera car ON car.id_carrera = cg.id_carrera
        WHERE cg.estado = 'activa' AND p.label = ? AND car.nombre = ?
        """,
        (periodo, carrera),
    ).fetchone()
    return dict(row) if row else None


def obtener_carga(conn: sqlite3.Connection, id_carga: int) -> dict | None:
    """Una carga del historial por id (estado, período y carrera), o None si no existe."""
    row = conn.execute(
        """
        SELECT id_carga, estado, id_periodo, id_carrera, periodo_label, nombre_carrera
        FROM Carga WHERE id_carga = ?
        """,
        (id_carga,),
    ).fetchone()
    return dict(row) if row else None


def dueno_carga(conn: sqlite3.Connection, id_periodo: int, id_carrera: int) -> str | None:
    """Email de quien hizo la carga ACTIVA de ese período + carrera, o None si no hay."""
    row = conn.execute(
        "SELECT usuario FROM Carga WHERE id_periodo = ? AND id_carrera = ? AND estado = 'activa'",
        (id_periodo, id_carrera),
    ).fetchone()
    return row["usuario"] if row else None


def carreras_con_datos(conn: sqlite3.Connection, id_periodo: int) -> list[int]:
    """ids de las carreras que tienen comisiones cargadas en el período."""
    rows = conn.execute(
        "SELECT DISTINCT id_carrera FROM Comision WHERE id_periodo = ?", (id_periodo,)
    ).fetchall()
    return [r["id_carrera"] for r in rows]


def dar_de_baja_cargas(
    conn: sqlite3.Connection,
    estado: str,
    por: str,
    id_periodo: int | None = None,
    id_carrera: int | None = None,
) -> None:
    """
    Pasa las cargas ACTIVAS a 'reemplazada' o 'borrada', registrando quién y cuándo.
    Sin id_periodo afecta a todas; con id_periodo y sin id_carrera, a todo el período.
    No hace commit: se usa dentro de la transacción de quien la llama.
    """
    sql = "UPDATE Carga SET estado = ?, dado_de_baja_por = ?, fecha_baja = ? WHERE estado = 'activa'"
    params: list = [estado, por, ahora_utc()]
    if id_periodo is not None:
        sql += " AND id_periodo = ?"
        params.append(id_periodo)
    if id_carrera is not None:
        sql += " AND id_carrera = ?"
        params.append(id_carrera)
    conn.execute(sql, params)


def ahora_utc() -> str:
    """Fecha y hora actual en UTC, formato ISO 8601 (ej. '2026-11-18T19:40:05+00:00')."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Lectura: árbol de datos del dashboard
# ---------------------------------------------------------------------------

def obtener_datos(conn: sqlite3.Connection, periodo: str, carrera: str | None) -> dict:
    """
    Arma el árbol actividades → comisiones → estados de UNA carrera en UN período.

    Args:
        periodo: label del período (ej. '2022 - PRIMER CUATRIMESTRE').
        carrera: nombre EXACTO de la carrera. Si es None se usa la primera
                 carrera del período (nunca se mezclan datos de varias carreras).

    Retorna:
        {
            "nombre_carrera": str,
            "carreras_disponibles": [str],
            "actividades": [
                {"nombre": str, "codigo_materia": str,
                 "comisiones": [
                    {"numero_comision": int, "modalidad": str, "nombre_completo": str,
                     "estados": [{"estado": str, "total_alumnos": int}]}
                 ]}
            ]
        }
        Si no hay datos para esa combinación, "actividades" viene vacía.
    """
    carreras = [c["nombre"] for c in listar_carreras(conn, periodo)]

    # Si no pidieron carrera, usamos la primera: nunca mezclamos carreras.
    carrera_elegida = carrera if carrera else (carreras[0] if carreras else "")
    vacio = {"nombre_carrera": carrera_elegida, "carreras_disponibles": carreras, "actividades": []}

    # Comparación exacta contra la lista: una carrera inexistente no devuelve nada
    if carrera_elegida not in carreras:
        return vacio

    # Una sola consulta trae todo "plano": una fila por (comisión, estado).
    # LEFT JOIN en resultados/estados para no perder comisiones sin resultados.
    filas = conn.execute(
        """
        SELECT m.codigo AS codigo_materia, m.nombre AS materia,
               c.id_comision, c.numero_comision, c.nombre_completo,
               mo.nombre AS modalidad,
               e.nombre AS estado, rc.cantidad_alumnos
        FROM Comision c
        JOIN Periodo p   ON p.id_periodo   = c.id_periodo
        JOIN Carrera car ON car.id_carrera = c.id_carrera
        JOIN Materia m   ON m.id_materia   = c.id_materia
        JOIN Modalidad mo ON mo.id_modalidad = c.id_modalidad
        LEFT JOIN Resultado_Comision rc ON rc.id_comision = c.id_comision
        LEFT JOIN Estado e ON e.id_estado = rc.id_estado
        WHERE p.label = ? AND car.nombre = ?
        ORDER BY m.nombre, c.numero_comision, e.nombre
        """,
        (periodo, carrera_elegida),
    ).fetchall()

    # Convertimos las filas planas en el árbol anidado que espera el frontend,
    # usando dos diccionarios auxiliares para no duplicar actividades ni comisiones.
    actividades: dict[str, dict] = {}   # codigo_materia -> actividad
    comisiones: dict[int, dict] = {}    # id_comision    -> comisión
    for f in filas:
        # Actividad: se crea la primera vez que aparece su código de materia
        act = actividades.setdefault(
            f["codigo_materia"],
            {"nombre": f["materia"], "codigo_materia": f["codigo_materia"], "comisiones": []},
        )

        # Comisión: se crea la primera vez que aparece su id y se cuelga de la actividad
        com = comisiones.get(f["id_comision"])
        if com is None:
            com = {
                "numero_comision": f["numero_comision"],
                "modalidad": f["modalidad"],
                "nombre_completo": f["nombre_completo"],
                "estados": [],
            }
            comisiones[f["id_comision"]] = com
            act["comisiones"].append(com)

        # Estado: puede ser None si la comisión no tiene resultados cargados
        if f["estado"] is not None:
            com["estados"].append({"estado": f["estado"], "total_alumnos": f["cantidad_alumnos"]})

    return {
        "nombre_carrera": carrera_elegida,
        "carreras_disponibles": carreras,
        "actividades": list(actividades.values()),
    }


# ---------------------------------------------------------------------------
# Borrado (el ON DELETE CASCADE del schema se encarga de las tablas hijas)
# ---------------------------------------------------------------------------

def obtener_periodo(conn: sqlite3.Connection, id_periodo: int) -> dict | None:
    """
    Busca un período por id.

    Retorna:
        {"id_periodo": int, "label": str}, o None si no existe
        (el router lo usa para responder 404).
    """
    row = conn.execute(
        "SELECT id_periodo, label FROM Periodo WHERE id_periodo = ?", (id_periodo,)
    ).fetchone()
    return dict(row) if row else None


def borrar_periodo(
    conn: sqlite3.Connection, id_periodo: int, id_carrera: int | None, borrado_por: str
) -> None:
    """
    Borra datos de un período y marca sus cargas como 'borrada' en el historial.
    Los permisos (dueño de la carga, etc.) los valida el router ANTES de llamar.

    Args:
        id_periodo:  período a borrar.
        id_carrera:  si es None, borra el período COMPLETO (todas las carreras).
                     Si se indica, borra solo los datos de esa carrera en ese período,
                     y si el período queda sin comisiones, borra también el período.
        borrado_por: email del usuario que borra (queda en el historial).
    """
    # 'with conn' abre una transacción: si todo sale bien hace commit,
    # y si algo falla hace rollback (nunca queda el borrado a medias).
    with conn:
        dar_de_baja_cargas(conn, "borrada", borrado_por, id_periodo, id_carrera)

        if id_carrera is None:
            # Borrar el período arrastra comisiones y resultados por ON DELETE CASCADE
            conn.execute("DELETE FROM Periodo WHERE id_periodo = ?", (id_periodo,))
            return

        # Borrar solo las comisiones de esa carrera; sus resultados caen en cascada
        conn.execute(
            "DELETE FROM Comision WHERE id_periodo = ? AND id_carrera = ?",
            (id_periodo, id_carrera),
        )

        # Si no quedó ninguna carrera en el período, el período ya no tiene sentido
        quedan = conn.execute(
            "SELECT COUNT(*) FROM Comision WHERE id_periodo = ?", (id_periodo,)
        ).fetchone()[0]
        if quedan == 0:
            conn.execute("DELETE FROM Periodo WHERE id_periodo = ?", (id_periodo,))


def listar_cargas(
    conn: sqlite3.Connection, usuario: str | None = None, estado: str | None = None
) -> list[dict]:
    """
    Historial de cargas, la más reciente primero.

    Args:
        usuario: si se indica (email), solo las cargas de ese usuario.
        estado:  'activa' | 'reemplazada' | 'borrada'; None = todas.

    Retorna una lista de dicts con los campos de Carga más el NOMBRE de quien
    la dio de baja (no el email). Incluye 'dueno' (email de quien la subió) para
    que el router calcule permisos; el router no lo expone.
    """
    sql = """
        SELECT cg.id_carga, cg.fecha, cg.nombre_archivo, cg.nombre_usuario AS cargado_por,
               cg.usuario AS dueno, cg.id_periodo, cg.id_carrera,
               cg.periodo_label, cg.nombre_carrera, cg.materias, cg.comisiones, cg.resultados,
               cg.estado, COALESCE(u.nombre, cg.dado_de_baja_por) AS dado_de_baja_por, cg.fecha_baja
        FROM Carga cg
        LEFT JOIN Usuario u ON u.usuario = cg.dado_de_baja_por
        WHERE 1 = 1
    """
    params: list = []
    if usuario is not None:
        sql += " AND cg.usuario = ?"
        params.append(usuario)
    if estado is not None:
        sql += " AND cg.estado = ?"
        params.append(estado)
    sql += " ORDER BY cg.id_carga DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# Orden de borrado: primero las tablas hijas y al final las que otras referencian,
# así no se viola ninguna clave foránea.
_TABLAS_HIJAS_PRIMERO = (
    "Resultado_Comision", "Comision", "Carrera_Materia",
    "Materia", "Carrera", "Periodo", "Estado", "Modalidad",
)


def vaciar_base(conn: sqlite3.Connection, borrado_por: str) -> None:
    """
    Vacía las tablas de datos académicos y reinicia sus contadores AUTOINCREMENT.
    NO toca Usuario, Directivo ni el historial de Carga: las cargas activas
    quedan marcadas como 'borrada' por quien hizo el reset.
    """
    with conn:  # transacción: o se vacía todo o no se vacía nada
        dar_de_baja_cargas(conn, "borrada", borrado_por)
        for tabla in _TABLAS_HIJAS_PRIMERO:  # lista fija: nunca viene del usuario
            conn.execute(f"DELETE FROM {tabla}")
        # Solo se reinician los ids de las tablas vaciadas (los de Carga y Usuario siguen)
        marcadores = ", ".join("?" for _ in _TABLAS_HIJAS_PRIMERO)
        conn.execute(f"DELETE FROM sqlite_sequence WHERE name IN ({marcadores})", _TABLAS_HIJAS_PRIMERO)


# ---------------------------------------------------------------------------
# Institutos (tabla Directivo: un instituto + el email de su dirección)
# ---------------------------------------------------------------------------

def listar_institutos(conn: sqlite3.Connection) -> list[dict]:
    """
    Institutos para el selector del registro: solo id y nombre.
    El email de la dirección NO se devuelve: es para el envío interno de la
    solicitud y no debe llegar al navegador (el endpoint es público).
    """
    rows = conn.execute(
        "SELECT id_directivo AS id, nombre FROM Directivo ORDER BY id_directivo"
    ).fetchall()
    return [dict(r) for r in rows]
