"""
routers/auth.py
===============
Endpoints de autenticación, institutos y solicitudes de registro.
"""
import sqlite3
import secrets 
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from app.api import permisos as P
from app.api.auth import crear_token, hashear_password, verificar_password
from app.api.deps import get_db, require_permiso
from app.api.schemas import (
    InstitutosOut,
    LoginIn,
    MensajeOut,
    SolicitudRegistroIn,
    SolicitudesOut,
    TokenOut,
)
from app.db import queries

router = APIRouter(tags=["Autenticación"])

DOMINIOS_PERMITIDOS = ("@unahur.edu.ar",)


class ResolverSolicitudIn(BaseModel):
    rol: str | None = None


@router.post("/api/login", response_model=TokenOut)
def login(body: LoginIn, conn=Depends(get_db)):
    row = conn.execute(
        "SELECT usuario, nombre, cargo, role, password_hash FROM Usuario WHERE usuario = ?",
        (body.usuario.strip().lower(),),
    ).fetchone()

    if row is None or not verificar_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")

    token = crear_token({
        "sub": row["usuario"],
        "nombre": row["nombre"],
        "cargo": row["cargo"],
        "role": row["role"],
        "permisos": sorted(P.permisos_de(row["role"])),
    })
    return {"access_token": token, "token_type": "bearer"}


@router.get("/api/institutos", response_model=InstitutosOut)
def institutos(conn=Depends(get_db)):
    return {"institutos": queries.listar_institutos(conn)}


@router.post("/api/registro/solicitar", response_model=MensajeOut, status_code=201)
def solicitar_registro(body: SolicitudRegistroIn, conn=Depends(get_db)):
    email = body.email.strip().lower()
    if not any(email.endswith(dom) for dom in DOMINIOS_PERMITIDOS):
        raise HTTPException(
            status_code=400,
            detail="Solo se permiten correos institucionales (@unahur.edu.ar).",
        )
    if body.rol not in ("directivo", "docente", "no_docente"):
        raise HTTPException(status_code=400, detail="Rol inválido.")
    if len(body.password) < 4:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 4 caracteres.")

    existe_usuario = conn.execute(
        "SELECT 1 FROM Usuario WHERE usuario = ?", (email,)
    ).fetchone()
    if existe_usuario:
        raise HTTPException(status_code=409, detail="Ese correo ya está registrado.")

    try:
        queries.crear_solicitud_registro(
            conn=conn,
            email=email,
            nombre=body.nombre.strip(),
            password_hash=hashear_password(body.password),
            rol=body.rol,
            id_instituto=body.id_instituto,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Ya existe una solicitud pendiente para ese correo.",
        )

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
    if body and body.rol and body.rol not in ("directivo", "docente", "no_docente"):
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


# Todo SOBRE RECUPERAR CONTRASEÑA: 


class VerificarUsuarioIn(BaseModel):
    usuario: str


class CambiarPasswordIn(BaseModel):
    usuario: str
    nueva_password: str


@router.post("/api/recuperar-password/verificar", response_model=MensajeOut)
def verificar_usuario_recuperacion(body: VerificarUsuarioIn, conn=Depends(get_db)):
    usuario = body.usuario.strip().lower()
    row = conn.execute(
        "SELECT 1 FROM Usuario WHERE usuario = ?", (usuario,)
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="El correo no figura como personal autorizado de UNAHUR.",
        )
    return {"message": "Usuario verificado."}


@router.post("/api/recuperar-password/cambiar", response_model=MensajeOut)
def cambiar_password_directo(body: CambiarPasswordIn, conn=Depends(get_db)):
    usuario = body.usuario.strip().lower()
    if len(body.nueva_password) < 4:
        raise HTTPException(
            status_code=400,
            detail="La nueva contraseña debe tener al menos 4 caracteres.",
        )

    row = conn.execute(
        "SELECT password_hash FROM Usuario WHERE usuario = ?", (usuario,)
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="El correo no figura como personal autorizado de UNAHUR.",
        )

    if verificar_password(body.nueva_password, row["password_hash"]):
        raise HTTPException(
            status_code=400,
            detail="La nueva contraseña no puede ser igual a la anterior.",
        )

    with conn:
        conn.execute(
            "UPDATE Usuario SET password_hash = ? WHERE usuario = ?",
            (hashear_password(body.nueva_password), usuario),
        )

    return {"message": "Contraseña actualizada correctamente."}