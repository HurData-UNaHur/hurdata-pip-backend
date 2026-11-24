"""
routers/auth.py
===============
Autenticación, institutos, solicitudes de registro y recuperación de contraseña.

Recuperación por solicitud (no hay servidor de mail):
    1. El usuario pide la recuperación con su correo.
    2. Un Directivo o Admin la aprueba y el sistema le muestra un código de un solo uso.
    3. Quien aprueba le pasa el código al usuario, que lo canjea y elige su nueva contraseña.
Las cuentas Admin y Directivo solo las puede resetear un Admin, y nadie puede aprobar la suya.
"""
import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api import permisos as P
from app.api.auth import crear_token, hashear_password, verificar_password
from app.api.deps import get_db, get_usuario_actual, require_permiso
from app.api.schemas import (
    CambiarPasswordIn,
    CanjearCodigoIn,
    CodigoRecuperacionOut,
    InstitutosOut,
    LoginIn,
    MensajeOut,
    PerfilOut,
    ResolverSolicitudIn,
    SolicitarRecuperacionIn,
    SolicitudRegistroIn,
    SolicitudesOut,
    SolicitudesRecuperacionOut,
    TokenOut,
)
from app.api.validaciones import email_institucional_valido, mensaje_password, normalizar_email
from app.db import queries

router = APIRouter(tags=["Autenticación"])

ROLES_SOLICITABLES = ("directivo", "docente", "no_docente")
ROLES_PRIVILEGIADOS = ("admin", "directivo")   # solo un Admin resetea estas cuentas

CODIGO_VALIDEZ_MIN = 60
CODIGO_MAX_INTENTOS = 5
PASSWORD_MAX_INTENTOS = 5     # errores seguidos de contraseña actual en "Mi cuenta"
PASSWORD_BLOQUEO_MIN = 15
_ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sin 0/O ni 1/I para que se dicte bien
_ERROR_CODIGO = "El código es incorrecto o venció. Pedí uno nuevo."


# ---------------------------------------------------------------------------
# Login e institutos
# ---------------------------------------------------------------------------

@router.post("/api/login", response_model=TokenOut)
def login(body: LoginIn, conn=Depends(get_db)):
    """Autentica un usuario y devuelve un JWT Bearer. 401 si usuario o contraseña no coinciden."""
    row = conn.execute(
        "SELECT usuario, nombre, cargo, role, password_hash, activo FROM Usuario WHERE usuario = ?",
        (normalizar_email(body.usuario),),
    ).fetchone()

    if row is None or not verificar_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
    if not row["activo"]:
        # Se avisa recién con la contraseña correcta, para no revelar qué cuentas existen
        raise HTTPException(status_code=403, detail="Tu acceso fue revocado. Consultá con un administrador.")

    token = crear_token({
        "sub": row["usuario"],
        "nombre": row["nombre"],
        "cargo": row["cargo"],
        "role": row["role"],
        # Solo para que el frontend muestre u oculte botones. El backend NO confía
        # en esta lista: la recalcula desde el rol en cada request (deps.py).
        "permisos": sorted(P.permisos_de(row["role"])),
    })
    return {"access_token": token, "token_type": "bearer"}


@router.get("/api/institutos", response_model=InstitutosOut)
def institutos(conn=Depends(get_db)):
    """Institutos para el selector del registro. Devuelve solo id y nombre (sin emails)."""
    return {"institutos": queries.listar_institutos(conn)}


# ---------------------------------------------------------------------------
# Mi cuenta (usuario con sesión iniciada)
# ---------------------------------------------------------------------------

@router.get("/api/perfil", response_model=PerfilOut)
def perfil(conn=Depends(get_db), actual: dict = Depends(get_usuario_actual)):
    """Datos de la cuenta con sesión iniciada. Se leen de la base, no del token."""
    datos = queries.obtener_perfil(conn, actual["sub"])
    if datos is None:
        raise HTTPException(status_code=404, detail="La cuenta ya no existe.")
    return datos


