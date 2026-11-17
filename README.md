**HurData** es un Dashboard Analítico de Gestión Académica diseñado para procesar, depurar y visualizar los datos operativos exportados por el sistema SIU Guaraní. Desarrollado en el ámbito del Instituto de Tecnología e Ingeniería de la Universidad Nacional de Hurlingham (UNaHur), el proyecto busca transformar reportes tabulares estáticos en información estratégica e interactiva.

Los reportes nativos del sistema (como las estadísticas de fin de cursada) suelen exportarse con formatos visuales pensados para la lectura humana, lo que dificulta el análisis masivo y programático. HurData resuelve este cuello de botella mediante un pipeline ETL (Extracción, Transformación y Carga) construido en Python, Pandas y FastAPI, automatizando la limpieza de archivos y preparándolos para su consumo en la web.

### ✨ Características Principales
* **Motor de Procesamiento Dinámico:** Limpia y normaliza automáticamente archivos Excel crudos del SIU, aislando los datos reales de los metadatos visuales.
* **Arquitectura Modular Orientada a Objetos:** Código backend estructurado profesionalmente, separando responsabilidades para facilitar el testing, la escalabilidad y el trabajo ágil en equipo.
* **Privacidad por Diseño (Privacy-First):** Configuración estricta de repositorios y entornos para garantizar que los archivos con datos sensibles de la universidad nunca se expongan en la nube pública.
* **API RESTful:** Endpoints rápidos y documentados, organizados por responsabilidad (consultas vs. administración), con autenticación por API key para las operaciones que modifican datos.

---

# HurData - Backend

Backend del Dashboard Analítico de Gestión Académica para la Universidad Nacional de Hurlingham (UNaHur). Desarrollado con Python, FastAPI y Pandas.

## Requisitos Previos
* Python 3.10 o superior.
* Git.

## Configuración del Entorno Local (Setup)

**1. Clonar el repositorio**
```bash
git clone https://github.com/HurData-UNaHur/hurdata-pip-backend.git
cd hurdata-pip-backend
```

**2. Crear el entorno virtual**
```bash
python -m venv venv
```

**3. Activar el entorno virtual**
* En Windows:
  ```bash
  venv\Scripts\activate
  ```
* En macOS / Linux:
  ```bash
  source venv/bin/activate
  ```
*(Deberían ver un `(venv)` al inicio de la línea en su terminal).*

**4. Instalar las dependencias**
```bash
pip install -r requirements.txt
```

**5. Configurar las variables de entorno**

Crear un archivo `.env` en la raíz del proyecto (ya está excluido del repositorio por `.gitignore`):
```
EXCEL_SIU_FILENAME=estadisticas de fin de cursada.xlsx
DB_PATH=hurdata.db
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
ADMIN_API_KEY=
MAX_UPLOAD_MB=10
```

| Variable | Descripción | Default |
|---|---|---|
| `EXCEL_SIU_FILENAME` | Nombre del Excel en `/files` para el pipeline por CLI | `estadisticas de fin de cursada.xlsx` |
| `DB_PATH` | Ruta al archivo SQLite | `hurdata.db` (raíz del proyecto) |
| `CORS_ORIGINS` | Orígenes permitidos para el frontend, separados por coma | `http://localhost:5173` |
| `ADMIN_API_KEY` | Clave para los endpoints que modifican datos. Si se deja vacía, no se exige (modo desarrollo) | vacío |
| `MAX_UPLOAD_MB` | Tamaño máximo de un Excel subido por `/upload` | `10` |

> **Producción:** definir siempre `ADMIN_API_KEY` con un valor secreto. Sin ella, cualquiera puede subir o borrar datos.

## Gestión de Archivos Sensibles (Inputs)
Los reportes crudos del SIU Guaraní (archivos `.xlsx`) **NO** deben subirse a GitHub por cuestiones de privacidad de datos.
Colocar el Excel dentro de la carpeta `files/` en la raíz del proyecto. El `.gitignore` ya está configurado para omitir esa carpeta.

---

## Uso

### Levantar la base de datos (primera vez o datos nuevos)

El pipeline ETL lee el Excel configurado en `.env`, lo transforma y lo carga en la DB SQLite. También crea las tablas automáticamente si no existen.

```bash
python -m app.etl.pipeline
```

Output esperado:
```
[ETL] Procesando: estadisticas de fin de cursada.xlsx
[EXTRACT] Leyendo datos desde: ...
[TRANSFORM] 42 actividades y 113 comisiones procesadas.
[DB] Esquema inicializado correctamente.
[LOADER] ✅ Carga completada — 42 materias, 111 comisiones, 365 resultados.
```

La DB puede recargarse con el mismo Excel sin duplicar datos (las inserciones usan upsert).

### Levantar el servidor de desarrollo

```bash
uvicorn app.api.main:app --reload
```

El servidor queda disponible en `http://127.0.0.1:8000`.

### Endpoints disponibles

#### Consultas (GET — públicos)

| Método | URL | Descripción |
|--------|-----|-------------|
| `GET` | `/health` | Estado de la API y lista de tablas en la DB |
| `GET` | `/api/periodos` | Períodos cargados, del más reciente al más antiguo |
| `GET` | `/api/carreras?periodo=...` | Carreras con datos (filtrable por período) |
| `GET` | `/api/periodos-carreras` | Cada combinación período + carrera cargada |
| `GET` | `/api/datos?periodo=...&carrera=...` | Árbol actividades → comisiones → estados |

