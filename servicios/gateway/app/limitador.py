"""Límite de solicitudes con cubeta de fichas (token bucket) por clave.

La clave es la empresa del token, de modo que una campaña masiva de un cliente
no deja sin servicio a los demás (aislamiento entre inquilinos). El estado vive
en la memoria de cada réplica del gateway: con N réplicas el límite efectivo es
N veces el configurado, lo que se acepta en el prototipo.
"""

import time

MAXIMO_CLAVES = 10_000


class Cubeta:
    def __init__(self, tasa: float, capacidad: int, reloj=time.monotonic):
        self.tasa = tasa
        self.capacidad = capacidad
        self.reloj = reloj
        self._fichas: dict[str, tuple[float, float]] = {}

    def consumir(self, clave: str) -> bool:
        ahora = self.reloj()
        if len(self._fichas) > MAXIMO_CLAVES:
            self._fichas.clear()
        fichas, ultimo = self._fichas.get(clave, (float(self.capacidad), ahora))
        fichas = min(float(self.capacidad), fichas + (ahora - ultimo) * self.tasa)
        if fichas < 1:
            self._fichas[clave] = (fichas, ahora)
            return False
        self._fichas[clave] = (fichas - 1, ahora)
        return True
