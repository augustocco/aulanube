"""API Gateway de AulaNube.

Es la única puerta de entrada a los servicios internos. Concentra lo que
ningún servicio debería repetir (Gateway Offloading):

- valida el JWT y reenvía la identidad en cabeceras `X-Usuario-*`, `X-Empresa-*`
  y `X-Rol`, después de borrar las que haya enviado el cliente;
- limita las solicitudes por empresa;
- protege a cada servicio con un interruptor de circuito y reintenta una vez
  las lecturas (GET) que fallan por red;
- asigna un identificador de correlación que viaja por todos los servicios.
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from urllib.parse import quote

import httpx
import jwt
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from . import config
from .interruptor import Interruptor
from .limitador import Cubeta

log = logging.getLogger("gateway")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

CABECERAS_IDENTIDAD = {"x-usuario-id", "x-usuario-nombre", "x-empresa-id", "x-empresa-nombre", "x-rol"}
# Cabeceras que no se copian entre la solicitud del cliente y la del servicio (o al revés).
CABECERAS_SALTO = {
    "host", "content-length", "connection", "keep-alive", "transfer-encoding", "upgrade",
    "te", "trailer", "proxy-authorization", "authorization", "content-encoding",
}

interruptores = {
    nombre: Interruptor(nombre, config.UMBRAL_FALLOS, config.SEGUNDOS_ABIERTO) for nombre in config.SERVICIOS
}
limitador = Cubeta(config.LIMITE_TASA, config.LIMITE_RAFAGA)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    app.state.cliente = httpx.AsyncClient(timeout=httpx.Timeout(config.TIEMPO_ESPERA, connect=2.0))
    yield
    await app.state.cliente.aclose()


app = FastAPI(title="AulaNube · API Gateway", lifespan=ciclo_de_vida, docs_url=None, redoc_url=None)


def respuesta_error(estado: int, mensaje: str, correlacion: str, **cabeceras: str) -> JSONResponse:
    return JSONResponse(
        {"detalle": mensaje},
        status_code=estado,
        headers={"X-Correlacion-Id": correlacion, **cabeceras},
    )


def leer_token(request: Request) -> dict | None:
    autorizacion = request.headers.get("authorization", "")
    if not autorizacion.lower().startswith("bearer "):
        return None
    try:
        return jwt.decode(autorizacion[7:], config.JWT_SECRETO, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def cabeceras_hacia_servicio(request: Request, reclamos: dict | None, correlacion: str) -> dict:
    cabeceras = {
        k: v for k, v in request.headers.items()
        if k.lower() not in CABECERAS_SALTO and k.lower() not in CABECERAS_IDENTIDAD
    }
    cabeceras["x-correlacion-id"] = correlacion
    if reclamos:
        # Los nombres llevan tildes: se codifican para que viajen como ASCII.
        cabeceras["x-usuario-id"] = str(reclamos["sub"])
        cabeceras["x-usuario-nombre"] = quote(reclamos.get("nombre", ""))
        cabeceras["x-empresa-id"] = str(reclamos["empresa_id"])
        cabeceras["x-empresa-nombre"] = quote(reclamos.get("empresa", ""))
        cabeceras["x-rol"] = reclamos.get("rol", "estudiante")
    return cabeceras


@app.get("/salud")
async def salud():
    return {"estado": "ok"}


@app.get("/api/estado")
async def estado(request: Request):
    """Panel de arquitectura: salud de cada servicio, circuitos y cola de eventos."""
    reclamos = leer_token(request)
    if not reclamos or reclamos.get("rol") != "admin":
        return JSONResponse({"detalle": "Solo los administradores ven el estado"}, status_code=403)
    cliente: httpx.AsyncClient = app.state.cliente

    async def sondear(nombre: str, url: str) -> dict:
        try:
            r = await cliente.get(f"{url}/salud", timeout=2)
            disponible = r.status_code == 200
        except httpx.HTTPError:
            disponible = False
        return {"servicio": nombre, "disponible": disponible, "circuito": interruptores[nombre].resumen()}

    servicios = await asyncio.gather(*(sondear(n, u) for n, u in config.SERVICIOS.items()))
    cola = None
    try:
        r = await cliente.get(f"{config.SERVICIOS['certificados']}/cola", timeout=2)
        if r.status_code == 200:
            cola = r.json()
    except httpx.HTTPError:
        pass
    return {"servicios": servicios, "cola": cola}


@app.api_route("/api/{servicio}/{resto:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def reenviar(servicio: str, resto: str, request: Request):
    correlacion = request.headers.get("x-correlacion-id") or uuid.uuid4().hex[:12]
    base = config.SERVICIOS.get(servicio)
    if base is None:
        return respuesta_error(404, "Ruta no encontrada", correlacion)

    reclamos = leer_token(request)
    publica = (servicio, resto.split("/", 1)[0]) in config.RUTAS_PUBLICAS
    if reclamos is None and not publica:
        return respuesta_error(401, "Inicie sesión para continuar", correlacion)

    clave = f"empresa:{reclamos['empresa_id']}" if reclamos else f"ip:{request.client.host if request.client else '-'}"
    if not limitador.consumir(clave):
        return respuesta_error(429, "Demasiadas solicitudes, intente en un momento", correlacion, **{"Retry-After": "1"})

    interruptor = interruptores[servicio]
    if not interruptor.permitir():
        return respuesta_error(
            503, f"El servicio de {servicio} no está disponible por ahora", correlacion, **{"X-Circuito": "abierto"}
        )

    cliente: httpx.AsyncClient = app.state.cliente
    cabeceras = cabeceras_hacia_servicio(request, reclamos, correlacion)
    cuerpo = await request.body()
    # Solo las lecturas son idempotentes: se reintentan una vez ante un fallo de red.
    intentos = 2 if request.method == "GET" else 1
    respuesta = None
    for intento in range(intentos):
        try:
            respuesta = await cliente.request(
                request.method, f"{base}/{resto}", params=request.query_params, content=cuerpo, headers=cabeceras
            )
            break
        except httpx.TransportError as exc:
            log.warning("correlacion=%s servicio=%s intento=%d error=%s", correlacion, servicio, intento + 1, exc)
            if intento + 1 < intentos:
                await asyncio.sleep(0.15)
    if respuesta is None:
        interruptor.fallo()
        return respuesta_error(503, f"El servicio de {servicio} no respondió", correlacion)

    if respuesta.status_code >= 500:
        interruptor.fallo()
    else:
        interruptor.exito()

    salida = {k: v for k, v in respuesta.headers.items() if k.lower() not in CABECERAS_SALTO}
    salida["X-Correlacion-Id"] = correlacion
    return Response(content=respuesta.content, status_code=respuesta.status_code, headers=salida)
