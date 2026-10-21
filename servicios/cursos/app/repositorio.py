"""Repositorio de cursos (patrón Repository).

Los controladores no escriben consultas: piden objetos del dominio a este
repositorio, que además impone el filtro por empresa en cada lectura. Así el
aislamiento entre inquilinos queda en un solo lugar.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .modelos import Curso, EventoSalida, Inscripcion, Leccion, LeccionVista, ahora


class RepositorioCursos:
    def __init__(self, sesion: Session):
        self.sesion = sesion

    # Cursos -----------------------------------------------------------------
    def listar(self, empresa_id: int) -> list[Curso]:
        return list(self.sesion.scalars(select(Curso).where(Curso.empresa_id == empresa_id).order_by(Curso.id)))

    def obtener(self, empresa_id: int, curso_id: int) -> Curso | None:
        return self.sesion.scalar(select(Curso).where(Curso.id == curso_id, Curso.empresa_id == empresa_id))

    def crear(self, empresa_id: int, titulo: str, descripcion: str, horas: int, lecciones: list[tuple[str, str]]) -> Curso:
        curso = Curso(empresa_id=empresa_id, titulo=titulo, descripcion=descripcion, horas=horas)
        curso.lecciones = [Leccion(orden=i + 1, titulo=t, contenido=c) for i, (t, c) in enumerate(lecciones)]
        self.sesion.add(curso)
        self.sesion.flush()
        return curso

    # Inscripciones ------------------------------------------------------------
    def inscripcion(self, curso_id: int, usuario_id: str) -> Inscripcion | None:
        return self.sesion.scalar(
            select(Inscripcion).where(Inscripcion.curso_id == curso_id, Inscripcion.usuario_id == usuario_id)
        )

    def inscripciones_de(self, empresa_id: int, usuario_id: str) -> dict[int, Inscripcion]:
        filas = self.sesion.scalars(
            select(Inscripcion).where(Inscripcion.empresa_id == empresa_id, Inscripcion.usuario_id == usuario_id)
        )
        return {i.curso_id: i for i in filas}

    def inscritos(self, curso_id: int, limite: int = 200) -> list[Inscripcion]:
        return list(
            self.sesion.scalars(
                select(Inscripcion).where(Inscripcion.curso_id == curso_id).order_by(Inscripcion.id.desc()).limit(limite)
            )
        )

    def resumen_inscritos(self, curso_id: int) -> dict:
        filas = self.sesion.execute(
            select(Inscripcion.estado, func.count()).where(Inscripcion.curso_id == curso_id).group_by(Inscripcion.estado)
        ).all()
        conteo = {estado: n for estado, n in filas}
        return {"total": sum(conteo.values()), "completados": conteo.get("completado", 0)}

    def inscribir(self, curso: Curso, usuario_id: str, usuario_nombre: str) -> Inscripcion:
        inscripcion = Inscripcion(
            curso_id=curso.id, empresa_id=curso.empresa_id, usuario_id=usuario_id, usuario_nombre=usuario_nombre
        )
        self.sesion.add(inscripcion)
        self.sesion.flush()
        return inscripcion

    def lecciones_vistas(self, inscripcion_id: int) -> set[int]:
        return set(self.sesion.scalars(select(LeccionVista.leccion_id).where(LeccionVista.inscripcion_id == inscripcion_id)))

    def marcar_vista(self, inscripcion: Inscripcion, leccion_id: int) -> None:
        if leccion_id not in self.lecciones_vistas(inscripcion.id):
            self.sesion.add(LeccionVista(inscripcion_id=inscripcion.id, leccion_id=leccion_id))
            self.sesion.flush()

    def completar(self, inscripcion: Inscripcion, curso: Curso, empresa_nombre: str) -> None:
        """Marca la inscripción como completada y deja el evento en la bandeja de salida."""
        inscripcion.estado = "completado"
        inscripcion.progreso = 100
        inscripcion.completado_en = ahora()
        self.sesion.flush()
        self.sesion.add(
            EventoSalida(
                tipo="curso.completado",
                datos={
                    "inscripcion_id": inscripcion.id,
                    "curso_id": curso.id,
                    "curso_titulo": curso.titulo,
                    "horas": curso.horas,
                    "usuario_id": inscripcion.usuario_id,
                    "usuario_nombre": inscripcion.usuario_nombre,
                    "empresa_id": curso.empresa_id,
                    "empresa_nombre": empresa_nombre,
                    "completado_en": inscripcion.completado_en.isoformat(),
                },
            )
        )

    def eventos_pendientes(self) -> int:
        return self.sesion.scalar(select(func.count()).select_from(EventoSalida).where(EventoSalida.publicado_en.is_(None)))
