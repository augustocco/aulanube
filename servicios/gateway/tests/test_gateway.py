import time

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.interruptor import Interruptor
from app.limitador import Cubeta


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def token(rol="estudiante", empresa_id=1):
    return jwt.encode(
        {"sub": "7", "nombre": "José Peña", "rol": rol, "empresa_id": empresa_id, "empresa": "Clínica Santa Lucía",
         "exp": int(time.time()) + 60},
        config.JWT_SECRETO,
        algorithm="HS256",
    )


@pytest.fixture
def cliente():
    for i in main.interruptores.values():
        i.exito()
    main.limitador._fichas.clear()
    recibidas = []

    def manejar(solicitud: httpx.Request):
        recibidas.append(solicitud)
        if solicitud.url.host == "certificados":
            raise httpx.ConnectError("caído", request=solicitud)
        return httpx.Response(200, json={"ruta": solicitud.url.path})

    with TestClient(main.app) as c:
        main.app.state.cliente = httpx.AsyncClient(transport=httpx.MockTransport(manejar))
        c.recibidas = recibidas
        yield c


def test_interruptor_abre_y_se_recupera_en_semiabierto():
    reloj = Reloj()
    i = Interruptor("x", umbral=2, espera=10, reloj=reloj)
    i.fallo()
    assert i.permitir()
    i.fallo()
    assert i.estado == "abierto" and not i.permitir()
    reloj.t = 11
    assert i.resumen()["estado"] == "semiabierto"
    assert i.permitir() and i.estado == "semiabierto"
    assert not i.permitir()  # solo una solicitud de prueba
    i.exito()
    assert i.estado == "cerrado"


def test_interruptor_semiabierto_que_falla_vuelve_a_abrir():
    reloj = Reloj()
    i = Interruptor("x", umbral=1, espera=5, reloj=reloj)
    i.fallo()
    reloj.t = 6
    assert i.permitir()
    i.fallo()
    assert i.estado == "abierto"


def test_cubeta_limita_y_recarga():
    reloj = Reloj()
    c = Cubeta(tasa=1, capacidad=2, reloj=reloj)
    assert c.consumir("a") and c.consumir("a") and not c.consumir("a")
    assert c.consumir("b")  # otra empresa no se ve afectada
    reloj.t = 1
    assert c.consumir("a")


def test_sin_token_responde_401(cliente):
    assert cliente.get("/api/cursos/cursos").status_code == 401


def test_ruta_publica_no_exige_token(cliente):
    assert cliente.post("/api/identidad/login", json={}).status_code == 200


def test_reenvia_identidad_y_borra_cabeceras_falsificadas(cliente):
    r = cliente.get(
        "/api/cursos/cursos",
        headers={"Authorization": f"Bearer {token()}", "X-Rol": "admin", "X-Empresa-Id": "99"},
    )
    assert r.status_code == 200
    enviada = cliente.recibidas[-1]
    assert enviada.url.path == "/cursos"
    assert enviada.headers["x-rol"] == "estudiante"
    assert enviada.headers["x-empresa-id"] == "1"
    assert enviada.headers["x-usuario-nombre"] == "Jos%C3%A9%20Pe%C3%B1a"
    assert "authorization" not in enviada.headers
    assert r.headers["x-correlacion-id"]


def test_circuito_se_abre_tras_fallos_seguidos(cliente):
    cabeceras = {"Authorization": f"Bearer {token()}"}
    for _ in range(config.UMBRAL_FALLOS):
        assert cliente.get("/api/certificados/certificados", headers=cabeceras).status_code == 503
    llamadas = len(cliente.recibidas)
    r = cliente.get("/api/certificados/certificados", headers=cabeceras)
    assert r.status_code == 503 and r.headers["x-circuito"] == "abierto"
    assert len(cliente.recibidas) == llamadas  # ya no se toca el servicio caído
    # Los demás servicios siguen respondiendo.
    assert cliente.get("/api/cursos/cursos", headers=cabeceras).status_code == 200


def test_get_reintenta_una_vez(cliente):
    cabeceras = {"Authorization": f"Bearer {token()}"}
    cliente.get("/api/certificados/certificados", headers=cabeceras)
    assert len(cliente.recibidas) == 2


def test_estado_solo_para_admin(cliente):
    assert cliente.get("/api/estado", headers={"Authorization": f"Bearer {token()}"}).status_code == 403
    r = cliente.get("/api/estado", headers={"Authorization": f"Bearer {token('admin')}"})
    assert r.status_code == 200
    estados = {s["servicio"]: s["disponible"] for s in r.json()["servicios"]}
    assert estados["cursos"] and not estados["certificados"]


def test_limite_por_empresa(cliente, monkeypatch):
    monkeypatch.setattr(main, "limitador", Cubeta(tasa=0.001, capacidad=2))
    cabeceras = {"Authorization": f"Bearer {token()}"}
    codigos = [cliente.get("/api/cursos/cursos", headers=cabeceras).status_code for _ in range(3)]
    assert codigos == [200, 200, 429]
