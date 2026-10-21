"""Servicio de cursos: catálogo por empresa, inscripciones y progreso.

Cuando un estudiante termina la última lección se registra el evento
`curso.completado`. Este servicio no sabe quién lo consume: certificados y
notificaciones se suscriben por su cuenta (bajo acoplamiento).
"""

import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import relevo
from .contexto import Contexto, contexto, solo_admin
from .db import Base, Sesion, esperar_base, motor, obtener_sesion
from .modelos import Curso, Inscripcion
from .repositorio import RepositorioCursos
from .semilla import sembrar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

RELEVO_ACTIVO = os.environ.get("RELEVO_ACTIVO", "true") == "true"


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    esperar_base()
    Base.metadata.create_all(motor)
    with Sesion() as sesion:
        sembrar(sesion)
    detener = threading.Event()
    if RELEVO_ACTIVO:
        relevo.iniciar(detener)
    yield
    detener.set()


app = FastAPI(title="AulaNube · Cursos", lifespan=ciclo_de_vida)


def repositorio(sesion: Session = Depends(obtener_sesion)) -> RepositorioCursos:
    return RepositorioCursos(sesion)


class NuevaLeccion(BaseModel):
    titulo: str = Field(min_length=2, max_length=160)
    contenido: str = Field(default="", max_length=10_000)


class NuevoCurso(BaseModel):
    titulo: str = Field(min_length=3, max_length=160)
    descripcion: str = Field(default="", max_length=2000)
    horas: int = Field(default=1, ge=1, le=200)
    lecciones: list[NuevaLeccion] = Field(min_length=1, max_length=50)


class Campana(BaseModel):
    curso_id: int
    participantes: int = Field(ge=1, le=500)


def vista_inscripcion(i: Inscripcion | None) -> dict | None:
    if i is None:
        return None
    return {
        "id": i.id,
        "estado": i.estado,
        "progreso": i.progreso,
        "completado_en": i.completado_en.isoformat() if i.completado_en else None,
    }


def vista_curso(c: Curso, inscripcion: Inscripcion | None = None) -> dict:
    return {
        "id": c.id,
        "titulo": c.titulo,
        "descripcion": c.descripcion,
        "horas": c.horas,
        "lecciones": len(c.lecciones),
        "inscripcion": vista_inscripcion(inscripcion),
    }


def curso_o_404(repo: RepositorioCursos, ctx: Contexto, curso_id: int) -> Curso:
    curso = repo.obtener(ctx.empresa_id, curso_id)
    if curso is None:
        raise HTTPException(404, "Curso no encontrado")
    return curso


@app.get("/salud")
def salud():
    return {"estado": "ok"}


@app.get("/cursos")
def listar(ctx: Contexto = Depends(contexto), repo: RepositorioCursos = Depends(repositorio)):
    mias = repo.inscripciones_de(ctx.empresa_id, ctx.usuario_id)
    cursos = []
    for c in repo.listar(ctx.empresa_id):
        vista = vista_curso(c, mias.get(c.id))
        if ctx.es_admin:
            vista["inscritos"] = repo.resumen_inscritos(c.id)
        cursos.append(vista)
    return cursos


@app.post("/cursos", status_code=201)
def crear(datos: NuevoCurso, ctx: Contexto = Depends(solo_admin), repo: RepositorioCursos = Depends(repositorio)):
    curso = repo.crear(
        ctx.empresa_id,
        datos.titulo.strip(),
        datos.descripcion.strip(),
        datos.horas,
        [(l.titulo.strip(), l.contenido.strip()) for l in datos.lecciones],
    )
    repo.sesion.commit()
    return vista_curso(curso)


