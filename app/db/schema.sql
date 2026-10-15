-- =============================================================================
-- schema.sql — HurData PIP
-- =============================================================================
-- DER basado en la estructura jerárquica del reporte SIU Guaraní:
--
--   Periodo (año + cuatrimestre)
--     └─ Carrera
--          └─ Materia
--               └─ Comision  (Modalidad, Numero)
--                    └─ Resultado_Comision  (Estado, Cantidad_Alumnos)
--
-- Decisiones de diseño:
--   • Todos los IDs son INTEGER PRIMARY KEY AUTOINCREMENT para simplificar joins.
--   • Modalidad y Estado son tablas de catálogo (lookup) para evitar strings
--     duplicados en Resultado_Comision y facilitar filtros desde el frontend.
--   • Los porcentajes NO se persisten — se calculan en tiempo de consulta.
--   • UNIQUE constraints para evitar duplicados en cargas repetidas del mismo Excel.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Tablas de catálogo (lookup tables)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Modalidad (
    id_modalidad    INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL UNIQUE   -- 'Virtual' | 'Presencial' | 'Combinada'
);

CREATE TABLE IF NOT EXISTS Estado (
    id_estado       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL UNIQUE   -- 'Libre' | 'Promocionó' | 'Regular' | 'Insuficiente' | 'Sin Condición'
);

-- -----------------------------------------------------------------------------
-- Dimensión temporal
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Periodo (
    id_periodo      INTEGER PRIMARY KEY AUTOINCREMENT,
    anio            INTEGER NOT NULL,
    cuatrimestre    TEXT    NOT NULL,         -- 'PRIMER CUATRIMESTRE' | 'SEGUNDO CUATRIMESTRE'
    label           TEXT    GENERATED ALWAYS AS (anio || ' - ' || cuatrimestre) VIRTUAL,
    UNIQUE (anio, cuatrimestre)
);

-- -----------------------------------------------------------------------------
-- Dimensión académica
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Carrera (
    id_carrera      INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT    NOT NULL UNIQUE,  -- ej: '023'
    nombre          TEXT    NOT NULL          -- ej: 'Licenciatura en Informática'
);

CREATE TABLE IF NOT EXISTS Materia (
    id_materia      INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT    NOT NULL UNIQUE,  -- ej: '030', 'AU_13'
    nombre          TEXT    NOT NULL          -- ej: 'Inglés I'
);

-- Tabla de relación Carrera ↔ Materia (una materia puede pertenecer a varias carreras)
CREATE TABLE IF NOT EXISTS Carrera_Materia (
    id_carrera      INTEGER NOT NULL REFERENCES Carrera(id_carrera),
    id_materia      INTEGER NOT NULL REFERENCES Materia(id_materia),
    PRIMARY KEY (id_carrera, id_materia)
);

-- -----------------------------------------------------------------------------
-- Tabla de hechos
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Comision (
    id_comision         INTEGER PRIMARY KEY AUTOINCREMENT,
    id_periodo          INTEGER NOT NULL REFERENCES Periodo(id_periodo),
    id_materia          INTEGER NOT NULL REFERENCES Materia(id_materia),
    id_modalidad        INTEGER NOT NULL REFERENCES Modalidad(id_modalidad),
    numero_comision     INTEGER NOT NULL,
    nombre_completo     TEXT    NOT NULL,     -- ej: 'COMISIÓN 1-VIRTUAL-ITI y IB'
    UNIQUE (id_periodo, id_materia, numero_comision)
);

CREATE TABLE IF NOT EXISTS Resultado_Comision (
    id_resultado    INTEGER PRIMARY KEY AUTOINCREMENT,
    id_comision     INTEGER NOT NULL REFERENCES Comision(id_comision),
    id_estado       INTEGER NOT NULL REFERENCES Estado(id_estado),
    cantidad_alumnos INTEGER NOT NULL DEFAULT 0,
    UNIQUE (id_comision, id_estado)
);

-- -----------------------------------------------------------------------------
-- Índices para las consultas más frecuentes del dashboard
-- -----------------------------------------------------------------------------

-- Filtrar comisiones por período (muy frecuente en todos los endpoints)
CREATE INDEX IF NOT EXISTS idx_comision_periodo
    ON Comision(id_periodo);

-- Filtrar comisiones por materia (ranking de materias, histórico)
CREATE INDEX IF NOT EXISTS idx_comision_materia
    ON Comision(id_materia);

-- Filtrar comisiones por modalidad
CREATE INDEX IF NOT EXISTS idx_comision_modalidad
    ON Comision(id_modalidad);

-- Resultados por comisión (KPIs, detalle)
CREATE INDEX IF NOT EXISTS idx_resultado_comision
    ON Resultado_Comision(id_comision);
