"""
transformer.py
==============
Responsabilidad: tomar el DataFrame crudo que entrega el Extractor y producir
un diccionario Python estructurado y listo para persistir en la DB o serializar
a JSON.

NO hace lectura de archivos ni IO — eso es trabajo del Extractor y del Pipeline.

Campos que se extraen y su destino en la DB (según DER HurData_DB):
┌──────────────────────────────────────────┬───────────────────────────────────────┐
│ Origen en el Excel                       │ Tabla.Campo destino                   │
├──────────────────────────────────────────┼───────────────────────────────────────┤
│ Fila "Año Académico"  (col 2)            │ Periodo.Anio                          │
│ Fila "Período Lectivo" (col 2)           │ Cuatrimestre.Nombre_Cuatrimestre      │
│ Fila "Propuesta"      (col 2)            │ Carrera.Nombre_Carrera + Codigo       │
│ "Actividad <nombre>"  (col 0)            │ Materia.Nombre_Materia                │
│ Código entre paréntesis ej. (004)        │ Materia.Codigo_Materia  (TEXT)        │
│ "Comisión (XXX)-COMISIÓN N-MODALIDAD"   │                                       │
│   └─ número N                            │ Comision.Numero_Comision  (INTEGER)   │
│   └─ VIRTUAL / PRESENCIAL / COMBINADA   │ Modalidad.Nombre_Modalidad            │
│ Estado (Libre / Promocionó / etc.)       │ Estado.Nombre_Estado                  │
│ Total Alumnos                            │ Resultado_Comision.Cantidad_Alumnos   │
│ Porcentaje sobre el total                │ NO se persiste — calculable en query  │
└──────────────────────────────────────────┴───────────────────────────────────────┘
"""

import re
import pandas as pd


