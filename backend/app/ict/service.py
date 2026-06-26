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
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


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
    """Cierre/encerado de proyecto iniciado por el usuario.

    Borra:
      - El directorio de archivos físicos del proyecto en /tmp/ict/<session_id>/
        (F-101, F-104, F-103, Balance, y cualquier output generado).
      - La referencia ``uploaded_files`` de cada ICTAnexo (deja vacío).
      - La data extraída (``extracted_data``) y advertencias (``warnings``).
      - Marca status="expired" para que get_active_session no lo retorne.

    Conserva el registro de ICTSession (con razón social, RUC, ejercicio)
    en estado expired como histórico de auditoría; el cliente puede
    crear inmediatamente un nuevo proyecto en blanco vía
    create_session() porque get_active_session sólo devuelve los
    in_progress.
    """
    import shutil
    from pathlib import Path
    from backend.app.aud.obligaciones_fiscales import file_storage as _fs

    # 1) Borrar archivos físicos del disco
    try:
        ict_root = _fs._root() / "ict" / f"{session.id}"
        if ict_root.exists():
            shutil.rmtree(ict_root, ignore_errors=True)
    except Exception:
        # No bloqueamos el cierre si el FS falla; la DB sí queda consistente.
        pass

    # 2) Limpiar uploaded_files, extracted_data y warnings de cada anexo
    for anexo in session.anexos:
        anexo.uploaded_files = None
        anexo.extracted_data = None
        anexo.warnings = None
        anexo.status = "empty"
        db.add(anexo)

    # 3) Marcar la sesión como expired
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


