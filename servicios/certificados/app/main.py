"""Servicio de certificados: trabajador que consume `curso.completado` y API de consulta."""

import logging
import os
import threading
from contextlib import asynccontextmanager

import redis
from fastapi import Depends, FastAPI, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, undefer

from .consumidor import FLUJO_CURSOS, REDIS_URL, Consumidor, estado_cola
from .contexto import Contexto, contexto
from .db import Base, esperar_base, motor, obtener_sesion
from .emision import crear_manejador, url_verificacion
from .modelos import Certificado

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

CONSUMIDOR_ACTIVO = os.environ.get("CONSUMIDOR_ACTIVO", "true") == "true"


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    esperar_base()
    Base.metadata.create_all(motor)
    app.state.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    detener = threading.Event()
    if CONSUMIDOR_ACTIVO:
        Consumidor("certificados", [FLUJO_CURSOS], crear_manejador(app.state.redis), app.state.redis).iniciar(detener)
    yield
    detener.set()


app = FastAPI(title="AulaNube · Certificados", lifespan=ciclo_de_vida)


def vista(c: Certificado) -> dict:
    return {
        "codigo": c.codigo,
        "curso_titulo": c.curso_titulo,
        "horas": c.horas,
        "usuario_nombre": c.usuario_nombre,
        "empresa_nombre": c.empresa_nombre,
        "emitido_en": c.emitido_en.isoformat(),
        "emitido_por": c.emitido_por,
        "url_verificacion": url_verificacion(c.codigo),
    }


@app.get("/salud")
def salud():
    return {"estado": "ok"}


@app.get("/certificados")
def listar(ctx: Contexto = Depends(contexto), sesion: Session = Depends(obtener_sesion)):
    consulta = select(Certificado).where(Certificado.empresa_id == ctx.empresa_id)
    if not ctx.es_admin:
        consulta = consulta.where(Certificado.usuario_id == ctx.usuario_id)
    return [vista(c) for c in sesion.scalars(consulta.order_by(Certificado.id.desc()).limit(200))]


@app.get("/certificados/{codigo}/pdf")
def descargar(codigo: str, ctx: Contexto = Depends(contexto), sesion: Session = Depends(obtener_sesion)):
    c = sesion.scalar(select(Certificado).options(undefer(Certificado.pdf)).where(Certificado.codigo == codigo))
    propio = c is not None and c.empresa_id == ctx.empresa_id and (ctx.es_admin or c.usuario_id == ctx.usuario_id)
    if not propio:
        raise HTTPException(404, "Certificado no encontrado")
    return Response(
        c.pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificado-{c.codigo}.pdf"'},
    )


@app.get("/verificar/{codigo}")
def verificar(codigo: str, sesion: Session = Depends(obtener_sesion)):
    """Consulta pública: un tercero confirma que el certificado existe."""
    c = sesion.scalar(select(Certificado).where(Certificado.codigo == codigo.strip().upper()))
    if c is None:
        raise HTTPException(404, "No existe un certificado con ese código")
    return {"valido": True, **{k: v for k, v in vista(c).items() if k not in ("emitido_por", "url_verificacion")}}


@app.get("/cola")
def cola(sesion: Session = Depends(obtener_sesion)):
    """Uso interno del gateway: estado de la cola de eventos y certificados emitidos."""
    try:
        estado = estado_cola(app.state.redis)
    except redis.RedisError:
        estado = {"disponible": False}
    estado["certificados_emitidos"] = sesion.scalar(select(func.count()).select_from(Certificado))
    return estado
