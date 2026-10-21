"""Servicio de notificaciones: avisos en la plataforma y correo simulado.

Se suscribe a `curso.completado` y `certificado.emitido`. El envío de correo
se simula con una línea en el registro; en producción se cambiaría por un
proveedor (OCI Email Delivery) sin tocar a los demás servicios.
"""

import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .consumidor import FLUJO_CERTIFICADOS, FLUJO_CURSOS, Consumidor
from .contexto import Contexto, contexto
from .db import Base, Sesion, esperar_base, motor, obtener_sesion
from .modelos import Notificacion

log = logging.getLogger("notificaciones")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

CONSUMIDOR_ACTIVO = os.environ.get("CONSUMIDOR_ACTIVO", "true") == "true"


def redactar(tipo: str, datos: dict) -> tuple[str, str, str] | None:
    if tipo == "curso.completado":
        return (
            f"Completaste «{datos['curso_titulo']}»",
            "¡Felicitaciones! Estamos generando tu certificado; te avisaremos cuando esté listo.",
            f"#/curso/{datos['curso_id']}",
        )
    if tipo == "certificado.emitido":
        return (
            "Tu certificado está listo",
            f"El certificado de «{datos['curso_titulo']}» tiene el código {datos['codigo']}. Ya puedes descargarlo.",
            "#/certificados",
        )
    return None


def manejar(evento_id: str, tipo: str, datos: dict, fabrica_sesion=Sesion) -> None:
    texto = redactar(tipo, datos)
    if texto is None:
        return
    titulo, mensaje, enlace = texto
    with fabrica_sesion() as sesion:
        sesion.add(Notificacion(
            evento_id=evento_id, empresa_id=datos["empresa_id"], usuario_id=str(datos["usuario_id"]),
            titulo=titulo, mensaje=mensaje, enlace=enlace,
        ))
        try:
            sesion.commit()
        except IntegrityError:
            sesion.rollback()
            return
    log.info("correo simulado para=%s asunto=%r", datos.get("usuario_nombre", datos["usuario_id"]), titulo)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    esperar_base()
    Base.metadata.create_all(motor)
    detener = threading.Event()
    if CONSUMIDOR_ACTIVO:
        Consumidor("notificaciones", [FLUJO_CURSOS, FLUJO_CERTIFICADOS], manejar).iniciar(detener)
    yield
    detener.set()


app = FastAPI(title="AulaNube · Notificaciones", lifespan=ciclo_de_vida)


def de_usuario(ctx: Contexto):
    return (Notificacion.empresa_id == ctx.empresa_id, Notificacion.usuario_id == ctx.usuario_id)


@app.get("/salud")
def salud():
    return {"estado": "ok"}


@app.get("/notificaciones")
def listar(ctx: Contexto = Depends(contexto), sesion: Session = Depends(obtener_sesion)):
    filtro = de_usuario(ctx)
    avisos = sesion.scalars(select(Notificacion).where(*filtro).order_by(Notificacion.id.desc()).limit(50))
    sin_leer = sesion.scalar(select(func.count()).select_from(Notificacion).where(*filtro, Notificacion.leida.is_(False)))
    return {
        "sin_leer": sin_leer,
        "avisos": [
            {"id": n.id, "titulo": n.titulo, "mensaje": n.mensaje, "enlace": n.enlace, "leida": n.leida,
             "creada_en": n.creada_en.isoformat()}
            for n in avisos
        ],
    }


@app.post("/notificaciones/{aviso_id}/leida")
def marcar(aviso_id: int, ctx: Contexto = Depends(contexto), sesion: Session = Depends(obtener_sesion)):
    resultado = sesion.execute(update(Notificacion).where(Notificacion.id == aviso_id, *de_usuario(ctx)).values(leida=True))
    sesion.commit()
    if resultado.rowcount == 0:
        raise HTTPException(404, "Aviso no encontrado")
    return {"leida": True}


@app.post("/notificaciones/leidas")
def marcar_todas(ctx: Contexto = Depends(contexto), sesion: Session = Depends(obtener_sesion)):
    sesion.execute(update(Notificacion).where(*de_usuario(ctx)).values(leida=True))
    sesion.commit()
    return {"leidas": True}
