import asyncio
import datetime
import json
import os
import shutil
import sys
import tempfile
import traceback
import uuid
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

APP_VERSION = "4.0.0"

# ==========================================================
# AuditBrain: Motor Analítico del Ecosistema Audit Consulting IA Suite
# ==========================================================
app = FastAPI(
    title="AuditBrain - Python Runner",
    description=(
        "Motor analítico, financiero, legal y de automatización "
        "integrado con el ecosistema Audit Consulting IA Suite. "
        "Ejecuta scripts Python dinámicos, genera entregables corporativos "
        "y se conecta al Universal Creador de Documentos."
    ),
    version=APP_VERSION
)

# ==========================================================
# Configuración Global de Servicios Externos
# ==========================================================
DOCUMENT_SERVICE = os.getenv("DOCUMENT_SERVICE", "https://universal-creador-documentos.onrender.com").rstrip("/")
RESULT_DIR = os.path.abspath("resultados")
SCRIPT_WORKDIR = os.getcwd()
RUNNER_PATH = os.path.join(SCRIPT_WORKDIR, "auditbrain_exec_runner.py")
PYTHON_EXECUTABLE = sys.executable
EXECUTION_TIMEOUT_SECONDS = int(os.getenv("EXECUTION_TIMEOUT_SECONDS", "300"))
EXECUTION_CONCURRENCY = max(1, int(os.getenv("EXECUTION_CONCURRENCY", "1")))
MAX_STD_STREAM_CHARS = int(os.getenv("AUDITBRAIN_MAX_STREAM_CHARS", "200000"))
PUBLISHABLE_EXTENSIONS = {
    ".csv", ".doc", ".docx", ".html", ".json", ".pdf", ".png", ".ppt", ".pptx",
    ".svg", ".txt", ".xls", ".xlsx", ".zip"
}
EXECUTION_SEMAPHORE = asyncio.Semaphore(EXECUTION_CONCURRENCY)
os.makedirs(RESULT_DIR, exist_ok=True)


def _publish_generated_files(generated_paths, request):
    published_files = []
    seen_filenames = set()

    for source_path in generated_paths:
        filename = os.path.basename(source_path)
        if not filename:
            continue

        target_name = filename
        target_path = os.path.join(RESULT_DIR, target_name)
        if os.path.abspath(source_path) != os.path.abspath(target_path):
            stem, ext = os.path.splitext(filename)
            target_name = f"{stem}_{uuid.uuid4().hex[:8]}{ext}"
            target_path = os.path.join(RESULT_DIR, target_name)
            shutil.copy2(source_path, target_path)

        if target_name in seen_filenames:
            continue

        seen_filenames.add(target_name)
        published_files.append({
            "filename": target_name,
            "url": f"{str(request.base_url).rstrip('/')}/resultados/{target_name}"
        })

    return published_files


def _truncate_stream(value):
    if len(value) <= MAX_STD_STREAM_CHARS:
        return value
    return value[:MAX_STD_STREAM_CHARS] + "\n...[truncated]"


