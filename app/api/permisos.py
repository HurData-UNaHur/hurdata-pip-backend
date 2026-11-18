"""
permisos.py
===========
Responsabilidad: definir QUÉ puede hacer cada rol. Es el único lugar donde
se asignan permisos; los endpoints piden un permiso, nunca preguntan por un rol.

    Permiso                   Admin  Directivo  Docente  No Docente
    datos:cargar               ✅      ✅         ✅        ❌
    datos:borrar (propias)     ✅      ✅         ✅        ❌
    datos:borrar_cualquiera    ✅      ✅         ❌        ❌
    db:resetear                ✅      ❌         ❌        ❌
    cargas:ver (propias)       ✅      ✅         ✅        ❌
    cargas:ver_todas           ✅      ✅         ❌        ❌
    registros:aprobar          ✅      ✅         ❌        ❌
    usuarios:gestionar         ✅      ❌         ❌        ❌

Ver datos (GET /api/periodos, /api/datos, etc.) no requiere permiso: es público
para que el modo invitado del frontend siga funcionando.

Si se cambia qué puede hacer un rol, se cambia SOLO este archivo.
"""

ROLES = ("admin", "directivo", "docente", "no_docente")

# Permisos
CARGAR = "datos:cargar"
BORRAR = "datos:borrar"
BORRAR_CUALQUIERA = "datos:borrar_cualquiera"
RESETEAR_DB = "db:resetear"
VER_CARGAS = "cargas:ver"
VER_TODAS_LAS_CARGAS = "cargas:ver_todas"
APROBAR_REGISTROS = "registros:aprobar"
GESTIONAR_USUARIOS = "usuarios:gestionar"

_DOCENTE = {CARGAR, BORRAR, VER_CARGAS}
_DIRECTIVO = _DOCENTE | {BORRAR_CUALQUIERA, VER_TODAS_LAS_CARGAS, APROBAR_REGISTROS}
_ADMIN = _DIRECTIVO | {RESETEAR_DB, GESTIONAR_USUARIOS}

PERMISOS_POR_ROL: dict[str, frozenset[str]] = {
    "admin": frozenset(_ADMIN),
    "directivo": frozenset(_DIRECTIVO),
    "docente": frozenset(_DOCENTE),
    "no_docente": frozenset(),
}


def permisos_de(role: str | None) -> frozenset[str]:
    """Permisos de un rol. Un rol desconocido (ej. tokens viejos con 'autorizado') no tiene ninguno."""
    return PERMISOS_POR_ROL.get(role or "", frozenset())


def puede_modificar_carga(usuario: dict, dueno: str | None) -> bool:
    """
    Regla de dueño para borrar o recargar los datos de un período + carrera.

        • Con datos:borrar_cualquiera (Directivo, Admin) → siempre.
        • Con datos:borrar (Docente) → solo si es el dueño de la carga activa.
        • Datos sin carga registrada (dueno=None) → solo con datos:borrar_cualquiera.

    Args:
        usuario: payload del JWT con 'sub' y 'permisos' (ver deps.get_usuario_actual).
        dueno:   email del dueño de la carga activa, o None.
    """
    permisos = usuario.get("permisos", frozenset())
    if BORRAR_CUALQUIERA in permisos:
        return True
    return BORRAR in permisos and dueno is not None and dueno == usuario.get("sub")
