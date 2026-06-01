"""Service layer for ICT 2025: sessions, anexos, Excel generation."""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import User
from backend.app.ict.models import ICTAnexo, ICTSession

SESSION_TTL_DAYS = 90
ANEXOS_CATALOG = ["INDICE", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]


def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _expires_at(from_dt: datetime.datetime | None = None) -> datetime.datetime:
    base = from_dt or _now()
    return base + datetime.timedelta(days=SESSION_TTL_DAYS)


def create_session(
    db: Session,
    *,
    user: User,
    ejercicio_fiscal: str,
    ruc: str,
    razon_social: str,
    numero_adhesivo: str | None,
) -> ICTSession:
    """Create new ICT session or return existing in_progress (idempotent)."""
    existing = get_active_session(db, user=user)
    if existing is not None:
        return existing

    now = _now()
    session = ICTSession(
        user_id=user.id,
        ejercicio_fiscal=ejercicio_fiscal,
        ruc=ruc,
        razon_social=razon_social,
        numero_adhesivo=numero_adhesivo,
        status="in_progress",
        created_at=now,
        last_activity_at=now,
        expires_at=_expires_at(now),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    for anexo_code in ANEXOS_CATALOG:
        db.add(ICTAnexo(
            session_id=session.id,
            anexo_code=anexo_code,
            status="empty",
            extracted_data=None,
            warnings=None,
            uploaded_files=None,
            last_updated_at=now,
        ))
    db.commit()
    db.refresh(session)
    return session


def get_active_session(db: Session, *, user: User) -> ICTSession | None:
    """Return user's in_progress session or None."""
    return db.execute(
        select(ICTSession)
        .where(ICTSession.user_id == user.id, ICTSession.status == "in_progress")
        .order_by(ICTSession.created_at.desc())
    ).scalars().first()


def get_session(db: Session, *, session_id: int, user: User) -> ICTSession:
    """Get session by id, validates ownership. Raises PermissionError if not owner."""
    s = db.get(ICTSession, session_id)
    if s is None or s.user_id != user.id:
        raise PermissionError("Session not found or not owned by user")
    return s


def touch_session(db: Session, *, session: ICTSession) -> None:
    """Update last_activity_at + extend expires_at."""
    now = _now()
    session.last_activity_at = now
    session.expires_at = _expires_at(now)
    db.add(session)
    db.commit()


def update_session(
    db: Session,
    *,
    session: ICTSession,
    ruc: str | None = None,
    razon_social: str | None = None,
    numero_adhesivo: str | None = None,
) -> ICTSession:
    """Update session contribuyente data and touch activity."""
    if ruc is not None:
        session.ruc = ruc
    if razon_social is not None:
        session.razon_social = razon_social
    if numero_adhesivo is not None:
        session.numero_adhesivo = numero_adhesivo
    now = _now()
    session.last_activity_at = now
    session.expires_at = _expires_at(now)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def expire_session(db: Session, *, session: ICTSession) -> None:
    """Mark session as expired (user-initiated close)."""
    session.status = "expired"
    db.add(session)
    db.commit()


from pathlib import Path
from backend.app.aud.obligaciones_fiscales import file_storage


def _ict_job_dir(session_id: int, anexo_code: str) -> Path:
    """Returns the /tmp dir for an ICT anexo (under OF's tmp root for cleanup reuse)."""
    of_dir = file_storage._root() / "ict" / f"{session_id}" / anexo_code
    of_dir.mkdir(parents=True, exist_ok=True)
    return of_dir


def save_uploaded_file(
    *,
    session_id: int,
    anexo_code: str,
    slot_name: str,
    filename: str,
    data: bytes,
) -> Path:
    """Persist a raw uploaded file under /tmp/ict/<session>/<anexo>/<slot>/."""
    import re
    safe_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)[:200] or "file"
    safe_slot = re.sub(r"[^a-zA-Z0-9._-]", "_", slot_name)[:64] or "slot"
    slot_dir = _ict_job_dir(session_id, anexo_code) / safe_slot
    slot_dir.mkdir(parents=True, exist_ok=True)
    target = slot_dir / safe_filename
    target.write_bytes(data)
    return target


def update_anexo_data(
    db: Session,
    *,
    session: ICTSession,
    anexo_code: str,
    extracted_data: dict,
    warnings: list[str],
    uploaded_file_meta: dict,
    new_status: str,
) -> ICTAnexo:
    """Merge extracted data into the anexo, append warnings, set status.

    extracted_data is MERGED (top-level keys overwrite). warnings is APPENDED.
    uploaded_file_meta is keyed by slot_name and merged into uploaded_files.
    """
    anexo = next((a for a in session.anexos if a.anexo_code == anexo_code), None)
    if anexo is None:
        raise ValueError(f"Anexo {anexo_code} not in session")

    existing_data = anexo.extracted_data or {}
    merged = {**existing_data, **extracted_data}
    anexo.extracted_data = merged

    existing_warnings = anexo.warnings or []
    anexo.warnings = existing_warnings + (warnings or [])

    existing_files = anexo.uploaded_files or {}
    slot = uploaded_file_meta.get("slot")
    if slot:
        existing_files[slot] = uploaded_file_meta
    anexo.uploaded_files = existing_files

    anexo.status = new_status
    anexo.last_updated_at = _now()

    touch_session(db, session=session)

    db.add(anexo)
    db.commit()
    db.refresh(anexo)
    return anexo


