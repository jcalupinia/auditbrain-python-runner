"""Trazabilidad de los envíos de circularización.

Cada llamada a `/enviar` registra un lote: quién, cuándo, cuántas cartas, el
resultado por carta y una foto mínima del encargo. `resumen` va como JSON porque
solo se lista/consulta por proyecto y fecha; normalizarlo no compra nada hoy.
"""
import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.app.db.session import Base


def _ahora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class ConfirmacionEnvio(Base):
    """Un lote de envío de cartas de confirmación (bitácora, NIA 505/230)."""

    __tablename__ = "aud_confirmaciones_envios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    enviado_por: Mapped[str | None] = mapped_column(String(320), nullable=True)
    enviado_en: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_ahora, index=True, nullable=False
    )
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    enviadas: Mapped[int] = mapped_column(Integer, nullable=False)
    fallidas: Mapped[int] = mapped_column(Integer, nullable=False)
    # Foto mínima del encargo para poder auditar el lote sin recomputar.
    cliente: Mapped[str | None] = mapped_column(String(320), nullable=True)
    corte: Mapped[str | None] = mapped_column(String(20), nullable=True)
    idioma: Mapped[str | None] = mapped_column(String(8), nullable=True)
    input_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # [{id, to, status, provider_id?|detail?}] por carta.
    resumen: Mapped[dict] = mapped_column(JSON, nullable=False)
