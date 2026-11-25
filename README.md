**HurData** es un Dashboard Analítico de Gestión Académica diseñado para procesar, depurar y visualizar los datos operativos exportados por el sistema SIU Guaraní. Desarrollado en el ámbito del Instituto de Tecnología e Ingeniería de la Universidad Nacional de Hurlingham (UNaHur), el proyecto busca transformar reportes tabulares estáticos en información estratégica e interactiva.

Los reportes nativos del sistema (como las estadísticas de fin de cursada) suelen exportarse con formatos visuales pensados para la lectura humana, lo que dificulta el análisis masivo y programático. HurData resuelve este cuello de botella mediante un pipeline ETL (Extracción, Transformación y Carga) construido en Python, Pandas y FastAPI, automatizando la limpieza de archivos y preparándolos para su consumo en la web.

### ✨ Características Principales
* **Motor de Procesamiento Dinámico:** Limpia y normaliza automáticamente archivos Excel crudos del SIU, aislando los datos reales de los metadatos visuales.
* **Arquitectura Modular Orientada a Objetos:** Código backend estructurado profesionalmente, separando responsabilidades para facilitar el testing, la escalabilidad y el trabajo ágil en equipo.
* **Privacidad por Diseño (Privacy-First):** Configuración estricta de repositorios y entornos para garantizar que los archivos con datos sensibles de la universidad nunca se expongan en la nube pública.
* **API RESTful:** Endpoints rápidos y documentados, organizados por responsabilidad (consultas vs. administración). Las operaciones que modifican datos exigen un usuario con sesión (JWT) y el permiso correspondiente a su rol.
* **Roles y permisos:** cuatro roles (Admin, Directivo, Docente, No Docente) con permisos centralizados en un solo archivo, e historial de quién cargó cada Excel.
* **Cuentas y accesos:** registro y recuperación de contraseña por solicitud (sin servidor de mail), Mi cuenta con cambio de contraseña y límite de intentos, y gestión de cuentas por el Admin (cambiar rol, revocar y reactivar acceso). El rol y el estado de la cuenta se leen de la base en cada pedido.

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

#### Públicos (sin sesión)

| Método | URL | Descripción |
|--------|-----|-------------|
| `GET` | `/health` | Estado de la API y lista de tablas en la DB |
| `GET` | `/api/periodos` | Períodos cargados, del más reciente al más antiguo |
| `GET` | `/api/carreras?periodo=...` | Carreras con datos (filtrable por período) |
| `GET` | `/api/datos?periodo=...&carrera=...` | Árbol actividades → comisiones → estados |
| `GET` | `/api/evolucion?carrera=...&materia=...` | Estados por período de una carrera, o de una materia si se indica su código. Incluye la lista de materias de la carrera |
| `GET` | `/api/institutos` | Institutos para el selector de registro (sin emails) |
| `POST` | `/api/login` | Recibe `{usuario, password}` y devuelve `{access_token, token_type}` |
| `POST` | `/api/registro/solicitar` | Pide el alta de un usuario (correo `@unahur.edu.ar`, rol, instituto y contraseña). Queda pendiente de aprobación |
| `POST` | `/api/recuperar-password/solicitar` | Pide la recuperación de contraseña. Responde lo mismo exista o no el correo |
| `POST` | `/api/recuperar-password/canjear` | Cambia la contraseña con un código aprobado: `{usuario, codigo, nueva_password}` |

#### Con sesión

