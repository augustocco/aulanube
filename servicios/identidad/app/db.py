"""Conexión a la base de datos propia del servicio (Database per Service).

Cada servicio recibe su propia `DATABASE_URL`, con un usuario que solo tiene
permisos sobre su base. Ningún otro servicio lee estas tablas.
"""

import logging
import os
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

URL = os.environ.get("DATABASE_URL", "sqlite://")

if URL.startswith("sqlite"):
    # En las pruebas: una sola conexión en memoria compartida entre hilos.
    motor = create_engine(URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
else:
    motor = create_engine(URL, pool_pre_ping=True, pool_size=5, max_overflow=5)

Sesion = sessionmaker(motor, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def obtener_sesion():
    with Sesion() as sesion:
        yield sesion


def esperar_base(intentos: int = 30) -> None:
    """Espera a que la base acepte conexiones; en el clúster puede arrancar después."""
    for intento in range(intentos):
        try:
            with motor.connect() as conexion:
                conexion.execute(text("select 1"))
            return
        except Exception as exc:  # noqa: BLE001 - cualquier error de conexión se reintenta
            logging.getLogger("db").warning("base no disponible (intento %d): %s", intento + 1, exc)
            time.sleep(2)
    raise RuntimeError("La base de datos no respondió")
