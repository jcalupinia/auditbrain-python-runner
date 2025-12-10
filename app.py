from fastapi import FastAPI, Request
import io, sys, traceback, json, requests, datetime

# ==========================================================
# 🧠 AuditBrain: Motor Analítico del Ecosistema Audit Consulting IA Suite
# ==========================================================
app = FastAPI(
    title="AuditBrain - Python Runner",
    description=(
        "Motor analítico, financiero, legal y de automatización "
        "integrado con el ecosistema Audit Consulting IA Suite. "
        "Ejecuta scripts Python dinámicos, genera entregables corporativos "
        "y se conecta al Universal Creador de Documentos."
    ),
    version="3.0.0"
)

# ==========================================================
# 🌐 Configuración Global de Servicios Externos
# ==========================================================
DOCUMENT_SERVICE = "https://universal-creador-documentos.onrender.com"

# ==========================================================
# 🩺 Ruta raíz para verificación (Render Health Check)
# ==========================================================
@app.get("/")
async def root():
    """Verificación de estado del servicio (evita errores 502 en Render)."""
    return {
        "status": "ok",
        "service": "AuditBrain Python Runner",
        "version": "3.0.0",
        "message": "AuditBrain operativo y conectado al Universal Creador de Documentos 🚀",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# ==========================================================
# 🧩 Endpoint principal — ejecución de scripts y generación de entregables
# ==========================================================
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
        # 🔹 Lectura del cuerpo JSON
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
        # 🔹 Preparación del entorno seguro de ejecución
        # ----------------------------
        stdout, stderr = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = stdout, stderr

        local_vars = {"inputs": inputs}
        exec(code, {}, local_vars)

        # Restaurar flujos estándar
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__

        # ----------------------------
        # 🔹 Captura de resultados
        # ----------------------------
        result = local_vars.get("result", None)
        response_data = {
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "result": result,
            "execution_context": execution_context
        }

        # ==========================================================
        # 📦 Generación de documentos con el servicio externo universal
        # ==========================================================
        if send_to_doc and result:
            try:
                format_type = output_expectations.get("format", "excel").lower()
                endpoint = f"{DOCUMENT_SERVICE}/generate_{format_type}"

                # ===========================
                # 📊 Excel
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
                # 📄 PDF
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
                # 🧾 Word
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
                # 🧠 PowerPoint
                # ===========================
                elif format_type == "pptx":
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
                # 📈 CSV
                # ===========================
                elif format_type == "csv":
                    payload = {
                        "headers": list(result.keys()),
                        "rows": [[str(v) for v in result.values()]]
                    }

                # ===========================
                # 📑 Default / Canva / JSON
                # ===========================
                else:
                    payload = {
                        "title": "Reporte General",
                        "sections": [{"type": "p", "text": json.dumps(result)}]
                    }

                # 🔗 Envío al servicio de documentos
                doc_response = requests.post(endpoint, json=payload)
                if doc_response.status_code == 200:
                    response_data["document_service"] = doc_response.json()
                else:
                    response_data["document_service"] = {
                        "error": f"Fallo al generar documento ({doc_response.status_code})",
                        "endpoint": endpoint
                    }

            except Exception as e:
                response_data["document_service"] = {"error": str(e)}

        # ==========================================================
        # ✅ Respuesta final al cliente
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