class ExcelTransformer:
    """
    Transforma el DataFrame crudo del SIU Guaraní en una estructura jerárquica:

        metadatos
        └── actividades[]
              └── comisiones[]
                    └── estados[]

    Uso típico:
        transformer = ExcelTransformer()
        resultado = transformer.estructurar_a_json(df_raw)
    """

    # -------------------------------------------------------------------------
    # Helpers privados de detección de tipo de fila
    # -------------------------------------------------------------------------

    def _es_fila_actividad(self, valor: str) -> bool:
        """
        Devuelve True si la celda corresponde a una fila de actividad/materia.
        Ejemplo: 'Actividad Inglés I'  |  'Actividad AU_Literatura y Memoria'
        """
        return str(valor).strip().startswith("Actividad ")

    def _es_fila_comision(self, valor: str) -> bool:
        """
        Devuelve True si la celda corresponde a una fila de comisión.
        Ejemplo: 'Comisión (004)-COMISIÓN 1-COMBINADA'
        """
        return str(valor).strip().startswith("Comisión ")

    def _es_fila_header(self, valor: str) -> bool:
        """
        Devuelve True si la celda es la fila de encabezado de columnas ('Estado').
        Estas filas se ignoran porque ya conocemos la estructura.
        """
        return str(valor).strip() == "Estado"

    def _es_fila_totales(self, valor: str) -> bool:
        """
        Devuelve True si la celda es un resumen de totales por actividad.
        Ejemplo: '<b>Totales por actividad</b>: Libre: 10 Promocionó: 5'
        Estas filas se descartan — los totales se calculan en query.
        """
        return "<b>Totales por actividad</b>" in str(valor)

    # -------------------------------------------------------------------------
    # Helpers privados de parseo de sub-campos
    # -------------------------------------------------------------------------

    def _extraer_nombre_actividad(self, valor: str) -> str:
        """
        Extrae el nombre limpio de la materia quitando el prefijo 'Actividad '.
        Ejemplo: 'Actividad Inglés I'  →  'Inglés I'
        """
        return str(valor).strip().removeprefix("Actividad ").strip()

    def _parsear_comision(self, valor: str) -> dict:
        """
        Descompone el string de comisión en sus partes constitutivas.

        Formato esperado: 'Comisión (CODIGO)-COMISIÓN N-MODALIDAD[...]'
        Ejemplo:          'Comisión (004)-COMISIÓN 1-COMBINADA'

        Retorna un dict con:
            codigo_materia  → str  ej: '004', 'AU_13'   → Materia.Codigo_Materia
            numero_comision → int  ej: 1                → Comision.Numero_Comision
            modalidad       → str  ej: 'COMBINADA'      → Modalidad.Nombre_Modalidad
            nombre_completo → str  (para debug/log)
        """
        valor = str(valor).strip()

        # Extraer código de materia entre paréntesis: (004) o (AU_13)
        match_codigo = re.search(r'\(([^)]+)\)', valor)
        codigo_materia = match_codigo.group(1) if match_codigo else None

        # Extraer número de comisión: 'COMISIÓN 5' → 5
        match_numero = re.search(r'COMISI[ÓO]N\s+(\d+)', valor, re.IGNORECASE)
        numero_comision = int(match_numero.group(1)) if match_numero else None

        # Extraer modalidad: último segmento después del segundo guión
        # 'COMISIÓN 1-COMBINADA' | 'COMISIÓN 1-VIRTUAL-ITI y IB' → 'COMBINADA' / 'VIRTUAL'
        modalidades_conocidas = {"VIRTUAL", "PRESENCIAL", "COMBINADA"}
        modalidad = None
        for token in valor.upper().split("-"):
            token = token.strip().split()[0] if token.strip() else ""
            if token in modalidades_conocidas:
                modalidad = token.capitalize()  # 'Virtual', 'Presencial', 'Combinada'
                break

        # Nombre legible para mostrar en UI: todo lo que viene después del ')- '
        match_nombre = re.search(r'\)-(.+)$', valor)
        nombre_completo = match_nombre.group(1).strip() if match_nombre else valor

        return {
            "codigo_materia": codigo_materia,
            "numero_comision": numero_comision,
            "modalidad": modalidad,
            "nombre_completo": nombre_completo,
        }

    def _parsear_periodo(self, valor: str) -> dict:
        """
        Descompone el string del período lectivo en cuatrimestre y año.

        Ejemplo: 'PRIMER CUATRIMESTRE 2022'
        Retorna:
            cuatrimestre → 'PRIMER CUATRIMESTRE'   → Cuatrimestre.Nombre_Cuatrimestre
            anio         → 2022                     → Periodo.Anio
        """
        valor = str(valor).strip()
        match = re.search(r'(\d{4})', valor)
        anio = int(match.group(1)) if match else None
        cuatrimestre = re.sub(r'\d{4}', '', valor).strip() if anio else valor
        return {"cuatrimestre": cuatrimestre, "anio": anio}

    def _parsear_propuesta(self, valor: str) -> dict:
        """
        Descompone el string de propuesta en código y nombre de carrera.

        Ejemplo: '(023) Licenciatura en Informática'
        Retorna:
            codigo_carrera  → '023'                         → (referencia futura)
            nombre_carrera  → 'Licenciatura en Informática' → Carrera.Nombre_Carrera
        """
        valor = str(valor).strip()
        match = re.match(r'\((\d+)\)\s*(.+)', valor)
        if match:
            return {"codigo_carrera": match.group(1), "nombre_carrera": match.group(2).strip()}
        return {"codigo_carrera": None, "nombre_carrera": valor}

    # -------------------------------------------------------------------------
    # Parseo de metadatos globales (primeras filas del Excel)
    # -------------------------------------------------------------------------

    def _extraer_metadatos(self, df_raw: pd.DataFrame) -> dict:
        """
        Lee las primeras filas del DataFrame crudo para extraer los metadatos
        globales del reporte: año académico, período lectivo y propuesta.

        Estos datos aplican a todas las actividades del archivo.
        Se detiene al encontrar la primera fila de actividad.

        Campos producidos:
            año_academico   → int                    → Periodo.Anio
            cuatrimestre    → str                    → Cuatrimestre.Nombre_Cuatrimestre
            codigo_carrera  → str                    → (referencia futura)
            nombre_carrera  → str                    → Carrera.Nombre_Carrera
        """
        meta = {}
        for _, row in df_raw.iterrows():
            clave = str(row.iloc[0]).strip()

            if clave == "Año Académico":
                meta["año_academico"] = int(str(row.iloc[2]).strip())

            elif clave == "Período Lectivo":
                periodo_parseado = self._parsear_periodo(str(row.iloc[2]).strip())
                meta["cuatrimestre"] = periodo_parseado["cuatrimestre"]
                # año_academico ya lo tenemos de la fila anterior, pero por consistencia:
                if "año_academico" not in meta and periodo_parseado["anio"]:
                    meta["año_academico"] = periodo_parseado["anio"]

            elif clave == "Propuesta":
                propuesta_parseada = self._parsear_propuesta(str(row.iloc[2]).strip())
                meta.update(propuesta_parseada)

            # Detener cuando lleguemos a la primera actividad
            if self._es_fila_actividad(clave):
                break

        return meta

    # -------------------------------------------------------------------------
    # Transformación principal
    # -------------------------------------------------------------------------

    def estructurar_a_json(self, df_raw: pd.DataFrame) -> dict:
        """
        Método principal del transformer. Recorre el DataFrame crudo fila por fila
        y construye la estructura jerárquica completa del reporte.

        Estructura de salida:
        {
            "año_academico": 2022,
            "cuatrimestre": "PRIMER CUATRIMESTRE",
            "codigo_carrera": "023",
            "nombre_carrera": "Licenciatura en Informática",
            "actividades": [
                {
                    "nombre": "Inglés I",
                    "codigo_materia": "030",
                    "comisiones": [
                        {
                            "numero_comision": 1,
                            "modalidad": "Virtual",
                            "nombre_completo": "COMISIÓN 1-VIRTUAL",
                            "estados": [
                                {
                                    "estado": "Libre",
                                    "total_alumnos": 20
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        Args:
            df_raw: DataFrame sin encabezado procesado, tal como lo devuelve
                    ExcelExtractor con header=None.

        Returns:
            dict con metadatos + lista de actividades completamente parseadas.
        """
        print("[TRANSFORM] Estructurando datos en formato JSON jerárquico...")

        resultado = self._extraer_metadatos(df_raw)
        resultado["actividades"] = []

        actividad_actual = None   # bloque de materia activo
        comision_actual = None    # bloque de comisión activo

        for _, row in df_raw.iterrows():
            valor_col0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""

            # Ignorar filas vacías, encabezados de columna repetidos y totales
            if not valor_col0 or self._es_fila_header(valor_col0) or self._es_fila_totales(valor_col0):
                continue

            # --- Fila de ACTIVIDAD → abre nuevo bloque de materia ---
            if self._es_fila_actividad(valor_col0):
                actividad_actual = {
                    "nombre": self._extraer_nombre_actividad(valor_col0),
                    # codigo_materia se completa cuando aparece la primera comisión
                    "codigo_materia": None,
                    "comisiones": []
                }
                resultado["actividades"].append(actividad_actual)
                comision_actual = None
                continue

            # --- Fila de COMISIÓN → abre nueva comisión dentro de la actividad ---
            if self._es_fila_comision(valor_col0):
                # Robustez: comisión sin actividad padre no debería ocurrir, pero se maneja
                if actividad_actual is None:
                    actividad_actual = {"nombre": "Sin actividad", "codigo_materia": None, "comisiones": []}
                    resultado["actividades"].append(actividad_actual)

                datos_comision = self._parsear_comision(valor_col0)

                # El código de materia viene de la comisión — lo propagamos a la actividad
                if actividad_actual["codigo_materia"] is None:
                    actividad_actual["codigo_materia"] = datos_comision["codigo_materia"]

                comision_actual = {
                    "numero_comision": datos_comision["numero_comision"],
                    "modalidad": datos_comision["modalidad"],
                    "nombre_completo": datos_comision["nombre_completo"],
                    "estados": []
                }
                actividad_actual["comisiones"].append(comision_actual)
                continue

            # --- Fila de DATOS → agrega estado a la comisión activa ---
            if comision_actual is not None:
                total = row.iloc[1]
                # Porcentaje NO se persiste en DB (calculable), pero se incluye
                # en el JSON de debug para verificar integridad de los datos.
                porcentaje = row.iloc[2]

                # Ignorar filas de datos completamente vacías
                if pd.isna(total) and pd.isna(porcentaje):
                    continue

                comision_actual["estados"].append({
                    "estado": valor_col0,
                    # Cantidad_Alumnos → Resultado_Comision.Cantidad_Alumnos
                    "total_alumnos": int(total) if pd.notna(total) else None,
                    # Solo para debug — NO va a la DB
                    "porcentaje_debug": round(float(porcentaje), 6) if pd.notna(porcentaje) else None,
                })

        total_actividades = len(resultado["actividades"])
        total_comisiones = sum(len(a["comisiones"]) for a in resultado["actividades"])
        print(f"[TRANSFORM] {total_actividades} actividades y {total_comisiones} comisiones procesadas.")
        return resultado

    # -------------------------------------------------------------------------
    # Limpieza básica — mantenida para usos alternativos / experimentación
    # -------------------------------------------------------------------------

    def limpiar_basico(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalización básica de un DataFrame tabular plano.
        Útil para exploración rápida o si en el futuro se procesan otros
        reportes del SIU con estructura más simple.

        No se usa en el flujo principal de HurData — ver estructurar_a_json().
        """
        print("[TRANSFORM] Iniciando limpieza básica de datos...")
        df_limpio = df.copy()
        df_limpio.dropna(how='all', inplace=True)
        df_limpio.dropna(axis=1, how='all', inplace=True)
        df_limpio.columns = [str(c).strip().lower().replace(" ", "_") for c in df_limpio.columns]
        return df_limpio
