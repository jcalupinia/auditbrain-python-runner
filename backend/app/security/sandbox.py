"""Tier 0 del sandbox de ejecución (F1).

Endurecimiento del subproceso que ejecuta código arbitrario de los GPTs,
SIN cambiar de plataforma (compatible con el runtime nativo de Render) y
SIN tocar ``auditbrain_exec_runner.py``.

Cubre:
- Scrub de entorno: el subproceso NO recibe ``AUDITBRAIN_API_KEY`` ni
  variables con pinta de secreto (KEY/SECRET/TOKEN/PASSWORD/...).
- Quita la raíz del proyecto del PYTHONPATH del hijo (evita que el script
  haga ``import backend.app.core.config`` y lea ``settings.API_KEY``).
- Límites de recursos opt-in vía ``resource.setrlimit`` (memoria, CPU,
  tamaño de archivo, nº de procesos, descriptores).
- Barrido best-effort de directorios de jobs antiguos.

Las constantes se resuelven desde el entorno aquí (no en config) para que
el flujo legacy (app.py) y el v1 compartan EXACTAMENTE el mismo
comportamiento sin duplicar configuración.
"""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path
from typing import Callable, Dict, Optional

# --- Scrub de entorno ---------------------------------------------------

# Nombres exactos que nunca deben llegar al subproceso.
_DENY_EXACT = {"AUDITBRAIN_API_KEY"}

# Patrón de variables con pinta de secreto (defensa a futuro: credenciales
# de BD/JWT que se añadan más adelante quedan filtradas por nombre).
_SECRET_PATTERN = re.compile(
    r"(API[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE|CREDENTIAL|"
    r"_PWD|AUTH[_-]?KEY)",
    re.IGNORECASE,
)

# Modo estricto opcional: en vez de denylist, allowlist mínima.
_STRICT_ENV = os.getenv("AUDITBRAIN_SANDBOX_STRICT_ENV", "0").strip() in {"1", "true", "yes"}
_STRICT_ALLOW = {
    "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "HOME", "TMPDIR",
    "PYTHONIOENCODING", "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE",
    "AUDITBRAIN_MAX_STREAM_CHARS",
}


def build_child_env(
    parent_env: Optional[Dict[str, str]] = None,
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Construye el entorno saneado para el subproceso de ejecución.

    - Modo por defecto (denylist): copia el entorno quitando secretos.
      Bajo riesgo de regresión para scripts existentes.
    - Modo estricto (``AUDITBRAIN_SANDBOX_STRICT_ENV=1``): allowlist mínima.
    """
    src = dict(os.environ if parent_env is None else parent_env)

    if _STRICT_ENV:
        child = {k: v for k, v in src.items() if k in _STRICT_ALLOW}
    else:
        child = {}
        for k, v in src.items():
            if k in _DENY_EXACT or _SECRET_PATTERN.search(k):
                continue
            child[k] = v

    # La raíz del proyecto NO debe estar en el PYTHONPATH del hijo: el
    # runner se invoca por ruta absoluta y solo usa stdlib; dejarla
    # permitiría ``import backend...`` y leer la API Key desde settings.
    child.pop("PYTHONPATH", None)

    child.setdefault("PYTHONIOENCODING", "utf-8")
    child.setdefault("PYTHONDONTWRITEBYTECODE", "1")

    if extra:
        child.update(extra)
    return child


# --- Límites de recursos (opt-in) --------------------------------------

def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def make_rlimit_preexec() -> Optional[Callable[[], None]]:
    """Devuelve un ``preexec_fn`` que aplica rlimits, o ``None``.

    Todos los límites son opt-in (0 = sin límite) para no romper cargas
    de trabajo existentes (pandas/numpy reservan mucha memoria). El
    operador los activa según el tamaño de la instancia. Valores
    recomendados documentados en docs/DEPLOYMENT.md.
    """
    if os.name != "posix":
        return None

    as_mb = _env_int("AUDITBRAIN_RLIMIT_AS_MB", 0)
    cpu_s = _env_int("AUDITBRAIN_RLIMIT_CPU_SECONDS", 0)
    fsize_mb = _env_int("AUDITBRAIN_RLIMIT_FSIZE_MB", 0)
    nproc = _env_int("AUDITBRAIN_RLIMIT_NPROC", 0)
    nofile = _env_int("AUDITBRAIN_RLIMIT_NOFILE", 0)

    if not any((as_mb, cpu_s, fsize_mb, nproc, nofile)):
        return None

    def _apply() -> None:
        import resource  # POSIX-only; import en el hijo

        def _set(res_id, soft: int) -> None:
            try:
                resource.setrlimit(res_id, (soft, soft))
            except (ValueError, OSError):
                pass

        if as_mb:
            _set(resource.RLIMIT_AS, as_mb * 1024 * 1024)
        if cpu_s:
            _set(resource.RLIMIT_CPU, cpu_s)
        if fsize_mb:
            _set(resource.RLIMIT_FSIZE, fsize_mb * 1024 * 1024)
        if nproc:
            _set(resource.RLIMIT_NPROC, nproc)
        if nofile:
            _set(resource.RLIMIT_NOFILE, nofile)

    return _apply


# --- Limpieza de jobs antiguos -----------------------------------------

JOB_TTL_SECONDS = _env_int("AUDITBRAIN_JOB_TTL_SECONDS", 3600)
_JOB_PREFIX = "auditbrain_job_"


def purge_old_jobs(base_dir: str, ttl_seconds: int = None) -> None:
    """Borra directorios de jobs más viejos que el TTL (best-effort).

    Se llama antes de crear un job nuevo: no toca el job en vuelo y evita
    que ``resultados/`` crezca sin límite. Nunca lanza excepción.
    """
    ttl = JOB_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    if ttl <= 0:
        return
    cutoff = time.time() - ttl
    try:
        base = Path(base_dir)
        if not base.is_dir():
            return
        for entry in base.iterdir():
            if not entry.is_dir() or not entry.name.startswith(_JOB_PREFIX):
                continue
            try:
                if entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)
            except OSError:
                continue
    except OSError:
        return
