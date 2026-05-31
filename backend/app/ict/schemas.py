"""Pydantic schemas for ICT 2025 endpoints."""

import datetime

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    ejercicio_fiscal: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    ruc: str = Field(min_length=10, max_length=13, pattern=r"^\d+$")
    razon_social: str = Field(min_length=1, max_length=255)
    numero_adhesivo: str | None = Field(default=None, max_length=64)


class UpdateSessionRequest(BaseModel):
    ruc: str | None = Field(default=None, min_length=10, max_length=13, pattern=r"^\d+$")
    razon_social: str | None = Field(default=None, min_length=1, max_length=255)
    numero_adhesivo: str | None = Field(default=None, max_length=64)


class AnexoOut(BaseModel):
    anexo_code: str
    status: str
    warnings: list[str] = []
    uploaded_files: dict = {}
    last_updated_at: datetime.datetime


class SessionOut(BaseModel):
    id: int
    ejercicio_fiscal: str
    ruc: str
    razon_social: str
    numero_adhesivo: str | None
    status: str
    created_at: datetime.datetime
    last_activity_at: datetime.datetime
    expires_at: datetime.datetime
    anexos: list[AnexoOut] = []


class FileResult(BaseModel):
    filename: str
    status: str  # "ok" | "warning" | "error"
    periodo: str | None = None
    casilleros_found: int | None = None
    message: str | None = None
    errores: list[str] = []


class UploadResponse(BaseModel):
    anexo_code: str
    status: str
    warnings: list[str] = []
    filename: str          # nombre del primer archivo (backward compat)
    size_bytes: int        # tamaño total acumulado
    files_processed: int = 1
    per_file: list[FileResult] = []
