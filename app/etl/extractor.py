"""
extractor.py
============
Responsabilidad: leer el archivo Excel crudo del SIU Guaraní y devolver un
DataFrame de pandas con la estructura original intacta (header=None).

NO hace transformaciones de datos — eso es trabajo del Transformer.
Su única responsabilidad estructural es detectar dónde empieza el header real
y devolver el DataFrame completo sin descartar nada, para que el Transformer
tenga acceso a los metadatos de las primeras filas.
"""

import pandas as pd
from pathlib import Path


class ExcelExtractor:
    """
    Lee un archivo Excel exportado por el SIU Guaraní y devuelve el DataFrame
    crudo completo (header=None), sin asumir nada sobre su estructura.

    La detección dinámica del encabezado real mediante HEADER_ANCHOR hace que
    este extractor sea robusto ante cambios en la cantidad de filas de metadatos
    que el SIU pueda agregar en el futuro (ej: nuevas filas de filtros arriba).

    Uso típico:
        extractor = ExcelExtractor("files/estadisticas de fin de cursada.xlsx")
        df_raw = extractor.extraer()
    """

    # Valor de celda que identifica la fila de encabezado real de datos.
    # El SIU siempre usa "Estado" como primera columna del header.
    # Si el SIU cambia este valor en el futuro, solo hay que actualizar esta constante.
    HEADER_ANCHOR = "Estado"

    def __init__(self, file_path: str | Path):
        """
        Args:
            file_path: Ruta al archivo .xlsx exportado desde el SIU Guaraní.
                       Se acepta str o Path; se convierte internamente a Path.
        """
        self.file_path = Path(file_path)

    def extraer(self) -> pd.DataFrame:
        """
        Lee el archivo Excel completo sin procesamiento de encabezado.

        Estrategia:
            1. Lee todo el archivo con header=None (pandas no interpreta ninguna
               fila como encabezado).
            2. Busca en todas las columnas la primera fila que contenga el valor
               HEADER_ANCHOR ("Estado") — esa fila identifica dónde empiezan
               los datos reales.
            3. Devuelve el DataFrame COMPLETO desde la fila 0, incluyendo los
               metadatos superiores, para que el Transformer pueda leerlos.

        NOTA: el DataFrame devuelto tiene columnas numéricas (0, 1, 2).
        El Transformer es quien conoce el significado de cada columna:
            col 0 → clave / nombre de fila
            col 1 → valor numérico (Total Alumnos)
            col 2 → valor de texto o porcentaje (Período, Propuesta, Porcentaje)

        Returns:
            pd.DataFrame con header=None y todos los datos del Excel.

        Raises:
            FileNotFoundError: si el archivo no existe en la ruta indicada.
            ValueError: si no se encuentra ninguna fila con HEADER_ANCHOR,
                        lo que indica que el formato del Excel es inesperado.
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo de origen en: {self.file_path}")

        print(f"[EXTRACT] Leyendo datos desde: {self.file_path.name}")

        # Leer el archivo completo sin asumir encabezado
        df_raw = pd.read_excel(self.file_path, header=None)

        # Buscar en qué fila aparece el anchor (busca en todas las columnas)
        mascara = df_raw.apply(
            lambda row: row.astype(str).str.strip().eq(self.HEADER_ANCHOR).any(),
            axis=1
        )
        filas_encontradas = mascara[mascara].index.tolist()

        if not filas_encontradas:
            raise ValueError(
                f"Formato de Excel inesperado: no se encontró la fila de encabezado "
                f"(buscando celda con valor '{self.HEADER_ANCHOR}'). "
                f"Verificar que el archivo es un export válido del SIU Guaraní."
            )

        header_row = filas_encontradas[0]
        print(f"[EXTRACT] Encabezado de datos encontrado en la fila {header_row}.")

        # Devolver el DataFrame completo — el Transformer maneja la navegación
        return df_raw