| Método | URL | Permiso | Descripción |
|--------|-----|---------|-------------|
| `GET` | `/api/periodos-carreras` | cualquier usuario con sesión | Cada combinación período + carrera cargada |
| `GET` | `/api/carga-activa?periodo=...&carrera=...` | cualquier usuario con sesión | Quién cargó los datos activos de ese período y carrera, y cuándo |
| `GET` | `/api/cargas?estado=...` | `cargas:ver` | Historial de cargas (`activa`, `reemplazada` o `borrada`). Docente ve las suyas; Directivo y Admin, todas |
| `POST` | `/upload` | `datos:cargar` | Carga un `.xlsx` del SIU y ejecuta el pipeline ETL. Con `?reemplaza={id_carga}` se sube una "nueva versión" de una carga activa (tiene que ser del mismo período y carrera) |
| `DELETE` | `/api/periodos/{id}?id_carrera=...` | `datos:borrar` | Borra un período, o solo una carrera dentro de él. Docente solo puede borrar lo que cargó él |
| `DELETE` | `/api/limpiar-db` | `db:resetear` | Vacía los datos académicos (el historial de cargas se conserva) |
| `GET` | `/api/registro/solicitudes` | `registros:aprobar` | Solicitudes de alta pendientes |
| `POST` | `/api/registro/solicitudes/{id}/{aprobar\|rechazar}` | `registros:aprobar` | Aprueba (con el rol a asignar, opcional) o rechaza una solicitud de alta |
| `GET` | `/api/recuperacion/solicitudes` | `registros:aprobar` | Solicitudes de recuperación pendientes |
| `POST` | `/api/recuperacion/solicitudes/{id}/{aprobar\|rechazar}` | `registros:aprobar` | Aprobar devuelve el código de un solo uso, una única vez |
| `GET` | `/api/registro/historial` | `registros:aprobar` | Solicitudes de alta ya resueltas (aprobadas y rechazadas). El Admin ve todas; el Directivo, las de su instituto |
| `GET` | `/api/perfil` | cualquier usuario con sesión | Datos de la cuenta: nombre, correo, cargo, rol e instituto |
| `POST` | `/api/perfil/cambiar-password` | cualquier usuario con sesión | Cambia la contraseña: `{password_actual, password_nueva}`. Tras 5 errores seguidos bloquea el cambio 15 minutos (429) |
| `GET` | `/api/usuarios` | `usuarios:gestionar` | Lista de cuentas con rol, instituto y estado |
| `POST` | `/api/usuarios/{usuario}/rol` | `usuarios:gestionar` | Cambia el rol de otra cuenta: `{rol}` |
| `POST` | `/api/usuarios/{usuario}/estado` | `usuarios:gestionar` | Revoca o reactiva el acceso de otra cuenta: `{activo}` |

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

El permiso `registros:aprobar` lo usan los endpoints de solicitudes de registro y de recuperación. El permiso `usuarios:gestionar` (solo Admin) habilita los endpoints de `/api/usuarios` y decide quién puede restablecer cuentas Admin y Directivo.

### Registro y recuperación de contraseña

**Reglas.** El correo tiene que ser `nombre@unahur.edu.ar`. La contraseña nueva tiene entre 8 y 72 caracteres, con una mayúscula, una minúscula, un número y un símbolo, y distinta de la anterior. El login no aplica estas reglas: solo exige usuario y contraseña. Las reglas viven en `app/api/validaciones.py` y el frontend las repite solo para avisar mientras se escribe.

**Registro.** La persona pide el alta con su instituto y un rol. Un Directivo o un Admin la ve en la sección Accesos del frontend y la aprueba (pudiendo cambiar el rol) o la rechaza. La cuenta queda asociada al instituto que eligió. Hoy cualquier Directivo ve las solicitudes pendientes de todos los institutos. Las solicitudes rechazadas no se borran: quedan en el historial (si la persona vuelve a pedir el alta, se descarta la rechazada anterior).

**Recuperación (sin servidor de mail).**
1. La persona pide la recuperación con su correo.
2. Un Directivo o un Admin la aprueba y el sistema le muestra un código de un solo uso (vale 60 minutos). Se muestra una única vez y en la base se guarda hasheado.
3. Quien aprueba le pasa el código a la persona (en persona, por teléfono o chat), que lo canjea y elige su nueva contraseña.

