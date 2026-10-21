"""Prueba de humo de punta a punta contra un despliegue de AulaNube.

    python scripts/prueba_humo.py                       # local, http://localhost:8080
    python scripts/prueba_humo.py https://<dominio>     # despliegue en la nube

Recorre el flujo principal: ingreso, inscripción, lecciones, certificado
emitido por el trabajador, aviso generado y verificación pública. Usa solo la
biblioteca estándar.
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
CLAVE = "AulaNube-2026"


def llamar(metodo, ruta, token=None, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    solicitud = urllib.request.Request(f"{BASE}/api/{ruta}", data=datos, method=metodo)
    if datos is not None:
        solicitud.add_header("Content-Type", "application/json")
    if token:
        solicitud.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(solicitud, timeout=15) as r:
            contenido = r.read()
            return r.status, (json.loads(contenido) if r.headers.get_content_type() == "application/json" else contenido)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def ingresar(correo):
    estado, r = llamar("POST", "identidad/login", cuerpo={"correo": correo, "clave": CLAVE})
    assert estado == 200, (estado, r)
    return r["token"]


def esperar(condicion, segundos=30):
    limite = time.time() + segundos
    while time.time() < limite:
        valor = condicion()
        if valor:
            return valor
        time.sleep(0.5)
    raise AssertionError("tiempo de espera agotado")


def paso(texto):
    print(f"  ✔ {texto}")


def main():
    print(f"Prueba de humo contra {BASE}")
    estado, _ = llamar("GET", "cursos/cursos")
    assert estado == 401, estado
    paso("sin token el gateway responde 401")

    admin = ingresar("admin@andes.demo")
    # Colaborador nuevo en cada ejecución: tiene todos los cursos pendientes y no ensucia el catálogo.
    correo = f"humo-{int(time.time())}@andes.demo"
    estado, _ = llamar("POST", "identidad/usuarios", admin, {"nombre": "Prueba de humo", "correo": correo, "clave": CLAVE})
    assert estado == 201, estado
    alumno = ingresar(correo)
    paso("ingreso de administradora y de un colaborador creado para la prueba")

    _, cursos = llamar("GET", "cursos/cursos", alumno)
    _, otros = llamar("GET", "cursos/cursos", ingresar("andres@santalucia.demo"))
    assert not {c["id"] for c in cursos} & {c["id"] for c in otros}
    paso(f"catálogo aislado por empresa ({len(cursos)} cursos de Los Andes)")

    pendiente = min(cursos, key=lambda c: c["lecciones"])
    curso_id = pendiente["id"]
    llamar("POST", f"cursos/cursos/{curso_id}/inscripcion", alumno)
    _, detalle = llamar("GET", f"cursos/cursos/{curso_id}", alumno)
    for leccion in detalle["lecciones"]:
        _, insc = llamar("POST", f"cursos/cursos/{curso_id}/lecciones/{leccion['id']}/completar", alumno)
    assert insc["estado"] == "completado", insc
    paso(f"curso «{detalle['titulo']}» completado")

    def certificado():
        _, lista = llamar("GET", "certificados/certificados", alumno)
        return next((c for c in lista if c["curso_titulo"] == detalle["titulo"]), None)

    cert = esperar(certificado)
    paso(f"certificado {cert['codigo']} emitido por {cert['emitido_por'] or 'el trabajador'}")

    estado, pdf = llamar("GET", f"certificados/certificados/{cert['codigo']}/pdf", alumno)
    assert estado == 200 and pdf[:4] == b"%PDF"
    estado, v = llamar("GET", f"certificados/verificar/{cert['codigo']}")
    assert estado == 200 and v["valido"]
    paso("PDF descargado y verificación pública sin token")

    _, avisos = llamar("GET", "notificaciones/notificaciones", alumno)
    esperar(lambda: any(cert["codigo"] in a["mensaje"] for a in llamar("GET", "notificaciones/notificaciones", alumno)[1]["avisos"]))
    paso("aviso «Tu certificado está listo» recibido")

    _, antes = llamar("GET", "estado", admin)
    emitidos = antes["cola"]["certificados_emitidos"]
    inicio = time.time()
    estado, r = llamar("POST", "cursos/campanas", admin, {"curso_id": curso_id, "participantes": 40})
    assert estado == 202, (estado, r)
    respuesta_ms = (time.time() - inicio) * 1000
    esperar(lambda: llamar("GET", "estado", admin)[1]["cola"]["certificados_emitidos"] >= emitidos + 40, 120)
    paso(f"campaña de 40 participantes: respuesta en {respuesta_ms:.0f} ms, certificados listos en {time.time() - inicio:.1f} s")

    _, estado_final = llamar("GET", "estado", admin)
    for s in estado_final["servicios"]:
        assert s["disponible"], s
    paso("los cuatro servicios responden y sus circuitos están cerrados")
    print("Todo en orden.")


if __name__ == "__main__":
    main()