@router.post("/api/perfil/cambiar-password", response_model=MensajeOut)
def cambiar_password(body: CambiarPasswordIn, conn=Depends(get_db), actual: dict = Depends(get_usuario_actual)):
    """
    Cambia la contraseña de quien tiene la sesión iniciada, pidiendo la actual.
    Devuelve 400 (no 401) si la actual está mal, para no confundirlo con una sesión vencida.
    """
    usuario = actual["sub"]
    hash_actual = queries.hash_password_de(conn, usuario)
    if hash_actual is None:
        raise HTTPException(status_code=404, detail="La cuenta ya no existe.")

    # Límite de intentos: tras PASSWORD_MAX_INTENTOS errores seguidos se bloquea el cambio un rato
    intentos, bloqueo_hasta = queries.estado_intentos_password(conn, usuario)
    ahora = datetime.now(timezone.utc)
    if bloqueo_hasta:
        segundos = (datetime.fromisoformat(bloqueo_hasta) - ahora).total_seconds()
        if segundos > 0:
            minutos = max(1, -(-int(segundos) // 60))
            raise HTTPException(
                status_code=429,
                detail=f"Superaste los intentos permitidos. Probá de nuevo en {minutos} minutos.",
            )
        intentos = 0   # el bloqueo ya venció

    if not verificar_password(body.password_actual, hash_actual):
        intentos += 1
        if intentos >= PASSWORD_MAX_INTENTOS:
            hasta = (ahora + timedelta(minutes=PASSWORD_BLOQUEO_MIN)).isoformat(timespec="seconds")
            queries.guardar_intentos_password(conn, usuario, 0, hasta)
            raise HTTPException(
                status_code=429,
                detail=f"Superaste los intentos permitidos. Probá de nuevo en {PASSWORD_BLOQUEO_MIN} minutos.",
            )
        queries.guardar_intentos_password(conn, usuario, intentos, None)
        restantes = PASSWORD_MAX_INTENTOS - intentos
        raise HTTPException(
            status_code=400,
            detail=f"La contraseña actual no es correcta. Te quedan {restantes} {'intento' if restantes == 1 else 'intentos'}.",
        )

    error_password = mensaje_password(body.password_nueva)
    if error_password:
        raise HTTPException(status_code=400, detail=error_password)
    if verificar_password(body.password_nueva, hash_actual):
        raise HTTPException(status_code=400, detail="La nueva contraseña no puede ser igual a la anterior.")

    queries.actualizar_password(conn, usuario, hashear_password(body.password_nueva))
    return {"message": "Contraseña actualizada correctamente."}

# ---------------------------------------------------------------------------
# Solicitudes de registro
# ---------------------------------------------------------------------------

@router.post("/api/registro/solicitar", response_model=MensajeOut, status_code=201)
def solicitar_registro(body: SolicitudRegistroIn, conn=Depends(get_db)):
    email = normalizar_email(body.email)
    nombre = body.nombre.strip()

    if not email_institucional_valido(email):
        raise HTTPException(status_code=400, detail="Usá un correo institucional válido (nombre@unahur.edu.ar).")
    if len(nombre) < 3:
        raise HTTPException(status_code=400, detail="El nombre debe tener al menos 3 caracteres.")
    if body.rol not in ROLES_SOLICITABLES:
        raise HTTPException(status_code=400, detail="Rol inválido.")
    error_password = mensaje_password(body.password)
    if error_password:
        raise HTTPException(status_code=400, detail=error_password)
    if conn.execute("SELECT 1 FROM Directivo WHERE id_directivo = ?", (body.id_instituto,)).fetchone() is None:
        raise HTTPException(status_code=400, detail="El instituto elegido no existe.")

    if conn.execute("SELECT 1 FROM Usuario WHERE usuario = ?", (email,)).fetchone():
        raise HTTPException(status_code=409, detail="Ese correo ya está registrado.")

    queries.descartar_solicitud_rechazada(conn, email)   # una solicitud rechazada antes no impide pedir de nuevo

    try:
        queries.crear_solicitud_registro(
            conn=conn,
            email=email,
            nombre=nombre,
            password_hash=hashear_password(body.password),
            rol=body.rol,
            id_instituto=body.id_instituto,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Ya existe una solicitud pendiente para ese correo.")

    return {"message": "Solicitud enviada correctamente."}


@router.get("/api/registro/solicitudes", response_model=SolicitudesOut)
def listar_solicitudes(
    conn=Depends(get_db),
    usuario: dict = Depends(require_permiso(P.APROBAR_REGISTROS)),
):
    return {"solicitudes": queries.listar_solicitudes_pendientes(conn)}


@router.post("/api/registro/solicitudes/{id_solicitud}/{accion}", response_model=MensajeOut)
def resolver_solicitud(
    id_solicitud: int,
    accion: str,
    body: ResolverSolicitudIn | None = Body(default=None),
    conn=Depends(get_db),
    usuario: dict = Depends(require_permiso(P.APROBAR_REGISTROS)),
):
    if accion not in ("aprobar", "rechazar"):
        raise HTTPException(status_code=400, detail="Acción inválida. Usar 'aprobar' o 'rechazar'.")
    if body and body.rol and body.rol not in ROLES_SOLICITABLES:
        raise HTTPException(status_code=400, detail="Rol inválido.")

    try:
        estado = queries.resolver_solicitud_registro(
            conn=conn,
            id_solicitud=id_solicitud,
            accion=accion,
            resuelto_por=usuario["sub"],
            rol_asignado=body.rol if body else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="El usuario ya existe en el sistema.")

    return {"message": f"Solicitud {estado} correctamente."}


# ---------------------------------------------------------------------------
# Recuperación de contraseña por solicitud
# ---------------------------------------------------------------------------

def _normalizar_codigo(codigo: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", codigo.upper())


def _hash_codigo(usuario: str, codigo: str) -> str:
    return hashlib.sha256(f"{usuario}:{_normalizar_codigo(codigo)}".encode()).hexdigest()


def _generar_codigo() -> str:
    letras = "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(8))
    return f"{letras[:4]}-{letras[4:]}"


def _puede_resetear(aprobador: dict, rol_objetivo: str) -> bool:
    """Admin y Directivo resetean Docente y No Docente. Solo el Admin resetea Admin y Directivo."""
    if rol_objetivo in ROLES_PRIVILEGIADOS:
        return P.GESTIONAR_USUARIOS in aprobador["permisos"]
    return True


@router.post("/api/recuperar-password/solicitar", response_model=MensajeOut)
def solicitar_recuperacion(body: SolicitarRecuperacionIn, conn=Depends(get_db)):
    """
    Pide la recuperación. Responde siempre lo mismo, exista o no el correo,
    para no revelar qué cuentas existen.
    """
    usuario = normalizar_email(body.usuario)
    if queries.buscar_usuario(conn, usuario):
        queries.crear_solicitud_recuperacion(conn, usuario)
    return {
        "message": "Si el correo está registrado, la solicitud quedó enviada. "
                   "Un directivo o administrador va a revisarla y te va a dar un código."
    }


@router.get("/api/recuperacion/solicitudes", response_model=SolicitudesRecuperacionOut)
def listar_solicitudes_recuperacion(
    conn=Depends(get_db),
    usuario: dict = Depends(require_permiso(P.APROBAR_REGISTROS)),
):
    privilegiado = P.GESTIONAR_USUARIOS in usuario["permisos"]
    return {"solicitudes": queries.listar_solicitudes_recuperacion(conn, privilegiado)}


@router.post("/api/recuperacion/solicitudes/{id_solicitud}/{accion}", response_model=CodigoRecuperacionOut)
def resolver_solicitud_recuperacion(
    id_solicitud: int,
    accion: str,
    conn=Depends(get_db),
    usuario: dict = Depends(require_permiso(P.APROBAR_REGISTROS)),
):
    """Aprobar devuelve el código UNA sola vez. Rechazar cierra la solicitud."""
    if accion not in ("aprobar", "rechazar"):
        raise HTTPException(status_code=400, detail="Acción inválida. Usar 'aprobar' o 'rechazar'.")

    sol = queries.obtener_solicitud_recuperacion(conn, id_solicitud)
    if sol is None or sol["estado"] != "pendiente":
        raise HTTPException(status_code=404, detail="La solicitud no existe o ya fue resuelta.")
    if sol["usuario"] == usuario["sub"]:
        raise HTTPException(status_code=403, detail="No podés aprobar tu propia solicitud. Pedile a otra persona.")
    if not _puede_resetear(usuario, sol["role"]):
        raise HTTPException(status_code=403, detail="Esta cuenta solo la puede restablecer un administrador.")

    if accion == "rechazar":
        queries.rechazar_solicitud_recuperacion(conn, id_solicitud, usuario["sub"])
        return {"message": "Solicitud rechazada."}

    codigo = _generar_codigo()
    expira = (datetime.now(timezone.utc) + timedelta(minutes=CODIGO_VALIDEZ_MIN)).isoformat(timespec="seconds")
    queries.aprobar_solicitud_recuperacion(
        conn, id_solicitud, usuario["sub"], _hash_codigo(sol["usuario"], codigo), expira
    )
    return {
        "message": f"Solicitud aprobada. Pasale el código a {sol['usuario']}: vale {CODIGO_VALIDEZ_MIN} minutos y se usa una sola vez.",
        "codigo": codigo,
        "expira_en": expira,
    }


@router.post("/api/recuperar-password/canjear", response_model=MensajeOut)
def canjear_codigo(body: CanjearCodigoIn, conn=Depends(get_db)):
    """Cambia la contraseña con un código aprobado. Mismo error para cualquier fallo del código."""
    usuario = normalizar_email(body.usuario)
    cuenta = queries.buscar_usuario(conn, usuario)
    sol = queries.solicitud_recuperacion_aprobada(conn, usuario) if cuenta else None
    if sol is None:
        raise HTTPException(status_code=400, detail=_ERROR_CODIGO)

    if datetime.fromisoformat(sol["expira_en"]) < datetime.now(timezone.utc):
        queries.rechazar_solicitud_recuperacion(conn, sol["id_solicitud"], "sistema")
        raise HTTPException(status_code=400, detail=_ERROR_CODIGO)

    if not hmac.compare_digest(sol["codigo_hash"], _hash_codigo(usuario, body.codigo)):
        queries.sumar_intento_recuperacion(conn, sol["id_solicitud"], CODIGO_MAX_INTENTOS)
        raise HTTPException(status_code=400, detail=_ERROR_CODIGO)

    error_password = mensaje_password(body.nueva_password)
    if error_password:
        raise HTTPException(status_code=400, detail=error_password)
    if verificar_password(body.nueva_password, cuenta["password_hash"]):
        raise HTTPException(status_code=400, detail="La nueva contraseña no puede ser igual a la anterior.")

    queries.canjear_recuperacion(conn, sol["id_solicitud"], usuario, hashear_password(body.nueva_password))
    return {"message": "Contraseña actualizada correctamente."}
