
import io, os, tempfile
from pathlib import Path
 
# La DB de prueba y la API key se definen ANTES de importar la app.
_tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = str(Path(_tmp) / "test.db")
os.environ["ADMIN_API_KEY"] = "secreta"
 
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
 
from app.api.main import app
 
H = {"X-API-Key": "secreta"}
 
 
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
    pc = c.get("/api/periodos-carreras").json()["periodos"]
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
    assert subir(c, excel("023", "L", 1, 1), headers={}).status_code == 401
    assert c.delete("/api/limpiar-db").status_code == 401
    assert c.delete("/api/limpiar-db", headers={"X-API-Key": "mala"}).status_code == 401
    assert c.get("/api/periodos").status_code == 200       # lecturas siguen públicas
 
 
def test_09_borrar_una_carrera_no_toca_la_otra(c):
    pc = c.get("/api/periodos-carreras").json()["periodos"]
    inf = next(x for x in pc if x["nombre_carrera"] == "Licenciatura en Informática")
    r = c.delete(f"/api/periodos/{inf['id_periodo']}", params={"id_carrera": inf["id_carrera"]}, headers=H)
    assert r.status_code == 200
    per = "2022 - PRIMER CUATRIMESTRE"
    b = c.get("/api/datos", params={"periodo": per, "carrera": "Licenciatura en Sistemas"}).json()
    assert libres_ingles(b) == 99                           # intacta
    assert [x["nombre"] for x in c.get("/api/carreras", params={"periodo": per}).json()["carreras"]] == ["Licenciatura en Sistemas"]
 
 
def test_10_borrar_ultima_carrera_borra_el_periodo_y_404(c):
    pc = c.get("/api/periodos-carreras").json()["periodos"]
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