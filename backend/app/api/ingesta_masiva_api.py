"""API opt-in para ingesta masiva; solo SQLite aislado, sin acceso a PostgreSQL.

El router padre /ingesta aplica require_runner_access. No se registra ni abre
ninguna base si INGESTA_MASIVA_SQLITE_PATH no esta configurada.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import create_engine

from backend.app.ingesta.ingesta_masiva import crear_tablas, consultar_filas, ingerir_archivo

router = APIRouter(prefix="/masiva", tags=["ingesta-masiva"])
_CHUNK = 1024 * 1024
_MAX_BYTES = 100 * 1024 * 1024


def _engine_aislado():
    ruta = os.environ.get("INGESTA_MASIVA_SQLITE_PATH", "").strip()
    if not ruta:
        raise HTTPException(503, "Ingesta masiva no habilitada: falta ruta SQLite aislada")
    p = Path(ruta).expanduser().resolve()
    if p.suffix.lower() not in (".db", ".sqlite", ".sqlite3"):
        raise HTTPException(503, "La base aislada debe ser SQLite")
    if not p.parent.is_dir():
        raise HTTPException(503, "Directorio de base aislada inexistente")
    engine = create_engine("sqlite:///" + str(p))
    crear_tablas(engine)  # DDL solo en SQLite explicitamente configurado
    return engine


def _mapeo(raw: str):
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(400, "mapeo_confirmado debe ser JSON valido")
    if not isinstance(value, dict) or not value:
        raise HTTPException(400, "mapeo_confirmado debe ser objeto no vacio")
    if any(not isinstance(k, str) or type(v) is not int for k, v in value.items()):
        raise HTTPException(400, "Los indices del mapeo deben ser enteros")
    return value


@router.post("/cargar")
async def cargar(
    file: UploadFile = File(...),
    cliente_id: str = Form(...),
    encargo_id: str = Form(...),
    periodo: str = Form(...),
    tipo_documento: str = Form(...),
    mapeo_confirmado: str = Form(...),
    saltar_filas: int = Form(1),
):
    """Sube CSV/XLSX sin retener poblacion completa; responde solo metadatos."""
    nombre = (file.filename or "").lower()
    sufijo = Path(nombre).suffix
    if sufijo not in (".csv", ".xlsx"):
        raise HTTPException(400, "Solo CSV o XLSX")
    if any(not x.strip() or len(x) > 128 for x in (cliente_id, encargo_id, periodo)):
        raise HTTPException(400, "Cliente, encargo y periodo son obligatorios")
    mapeo = _mapeo(mapeo_confirmado)
    engine = _engine_aislado()
    ruta = None
    try:
        with tempfile.NamedTemporaryFile(prefix="ingesta_", suffix=sufijo, delete=False) as tmp:
            ruta = Path(tmp.name)
            n = 0
            while True:
                chunk = await file.read(_CHUNK)
                if not chunk:
                    break
                n += len(chunk)
                if n > _MAX_BYTES:
                    raise HTTPException(413, "Archivo supera 100 MB")
                tmp.write(chunk)
        if n == 0:
            raise HTTPException(400, "Archivo vacio")
        try:
            return ingerir_archivo(
                engine, ruta, cliente_id=cliente_id, encargo_id=encargo_id,
                periodo=periodo, tipo_documento=tipo_documento,
                mapeo_confirmado=mapeo, saltar_filas=saltar_filas,
            )
        except (ValueError, KeyError) as exc:
            raise HTTPException(400, str(exc)) from exc
    finally:
        if ruta is not None:
            ruta.unlink(missing_ok=True)
        engine.dispose()


@router.get("/{dataset_id}/filas")
def pagina(
    dataset_id: str,
    cliente_id: str = Query(...),
    encargo_id: str = Query(...),
    limite: int = Query(100, ge=1, le=1000),
    desde_fila: int = Query(0, ge=0),
):
    engine = _engine_aislado()
    try:
        try:
            return {"dataset_id": dataset_id, "filas": consultar_filas(
                engine, dataset_id, cliente_id=cliente_id,
                encargo_id=encargo_id, limite=limite, desde_fila=desde_fila,
            )}
        except LookupError:
            raise HTTPException(404, "Dataset no encontrado en este encargo")
    finally:
        engine.dispose()
