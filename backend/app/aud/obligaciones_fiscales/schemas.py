"""Pydantic schemas de la API de AUD.IMPUESTOS.OBLIGACIONES_FISCALES."""

import datetime

from pydantic import BaseModel


FIRMAS_VALIDAS = {"audit_consulting", "partner_auditing"}


class JobCreateForm(BaseModel):
    """Datos del form (no incluye archivos — esos van como UploadFile en multipart)."""

    project_id: int
    cliente_name: str
    period_label: str
    period_start: datetime.date | None = None
    period_end: datetime.date | None = None
    prepared_by_name: str | None = None
    reviewed_by_name: str | None = None
    firma_auditora: str | None = None  # "audit_consulting" | "partner_auditing"


class JobOut(BaseModel):
    id: int
    user_id: int | None
    project_id: int
    tool_code: str
    status: str
    cliente_name: str
    period_label: str
    period_start: datetime.date | None
    period_end: datetime.date | None
    prepared_by_name: str | None
    reviewed_by_name: str | None
    firma_auditora: str | None
    error_message: str | None
    summary_json: dict | None
    created_at: datetime.datetime
    finished_at: datetime.datetime | None
    downloaded_at: datetime.datetime | None
    expires_at: datetime.datetime

    model_config = {"from_attributes": True}