def recompute_indice(db: Session, *, session: ICTSession) -> ICTAnexo:
    """Rebuild INDICE.extracted_data['aplica'] from other anexos' statuses.

    Rule: SI if anexo.status in ('partial', 'ready'); NO otherwise.
    INDICE itself is always 'ready' after recompute (it has no inputs).
    """
    aplica: dict[str, str] = {}
    for a in session.anexos:
        if a.anexo_code == "INDICE":
            continue
        aplica[a.anexo_code] = "SI" if a.status in ("partial", "ready") else "NO"

    indice = next(a for a in session.anexos if a.anexo_code == "INDICE")
    indice.extracted_data = {"aplica": aplica}
    indice.status = "ready"
    indice.last_updated_at = _now()
    db.add(indice)
    db.commit()
    db.refresh(indice)
    return indice


def generate_excel(db: Session, *, session: ICTSession) -> bytes:
    """Generate the ICT Excel by loading template + applying all fillers."""
    from io import BytesIO
    from backend.app.ict.fillers.base import load_template
    from backend.app.ict.fillers.indice import IndiceFiller
    from backend.app.ict.fillers.a1_mapeo import A1Filler
    from backend.app.ict.fillers.a2_ingresos import A2Filler
    from backend.app.ict.fillers.a3_costos_gastos import A3Filler
    from backend.app.ict.fillers.a4_conciliacion_ingresos import A4Filler
    from backend.app.ict.fillers.a5_conciliacion_costos import A5Filler
    from backend.app.ict.fillers.a6_beneficios import A6Filler
    from backend.app.ict.fillers.a7_credito import A7Filler
    from backend.app.ict.fillers.a8_comercio_exterior import A8Filler
    from backend.app.ict.fillers.a9_inventarios import A9Filler

    wb = load_template()
    session_data = {
        "razon_social": session.razon_social,
        "ruc": session.ruc,
        "ejercicio_fiscal": session.ejercicio_fiscal,
        "numero_adhesivo": session.numero_adhesivo or "",
    }

    filler_map = {
        "INDICE": IndiceFiller(),
        "A1": A1Filler(),
        "A2": A2Filler(),
        "A3": A3Filler(),
        "A4": A4Filler(),
        "A5": A5Filler(),
        "A6": A6Filler(),
        "A7": A7Filler(),
        "A8": A8Filler(),
        "A9": A9Filler(),
    }

    for anexo in session.anexos:
        filler = filler_map.get(anexo.anexo_code)
        if filler is None:
            continue
        if anexo.status == "empty":
            continue
        try:
            filler.fill(wb, session_data, anexo.extracted_data or {})
        except Exception:
            import logging
            logging.exception("Filler %s failed for session %s", anexo.anexo_code, session.id)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def reset_anexo_slot(
    db: Session, *, session: ICTSession, anexo_code: str, slot_name: str
) -> ICTAnexo:
    """Remove a slot's data + metadata from an anexo, recalc status."""
    anexo = next((a for a in session.anexos if a.anexo_code == anexo_code), None)
    if anexo is None:
        raise ValueError(f"Anexo {anexo_code} not found")

    files = anexo.uploaded_files or {}
    if slot_name in files:
        del files[slot_name]
    anexo.uploaded_files = files

    extracted = anexo.extracted_data or {}
    key_map = {
        "f101": "f101",
        "balance_mapeado": "balance_mapeado",
        "kardex": "kardex_items",
        "f104": "f104_monthly",
        "facturacion": "facturacion",
        "mayor_exentos": "mayor_exentos",
        "mayor_no_deducibles": "mayor_no_deducibles",
        "f101_multiyear": "f101_multiyear",
        "f108_multiyear": "f108_multiyear",
        "ats": "ats_pagos_exterior",
    }
    main_key = key_map.get(slot_name, slot_name)
    if main_key in extracted:
        del extracted[main_key]
    anexo.extracted_data = extracted

    anexo.status = "empty" if not files else "partial"
    anexo.last_updated_at = _now()
    db.add(anexo)
    db.commit()
    db.refresh(anexo)
    return anexo


def cleanup_ict_orphan_files(max_age_hours: int = 24) -> int:
    """Delete ICT files older than max_age_hours.
    The extracted_data in DB is preserved (only the raw files go).
    """
    import time
    from backend.app.aud.obligaciones_fiscales import file_storage as of_storage

    root = of_storage._root() / "ict"
    if not root.exists():
        return 0
    cutoff = time.time() - (max_age_hours * 3600)
    deleted = 0
    for session_dir in root.iterdir():
        if not session_dir.is_dir():
            continue
        for anexo_dir in session_dir.iterdir():
            if not anexo_dir.is_dir():
                continue
            for slot_dir in anexo_dir.iterdir():
                if not slot_dir.is_dir():
                    continue
                for f in slot_dir.iterdir():
                    if f.is_file() and f.stat().st_mtime < cutoff:
                        try:
                            f.unlink()
                            deleted += 1
                        except OSError:
                            pass
    return deleted
