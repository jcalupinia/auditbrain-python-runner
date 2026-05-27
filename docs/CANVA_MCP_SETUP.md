# Setup Canva MCP — Designs profesionales via Claude API

Permite que AuditBrain backend genere designs Canva reales (PDF/PPTX/PNG)
con calidad de agencia, brand kit aplicado, vía la integración nativa de
Anthropic Claude API con el MCP de Canva.

**Resultado:** los GPTs (AuditSmart, H&G Abogados, etc.) podrán pedir
presentaciones para Board, informes ejecutivos, etc., y AuditBrain
devolverá URLs descargables (PDF + PPTX editables).

## Coste real

| Concepto | Coste |
|---|---|
| Anthropic Claude API tokens (input + output) | ~$0.10-0.20 por design |
| Canva.com generación | Free hasta cuota de tu plan Canva |
| **Total típico por design** | **~$0.15** |

Con un balance de $20 en Anthropic, alcanza para ~130 designs profesionales.

## Pre-requisitos

- ✅ Tener `ANTHROPIC_API_KEY` configurado en Render (ya lo tienes).
- ✅ Tener una cuenta Canva (free funciona; Pro/Teams permite Brand Templates).
- ⏳ Obtener un OAuth token de Canva (lo hacemos en esta guía).

## Paso 1 — Verificar que tienes balance de Anthropic

1. https://console.anthropic.com/settings/billing
2. Confirma que `Credit balance` > $1.
3. Si está vacío: **Add to credit balance** → mín $5.

## Paso 2 — Obtener el OAuth token de Canva para MCP

Esta es la parte más delicada porque depende del flujo OAuth de Anthropic.
Hay dos caminos según cómo Anthropic exponga el MCP de Canva:

### Camino A — MCP gestionado por Anthropic (recomendado si está disponible)

Si Anthropic ofrece el MCP de Canva como "managed connector":

1. https://console.anthropic.com/connectors
2. Buscar "Canva" en la lista de connectors disponibles.
3. Click **Connect**.
4. OAuth flow: te redirige a Canva → autorizas → vuelves a Anthropic.
5. Anthropic genera un token interno para tu organización.
6. En la página del connector verás el campo **MCP Token** (o equivalente).
7. Cópialo.

### Camino B — Self-hosted MCP (si Anthropic no ofrece Canva gestionado)

Si el MCP de Canva NO está gestionado, hay que obtenerlo de Canva directamente:

1. https://www.canva.com/developers/
2. Apply for Canva Connect API (puede requerir aprobación, especialmente
   para apps de producción).
3. Crear una "Connected App" con scopes:
   - `design:read`
   - `design:write`
   - `design:meta:read`
   - `asset:read`
   - `asset:write`
   - `brandtemplate:meta:read`
   - `brandtemplate:content:read`
   - `comment:read`
   - `comment:write`
4. Configurar OAuth callback (puede ser un endpoint de prueba si solo
   usas el token server-to-server).
5. Ejecutar el OAuth flow una vez para obtener el `access_token`.
6. Refrescarlo cuando expire (válidez típica: ~30 días).

## Paso 3 — Pegar el token en Render

1. https://dashboard.render.com → `auditbrain-python-runner` → **Environment**.
2. Busca la variable `CANVA_MCP_OAUTH_TOKEN` (ya existe vacía gracias al
   render.yaml de este commit).
3. Click el ✏️ → pega el token.
4. **Save Changes**.
5. Render redespliega automáticamente (~3 min).

## Paso 4 — Verificar que está activo

Después del redeploy:

```bash
curl https://auditbrain-python-runner.onrender.com/api/v1/health
```

Debes ver:
```json
{
  ...
  "canva": {
    "available": true,
    "engine": "anthropic-mcp-canva"
  },
  "formats": {
    ...
    "canva_native": true
  }
}
```

Si `available: false`, el endpoint `/api/v1/canva/status` te dice qué
falta:
```bash
curl -H "X-API-Key: TU_KEY" \
  https://auditbrain-python-runner.onrender.com/api/v1/canva/status
```

## Paso 5 — Test desde curl

Genera un reporte ejecutivo de prueba:

```bash
curl -X POST https://auditbrain-python-runner.onrender.com/api/v1/canva/audit-report \
  -H "X-API-Key: TU_AUDITBRAIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "ACME Holding S.A.",
    "period": "2026",
    "findings": [
      {
        "titulo": "Conciliación bancaria deficiente",
        "descripcion": "Diferencias no conciliadas mayores a 60 días.",
        "riesgo": "Alto",
        "recomendacion": "Implementar conciliación diaria automatizada."
      }
    ],
    "kpis": {
      "ingresos": "USD 12.5M",
      "ebitda_pct": "18%",
      "liquidez_corriente": 1.4
    },
    "recommendations": [
      "Reforzar controles de tesorería",
      "Actualizar políticas de provisiones"
    ]
  }'
```

Respuesta esperada (~30-60 seg):
```json
{
  "status": "ok",
  "design_id": "DXXXXXXXXX",
  "edit_url": "https://www.canva.com/d/XXXXXXX",
  "view_url": "https://www.canva.com/d/XXXXXXX",
  "page_count": 6,
  "exports": {
    "pdf": "https://export-download.canva.com/...",
    "pptx": "https://export-download.canva.com/..."
  },
  "tokens_in": 28000,
  "tokens_out": 4500
}
```

## Paso 6 — Integrar en los GPTs (opcional)

Para que tus 4 GPTs puedan pedir designs Canva directamente, añade esta
action en su OpenAPI:

```yaml
/api/v1/canva/audit-report:
  post:
    summary: Genera reporte ejecutivo de auditoría en Canva
    security:
      - ApiKeyAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [client_name, period]
            properties:
              client_name: { type: string }
              period: { type: string }
              findings:
                type: array
                items:
                  type: object
              kpis: { type: object }
              recommendations:
                type: array
                items: { type: string }
    responses:
      '200':
        description: Design generado
        content:
          application/json:
            schema:
              type: object
              properties:
                design_id: { type: string }
                edit_url: { type: string }
                exports: { type: object }
```

## Troubleshooting

### "canva.available: false" después de configurar el token
- Verifica que `CANVA_MCP_OAUTH_TOKEN` no esté vacío en Render.
- Confirma que el redeploy completó (Logs → "Live").
- Revisa que la librería `anthropic` esté instalada (parte del deploy).

### "Error invocando Claude API con MCP de Canva: ..."
- Token expirado: regéneralo (Camino A o B).
- Modelo no soporta MCP: usa `claude-sonnet-4-6` o superior.
- Beta header rechazado: Anthropic puede haber cambiado el header
  `anthropic-beta`; revisa docs oficiales y actualiza `canva_mcp.py`.

### Token expirado (refresh)
- Canva OAuth access_token expira típicamente en 30 días.
- Implementar refresh con el `refresh_token` (no incluido en esta fase).
- Por ahora, cuando expira, repite el Paso 2 y actualiza el env var.

### Coste mayor al esperado
- Cada design ~$0.15. Si ves consumo mayor, revisa logs del backend
  para ver si está reintentando llamadas.
- Configura alertas de balance en Anthropic console.

## Recursos

- Anthropic Messages API + MCP: https://docs.anthropic.com/claude/docs/agents-tools-use
- Canva Connect API: https://www.canva.com/developers/docs/connect-api/
- MCP especificación: https://modelcontextprotocol.io/