@app.get("/cursos/{curso_id}")
def detalle(curso_id: int, ctx: Contexto = Depends(contexto), repo: RepositorioCursos = Depends(repositorio)):
    curso = curso_o_404(repo, ctx, curso_id)
    inscripcion = repo.inscripcion(curso.id, ctx.usuario_id)
    vistas = repo.lecciones_vistas(inscripcion.id) if inscripcion else set()
    vista = vista_curso(curso, inscripcion)
    vista["lecciones"] = [
        {"id": l.id, "orden": l.orden, "titulo": l.titulo, "contenido": l.contenido, "vista": l.id in vistas}
        for l in curso.lecciones
    ]
    return vista


@app.post("/cursos/{curso_id}/inscripcion", status_code=201)
def inscribirse(curso_id: int, ctx: Contexto = Depends(contexto), repo: RepositorioCursos = Depends(repositorio)):
    curso = curso_o_404(repo, ctx, curso_id)
    existente = repo.inscripcion(curso.id, ctx.usuario_id)
    if existente:
        return vista_inscripcion(existente)
    try:
        inscripcion = repo.inscribir(curso, ctx.usuario_id, ctx.usuario_nombre)
        repo.sesion.commit()
    except IntegrityError:
        # Dos clics simultáneos: la restricción única deja pasar solo uno.
        repo.sesion.rollback()
        inscripcion = repo.inscripcion(curso.id, ctx.usuario_id)
    return vista_inscripcion(inscripcion)


@app.post("/cursos/{curso_id}/lecciones/{leccion_id}/completar")
def completar_leccion(
    curso_id: int, leccion_id: int, ctx: Contexto = Depends(contexto), repo: RepositorioCursos = Depends(repositorio)
):
    curso = curso_o_404(repo, ctx, curso_id)
    if leccion_id not in {l.id for l in curso.lecciones}:
        raise HTTPException(404, "Lección no encontrada")
    inscripcion = repo.inscripcion(curso.id, ctx.usuario_id)
    if inscripcion is None:
        raise HTTPException(409, "Primero inscríbase en el curso")
    if inscripcion.estado == "completado":
        return vista_inscripcion(inscripcion)

    repo.marcar_vista(inscripcion, leccion_id)
    vistas = len(repo.lecciones_vistas(inscripcion.id))
    if vistas >= len(curso.lecciones):
        repo.completar(inscripcion, curso, ctx.empresa_nombre)
    else:
        inscripcion.progreso = round(100 * vistas / len(curso.lecciones))
    repo.sesion.commit()
    return vista_inscripcion(inscripcion)


@app.get("/cursos/{curso_id}/inscritos")
def inscritos(curso_id: int, ctx: Contexto = Depends(solo_admin), repo: RepositorioCursos = Depends(repositorio)):
    curso = curso_o_404(repo, ctx, curso_id)
    return {
        "resumen": repo.resumen_inscritos(curso.id),
        "inscritos": [
            {"usuario_nombre": i.usuario_nombre, **vista_inscripcion(i)} for i in repo.inscritos(curso.id)
        ],
    }


@app.post("/campanas", status_code=202)
def campana(datos: Campana, ctx: Contexto = Depends(solo_admin), repo: RepositorioCursos = Depends(repositorio)):
    """Simula el cierre de una campaña masiva: N participantes terminan el curso a la vez.

    Responde enseguida (202): los certificados se generan después, a medida que
    los trabajadores consumen la cola. Es la demostración de nivelación de carga.
    """
    curso = curso_o_404(repo, ctx, datos.curso_id)
    lote = uuid.uuid4().hex[:6]
    for n in range(1, datos.participantes + 1):
        inscripcion = repo.inscribir(curso, f"sim-{lote}-{n}", f"Participante {lote.upper()}-{n:03d}")
        repo.completar(inscripcion, curso, ctx.empresa_nombre)
    repo.sesion.commit()
    return {"curso_id": curso.id, "eventos": datos.participantes, "lote": lote}


@app.get("/eventos/pendientes")
def pendientes(repo: RepositorioCursos = Depends(repositorio)):
    return {"pendientes": repo.eventos_pendientes()}
