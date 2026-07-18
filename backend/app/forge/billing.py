"""Integración con Stripe para la facturación de Forge.

El código es **inerte sin claves**: si falta ``STRIPE_SECRET_KEY`` los endpoints
de pago devuelven 503. Las claves se configuran como env vars en Render; nunca se
versionan. Stripe solo mueve el estado de la suscripción; el gating vive en
``plans.py``.
"""

from __future__ import annotations

import datetime
import json
import os

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ForgeSubscription
from .plans import PAID_PLANS

_PRICE_ENV = {"pro": "FORGE_STRIPE_PRICE_PRO", "team": "FORGE_STRIPE_PRICE_TEAM"}


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _require_stripe():
    key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code=503, detail="Facturación no configurada (falta STRIPE_SECRET_KEY)."
        )
    import stripe

    stripe.api_key = key
    return stripe


def create_checkout_url(user, plan: str) -> str:
    if plan not in PAID_PLANS:
        raise HTTPException(status_code=400, detail=f"El plan '{plan}' no es de pago.")
    price = os.getenv(_PRICE_ENV[plan], "").strip()
    if not price:
        raise HTTPException(
            status_code=503, detail=f"Precio del plan '{plan}' no configurado."
        )
    stripe = _require_stripe()
    base = "https://auditbrain-clientes.onrender.com/forge"
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price, "quantity": 1}],
        success_url=os.getenv("FORGE_BILLING_SUCCESS_URL", f"{base}?checkout=success"),
        cancel_url=os.getenv("FORGE_BILLING_CANCEL_URL", f"{base}?checkout=cancel"),
        client_reference_id=str(user.id),
        metadata={"forge_user_id": str(user.id), "forge_plan": plan},
    )
    return session.url


def _upsert(db: Session, user_id: int, plan: str, status: str, **stripe_ids) -> None:
    sub = db.execute(
        select(ForgeSubscription).where(ForgeSubscription.user_id == user_id)
    ).scalar_one_or_none()
    if sub is None:
        sub = ForgeSubscription(user_id=user_id)
        db.add(sub)
    sub.plan = plan
    sub.status = status
    if stripe_ids.get("customer_id"):
        sub.stripe_customer_id = stripe_ids["customer_id"]
    if stripe_ids.get("subscription_id"):
        sub.stripe_subscription_id = stripe_ids["subscription_id"]
    sub.updated_at = _utcnow()
    db.commit()


def handle_webhook(db: Session, payload: bytes, signature: str) -> dict:
    """Procesa un evento de Stripe. **Fail-closed**: sin firma verificable, rechaza.

    El endpoint no tiene auth (lo llama Stripe). Si aceptara payloads sin firmar,
    cualquiera que conozca la URL podría forjar un ``checkout.session.completed`` y
    activarse un plan de pago. Por eso:

    - Con ``STRIPE_WEBHOOK_SECRET`` (producción): se verifica la firma. Es el camino
      normal y el único seguro.
    - Sin él: se **rechaza con 400**, salvo que se pida explícitamente lo contrario
      con ``FORGE_STRIPE_WEBHOOK_ALLOW_UNSIGNED=true`` — un opt-in solo para
      dev/test que jamás debe existir en Render. `SECURITY.md §5.2` exige
      fail-closed; el antiguo `else: json.loads(payload)` era fail-open.
    """
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if secret:
        stripe = _require_stripe()
        try:
            event = stripe.Webhook.construct_event(payload, signature, secret)
        except Exception as exc:  # firma inválida / payload corrupto
            raise HTTPException(status_code=400, detail=f"Firma inválida: {exc}") from exc
    elif os.getenv("FORGE_STRIPE_WEBHOOK_ALLOW_UNSIGNED", "").strip().lower() == "true":
        # Opt-in EXPLÍCITO para dev/test. En producción no se pone esta variable.
        event = json.loads(payload)
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "Webhook sin verificar: falta STRIPE_WEBHOOK_SECRET. Se rechaza por "
                "seguridad (un payload sin firma podría ser forjado)."
            ),
        )

    etype = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    if etype == "checkout.session.completed":
        user_id = int((obj.get("metadata") or {}).get("forge_user_id") or obj.get("client_reference_id") or 0)
        plan = (obj.get("metadata") or {}).get("forge_plan", "pro")
        if user_id:
            _upsert(
                db, user_id, plan, "active",
                customer_id=obj.get("customer"),
                subscription_id=obj.get("subscription"),
            )
            return {"ok": True, "action": "activated", "user_id": user_id, "plan": plan}

    elif etype == "customer.subscription.deleted":
        sub_id = obj.get("id")
        if sub_id:
            row = db.execute(
                select(ForgeSubscription).where(
                    ForgeSubscription.stripe_subscription_id == sub_id
                )
            ).scalar_one_or_none()
            if row:
                row.plan = "free"
                row.status = "canceled"
                row.updated_at = _utcnow()
                db.commit()
                return {"ok": True, "action": "canceled", "user_id": row.user_id}

    return {"ok": True, "action": "ignored", "type": etype}
