# OCR para PDFs escaneados — opciones

## Por qué no está implementado todavía

El módulo `pdfplumber` actual extrae texto de **PDFs digitales** (los que
tienen capa de texto). Para **PDFs escaneados** (imagen pura, como
declaraciones del SRI antiguas) se necesita **OCR**.

El bloqueador es el runtime de Render:

```yaml
env: python   # buildpack Python — solo pip install, no apt-get
```

Tesseract OCR es un binario nativo. Para instalarlo se necesita:

```bash
apt-get install -y tesseract-ocr tesseract-ocr-spa
```

Con el buildpack Python actual no se puede ejecutar `apt-get`.
Hay 3 caminos posibles:

---

## Opción A — Cambiar Render a buildpack Docker ⭐ Recomendada

**Esfuerzo:** medio (1 día)
**Coste:** $0 adicional
**Pros:** control total, Tesseract local, sin latencia de red
**Contras:** build más lento, imagen ~600 MB en lugar de ~250 MB

### Cambios necesarios

1. En `render.yaml`:
```yaml
services:
  - type: web
    name: auditbrain-python-runner
    env: docker                    # <- cambio aquí
    dockerfilePath: ./Dockerfile   # <- el Dockerfile ya existe
    plan: starter
    # buildCommand y startCommand desaparecen — los maneja Dockerfile
```

2. En `Dockerfile`, añadir Tesseract:
```dockerfile
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*
```

3. En `requirements-prod.txt`:
```
pytesseract==0.3.13
pdf2image==1.17.0
```

4. Nuevo módulo `backend/app/utils/ocr.py`:
```python
import pytesseract
from pdf2image import convert_from_path

def ocr_pdf_to_text(pdf_path: str, lang: str = "spa") -> str:
    images = convert_from_path(pdf_path, dpi=200)
    text_parts = []
    for img in images:
        text_parts.append(pytesseract.image_to_string(img, lang=lang))
    return "\n".join(text_parts)
```

### Riesgos
- El primer build tarda ~10 min (vs ~3 min actuales).
- Imagen Docker más grande puede tardar en plan starter.
- pdf2image necesita poppler que añade ~50 MB.

---

## Opción B — Cloud OCR API (Google Vision / AWS Textract)

**Esfuerzo:** bajo (4 horas)
**Coste:** ~$0.50-1.50 por cada 1000 páginas OCR
**Pros:** sin cambios de infra, alta calidad (mejor que Tesseract)
**Contras:** coste por uso, datos salen del servidor

### Pasos

1. Cuenta en Google Cloud → habilitar Vision API
2. Generar Service Account JSON → guardar como secret en Render
3. Nuevo módulo `backend/app/utils/ocr_cloud.py`:

```python
from google.cloud import vision

def ocr_pdf_cloud(pdf_path: str) -> str:
    client = vision.ImageAnnotatorClient()
    with open(pdf_path, "rb") as f:
        content = f.read()
    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)
    return response.full_text_annotation.text
```

### Pricing real (Google Vision)
- Primeras 1,000 unidades/mes: GRATIS
- 1,001-5,000,000/mes: $1.50 por 1,000
- Para uso normal de un auditor (~500 PDFs/mes): siempre gratis

---

## Opción C — Servicio separado en Render con Docker

**Esfuerzo:** medio-alto (2 días)
**Coste:** $7/mes adicional (otro servicio starter)
**Pros:** no toca el backend actual
**Contras:** dos servicios para mantener

Crear un microservicio dedicado `auditbrain-ocr` con su propio
Dockerfile + Tesseract. El backend principal lo llama vía HTTP.

```yaml
services:
  - type: web
    name: auditbrain-python-runner
    # ... config actual sin cambios ...

  - type: web                         # <- nuevo servicio
    name: auditbrain-ocr
    env: docker
    dockerfilePath: ./services/ocr/Dockerfile
    plan: starter
```

---

## Recomendación

Para uso profesional con volumen impredecible: **Opción A (Docker)**.

Para empezar sin compromiso: **Opción B (Google Vision)** — gratis para
<1000 páginas/mes, sin tocar infra, ~4 horas de trabajo.

Para escenarios muy específicos (regulación, datos sensibles que no
salen del servidor): **Opción A**.
