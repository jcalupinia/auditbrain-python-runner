"""Identidad y arranque seguro de un Preview Environment (Coolify o Render).

Un preview se reconoce por ``APP_ENV=preview``. Su IDENTIDAD es el número de PR y
el proveedor, y se lee de una ÚNICA fuente primaria, ``PREVIEW_PUBLIC_HOST`` (el
hostname público del backend que Coolify rellena en ``SERVICE_FQDN_BACKEND_10000``,
o ``RENDER_EXTERNAL_HOSTNAME`` en Render). Las fuentes de confirmación
(``COOLIFY_FQDN``, ``RENDER_EXTERNAL_HOSTNAME``) deben coincidir si existen.

Regla de fallo seguro: si la identidad está ausente, no coincide con el patrón o
es ambigua, o si la configuración apunta a producción (base, CORS, portal) o
falta el secreto JWT o la imagen no corresponde al commit esperado, el backend
**no arranca** (``preview_bootstrap`` termina el proceso con código 3). Nunca se
cae a «cualquier PR» ni a producción.

Fuera de preview (``APP_ENV`` distinto de "preview") nada de esto actúa y el
comportamiento es el de siempre.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from backend.app.core.hostnames import normalize_host, split_hosts

log = logging.getLogger("auditbrain")

# URL del portal de clientes en producción (default histórico de CLIENT_PORTAL_URL).
PRODUCTION_PORTAL_URL = "https://auditbrain-clientes.onrender.com"
# Centinela para enlaces de un preview sin identidad válida (RFC 6761, no resuelve).
PREVIEW_PORTAL_UNRESOLVED = "https://preview-portal-no-resuelto.invalid"

# Dominio base de los previews en Coolify (decisión del dueño, 2026-10-13).
COOLIFY_PREVIEW_DOMAIN = "preview.audit-ia.ec"
_DOM = re.escape(COOLIFY_PREVIEW_DOMAIN)
_COOLIFY_API_RE = re.compile(rf"^(\d{{1,7}})\.api\.{_DOM}$")
_RENDER_API_RE = re.compile(r"^auditbrain-python-runner-pr-(\d{1,7})\.onrender\.com$")
# Dominios de producción que un preview nunca debe usar como portal ni como origen CORS.
_PRODUCTION_HOSTS = {
    "consola.audit-ia.ec", "clientes.audit-ia.ec", "api.audit-ia.ec",
    "auditbrain-frontend.onrender.com", "auditbrain-clientes.onrender.com",
    "auditbrain-python-runner.onrender.com",
}

EXIT_CODE_CONFIG = 3


class PreviewConfigError(RuntimeError):
    """Configuración de preview inválida: el proceso no debe servir tráfico."""


def is_preview() -> bool:
    """True solo si ``APP_ENV`` vale exactamente "preview" (tras strip/lower)."""
    return os.getenv("APP_ENV", "production").strip().lower() == "preview"


def _pr_from_host(host: str) -> tuple[str, str] | None:
    m = _COOLIFY_API_RE.fullmatch(host)
    if m:
        return ("coolify", m.group(1))
    m = _RENDER_API_RE.fullmatch(host)
    if m:
        return ("render", m.group(1))
    return None


def preview_identity() -> tuple[str, str]:
    """(proveedor, número de PR) o ``PreviewConfigError``.

    Fuente primaria: ``PREVIEW_PUBLIC_HOST``. Fuentes de confirmación: ``COOLIFY_FQDN``
    y ``RENDER_EXTERNAL_HOSTNAME``. Toda fuente presente que coincida con un patrón
    debe dar la MISMA identidad; dos identidades distintas = ambigüedad = inválido.
    """
    primary = split_hosts(os.getenv("PREVIEW_PUBLIC_HOST"))
    if not primary:
        raise PreviewConfigError("PREVIEW_PUBLIC_HOST ausente o sin un hostname válido")
    found: set[tuple[str, str]] = set()
    for h in primary:
        r = _pr_from_host(h)
        if r:
            found.add(r)
    if not found:
        raise PreviewConfigError(f"PREVIEW_PUBLIC_HOST={primary!r} no coincide con el patrón de preview")
    for var in ("COOLIFY_FQDN", "RENDER_EXTERNAL_HOSTNAME"):
        for h in split_hosts(os.getenv(var)):
            r = _pr_from_host(h)
            if r:
                found.add(r)
    if len(found) != 1:
        raise PreviewConfigError(f"identidad de preview ambigua: {sorted(found)}")
    return next(iter(found))


def preview_pr_number() -> str | None:
    """Número de PR en preview; None fuera de preview. Propaga PreviewConfigError."""
    if not is_preview():
        return None
    return preview_identity()[1]


def preview_provider() -> str | None:
    """Proveedor del preview ("coolify" o "render") sin lanzar excepciones; None fuera de preview
    o si la identidad es inválida (en ese caso ``preview_bootstrap`` ya habrá detenido el arranque)."""
    if not is_preview():
        return None
    try:
        return preview_identity()[0]
    except PreviewConfigError:
        return None


def cors_origin_regex_for(info: dict) -> str | None:
    """Regex de orígenes CORS anclado al PR del preview; None fuera de preview.

    Sin fallback: solo los frontends de ESE PR (Coolify y, mientras conviva, Render).
    Starlette aplica ``fullmatch`` sobre el ``Origin`` recibido; se exige ``https``
    y ningún puerto.
    """
    if not info.get("preview"):
        return None
    pr = re.escape(str(info["pr"]))
    coolify = rf"https://{pr}\.(?:consola|clientes)\.{_DOM}"
    render = rf"https://auditbrain-(?:frontend|clientes)-pr-{pr}\.onrender\.com"
    return rf"^(?:{coolify}|{render})$"


def client_portal_url() -> str:
    """URL base del portal de clientes para enlaces y redirecciones.

    Producción / dev: ``CLIENT_PORTAL_URL`` o el default histórico. Preview: el
    portal del MISMO PR; ante identidad inválida (no debería ocurrir porque el
    arranque la exige) devuelve el centinela y registra el error.
    """
    if not is_preview():
        return os.getenv("CLIENT_PORTAL_URL", PRODUCTION_PORTAL_URL)
    try:
        provider, pr = preview_identity()
    except PreviewConfigError as e:
        log.error("PREVIEW: portal sin identidad válida (%s); se usa el centinela", e)
        return PREVIEW_PORTAL_UNRESOLVED
    if provider == "coolify":
        return f"https://{pr}.clientes.{COOLIFY_PREVIEW_DOMAIN}"
    return f"https://auditbrain-clientes-pr-{pr}.onrender.com"


# --------------------------------------------------------------------------------------
# Comprobaciones de arranque (fallo seguro)
# --------------------------------------------------------------------------------------
def _check_database_url() -> None:
    url = os.getenv("DATABASE_URL", "")
    host = normalize_host(urlsplit(url).hostname or "") if url else None
    if host != "db":
        raise PreviewConfigError(
            f"DATABASE_URL de un preview debe apuntar al servicio interno 'db' (host={host!r})")


def _check_no_production_targets() -> None:
    for h in split_hosts(os.getenv("CORS_ALLOW_ORIGINS")):
        if h in _PRODUCTION_HOSTS:
            raise PreviewConfigError(f"CORS_ALLOW_ORIGINS contiene un origen de producción ({h})")
    portal = normalize_host(os.getenv("CLIENT_PORTAL_URL"))
    if portal in _PRODUCTION_HOSTS:
        raise PreviewConfigError(f"CLIENT_PORTAL_URL apunta a producción ({portal})")


def _check_secrets_dir() -> Path:
    d = Path(os.getenv("PREVIEW_SECRETS_DIR", "/run/secrets"))
    f = d / "jwt_secret"
    try:
        value = f.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise PreviewConfigError(f"no se puede leer el secreto JWT del preview en {f}: {e.__class__.__name__}") from e
    if len(value) < 32:
        raise PreviewConfigError("el secreto JWT del preview es demasiado corto")
    return d


_SHA40 = re.compile(r"[0-9a-f]{40}")


def _check_image_commit(provider: str) -> str:
    """La imagen desplegada debe ser la del commit esperado.

    ``BUILD_COMMIT`` lo fija la imagen al construirse (ARG GIT_SHA) y ``PREVIEW_EXPECTED_IMAGE_TAG``
    llega del Compose como ``sha-${SOURCE_COMMIT}``. En **Coolify** la identidad por commit es
    estricta (F1): ``SOURCE_COMMIT`` (el head del PR que Coolify escribe en el .env con el que
    interpola las imágenes) debe ser un SHA de 40 caracteres idéntico a ``BUILD_COMMIT``; ni vacío
    ni "unknown". En **Render** ``SOURCE_COMMIT`` es opcional (compatibilidad con los previews
    existentes), pero si llega y no es "unknown" debe coincidir.
    """
    commit = (os.getenv("BUILD_COMMIT") or "").strip().lower()
    tag = (os.getenv("PREVIEW_EXPECTED_IMAGE_TAG") or "").strip().lower()
    if not _SHA40.fullmatch(commit):
        raise PreviewConfigError("BUILD_COMMIT ausente o inválido en la imagen del backend")
    if tag != f"sha-{commit}":
        raise PreviewConfigError(
            f"la etiqueta esperada ({tag or 'ausente'}) no corresponde al commit de la imagen (sha-{commit[:12]}…)")
    source = (os.getenv("SOURCE_COMMIT") or "").strip().lower()
    if provider == "coolify":
        if not _SHA40.fullmatch(source):
            raise PreviewConfigError(
                "SOURCE_COMMIT ausente o inválido: Coolify debe entregar el commit del PR (SHA de 40 caracteres)")
        if source != commit:
            raise PreviewConfigError(
                f"SOURCE_COMMIT ({source[:12]}…) no coincide con el commit de la imagen (sha-{commit[:12]}…)")
    elif source and source != "unknown" and source != commit:
        raise PreviewConfigError("SOURCE_COMMIT no coincide con el commit de la imagen")
    return commit


# Credenciales que un preview de Coolify NUNCA debe recibir heredadas del entorno de la aplicación
# base ni de variables compartidas (las variables de la app base que el preview no define se heredan).
# Justificación: el JWT se firma solo con el volumen del PR; el resto son credenciales de proveedores
# externos (IA, correo, pagos, Canva, OCR, puentes) o apuntan a servicios de producción, y un preview
# no tiene ningún uso legítimo para ellas. Solo se registran los NOMBRES, nunca los valores.
FORBIDDEN_INHERITED_IN_COOLIFY_PREVIEW = (
    "AUDITBRAIN_JWT_SECRET",
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "LOCAL_LLM_API_KEY", "LOCAL_LLM_BASE_URL",
    "RESEND_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "CANVA_MCP_OAUTH_TOKEN",
    "GOOGLE_APPLICATION_CREDENTIALS_JSON", "COMFY_BRIDGE_KEY", "COMFY_BRIDGE_URL",
    "MOTOR_TOKEN_SECRET", "MOTOR_ANALITICO_URL",
)
# Identificador del contenedor de la base productiva en Coolify; ningún valor del entorno debe citarlo.
_PRODUCTION_DB_MARKERS = ("z4wy8ngriiesg6z20n7ftcnj",)
# Variables cuyo valor legítimamente contiene el dominio base de previews (no se escanean).
_IDENTITY_VARS = {"PREVIEW_PUBLIC_HOST", "COOLIFY_FQDN", "COOLIFY_URL", "RENDER_EXTERNAL_HOSTNAME"}


def _check_no_inherited_secrets(provider: str) -> None:
    """Fallo cerrado ante credenciales productivas heredadas (solo Coolify; Render usa sus propias).

    Se ejecuta ANTES de cualquier otra comprobación para que un preview mal configurado no llegue a
    usar esas variables. No imprime valores: solo los nombres de las variables prohibidas presentes.
    """
    if provider != "coolify":
        return
    presentes = [k for k in FORBIDDEN_INHERITED_IN_COOLIFY_PREVIEW if (os.getenv(k) or "").strip()]
    if presentes:
        raise PreviewConfigError(
            "credenciales heredadas del entorno en un preview de Coolify: " + ", ".join(presentes))
    sospechosas = []
    for k, v in os.environ.items():
        if k in _IDENTITY_VARS or k.startswith("SERVICE_FQDN_") or k.startswith("SERVICE_URL_"):
            continue
        low = v.lower()
        if any(h in low for h in _PRODUCTION_HOSTS) or any(m in low for m in _PRODUCTION_DB_MARKERS):
            sospechosas.append(k)
    if sospechosas:
        raise PreviewConfigError("variables que apuntan a producción en un preview de Coolify: " + ", ".join(sorted(sospechosas)))


def _check_runtime_credentials(provider: str) -> None:
    """Las credenciales de prueba del PR (exportadas por el command desde /run/secrets) no pueden faltar.

    Con ``AUDITBRAIN_API_KEY`` vacía el backend desactivaría la autenticación por API key, y sin
    contraseña no se crearía el administrador de prueba. Solo Coolify (Render fija las suyas).
    """
    if provider != "coolify":
        return
    faltan = [k for k in ("AUDITBRAIN_API_KEY", "AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD") if not (os.getenv(k) or "").strip()]
    if faltan:
        raise PreviewConfigError("credenciales de prueba del preview ausentes o vacías: " + ", ".join(faltan))


def preview_bootstrap(*, exit_on_error: bool = True) -> dict:
    """Valida la configuración del preview al importar la aplicación.

    Fuera de preview devuelve ``{"preview": False}`` sin tocar nada. En preview, ante
    cualquier incumplimiento registra el motivo y termina el proceso (código 3) o,
    con ``exit_on_error=False``, lanza ``PreviewConfigError``.
    """
    if not is_preview():
        return {"preview": False}
    try:
        provider, pr = preview_identity()
        _check_no_inherited_secrets(provider)   # primero: nada heredado de producción (F1, S-06)
        _check_database_url()
        _check_no_production_targets()
        _check_secrets_dir()
        _check_runtime_credentials(provider)    # API key y contraseña de prueba presentes (F1, S-05)
        commit = _check_image_commit(provider)  # BUILD_COMMIT == SOURCE_COMMIT == etiqueta (F1, C-01)
    except PreviewConfigError as e:
        log.critical("PREVIEW: configuración inválida: %s. El servicio no arranca.", e)
        if exit_on_error:
            raise SystemExit(EXIT_CODE_CONFIG) from e
        raise
    info = {"preview": True, "provider": provider, "pr": pr, "config": "ok", "commit": commit}
    log.info("PREVIEW: identidad válida proveedor=%s pr=%s commit=%s", provider, pr, commit[:12])
    return info


def preview_health_info() -> dict:
    """Bloque ``preview`` de /api/v1/health, sin lanzar excepciones."""
    if not is_preview():
        return {"active": False}
    try:
        provider, pr = preview_identity()
        return {"active": True, "provider": provider, "pr": pr, "config": "ok"}
    except PreviewConfigError as e:
        return {"active": True, "provider": None, "pr": None, "config": "invalid", "detail": str(e)}
