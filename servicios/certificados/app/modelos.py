from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, deferred, mapped_column

from .db import Base


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class Certificado(Base):
    __tablename__ = "certificados"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    # Una inscripción produce un solo certificado aunque el evento llegue dos veces.
    inscripcion_id: Mapped[int] = mapped_column(Integer, unique=True)
    empresa_id: Mapped[int] = mapped_column(Integer, index=True)
    empresa_nombre: Mapped[str] = mapped_column(String(120))
    usuario_id: Mapped[str] = mapped_column(String(40), index=True)
    usuario_nombre: Mapped[str] = mapped_column(String(120))
    curso_titulo: Mapped[str] = mapped_column(String(160))
    horas: Mapped[int] = mapped_column(Integer)
    emitido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    emitido_por: Mapped[str] = mapped_column(String(80), default="")
    # El PDF no se carga en los listados, solo al descargarlo.
    pdf: Mapped[bytes] = deferred(mapped_column(LargeBinary))
