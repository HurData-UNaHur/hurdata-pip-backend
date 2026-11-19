"""
routers/auth.py
===============
Endpoints de autenticación e institutos (selector del registro).
"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import crear_token, verificar_password
from app.api.permisos import permisos_de
from app.api.deps import get_db
from app.api.schemas import InstitutosOut, LoginIn, TokenOut
from app.db import queries

router = APIRouter(tags=["Autenticación"])


@router.post("/api/login", response_model=TokenOut)
def login(body: LoginIn, conn=Depends(get_db)):
    """
    Autentica un usuario y devuelve un JWT Bearer.

    Returns:
        {"access_token": str, "token_type": "bearer"}

    Errors:
        401: usuario o contraseña incorrectos.
    """
    row = conn.execute(
        "SELECT usuario, nombre, cargo, role, password_hash FROM Usuario WHERE usuario = ?",
        (body.usuario,),
    ).fetchone()

    if row is None or not verificar_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")

    token = crear_token({
        "sub":    row["usuario"],
        "nombre": row["nombre"],
        "cargo":  row["cargo"],
        "role":   row["role"],
        # Solo para que el frontend muestre u oculte botones. El backend NO confía
        # en esta lista: la recalcula desde el rol en cada request (deps.py).
        "permisos": sorted(permisos_de(row["role"])),
    })
    return {"access_token": token, "token_type": "bearer"}


@router.get("/api/institutos", response_model=InstitutosOut)
def institutos(conn=Depends(get_db)):
    """
    Institutos para el selector del registro (endpoint público).
    Devuelve solo id y nombre: el email de cada dirección queda en el backend.
    """
    return {"institutos": queries.listar_institutos(conn)}
