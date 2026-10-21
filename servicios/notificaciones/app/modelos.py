from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Clave de idempotencia: el mismo evento nunca genera dos avisos.
    evento_id: Mapped[str] = mapped_column(String(80), unique=True)
    empresa_id: Mapped[int] = mapped_column(Integer, index=True)
    usuario_id: Mapped[str] = mapped_column(String(40), index=True)
    titulo: Mapped[str] = mapped_column(String(160))
    mensaje: Mapped[str] = mapped_column(Text)
    enlace: Mapped[str] = mapped_column(String(200), default="")
    leida: Mapped[bool] = mapped_column(Boolean, default=False)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
