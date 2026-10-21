from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class Curso(Base):
    __tablename__ = "cursos"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(Integer, index=True)
    titulo: Mapped[str] = mapped_column(String(160))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    horas: Mapped[int] = mapped_column(Integer, default=1)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    lecciones: Mapped[list["Leccion"]] = relationship(
        order_by="Leccion.orden", cascade="all, delete-orphan", lazy="selectin"
    )


class Leccion(Base):
    __tablename__ = "lecciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("cursos.id"), index=True)
    orden: Mapped[int] = mapped_column(Integer)
    titulo: Mapped[str] = mapped_column(String(160))
    contenido: Mapped[str] = mapped_column(Text, default="")


class Inscripcion(Base):
    __tablename__ = "inscripciones"
    __table_args__ = (UniqueConstraint("curso_id", "usuario_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("cursos.id"), index=True)
    empresa_id: Mapped[int] = mapped_column(Integer, index=True)
    # El usuario vive en el servicio de identidad: aquí solo se guarda una copia
    # del identificador y del nombre, sin clave foránea entre bases.
    usuario_id: Mapped[str] = mapped_column(String(40), index=True)
    usuario_nombre: Mapped[str] = mapped_column(String(120))
    estado: Mapped[str] = mapped_column(String(20), default="en_progreso")
    progreso: Mapped[int] = mapped_column(Integer, default=0)
    inscrito_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    completado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LeccionVista(Base):
    __tablename__ = "lecciones_vistas"
    __table_args__ = (UniqueConstraint("inscripcion_id", "leccion_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    inscripcion_id: Mapped[int] = mapped_column(ForeignKey("inscripciones.id"), index=True)
    leccion_id: Mapped[int] = mapped_column(ForeignKey("lecciones.id"))
    vista_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class EventoSalida(Base):
    """Bandeja de salida (Transactional Outbox).

    El evento se guarda en la misma transacción que el cambio que lo origina;
    un hilo aparte lo publica en Redis. Si Redis no está, el evento espera aquí.
    """

    __tablename__ = "eventos_salida"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(60))
    datos: Mapped[dict] = mapped_column(JSON)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
