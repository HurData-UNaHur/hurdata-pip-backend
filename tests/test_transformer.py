import pytest

from app.etl.transformer import ExcelTransformer

# Los tres formatos de cabecera que aparecen en el Excel real del SIU.
CASOS = [
    ("Comisión (004)-COMISIÓN 1-COMBINADA",          "004",   1, "Combinada", "COMISIÓN 1-COMBINADA"),
    ("Comisión AU_48-COMISIÓN 1-VIRTUAL",            "AU_48", 1, "Virtual",   "COMISIÓN 1-VIRTUAL"),
    ("Comisión AU_49-COMISIÓN 1-VIRTUAL-SABADOS",    "AU_49", 1, "Virtual",   "COMISIÓN 1-VIRTUAL-SABADOS"),
    ("Comisión (AU_40) COMISIÓN 1 - VIRTUAL",        "AU_40", 1, "Virtual",   "COMISIÓN 1 - VIRTUAL"),
    ("Comisión (AU_13)-COMISIÓN 12-PRESENCIAL",      "AU_13", 12, "Presencial", "COMISIÓN 12-PRESENCIAL"),
]


@pytest.mark.parametrize("texto,codigo,numero,modalidad,nombre", CASOS)
def test_parsear_comision(texto, codigo, numero, modalidad, nombre):
    r = ExcelTransformer()._parsear_comision(texto)
    assert r["codigo_materia"] == codigo
    assert r["numero_comision"] == numero
    assert r["modalidad"] == modalidad
    assert r["nombre_completo"] == nombre