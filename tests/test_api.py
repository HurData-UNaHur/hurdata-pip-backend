
import io, os
from pathlib import Path
 
# La DB de prueba y las variables de entorno se definen ANTES de importar la app.
# config.py solo acepta un NOMBRE de archivo (siempre en la raíz del proyecto, por
# seguridad), así que la DB de prueba es <raíz>/test.db. Se borra al empezar para
# que cada corrida arranque vacía y con el schema actual.
_RAIZ = Path(__file__).resolve().parent.parent
for _sufijo in ("", "-wal", "-shm"):
    (_RAIZ / f"test.db{_sufijo}").unlink(missing_ok=True)
os.environ["DB_PATH"] = "test.db"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-tests-aaaabbbbccccdddd"
 
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
 
from app.api.main import app
 
# H se puebla con un token real por el fixture _populate_auth_headers antes de cualquier test.
# Como es un dict mutable referenciado por subir(..., headers=H), la mutación es visible
# en todos los tests sin cambiar sus firmas.
H: dict = {}
 
 
def excel(carrera_cod, carrera_nom, libres, promo, anio=2022, cuat="PRIMER CUATRIMESTRE 2022",
          completo=True) -> bytes:
    """Genera un Excel con el layout del SIU (metadatos + actividad + comisión + estados)."""
    wb = Workbook(); ws = wb.active
    if completo:
        ws.append(["Año Académico", None, anio])
        ws.append(["Período Lectivo", None, cuat])
        ws.append(["Propuesta", None, f"({carrera_cod}) {carrera_nom}"])
    ws.append(["Estado", "Total Alumnos", "Porcentaje sobre el total"])
    ws.append(["Actividad Inglés I"])
    ws.append(["Comisión (004)-COMISIÓN 1-COMBINADA"])
    ws.append(["Libre", libres, 0.3])
    ws.append(["Promocionó", promo, 0.7])
    ws.append(["<b>Totales por actividad</b>: Libre: 1"])
    ws.append(["Actividad Programación I"])
    ws.append(["Comisión (007)-COMISIÓN 2-VIRTUAL"])
    ws.append(["Libre", 3, 0.5])
    ws.append(["Regular", 3, 0.5])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()
 
 
def subir(c, data, nombre="x.xlsx", headers=H):
    return c.post("/upload", files={"archivo": (nombre, data)}, headers=headers)
 
 
@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:      # dispara el lifespan (init_db)
        yield client


@pytest.fixture(scope="module", autouse=True)
def _populate_auth_headers(c):
    """Obtiene un token JWT real y puebla H para todos los tests del módulo."""
    resp = c.post("/api/login", json={"usuario": "admin@unahur.edu.ar", "password": "Origone151"})
    assert resp.status_code == 200, f"Login falló en setup: {resp.text}"
    token = resp.json()["access_token"]
    H.update({"Authorization": f"Bearer {token}"})

 
def test_01_vacio(c):
    assert c.get("/api/periodos").json() == {"periodos": []}
    assert c.get("/api/carreras", params={"periodo": "2022 - PRIMER CUATRIMESTRE"}).json() == {"carreras": []}
    d = c.get("/api/datos", params={"periodo": "2022 - PRIMER CUATRIMESTRE"}).json()
    assert d["actividades"] == []
 
 
def test_02_upload_dos_carreras_que_comparten_materia(c):
    r = subir(c, excel("023", "Licenciatura en Informática", libres=10, promo=20))
    assert r.status_code == 201, r.text
    resumen = r.json()["resumen"]
    # El front lee EXACTAMENTE estas dos claves:
    assert resumen["periodo"] == "2022 - PRIMER CUATRIMESTRE"
    assert resumen["nombre_carrera"] == "Licenciatura en Informática"
    r = subir(c, excel("024", "Licenciatura en Sistemas", libres=99, promo=1))
    assert r.status_code == 201, r.text
 
 
def test_03_listados(c):
    p = c.get("/api/periodos").json()["periodos"]
    assert [x["label"] for x in p] == ["2022 - PRIMER CUATRIMESTRE"]
    car = c.get("/api/carreras", params={"periodo": p[0]["label"]}).json()["carreras"]
    assert [x["nombre"] for x in car] == ["Licenciatura en Informática", "Licenciatura en Sistemas"]
    pc = c.get("/api/periodos-carreras", headers=H).json()["periodos"]
    assert len(pc) == 2 and {"id_periodo", "id_carrera", "label", "nombre_carrera"} <= set(pc[0])
 
 
def libres_ingles(d):
    act = next(a for a in d["actividades"] if a["codigo_materia"] == "004")
    return next(e["total_alumnos"] for e in act["comisiones"][0]["estados"] if e["estado"] == "Libre")
 
 
def test_04_no_se_mezclan_las_carreras(c):
    per = "2022 - PRIMER CUATRIMESTRE"
    a = c.get("/api/datos", params={"periodo": per, "carrera": "Licenciatura en Informática"}).json()
    b = c.get("/api/datos", params={"periodo": per, "carrera": "Licenciatura en Sistemas"}).json()
    assert libres_ingles(a) == 10      # antes se pisaban entre sí
    assert libres_ingles(b) == 99
    assert a["carreras_disponibles"] == ["Licenciatura en Informática", "Licenciatura en Sistemas"]
    # forma que espera transformData.js
    com = a["actividades"][0]["comisiones"][0]
    assert set(com) == {"numero_comision", "modalidad", "nombre_completo", "estados"}
    assert com["modalidad"] in ("Virtual", "Presencial", "Combinada")
    # sin carrera -> usa la primera, no mezcla
    assert libres_ingles(c.get("/api/datos", params={"periodo": per}).json()) == 10
 
 
