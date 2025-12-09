# 🧠 AuditBrain (Python Runner)

AuditBrain es el motor analítico y generador de entregables del ecosistema **Audit Consulting IA Suite**.

## 🚀 Funcionalidad
- Ejecuta scripts Python enviados por los módulos GPT (AuditSmart, Audit Advisor, H&G Abogados, GPT Maestro).
- Procesa datos de finanzas, auditoría, legal y automatización.
- Envía automáticamente los resultados al servicio **Universal Creador de Documentos** (Render) para generar reportes en Excel, PDF, Word o Canva.

## 🧩 Endpoint principal
**POST** `/run_python`

### Ejemplo de solicitud
```json
{
  "script": "import pandas as pd\nresult = {'Ingresos': 10000, 'Utilidad': 2500}",
  "inputs": {},
  "output_expectations": {
    "format": "pdf",
    "send_to_document_service": true
  }
}
```

### Ejemplo de respuesta
```json
{
  "stdout": "",
  "stderr": "",
  "result": {"Ingresos": 10000, "Utilidad": 2500},
  "document_service": {"url": "https://universal-creador-documentos.onrender.com/files/resultados/Reporte.pdf"}
}
```

## 🧾 Dependencias
Ver `requirements.txt`

## 🧠 Integraciones
- Universal Creador de Documentos (Render)
- GPT Modules: AuditSmart, Audit Advisor IA, H&G Abogados, GPT Maestro