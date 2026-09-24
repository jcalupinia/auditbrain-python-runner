"""Alta idempotente de las Audit Apps de ejemplo en el catálogo (AUT-002).

Se llama desde ``init_db`` en el arranque: deja el catálogo con al menos la app
de referencia AUD-INV-VNR publicada, para que ``GET /audit-apps`` no salga vacío
y el ejemplo esté disponible en cualquier entorno. Idempotente por
``(app_id, version)`` vía el registry: re-arrancar no duplica ni pisa.

Las apps de ejemplo se publican como catálogo global (sin owner ni tenant): son
plantillas de la firma, no una app subida por un cliente.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .examples import AUD_INV_VNR
from .manifest import AuditAppManifest
from .registry import AuditAppRegistry

#: Manifests de ejemplo que la firma publica de fábrica.
EJEMPLOS: tuple[dict, ...] = (AUD_INV_VNR,)


def seed_ejemplos(db: Session) -> int:
    """Publica los manifests de ejemplo que falten. Devuelve cuántos creó."""
    reg = AuditAppRegistry(db)
    creados = 0
    for data in EJEMPLOS:
        manifest = AuditAppManifest.from_dict(data).validate()
        _, creado = reg.register(manifest, owner_user_id=None, organization_id=None)
        creados += 1 if creado else 0
    if creados:
        db.commit()
    return creados
