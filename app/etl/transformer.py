"""
transformer.py
==============
Responsabilidad: tomar el DataFrame crudo que entrega el Extractor y producir
un diccionario Python estructurado y listo para persistir en la DB o serializar
a JSON.

NO hace lectura de archivos ni IO ÔÇö eso es trabajo del Extractor y del Pipeline.

Campos que se extraen y su destino en la DB (seg├║n DER HurData_DB):
ÔöîÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔö¼ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÉ
Ôöé Origen en el Excel                       Ôöé Tabla.Campo destino                   Ôöé
Ôö£ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔö╝ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöñ
Ôöé Fila "A├▒o Acad├®mico"  (col 2)            Ôöé Periodo.Anio                          Ôöé
Ôöé Fila "Per├¡odo Lectivo" (col 2)           Ôöé Cuatrimestre.Nombre_Cuatrimestre      Ôöé
Ôöé Fila "Propuesta"      (col 2)            Ôöé Carrera.Nombre_Carrera + Codigo       Ôöé
Ôöé "Actividad <nombre>"  (col 0)            Ôöé Materia.Nombre_Materia                Ôöé
Ôöé C├│digo de materia (ej. 004, AU_13)       Ôöé Materia.Codigo_Materia  (TEXT)        Ôöé
Ôöé "Comisi├│n XXX-COMISI├ôN N-MODALIDAD"      Ôöé                                       Ôöé
Ôöé   ÔööÔöÇ n├║mero N                            Ôöé Comision.Numero_Comision  (INTEGER)   Ôöé
Ôöé   ÔööÔöÇ VIRTUAL / PRESENCIAL / COMBINADA    Ôöé Modalidad.Nombre_Modalidad            Ôöé
Ôöé Estado (Libre / Promocion├│ / etc.)       Ôöé Estado.Nombre_Estado                  Ôöé
Ôöé Total Alumnos                            Ôöé Resultado_Comision.Cantidad_Alumnos   Ôöé
Ôöé Porcentaje sobre el total                Ôöé NO se persiste ÔÇö calculable en query  Ôöé
ÔööÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔö┤ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÿ
"""

import re
import pandas as pd


