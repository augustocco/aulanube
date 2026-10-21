"""Hilo que publica la bandeja de salida en Redis Streams (Publisher).

La entrega es "al menos una vez": si Redis falla a mitad de un lote, la
transacción se revierte y los eventos se vuelven a enviar en la siguiente
vuelta. Por eso los consumidores descartan los eventos repetidos por su
`evento_id`. Con varias réplicas, `FOR UPDATE SKIP LOCKED` evita que dos
hilos publiquen la misma fila.
"""

import json
import logging
import os
import threading

import redis
from sqlalchemy import select

from .db import Sesion
from .modelos import EventoSalida, ahora

log = logging.getLogger("cursos.relevo")

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
FLUJO = "aulanube.cursos"
LOTE = 100


def publicar_pendientes(fabrica_sesion, cliente: redis.Redis) -> int:
    with fabrica_sesion() as sesion:
        consulta = (
            select(EventoSalida)
            .where(EventoSalida.publicado_en.is_(None))
            .order_by(EventoSalida.id)
            .limit(LOTE)
            .with_for_update(skip_locked=True)
        )
        eventos = list(sesion.scalars(consulta))
        for evento in eventos:
            cliente.xadd(
                FLUJO,
                {"evento_id": f"cursos-{evento.id}", "tipo": evento.tipo, "datos": json.dumps(evento.datos)},
                maxlen=50_000,
                approximate=True,
            )
            evento.publicado_en = ahora()
        sesion.commit()
        return len(eventos)


def iniciar(detener: threading.Event) -> threading.Thread:
    def bucle():
        cliente = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        while not detener.is_set():
            try:
                publicados = publicar_pendientes(Sesion, cliente)
            except Exception as exc:  # noqa: BLE001 - el hilo no debe morir por un fallo pasajero
                log.warning("no se pudo publicar la bandeja de salida: %s", exc)
                detener.wait(2)
                continue
            if publicados:
                log.info("eventos publicados=%d", publicados)
            if publicados < LOTE:
                detener.wait(0.5)

    hilo = threading.Thread(target=bucle, name="relevo-eventos", daemon=True)
    hilo.start()
    return hilo
