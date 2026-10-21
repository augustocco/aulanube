"""Servicio de identidad: empresas, usuarios, ingreso y emisión de tokens."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .contexto import Contexto, contexto, solo_admin
from .db import Base, Sesion, esperar_base, motor, obtener_sesion
from .modelos import Usuario
from .semilla import sembrar
from .seguridad import cifrar_clave, clave_valida, emitir_token


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    esperar_base()
    Base.metadata.create_all(motor)
    with Sesion() as sesion:
        sembrar(sesion)
    yield


app = FastAPI(title="AulaNube · Identidad", lifespan=ciclo_de_vida)


class Ingreso(BaseModel):
    correo: str = Field(max_length=160)
    clave: str = Field(max_length=200)


class NuevoUsuario(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    correo: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=160)
    clave: str = Field(min_length=8, max_length=200)


def publico(u: Usuario) -> dict:
    return {
        "id": u.id,
        "nombre": u.nombre,
        "correo": u.correo,
        "rol": u.rol,
        "empresa_id": u.empresa_id,
        "empresa": u.empresa.nombre,
    }


@app.get("/salud")
def salud():
    return {"estado": "ok"}


@app.post("/login")
def ingresar(datos: Ingreso, sesion: Session = Depends(obtener_sesion)):
    usuario = sesion.scalar(select(Usuario).where(Usuario.correo == datos.correo.strip().lower()))
    if usuario is None or not clave_valida(datos.clave, usuario.clave_hash):
        raise HTTPException(401, "Correo o clave incorrectos")
    return {"token": emitir_token(usuario), "usuario": publico(usuario)}


@app.get("/yo")
def yo(ctx: Contexto = Depends(contexto), sesion: Session = Depends(obtener_sesion)):
    usuario = sesion.get(Usuario, int(ctx.usuario_id))
    if usuario is None:
        raise HTTPException(404, "Usuario no encontrado")
    return publico(usuario)


@app.get("/usuarios")
def listar_usuarios(ctx: Contexto = Depends(solo_admin), sesion: Session = Depends(obtener_sesion)):
    usuarios = sesion.scalars(
        select(Usuario).where(Usuario.empresa_id == ctx.empresa_id).order_by(Usuario.rol, Usuario.nombre)
    )
    return [publico(u) for u in usuarios]


@app.post("/usuarios", status_code=201)
def crear_usuario(datos: NuevoUsuario, ctx: Contexto = Depends(solo_admin), sesion: Session = Depends(obtener_sesion)):
    usuario = Usuario(
        empresa_id=ctx.empresa_id,
        nombre=datos.nombre.strip(),
        correo=datos.correo.strip().lower(),
        clave_hash=cifrar_clave(datos.clave),
        rol="estudiante",
    )
    sesion.add(usuario)
    try:
        sesion.commit()
    except IntegrityError:
        sesion.rollback()
        raise HTTPException(409, "Ya existe un usuario con ese correo")
    sesion.refresh(usuario)
    return publico(usuario)
