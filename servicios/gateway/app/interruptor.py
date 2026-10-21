"""Interruptor de circuito (Circuit Breaker) para cada servicio interno.

Estados:
- cerrado: las solicitudes pasan; cada fallo seguido suma uno.
- abierto: se rechazan de inmediato durante `espera` segundos, sin tocar el servicio.
- semiabierto: pasada la espera se deja pasar una sola solicitud de prueba;
  si funciona el circuito se cierra y si falla vuelve a abrirse.

El gateway corre en un solo bucle de asyncio, así que no hace falta un candado.
"""

import time


class Interruptor:
    def __init__(self, nombre: str, umbral: int = 3, espera: float = 15.0, reloj=time.monotonic):
        self.nombre = nombre
        self.umbral = umbral
        self.espera = espera
        self.reloj = reloj
        self.estado = "cerrado"
        self.fallos = 0
        self.abierto_desde = 0.0
        self.prueba_en_curso = False
        self.rechazadas = 0

    def permitir(self) -> bool:
        if self.estado == "abierto":
            if self.reloj() - self.abierto_desde < self.espera:
                self.rechazadas += 1
                return False
            self.estado = "semiabierto"
            self.prueba_en_curso = False
        if self.estado == "semiabierto":
            if self.prueba_en_curso:
                self.rechazadas += 1
                return False
            self.prueba_en_curso = True
        return True

    def exito(self) -> None:
        self.estado = "cerrado"
        self.fallos = 0
        self.prueba_en_curso = False

    def fallo(self) -> None:
        self.fallos += 1
        if self.estado == "semiabierto" or self.fallos >= self.umbral:
            self.estado = "abierto"
            self.abierto_desde = self.reloj()
            self.prueba_en_curso = False

    def resumen(self) -> dict:
        estado = self.estado
        restante = 0.0
        if estado == "abierto":
            restante = max(0.0, self.espera - (self.reloj() - self.abierto_desde))
            if restante == 0:
                # Pasó la espera: la próxima solicitud será la de prueba.
                estado = "semiabierto"
        return {
            "estado": estado,
            "fallos_seguidos": self.fallos,
            "rechazadas": self.rechazadas,
            "segundos_para_reintento": round(restante, 1),
        }
