# Setup OCR con Google Cloud Vision API

Esta guía te lleva paso a paso desde cero hasta tener OCR funcionando
en AuditBrain. Tiempo estimado: **15 minutos**.

## Resumen del flujo

```
1. Crear proyecto Google Cloud  ─┐
2. Habilitar Vision API          ├─→  Service Account JSON
3. Crear Service Account         │        │
4. Generar key (JSON)            ─┘        ▼
                                     5. Pegar JSON completo en
                                        Render → Environment →
                                        GOOGLE_APPLICATION_CREDENTIALS_JSON
                                            │
                                            ▼
                                     6. Render redeploy
                                            │
                                            ▼
                                     7. Probar OCR
```

## Coste real

- **Gratis** hasta 1000 unidades/mes (1 unidad = 1 imagen O 1 página PDF).
- A partir de 1001: **$1.50 por 1000 unidades**.
- Para un auditor típico (~300 PDFs/mes de 5 págs = 1500 unidades):
  costo mensual ≈ **$0.75/mes**.
- Pico de uso (10,000 unidades/mes): **$15/mes**.

Google da $300 USD de crédito inicial gratis para nuevos usuarios de
Cloud, suficiente para ~200,000 unidades.

## Paso 1 — Crear proyecto Google Cloud

1. Abrir https://console.cloud.google.com/projectcreate
2. Login con tu cuenta Google (la misma de Gemini sirve).
3. **Project name**: `AuditBrain OCR` (o el que quieras).
4. **Organization**: si tienes Workspace corporativo, elígelo. Si no,
   "No organization".
5. Click **Create**.
6. Espera ~10 segundos a que se cree.
7. Asegúrate de que esté **seleccionado** en el dropdown de arriba.

## Paso 2 — Habilitar Cloud Vision API

1. Abrir https://console.cloud.google.com/apis/library/vision.googleapis.com
2. Confirma que el proyecto seleccionado arriba es `AuditBrain OCR`.
3. Click **Enable** (botón azul).
4. Espera ~30 seg a que aparezca el panel de la API habilitada.

> Nota: si te pide habilitar facturación, ve al paso 2.1.

### Paso 2.1 — (Si te lo pide) Habilitar facturación

Google requiere una tarjeta para usar Cloud Vision, **incluso dentro
del free tier**. No se te cobrará nada si te mantienes bajo 1000
unidades/mes.

1. https://console.cloud.google.com/billing
2. **Link a billing account** → crea una nueva si no tienes.
3. Tarjeta de crédito / débito.
4. Vincúlala al proyecto `AuditBrain OCR`.

Activa **alertas de presupuesto** para evitar sorpresas:
1. Billing → Budgets & alerts → Create budget
2. Threshold: $5/mes
3. Email notification al 100% del presupuesto.

## Paso 3 — Crear Service Account

El service account es una "cuenta de robot" que tu AuditBrain usará
para llamar a Vision API.

1. Abrir https://console.cloud.google.com/iam-admin/serviceaccounts
2. Confirma el proyecto correcto arriba.
3. Click **+ Create Service Account**.
4. **Service account name**: `auditbrain-ocr`
5. **Service account ID**: se autogenera, déjalo.
6. **Description**: `OCR service for AuditBrain backend`
7. Click **Create and continue**.
8. **Grant this service account access to project**:
   - Role: busca y selecciona **Cloud Vision AI User**
     (también vale "Cloud Vision API Service Agent" si no aparece).
9. Click **Continue** → **Done**.

## Paso 4 — Generar la key JSON

1. En la lista de service accounts, encuentra `auditbrain-ocr@...`
2. Click el menú de 3 puntos (⋮) a la derecha → **Manage keys**.
3. **Add key** → **Create new key**.
4. Tipo: **JSON** (seleccionado por default).
5. Click **Create**.
6. Tu navegador descarga un archivo `auditbrain-ocr-XXXXX.json`.

> ⚠️ **CRÍTICO**: este archivo es como una contraseña maestra. Trátalo
> con cuidado. No lo commitees a git, no lo pegues en chats, no lo
> compartas.

