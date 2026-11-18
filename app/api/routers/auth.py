"""
routers/auth.py
===============
Endpoints de autenticación y datos de directivos.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import crear_token, verificar_password
from app.api.deps import get_db
from app.api.schemas import DirectivosOut, LoginIn, TokenOut
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
    })
    return {"access_token": token, "token_type": "bearer"}


@router.get("/api/directivos", response_model=DirectivosOut)
def directivos(conn=Depends(get_db)):
    """Devuelve la lista de directivos (endpoint público)."""
    return {"directivos": queries.listar_directivos(conn)}
