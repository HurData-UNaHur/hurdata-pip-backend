"""
routers/usuarios.py
===================
Gestión de cuentas (solo Admin) e historial de solicitudes de registro.

    GET  /api/usuarios                    lista las cuentas                          (usuarios:gestionar)
    POST /api/usuarios/{usuario}/rol      cambia el rol                              (usuarios:gestionar)
    POST /api/usuarios/{usuario}/estado   revoca (activo=false) o reactiva el acceso (usuarios:gestionar)
    GET  /api/registro/historial          solicitudes aprobadas y rechazadas         (registros:aprobar)

Regla: nadie modifica ni revoca su propia cuenta; así siempre queda al menos un Admin activo.
El historial lo ve completo el Admin; un Directivo ve solo el de su instituto.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.api import permisos as P
from app.api.deps import get_db, require_permiso
from app.api.schemas import (
    CambiarEstadoIn,
    CambiarRolIn,
    HistorialOut,
    MensajeOut,
    UsuariosOut,
)
from app.api.validaciones import normalizar_email
from app.db import queries

router = APIRouter(tags=["Usuarios"])

CARGO_POR_ROL = {
    "admin": "Administrador",
    "directivo": "Directivo",
    "docente": "Docente",
    "no_docente": "No Docente",
}


def _cuenta_o_404(conn, usuario: str) -> dict:
    cuenta = queries.estado_cuenta(conn, normalizar_email(usuario))
    if cuenta is None:
        raise HTTPException(status_code=404, detail="La cuenta no existe.")
    return cuenta


@router.get("/api/usuarios", response_model=UsuariosOut)
def listar_usuarios(conn=Depends(get_db), actual: dict = Depends(require_permiso(P.GESTIONAR_USUARIOS))):
    return {"usuarios": queries.listar_usuarios(conn)}


@router.post("/api/usuarios/{usuario}/rol", response_model=MensajeOut)
def cambiar_rol(
    usuario: str,
    body: CambiarRolIn,
    conn=Depends(get_db),
    actual: dict = Depends(require_permiso(P.GESTIONAR_USUARIOS)),
):
    if body.rol not in CARGO_POR_ROL:
        raise HTTPException(status_code=400, detail="Rol inválido.")
    cuenta = _cuenta_o_404(conn, usuario)
    if cuenta["usuario"] == actual["sub"]:
        raise HTTPException(status_code=403, detail="No podés cambiar tu propio rol.")

    queries.actualizar_rol_usuario(conn, cuenta["usuario"], body.rol, CARGO_POR_ROL[body.rol])
    return {"message": "Rol actualizado correctamente."}


@router.post("/api/usuarios/{usuario}/estado", response_model=MensajeOut)
def cambiar_estado(
    usuario: str,
    body: CambiarEstadoIn,
    conn=Depends(get_db),
    actual: dict = Depends(require_permiso(P.GESTIONAR_USUARIOS)),
):
    cuenta = _cuenta_o_404(conn, usuario)
    if cuenta["usuario"] == actual["sub"]:
        raise HTTPException(status_code=403, detail="No podés revocar ni reactivar tu propio acceso.")

    queries.actualizar_activo_usuario(conn, cuenta["usuario"], body.activo)
    return {"message": "Acceso reactivado correctamente." if body.activo else "Acceso revocado correctamente."}


@router.get("/api/registro/historial", response_model=HistorialOut)
def historial_solicitudes(conn=Depends(get_db), actual: dict = Depends(require_permiso(P.APROBAR_REGISTROS))):
    """Admin: todas. Directivo: solo las de su instituto (si no tiene instituto asignado, ninguna)."""
    if P.GESTIONAR_USUARIOS in actual["permisos"]:
        return {"solicitudes": queries.listar_historial_solicitudes(conn)}
    cuenta = queries.estado_cuenta(conn, actual["sub"])
    if cuenta is None or cuenta["id_directivo"] is None:
        return {"solicitudes": []}
    return {"solicitudes": queries.listar_historial_solicitudes(conn, cuenta["id_directivo"])}
