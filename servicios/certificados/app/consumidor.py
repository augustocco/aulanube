"""Consumidor de Redis Streams con grupo de consumidores (Subscriber).

- Cada publicador escribe en su propio flujo (`aulanube.cursos`,
  `aulanube.certificados`) y cada servicio se suscribe solo a los que le
  interesan, con un grupo propio: recibe todos los eventos de esos flujos.
- Dentro de un grupo, cada evento lo procesa una sola réplica (Competing
  Consumers): agregar réplicas reparte la cola entre ellas.
- Un evento solo se confirma (XACK) después de procesarlo. Si una réplica
  muere con eventos sin confirmar, otra los reclama pasado un minuto (XAUTOCLAIM).
- Tras tres fallos seguidos con el mismo evento se aparta a un flujo de
  fallidos (Dead Letter) para que no bloquee la cola.
"""

import json
import logging
import os
import socket
import threading
import time
from typing import Callable

import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
FLUJO_CURSOS = "aulanube.cursos"
FLUJO_CERTIFICADOS = "aulanube.certificados"
FLUJO_FALLIDOS = "aulanube.fallidos"
RECLAMAR_TRAS_MS = 60_000
MAXIMO_INTENTOS = 3

Manejador = Callable[[str, str, dict], None]


class Consumidor:
    def __init__(
        self,
        grupo: str,
        flujos: list[str],
        manejar: Manejador,
        cliente: redis.Redis | None = None,
        nombre: str | None = None,
    ):
        self.grupo = grupo
        self.flujos = flujos
        self.manejar = manejar
        self.cliente = cliente or redis.Redis.from_url(REDIS_URL, decode_responses=True)
        self.nombre = nombre or os.environ.get("POD_NOMBRE") or socket.gethostname()
        self.log = logging.getLogger(f"{grupo}.consumidor")
        self._fallos: dict[str, int] = {}
        self._ultimo_reclamo = 0.0

    def asegurar_grupo(self) -> None:
        for flujo in self.flujos:
            try:
                self.cliente.xgroup_create(flujo, self.grupo, id="0", mkstream=True)
            except redis.ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise

    def _reclamar_abandonados(self) -> list:
        if time.monotonic() - self._ultimo_reclamo < 30:
            return []
        self._ultimo_reclamo = time.monotonic()
        mensajes = []
        for flujo in self.flujos:
            respuesta = self.cliente.xautoclaim(flujo, self.grupo, self.nombre, RECLAMAR_TRAS_MS, "0-0", count=20)
            mensajes += [(flujo, id_, campos) for id_, campos in respuesta[1] if campos]
            # Las réplicas que ya no existen y no dejaron nada pendiente salen del grupo.
            for c in self.cliente.xinfo_consumers(flujo, self.grupo):
                if c["name"] != self.nombre and c["pending"] == 0 and c["idle"] > 5 * RECLAMAR_TRAS_MS:
                    self.cliente.xgroup_delconsumer(flujo, self.grupo, c["name"])
        return mensajes

    def procesar_lote(self, bloquear_ms: int = 2000) -> int:
        mensajes = self._reclamar_abandonados()
        leidos = self.cliente.xreadgroup(
            self.grupo, self.nombre, {f: ">" for f in self.flujos}, count=10, block=bloquear_ms
        )
        for flujo, entradas in leidos or []:
            mensajes += [(flujo, id_, campos) for id_, campos in entradas]
        for flujo, id_, campos in mensajes:
            self._procesar(flujo, id_, campos)
        return len(mensajes)

    def _procesar(self, flujo: str, id_: str, campos: dict) -> None:
        try:
            self.manejar(campos.get("evento_id", id_), campos.get("tipo", ""), json.loads(campos.get("datos", "{}")))
        except Exception as exc:  # noqa: BLE001 - un evento malo no debe tumbar al consumidor
            intentos = self._fallos.get(id_, 0) + 1
            self._fallos[id_] = intentos
            self.log.warning("evento=%s intento=%d error=%s", id_, intentos, exc)
            if intentos < MAXIMO_INTENTOS:
                return  # queda pendiente y se reintenta al reclamarlo
            self.cliente.xadd(FLUJO_FALLIDOS, {**campos, "flujo": flujo, "grupo": self.grupo, "error": str(exc)[:500]})
            self.log.error("evento=%s apartado en %s", id_, FLUJO_FALLIDOS)
        self._fallos.pop(id_, None)
        self.cliente.xack(flujo, self.grupo, id_)

    def iniciar(self, detener: threading.Event) -> threading.Thread:
        def bucle():
            listo = False
            while not detener.is_set():
                try:
                    if not listo:
                        self.asegurar_grupo()
                        listo = True
                    self.procesar_lote()
                except redis.RedisError as exc:
                    self.log.warning("Redis no disponible: %s", exc)
                    listo = False
                    detener.wait(2)

        hilo = threading.Thread(target=bucle, name=f"consumidor-{self.grupo}", daemon=True)
        hilo.start()
        return hilo


def estado_cola(cliente: redis.Redis) -> dict:
    """Por flujo y grupo: eventos sin leer y entregados sin confirmar."""
    grupos = []
    for flujo in (FLUJO_CURSOS, FLUJO_CERTIFICADOS):
        try:
            info = cliente.xinfo_groups(flujo)
        except redis.ResponseError:
            continue
        for g in info:
            grupos.append({
                "flujo": flujo,
                "grupo": g["name"],
                "consumidores": g["consumers"],
                "pendientes": g["pending"],
                "sin_leer": g.get("lag") or 0,
            })
    return {
        "longitud": sum(cliente.xlen(f) for f in (FLUJO_CURSOS, FLUJO_CERTIFICADOS)),
        "fallidos": cliente.xlen(FLUJO_FALLIDOS),
        "grupos": grupos,
    }
