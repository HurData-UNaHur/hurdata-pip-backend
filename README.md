**HurData** es un Dashboard Analítico de Gestión Académica diseñado para procesar, depurar y visualizar los datos operativos exportados por el sistema SIU Guaraní. Desarrollado en el ámbito del Instituto de Tecnología e Ingeniería de la Universidad Nacional de Hurlingham (UNaHur), el proyecto busca transformar reportes tabulares estáticos en información estratégica e interactiva.

Los reportes nativos del sistema (como las estadísticas de fin de cursada) suelen exportarse con formatos visuales pensados para la lectura humana, lo que dificulta el análisis masivo y programático. HurData resuelve este cuello de botella mediante un pipeline ETL (Extracción, Transformación y Carga) construido en Python, Pandas y FastAPI, automatizando la limpieza de archivos y preparándolos para su consumo en la web.

### ✨ Características Principales
* **Motor de Procesamiento Dinámico:** Limpia y normaliza automáticamente archivos Excel crudos del SIU, aislando los datos reales de los metadatos visuales.
* **Arquitectura Modular Orientada a Objetos:** Código backend estructurado profesionalmente, separando responsabilidades para facilitar el testing, la escalabilidad y el trabajo ágil en equipo.
* **Privacidad por Diseño (Privacy-First):** Configuración estricta de repositorios y entornos para garantizar que los archivos con datos sensibles de la universidad nunca se expongan en la nube pública.
* **API RESTful:** Endpoints rápidos y documentados, organizados por responsabilidad (consultas vs. administración). Las operaciones que modifican datos exigen un usuario con sesión (JWT) y el permiso correspondiente a su rol.
* **Roles y permisos:** cuatro roles (Admin, Directivo, Docente, No Docente) con permisos centralizados en un solo archivo, e historial de quién cargó cada Excel.

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
MAX_UPLOAD_MB=10
JWT_SECRET_KEY=<generar con: python -c "import secrets; print(secrets.token_hex(32))">
SEED_DEFAULT_PASSWORD=
```

| Variable | Descripción | Default |
|---|---|---|
| `EXCEL_SIU_FILENAME` | Nombre del Excel en `/files` para el pipeline por CLI | `estadisticas de fin de cursada.xlsx` |
| `DB_PATH` | Nombre del archivo SQLite. Siempre se crea en la raíz del proyecto: si se pone una ruta, se usa solo el nombre | `hurdata.db` |
| `CORS_ORIGINS` | Orígenes permitidos para el frontend, separados por coma | `http://localhost:5173,http://127.0.0.1:5173` |
| `MAX_UPLOAD_MB` | Tamaño máximo de un Excel subido por `/upload` | `10` |
| `JWT_SECRET_KEY` | Clave para firmar los tokens de sesión. **Obligatoria**: sin ella el servidor no arranca | sin valor |
| `SEED_DEFAULT_PASSWORD` | Contraseña de los usuarios precargados (ver "Usuarios precargados") | definida en `app/config.py` |

> **Producción:** definir una `JWT_SECRET_KEY` propia y secreta, y cambiar `SEED_DEFAULT_PASSWORD`. El archivo `.env.example` sirve de plantilla.

> La variable `ADMIN_API_KEY` y el header `X-API-Key` del esquema anterior ya no se usan: la protección de los endpoints ahora es por usuario y rol.

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
[LOADER] ✅ Carga completada — 42 materias, 113 comisiones, 371 resultados.
```

La DB puede recargarse con el mismo Excel sin duplicar datos (las inserciones usan upsert).

### Levantar el servidor de desarrollo

```bash
uvicorn app.api.main:app --reload
```

El servidor queda disponible en `http://127.0.0.1:8000`.

### Endpoints disponibles

Los endpoints protegidos esperan el header `Authorization: Bearer <token>`, con el token que devuelve `POST /api/login`. El token dura 8 horas.

#### Públicos (sin sesión, para el modo invitado)

| Método | URL | Descripción |
|--------|-----|-------------|
| `GET` | `/health` | Estado de la API y lista de tablas en la DB |
| `GET` | `/api/periodos` | Períodos cargados, del más reciente al más antiguo |
| `GET` | `/api/carreras?periodo=...` | Carreras con datos (filtrable por período) |
| `GET` | `/api/datos?periodo=...&carrera=...` | Árbol actividades → comisiones → estados |
| `GET` | `/api/evolucion?carrera=...&materia=...` | Estados por período de una carrera, o de una materia si se indica su código. Incluye la lista de materias de la carrera |
| `GET` | `/api/institutos` | Institutos para el selector de registro (sin emails) |
| `POST` | `/api/login` | Recibe `{usuario, password}` y devuelve `{access_token, token_type}` |

#### Con sesión

| Método | URL | Permiso | Descripción |
|--------|-----|---------|-------------|
| `GET` | `/api/periodos-carreras` | cualquier usuario con sesión | Cada combinación período + carrera cargada |
| `GET` | `/api/carga-activa?periodo=...&carrera=...` | cualquier usuario con sesión | Quién cargó los datos activos de ese período y carrera, y cuándo |
| `GET` | `/api/cargas?estado=...` | `cargas:ver` | Historial de cargas (`activa`, `reemplazada` o `borrada`). Docente ve las suyas; Directivo y Admin, todas |
| `POST` | `/upload` | `datos:cargar` | Carga un `.xlsx` del SIU y ejecuta el pipeline ETL. Con `?reemplaza={id_carga}` se sube una "nueva versión" de una carga activa (tiene que ser del mismo período y carrera) |
| `DELETE` | `/api/periodos/{id}?id_carrera=...` | `datos:borrar` | Borra un período, o solo una carrera dentro de él. Docente solo puede borrar lo que cargó él |
| `DELETE` | `/api/limpiar-db` | `db:resetear` | Vacía los datos académicos (el historial de cargas se conserva) |