def reparse_session_uploads(db: Session, *, session: ICTSession) -> dict:
    """Re-parsea TODOS los archivos guardados en disco para esta sesión y
    actualiza extracted_data en BD con la versión actual del parser.

    Cuando deployamos un parser mejorado (más casilleros, regex más
    robusto, etc.), los archivos ya subidos siguen con el extracted_data
    parseado por la versión vieja. Esta función:

      1. Recorre /tmp/ict/<session_id>/<anexo>/<slot>/*.pdf|.xlsx|.xml
      2. Re-corre el parser correspondiente sobre cada archivo
      3. Actualiza extracted_data del anexo con el resultado nuevo

    Devuelve {anexo_code: {slot, archivos_re_parseados, casilleros_antes,
    casilleros_despues}} para reportar al usuario qué cambió.
    """
    from backend.app.ict.router import SLOT_PARSERS

    report: dict = {}
    root = _ict_job_dir(session.id, "").parent  # /tmp/ict/<id>/
    if not root.exists():
        return {"error": "No hay archivos guardados para esta sesión",
                "session_id": session.id}

    for anexo in session.anexos:
        anexo_dir = root / anexo.anexo_code
        if not anexo_dir.exists():
            continue
        anexo_report: dict = {}
        anexo_extracted_before = anexo.extracted_data or {}
        new_extracted: dict = {}

        # Recorrer slots dentro de la carpeta del anexo
        for slot_dir in sorted(anexo_dir.iterdir()):
            if not slot_dir.is_dir():
                continue
            slot_name = slot_dir.name
            parser = SLOT_PARSERS.get(slot_name)
            if parser is None:
                continue

            archivos_re = 0
            casilleros_total = 0

            if slot_name in ("f104", "f103"):
                # Multi-mes: re-parsear cada archivo y acumular en monthly
                monthly: dict = {}
                for f in sorted(slot_dir.iterdir()):
                    if not f.is_file():
                        continue
                    try:
                        data = f.read_bytes()
                        parsed = parser(data)
                        periodo = parsed.get("periodo")
                        if periodo:
                            mes_key = str(periodo).split("/")[0].strip() \
                                      if "/" in str(periodo) else str(periodo).strip()
                            monthly[mes_key] = parsed
                            archivos_re += 1
                            casilleros_total += len(parsed.get("casilleros", {}))
                    except Exception:
                        import logging
                        logging.exception("Re-parse failed for %s", f)
                if monthly:
                    key = "f104_monthly" if slot_name == "f104" else "f103_monthly"
                    new_extracted[key] = monthly
            else:
                # Slot single-file: re-parsear el primer archivo
                files = [f for f in slot_dir.iterdir() if f.is_file()]
                if not files:
                    continue
                f = files[0]
                try:
                    data = f.read_bytes()
                    parsed = parser(data)
                    archivos_re = 1
                    if slot_name == "f101":
                        new_extracted["f101"] = parsed["casilleros"]
                        casilleros_total = len(parsed.get("casilleros", {}))
                    elif slot_name == "balance_mapeado":
                        new_extracted["balance_mapeado"] = parsed.get("cuentas", [])
                        # Propagar advertencias del parser al shared_context.
                        # Bug histórico 2026-06-07: cuentas con cas pero sin
                        # saldo se omitían silenciosamente. El parser ahora las
                        # reporta y aquí las propagamos para que VERIFICACIÓN A1
                        # las muestre como hallazgo al auditor.
                        new_extracted["balance_mapeado_advertencias"] = (
                            parsed.get("advertencias", [])
                        )
                        new_extracted["balance_mapeado_cuentas_sin_saldo"] = (
                            parsed.get("cuentas_sin_saldo", [])
                        )
                        casilleros_total = len(parsed.get("cuentas", []))
                    elif slot_name == "kardex":
                        new_extracted["kardex_items"] = parsed["items"]
                        casilleros_total = len(parsed.get("items", []))
                    elif slot_name == "facturacion":
                        new_extracted["facturacion"] = parsed
                    elif slot_name == "mayor_exentos":
                        new_extracted["mayor_exentos"] = parsed.get("movimientos", [])
                    elif slot_name == "mayor_no_deducibles":
                        new_extracted["mayor_no_deducibles"] = parsed.get("movimientos", [])
                    elif slot_name == "ats":
                        new_extracted["ats_pagos_exterior"] = parsed.get("pagos_exterior", [])
                    else:
                        new_extracted[slot_name] = parsed
                except Exception:
                    import logging
                    logging.exception("Re-parse failed for %s", f)

            anexo_report[slot_name] = {
                "archivos_re_parseados": archivos_re,
                "items_total": casilleros_total,
            }

        if new_extracted:
            # MERGE: preservar campos del extracted que NO vienen de archivos
            # (ej. campos manuales como exoneraciones, contratos_inversion).
            merged = dict(anexo_extracted_before)
            # Limpieza de clave zombie "f103" (single-file, bug previo al
            # commit 2026-06-05). Si la sesión tenía datos con esa clave
            # huérfana, la borramos antes del update para evitar confusión.
            merged.pop("f103", None)
            merged.update(new_extracted)
            # Asignación nueva para que SQLAlchemy detecte el cambio
            anexo.extracted_data = merged
            db.add(anexo)

            anexo_report["_summary"] = {
                "casilleros_antes": sum(len(v) if isinstance(v, (dict, list)) else 0
                                        for v in anexo_extracted_before.values()),
                "casilleros_despues": sum(len(v) if isinstance(v, (dict, list)) else 0
                                          for v in merged.values()),
            }

        if anexo_report:
            report[anexo.anexo_code] = anexo_report

    db.commit()
    db.refresh(session)
    return {"session_id": session.id, "anexos": report}


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

    # ATENCIÓN — SQLAlchemy con columnas JSON sólo detecta cambios por
    # ASIGNACIÓN, no por mutación interna del dict/lista existente. Si
    # hacemos ``anexo.uploaded_files[slot] = ...`` directamente sobre el
    # dict ya cargado, la siguiente db.commit() NO persiste la mutación
    # porque el atributo "no cambió" (misma referencia). Bug real
    # observado en producción: subir un 2º upload al mismo anexo
    # (p.ej. F-101 a A1 cuando ya tenía Balance Mapeado) devolvía
    # 200 OK pero la DB conservaba solo el 1er upload.
    #
    # Fix: construir SIEMPRE un dict NUEVO con ``{**existing, slot: meta}``
    # antes de asignar al campo, garantizando que SQLAlchemy lo detecte
    # como un valor distinto.
    existing_data = anexo.extracted_data or {}
    anexo.extracted_data = {**existing_data, **extracted_data}

    existing_warnings = list(anexo.warnings or [])
    anexo.warnings = existing_warnings + list(warnings or [])

    existing_files = dict(anexo.uploaded_files or {})
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


