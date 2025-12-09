from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import io, sys, traceback, json, requests

# ======================================================
# METADATA DEL SERVICIO
# ======================================================
app = FastAPI(
    title="AuditBrain - Python Runner",
    description="Motor analítico y generador de entregables del ecosistema Audit Consulting IA Suite.",
    version="3.0.0",
    servers=[
        {
            "url": "https://auditbrain-python-runner.onrender.com",
            "description": "Instancia principal desplegada en Render (AuditBrain Cloud)"
        }
    ]
)

# ======================================================
# CONFIGURACIÓN GLOBAL
# ======================================================
DOCUMENT_SERVICE = "https://universal-creador-documentos.onrender.com"


# ======================================================
# ENDPOINT PRINCIPAL: /run_python
# ======================================================
@app.post("/run_python")
async def run_python(request: Request):
    """
    Ejecuta scripts Python analíticos, financieros, legales o de automatización,
    y genera resultados o documentos corporativos con integración total a Universal Creador de Documentos.
    """
    try:
        # ---------------------------------------------
        # Lectura y validación del cuerpo de la solicitud
        # ---------------------------------------------
        body = await request.json()
        code = body.get("script", "")
        inputs = body.get("inputs", {})
        output_expectations = body.get("output_expectations", {})
        doc_service = body.get("document_service", {})
        send_to_doc = output_expectations.get("send_to_document_service", False)

        if not code:
            return JSONResponse(
                status_code=400,
                content={"error": "No se recibió ningún script para ejecutar."}
            )

        # ---------------------------------------------
        # Captura de stdout / stderr
        # ---------------------------------------------
        stdout, stderr = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = stdout, stderr

        # ---------------------------------------------
        # Ejecución dinámica del script
        # ---------------------------------------------
        local_vars = {"inputs": inputs}
        exec(code, {}, local_vars)
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__

        # ---------------------------------------------
        # Resultado de la ejecución
        # ---------------------------------------------
        result = local_vars.get("result", None)
        response_data = {
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "result": result
        }

        # ======================================================
        # ENVÍO AUTOMÁTICO AL SERVICIO DE DOCUMENTOS
        # ======================================================
        if send_to_doc and result:
            try:
                format_type = output_expectations.get("format", "excel").lower()
                endpoint = f"{DOCUMENT_SERVICE}/generate_{format_type}"

                # ---------------------------------------------
                # GENERACIÓN DE PAYLOAD SEGÚN FORMATO
                # ---------------------------------------------
                if format_type == "excel":
                    payload = {
                        "titulo": "Reporte generado por AuditBrain",
                        "data": {
                            "headers": list(result.keys()) if isinstance(result, dict) else ["Resultado"],
                            "rows": [[str(v) for v in result.values()]] if isinstance(result, dict) else [[str(result)]]
                        }
                    }

                elif format_type == "pdf":
                    payload = {
                        "title": "Informe de Resultados",
                        "sections": [
                            {"type": "h1", "text": "Resultados Analíticos"},
                            {"type": "p", "text": json.dumps(result, indent=2)}
                        ]
                    }

                elif format_type == "word":
                    payload = {
                        "placeholders": {
                            "titulo": "Informe Corporativo",
                            "subtitulo": "Resultados de Auditoría / Consultoría",
                            "autor": "Audit Consulting IA Suite",
                            "fecha": "2025-12-09"
                        },
                        "content": [
                            {"type": "heading", "text": "Resultados Generales"},
                            {"type": "paragraph", "text": json.dumps(result, indent=2)}
                        ]
                    }

                elif format_type == "pptx":
                    payload = {
                        "title": "Presentación Ejecutiva - AuditBrain",
                        "subtitle": "Resumen de Resultados y KPIs",
                        "slides": [
                            {
                                "type": "summary",
                                "title": "Indicadores Clave",
                                "bullets": [f"{k}: {v}" for k, v in result.items()] if isinstance(result, dict) else [str(result)]
                            },
                            {
                                "type": "closing",
                                "title": "Conclusiones",
                                "bullets": ["Generado automáticamente por AuditBrain IA Suite."]
                            }
                        ]
                    }

                elif format_type == "csv":
                    payload = {
                        "headers": list(result.keys()) if isinstance(result, dict) else ["Campo", "Valor"],
                        "rows": [[str(k), str(v)] for k, v in result.items()] if isinstance(result, dict) else [["Resultado", str(result)]]
                    }

                else:
                    payload = {
                        "title": "Reporte General",
                        "sections": [{"type": "p", "text": json.dumps(result)}]
                    }

                # ---------------------------------------------
                # ENVÍO AL SERVICIO UNIVERSAL
                # ---------------------------------------------
                doc_response = requests.post(endpoint, json=payload)
                if doc_response.status_code == 200:
                    response_data["document_service"] = doc_response.json()
                else:
                    response_data["document_service"] = {
                        "error": f"Fallo al generar documento ({doc_response.status_code})",
                        "endpoint": endpoint,
                        "payload": payload
                    }

            except Exception as e:
                response_data["document_service"] = {"error": str(e)}

        # ---------------------------------------------
        # RESPUESTA FINAL AL CLIENTE / GPT
        # ---------------------------------------------
        return JSONResponse(status_code=200, content=response_data)

    # ======================================================
    # CAPTURA DE ERRORES GLOBALES
    # ======================================================
    except Exception as e:
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
