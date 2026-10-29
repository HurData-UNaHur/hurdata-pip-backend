"""
pipeline.py
===========
Responsabilidad: orquestar las tres etapas del ETL en orden:
    1. Extract  → ExcelExtractor lee el archivo y devuelve el DataFrame crudo.
    2. Transform → ExcelTransformer estructura los datos en un dict jerárquico.
    3. Load     → cargar_reporte() persiste el dict en SQLite de forma acumulativa y selectiva.

Uso directo (debug/carga manual):
    python -m app.etl.pipeline
"""

from pathlib import Path

from app.etl.extractor import ExcelExtractor
from app.etl.transformer import ExcelTransformer
from app.db.loader import cargar_reporte
from app.db.init_db import init_db
from app.config import config


def ejecutar_etl(ruta_excel: Path | None = None) -> dict:
    """
    Ejecuta el pipeline ETL completo: Extract → Transform → Load.

    Args:
        ruta_excel: ruta al archivo .xlsx a procesar. Si es None, usa el
                    valor configurado en .env (EXCEL_SIU_FILENAME).

    Returns:
        dict con el resumen de la carga devuelto por cargar_reporte().
    """
    if ruta_excel is None:
        ruta_excel = (
            Path(__file__).resolve().parent.parent.parent
            / "files"
            / config.EXCEL_SIU_FILENAME
        )

    print(f"[ETL] Procesando: {ruta_excel.name}")

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
    # 3. LOAD — inicializar esquema si no existe y persistir en SQLite
    # ------------------------------------------------------------------
    init_db()  # Crea las tablas si no existen sin borrar los datos acumulados
    resumen = cargar_reporte(datos)  # Reemplaza únicamente el período procesado

    return resumen


# Alias de compatibilidad — mantiene el nombre original por si hay imports externos
def ejecutar_etl_base() -> dict:
    return ejecutar_etl()


if __name__ == "__main__":
    resumen = ejecutar_etl_base()
    print("\n--- Resumen de la carga ---")
    for clave, valor in resumen.items():
        print(f"  {clave}: {valor}")