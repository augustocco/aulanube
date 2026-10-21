import os

os.environ["BCRYPT_RONDAS"] = "4"

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seguridad import JWT_SECRETO  # noqa: E402
from app.semilla import CLAVE_DEMO  # noqa: E402


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:
        yield c


def admin(empresa_id=1):
    return {"X-Usuario-Id": "1", "X-Empresa-Id": str(empresa_id), "X-Rol": "admin"}


def test_login_emite_token_con_empresa(cliente):
    r = cliente.post("/login", json={"correo": "Carlos@andes.demo", "clave": CLAVE_DEMO})
    assert r.status_code == 200
    reclamos = jwt.decode(r.json()["token"], JWT_SECRETO, algorithms=["HS256"])
    assert reclamos["rol"] == "estudiante"
    assert reclamos["empresa_id"] == 1
    assert reclamos["empresa"] == "Constructora Los Andes S.A.S."


def test_login_con_clave_errada(cliente):
    assert cliente.post("/login", json={"correo": "carlos@andes.demo", "clave": "otra"}).status_code == 401


def test_admin_solo_ve_usuarios_de_su_empresa(cliente):
    correos = {u["correo"] for u in cliente.get("/usuarios", headers=admin(2)).json()}
    assert "andres@santalucia.demo" in correos
    assert not any(c.endswith("@andes.demo") for c in correos)


def test_estudiante_no_puede_listar_usuarios(cliente):
    r = cliente.get("/usuarios", headers={"X-Usuario-Id": "2", "X-Empresa-Id": "1", "X-Rol": "estudiante"})
    assert r.status_code == 403


def test_crear_usuario_y_correo_repetido(cliente):
    datos = {"nombre": "Nuevo Operario", "correo": "operario@andes.demo", "clave": "clave-segura-1"}
    r = cliente.post("/usuarios", json=datos, headers=admin())
    assert r.status_code == 201 and r.json()["empresa_id"] == 1
    assert cliente.post("/usuarios", json=datos, headers=admin()).status_code == 409


def test_sin_identidad_responde_401(cliente):
    assert cliente.get("/yo").status_code == 401