# Hojas que el archivo destinado al SRI OCULTA (no borra). Regla CLAUDE.md
# "Separación SRI vs Papel de trabajo del auditor".
#
# CAMBIO 2026-06-26 (decisión del cliente): estas hojas ya NO se eliminan del
# archivo SRI — se ocultan (`sheet_state="hidden"`). Motivo crítico: las
# fórmulas referenciales de A1..A9 apuntan a 'DATOS F-101'!Cxxx,
# 'DATOS BALANCE'!.., 'DATOS F-103'!.., 'DATOS F-104'!.. Borrar esas hojas
# rompería las fórmulas con #REF! al abrir el Excel. Ocultarlas deja el
# archivo limpio a la vista del cliente (solo INDICE + A1..A9 en las
# pestañas) y mantiene TODAS las fórmulas resolviendo. El papel de trabajo
# (_PAPEL_TRABAJO.xlsx) conserva todas las hojas visibles.
HIDDEN_SHEETS_FOR_SRI: tuple[str, ...] = (
    # Datos fuente (referenciadas por las fórmulas de A1..A9 → ocultar, jamás borrar)
    "DATOS F-101",
    "DATOS F-103",
    "DATOS F-104",
    "DATOS BALANCE",
    # Papeles internos del auditor (no parte del formato oficial del SRI)
    "VERIFICACIÓN A1",
    "TRAZABILIDAD",
    # NOTA 2026-06-17: AUDITORÍA DE ANEXOS, ARTEFACTO A1 y ARTEFACTO AUDITORIA
    # ya no se generan; si se reactivan, agregarlas aquí para ocultarlas.
)

# Alias retrocompatible: antes la constante se llamaba INTERNAL_SHEETS_FOR_SRI
# y listaba solo las hojas del auditor que se BORRABAN. Se mantiene el nombre
# apuntando a la nueva lista para no romper imports externos.
INTERNAL_SHEETS_FOR_SRI: tuple[str, ...] = HIDDEN_SHEETS_FOR_SRI


def _apply_sri_sheet_visibility(wb) -> None:
    """Oculta en `wb` (la copia destinada al SRI) las hojas de
    HIDDEN_SHEETS_FOR_SRI que existan, dejándolas PRESENTES —para que las
    fórmulas referenciales de A1..A9 sigan resolviendo— pero fuera de la
    vista del cliente. Garantiza además que la hoja activa sea una visible
    (INDICE de preferencia), porque Excel muestra un aviso si abre un libro
    cuya hoja activa está oculta."""
    for sheet_name in HIDDEN_SHEETS_FOR_SRI:
        if sheet_name in wb.sheetnames:
            wb[sheet_name].sheet_state = "hidden"
    _set_visible_active_sheet(wb)


def _set_visible_active_sheet(wb) -> None:
    """Apunta `wb.active` a una hoja visible (INDICE si existe; si no, la
    primera visible). Salvaguarda: nunca deja el libro con todas las hojas
    ocultas (Excel lo rechaza)."""
    visibles = [ws for ws in wb.worksheets if ws.sheet_state == "visible"]
    if not visibles:
        wb.worksheets[0].sheet_state = "visible"
        visibles = [wb.worksheets[0]]
    target = next(
        (ws for ws in visibles if ws.title.strip().upper() == "INDICE"),
        visibles[0],
    )
    wb.active = wb.worksheets.index(target)


def _get_interpretations(wb, contexto: dict) -> dict:
    """Llama al motor LLM (interpret_all_anexos) desde código sync.

    Devuelve dict {code: AnexoInterpretation} para los 9 anexos.
    Si la llamada falla por cualquier razón (no hay ANTHROPIC_API_KEY,
    timeout, etc.), devuelve fallbacks que marcan confianza=baja y
    requiere_revision_humana=True. El sistema sigue funcionando sin
    interpretación IA.
    """
    import asyncio
    import logging
    from backend.app.ict.audit.interpreter import (
        _fallback_interpretation,
        interpret_all_anexos,
    )
    codes = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
    try:
        return asyncio.run(interpret_all_anexos(wb, contexto))
    except RuntimeError as exc:
        # asyncio.run no se puede llamar dentro de un event loop ya activo.
        # Caso típico: tests pytest-asyncio. Crear nuevo loop en thread separado.
        if "running event loop" in str(exc).lower():
            import threading
            result: list = [None]
            def _runner():
                loop = asyncio.new_event_loop()
                try:
                    result[0] = loop.run_until_complete(
                        interpret_all_anexos(wb, contexto)
                    )
                finally:
                    loop.close()
            t = threading.Thread(target=_runner)
            t.start()
            t.join(timeout=120)
            if result[0] is not None:
                return result[0]
        logging.warning("interpret_all_anexos RuntimeError: %s — usando fallback", exc)
    except Exception as exc:
        logging.warning("interpret_all_anexos falló: %s — usando fallback", exc)
    return {c: _fallback_interpretation(c) for c in codes}