def test_05_filtro_exacto_sin_like(c):
    per = "2022 - PRIMER CUATRIMESTRE"
    d = c.get("/api/datos", params={"periodo": per, "carrera": "Licenciatura"}).json()
    assert d["actividades"] == []      # "Licenciatura" ya no matchea por substring
 
 
def test_06_recargar_reemplaza_solo_su_carrera(c):
    r = subir(c, excel("023", "Licenciatura en Informática", libres=11, promo=19))
    assert r.status_code == 201
    per = "2022 - PRIMER CUATRIMESTRE"
    a = c.get("/api/datos", params={"periodo": per, "carrera": "Licenciatura en Informática"}).json()
    b = c.get("/api/datos", params={"periodo": per, "carrera": "Licenciatura en Sistemas"}).json()
    assert libres_ingles(a) == 11 and libres_ingles(b) == 99
    assert len(a["actividades"][0]["comisiones"]) == 1   # sin duplicados
 
 
def test_07_validaciones_de_upload(c):
    assert subir(c, b"hola", "x.txt").status_code == 400                 # extensión
    assert subir(c, b"no soy un zip", "x.xlsx").status_code == 400       # contenido
    r = subir(c, excel("1", "X", 1, 1, completo=False))                  # sin metadatos
    assert r.status_code == 422 and "Faltan" in r.json()["detail"]
 
 
def test_08_auth_en_endpoints_destructivos(c):
    # Sin header Authorization → 401
    assert subir(c, excel("023", "L", 1, 1), headers={}).status_code == 401
    assert c.delete("/api/limpiar-db").status_code == 401
    # Token inválido (manipulado) → 401
    assert c.delete("/api/limpiar-db", headers={"Authorization": "Bearer token.invalido.xyz"}).status_code == 401
    # Token válido → acceso permitido (200)
    assert c.delete("/api/limpiar-db", headers=H).status_code == 200
    # Tras vaciar la DB, re-cargar datos para que los tests siguientes tengan datos
    subir(c, excel("023", "Licenciatura en Informática", libres=10, promo=20))
    subir(c, excel("024", "Licenciatura en Sistemas", libres=99, promo=1))
    assert c.get("/api/periodos").status_code == 200       # lecturas siguen públicas
 
 
def test_09_borrar_una_carrera_no_toca_la_otra(c):
    pc = c.get("/api/periodos-carreras", headers=H).json()["periodos"]
    inf = next(x for x in pc if x["nombre_carrera"] == "Licenciatura en Informática")
    r = c.delete(f"/api/periodos/{inf['id_periodo']}", params={"id_carrera": inf["id_carrera"]}, headers=H)
    assert r.status_code == 200
    per = "2022 - PRIMER CUATRIMESTRE"
    b = c.get("/api/datos", params={"periodo": per, "carrera": "Licenciatura en Sistemas"}).json()
    assert libres_ingles(b) == 99                           # intacta
    assert [x["nombre"] for x in c.get("/api/carreras", params={"periodo": per}).json()["carreras"]] == ["Licenciatura en Sistemas"]
 
 
def test_10_borrar_ultima_carrera_borra_el_periodo_y_404(c):
    pc = c.get("/api/periodos-carreras", headers=H).json()["periodos"]
    assert len(pc) == 1
    c.delete(f"/api/periodos/{pc[0]['id_periodo']}", params={"id_carrera": pc[0]["id_carrera"]}, headers=H)
    assert c.get("/api/periodos").json()["periodos"] == []
    assert c.delete("/api/periodos/9999", headers=H).status_code == 404
 
 
def test_11_limpiar_db(c):
    subir(c, excel("023", "Licenciatura en Informática", 1, 1))
    assert c.delete("/api/limpiar-db", headers=H).status_code == 200
    assert c.get("/api/periodos").json() == {"periodos": []}
    # sigue funcionando después de vaciar (secuencias reiniciadas, FKs ok)
    assert subir(c, excel("023", "Licenciatura en Informática", 1, 1)).status_code == 201
 
 
