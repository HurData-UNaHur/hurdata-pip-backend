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
    id_periodo          INTEGER NOT NULL REFERENCES Periodo(id_periodo)   ON DELETE CASCADE,
    id_carrera          INTEGER NOT NULL REFERENCES Carrera(id_carrera)   ON DELETE CASCADE,
    id_materia          INTEGER NOT NULL REFERENCES Materia(id_materia),
    id_modalidad        INTEGER NOT NULL REFERENCES Modalidad(id_modalidad),
    numero_comision     INTEGER NOT NULL,
    nombre_completo     TEXT    NOT NULL,     -- ej: 'COMISIÓN 1-VIRTUAL-ITI y IB'
    UNIQUE (id_periodo, id_carrera, id_materia, numero_comision)
);

CREATE TABLE IF NOT EXISTS Resultado_Comision (
    id_resultado    INTEGER PRIMARY KEY AUTOINCREMENT,
    id_comision     INTEGER NOT NULL REFERENCES Comision(id_comision) ON DELETE CASCADE,
    id_estado       INTEGER NOT NULL REFERENCES Estado(id_estado),
    cantidad_alumnos INTEGER NOT NULL DEFAULT 0,
    UNIQUE (id_comision, id_estado)
);

-- -----------------------------------------------------------------------------
-- Índices para las consultas más frecuentes del dashboard
-- -----------------------------------------------------------------------------

-- Filtrar comisiones por materia (ranking de materias, histórico)
CREATE INDEX IF NOT EXISTS idx_comision_materia
    ON Comision(id_materia);

-- Filtrar comisiones por modalidad
CREATE INDEX IF NOT EXISTS idx_comision_modalidad
    ON Comision(id_modalidad);

-- -----------------------------------------------------------------------------
-- Autenticación
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Usuario (
    id_usuario      INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario         TEXT    NOT NULL UNIQUE,
    nombre          TEXT    NOT NULL,
    cargo           TEXT    NOT NULL,
    -- Los permisos de cada rol están en app/api/permisos.py
    role            TEXT    NOT NULL
                    CHECK (role IN ('admin', 'directivo', 'docente', 'no_docente')),
    password_hash   TEXT    NOT NULL
);

-- Un instituto por fila, con el email de su dirección (quien aprueba los registros).
-- El email es solo para uso interno: GET /api/institutos no lo devuelve.
CREATE TABLE IF NOT EXISTS Directivo (
    id_directivo    INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL,         -- nombre del instituto, ej: 'Tecnología e Ingeniería'
    email           TEXT    NOT NULL UNIQUE   -- email de la dirección del instituto
);

-- -----------------------------------------------------------------------------
-- Historial de cargas de Excel (auditoría + dueño de cada carga)
-- -----------------------------------------------------------------------------
-- Una fila por CADA subida. La fila 'activa' de un período + carrera indica
-- quién es el dueño de esos datos (solo él, un directivo o el admin pueden
-- borrarlos o recargarlos). Al recargar, la anterior pasa a 'reemplazada';
-- al borrar, a 'borrada'.
--
-- Sin FOREIGN KEY a Periodo/Carrera a propósito: el historial tiene que
-- sobrevivir cuando se borran los datos. Por eso guarda también el label del
-- período y el nombre de la carrera como texto.

CREATE TABLE IF NOT EXISTS Carga (
    id_carga        INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha           TEXT    NOT NULL,            -- ISO 8601 en UTC
    nombre_archivo  TEXT    NOT NULL,            -- nombre original del .xlsx (el archivo NO se guarda)
    usuario         TEXT    NOT NULL,            -- email (sub del JWT) de quien subió
    nombre_usuario  TEXT    NOT NULL,
    id_periodo      INTEGER NOT NULL,
    id_carrera      INTEGER NOT NULL,
    periodo_label   TEXT    NOT NULL,
    nombre_carrera  TEXT    NOT NULL,
    materias        INTEGER NOT NULL DEFAULT 0,
    comisiones      INTEGER NOT NULL DEFAULT 0,
    resultados      INTEGER NOT NULL DEFAULT 0,
    estado          TEXT    NOT NULL DEFAULT 'activa'
                    CHECK (estado IN ('activa', 'reemplazada', 'borrada')),
    dado_de_baja_por TEXT,                       -- email de quien la reemplazó o borró
    fecha_baja      TEXT
);

-- Como mucho UNA carga activa por período + carrera
CREATE UNIQUE INDEX IF NOT EXISTS idx_carga_activa
    ON Carga(id_periodo, id_carrera) WHERE estado = 'activa';



/*
Solucitudes y Registros
*/

CREATE TABLE IF NOT EXISTS Solicitud_Registro (
    id_solicitud    INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT    NOT NULL UNIQUE,
    nombre          TEXT    NOT NULL,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL
                    CHECK (role IN ('directivo', 'docente', 'no_docente')),
    id_directivo    INTEGER NOT NULL REFERENCES Directivo(id_directivo),
    estado          TEXT    NOT NULL DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente', 'aprobada', 'rechazada')),
    fecha_solicitud TEXT    NOT NULL,
    resuelto_por    TEXT,
    fecha_resolucion TEXT
);


-- -----------------------------------------------------------------------------
-- Recuperación de contraseña por solicitud
-- -----------------------------------------------------------------------------
-- El usuario pide la recuperación; un Directivo o Admin la aprueba y recibe un código
-- de un solo uso que le entrega al usuario. El código se guarda hasheado.
--   pendiente  → esperando que alguien la apruebe
--   aprobada   → tiene código vigente (codigo_hash y expira_en)
--   usada      → el código se canjeó y la contraseña se cambió
--   rechazada  → la rechazó un aprobador, o se agotaron los intentos del código

CREATE TABLE IF NOT EXISTS Solicitud_Recuperacion (
    id_solicitud     INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario          TEXT    NOT NULL REFERENCES Usuario(usuario) ON DELETE CASCADE,
    estado           TEXT    NOT NULL DEFAULT 'pendiente'
                     CHECK (estado IN ('pendiente', 'aprobada', 'usada', 'rechazada')),
    fecha_solicitud  TEXT    NOT NULL,
    codigo_hash      TEXT,
    expira_en        TEXT,
    intentos         INTEGER NOT NULL DEFAULT 0,
    resuelto_por     TEXT,
    fecha_resolucion TEXT
);

-- Como mucho una solicitud abierta (pendiente o con código vigente) por usuario
CREATE UNIQUE INDEX IF NOT EXISTS idx_recuperacion_abierta
    ON Solicitud_Recuperacion(usuario) WHERE estado IN ('pendiente', 'aprobada');