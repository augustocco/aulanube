import json
import os

os.environ["RELEVO_ACTIVO"] = "false"

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import relevo  # noqa: E402
from app.db import Sesion  # noqa: E402
from app.main import app  # noqa: E402


def quien(usuario="10", empresa=1, rol="estudiante", nombre="Carlos Rinc%C3%B3n"):
    return {
        "X-Usuario-Id": usuario,
        "X-Usuario-Nombre": nombre,
        "X-Empresa-Id": str(empresa),
        "X-Empresa-Nombre": "Constructora%20Los%20Andes",
        "X-Rol": rol,
    }


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:
        yield c


def test_catalogo_aislado_por_empresa(cliente):
    andes = {c["titulo"] for c in cliente.get("/cursos", headers=quien(empresa=1)).json()}
    lucia = {c["titulo"] for c in cliente.get("/cursos", headers=quien(empresa=2)).json()}
    assert andes and lucia and not andes & lucia
    otro = cliente.get("/cursos", headers=quien(empresa=2)).json()[0]["id"]
    assert cliente.get(f"/cursos/{otro}", headers=quien(empresa=1)).status_code == 404


def test_completar_curso_deja_evento_en_bandeja(cliente):
    curso = cliente.get("/cursos", headers=quien()).json()[1]
    assert cliente.post(f"/cursos/{curso['id']}/inscripcion", headers=quien()).status_code == 201
    detalle = cliente.get(f"/cursos/{curso['id']}", headers=quien()).json()
    progreso = []
    for leccion in detalle["lecciones"]:
        r = cliente.post(f"/cursos/{curso['id']}/lecciones/{leccion['id']}/completar", headers=quien())
        progreso.append(r.json()["progreso"])
    assert progreso[-1] == 100 and progreso[0] < 100
    assert r.json()["estado"] == "completado"
    assert cliente.get("/eventos/pendientes").json()["pendientes"] == 1

    redis = fakeredis.FakeRedis(decode_responses=True)
    assert relevo.publicar_pendientes(Sesion, redis) == 1
    assert relevo.publicar_pendientes(Sesion, redis) == 0
    [(_, campos)] = redis.xrange(relevo.FLUJO)
    datos = json.loads(campos["datos"])
    assert campos["tipo"] == "curso.completado"
    assert datos["usuario_nombre"] == "Carlos Rincón"
    assert datos["empresa_nombre"] == "Constructora Los Andes"


def test_repetir_leccion_no_duplica_evento(cliente):
    curso = cliente.get("/cursos", headers=quien()).json()[1]
    leccion = cliente.get(f"/cursos/{curso['id']}", headers=quien()).json()["lecciones"][0]
    cliente.post(f"/cursos/{curso['id']}/lecciones/{leccion['id']}/completar", headers=quien())
    assert cliente.get("/eventos/pendientes").json()["pendientes"] == 0


def test_sin_inscripcion_no_se_avanza(cliente):
    curso = cliente.get("/cursos", headers=quien(usuario="11")).json()[0]
    leccion = cliente.get(f"/cursos/{curso['id']}", headers=quien(usuario="11")).json()["lecciones"][0]
    r = cliente.post(f"/cursos/{curso['id']}/lecciones/{leccion['id']}/completar", headers=quien(usuario="11"))
    assert r.status_code == 409


def test_solo_admin_crea_cursos_y_campanas(cliente):
    nuevo = {"titulo": "Manejo de residuos", "horas": 2, "lecciones": [{"titulo": "Clasificación"}]}
    assert cliente.post("/cursos", json=nuevo, headers=quien()).status_code == 403
    r = cliente.post("/cursos", json=nuevo, headers=quien(usuario="1", rol="admin"))
    assert r.status_code == 201 and r.json()["lecciones"] == 1

    r = cliente.post("/campanas", json={"curso_id": r.json()["id"], "participantes": 25}, headers=quien(usuario="1", rol="admin"))
    assert r.status_code == 202
    assert cliente.get("/eventos/pendientes").json()["pendientes"] == 25