def generate_excel(db: Session, *, session: ICTSession) -> tuple[bytes, bytes]:
    """Generate the ICT Excel and split into (bytes_sri, bytes_papel_trabajo).

    Returns:
        (bytes_sri, bytes_papel_trabajo) where:
            bytes_sri              — Excel limpio, listo para cargar al SRI
                                     (sin VERIFICACIÓN A1 ni AUDITORÍA DE ANEXOS
                                     ni TRAZABILIDAD).
            bytes_papel_trabajo    — Excel completo con las hojas internas para
                                     uso del auditor.

    Builds a SHARED context across anexos: data uploaded for one anexo
    (e.g. balance_mapeado in A1) is accessible to other anexos that need it.
    """
    from io import BytesIO
    from backend.app.ict.fillers.base import load_template, reset_trace, write_trace_sheet
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

    # Inicia el trace log para esta generación. Cada safe_set() registrará
    # su escritura en el log y al final se vierte en la hoja "Trazabilidad".
    reset_trace()

    wb = load_template()
    session_data = {
        "razon_social": session.razon_social,
        "ruc": session.ruc,
        "ejercicio_fiscal": session.ejercicio_fiscal,
        "numero_adhesivo": session.numero_adhesivo or "",
    }

    # Build SHARED session context: merge extracted_data of ALL anexos
    # so each filler can see data uploaded to other anexos.
    # Strategy: keys that don't conflict (different anexos use different keys
    # like "f101", "balance_mapeado", "f104_monthly", "ats_pagos_exterior", etc.)
    # are merged as-is. If two anexos have the SAME key, the later anexo wins
    # (in practice this only matters if the same slot is uploaded twice, which
    # shouldn't happen in our flow).
    shared_context: dict = {}
    for a in session.anexos:
        if a.extracted_data:
            for k, v in a.extracted_data.items():
                shared_context[k] = v  # last write wins (anexos iteration order)

    # === Construir hojas de DATOS FUENTE ANTES de los fillers ===
    # Estas hojas son la fuente trazable de cada valor en los anexos.
    # Los fillers (a1..a9) usan f101_lookup/balance_lookup/etc. para
    # generar fórmulas como ='DATOS F-101'!C123 en lugar de valores literales.
    # IMPORTANTE: deben crearse ANTES porque los fillers necesitan el
    # mapeo casillero→row para sus fórmulas.
    f101_lookup: dict[str, int] = {}
    f103_lookup: dict = {}
    f104_lookup: dict = {}
    balance_lookup: list[int] = []
    try:
        from backend.app.ict.fillers.source_data_sheets import (
            build_f101_sheet, build_f103_sheet, build_f104_sheet, build_balance_sheet,
        )
        from backend.app.ict.cell_maps.a1 import A1_CASILLEROS_ORDERED
        casillero_names = dict(A1_CASILLEROS_ORDERED)
        f101_lookup = build_f101_sheet(
            wb, shared_context.get("f101", {}) or {}, casillero_names
        )
        f103_lookup = build_f103_sheet(wb, shared_context.get("f103_monthly", {}) or {})
        f104_lookup = build_f104_sheet(wb, shared_context.get("f104_monthly", {}) or {})
        balance_lookup = build_balance_sheet(wb, shared_context.get("balance_mapeado", []) or [])
    except Exception:
        import logging
        logging.exception("build_*_sheet falló para sesión %s", session.id)

    # Inyectar lookups en shared_context para que los fillers los puedan usar
    shared_context["_f101_lookup"] = f101_lookup
    shared_context["_f103_lookup"] = f103_lookup
    shared_context["_f104_lookup"] = f104_lookup
    shared_context["_balance_lookup"] = balance_lookup

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

    # Capturamos los warnings que devuelve cada filler para integrarlos
    # luego en la hoja AUDITORÍA DE ANEXOS (análisis automático).
    anexo_warnings_collected: dict[str, list[str]] = {}

    for anexo in session.anexos:
        filler = filler_map.get(anexo.anexo_code)
        if filler is None:
            continue
        if anexo.status == "empty":
            continue
        try:
            # Each filler gets: own anexo_data MERGED with shared context.
            # Own anexo_data takes precedence (last in **) for keys both have.
            merged_data = {**shared_context, **(anexo.extracted_data or {})}
            result = filler.fill(wb, session_data, merged_data)
            if isinstance(result, dict):
                w = result.get("warnings") or []
                if w:
                    anexo_warnings_collected[anexo.anexo_code] = w
        except Exception:
            import logging
            logging.exception("Filler %s failed for session %s", anexo.anexo_code, session.id)

    # Hoja "VERIFICACIÓN A1" con conciliación F-101 vs Balance vs A1.
    # Reporta cuántos casilleros y cuentas se trasladaron, cuáles
    # quedaron fuera y por qué. Esencial para auditoría.
    try:
        from backend.app.ict.fillers.verification import build_verification_sheet
        from backend.app.ict.fillers.base import get_trace
        build_verification_sheet(
            wb,
            f101=shared_context.get("f101", {}) or {},
            balance_mapeado=shared_context.get("balance_mapeado", []) or [],
            session_data=session_data,
            f103_monthly=shared_context.get("f103_monthly", {}) or {},
            f104_monthly=shared_context.get("f104_monthly", {}) or {},
            trace_log=get_trace(),
            # Lookups → fórmulas referenciales en la tabla CUADRATURA en
            # vez de valores literales (regla "auditor debe poder ver qué
            # celdas se están sumando").
            f101_lookup=shared_context.get("_f101_lookup") or {},
            balance_lookup=shared_context.get("_balance_lookup") or [],
            # Advertencias del parser de balance: cuentas con cas asignado
            # pero saldo vacío. Aparecen en VERIFICACIÓN A1 para que el
            # auditor las cotice con el cliente.
            balance_cuentas_sin_saldo=shared_context.get(
                "balance_mapeado_cuentas_sin_saldo", []
            ) or [],
        )
    except Exception:
        import logging
        logging.exception("build_verification_sheet falló para sesión %s", session.id)

    # NOTA 2026-06-17: hoja "AUDITORÍA DE ANEXOS" eliminada por decisión del
    # cliente — el dashboard ejecutivo de cuadre vive ahora en VERIFICACIÓN A1
    # y en las secciones CUADRE POR CASILLERO de DATOS BALANCE / DATOS F-101.
    # El filler `auditoria_anexos.build_auditoria_anexos_sheet` queda en el
    # repo por si se reactiva en el futuro, pero no se invoca.

    # Vuelca el trace log a una hoja "TRAZABILIDAD" al final del workbook.
    # Permite al auditor cruzar cualquier celda llenada con su origen
    # (F-101 página X, Balance Mapeado fila Y, F-103 mes ZZZZ-MM, etc).
    try:
        write_trace_sheet(wb)
    except Exception:
        import logging
        logging.exception("write_trace_sheet falló para sesión %s", session.id)

    # NOTA 2026-06-17: hojas "ARTEFACTO A1" y "ARTEFACTO AUDITORIA"
    # eliminadas por decisión del cliente. Vivían solo en el papel de trabajo
    # y replicaban con IA el cuadre del dashboard VERIFICACIÓN A1 + un análisis
    # por anexo. Como la información clave ya está en VERIFICACIÓN A1 y en
    # los bloques CUADRE de DATOS BALANCE/F-101, se quitaron para reducir
    # ruido y costos LLM. Los helpers `fill_verification_a1` y
    # `fill_auditoria_anexos` quedan en el repo por compatibilidad con tests
    # y por si se reactivan en el futuro, pero no se invocan desde el flujo.

    # Guardar workbook completo (con hojas internas) → bytes_papel_trabajo
    buf_papel = BytesIO()
    wb.save(buf_papel)
    buf_papel.seek(0)
    bytes_papel = buf_papel.read()

    # Reabrir y OCULTAR (no borrar) hojas internas/datos → bytes_sri (limpio
    # a la vista del cliente, pero con las fórmulas referenciales intactas).
    import openpyxl
    wb_sri = openpyxl.load_workbook(BytesIO(bytes_papel))
    _apply_sri_sheet_visibility(wb_sri)
    buf_sri = BytesIO()
    wb_sri.save(buf_sri)
    buf_sri.seek(0)
    bytes_sri = buf_sri.read()

    return bytes_sri, bytes_papel


