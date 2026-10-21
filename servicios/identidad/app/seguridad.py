import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .modelos import Usuario

JWT_SECRETO = os.environ.get("JWT_SECRETO", "secreto-local-solo-desarrollo")
HORAS_TOKEN = int(os.environ.get("HORAS_TOKEN", "8"))
RONDAS = int(os.environ.get("BCRYPT_RONDAS", "12"))


def cifrar_clave(clave: str) -> str:
    return bcrypt.hashpw(clave.encode(), bcrypt.gensalt(RONDAS)).decode()


def clave_valida(clave: str, clave_hash: str) -> bool:
    return bcrypt.checkpw(clave.encode(), clave_hash.encode())


def emitir_token(usuario: Usuario) -> str:
    reclamos = {
        "sub": str(usuario.id),
        "nombre": usuario.nombre,
        "rol": usuario.rol,
        "empresa_id": usuario.empresa_id,
        "empresa": usuario.empresa.nombre,
        "exp": datetime.now(timezone.utc) + timedelta(hours=HORAS_TOKEN),
    }
    return jwt.encode(reclamos, JWT_SECRETO, algorithm="HS256")
