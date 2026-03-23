from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
import io, sys, traceback, json, requests, datetime, os, shutil, uuid

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
PUBLISHABLE_EXTENSIONS = {
    ".csv", ".doc", ".docx", ".html", ".json", ".pdf", ".png", ".ppt", ".pptx",
    ".svg", ".txt", ".xls", ".xlsx", ".zip"
}
os.makedirs(RESULT_DIR, exist_ok=True)


def _snapshot_publishable_files():
    snapshots = {}
    search_roots = [SCRIPT_WORKDIR]
    if RESULT_DIR != SCRIPT_WORKDIR:
        search_roots.append(RESULT_DIR)

    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for entry in os.scandir(root):
            if not entry.is_file():
                continue
            ext = os.path.splitext(entry.name)[1].lower()
            if ext in PUBLISHABLE_EXTENSIONS:
                snapshots[os.path.abspath(entry.path)] = entry.stat().st_mtime
    return snapshots


def _namespace_file_candidates(exec_namespace):
    candidates = []
    for value in exec_namespace.values():
        if not isinstance(value, str):
            continue
        path = os.path.abspath(value)
        ext = os.path.splitext(path)[1].lower()
        if ext in PUBLISHABLE_EXTENSIONS and os.path.isfile(path):
            candidates.append(path)
    return candidates


def _publish_generated_files(before_snapshot, exec_namespace, request):
    after_snapshot = _snapshot_publishable_files()
    generated_paths = []

    for path, mtime in after_snapshot.items():
        if path not in before_snapshot or before_snapshot[path] != mtime:
            generated_paths.append(path)

    for path in _namespace_file_candidates(exec_namespace):
        if path not in generated_paths:
            generated_paths.append(path)

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
        stdout, stderr = io.StringIO(), io.StringIO()
        before_snapshot = _snapshot_publishable_files()
        sys.stdout, sys.stderr = stdout, stderr

        exec_namespace = {"__builtins__": __builtins__, "inputs": inputs}
        exec(code, exec_namespace, exec_namespace)

        # Restaurar flujos estándar
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__

        # ----------------------------
        # Captura de resultados
        # ----------------------------
        result = exec_namespace.get("result", None)
        response_data = {
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "result": result,
            "execution_context": execution_context
        }
        generated_files = _publish_generated_files(before_snapshot, exec_namespace, request)
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
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "service": "AuditBrain Python Runner"
        }