Reglas de seguridad: nadie puede aprobar su propia solicitud; las cuentas Admin y Directivo solo las restablece un Admin; el código se bloquea tras 5 intentos fallidos; un código nuevo reemplaza al anterior; y si el Admin pierde su contraseña, la restablece otro Admin o se hace a mano en la base. Cambiar el código por un mail es agregar el envío en `aprobar` sin tocar el resto.

### Mi cuenta y gestión de cuentas

**Cambio de contraseña.** `POST /api/perfil/cambiar-password` pide la contraseña actual. Si está mal responde 400 (no 401, para no confundirlo con una sesión vencida) y avisa cuántos intentos quedan. Al quinto error seguido bloquea el cambio 15 minutos y responde 429, aunque después se escriba la contraseña correcta. Un cambio exitoso reinicia el contador. Los contadores están en la tabla `Usuario` (`intentos_password` y `bloqueo_password_hasta`).

**Gestión de cuentas (solo Admin).** Cambiar el rol y revocar o reactivar el acceso. Nadie puede modificar su propia cuenta, así que siempre queda al menos un Admin. Una cuenta revocada no puede iniciar sesión (403 con la contraseña correcta) y su sesión abierta deja de valer (401): `get_usuario_actual` lee el rol y el estado de la base en cada pedido, así que cambiar un rol o revocar un acceso rige de inmediato, sin esperar a que venza el token.

**Migración.** Las columnas `id_directivo` (instituto), `activo` y las de intentos se agregan a `Usuario` al arrancar si la base es anterior (`migrar` en `init_db.py`); las cuentas creadas por solicitud conservan el instituto que eligieron. Las cuentas precargadas no tienen instituto, salvo `directivo@`, que pertenece a Tecnología e Ingeniería.

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

Son 35 tests: `test_api.py` cubre login, permisos por rol, carga, reemplazo, borrado, historial, registro, recuperación de contraseña, Mi cuenta, límite de intentos, migración de la base, gestión de cuentas e historial de solicitudes; `test_transformer.py` cubre el ETL.

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
│   │       ├── auth.py          # login, institutos, registro, recuperación de contraseña y Mi cuenta
│   │       ├── usuarios.py      # gestión de cuentas (Admin) e historial de solicitudes
│   │       ├── cargas.py        # GET /api/cargas, /api/carga-activa (historial)
│   │       └── admin.py         # POST /upload, DELETE /api/... (piden permiso)
│   ├── db/
│   │   ├── schema.sql           # Definición del DER (tablas académicas, Usuario, Directivo, Carga y solicitudes)
│   │   ├── connection.py        # get_connection(): una conexión SQLite nueva por request
│   │   ├── init_db.py           # Inicializa tablas al arrancar y migra bases anteriores
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

**Separación consultas / administración:** los endpoints de lectura de datos (`routers/consultas.py`) son públicos en la API (sirven para pruebas y herramientas externas); el frontend ya no tiene modo invitado y exige iniciar sesión. Los que modifican datos (`routers/admin.py`) piden un JWT y un permiso.

**Permisos, no roles:** cada endpoint declara el permiso que necesita con `Depends(require_permiso(...))` y nunca pregunta por un rol. La tabla de qué rol tiene qué permiso vive solo en `app/api/permisos.py`.

**Dueño de la carga:** el historial (`Carga`) guarda quién subió los datos de cada período y carrera. Un Docente solo puede borrar o reemplazar lo que cargó él. Directivo y Admin pueden con cualquier carga.

**Una conexión por request:** `get_connection()` abre una conexión nueva en cada llamada. `deps.get_db()` la entrega al endpoint y la cierra garantizadamente al terminar (incluso si hubo error), evitando los problemas de concurrencia del patrón singleton anterior.

**SQL centralizado:** todo el SQL vive en `db/queries.py`. Los routers solo reciben parámetros HTTP, llaman a una función de queries y devuelven el resultado. Esto hace que las queries sean testeables sin levantar el servidor.
