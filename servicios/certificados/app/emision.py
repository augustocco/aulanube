"""Reacción al evento `curso.completado`: emitir el certificado y avisarlo."""

import json
import logging
import os
import secrets
import socket
import time
from datetime import datetime

import redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .consumidor import FLUJO_CERTIFICADOS
from .db import Sesion
from .modelos import Certificado, ahora
from .pdf import generar_pdf

log = logging.getLogger("certificados.emision")

URL_PUBLICA = os.environ.get("URL_PUBLICA", "http://localhost:8080")
# Costo simulado de renderizar y firmar el documento: hace visible la cola.
TRABAJO_MS = int(os.environ.get("TRABAJO_MS", "300"))
ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
NOMBRE_TRABAJADOR = os.environ.get("POD_NOMBRE") or socket.gethostname()


def nuevo_codigo() -> str:
    return "AN-" + "".join(secrets.choice(ALFABETO) for _ in range(8))


def url_verificacion(codigo: str) -> str:
    return f"{URL_PUBLICA}/#/verificar/{codigo}"


def crear_manejador(cliente: redis.Redis, fabrica_sesion=Sesion):
    def manejar(evento_id: str, tipo: str, datos: dict) -> None:
        if tipo != "curso.completado":
            return
        with fabrica_sesion() as sesion:
            existente = sesion.scalar(select(Certificado.id).where(Certificado.inscripcion_id == datos["inscripcion_id"]))
            if existente is not None:
                log.info("evento=%s repetido, certificado ya emitido", evento_id)
                return
            if TRABAJO_MS:
                time.sleep(TRABAJO_MS / 1000)
            emitido = ahora()
            completado = datos.get("completado_en")
            fecha = datetime.fromisoformat(completado) if completado else emitido
            codigo = nuevo_codigo()
            certificado = Certificado(
                codigo=codigo,
                inscripcion_id=datos["inscripcion_id"],
                empresa_id=datos["empresa_id"],
                empresa_nombre=datos.get("empresa_nombre", ""),
                usuario_id=str(datos["usuario_id"]),
                usuario_nombre=datos["usuario_nombre"],
                curso_titulo=datos["curso_titulo"],
                horas=int(datos.get("horas", 1)),
                emitido_en=emitido,
                emitido_por=NOMBRE_TRABAJADOR,
                pdf=generar_pdf(
                    datos["usuario_nombre"], datos["curso_titulo"], int(datos.get("horas", 1)),
                    datos.get("empresa_nombre", ""), codigo, fecha, url_verificacion(codigo),
                ),
            )
            sesion.add(certificado)
            try:
                sesion.commit()
            except IntegrityError:
                # Otra réplica emitió el mismo certificado al mismo tiempo.
                sesion.rollback()
                return
        cliente.xadd(
            FLUJO_CERTIFICADOS,
            {
                "evento_id": f"certificados-{codigo}",
                "tipo": "certificado.emitido",
                "datos": json.dumps({
                    "codigo": codigo,
                    "inscripcion_id": datos["inscripcion_id"],
                    "curso_titulo": datos["curso_titulo"],
                    "usuario_id": str(datos["usuario_id"]),
                    "usuario_nombre": datos["usuario_nombre"],
                    "empresa_id": datos["empresa_id"],
                }),
            },
            maxlen=50_000,
            approximate=True,
        )
        log.info("certificado=%s inscripcion=%s trabajador=%s", codigo, datos["inscripcion_id"], NOMBRE_TRABAJADOR)

    return manejar