Si un `POST /upload` apunta a un período y carrera que ya tienen datos, los reemplaza, pero solo si quien sube es el dueño de esa carga, un Directivo o un Admin. En otro caso responde 403.

### Roles y permisos

Todo está en `app/api/permisos.py`: ahí se asignan los permisos a cada rol y es el único lugar a tocar para cambiarlos.

| Permiso | Admin | Directivo | Docente | No Docente |
|---|:-:|:-:|:-:|:-:|
| `datos:cargar` (subir Excel) | ✅ | ✅ | ✅ | ❌ |
| `datos:borrar` (borrar lo propio) | ✅ | ✅ | ✅ | ❌ |
| `datos:borrar_cualquiera` | ✅ | ✅ | ❌ | ❌ |
| `cargas:ver` (historial propio) | ✅ | ✅ | ✅ | ❌ |
| `cargas:ver_todas` | ✅ | ✅ | ❌ | ❌ |
| `registros:aprobar` | ✅ | ✅ | ❌ | ❌ |
| `db:resetear` | ✅ | ❌ | ❌ | ❌ |
| `usuarios:gestionar` | ✅ | ❌ | ❌ | ❌ |

Ver los datos (períodos, carreras, datos, evolución) no requiere permiso. El usuario **No Docente** solo consulta.

Los permisos `registros:aprobar` y `usuarios:gestionar` están definidos, pero todavía no hay endpoints que los usen (registro de usuarios y recuperación de contraseña quedan pendientes).

### Usuarios precargados

En cada arranque, `app/db/seed.py` crea (si no existen) los institutos y estos usuarios, todos con la contraseña de `SEED_DEFAULT_PASSWORD`:

| Usuario | Rol |
|---|---|
| `admin@unahur.edu.ar` | Admin |
| `directivo@unahur.edu.ar` | Directivo |
| `docente@unahur.edu.ar` | Docente |
| `nodocente@unahur.edu.ar` | No Docente |

Los usuarios que ya existen no se pisan al reiniciar. Los institutos se identifican por email: si se cambia un nombre en `seed.py`, se actualiza en la base. Si un rol del seed no es válido, el servidor no arranca.

### Historial de cargas

Cada subida de un Excel queda registrada en la tabla `Carga`: quién la hizo, cuándo, el nombre del archivo y cuántas materias, comisiones y resultados tenía. Para cada período y carrera hay como mucho una carga `activa`, y su autor es el dueño de esos datos. Al recargar, la anterior pasa a `reemplazada`. Al borrar, pasa a `borrada`. El historial sobrevive al borrado de los datos y el archivo en sí no se guarda.

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
│   │   ├── auth.py              # JWT: crear y validar tokens, hash de contraseñas
│   │   ├── permisos.py          # Qué puede hacer cada rol (único lugar donde se asignan)
│   │   ├── deps.py              # Dependencias: get_db, get_usuario_actual, require_permiso
│   │   ├── schemas.py           # Modelos Pydantic de entrada/salida
│   │   └── routers/
│   │       ├── consultas.py     # GET de períodos, carreras, datos y evolución
│   │       ├── auth.py          # POST /api/login, GET /api/institutos
│   │       ├── cargas.py        # GET /api/cargas, /api/carga-activa (historial)
│   │       └── admin.py         # POST /upload, DELETE /api/... (piden permiso)
│   ├── db/
│   │   ├── schema.sql           # Definición del DER (tablas académicas, Usuario, Directivo y Carga)
│   │   ├── connection.py        # get_connection(): una conexión SQLite nueva por request
│   │   ├── init_db.py           # Inicializa tablas al arrancar
│   │   ├── seed.py              # Institutos y usuarios precargados (se corre en cada arranque)
│   │   ├── reset_db.py          # Vacía las tablas académicas
│   │   ├── loader.py            # Persiste el dict del ETL en la DB
│   │   └── queries.py           # Todo el SQL de la API
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

**Separación consultas / administración:** los endpoints de lectura de datos (`routers/consultas.py`) son públicos para que funcione el modo invitado del frontend. Los que modifican datos (`routers/admin.py`) piden un JWT y un permiso.

**Permisos, no roles:** cada endpoint declara el permiso que necesita con `Depends(require_permiso(...))` y nunca pregunta por un rol. La tabla de qué rol tiene qué permiso vive solo en `app/api/permisos.py`.

**Dueño de la carga:** el historial (`Carga`) guarda quién subió los datos de cada período y carrera. Un Docente solo puede borrar o reemplazar lo que cargó él. Directivo y Admin pueden con cualquier carga.

**Una conexión por request:** `get_connection()` abre una conexión nueva en cada llamada. `deps.get_db()` la entrega al endpoint y la cierra garantizadamente al terminar (incluso si hubo error), evitando los problemas de concurrencia del patrón singleton anterior.

**SQL centralizado:** todo el SQL vive en `db/queries.py`. Los routers solo reciben parámetros HTTP, llaman a una función de queries y devuelven el resultado. Esto hace que las queries sean testeables sin levantar el servidor.