def process_session(db: Session, *, session: ICTSession) -> dict:
    """Procesa la sesión ICT completa:

    1. Recolecta todos los uploads disponibles a través del shared_context
       (data subida a un anexo se ve desde cualquier otro).
    2. Para cada anexo evalúa si tiene sus inputs necesarios (según
       ANEXO_REQUIRED_SLOTS) y PROMUEVE su status a ready / partial / empty.
    3. Pre-genera el Excel ICT y lo cachea en disco para que el GET de
       descarga subsiguiente sea instantáneo.

    Retorna un JSON con resultados por anexo + flag excel_ready, para que
    el frontend pueda animar el progreso y luego ofrecer el botón de
    descarga sólo cuando el archivo esté listo.
    """
    from time import perf_counter
    from backend.app.ict.router import ANEXO_REQUIRED_SLOTS

    start = perf_counter()

    # 1) Recolectar slots subidos en toda la sesión (shared_context)
    all_uploads: set[str] = set()
    for a in session.anexos:
        all_uploads.update((a.uploaded_files or {}).keys())

    # 2) Recorrer los anexos en orden visual y actualizar status
    ANEXO_ORDER = ["INDICE", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
    anexo_map = {a.anexo_code: a for a in session.anexos}

    results = []
    for code in ANEXO_ORDER:
        anexo = anexo_map.get(code)
        if anexo is None:
            results.append({"anexo_code": code, "status": "missing", "warnings_count": 0})
            continue

        anexo_start = perf_counter()

        if code == "INDICE":
            # INDICE se auto-completa a partir de los datos del contribuyente
            # y del estado de los demás anexos. Siempre lo marcamos ready.
            anexo.status = "ready"
        else:
            required = ANEXO_REQUIRED_SLOTS.get(code, [])
            if not required:
                # Anexo sin requisitos formales: se promueve a partial.
                if anexo.status == "empty":
                    anexo.status = "partial"
            else:
                has_all = all(slot in all_uploads for slot in required)
                has_some = any(slot in all_uploads for slot in required)
                if has_all:
                    anexo.status = "ready"
                elif has_some:
                    # No degradar si ya estaba ready por upload directo
                    if anexo.status != "ready":
                        anexo.status = "partial"

        db.add(anexo)
        anexo_ms = int((perf_counter() - anexo_start) * 1000)
        results.append({
            "anexo_code": code,
            "status": anexo.status,
            "warnings_count": len(anexo.warnings or []),
            "ms": anexo_ms,
        })

    db.commit()

    # 3) Recompute INDICE para reflejar los nuevos status
    try:
        recompute_indice(db, session=session)
    except Exception:
        pass

    # 4) Pre-generar los dos Excels (SRI + papel de trabajo) y dejarlos en
    #    disco para descarga rápida desde los endpoints.
    excel_ready = False
    try:
        bytes_sri, bytes_papel = generate_excel(db, session=session)
        out_dir = _ict_job_dir(session.id, "_output")
        (out_dir / "ICT.xlsx").write_bytes(bytes_sri)            # backwards-compat
        (out_dir / "ICT_SRI.xlsx").write_bytes(bytes_sri)
        (out_dir / "ICT_PAPEL_TRABAJO.xlsx").write_bytes(bytes_papel)
        excel_ready = True
    except Exception:
        import logging
        logging.exception("Pre-generación Excel falló para sesión %s", session.id)

    total_ms = int((perf_counter() - start) * 1000)
    ready_count = sum(1 for r in results if r["status"] == "ready")
    return {
        "results": results,
        "total_ms": total_ms,
        "ready_count": ready_count,
        "total_anexos": len(ANEXO_ORDER),
        "excel_ready": excel_ready,
    }


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
        "f103": "f103_monthly",          # fix 2026-06-05: antes faltaba (bug multi-archivo)
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
    # Limpieza de claves zombies del bug histórico: sesiones que tenían
    # extracted_data["f103"] (single, mal) en vez de "f103_monthly".
    if slot_name == "f103" and "f103" in extracted:
        del extracted["f103"]
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
