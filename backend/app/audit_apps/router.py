"""Rutas HTTP del catálogo de Audit Apps (AUT-002).

Expone el registry (publicar/listar/leer/versionar manifests) y una corrida
determinista del executor. Permisos: ``require_staff`` (admin y operadores),
igual que el resto del portal interno. ``owner_user_id``/``organization_id``
salen SIEMPRE de la sesión, nunca del cliente (aislamiento multi-tenant §P3).

La corrida (``/run``) usa el ``AuditAppExecutor`` con su allow-list determinista
(``motor.*`` / ``backend.app.aud.*``): el LLM no interviene en el cálculo. Los
pasos cuyo ``engine_ref`` aún no tiene adaptador ``fn(ctx)`` quedan en
``no_disponibles`` —el executor no fuerza resultados—, así que la corrida es
reproducible y honesta desde el primer día; el adaptador por-app es el paso
siguiente documentado.
"""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.auth.deps import require_staff
from backend.app.auth.models import User
from backend.app.db.session import get_db

from .executor import AuditAppExecutor, ExecutorError
from .manifest import AuditAppManifest, ManifestValidationError
from .registry import (
    AppNotFoundError,
    AppVersionConflictError,
    AuditAppRegistry,
    manifest_hash,
)

router = APIRouter(prefix="/audit-apps", tags=["audit-apps"])

#: Tope para incrustar una salida en base64 en la respuesta JSON de /run (8 MB de
#: bytes crudos). Por encima, se informa el hash/size y se marca truncado.
_MAX_OUTPUT_B64 = 8 * 1024 * 1024


class RegistrarIn(BaseModel):
    manifest: dict = Field(..., description="Manifest completo (AuditAppManifest.to_dict()).")


class CorridaIn(BaseModel):
    version: str | None = Field(default=None, description="Versión a correr; por defecto la vigente.")
    parameters: dict = Field(default_factory=dict)
    # Insumos como texto (utf-8) por id declarado; para archivos binarios grandes
    # se usará el Execution engine con carga por almacén (paso siguiente).
    inputs: dict[str, str] = Field(default_factory=dict)


def _manifest_desde(data: dict) -> AuditAppManifest:
    try:
        return AuditAppManifest.from_dict(data).validate()
    except ManifestValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"errores": list(e.problemas)})


@router.get("")
def catalogo(db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    """Apps visibles para el tenant, una por app con su versión vigente."""
    reg = AuditAppRegistry(db)
    apps = reg.list(organization_id=getattr(user, "organization_id", None))
    return {"apps": [{"app_id": a, "version": v} for a, v in apps]}


@router.post("", status_code=status.HTTP_201_CREATED)
def publicar(body: RegistrarIn, db: Session = Depends(get_db),
             user: User = Depends(require_staff)) -> dict:
    """Publica un manifest. Idempotente por (app_id, version); 409 si la versión
    ya existe con otro contenido; 400 si el manifest no valida."""
    manifest = _manifest_desde(body.manifest)
    reg = AuditAppRegistry(db)
    try:
        _, creado = reg.register(
            manifest,
            owner_user_id=getattr(user, "id", None),
            organization_id=getattr(user, "organization_id", None),
        )
    except AppVersionConflictError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    db.commit()
    return {"app_id": manifest.id, "version": manifest.version, "creado": creado,
            "manifest_hash": manifest_hash(manifest)}


@router.get("/{app_id}")
def leer(app_id: str, version: str | None = None, db: Session = Depends(get_db),
         user: User = Depends(require_staff)) -> dict:
    """Manifest de una app (vigente o la versión pedida) + sus versiones."""
    reg = AuditAppRegistry(db)
    try:
        manifest = reg.get(app_id, version)
    except AppNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"manifest": manifest.to_dict(), "versions": reg.versions(app_id)}


@router.get("/{app_id}/versions")
def versiones(app_id: str, db: Session = Depends(get_db),
              user: User = Depends(require_staff)) -> dict:
    return {"app_id": app_id, "versions": AuditAppRegistry(db).versions(app_id)}


@router.post("/{app_id}/run")
def correr(app_id: str, body: CorridaIn, db: Session = Depends(get_db),
           user: User = Depends(require_staff)) -> dict:
    """Corre la app contra el motor determinista y devuelve el trace de la corrida.

    Reproducible: congela hashes de insumos, snapshot de parámetros y hashes de
    salida. Los pasos sin adaptador quedan en ``no_disponibles`` (no se fuerzan).
    """
    reg = AuditAppRegistry(db)
    try:
        manifest = reg.get(app_id, body.version)
    except AppNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    inputs = {k: v.encode("utf-8") for k, v in body.inputs.items()}
    try:
        res = AuditAppExecutor().run(
            manifest, inputs=inputs, parameters=body.parameters, executed_by=user.email,
        )
    except (ExecutorError, ValueError) as e:
        # ValueError = validación del motor/adaptador (datos del cliente incompletos
        # o inválidos): es un 400, no un error del servidor.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Salidas materializadas en base64 (acotadas): el cliente recibe el papel
    # (Excel/HTML) y las excepciones directamente del /run. Se omite lo que exceda
    # el tope para no inflar la respuesta JSON.
    outputs = []
    for oid, contenido in res.outputs.items():
        entrada = {"id": oid, "size": len(contenido), "sha256": res.output_hashes.get(oid, "")}
        if len(contenido) <= _MAX_OUTPUT_B64:
            entrada["content_b64"] = base64.b64encode(contenido).decode("ascii")
        else:
            entrada["truncado"] = True  # descargar por un endpoint dedicado (paso siguiente)
        outputs.append(entrada)
    return {
        "app_id": res.app_id, "app_version": res.app_version,
        "engine_version": res.engine_version,
        "input_hashes": dict(res.input_hashes),
        "parameter_snapshot": dict(res.parameter_snapshot),
        "output_hashes": dict(res.output_hashes),
        "disponibles": list(res.disponibles),
        "no_disponibles": list(res.no_disponibles),
        "steps": [{"step_id": s.step_id, "produces": s.produces, "output_hash": s.output_hash}
                  for s in res.steps],
        "outputs": outputs,
        "acceptance": list(res.acceptance),
    }
