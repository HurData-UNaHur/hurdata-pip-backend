"""
pipeline.py
===========
Responsabilidad: orquestar las tres etapas del ETL en orden:
    1. Extract  → ExcelExtractor lee el archivo y devuelve el DataFrame crudo.
    2. Transform → ExcelTransformer estructura los datos en un dict jerárquico.
    3. Load      → (pendiente) ExcelLoader insertará los datos en SQLite.

También incluye un paso de debug: exporta el resultado a JSON en /files
para verificar visualmente el output antes de implementar la capa de DB.
Este archivo JSON es TEMPORAL y no forma parte del flujo de producción.
"""

import json
from pathlib import Path

from app.etl.extractor import ExcelExtractor
from app.etl.transformer import ExcelTransformer
from app.config import config


def ejecutar_etl_base():
    """
    Ejecuta el pipeline ETL completo sobre el Excel configurado en .env.

    Flujo actual (MVP):
        Excel → DataFrame crudo → dict estructurado → JSON de debug en /files

    Flujo futuro (post-MVP):
        Excel → DataFrame crudo → dict estructurado → INSERT en SQLite
    """
    ruta_excel = Path(__file__).resolve().parent.parent.parent / "files" / config.EXCEL_SIU_FILENAME
    ruta_json_debug = ruta_excel.parent / "output_debug.json"

    try:
        # ------------------------------------------------------------------
        # 1. EXTRACCIÓN
        # ------------------------------------------------------------------
        extractor = ExcelExtractor(ruta_excel)
        df_raw = extractor.extraer()

        # ------------------------------------------------------------------
        # 2. TRANSFORMACIÓN
        # ------------------------------------------------------------------
        transformer = ExcelTransformer()
        datos = transformer.estructurar_a_json(df_raw)

        # ------------------------------------------------------------------
        # 3. DEBUG — exportar JSON a /files para verificación manual
        #    TODO: reemplazar este bloque por el Loader de SQLite cuando
        #          la capa de DB esté implementada.
        # ------------------------------------------------------------------
        with open(ruta_json_debug, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)

        print(f"[DEBUG]  JSON de verificación guardado en: {ruta_json_debug.name}")

        # Preview rápido en consola
        print(f"\n--- Resumen del resultado ---")
        print(f"  Año académico : {datos.get('año_academico')}")
        print(f"  Cuatrimestre  : {datos.get('cuatrimestre')}")
        print(f"  Carrera       : {datos.get('nombre_carrera')}")
        print(f"  Actividades   : {len(datos.get('actividades', []))}")
        primera = datos["actividades"][0] if datos.get("actividades") else None
        if primera:
            print(f"\n  Primera actividad: '{primera['nombre']}' (cod: {primera['codigo_materia']})")
            print(f"  Comisiones: {len(primera['comisiones'])}")
            primera_com = primera["comisiones"][0] if primera["comisiones"] else None
            if primera_com:
                print(f"  Primera comisión: {primera_com['nombre_completo']} | modalidad: {primera_com['modalidad']}")
                print(f"  Estados:")
                for e in primera_com["estados"]:
                    print(f"    - {e['estado']}: {e['total_alumnos']} alumnos")

    except Exception as e:
        print(f"\n[ERROR] Pipeline fallido: {e}")
        raise


if __name__ == "__main__":
    ejecutar_etl_base()
