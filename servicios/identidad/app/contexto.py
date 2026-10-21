"""Identidad del usuario que hace la solicitud.

El gateway valida el token y la reenvía en cabeceras. Los servicios no son
accesibles desde fuera del clúster (NetworkPolicy), así que confían en ellas.
"""

from dataclasses import dataclass
from urllib.parse import unquote

from fastapi import Depends, Header, HTTPException


@dataclass(frozen=True)
class Contexto:
    usuario_id: str
    usuario_nombre: str
    empresa_id: int
    empresa_nombre: str
    rol: str

    @property
    def es_admin(self) -> bool:
        return self.rol == "admin"


def contexto(
    x_usuario_id: str | None = Header(None),
    x_usuario_nombre: str = Header(""),
    x_empresa_id: str | None = Header(None),
    x_empresa_nombre: str = Header(""),
    x_rol: str = Header("estudiante"),
) -> Contexto:
    if not x_usuario_id or not x_empresa_id or not x_empresa_id.isdigit():
        raise HTTPException(401, "Falta la identidad del usuario")
    return Contexto(x_usuario_id, unquote(x_usuario_nombre), int(x_empresa_id), unquote(x_empresa_nombre), x_rol)


def solo_admin(ctx: Contexto = Depends(contexto)) -> Contexto:
    if not ctx.es_admin:
        raise HTTPException(403, "Solo el administrador de la empresa puede hacer esto")
    return ctx
