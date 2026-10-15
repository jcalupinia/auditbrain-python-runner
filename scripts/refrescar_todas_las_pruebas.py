# -*- coding: utf-8 -*-
"""Refresca EN UNA SOLA PASADA todas las pruebas abiertas del Command Center a la
versión vigente de su herramienta.

Aplica la MISMA acción que el botón «Actualizar prueba» del frontend
(``servicio.aplicar_accion(..., "refrescar", ...)``): re-corre el motor con el
código ACTUAL del repo, con los MISMOS datos ya cargados, sin reiniciar el ciclo,
sin pedir volver a subir nada y sin cambiar el estado. Así, tras un deploy nuevo,
todas las pruebas ya ejecutadas pasan a la versión vigente del papel de una sola vez.

CUÁNDO CORRERLO
  - DESPUÉS de desplegar la versión nueva (backend) y con los auditores FUERA del
    sistema: es pesado (corre el motor + LibreOffice por cada prueba).

DÓNDE CORRERLO
  - En el SERVIDOR, con la base de PRODUCCIÓN. El script usa la MISMA cadena de
    conexión que la app: lee ``DATABASE_URL`` del entorno (no la inventa). Verifica
    con --dry-run que apunta a la base correcta antes de refrescar de verdad.

QUÉ PRUEBAS TOCA
  - Solo las que YA tienen resultado (``registro['run']``) y NO están APROBADAS
    (una versión aprobada es inmutable por NIA 230: se corrige con una versión nueva,
    nunca refrescándola). Las no ejecutadas y las aprobadas se SALTAN (se listan).

SEGURIDAD
  - Cada prueba va en su propio try/except: si una falla, se registra y sigue con
    las demás (no aborta la pasada). Al final imprime un resumen.
  - --dry-run no modifica nada: solo lista qué se refrescaría.

USO
  python scripts/refrescar_todas_las_pruebas.py --dry-run
  python scripts/refrescar_todas_las_pruebas.py                     # refresca de verdad
  python scripts/refrescar_todas_las_pruebas.py --processor nomina_beneficios
  python scripts/refrescar_todas_las_pruebas.py --ids 12,34,56
  python scripts/refrescar_todas_las_pruebas.py --limit 20
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# Permite correrlo como `python scripts/refrescar_todas_las_pruebas.py` desde la raíz del repo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ACTOR = "actualizacion-masiva@auditconsulting.ec"


def _cliente(p) -> str:
    try:
        return str(((p.registro or {}).get("engagement") or {}).get("client") or "")[:40]
    except Exception:  # noqa: BLE001
        return ""


def es_candidata(p, processor: str | None = None, ids: set[int] | None = None) -> bool:
    """¿Esta prueba se refresca? Ejecutada (tiene ``registro['run']``) y NO aprobada
    (las aprobadas son inmutables, NIA 230). Respeta los filtros opcionales."""
    if ids is not None and p.id not in ids:
        return False
    if processor and (p.definicion or {}).get("processor") != processor:
        return False
    if p.estado == "APROBADO":
        return False
    return bool((p.registro or {}).get("run"))


def _candidatas(db, Prueba, processor: str | None, ids: set[int] | None):
    """Pruebas candidatas (orden estable por id)."""
    from sqlalchemy import select

    filas = list(db.execute(select(Prueba).order_by(Prueba.id)).scalars())
    return [p for p in filas if es_candidata(p, processor, ids)]


def refrescar_todas(db, *, dry_run=False, processor=None, ids=None, limit=None, log=print) -> dict:
    """Refresca las pruebas candidatas. Devuelve un resumen {ok, error, total, detalle}."""
    from backend.app.aud.niif.ciclo import servicio
    from backend.app.aud.niif.ciclo.models import Prueba
    from backend.app.aud.niif.ciclo.reglas import ReglaIncumplida
    from backend.app.aud.niif.ciclo.servicio import Conflicto

    candidatas = _candidatas(db, Prueba, processor, ids)
    if limit:
        candidatas = candidatas[: int(limit)]
    total = len(candidatas)
    log(f"Candidatas (ejecutadas y no aprobadas): {total}"
        + (f" · filtro processor={processor}" if processor else "")
        + (" · DRY-RUN (no se modifica nada)" if dry_run else ""))
    res = {"ok": 0, "error": 0, "total": total, "detalle": []}
    for i, p in enumerate(candidatas, 1):
        etiqueta = f"[{i}/{total}] prueba #{p.id} · {(p.definicion or {}).get('processor') or p.origen} · {_cliente(p)} · {p.estado}"
        if dry_run:
            log(etiqueta + "  → se refrescaría")
            res["detalle"].append({"id": p.id, "estado": "dry-run"})
            continue
        t0 = time.time()
        try:
            # Relee la revisión vigente para evitar choques de versión, y aplica `refrescar`.
            db.refresh(p)
            servicio.aplicar_accion(db, p, "refrescar", p.revision, {}, ACTOR)
            dt = time.time() - t0
            log(etiqueta + f"  ✓ OK ({dt:.1f}s)")
            res["ok"] += 1
            res["detalle"].append({"id": p.id, "estado": "ok", "segundos": round(dt, 1)})
        except Conflicto as e:
            # Alguien tocó la prueba entre la lectura y el refresco: un reintento con la revisión fresca.
            try:
                db.refresh(p)
                servicio.aplicar_accion(db, p, "refrescar", p.revision, {}, ACTOR)
                log(etiqueta + "  ✓ OK (reintento)")
                res["ok"] += 1
                res["detalle"].append({"id": p.id, "estado": "ok-reintento"})
            except Exception as e2:  # noqa: BLE001
                db.rollback()
                log(etiqueta + f"  ✗ ERROR (conflicto): {e2}")
                res["error"] += 1
                res["detalle"].append({"id": p.id, "estado": "error", "msg": str(e2)})
        except ReglaIncumplida as e:
            db.rollback()
            log(etiqueta + f"  ↷ SALTADA: {e}")
            res["detalle"].append({"id": p.id, "estado": "saltada", "msg": str(e)})
        except Exception as e:  # noqa: BLE001
            db.rollback()
            log(etiqueta + f"  ✗ ERROR: {type(e).__name__}: {e}")
            res["error"] += 1
            res["detalle"].append({"id": p.id, "estado": "error", "msg": f"{type(e).__name__}: {e}"})
    log("")
    log(f"RESUMEN: {res['ok']} refrescadas · {res['error']} con error · "
        f"{total - res['ok'] - res['error']} saltadas/omitidas · {total} candidatas")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="Refresca en una sola pasada todas las pruebas abiertas a la versión vigente.")
    ap.add_argument("--dry-run", action="store_true", help="Lista qué se refrescaría, sin modificar nada.")
    ap.add_argument("--processor", default=None, help="Solo las pruebas de este procesador (p. ej. nomina_beneficios).")
    ap.add_argument("--ids", default=None, help="Solo estas pruebas (ids separados por coma).")
    ap.add_argument("--limit", type=int, default=None, help="Máximo de pruebas a refrescar.")
    args = ap.parse_args(argv)

    ids = {int(x) for x in args.ids.split(",") if x.strip()} if args.ids else None

    from backend.app.db.session import SessionLocal, engine, importar_modelos

    # Fuera de la app (uvicorn) hay que registrar TODOS los modelos para que SQLAlchemy resuelva
    # las llaves foráneas entre módulos (p. ej. aud_pruebas.project_id → projects); si no, el
    # refresco falla con NoReferencedTableError al tocar la relación.
    importar_modelos()

    print(f"Base de datos destino: {engine.url.render_as_string(hide_password=True)}")
    if not args.dry_run:
        print("⚠️  Modo REAL: se van a refrescar las pruebas. Ctrl+C en 5 s para abortar…")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("Abortado por el usuario."); return 1

    db = SessionLocal()
    try:
        res = refrescar_todas(db, dry_run=args.dry_run, processor=args.processor, ids=ids, limit=args.limit)
    finally:
        db.close()
    # Código de salida: 0 si no hubo errores, 1 si alguna prueba falló.
    return 1 if res["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
