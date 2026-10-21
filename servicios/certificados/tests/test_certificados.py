import json
import os

os.environ["CONSUMIDOR_ACTIVO"] = "false"
os.environ["TRABAJO_MS"] = "0"

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import consumidor as modulo  # noqa: E402
from app.consumidor import FLUJO_CERTIFICADOS, FLUJO_CURSOS, FLUJO_FALLIDOS, Consumidor  # noqa: E402
from app.emision import crear_manejador  # noqa: E402
from app.main import app  # noqa: E402

EVENTO = {
    "inscripcion_id": 41,
    "curso_id": 3,
    "curso_titulo": "Protección de datos personales",
    "horas": 4,
    "usuario_id": "5",
    "usuario_nombre": "Andrés Pabón",
    "empresa_id": 2,
    "empresa_nombre": "Clínica Santa Lucía",
    "completado_en": "2026-10-20T15:00:00+00:00",
}


def publicar(redis, evento_id, datos, tipo="curso.completado"):
    redis.xadd(FLUJO_CURSOS, {"evento_id": evento_id, "tipo": tipo, "datos": json.dumps(datos)})


@pytest.fixture(scope="module")
def entorno():
    redis = fakeredis.FakeRedis(decode_responses=True)
    with TestClient(app) as cliente:
        app.state.redis = redis
        consumidor = Consumidor("certificados", [FLUJO_CURSOS], crear_manejador(redis), redis, nombre="prueba")
        consumidor.asegurar_grupo()
        yield cliente, redis, consumidor


def del_usuario(usuario="5", empresa=2, rol="estudiante"):
    return {"X-Usuario-Id": usuario, "X-Empresa-Id": str(empresa), "X-Rol": rol}


def test_emite_certificado_y_publica_evento(entorno):
    cliente, redis, consumidor = entorno
    publicar(redis, "cursos-1", EVENTO)
    assert consumidor.procesar_lote(bloquear_ms=0) == 1

    [cert] = cliente.get("/certificados", headers=del_usuario()).json()
    assert cert["usuario_nombre"] == "Andrés Pabón" and cert["codigo"].startswith("AN-")
    [(_, emitido)] = redis.xrange(FLUJO_CERTIFICADOS)
    assert emitido["tipo"] == "certificado.emitido"
    # Certificados no está suscrito a su propio flujo: no queda nada por leer.
    assert consumidor.procesar_lote(bloquear_ms=0) == 0
    assert redis.xpending(FLUJO_CURSOS, "certificados")["pending"] == 0


def test_evento_repetido_no_duplica(entorno):
    cliente, redis, consumidor = entorno
    publicar(redis, "cursos-1", EVENTO)
    consumidor.procesar_lote(bloquear_ms=0)
    assert len(cliente.get("/certificados", headers=del_usuario()).json()) == 1


def test_descarga_y_verificacion(entorno):
    cliente, _, _ = entorno
    codigo = cliente.get("/certificados", headers=del_usuario()).json()[0]["codigo"]
    r = cliente.get(f"/certificados/{codigo}/pdf", headers=del_usuario())
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    # Otro estudiante, o la misma persona desde otra empresa, no lo descarga.
    assert cliente.get(f"/certificados/{codigo}/pdf", headers=del_usuario("6")).status_code == 404
    assert cliente.get(f"/certificados/{codigo}/pdf", headers=del_usuario(empresa=1)).status_code == 404
    # El administrador de la empresa sí.
    assert cliente.get(f"/certificados/{codigo}/pdf", headers=del_usuario("1", rol="admin")).status_code == 200
    v = cliente.get(f"/verificar/{codigo.lower()}").json()
    assert v["valido"] and v["curso_titulo"] == EVENTO["curso_titulo"]
    assert cliente.get("/verificar/AN-NOEXISTE").status_code == 404


def test_evento_invalido_va_a_fallidos(entorno):
    _, redis, consumidor = entorno
    publicar(redis, "cursos-99", {"inscripcion_id": 99})
    for _ in range(modulo.MAXIMO_INTENTOS):
        consumidor._ultimo_reclamo = 0
        modulo.RECLAMAR_TRAS_MS = 0
        consumidor.procesar_lote(bloquear_ms=0)
    assert redis.xlen(FLUJO_FALLIDOS) == 1
    assert redis.xpending(FLUJO_CURSOS, "certificados")["pending"] == 0


def test_estado_de_la_cola(entorno):
    cliente, _, _ = entorno
    estado = cliente.get("/cola").json()
    assert estado["certificados_emitidos"] == 1
    assert estado["grupos"][0]["grupo"] == "certificados"
