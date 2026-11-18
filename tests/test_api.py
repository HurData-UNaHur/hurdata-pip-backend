
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
