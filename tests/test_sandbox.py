"""Tests del sandbox Tier 0 (F1).

Verifica el scrub de entorno (la API Key NUNCA llega al subproceso),
los rlimits opt-in y la limpieza de jobs. No toca auditbrain_exec_runner.py.
"""

import asyncio
import os
import time

from backend.app.security import sandbox
from backend.app.services import python_runner_service


def test_build_child_env_scrubs_api_key(monkeypatch):
    monkeypatch.setenv("AUDITBRAIN_API_KEY", "supersecret")
    monkeypatch.setenv("DB_PASSWORD", "pw")
    monkeypatch.setenv("SOME_TOKEN", "t")
    monkeypatch.setenv("BENIGN_VAR", "ok")
    monkeypatch.setenv("PYTHONPATH", "/repo/root")

    env = sandbox.build_child_env(extra={"AUDITBRAIN_MAX_STREAM_CHARS": "123"})

    assert "AUDITBRAIN_API_KEY" not in env
    assert "DB_PASSWORD" not in env
    assert "SOME_TOKEN" not in env
    assert "PYTHONPATH" not in env  # raíz del proyecto fuera del hijo
    assert env.get("BENIGN_VAR") == "ok"
    assert env["AUDITBRAIN_MAX_STREAM_CHARS"] == "123"


def test_make_rlimit_preexec_optin(monkeypatch):
    for k in (
        "AUDITBRAIN_RLIMIT_AS_MB",
        "AUDITBRAIN_RLIMIT_CPU_SECONDS",
        "AUDITBRAIN_RLIMIT_FSIZE_MB",
        "AUDITBRAIN_RLIMIT_NPROC",
        "AUDITBRAIN_RLIMIT_NOFILE",
    ):
        monkeypatch.delenv(k, raising=False)
    assert sandbox.make_rlimit_preexec() is None  # sin knobs => sin límite

    monkeypatch.setenv("AUDITBRAIN_RLIMIT_AS_MB", "512")
    fn = sandbox.make_rlimit_preexec()
    assert callable(fn)


def test_purge_old_jobs(tmp_path):
    old = tmp_path / "auditbrain_job_old"
    new = tmp_path / "auditbrain_job_new"
    other = tmp_path / "keepme"
    for d in (old, new, other):
        d.mkdir()
    old_time = time.time() - 7200
    os.utime(old, (old_time, old_time))

    sandbox.purge_old_jobs(str(tmp_path), ttl_seconds=3600)

    assert not old.exists()       # job viejo borrado
    assert new.exists()           # job reciente intacto
    assert other.exists()         # no-job intacto


def test_api_key_never_reaches_executed_script(monkeypatch):
    """Integración real: corre el runner como subproceso y comprueba que
    el script NO puede leer AUDITBRAIN_API_KEY desde os.environ."""
    monkeypatch.setenv("AUDITBRAIN_API_KEY", "leak-me-if-you-can")

    script = (
        "import os\n"
        "result = {\n"
        "  'has_key': 'AUDITBRAIN_API_KEY' in os.environ,\n"
        "  'value': os.environ.get('AUDITBRAIN_API_KEY'),\n"
        "}\n"
    )
    out = asyncio.run(python_runner_service.run_python_code(script))

    assert out["result"]["has_key"] is False
    assert out["result"]["value"] is None
