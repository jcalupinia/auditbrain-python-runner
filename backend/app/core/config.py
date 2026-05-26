"""Configuración centralizada de la plataforma v1.

Espejo de las variables de entorno que ya usa el servicio legacy (app.py).
No se cambian nombres ni valores por defecto para mantener compatibilidad
total con el deployment actual de Render.
"""

import os
import sys
from pathlib import Path

# Raíz del repositorio (carpeta que contiene app.py y auditbrain_exec_runner.py).
# Se calcula desde este archivo: backend/app/core/config.py -> 3 niveles arriba.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings:
    """Settings de solo lectura, resueltos desde el entorno en import time."""

    APP_VERSION: str = "4.0.0"
    PLATFORM_API_PREFIX: str = "/api/v1"

    DOCUMENT_SERVICE: str = os.getenv(
        "DOCUMENT_SERVICE", "https://universal-creador-documentos.onrender.com"
    ).rstrip("/")

    RESULT_DIR: str = os.path.abspath("resultados")
    PROJECT_ROOT: Path = PROJECT_ROOT
    RUNNER_PATH: str = str(PROJECT_ROOT / "auditbrain_exec_runner.py")
    PYTHON_EXECUTABLE: str = sys.executable

    EXECUTION_TIMEOUT_SECONDS: int = int(os.getenv("EXECUTION_TIMEOUT_SECONDS", "300"))
    EXECUTION_CONCURRENCY: int = max(1, int(os.getenv("EXECUTION_CONCURRENCY", "1")))
    MAX_STD_STREAM_CHARS: int = int(os.getenv("AUDITBRAIN_MAX_STREAM_CHARS", "200000"))

    DEFAULT_RESPONSE_MODE: str = (
        os.getenv("AUDITBRAIN_RESPONSE_MODE", "compact").strip().lower() or "compact"
    )
    MAX_RESPONSE_TEXT_CHARS: int = int(
        os.getenv("AUDITBRAIN_MAX_RESPONSE_TEXT_CHARS", "4000")
    )

    # --- AUD.IMPUESTOS.OBLIGACIONES_FISCALES (efímero) ---
    AUD_OF_TMP_DIR: str = os.getenv(
        "AUD_OF_TMP_DIR", "/tmp/auditbrain/obligaciones_fiscales"
    )
    AUD_OF_JOB_TTL_MINUTES: int = int(os.getenv("AUD_OF_JOB_TTL_MINUTES", "60"))
    AUD_OF_POST_DOWNLOAD_TTL_MINUTES: int = int(
        os.getenv("AUD_OF_POST_DOWNLOAD_TTL_MINUTES", "5")
    )
    AUD_OF_MAX_FILE_MB: int = int(os.getenv("AUD_OF_MAX_FILE_MB", "20"))
    AUD_OF_MAX_TOTAL_MB: int = int(os.getenv("AUD_OF_MAX_TOTAL_MB", "100"))
    AUD_OF_CLEANUP_INTERVAL_SECONDS: int = int(
        os.getenv("AUD_OF_CLEANUP_INTERVAL_SECONDS", "300")
    )

    @property
    def aud_of_tmp_dir_path(self):
        from pathlib import Path

        p = Path(self.AUD_OF_TMP_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Auth mínima por API Key. Gated por entorno: si está vacío, la
    # autenticación queda DESACTIVADA (comportamiento legacy idéntico, los
    # GPTs existentes siguen funcionando sin cambios).
    API_KEY: str = os.getenv("AUDITBRAIN_API_KEY", "").strip()
    API_KEY_HEADER: str = "X-API-Key"

    @property
    def auth_enabled(self) -> bool:
        return bool(self.API_KEY)


settings = Settings()