#### Administración (POST / DELETE — requieren `X-API-Key` si está configurada)

| Método | URL | Descripción |
|--------|-----|-------------|
| `POST` | `/upload` | Carga un `.xlsx` del SIU y ejecuta el pipeline ETL completo |
| `DELETE` | `/api/periodos/{id}?id_carrera=...` | Borra un período (o solo una carrera dentro de él) |
| `DELETE` | `/api/limpiar-db` | Vacía toda la base de datos |

Los endpoints de administración esperan el header `X-API-Key: <valor>` cuando `ADMIN_API_KEY` está definida en `.env`.

### Documentación interactiva (Swagger)

FastAPI genera automáticamente una interfaz para explorar y probar los endpoints:

* **Swagger UI:** `http://127.0.0.1:8000/docs`
* **ReDoc:** `http://127.0.0.1:8000/redoc`

### Correr los tests

```bash
pytest tests/
```

### Inspeccionar la base de datos

**Opción A — Usando Python (sin instalar nada extra):**

```bash
python -c "
import sqlite3
conn = sqlite3.connect('hurdata.db')
conn.row_factory = sqlite3.Row
for t in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\").fetchall():
    n = conn.execute(f'SELECT COUNT(*) FROM {t[0]}').fetchone()[0]
    print(f'{t[0]}: {n} filas')
"
```

**Opción B — Usando el cliente sqlite3 (Windows):**

1. Descargar el zip desde [sqlite.org/download](https://www.sqlite.org/download.html) → sección *Precompiled Binaries for Windows* → **sqlite-tools-win-x64-\*.zip**
2. Descomprimir y copiar el contenido (incluyendo `sqlite3.exe`) a una carpeta, por ejemplo `C:\Program Files (x86)\SQLite3\`
3. Agregar esa carpeta al PATH del usuario: *Panel de control → Variables de entorno → Path → Nuevo*
4. Para aplicar el PATH en una terminal ya abierta sin cerrarla:
   ```powershell
   $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
   ```
5. Luego, desde la raíz del proyecto:
   ```bash
   sqlite3 hurdata.db
   ```

Comandos útiles dentro de la consola SQLite:
```sql
-- Ver todas las tablas
.tables

-- Ver carreras cargadas
SELECT * FROM Carrera;

-- Ver períodos disponibles
SELECT * FROM Periodo;

-- Ver materias con más alumnos libres (top 10)
SELECT m.nombre, SUM(rc.cantidad_alumnos) as libres
FROM Resultado_Comision rc
JOIN Comision c ON rc.id_comision = c.id_comision
JOIN Materia m ON c.id_materia = m.id_materia
JOIN Estado e ON rc.id_estado = e.id_estado
WHERE e.nombre = 'Libre'
GROUP BY m.id_materia
ORDER BY libres DESC
LIMIT 10;

-- Salir
.quit
```

---

## Estructura del Proyecto

```
hurdata-pip-backend/
├── app/
│   ├── api/
│   │   ├── main.py              # FastAPI: app, CORS, lifespan, router de /health
│   │   ├── deps.py              # Dependencias reutilizables: get_db, require_admin
│   │   ├── schemas.py           # Modelos Pydantic de entrada/salida
│   │   └── routers/
│   │       ├── consultas.py     # GET /api/... → endpoints de lectura (públicos)
│   │       └── admin.py         # POST /upload, DELETE /api/... → endpoints que modifican datos (protegidos)
│   ├── db/
│   │   ├── schema.sql           # Definición del DER (8 tablas)
│   │   ├── connection.py        # get_connection(): una conexión SQLite nueva por request
│   │   ├── init_db.py           # Inicializa tablas al arrancar
│   │   ├── loader.py            # Persiste el dict del ETL en la DB
│   │   └── queries.py           # Todo el SQL de lectura y borrado de la API
│   ├── etl/
│   │   ├── extractor.py         # Lee el Excel del SIU
│   │   ├── transformer.py       # Convierte el DataFrame a dict jerárquico
│   │   └── pipeline.py          # Orquesta Extract → Transform → Load
│   └── config.py                # Variables de entorno (con valores por defecto)
├── tests/
│   ├── test_api.py              # Tests de los endpoints HTTP
│   └── test_transformer.py      # Tests del transformer ETL
├── files/                       # Carpeta para Excels del SIU (ignorada por git)
├── .env                         # Variables locales (ignorado por git)
├── requirements.txt
└── README.md
```

---

## Decisiones de arquitectura relevantes

**Separación consultas / administración:** los endpoints de lectura (`routers/consultas.py`) son públicos y sin estado. Los que modifican datos (`routers/admin.py`) están agrupados en un router separado con autenticación por `X-API-Key`, lo que permite protegerlos en producción con un único punto de control.

**Una conexión por request:** `get_connection()` abre una conexión nueva en cada llamada. `deps.get_db()` la entrega al endpoint y la cierra garantizadamente al terminar (incluso si hubo error), evitando los problemas de concurrencia del patrón singleton anterior.

**SQL centralizado:** todo el SQL vive en `db/queries.py`. Los routers solo reciben parámetros HTTP, llaman a una función de queries y devuelven el resultado. Esto hace que las queries sean testeables sin levantar el servidor.
