"""Datos de demostración: dos empresas cliente con su administrador y estudiantes.

Los identificadores 1 y 2 de las empresas coinciden con la semilla del
servicio de cursos. Solo se siembra si no hay empresas.
"""

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from .modelos import Empresa, Usuario
from .seguridad import cifrar_clave

CLAVE_DEMO = os.environ.get("CLAVE_DEMO", "AulaNube-2026")

EMPRESAS = [
    {
        "id": 1,
        "nombre": "Constructora Los Andes S.A.S.",
        "sector": "Construcción",
        "usuarios": [
            ("Laura Méndez", "admin@andes.demo", "admin"),
            ("Carlos Rincón", "carlos@andes.demo", "estudiante"),
            ("Yesenia Duarte", "yesenia@andes.demo", "estudiante"),
        ],
    },
    {
        "id": 2,
        "nombre": "Clínica Santa Lucía",
        "sector": "Salud",
        "usuarios": [
            ("Diana Ortiz", "admin@santalucia.demo", "admin"),
            ("Andrés Pabón", "andres@santalucia.demo", "estudiante"),
            ("María José Silva", "mariajose@santalucia.demo", "estudiante"),
        ],
    },
]


def sembrar(sesion: Session) -> None:
    if sesion.scalar(select(Empresa.id).limit(1)) is not None:
        return
    clave_hash = cifrar_clave(CLAVE_DEMO)
    for datos in EMPRESAS:
        sesion.add(Empresa(id=datos["id"], nombre=datos["nombre"], sector=datos["sector"]))
        sesion.flush()
        for nombre, correo, rol in datos["usuarios"]:
            sesion.add(Usuario(empresa_id=datos["id"], nombre=nombre, correo=correo, clave_hash=clave_hash, rol=rol))
    sesion.commit()
