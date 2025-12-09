from fastapi import FastAPI, Request
import io, sys, traceback, json, requests

app = FastAPI(
    title="AuditBrain - Python Runner",
    description="Motor analítico y generador de entregables del ecosistema Audit Consulting IA Suite.",
    version="2.0.0"
)

DOCUMENT_SERVICE = "https://universal-creador-documentos.onrender.com"

@app.post("/run_python")
async def run_python(request: Request):
    try:
        body = await request.json()
        code = body.get("script", "")
        inputs = body.get("inputs", {})
        output_expectations = body.get("output_expectations", {})
        doc_service = body.get("document_service", {})
        send_to_doc = output_expectations.get("send_to_document_service", False)

        if not code:
            return {"error": "No se recibió ningún script para ejecutar."}

        stdout, stderr = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = stdout, stderr

        local_vars = {"inputs": inputs}
        exec(code, {}, local_vars)
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__

        result = local_vars.get("result", None)
        response_data = {
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "result": result
        }

        if send_to_doc and result:
            try:
                format_type = output_expectations.get("format", "excel").lower()
                endpoint = f"{DOCUMENT_SERVICE}/generate_{format_type}"

                if format_type == "excel":
                    payload = {
                        "titulo": "Reporte generado por AuditBrain",
                        "data": {
                            "headers": list(result.keys()),
                            "rows": [[str(v) for v in result.values()]]
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
                            "fecha": "2025-12-05"
                        },
                        "content": [
                            {"type": "heading", "text": "Resultados Generales"},
                            {"type": "paragraph", "text": json.dumps(result, indent=2)}
                        ]
                    }

                else:
                    payload = {
                        "title": "Reporte General",
                        "sections": [{"type": "p", "text": json.dumps(result)}]
                    }

                doc_response = requests.post(endpoint, json=payload)
                if doc_response.status_code == 200:
                    response_data["document_service"] = doc_response.json()
                else:
                    response_data["document_service"] = {"error": f"Fallo al generar documento ({doc_response.status_code})"}

            except Exception as e:
                response_data["document_service"] = {"error": str(e)}

        return response_data

    except Exception as e:
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        return {"error": str(e), "traceback": traceback.format_exc()}