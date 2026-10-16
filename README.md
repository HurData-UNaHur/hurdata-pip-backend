**HurData** es un Dashboard Analítico de Gestión Académica diseñado para procesar, depurar y visualizar los datos operativos exportados por el sistema SIU Guaraní. Desarrollado en el ámbito del Instituto de Tecnología e Ingeniería de la Universidad Nacional de Hurlingham (UNaHur), el proyecto busca transformar reportes tabulares estáticos en información estratégica e interactiva.

Los reportes nativos del sistema (como las estadísticas de fin de cursada) suelen exportarse con formatos visuales pensados para la lectura humana, lo que dificulta el análisis masivo y programático. HurData resuelve este cuello de botella mediante un pipeline ETL (Extracción, Transformación y Carga) construido en Python, Pandas y FastAPI, automatizando la limpieza de archivos y preparándolos para su consumo en la web.

### ✨ Características Principales
* **Motor de Procesamiento Dinámico:** Limpia y normaliza automáticamente archivos Excel crudos del SIU, aislando los datos reales de los metadatos visuales.
* **Arquitectura Modular Orientada a Objetos:** Código backend estructurado profesionalmente, separando responsabilidades para facilitar el testing, la escalabilidad y el trabajo ágil en equipo.
* **Privacidad por Diseño (Privacy-First):** Configuración estricta de repositorios y entornos para garantizar que los archivos con datos sensibles de la universidad nunca se expongan en la nube pública.
* **API RESTful:** Exposición de endpoints rápidos y documentados, optimizados para alimentar de forma directa los gráficos interactivos del frontend.

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
```

`DB_PATH` es opcional — si no se define, la base de datos se crea automáticamente como `hurdata.db` en la raíz del proyecto.

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
[DB] Conexión abierta: hurdata.db
[DB] Esquema inicializado correctamente.
[LOADER] ✅ Carga completada — 42 materias, 111 comisiones, 365 resultados.
```

La DB puede recargarse con el mismo Excel sin duplicar datos (todas las inserciones usan upsert).

### Levantar el servidor de desarrollo

```bash
uvicorn app.api.main:app --reload
```

El servidor queda disponible en `http://127.0.0.1:8000`.

### Endpoints disponibles

| Método | URL | Descripción |
|--------|-----|-------------|
| `GET`  | `http://127.0.0.1:8000/health` | Estado de la API y lista de tablas en la DB |
| `POST` | `http://127.0.0.1:8000/upload` | Carga un `.xlsx` del SIU y ejecuta el pipeline ETL |

### Documentación interactiva (Swagger)

FastAPI genera automáticamente una interfaz para explorar y probar los endpoints:

* **Swagger UI:** `http://127.0.0.1:8000/docs`
* **ReDoc:** `http://127.0.0.1:8000/redoc`

### Inspeccionar la base de datos

Para verificar el contenido de la DB directamente desde la terminal (requiere tener `sqlite3` instalado):

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
│   │   └── main.py          # FastAPI: endpoints, CORS, lifespan
│   ├── db/
│   │   ├── schema.sql        # Definición del DER (8 tablas)
│   │   ├── connection.py     # Conexión SQLite singleton
│   │   ├── init_db.py        # Inicializa tablas al arrancar
│   │   └── loader.py         # Carga el dict del ETL a la DB
│   ├── etl/
│   │   ├── extractor.py      # Lee el Excel del SIU
│   │   ├── transformer.py    # Convierte el DataFrame a dict jerárquico
│   │   └── pipeline.py       # Orquesta Extract → Transform → Load
│   └── config.py             # Variables de entorno (EXCEL_SIU_FILENAME, DB_PATH)
├── files/                    # Carpeta para Excels del SIU (ignorada por git)
├── .env                      # Variables locales (ignorado por git)
├── requirements.txt
└── README.md
```