## Paso 5 — Pegar el JSON en Render

El JSON tiene formato multilínea pero Render necesita una **sola línea**
para env vars. Hay dos formas:

### Forma A — Convertir a una línea (recomendado)

1. Abre el archivo JSON con Notepad o cualquier editor.
2. Verás algo como:
   ```json
   {
     "type": "service_account",
     "project_id": "auditbrain-ocr",
     "private_key_id": "abc123...",
     "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
     ...
   }
   ```
3. **Selecciona todo el contenido** (Ctrl+A) y cópialo.

### Forma B — Comprimir a una línea con PowerShell

Si tu Render no acepta multilínea bien:

```powershell
$json = Get-Content "auditbrain-ocr-XXXXX.json" -Raw | ConvertFrom-Json
$compact = $json | ConvertTo-Json -Compress
$compact | Set-Clipboard
```

Tu portapapeles tendrá el JSON en una sola línea.

### Pegarlo en Render

1. https://dashboard.render.com → `auditbrain-python-runner` → **Environment**
2. La variable `GOOGLE_APPLICATION_CREDENTIALS_JSON` ya está creada como
   slot vacío (gracias al render.yaml actualizado).
3. Click el ✏️ (lápiz) al lado de la variable.
4. **Value**: pega el contenido del JSON.
5. **Save Changes**.
6. Render redespliega automáticamente.

## Paso 6 — Verificar que funciona

Después del redeploy (~3 min), pega esto en el módulo Runner de
AuditBrain:

```python
from backend.app.utils import ocr

if not ocr.is_available():
    result = {"error": "OCR no disponible. Revisa env var."}
else:
    result = {"status": "OCR listo", "method": "google-vision"}
```

O desde tu PC con curl:

```powershell
curl -X POST https://auditbrain-python-runner.onrender.com/api/v1/python/run `
  -H "X-API-Key: TU_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"script": "from backend.app.utils import ocr; result = {\"available\": ocr.is_available()}"}'
```

Debería responder `{"available": true}`.

## Paso 7 — Usar OCR en tu código

```python
from backend.app.utils import ocr

# OCR híbrido (recomendado) — usa pdfplumber primero, OCR como fallback
result = ocr.extract_text_smart("declaracion_sri_2020.pdf")
print(result["text"])
print(f"Método usado: {result['method']}")  # 'pdfplumber' o 'ocr'
print(f"Unidades Vision API consumidas: {result['ocr_units_used']}")

# OCR forzado (siempre paga)
result = ocr.ocr_pdf("escritura_publica.pdf")

# OCR de imagen
result = ocr.ocr_image("foto_factura.jpg")
```

## Monitoreo del uso

1. https://console.cloud.google.com/apis/dashboard
2. Click en **Cloud Vision API** → **Quotas & System Limits**
3. Verás "Document text detection: N requests today".

## Troubleshooting

### "OCR no configurado" después de pegar el JSON
- Verifica que pegaste el contenido **completo**, incluyendo las llaves
  `{` y `}` exteriores.
- Render guarda automáticamente — confirma que aparezca como secreto.
- Espera el redeploy completo (estado `Live` verde).

### "Error 403: API not enabled"
- Vuelve al Paso 2 y confirma que Cloud Vision API está enabled
  **en el mismo proyecto** del service account.

### "PERMISSION_DENIED: The caller does not have permission"
- Vuelve al Paso 3.8 y confirma que el service account tiene el rol
  **Cloud Vision AI User**.

### "Quota exceeded for quota metric 'Requests'"
- Estás sobre el free tier. Habilita billing o espera al próximo mes.
- Si ya tienes billing: revisa límites en
  https://console.cloud.google.com/iam-admin/quotas

### Costo inesperado
- Si activaste billing, configura alertas (ver Paso 2.1).
- 1 PDF de 100 páginas = 100 unidades = $0.15.
- Un mes con muchos PDFs grandes puede sumarse.