def test_12_cors_solo_para_el_front(c):
    ok = c.options("/api/periodos", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    mal = c.options("/api/periodos", headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in mal.headers
 
 
def test_13_actividad_sin_codigo_se_informa_no_se_pierde_en_silencio(c):
    from app.db.loader import cargar_reporte
    datos = {
        "año_academico": 2023, "cuatrimestre": "PRIMER CUATRIMESTRE",
        "codigo_carrera": "023", "nombre_carrera": "Licenciatura en Informática",
        "actividades": [
            {"nombre": "Con código", "codigo_materia": "X1", "comisiones": []},
            {"nombre": "Sin código", "codigo_materia": None, "comisiones": []},
        ],
    }
    resumen = cargar_reporte(datos)
    assert resumen["actividades_omitidas"] == ["Sin código"]
    assert resumen["actividades_cargadas"] == 1


def token_de(c, usuario: str) -> dict:
    """Header Authorization con un JWT real del usuario precargado indicado."""
    r = c.post("/api/login", json={"usuario": usuario, "password": "Origone151"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_14_permisos_por_rol(c):
    """Matriz de permisos (app/api/permisos.py) aplicada a los endpoints."""
    import base64, json
    docente = token_de(c, "docente@unahur.edu.ar")
    no_docente = token_de(c, "nodocente@unahur.edu.ar")
    directivo = token_de(c, "directivo@unahur.edu.ar")

    # El JWT lleva el rol y los permisos para el frontend
    payload_b64 = no_docente["Authorization"].split(".")[1]
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
    assert payload["role"] == "no_docente" and payload["permisos"] == []

    # No Docente: solo ve
    assert subir(c, excel("030", "Tecnicatura X", 1, 1), headers=no_docente).status_code == 403
    assert c.delete("/api/periodos/1", headers=no_docente).status_code == 403
    assert c.get("/api/periodos").status_code == 200

    # Docente y Directivo cargan, pero no resetean la DB
    assert subir(c, excel("031", "Tecnicatura Docente", 1, 1), headers=docente).status_code == 201
    assert subir(c, excel("032", "Tecnicatura Directivo", 1, 1), headers=directivo).status_code == 201
    assert c.delete("/api/limpiar-db", headers=docente).status_code == 403
    assert c.delete("/api/limpiar-db", headers=directivo).status_code == 403

    # Solo el admin resetea
    assert c.delete("/api/limpiar-db", headers=H).status_code == 200


def _crear_docente(email: str) -> None:
    """Crea un segundo docente directo en la DB de prueba (el seed trae uno solo)."""
    from app.api.auth import hashear_password
    from app.db.connection import get_connection
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO Usuario (usuario, nombre, cargo, role, password_hash) "
            "VALUES (?, 'Otro Docente', 'Docente', 'docente', ?)",
            (email, hashear_password("Origone151")),
        )
    conn.close()


def _fila(c, headers, carrera):
    pc = c.get("/api/periodos-carreras", headers=headers).json()["periodos"]
    return next(x for x in pc if x["nombre_carrera"] == carrera)


def test_15_dueno_de_la_carga(c):
    _crear_docente("otro.docente@unahur.edu.ar")
    docente = token_de(c, "docente@unahur.edu.ar")
    otro = token_de(c, "otro.docente@unahur.edu.ar")
    directivo = token_de(c, "directivo@unahur.edu.ar")

    # periodos-carreras requiere login
    assert c.get("/api/periodos-carreras").status_code == 401

    # El docente carga dos carreras: queda como dueño
    assert subir(c, excel("040", "Carrera A", 5, 5), "a.xlsx", headers=docente).status_code == 201
    assert subir(c, excel("041", "Carrera B", 5, 5), "b.xlsx", headers=docente).status_code == 201
    fila_dueno = _fila(c, docente, "Carrera A")
    assert fila_dueno["cargado_por"] == "Docente" and fila_dueno["puede_borrar"] is True
    assert "dueno" not in fila_dueno                         # el email no se expone
    fila_otro = _fila(c, otro, "Carrera A")
    assert fila_otro["puede_borrar"] is False

    # Otro docente NO puede recargar, borrar la carrera ni borrar el período completo
    r = subir(c, excel("040", "Carrera A", 99, 1), headers=otro)
    assert r.status_code == 403
    assert libres_ingles(c.get("/api/datos", params={"periodo": "2022 - PRIMER CUATRIMESTRE",
                                                     "carrera": "Carrera A"}).json()) == 5  # intacta
    id_p, id_a = fila_dueno["id_periodo"], fila_dueno["id_carrera"]
    assert c.delete(f"/api/periodos/{id_p}", params={"id_carrera": id_a}, headers=otro).status_code == 403
    assert c.delete(f"/api/periodos/{id_p}", headers=otro).status_code == 403

    # El dueño sí puede recargar (la carga anterior queda 'reemplazada')
    assert subir(c, excel("040", "Carrera A", 7, 3), "a-v2.xlsx", headers=docente).status_code == 201

    # El directivo puede borrar cargas de otros
    assert c.delete(f"/api/periodos/{id_p}", params={"id_carrera": id_a}, headers=directivo).status_code == 200

    # El historial conserva todo: estado, archivo, quién y quién dio de baja
    from app.db.connection import get_connection
    conn = get_connection()
    filas = [dict(r) for r in conn.execute(
        "SELECT nombre_archivo, usuario, estado, dado_de_baja_por FROM Carga "
        "WHERE nombre_carrera = 'Carrera A' ORDER BY id_carga"
    ).fetchall()]
    conn.close()
    assert filas == [
        {"nombre_archivo": "a.xlsx", "usuario": "docente@unahur.edu.ar",
         "estado": "reemplazada", "dado_de_baja_por": "docente@unahur.edu.ar"},
        {"nombre_archivo": "a-v2.xlsx", "usuario": "docente@unahur.edu.ar",
         "estado": "borrada", "dado_de_baja_por": "directivo@unahur.edu.ar"},
    ]

    # El reset (admin) marca las activas como borradas pero conserva el historial
    assert c.delete("/api/limpiar-db", headers=H).status_code == 200
    conn = get_connection()
    activas = conn.execute("SELECT COUNT(*) FROM Carga WHERE estado = 'activa'").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM Carga").fetchone()[0]
    conn.close()
    assert activas == 0 and total > 0


def test_16_historial_de_cargas(c):
    docente = token_de(c, "docente@unahur.edu.ar")
    no_docente = token_de(c, "nodocente@unahur.edu.ar")
    directivo = token_de(c, "directivo@unahur.edu.ar")

    assert c.get("/api/cargas").status_code == 401                     # requiere login
    assert c.get("/api/cargas", headers=no_docente).status_code == 403  # No Docente no ve

    # Docente: solo las suyas
    d = c.get("/api/cargas", headers=docente).json()
    assert d["ve_todas"] is False and d["cargas"]
    assert {x["cargado_por"] for x in d["cargas"]} == {"Docente"}

    # Directivo: todas (incluye las del docente y las del admin)
    t = c.get("/api/cargas", headers=directivo).json()
    assert t["ve_todas"] is True
    assert {"Docente", "Admin"} <= {x["cargado_por"] for x in t["cargas"]}
    assert len(t["cargas"]) > len(d["cargas"])

    # Orden: la más reciente primero, con fecha ISO y nombre de archivo original
    ids = [x["id_carga"] for x in t["cargas"]]
    assert ids == sorted(ids, reverse=True)
    reemplazada = next(x for x in t["cargas"] if x["nombre_archivo"] == "a.xlsx")
    assert reemplazada["estado"] == "reemplazada" and reemplazada["fecha"].endswith("+00:00")
    borrada = next(x for x in t["cargas"] if x["nombre_archivo"] == "a-v2.xlsx")
    assert borrada["dado_de_baja_por"] == "Directivo"                   # nombre, no email

    # Filtro por estado
    solo_borradas = c.get("/api/cargas", params={"estado": "borrada"}, headers=directivo).json()["cargas"]
    assert solo_borradas and {x["estado"] for x in solo_borradas} == {"borrada"}
    assert c.get("/api/cargas", params={"estado": "otro"}, headers=directivo).status_code == 422


def test_17_institutos_y_seed(c, monkeypatch):
    from app.db import seed

    # El selector del registro recibe solo id y nombre (sin emails, endpoint público)
    r = c.get("/api/institutos")
    assert r.status_code == 200
    institutos = r.json()["institutos"]
    assert [i["nombre"] for i in institutos] == [
        "Tecnología e Ingeniería", "Salud Comunitaria", "Educación", "Biotecnología",
    ]
    assert all(set(i) == {"id", "nombre"} for i in institutos)
    assert "@" not in r.text
    assert c.get("/api/directivos").status_code == 404           # endpoint viejo eliminado

    # Cambiar un nombre en seed.py se aplica al reiniciar (antes se ignoraba)
    monkeypatch.setattr(seed, "_INSTITUTOS", [("Ingeniería", "ingenieria@unahur.edu.ar")] + seed._INSTITUTOS[1:])
    seed.seed_db()
    assert c.get("/api/institutos").json()["institutos"][0]["nombre"] == "Ingeniería"

    # Un rol inválido en el seed frena el arranque con un mensaje claro
    # (antes INSERT OR IGNORE lo salteaba en silencio y el usuario no existía)
    roto = [(u, n, cg, "Directivo" if r == "directivo" else r) for u, n, cg, r in seed._USUARIOS]
    monkeypatch.setattr(seed, "_USUARIOS", roto)
    with pytest.raises(ValueError, match="rol 'Directivo' inválido para directivo@unahur.edu.ar"):
        seed.seed_db()


def test_18_historial_indica_que_se_puede_borrar(c):
    """La página Cargas borra desde el historial: cada fila trae ids y puede_borrar."""
    _crear_docente("otro.docente@unahur.edu.ar")
    docente = token_de(c, "docente@unahur.edu.ar")
    otro = token_de(c, "otro.docente@unahur.edu.ar")
    directivo = token_de(c, "directivo@unahur.edu.ar")

    assert subir(c, excel("050", "Carrera H", 5, 5), "h.xlsx", headers=docente).status_code == 201
    assert subir(c, excel("050", "Carrera H", 6, 4), "h-v2.xlsx", headers=docente).status_code == 201

    def fila(headers, archivo):
        return next(x for x in c.get("/api/cargas", headers=headers).json()["cargas"]
                    if x["nombre_archivo"] == archivo)

    activa = fila(docente, "h-v2.xlsx")
    assert activa["estado"] == "activa" and activa["puede_borrar"] is True
    assert {"id_periodo", "id_carrera"} <= set(activa) and "dueno" not in activa
    assert fila(docente, "h.xlsx")["puede_borrar"] is False             # reemplazada: no se borra
    assert fila(directivo, "h-v2.xlsx")["puede_borrar"] is True         # directivo: cualquiera
    assert not any(x["nombre_archivo"] == "h-v2.xlsx"                   # otro docente no la ve
                   for x in c.get("/api/cargas", headers=otro).json()["cargas"])

    # Borrar con los ids del historial
    r = c.delete(f"/api/periodos/{activa['id_periodo']}",
                 params={"id_carrera": activa["id_carrera"]}, headers=docente)
    assert r.status_code == 200
    borrada = fila(docente, "h-v2.xlsx")
    assert borrada["estado"] == "borrada" and borrada["puede_borrar"] is False


def test_19_nueva_version_de_una_carga(c):
    docente = token_de(c, "docente@unahur.edu.ar")
    assert subir(c, excel("060", "Carrera V", 5, 5), "v1.xlsx", headers=docente).status_code == 201

    def carga(archivo):
        return next(x for x in c.get("/api/cargas", headers=docente).json()["cargas"]
                    if x["nombre_archivo"] == archivo)

    v1 = carga("v1.xlsx")

    def nueva_version(data, nombre, id_carga):
        return c.post("/upload", params={"reemplaza": id_carga},
                      files={"archivo": (nombre, data)}, headers=docente)

    # Excel de OTRA carrera: se rechaza y no se crea nada
    r = nueva_version(excel("061", "Carrera W", 1, 1), "w.xlsx", v1["id_carga"])
    assert r.status_code == 422 and "Carrera W" in r.json()["detail"] and "Carrera V" in r.json()["detail"]
    nombres = {x["nombre_archivo"] for x in c.get("/api/cargas", headers=docente).json()["cargas"]}
    assert "w.xlsx" not in nombres
    assert carga("v1.xlsx")["estado"] == "activa"

    # Mismo período + carrera: reemplaza
    assert nueva_version(excel("060", "Carrera V", 9, 1), "v2.xlsx", v1["id_carga"]).status_code == 201
    assert carga("v1.xlsx")["estado"] == "reemplazada"
    assert carga("v2.xlsx")["estado"] == "activa"

    # La carga reemplazada ya no se puede usar como referencia
    assert nueva_version(excel("060", "Carrera V", 1, 1), "v3.xlsx", v1["id_carga"]).status_code == 409
    assert nueva_version(excel("060", "Carrera V", 1, 1), "v3.xlsx", 999999).status_code == 409


def test_20_carga_activa_para_el_dashboard(c):
    directivo = token_de(c, "directivo@unahur.edu.ar")
    no_docente = token_de(c, "nodocente@unahur.edu.ar")
    assert subir(c, excel("070", "Carrera O", 5, 5), "origen.xlsx", headers=directivo).status_code == 201
    params = {"periodo": "2022 - PRIMER CUATRIMESTRE", "carrera": "Carrera O"}

    # Requiere login (el invitado no ve quién cargó)
    assert c.get("/api/carga-activa", params=params).status_code == 401

    # Cualquier usuario logueado la ve, aunque no tenga permisos de carga
    r = c.get("/api/carga-activa", params=params, headers=no_docente)
    assert r.status_code == 200
    carga = r.json()["carga"]
    assert carga["nombre_archivo"] == "origen.xlsx" and carga["cargado_por"] == "Directivo"
    assert set(carga) == {"id_carga", "fecha", "nombre_archivo", "cargado_por"}   # sin emails

    # Sin carga activa → null
    sin = c.get("/api/carga-activa", params={**params, "carrera": "No existe"}, headers=no_docente)
    assert sin.status_code == 200 and sin.json() == {"carga": None}


def test_21_evolucion_entre_periodos(c):
    # Misma carrera en dos períodos (y la segunda carga no pisa la primera)
    assert subir(c, excel("080", "Carrera E", libres=10, promo=30), "e22.xlsx").status_code == 201
    assert subir(c, excel("080", "Carrera E", libres=25, promo=15, anio=2023,
                          cuat="PRIMER CUATRIMESTRE 2023"), "e23.xlsx").status_code == 201

    r = c.get("/api/evolucion", params={"carrera": "Carrera E"})   # público
    assert r.status_code == 200, r.text
    d = r.json()
    assert [m["codigo"] for m in d["materias"]] == ["004", "007"]  # Inglés I, Programación I
    assert [p["label"] for p in d["periodos"]] == ["2022 - PRIMER CUATRIMESTRE", "2023 - PRIMER CUATRIMESTRE"]

    def estados(p):
        return {e["estado"]: e["total_alumnos"] for e in p["estados"]}

    # Toda la carrera: Inglés (libres/promo) + Programación (3 libres, 3 regulares)
    assert estados(d["periodos"][0]) == {"Libre": 13, "Promocionó": 30, "Regular": 3}
    assert estados(d["periodos"][1]) == {"Libre": 28, "Promocionó": 15, "Regular": 3}
    assert d["periodos"][0]["comisiones"] == 2

    # Una sola materia
    m = c.get("/api/evolucion", params={"carrera": "Carrera E", "materia": "004"}).json()
    assert [estados(p) for p in m["periodos"]] == [{"Libre": 10, "Promocionó": 30}, {"Libre": 25, "Promocionó": 15}]
    assert all(p["comisiones"] == 1 for p in m["periodos"])

    # Carrera sin datos
    assert c.get("/api/evolucion", params={"carrera": "No existe"}).json() == {"materias": [], "periodos": []}


# ---------------------------------------------------------------------------
# Solicitudes de registro y recuperación de contraseña
# ---------------------------------------------------------------------------

CLAVE_OK = "Nueva#Clave1"


def _pedido_registro(email, **cambios):
    datos = {"email": email, "nombre": "Ana Pérez", "password": CLAVE_OK, "rol": "docente", "id_instituto": 1}
    datos.update(cambios)
    return datos


def test_22_solicitud_de_registro_valida_y_se_aprueba(c):
    pedir = lambda **kw: c.post("/api/registro/solicitar", json=_pedido_registro(**kw))

    # Correo: solo @unahur.edu.ar con parte local
    for malo in ("ana@gmail.com", "@unahur.edu.ar", "a@b.com@unahur.edu.ar", "sin-arroba", "a b@unahur.edu.ar"):
        assert pedir(email=malo).status_code == 400, malo
    # Contraseña: 8+ caracteres con mayúscula, minúscula, número y símbolo
    for mala in ("Ab#1", "sinmayuscula#1", "SINMINUSCULA#1", "SinNumero#abc", "SinSimbolo123"):
        assert pedir(email="ana@unahur.edu.ar", password=mala).status_code == 400, mala
    assert pedir(email="ana@unahur.edu.ar", nombre="  ").status_code == 400
    assert pedir(email="ana@unahur.edu.ar", rol="admin").status_code == 400
    assert pedir(email="ana@unahur.edu.ar", id_instituto=999).status_code == 400

    assert pedir(email="Ana@UNAHUR.edu.ar").status_code == 201      # se normaliza a minúsculas
    assert pedir(email="ana@unahur.edu.ar").status_code == 409      # ya hay una pendiente
    assert pedir(email="admin@unahur.edu.ar").status_code == 409    # ya es usuario

    # Solo quien tiene registros:aprobar ve y resuelve las solicitudes
    assert c.get("/api/registro/solicitudes").status_code == 401
    assert c.get("/api/registro/solicitudes", headers=token_de(c, "docente@unahur.edu.ar")).status_code == 403
    pendientes = c.get("/api/registro/solicitudes", headers=H).json()["solicitudes"]
    sol = next(s for s in pendientes if s["email"] == "ana@unahur.edu.ar")
    r = c.post(f"/api/registro/solicitudes/{sol['id_solicitud']}/aprobar", headers=H)
    assert r.status_code == 200, r.text
    assert c.post("/api/login", json={"usuario": "ana@unahur.edu.ar", "password": CLAVE_OK}).status_code == 200


def _pedir_recuperacion(c, usuario):
    return c.post("/api/recuperar-password/solicitar", json={"usuario": usuario})


def _aprobar_recuperacion(c, headers, usuario):
    """Aprueba la solicitud pendiente del usuario y devuelve la respuesta."""
    lista = c.get("/api/recuperacion/solicitudes", headers=headers).json()["solicitudes"]
    sol = next(s for s in lista if s["usuario"] == usuario)
    return c.post(f"/api/recuperacion/solicitudes/{sol['id_solicitud']}/aprobar", headers=headers)


def test_23_recuperacion_de_contrasena_por_solicitud(c):
    canjear = lambda usuario, codigo, clave: c.post(
        "/api/recuperar-password/canjear", json={"usuario": usuario, "codigo": codigo, "nueva_password": clave}
    )
    # Responde igual exista o no el correo (no revela qué cuentas existen)
    existe = _pedir_recuperacion(c, "docente@unahur.edu.ar")
    no_existe = _pedir_recuperacion(c, "nadie@unahur.edu.ar")
    assert existe.status_code == no_existe.status_code == 200
    assert existe.json() == no_existe.json()
    # Los endpoints viejos, sin ninguna verificación, ya no existen
    assert c.post("/api/recuperar-password/cambiar", json={}).status_code == 404
    assert c.post("/api/recuperar-password/verificar", json={}).status_code == 404

    # Solo ve y resuelve quien tiene registros:aprobar
    assert c.get("/api/recuperacion/solicitudes").status_code == 401
    assert c.get("/api/recuperacion/solicitudes", headers=token_de(c, "docente@unahur.edu.ar")).status_code == 403

    # Sin aprobar no hay código: no se puede cambiar la contraseña
    assert canjear("docente@unahur.edu.ar", "ABCD-EFGH", CLAVE_OK).status_code == 400

    r = _aprobar_recuperacion(c, H, "docente@unahur.edu.ar")
    assert r.status_code == 200, r.text
    codigo = r.json()["codigo"]
    assert len(codigo) == 9 and r.json()["expira_en"]

    # Código incorrecto, contraseña débil y contraseña igual a la anterior se rechazan
    assert canjear("docente@unahur.edu.ar", "XXXX-XXXX", CLAVE_OK).status_code == 400
    assert canjear("docente@unahur.edu.ar", codigo, "debil").status_code == 400
    assert canjear("docente@unahur.edu.ar", codigo, "Origone151").status_code == 400   # la actual
    # El código de otra cuenta no sirve
    assert canjear("nodocente@unahur.edu.ar", codigo, CLAVE_OK).status_code == 400

    # Con el código correcto (en minúsculas y sin guion también vale) se cambia, una sola vez
    ok = canjear("DOCENTE@unahur.edu.ar", codigo.replace("-", "").lower(), CLAVE_OK)
    assert ok.status_code == 200, ok.text
    assert c.post("/api/login", json={"usuario": "docente@unahur.edu.ar", "password": CLAVE_OK}).status_code == 200
    assert c.post("/api/login", json={"usuario": "docente@unahur.edu.ar", "password": "Origone151"}).status_code == 401
    assert canjear("docente@unahur.edu.ar", codigo, "Otra#Clave22").status_code == 400


def test_24_recuperacion_reglas_de_quien_aprueba(c):
    directivo = token_de(c, "directivo@unahur.edu.ar")
    # Una solicitud de un Directivo no la ve ni la aprueba otro Directivo: solo un Admin
    _pedir_recuperacion(c, "directivo@unahur.edu.ar")
    visibles = c.get("/api/recuperacion/solicitudes", headers=directivo).json()["solicitudes"]
    assert all(s["usuario"] != "directivo@unahur.edu.ar" for s in visibles)
    en_admin = c.get("/api/recuperacion/solicitudes", headers=H).json()["solicitudes"]
    sol = next(s for s in en_admin if s["usuario"] == "directivo@unahur.edu.ar")
    # Nadie aprueba la propia
    assert c.post(f"/api/recuperacion/solicitudes/{sol['id_solicitud']}/aprobar", headers=directivo).status_code == 403
    # Un Directivo no aprueba la de un Admin
    _pedir_recuperacion(c, "admin@unahur.edu.ar")
    sol_admin = next(s for s in c.get("/api/recuperacion/solicitudes", headers=H).json()["solicitudes"]
                     if s["usuario"] == "admin@unahur.edu.ar")
    assert c.post(f"/api/recuperacion/solicitudes/{sol_admin['id_solicitud']}/aprobar", headers=directivo).status_code == 403
    assert c.post(f"/api/recuperacion/solicitudes/{sol_admin['id_solicitud']}/aprobar", headers=H).status_code == 403  # la propia
    # Pero un Admin sí aprueba la de un Directivo, y rechazar cierra la solicitud
    assert c.post(f"/api/recuperacion/solicitudes/{sol['id_solicitud']}/rechazar", headers=H).status_code == 200
    assert c.post(f"/api/recuperacion/solicitudes/{sol['id_solicitud']}/aprobar", headers=H).status_code == 404


def test_25_codigo_se_bloquea_tras_cinco_intentos(c):
    canjear = lambda codigo: c.post(
        "/api/recuperar-password/canjear",
        json={"usuario": "nodocente@unahur.edu.ar", "codigo": codigo, "nueva_password": CLAVE_OK},
    )
    _pedir_recuperacion(c, "nodocente@unahur.edu.ar")
    codigo = _aprobar_recuperacion(c, H, "nodocente@unahur.edu.ar").json()["codigo"]
    for _ in range(5):
        assert canjear("ZZZZ-ZZZZ").status_code == 400
    # Agotados los intentos, ni el código correcto sirve: hay que pedir otro
    assert canjear(codigo).status_code == 400

def token_de_con(c, usuario: str, clave: str) -> dict:
    """Header Authorization con un JWT real del usuario y la contraseña indicados."""
    r = c.post("/api/login", json={"usuario": usuario, "password": clave})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_26_mi_cuenta_perfil_y_cambio_de_contrasena(c):
    login = lambda usuario, clave: c.post("/api/login", json={"usuario": usuario, "password": clave})
    cambiar = lambda headers, actual, nueva: c.post(
        "/api/perfil/cambiar-password", headers=headers, json={"password_actual": actual, "password_nueva": nueva}
    )
    # Sin sesión no hay perfil ni cambio
    assert c.get("/api/perfil").status_code == 401
    assert c.post("/api/perfil/cambiar-password", json={"password_actual": "x", "password_nueva": "y"}).status_code == 401

    # Cuenta precargada: datos del usuario y sin instituto
    perfil = c.get("/api/perfil", headers=H).json()
    assert perfil == {
        "usuario": "admin@unahur.edu.ar", "nombre": "Admin", "cargo": "Desarrollador",
        "role": "admin", "instituto": None,
    }

    # Cuenta registrada por solicitud (test 22): trae el instituto que eligió
    ana = token_de_con(c, "ana@unahur.edu.ar", CLAVE_OK)
    perfil_ana = c.get("/api/perfil", headers=ana).json()
    assert perfil_ana["usuario"] == "ana@unahur.edu.ar"
    assert perfil_ana["role"] == "docente"
    nombre_instituto = next(i["nombre"] for i in c.get("/api/institutos").json()["institutos"] if i["id"] == 1)
    assert perfil_ana["instituto"] == nombre_instituto
    assert "password_hash" not in perfil_ana

    # Contraseña actual incorrecta: 400 (no 401, que cerraría la sesión en el frontend)
    assert cambiar(ana, "Incorrecta#1", "Otra#Clave22").status_code == 400
    # La nueva tiene que cumplir la política y ser distinta de la actual
    for mala in ("debil", "sinmayuscula#1", "SINMINUSCULA#1", "SinNumero#abc", "SinSimbolo123"):
        assert cambiar(ana, CLAVE_OK, mala).status_code == 400, mala
    assert cambiar(ana, CLAVE_OK, CLAVE_OK).status_code == 400

    # Cambio válido: la vieja deja de servir y la nueva sí
    ok = cambiar(ana, CLAVE_OK, "Otra#Clave22")
    assert ok.status_code == 200, ok.text
    assert login("ana@unahur.edu.ar", CLAVE_OK).status_code == 401
    assert login("ana@unahur.edu.ar", "Otra#Clave22").status_code == 200

def test_27_cambio_de_contrasena_se_bloquea_tras_cinco_intentos(c):
    from app.db.connection import get_connection

    # Cuenta nueva por solicitud, para no tocar las precargadas
    assert c.post("/api/registro/solicitar", json=_pedido_registro("luis@unahur.edu.ar")).status_code == 201
    sol = next(s for s in c.get("/api/registro/solicitudes", headers=H).json()["solicitudes"]
               if s["email"] == "luis@unahur.edu.ar")
    assert c.post(f"/api/registro/solicitudes/{sol['id_solicitud']}/aprobar", headers=H).status_code == 200
    luis = token_de_con(c, "luis@unahur.edu.ar", CLAVE_OK)
    cambiar = lambda actual: c.post(
        "/api/perfil/cambiar-password", headers=luis,
        json={"password_actual": actual, "password_nueva": "Otra#Clave22"},
    )

    # Cuatro errores avisan cuántos intentos quedan; el quinto bloquea
    for restantes in (4, 3, 2, 1):
        r = cambiar("Incorrecta#1")
        assert r.status_code == 400
        assert f"Te quedan {restantes}" in r.json()["detail"]
    assert cambiar("Incorrecta#1").status_code == 429
    # Bloqueada, ni la contraseña correcta sirve
    assert cambiar(CLAVE_OK).status_code == 429
    assert c.post("/api/login", json={"usuario": "luis@unahur.edu.ar", "password": CLAVE_OK}).status_code == 200

    # Vencido el bloqueo se puede volver a intentar
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE Usuario SET bloqueo_password_hasta = '2000-01-01T00:00:00+00:00' WHERE usuario = ?",
                ("luis@unahur.edu.ar",),
            )
    finally:
        conn.close()
    assert cambiar(CLAVE_OK).status_code == 200
    assert c.post("/api/login", json={"usuario": "luis@unahur.edu.ar", "password": "Otra#Clave22"}).status_code == 200


def test_28_migracion_agrega_columnas_de_usuario_y_conserva_el_instituto():
    import sqlite3

    from app.db.init_db import migrar

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Esquema anterior: Usuario sin id_directivo ni columnas de intentos
    conn.executescript(
        """
        CREATE TABLE Directivo (id_directivo INTEGER PRIMARY KEY, nombre TEXT, email TEXT);
        CREATE TABLE Usuario (id_usuario INTEGER PRIMARY KEY, usuario TEXT, nombre TEXT, cargo TEXT,
                              role TEXT, password_hash TEXT);
        CREATE TABLE Solicitud_Registro (id_solicitud INTEGER PRIMARY KEY, email TEXT, estado TEXT,
                                         id_directivo INTEGER);
        INSERT INTO Directivo VALUES (2, 'Salud Comunitaria', 'salud@unahur.edu.ar');
        INSERT INTO Usuario (usuario, nombre, cargo, role, password_hash) VALUES
            ('ana@unahur.edu.ar', 'Ana', 'Docente', 'docente', 'x'),
            ('admin@unahur.edu.ar', 'Admin', 'Desarrollador', 'admin', 'x');
        INSERT INTO Solicitud_Registro VALUES (1, 'ana@unahur.edu.ar', 'aprobada', 2);
        """
    )
    migrar(conn)
    migrar(conn)    # idempotente: la segunda corrida no falla ni duplica nada
    filas = {f["usuario"]: f for f in conn.execute("SELECT * FROM Usuario")}
    assert filas["ana@unahur.edu.ar"]["id_directivo"] == 2
    assert filas["admin@unahur.edu.ar"]["id_directivo"] is None
    assert filas["ana@unahur.edu.ar"]["intentos_password"] == 0
    assert filas["ana@unahur.edu.ar"]["activo"] == 1     # las cuentas existentes siguen activas
    assert filas["ana@unahur.edu.ar"]["bloqueo_password_hasta"] is None

def test_29_gestion_de_usuarios_solo_admin(c):
    estado = lambda usuario, activo, headers=H: c.post(
        f"/api/usuarios/{usuario}/estado", headers=headers, json={"activo": activo}
    )
    rol = lambda usuario, nuevo, headers=H: c.post(
        f"/api/usuarios/{usuario}/rol", headers=headers, json={"rol": nuevo}
    )

    # Solo quien tiene usuarios:gestionar (el Admin)
    assert c.get("/api/usuarios").status_code == 401
    assert c.get("/api/usuarios", headers=token_de(c, "directivo@unahur.edu.ar")).status_code == 403
    assert c.get("/api/usuarios", headers=token_de_con(c, "docente@unahur.edu.ar", CLAVE_OK)).status_code == 403
    assert rol("luis@unahur.edu.ar", "docente", token_de(c, "directivo@unahur.edu.ar")).status_code == 403

    # La lista trae las cuentas con rol, instituto y estado, y nunca el hash
    lista = c.get("/api/usuarios", headers=H).json()["usuarios"]
    luis_fila = next(u for u in lista if u["usuario"] == "luis@unahur.edu.ar")
    assert luis_fila["activo"] is True and luis_fila["role"] == "docente" and luis_fila["instituto"]
    assert all("password_hash" not in u for u in lista)

    # Validaciones de rol y de cuenta
    assert rol("luis@unahur.edu.ar", "superusuario").status_code == 400
    assert rol("nadie@unahur.edu.ar", "docente").status_code == 404
    assert estado("nadie@unahur.edu.ar", False).status_code == 404
    # Nadie se modifica a sí mismo
    assert rol("admin@unahur.edu.ar", "docente").status_code == 403
    assert estado("admin@unahur.edu.ar", False).status_code == 403

    # Cambiar el rol rige de inmediato, aunque el token de Luis siga diciendo "docente"
    luis = token_de_con(c, "luis@unahur.edu.ar", "Otra#Clave22")
    assert c.get("/api/registro/solicitudes", headers=luis).status_code == 403
    assert rol("luis@unahur.edu.ar", "directivo").status_code == 200
    assert c.get("/api/registro/solicitudes", headers=luis).status_code == 200
    assert next(u for u in c.get("/api/usuarios", headers=H).json()["usuarios"]
                if u["usuario"] == "luis@unahur.edu.ar")["cargo"] == "Directivo"
    assert rol("luis@unahur.edu.ar", "docente").status_code == 200

    # Revocar: no puede iniciar sesión y su sesión abierta deja de servir
    assert estado("luis@unahur.edu.ar", False).status_code == 200
    asercion_login = c.post("/api/login", json={"usuario": "luis@unahur.edu.ar", "password": "Otra#Clave22"})
    assert asercion_login.status_code == 403
    assert c.post("/api/login", json={"usuario": "luis@unahur.edu.ar", "password": "Incorrecta#1"}).status_code == 401
    assert c.get("/api/perfil", headers=luis).status_code == 401

    # Reactivar: vuelve a entrar
    assert estado("luis@unahur.edu.ar", True).status_code == 200
    assert c.get("/api/perfil", headers=luis).status_code == 200
    assert c.post("/api/login", json={"usuario": "luis@unahur.edu.ar", "password": "Otra#Clave22"}).status_code == 200


def test_30_historial_de_solicitudes(c):
    pedir = lambda email, instituto: c.post(
        "/api/registro/solicitar", json=_pedido_registro(email, id_instituto=instituto)
    )
    pendientes = lambda: c.get("/api/registro/solicitudes", headers=H).json()["solicitudes"]
    historial = lambda headers: c.get("/api/registro/historial", headers=headers)

    assert historial({}).status_code == 401
    assert historial(token_de_con(c, "docente@unahur.edu.ar", CLAVE_OK)).status_code == 403

    # Una solicitud rechazada queda en el historial (ya no se borra)
    assert pedir("rechazada@unahur.edu.ar", 2).status_code == 201
    sol = next(s for s in pendientes() if s["email"] == "rechazada@unahur.edu.ar")
    assert c.post(f"/api/registro/solicitudes/{sol['id_solicitud']}/rechazar", headers=H).status_code == 200
    fila = next(s for s in historial(H).json()["solicitudes"] if s["email"] == "rechazada@unahur.edu.ar")
    assert fila["estado"] == "rechazada"
    assert fila["resuelto_por"] == "admin@unahur.edu.ar" and fila["nombre_resuelto_por"] == "Admin"
    assert fila["fecha_resolucion"]

    # El Admin ve también las aprobadas (Ana, del test 22)
    todas = historial(H).json()["solicitudes"]
    assert next(s for s in todas if s["email"] == "ana@unahur.edu.ar")["estado"] == "aprobada"
    assert all(s["estado"] in ("aprobada", "rechazada") for s in todas)

    # Un Directivo ve solo las de su instituto: Ana pidió el 1; la rechazada, el 2
    del_directivo = historial(token_de(c, "directivo@unahur.edu.ar")).json()["solicitudes"]
    correos = {s["email"] for s in del_directivo}
    assert "ana@unahur.edu.ar" in correos
    assert "rechazada@unahur.edu.ar" not in correos

    # Tras un rechazo se puede volver a pedir, y la nueva queda pendiente (no en el historial)
    assert pedir("rechazada@unahur.edu.ar", 2).status_code == 201
    assert any(s["email"] == "rechazada@unahur.edu.ar" for s in pendientes())
    assert all(s["email"] != "rechazada@unahur.edu.ar" for s in historial(H).json()["solicitudes"])
