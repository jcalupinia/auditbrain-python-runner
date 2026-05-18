"""Encapsula la ejecución de código Python como módulo interno de la plataforma.

El motor real sigue siendo ``auditbrain_exec_runner.py`` (intocado): este
service solo orquesta el subproceso. La lógica replica la de app.py de forma
deliberada durante esta fase de migración; la consolidación (que el endpoint
legacy delegue aquí) está planificada en docs/MIGRATION_PLAN.md.
"""

import asyncio
import json
import os
import tempfile

from backend.app.core.config import settings

_EXECUTION_SEMAPHORE = asyncio.Semaphore(settings.EXECUTION_CONCURRENCY)


def _truncate_stream(value: str) -> str:
    if len(value) <= settings.MAX_STD_STREAM_CHARS:
        return value
    return value[: settings.MAX_STD_STREAM_CHARS] + "\n...[truncated]"


def _compact_text(value, max_chars: int = None):
    if not isinstance(value, str):
        return value
    limit = settings.MAX_RESPONSE_TEXT_CHARS if max_chars is None else max_chars
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[truncated]"


def _compact_value(value, depth: int = 0):
    if value is None or isinstance(value, (int, float, bool)):
        return value, False
    if isinstance(value, str):
        compacted = _compact_text(value)
        return compacted, compacted != value
    if depth >= 3:
        return type(value).__name__, True
    if isinstance(value, dict):
        compacted = {}
        truncated = False
        items = list(value.items())
        for key, item_value in items[:20]:
            cv, it = _compact_value(item_value, depth + 1)
            compacted[key] = cv
            truncated = truncated or it
        if len(items) > 20:
            compacted["_truncated_items"] = len(items) - 20
            truncated = True
        return compacted, truncated
    if isinstance(value, (list, tuple)):
        compacted = []
        truncated = False
        for item in list(value)[:20]:
            ci, it = _compact_value(item, depth + 1)
            compacted.append(ci)
            truncated = truncated or it
        if len(value) > 20:
            compacted.append(f"...[{len(value) - 20} more items]")
            truncated = True
        return compacted, truncated
    return str(value), True


def _build_result_summary(result) -> str:
    if result is None:
        return "Sin resultado estructurado."
    if isinstance(result, dict):
        keys = list(result.keys())
        preview = ", ".join(str(k) for k in keys[:5]) or "sin claves"
        if len(keys) > 5:
            preview += f" (+{len(keys) - 5} mas)"
        return f"Resultado tipo objeto con {len(keys)} claves: {preview}."
    if isinstance(result, list):
        return f"Resultado tipo lista con {len(result)} elementos."
    if isinstance(result, str):
        return f"Resultado de texto con {len(result)} caracteres."
    return f"Resultado tipo {type(result).__name__}."


async def _execute_script_subprocess(code: str, inputs: dict) -> dict:
    os.makedirs(settings.RESULT_DIR, exist_ok=True)
    job_dir = tempfile.mkdtemp(prefix="auditbrain_job_", dir=settings.RESULT_DIR)
    payload_path = os.path.join(job_dir, "payload.json")
    output_path = os.path.join(job_dir, "output.json")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(settings.PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["AUDITBRAIN_MAX_STREAM_CHARS"] = str(settings.MAX_STD_STREAM_CHARS)

    with open(payload_path, "w", encoding="utf-8") as fh:
        json.dump({"code": code, "inputs": inputs}, fh, ensure_ascii=False)

    process = await asyncio.create_subprocess_exec(
        settings.PYTHON_EXECUTABLE,
        settings.RUNNER_PATH,
        payload_path,
        output_path,
        cwd=job_dir,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=settings.EXECUTION_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        raise TimeoutError(
            f"La ejecucion excedio el limite de {settings.EXECUTION_TIMEOUT_SECONDS} segundos."
        )

    runner_stdout = stdout_bytes.decode("utf-8", errors="replace")
    runner_stderr = stderr_bytes.decode("utf-8", errors="replace")

    if not os.path.isfile(output_path):
        raise RuntimeError(
            "El runner no produjo salida utilizable."
            + (f" STDERR: {runner_stderr[:500]}" if runner_stderr else "")
        )

    with open(output_path, "r", encoding="utf-8") as fh:
        result_payload = json.load(fh)

    if process.returncode != 0 and "error" not in result_payload:
        result_payload["error"] = (
            "La ejecucion del runner fallo."
            + (f" STDERR: {runner_stderr[:500]}" if runner_stderr else "")
        )

    if runner_stdout:
        result_payload["runner_stdout"] = _truncate_stream(runner_stdout)
    if runner_stderr:
        result_payload["runner_stderr"] = _truncate_stream(runner_stderr)
    result_payload["job_dir"] = job_dir
    return result_payload


async def run_python_code(code: str, inputs: dict = None, response_mode: str = None) -> dict:
    """Punto de entrada del service para la plataforma v1.

    Devuelve una respuesta estructurada (sin tocar el flujo legacy).
    """
    inputs = inputs or {}
    mode = (response_mode or settings.DEFAULT_RESPONSE_MODE).strip().lower()

    if not code:
        return {"error": "No se recibió ningún script para ejecutar."}

    async with _EXECUTION_SEMAPHORE:
        execution_output = await _execute_script_subprocess(code, inputs)

    if execution_output.get("error"):
        return {
            "error": execution_output.get("error"),
            "stdout": execution_output.get("stdout", ""),
            "stderr": execution_output.get("stderr", ""),
            "traceback": execution_output.get("traceback"),
            "service": "AuditBrain Platform v1 - python_runner",
        }

    result = execution_output.get("result")
    compact_result, result_truncated = _compact_value(result)
    response = {
        "stdout": _compact_text(execution_output.get("stdout", "")),
        "stderr": _compact_text(execution_output.get("stderr", "")),
        "result": result if mode == "full" else compact_result,
        "result_summary": _build_result_summary(result),
        "service": "AuditBrain Platform v1 - python_runner",
    }
    if mode != "full" and result_truncated:
        response["result_truncated"] = True
    if not response["stdout"]:
        response.pop("stdout")
    if not response["stderr"]:
        response.pop("stderr")
    response["generated_paths"] = execution_output.get("generated_paths", [])
    return response
