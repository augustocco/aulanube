import json
import os

os.environ["CONSUMIDOR_ACTIVO"] = "false"

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.consumidor import FLUJO_CERTIFICADOS, FLUJO_CURSOS, Consumidor  # noqa: E402
from app.main import app, manejar  # noqa: E402

COMPLETADO = {"inscripcion_id": 1, "curso_id": 2, "curso_titulo": "Inducción al SG-SST", "usuario_id": "2",
              "usuario_nombre": "Carlos Rincón", "empresa_id": 1}
EMITIDO = {"codigo": "AN-ABCD2345", "inscripcion_id": 1, "curso_titulo": "Inducción al SG-SST", "usuario_id": "2",
           "usuario_nombre": "Carlos Rincón", "empresa_id": 1}

CARLOS = {"X-Usuario-Id": "2", "X-Empresa-Id": "1"}


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:
        yield c


def test_un_aviso_por_evento_aunque_llegue_dos_veces(cliente):
    redis = fakeredis.FakeRedis(decode_responses=True)
    consumidor = Consumidor("notificaciones", [FLUJO_CURSOS, FLUJO_CERTIFICADOS], manejar, redis, nombre="prueba")
    consumidor.asegurar_grupo()
    for flujo, evento_id, tipo, datos in [
        (FLUJO_CURSOS, "cursos-1", "curso.completado", COMPLETADO),
        (FLUJO_CERTIFICADOS, "certificados-AN-ABCD2345", "certificado.emitido", EMITIDO),
        (FLUJO_CURSOS, "cursos-1", "curso.completado", COMPLETADO),
    ]:
        redis.xadd(flujo, {"evento_id": evento_id, "tipo": tipo, "datos": json.dumps(datos)})
    consumidor.procesar_lote(bloquear_ms=0)

    r = cliente.get("/notificaciones", headers=CARLOS).json()
    assert r["sin_leer"] == 2
    assert [a["titulo"] for a in r["avisos"]] == ["Tu certificado está listo", "Completaste «Inducción al SG-SST»"]


def test_avisos_privados_y_marcar_leidos(cliente):
    otro = {"X-Usuario-Id": "3", "X-Empresa-Id": "1"}
    assert cliente.get("/notificaciones", headers=otro).json()["avisos"] == []
    aviso = cliente.get("/notificaciones", headers=CARLOS).json()["avisos"][0]["id"]
    assert cliente.post(f"/notificaciones/{aviso}/leida", headers=otro).status_code == 404
    assert cliente.post(f"/notificaciones/{aviso}/leida", headers=CARLOS).status_code == 200
    assert cliente.get("/notificaciones", headers=CARLOS).json()["sin_leer"] == 1
    cliente.post("/notificaciones/leidas", headers=CARLOS)
    assert cliente.get("/notificaciones", headers=CARLOS).json()["sin_leer"] == 0
