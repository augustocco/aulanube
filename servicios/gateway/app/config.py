"""Configuración externa del gateway (patrón External Configuration Store).

Todo lo que cambia entre el entorno local y el clúster llega por variables de
entorno; el código no conoce direcciones ni secretos.
"""

import os

JWT_SECRETO = os.environ.get("JWT_SECRETO", "secreto-local-solo-desarrollo")

SERVICIOS = {
    "identidad": os.environ.get("URL_IDENTIDAD", "http://identidad:8000"),
    "cursos": os.environ.get("URL_CURSOS", "http://cursos:8000"),
    "certificados": os.environ.get("URL_CERTIFICADOS", "http://certificados:8000"),
    "notificaciones": os.environ.get("URL_NOTIFICACIONES", "http://notificaciones:8000"),
}

# Rutas que se atienden sin token: (servicio, primer segmento de la ruta).
RUTAS_PUBLICAS = {("identidad", "login"), ("certificados", "verificar")}

TIEMPO_ESPERA = float(os.environ.get("TIEMPO_ESPERA_S", "5"))

# Interruptor de circuito: fallos seguidos que lo abren y segundos que permanece abierto.
UMBRAL_FALLOS = int(os.environ.get("UMBRAL_FALLOS", "3"))
SEGUNDOS_ABIERTO = float(os.environ.get("SEGUNDOS_ABIERTO", "15"))

# Límite de solicitudes por empresa (o por IP si no hay token): fichas por segundo y ráfaga.
LIMITE_TASA = float(os.environ.get("LIMITE_TASA", "20"))
LIMITE_RAFAGA = int(os.environ.get("LIMITE_RAFAGA", "40"))
