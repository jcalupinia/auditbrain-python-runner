"""F2b.1 — La cadena de gobernanza en la BD: append-only real, identidad real.

Criterios del diseño F2b que se prueban aquí:
- **P4**  append-only a nivel de motor: un UPDATE/DELETE sobre ``forge_decisions``
  falla (trigger), y esto se prueba en CI sobre SQLite.
- **P12** borrar un usuario con decisiones se bloquea (409); la cadena queda intacta.
- Cadena: ``verify_chain`` detecta una fila con hash alterado.
"""

import uuid

import pytest
from sqlalchemy import text

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal, init_db
from backend.app.forge import governance_service as gov
from backend.app.forge.governance_service import ChainError
from backend.app.forge.models import ForgeDecision, ForgePlan


def _mk_user(db, role=Role.admin):
    email = f"gov-{uuid.uuid4().hex[:10]}@example.com"
    u = auth_service.create_user(db, email=email, password="Sup3rSecret!", role=role)
    return u


def _mk_plan(db, owner_id) -> ForgePlan:
    plan = ForgePlan(
        owner_user_id=owner_id,
        plan_id=f"plan-{uuid.uuid4().hex[:12]}",
        goal="objetivo de prueba",
        confidence="alta",
        model="fallback",
        ai_invoked=False,
        tasks=[{"id": "t1", "description": "hacer algo", "acceptance": "hecho"}],
    )
    db.add(plan)
    db.flush()
    return plan


# --- La cadena se escribe y verifica -------------------------------------------


def test_append_encadena_y_verify_pasa():
    init_db()
    db = SessionLocal()
    try:
        u = _mk_user(db)
        plan = _mk_plan(db, u.id)
        d1 = gov.append_decision(
            db, plan, actor_user_id=u.id, actor_label=u.email,
            action="approve", decision="approved", rationale="ok", task_id="t1",
            content_hash="abc123",
        )
        d2 = gov.append_decision(
            db, plan, actor_user_id=u.id, actor_label=u.email,
            action="reject", decision="rejected", rationale="faltan pruebas",
            task_id="t2",
        )
        db.commit()

        assert d1.seq == 1 and d2.seq == 2
        assert d2.prev_hash == d1.hash  # encadena
        cadena = gov.verify_chain(db, plan)  # no lanza
        assert [f.seq for f in cadena] == [1, 2]
        # Identidad REAL: la decisión guarda el user autenticado, no un texto libre.
        assert d1.actor_user_id == u.id
    finally:
        db.rollback()
        db.close()


def test_verify_detecta_una_fila_con_hash_alterado():
    """Como no se puede UPDATE (trigger), se inserta directamente una fila con un
    hash falso: ``verify_chain`` debe pillarlo."""
    init_db()
    db = SessionLocal()
    try:
        u = _mk_user(db)
        plan = _mk_plan(db, u.id)
        db.add(ForgeDecision(
            seq=1, plan_row_id=plan.id, organization_id=None,
            actor_user_id=u.id, actor_label=u.email, action="approve",
            task_id="t1", content_hash="", decision="approved", rationale="ok",
            ts="2026-07-18T00:00:00+00:00", prev_hash="0" * 64,
            hash="0" * 64,  # <- hash FALSO (no corresponde al contenido)
        ))
        db.commit()
        with pytest.raises(ChainError, match="alterada"):
            gov.verify_chain(db, plan)
    finally:
        db.rollback()
        db.close()


# --- P4: append-only a nivel de motor ------------------------------------------


def test_p4_no_se_puede_actualizar_una_decision():
    init_db()
    db = SessionLocal()
    try:
        u = _mk_user(db)
        plan = _mk_plan(db, u.id)
        d = gov.append_decision(
            db, plan, actor_user_id=u.id, actor_label=u.email,
            action="approve", decision="approved", rationale="ok", task_id="t1",
        )
        db.commit()
        # Intentar cambiar el veredicto a mano: el trigger lo aborta.
        with pytest.raises(Exception) as exc:
            db.execute(
                text("UPDATE forge_decisions SET decision='rejected' WHERE id=:i"),
                {"i": d.id},
            )
            db.commit()
        assert "append-only" in str(exc.value).lower()
    finally:
        db.rollback()
        db.close()


def test_p4_no_se_puede_borrar_una_decision():
    init_db()
    db = SessionLocal()
    try:
        u = _mk_user(db)
        plan = _mk_plan(db, u.id)
        d = gov.append_decision(
            db, plan, actor_user_id=u.id, actor_label=u.email,
            action="approve", decision="approved", rationale="ok", task_id="t1",
        )
        db.commit()
        with pytest.raises(Exception) as exc:
            db.execute(text("DELETE FROM forge_decisions WHERE id=:i"), {"i": d.id})
            db.commit()
        assert "append-only" in str(exc.value).lower()
    finally:
        db.rollback()
        db.close()


# --- P12: la baja de cuenta no borra la traza ----------------------------------


def test_p12_borrar_usuario_con_decisiones_se_bloquea():
    from fastapi import HTTPException

    init_db()
    db = SessionLocal()
    try:
        aprobador = _mk_user(db)
        plan = _mk_plan(db, aprobador.id)
        gov.append_decision(
            db, plan, actor_user_id=aprobador.id, actor_label=aprobador.email,
            action="approve", decision="approved", rationale="ok", task_id="t1",
        )
        db.commit()

        with pytest.raises(HTTPException) as exc:
            auth_service.delete_user_completely(db, user=aprobador)
        assert exc.value.status_code == 409
        db.rollback()

        # La cadena sigue intacta y el usuario sigue existiendo.
        assert gov.usuario_tiene_decisiones(db, aprobador.id) is True
        assert gov.verify_chain(db, plan)  # no lanza
    finally:
        db.rollback()
        db.close()


def test_borrar_usuario_sin_decisiones_sigue_funcionando():
    """El guard NO debe romper el borrado normal de una cuenta sin traza."""
    init_db()
    db = SessionLocal()
    try:
        u = _mk_user(db)
        uid = u.id
        auth_service.delete_user_completely(db, user=u)  # no lanza
        from backend.app.auth.models import User
        assert db.get(User, uid) is None
    finally:
        db.rollback()
        db.close()
