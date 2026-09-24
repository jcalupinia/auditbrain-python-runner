"""Registro versionado de Audit Apps (AUT-002) — SCAFFOLD.

El registro es el catálogo de qué Audit Apps existen y en qué versiones. Cumple
el rol de "Audit App Package registry" del benchmark (§P2.1, estilo SmartAnalyzer):
dar de alta un manifest, listarlos, y resolver la versión vigente o una versión
pinada. Es el equivalente para pruebas de auditoría de lo que ``ForgePlan`` +
``register_plan`` (idempotente por ``plan_id``) es para los planes de código.

**Estado: scaffold tipado.** La persistencia vive en PostgreSQL vía SQLAlchemy,
que no corre en este contenedor; los métodos declaran su firma/contrato y lanzan
``NotImplementedError``. La implementación a verde corre en el servidor, guiada por
``docs/superpowers/plans/`` (ver el plan de audit_apps cuando se escriba).

Contrato de persistencia previsto (tabla ``audit_apps`` a crear en el servidor,
patrón de ``ForgePlan``):

    id (pk) · app_id (str, index) · version (semver) · owner_user_id (FK, RESTRICT)
    · organization_id (FK, SET NULL, aislamiento multi-tenant) · name · manifest
    (JSON, el ``to_dict()`` completo) · manifest_hash (str, huella del contenido)
    · created_at · UniqueConstraint(app_id, version)

Reglas del registro (a implementar y probar en el servidor):

- **Alta idempotente por (app_id, version):** re-subir la MISMA versión con
  contenido idéntico devuelve la fila guardada; con contenido distinto es
  conflicto (409). No se pisa una versión publicada — son inmutables (§6).
- **Aislamiento multi-tenant (P3):** ``owner_user_id``/``organization_id`` salen de
  la sesión autenticada, nunca de un parámetro del cliente.
- **Validación en el alta:** ``manifest.validate()`` antes de escribir; un manifest
  inválido no entra al catálogo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .manifest import AuditAppManifest

if TYPE_CHECKING:  # evita importar SQLAlchemy/DB en un contenedor sin dependencias
    from sqlalchemy.orm import Session


class AuditAppRegistryError(RuntimeError):
    """Error de la operación de registro. El caller debe denegar la request."""


class AppNotFoundError(AuditAppRegistryError):
    """No existe la app (o la versión pedida) en el catálogo (404)."""


class AppVersionConflictError(AuditAppRegistryError):
    """Se re-subió una (app_id, version) ya publicada con contenido distinto (409).

    Una versión publicada es inmutable: para cambiar algo se sube una versión nueva.
    """


class AuditAppRegistry:
    """Fachada del catálogo de Audit Apps sobre la BD. SCAFFOLD.

    Se instancia con la ``Session`` de la request (como los servicios de Forge),
    para que el alta y sus efectos entren en una sola transacción. Ningún método
    hace ``commit`` — lo hace el router.
    """

    def __init__(self, db: "Session") -> None:
        self._db = db

    def register(
        self,
        manifest: AuditAppManifest,
        *,
        owner_user_id: int,
        organization_id: int | None,
    ) -> tuple[AuditAppManifest, bool]:
        """Da de alta un manifest en el catálogo. Idempotente por (app_id, version).

        Valida el manifest, calcula su huella y escribe la fila. Devuelve
        ``(manifest, creado)``: ``creado=False`` cuando ya existía idéntico (200).
        Lanza ``AppVersionConflictError`` si la versión existe con contenido
        distinto (409) y ``ManifestValidationError`` si el manifest no valida.

        ``owner_user_id``/``organization_id`` salen de la sesión, no del cliente.
        """
        raise NotImplementedError(
            "audit_apps.registry.register: implementar contra PostgreSQL en el servidor"
        )

    def get(self, app_id: str, version: str | None = None) -> AuditAppManifest:
        """Devuelve el manifest de una app. Sin ``version`` da la vigente (mayor
        semver publicada). Lanza ``AppNotFoundError`` si no existe."""
        raise NotImplementedError(
            "audit_apps.registry.get: implementar contra PostgreSQL en el servidor"
        )

    def versions(self, app_id: str) -> list[str]:
        """Lista las versiones publicadas de una app, ordenadas ascendente por
        semver. Lista vacía si la app no existe (no lanza)."""
        raise NotImplementedError(
            "audit_apps.registry.versions: implementar contra PostgreSQL en el servidor"
        )

    def list(
        self, *, organization_id: int | None = None
    ) -> list[tuple[str, str]]:
        """Cataloga las apps visibles como ``(app_id, version_vigente)``, una por
        app, filtradas por tenant. Base del ``GET /audit-apps`` de la UI."""
        raise NotImplementedError(
            "audit_apps.registry.list: implementar contra PostgreSQL en el servidor"
        )