async def _execute_script_subprocess(code, inputs):
    job_dir = tempfile.mkdtemp(prefix="auditbrain_job_", dir=RESULT_DIR)
    payload_path = os.path.join(job_dir, "payload.json")
    output_path = os.path.join(job_dir, "output.json")
    env = os.environ.copy()
    env["PYTHONPATH"] = SCRIPT_WORKDIR + os.pathsep + env.get("PYTHONPATH", "")
    env["AUDITBRAIN_MAX_STREAM_CHARS"] = str(MAX_STD_STREAM_CHARS)

    with open(payload_path, "w", encoding="utf-8") as fh:
        json.dump({"code": code, "inputs": inputs}, fh, ensure_ascii=False)

    process = await asyncio.create_subprocess_exec(
        PYTHON_EXECUTABLE,
        RUNNER_PATH,
        payload_path,
        output_path,
        cwd=job_dir,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=EXECUTION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        raise TimeoutError(
            f"La ejecucion excedio el limite de {EXECUTION_TIMEOUT_SECONDS} segundos."
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

# ==========================================================
# Ruta raíz para verificación (Render Health Check)
# ==========================================================
@app.get("/")
async def root():
    """Verificación de estado del servicio (evita errores 502 en Render)."""
    return {
        "status": "ok",
        "service": "AuditBrain Python Runner",
        "version": APP_VERSION,
        "message": "AuditBrain operativo y conectado al Universal Creador de Documentos 🚀",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# ==========================================================
# Endpoint principal — ejecución de scripts y generación de entregables
# ==========================================================
@app.get("/resultados/{filename}")
async def get_result_file(filename: str):
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo invalido.")

    file_path = os.path.join(RESULT_DIR, safe_name)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    return FileResponse(file_path, filename=safe_name)

@app.post("/run_python")
async def run_python(request: Request):
    """
    Ejecuta un script Python recibido dinámicamente desde los GPTs del ecosistema:
    - Audit Advisor IA (consultoría financiera, riesgo, valoración, dashboards)
    - AuditSmart (auditoría financiera, tributaria, forense, sistemas)
    - H&G Abogados IA (asesoría legal, societaria, digital, propiedad intelectual)
    - GPT Maestro RPA (automatización, chatbots, flujos, ETL, IA generativa)
    """

    try:
        # ----------------------------
        # Lectura del cuerpo JSON
        # ----------------------------
        body = await request.json()
        code = body.get("script", "")
        inputs = body.get("inputs", {})
        execution_context = body.get("execution_context", {})
        output_expectations = body.get("output_expectations", {})
        document_service = body.get("document_service", {})
        send_to_doc = output_expectations.get("send_to_document_service", False)

        if not code:
            return {"error": "No se recibió ningún script para ejecutar."}

        # ----------------------------
        # Preparación del entorno seguro de ejecución
        # ----------------------------
        async with EXECUTION_SEMAPHORE:
            execution_output = await _execute_script_subprocess(code, inputs)

        if execution_output.get("error"):
            return {
                "error": execution_output.get("error"),
                "stdout": execution_output.get("stdout", ""),
                "stderr": execution_output.get("stderr", ""),
                "traceback": execution_output.get("traceback"),
                "service": "AuditBrain Python Runner"
            }

        # Restaurar flujos estándar

        # ----------------------------
        # Captura de resultados
        # ----------------------------
        result = execution_output.get("result", None)
        response_data = {
            "stdout": execution_output.get("stdout", ""),
            "stderr": execution_output.get("stderr", ""),
            "result": result,
            "execution_context": execution_context
        }
        generated_files = _publish_generated_files(execution_output.get("generated_paths", []), request)
        if generated_files:
            response_data["generated_files"] = generated_files

        # ==========================================================
        # Generación de documentos con el servicio externo universal
        # ==========================================================
        if send_to_doc and result:
            try:
                document_service_base = DOCUMENT_SERVICE
                if isinstance(document_service, dict):
                    custom_document_service = str(document_service.get("endpoint", "")).strip()
                    if custom_document_service:
                        if not custom_document_service.startswith(("http://", "https://")):
                            custom_document_service = f"https://{custom_document_service.lstrip('/')}"
                        document_service_base = custom_document_service.rstrip("/")

                format_type = output_expectations.get("format", "excel").lower().strip()
                format_aliases = {
                    "xlsx": "excel",
                    "docx": "word",
                    "pptx": "ppt",
                    "power_bi": "powerbi",
                    "bi": "powerbi",
                    "zipfile": "zip"
                }
                format_type = format_aliases.get(format_type, format_type)
                endpoint_format = "powerbi" if format_type == "csv" else format_type
                endpoint = f"{document_service_base}/generate_{endpoint_format}"
                pdf_fallback_payload = None

                # ===========================
                # Excel
                # ===========================
                if format_type == "excel":
                    payload = {
                        "titulo": execution_context.get("task_name", "Reporte generado por AuditBrain"),
                        "data": {
                            "headers": list(result.keys()),
                            "rows": [[str(v) for v in result.values()]]
                        }
                    }

                # ===========================
                # PDF
                # ===========================
                elif format_type == "pdf":
                    payload = {
                        "title": "Informe de Resultados",
                        "sections": [
                            {"type": "h1", "text": "Resultados Analíticos"},
                            {"type": "p", "text": json.dumps(result, indent=2)},
                            {"type": "p", "text": f"Generado por AuditBrain el {datetime.datetime.utcnow().isoformat()}"}
                        ]
                    }

                # ===========================
                # Word
                # ===========================
                elif format_type == "word":
                    payload = {
                        "placeholders": {
                            "titulo": execution_context.get("task_name", "Informe Corporativo"),
                            "subtitulo": execution_context.get("module_area", "Resultados de Análisis"),
                            "autor": "Audit Consulting IA Suite",
                            "fecha": datetime.datetime.utcnow().strftime("%Y-%m-%d")
                        },
                        "content": [
                            {"type": "heading", "text": "Resultados Generales"},
                            {"type": "paragraph", "text": json.dumps(result, indent=2)}
                        ]
                    }

                # ===========================
                # PowerPoint
                # ===========================
                elif format_type == "ppt":
                    payload = {
                        "title": execution_context.get("task_name", "Presentación Ejecutiva"),
                        "subtitle": "Análisis generado automáticamente por AuditBrain",
                        "slides": [
                            {
                                "type": "title",
                                "title": "Resumen Ejecutivo",
                                "bullets": ["Resultados clave del análisis", "Integración completa con IA Suite"]
                            },
                            {
                                "type": "content",
                                "title": "Datos Principales",
                                "bullets": [json.dumps(result, indent=2)]
                            }
                        ]
                    }

                # ===========================
                # CSV
                # ===========================
                elif format_type == "csv":
                    payload = {
                        "headers": list(result.keys()),
                        "rows": [[str(v) for v in result.values()]]
                    }

                # ===========================
                # Canva
                # ===========================
                elif format_type == "canva":
                    payload = {
                        "title": execution_context.get("task_name", "Presentación Canva"),
                        "subtitle": execution_context.get("module_area", "Resultados de análisis"),
                        "sections": [
                            {"type": "heading", "text": "Resumen"},
                            {"type": "paragraph", "text": json.dumps(result, indent=2)}
                        ]
                    }

                # ===========================
                # Power BI
                # ===========================
                elif format_type == "powerbi":
                    payload = {
                        "dataset_name": execution_context.get("task_name", "Dataset AuditBrain"),
                        "headers": list(result.keys()),
                        "rows": [[v for v in result.values()]],
                        "metadata": {
                            "module_area": execution_context.get("module_area", "general"),
                            "generated_at": datetime.datetime.utcnow().isoformat()
                        }
                    }

                # ===========================
                # ZIP
                # ===========================
                elif format_type == "zip":
                    payload = {
                        "title": execution_context.get("task_name", "Paquete AuditBrain"),
                        "files": [
                            {
                                "filename": "resultado.json",
                                "content_type": "application/json",
                                "content": json.dumps(result, indent=2)
                            }
                        ]
                    }

                # ===========================
                # Default / Canva / JSON
                # ===========================
                else:
                    payload = {
                        "title": "Reporte General",
                        "sections": [{"type": "p", "text": json.dumps(result)}]
                    }

                # 🔗 Envío al servicio de documentos
                if format_type == "pdf":
                    # Fallback para instancias sin WeasyPrint operativo.
                    pdf_fallback_payload = {
                        "titulo": execution_context.get("task_name", "Informe de Resultados"),
                        "contenido": [json.dumps(result, indent=2)],
                        "incluir_grafico": False
                    }

                doc_response = requests.post(endpoint, json=payload, timeout=90)
                if doc_response.status_code != 200 and format_type == "pdf" and pdf_fallback_payload:
                    doc_response = requests.post(endpoint, json=pdf_fallback_payload, timeout=90)
                if doc_response.status_code == 200:
                    response_data["document_service"] = doc_response.json()
                else:
                    response_data["document_service"] = {
                        "error": f"Fallo al generar documento ({doc_response.status_code})",
                        "endpoint": endpoint,
                        "details": (doc_response.text or "")[:500]
                    }

            except Exception as e:
                response_data["document_service"] = {"error": str(e)}

        # ==========================================================
        # Respuesta final al cliente
        # ==========================================================
        response_data["timestamp"] = datetime.datetime.utcnow().isoformat()
        response_data["service"] = "AuditBrain Python Runner"
        return response_data

    except Exception as e:
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "service": "AuditBrain Python Runner"
        }
