"""
schemas.py
==========
Responsabilidad: definir la FORMA exacta del JSON que devuelve la API.

Son el contrato con el frontend (ver src/services/api.js y src/App.jsx):
    • FastAPI valida que cada respuesta cumpla el modelo antes de enviarla.
    • Swagger (/docs) los muestra como documentación de cada endpoint.
Si se cambia un nombre de campo acá, hay que cambiarlo también en el frontend.
"""

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# GET /api/periodos
# ---------------------------------------------------------------------------

class PeriodoOut(BaseModel):
    id_periodo: int
    anio: int
    cuatrimestre: str       # ej: 'PRIMER CUATRIMESTRE'
    label: str              # ej: '2022 - PRIMER CUATRIMESTRE' (lo que muestra el selector)


class PeriodosOut(BaseModel):
    periodos: list[PeriodoOut]


# ---------------------------------------------------------------------------
# GET /api/carreras
# ---------------------------------------------------------------------------

class CarreraOut(BaseModel):
    id: int
    nombre: str


class CarrerasOut(BaseModel):
    carreras: list[CarreraOut]


# ---------------------------------------------------------------------------
# GET /api/periodos-carreras
# ---------------------------------------------------------------------------

class PeriodoCarreraOut(BaseModel):
    id_periodo: int
    id_carrera: int
    label: str              # label del período
    nombre_carrera: str
    cargado_por: str | None # nombre de quien hizo la carga activa (None: sin carga registrada)
    puede_borrar: bool      # si el usuario actual puede borrar o recargar esta carga


class PeriodosCarrerasOut(BaseModel):
    periodos: list[PeriodoCarreraOut]


# ---------------------------------------------------------------------------
# GET /api/datos  (de adentro hacia afuera: estado → comisión → actividad)
# ---------------------------------------------------------------------------

class EstadoOut(BaseModel):
    estado: str             # ej: 'Libre', 'Promocionó', 'Regular'
    total_alumnos: int


class ComisionOut(BaseModel):
    numero_comision: int
    modalidad: str          # 'Virtual' | 'Presencial' | 'Combinada'
    nombre_completo: str    # ej: 'COMISIÓN 1-VIRTUAL'
    estados: list[EstadoOut]


class ActividadOut(BaseModel):
    nombre: str
    codigo_materia: str     # ej: '004', 'AU_13'
    comisiones: list[ComisionOut]


class DatosOut(BaseModel):
    nombre_carrera: str
    carreras_disponibles: list[str]
    actividades: list[ActividadOut]


# ---------------------------------------------------------------------------
# Respuestas simples (DELETE)
# ---------------------------------------------------------------------------

class MensajeOut(BaseModel):
    message: str

# ---------------------------------------------------------------------------
# POST /api/login  /  GET /api/directivos
# ---------------------------------------------------------------------------

class LoginIn(BaseModel):
    usuario: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str


class DirectivoOut(BaseModel):
    id: int
    nombre: str
    email: str


class DirectivosOut(BaseModel):
    directivos: list[DirectivoOut]


# ---------------------------------------------------------------------------
# GET /api/cargas  (historial de Excel cargados)
# ---------------------------------------------------------------------------

class CargaOut(BaseModel):
    id_carga: int
    fecha: str                      # ISO 8601 en UTC; el frontend la muestra en hora local
    nombre_archivo: str             # nombre original del .xlsx
    cargado_por: str                # nombre de quien lo subió
    periodo_label: str
    nombre_carrera: str
    materias: int
    comisiones: int
    resultados: int
    estado: str                     # 'activa' | 'reemplazada' | 'borrada'
    dado_de_baja_por: str | None    # nombre de quien lo reemplazó o borró
    fecha_baja: str | None


class CargasOut(BaseModel):
    cargas: list[CargaOut]
    ve_todas: bool                  # False: el usuario solo ve sus propias cargas