class ExcelTransformer:
    """
    Transforma el DataFrame crudo del SIU Guaran├¡ en una estructura jer├írquica:

        metadatos
        ÔööÔöÇÔöÇ actividades[]
              ÔööÔöÇÔöÇ comisiones[]
                    ÔööÔöÇÔöÇ estados[]

    Uso t├¡pico:
        transformer = ExcelTransformer()
        resultado = transformer.estructurar_a_json(df_raw)
    """

    # -------------------------------------------------------------------------
    # Helpers privados de detecci├│n de tipo de fila
    # -------------------------------------------------------------------------

    def _es_fila_actividad(self, valor: str) -> bool:
        """
        Devuelve True si la celda corresponde a una fila de actividad/materia.
        Ejemplo: 'Actividad Ingl├®s I'  |  'Actividad AU_Literatura y Memoria'
        """
        return str(valor).strip().startswith("Actividad ")

    def _es_fila_comision(self, valor: str) -> bool:
        """
        Devuelve True si la celda corresponde a una fila de comisi├│n.
        Ejemplo: 'Comisi├│n (004)-COMISI├ôN 1-COMBINADA'
        """
        return str(valor).strip().startswith("Comisi├│n ")

    def _es_fila_header(self, valor: str) -> bool:
        """
        Devuelve True si la celda es la fila de encabezado de columnas ('Estado').
        Estas filas se ignoran porque ya conocemos la estructura.
        """
        return str(valor).strip() == "Estado"

    def _es_fila_totales(self, valor: str) -> bool:
        """
        Devuelve True si la celda es un resumen de totales por actividad.
        Ejemplo: '<b>Totales por actividad</b>: Libre: 10 Promocion├│: 5'
        Estas filas se descartan ÔÇö los totales se calculan en query.
        """
        return "<b>Totales por actividad</b>" in str(valor)

    # -------------------------------------------------------------------------
    # Helpers privados de parseo de sub-campos
    # -------------------------------------------------------------------------

    def _extraer_nombre_actividad(self, valor: str) -> str:
        """
        Extrae el nombre limpio de la materia quitando el prefijo 'Actividad '.
        Ejemplo: 'Actividad Ingl├®s I'  ÔåÆ  'Ingl├®s I'
        """
        return str(valor).strip().removeprefix("Actividad ").strip()

    def _parsear_comision(self, valor: str) -> dict:
        """
        Descompone el string de comisi├│n en sus partes constitutivas.

         cabecera en varios formatos; todos se aceptan:
            'Comisi├│n (004)-COMISI├ôN 1-COMBINADA'            c├│digo entre par├®ntesis
            'Comisi├│n AU_48-COMISI├ôN 1-VIRTUAL'              c├│digo sin par├®ntesis
            'Comisi├│n (AU_40) COMISI├ôN 1 - VIRTUAL'          sin gui├│n tras el c├│digo

        Retorna un dict con:
            codigo_materia  ÔåÆ str  ej: '004', 'AU_13'   ÔåÆ Materia.Codigo_Materia
            numero_comision ÔåÆ int  ej: 1                ÔåÆ Comision.Numero_Comision
            modalidad       ÔåÆ str  ej: 'COMBINADA'      ÔåÆ Modalidad.Nombre_Modalidad
            nombre_completo ÔåÆ str  (para debug/log)
        """
        valor = str(valor).strip()

        # Cabecera completa: captura el c├│digo de materia (grupo 1, con o sin par├®ntesis)
        # y el resto del texto (grupo 2), separados por gui├│n y/o espacios.
        patron_cabecera = r'\s*Comisi[├│o]n\s+\(?([^)\s\-]+)\)?[\s\-]+(.+)$'
        match_cab = re.match(patron_cabecera, valor, re.IGNORECASE)
        codigo_materia = match_cab.group(1) if match_cab else None

        # Extraer n├║mero de comisi├│n: 'COMISI├ôN 5' ÔåÆ 5
        match_numero = re.search(r'COMISI[├ôO]N\s+(\d+)', valor, re.IGNORECASE)
        numero_comision = int(match_numero.group(1)) if match_numero else None

        # Extraer modalidad: ├║ltimo segmento despu├®s del segundo gui├│n
        # 'COMISI├ôN 1-COMBINADA' | 'COMISI├ôN 1-VIRTUAL-ITI y IB' ÔåÆ 'COMBINADA' / 'VIRTUAL'
        modalidades_conocidas = {"VIRTUAL", "PRESENCIAL", "COMBINADA"}
        modalidad = None
        for token in valor.upper().split("-"):
            token = token.strip().split()[0] if token.strip() else ""
            if token in modalidades_conocidas:
                modalidad = token.capitalize()  # 'Virtual', 'Presencial', 'Combinada'
                break

        # Nombre legible para mostrar en UI: todo lo que viene despu├®s del c├│digo
        nombre_completo = match_cab.group(2).strip() if match_cab else valor

        return {
            "codigo_materia": codigo_materia,
            "numero_comision": numero_comision,
            "modalidad": modalidad,
            "nombre_completo": nombre_completo,
        }

    def _parsear_periodo(self, valor: str) -> dict:
        """
        Descompone el string del per├¡odo lectivo en cuatrimestre y a├▒o.

        Ejemplo: 'PRIMER CUATRIMESTRE 2022'
        Retorna:
            cuatrimestre ÔåÆ 'PRIMER CUATRIMESTRE'   ÔåÆ Cuatrimestre.Nombre_Cuatrimestre
            anio         ÔåÆ 2022                     ÔåÆ Periodo.Anio
        """
        valor = str(valor).strip()
        match = re.search(r'(\d{4})', valor)
        anio = int(match.group(1)) if match else None
        cuatrimestre = re.sub(r'\d{4}', '', valor).strip() if anio else valor
        return {"cuatrimestre": cuatrimestre, "anio": anio}

    def _parsear_propuesta(self, valor: str) -> dict:
        """
        Descompone el string de propuesta en c├│digo y nombre de carrera.

        Ejemplo: '(023) Licenciatura en Inform├ítica'
        Retorna:
            codigo_carrera  ÔåÆ '023'                         ÔåÆ (referencia futura)
            nombre_carrera  ÔåÆ 'Licenciatura en Inform├ítica' ÔåÆ Carrera.Nombre_Carrera
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
        globales del reporte: a├▒o acad├®mico, per├¡odo lectivo y propuesta.

        Estos datos aplican a todas las actividades del archivo.
        Se detiene al encontrar la primera fila de actividad.

        Campos producidos:
            a├▒o_academico   ÔåÆ int                    ÔåÆ Periodo.Anio
            cuatrimestre    ÔåÆ str                    ÔåÆ Cuatrimestre.Nombre_Cuatrimestre
            codigo_carrera  ÔåÆ str                    ÔåÆ (referencia futura)
            nombre_carrera  ÔåÆ str                    ÔåÆ Carrera.Nombre_Carrera
        """
        meta = {}
        for _, row in df_raw.iterrows():
            clave = str(row.iloc[0]).strip()

            if clave == "A├▒o Acad├®mico":
                meta["a├▒o_academico"] = int(str(row.iloc[2]).strip())

            elif clave == "Per├¡odo Lectivo":
                periodo_parseado = self._parsear_periodo(str(row.iloc[2]).strip())
                meta["cuatrimestre"] = periodo_parseado["cuatrimestre"]
                # a├▒o_academico ya lo tenemos de la fila anterior, pero por consistencia:
                if "a├▒o_academico" not in meta and periodo_parseado["anio"]:
                    meta["a├▒o_academico"] = periodo_parseado["anio"]

            elif clave == "Propuesta":
                propuesta_parseada = self._parsear_propuesta(str(row.iloc[2]).strip())
                meta.update(propuesta_parseada)

            # Detener cuando lleguemos a la primera actividad
            if self._es_fila_actividad(clave):
                break

        return meta

    # -------------------------------------------------------------------------
    # Transformaci├│n principal
    # -------------------------------------------------------------------------

    def estructurar_a_json(self, df_raw: pd.DataFrame) -> dict:
        """
        M├®todo principal del transformer. Recorre el DataFrame crudo fila por fila
        y construye la estructura jer├írquica completa del reporte.

        Estructura de salida:
        {
            "a├▒o_academico": 2022,
            "cuatrimestre": "PRIMER CUATRIMESTRE",
            "codigo_carrera": "023",
            "nombre_carrera": "Licenciatura en Inform├ítica",
            "actividades": [
                {
                    "nombre": "Ingl├®s I",
                    "codigo_materia": "030",
                    "comisiones": [
                        {
                            "numero_comision": 1,
                            "modalidad": "Virtual",
                            "nombre_completo": "COMISI├ôN 1-VIRTUAL",
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
        print("[TRANSFORM] Estructurando datos en formato JSON jer├írquico...")

        resultado = self._extraer_metadatos(df_raw)
        resultado["actividades"] = []

        actividad_actual = None   # bloque de materia activo
        comision_actual = None    # bloque de comisi├│n activo

        for _, row in df_raw.iterrows():
            valor_col0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""

            # Ignorar filas vac├¡as, encabezados de columna repetidos y totales
            if not valor_col0 or self._es_fila_header(valor_col0) or self._es_fila_totales(valor_col0):
                continue

            # --- Fila de ACTIVIDAD ÔåÆ abre nuevo bloque de materia ---
            if self._es_fila_actividad(valor_col0):
                actividad_actual = {
                    "nombre": self._extraer_nombre_actividad(valor_col0),
                    # codigo_materia se completa cuando aparece la primera comisi├│n
                    "codigo_materia": None,
                    "comisiones": []
                }
                resultado["actividades"].append(actividad_actual)
                comision_actual = None
                continue

            # --- Fila de COMISI├ôN ÔåÆ abre nueva comisi├│n dentro de la actividad ---
            if self._es_fila_comision(valor_col0):
                # Robustez: comisi├│n sin actividad padre no deber├¡a ocurrir, pero se maneja
                if actividad_actual is None:
                    actividad_actual = {"nombre": "Sin actividad", "codigo_materia": None, "comisiones": []}
                    resultado["actividades"].append(actividad_actual)

                datos_comision = self._parsear_comision(valor_col0)

                # El c├│digo de materia viene de la comisi├│n ÔÇö lo propagamos a la actividad
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

            # --- Fila de DATOS ÔåÆ agrega estado a la comisi├│n activa ---
            if comision_actual is not None:
                total = row.iloc[1]
                # Porcentaje NO se persiste en DB (calculable), pero se incluye
                # en el JSON de debug para verificar integridad de los datos.
                porcentaje = row.iloc[2]

                # Ignorar filas de datos completamente vac├¡as
                if pd.isna(total) and pd.isna(porcentaje):
                    continue

                comision_actual["estados"].append({
                    "estado": valor_col0,
                    # Cantidad_Alumnos ÔåÆ Resultado_Comision.Cantidad_Alumnos
                    "total_alumnos": int(total) if pd.notna(total) else None,
                    # Solo para debug ÔÇö NO va a la DB
                    "porcentaje_debug": round(float(porcentaje), 6) if pd.notna(porcentaje) else None,
                })

        total_actividades = len(resultado["actividades"])
        total_comisiones = sum(len(a["comisiones"]) for a in resultado["actividades"])
        print(f"[TRANSFORM] {total_actividades} actividades y {total_comisiones} comisiones procesadas.")
        return resultado

    # -------------------------------------------------------------------------
    # Limpieza b├ísica ÔÇö mantenida para usos alternativos / experimentaci├│n
    # -------------------------------------------------------------------------

    def limpiar_basico(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalizaci├│n b├ísica de un DataFrame tabular plano.
        ├Ütil para exploraci├│n r├ípida o si en el futuro se procesan otros
        reportes del SIU con estructura m├ís simple.

        No se usa en el flujo principal de HurData ÔÇö ver estructurar_a_json().
        """
        print("[TRANSFORM] Iniciando limpieza b├ísica de datos...")
        df_limpio = df.copy()
        df_limpio.dropna(how='all', inplace=True)
        df_limpio.dropna(axis=1, how='all', inplace=True)
        df_limpio.columns = [str(c).strip().lower().replace(" ", "_") for c in df_limpio.columns]
        return df_limpio
