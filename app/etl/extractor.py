import pandas as pd
from pathlib import Path

class ExcelExtractor:
    HEADER_ANCHOR = "Estado"  # Valor que identifica la fila de encabezado real

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    def extraer(self) -> pd.DataFrame:
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
                f"No se encontró la fila de encabezado "
                f"(buscando '{self.HEADER_ANCHOR}') en el archivo."
            )

        header_row = filas_encontradas[0]
        print(f"[EXTRACT] Encabezado encontrado en la fila {header_row}.")

        # Usar esa fila como encabezado y descartar todo lo que estaba arriba
        df = df_raw.iloc[header_row:].reset_index(drop=True)
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

        return df