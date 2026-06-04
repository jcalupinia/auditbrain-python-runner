# Papel de Trabajo del Auditor — Rediseño VERIFICACIÓN A1 y AUDITORÍA DE ANEXOS

**Status:** Proposed
**Fecha:** 2026-06-04
**Autor:** Jorge Vinicio (Líder Audit-IA) + Claude (asistencia diseño)
**Sesión brainstorming:** continuación de trabajo previo sobre catálogos OFICIALES SRI y verificación A1
**Spec relacionado anterior:** `2026-05-30-ict-2025-design.md`

---

## 1. Contexto y problema

### Estado actual
El sistema genera un único Excel ICT (Informe de Cumplimiento Tributario) que incluye los anexos oficiales A1..A9 más dos hojas internas de control:
- **`VERIFICACIÓN A1`** (`backend/app/ict/fillers/verification.py`, 843 líneas): analiza las diferencias entre el saldo declarado (F-101) y el saldo contable, categorizadas en 5 grupos (real / signos / falta / no declarado / total agregado).
- **`AUDITORÍA DE ANEXOS`** (`backend/app/ict/fillers/auditoria_anexos.py`, 795 líneas): recorre A1..A9 y reporta saldos por sección.

### Problema 1 — Compatibilidad con SRI
El archivo Excel final **se carga al portal del SRI Ecuador**. El SRI espera la estructura oficial del ICT con los anexos A1..A9 y el INDICE, no hojas adicionales. Las hojas de auditoría son útiles para el auditor interno pero contaminan el archivo de carga: pueden ser rechazadas, ignoradas o, en el peor caso, generar inconsistencias.

### Problema 2 — Estética
Las hojas actuales son funcionales pero no se ven "profesionales como hechas por un ingeniero de datos/auditor Big 4". Faltan: KPIs ejecutivos arriba, semáforos visuales por anexo, narrativa interpretativa de qué significa cada diferencia.

### Problema 3 — Falta análisis interpretativo
El sistema detecta diferencias mecánicas (ej: "cas 6999 declarado $4.2M, contable $5.4M, Δ $1.2M") pero **no interpreta su significado tributario**. Para un auditor, "Δ $1.2M" no es accionable; "Subdeclaración de ventas con riesgo de glosa por IVA y Renta no declarados, exposición $444K" sí lo es.

### Restricciones
- No romper compatibilidad con SRI (Excel oficial intacto).
- No erosionar la regla suprema del CLAUDE.md (verificación empírica antes de declarar trabajo concluido).
- Mantener el formato profesional ya validado (estética SRI 2024 ARCOLANDS).
- Mantener tests existentes en verde.
- Latencia adicional ≤ 10s extra; costo IA ≤ $0.05 por sesión ICT.

---

## 2. Decisiones de diseño

Cuatro decisiones cerradas en sesión de brainstorming con el usuario el 2026-06-04:

| Decisión | Opción elegida | Razón |
|---|---|---|
| Estética visual | **Híbrido SRI Ecuador + Big 4** | Mantiene institucionalidad SRI + suma KPIs ejecutivos + semáforos |
| Alcance | **Solo VERIFICACIÓN A1 + AUDITORÍA DE ANEXOS** | Foco, bajo riesgo. Los anexos A1..A9 mantienen su formato actual. |
| KPIs A1 | (a) Saldos macro A=P+Pa con semáforo · (b) Cobertura mapeo % | Los 2 más críticos para el socio auditor |
| KPIs Anexos | Matriz 3×3 de semáforos por anexo | Triage visual instantáneo |
| Motor análisis | **LLM Claude API + Pydantic + QA evaluator** | Narrativa interpretativa rica + control de alucinación |
| Entrega artefactos | **Excel separado de papel de trabajo** | El Excel SRI queda limpio; el papel de trabajo va en archivo aparte |

---

## 3. Arquitectura — Layer split (Data / Presentation / LLM)

**Approach C aprobado**: separar generación de datos de auditoría de presentación visual. Esto se vuelve obligatorio porque ahora hay 3 layers (cálculo cuantitativo, interpretación LLM, presentación Excel) que deben evolucionar independientemente.

### 3.1 Módulos nuevos

```
backend/app/ict/
├── audit/                                  ← módulo nuevo
│   ├── __init__.py
│   ├── schemas.py                          ← Pydantic models compartidos
│   │     ├── A1Metrics
│   │     ├── AnexoStatus
│   │     ├── AnexosMetrics
│   │     ├── AnexoFinding
│   │     └── AnexoInterpretation
│   ├── metrics.py                          ← KPIs cuantitativos puros
│   │     ├── compute_a1_metrics(workbook) → A1Metrics
│   │     └── compute_anexos_metrics(workbook) → AnexosMetrics
│   ├── classifiers.py                      ← reglas de status
│   │     ├── semaforo_from_diff(diff, total, umbrales) → Status
│   │     ├── status_from_completeness(anexo_data) → Status
│   │     └── UMBRALES_MATERIALIDAD (constantes calibradas)
│   ├── interpreter.py                      ← motor LLM
│   │     ├── extract_anexo_data(workbook, anexo_code) → dict
│   │     ├── interpret_anexo(anexo_code, anexo_data) → AnexoInterpretation
│   │     └── interpret_all_anexos(workbook) → dict[code, Interpretation]
│   └── prompts/
│       └── auditor_tributario_ec.md        ← prompt template versionado
│
├── fillers/
│   ├── kpi_components.py                   ← módulo nuevo (Presentation helpers)
│   │     ├── build_kpi_card(ws, range, title, value, status, fmt)
│   │     ├── build_traffic_light_grid(ws, anchor, statuses)
│   │     ├── build_executive_banner(ws, title, kpis)
│   │     ├── build_finding_box(ws, anchor, finding: AnexoFinding)
│   │     └── STATUS_COLORS, KPI_STYLES (constantes)
│   ├── verification.py                     ← REFACTOR (solo consume audit + kpi)
│   └── auditoria_anexos.py                 ← REFACTOR (solo consume audit + kpi)
│
└── service.py                              ← devuelve tuple[bytes, bytes] (SRI, papel)
```

### 3.2 Pipeline de generación

```
generate_workbook(session_id) → tuple[bytes_sri, bytes_papel_trabajo]
  ├── 1. build_all_anexos(wb)                    [A1..A9 + INDICE — igual que hoy]
  │
  ├── 2. metrics_a1 = compute_a1_metrics(wb)     [cuantitativo, sync]
  ├── 3. metrics_anexos = compute_anexos_metrics(wb)
  │
  ├── 4. interpretations = await interpret_all_anexos(wb)  [LLM, async paralelo]
  │       ├── por anexo: extract_anexo_data + call Claude API
  │       ├── valida con Pydantic schema
  │       ├── pasa por auditbrain-ai-response-quality-evaluator
  │       └── registra en audit_trail
  │
  ├── 5. wb_papel = copy(wb)
  │       ├── fill_verification_a1(wb_papel, metrics_a1, interpretations["A1"])
  │       └── fill_auditoria_anexos(wb_papel, metrics_anexos, interpretations)
  │       → bytes_papel_trabajo
  │
  └── 6. wb_sri = wb                             [no incluye hojas auditoría]
        → bytes_sri
```

**Garantía de aislamiento:** el workbook SRI nunca toca el filler de auditoría. Si el filler de auditoría falla, el SRI se entrega igual con warning.

### 3.3 Schemas de datos (`backend/app/ict/audit/schemas.py`)

```python
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field

class Status(str, Enum):
    OK = "ok"                    # verde
    REVISAR = "revisar"          # amarillo
    CRITICO = "critico"          # rojo
    NA = "na"                    # gris (no aplica / sin datos)

class A1Metrics(BaseModel):
    activo_total: Decimal
    pasivo_patrimonio_total: Decimal
    diferencia: Decimal
    status_cuadre: Status
    cobertura_mapeo_pct: float = Field(ge=0, le=100)
    cas_mapeados: int
    cas_total: int
    cas_sin_contrapartida: list[str]

class AnexoStatus(BaseModel):
    codigo: str                  # "A1" .. "A9"
    nombre: str                  # "Mapeo del balance"
    status: Status
    observacion_corta: str       # "Cuadra" / "Δ $1.2K" / "Falta info"
    monto_principal: Optional[Decimal] = None

class AnexosMetrics(BaseModel):
    anexos: list[AnexoStatus]    # los 9
    resumen_global: dict[Status, int]  # {OK: 5, REVISAR: 2, CRITICO: 1, NA: 1}

class AnexoFinding(BaseModel):
    severity: Literal["critico", "material", "leve", "informativo"]
    categoria: Literal[
        "subdeclaracion_ventas", "sobredeclaracion_ventas",
        "gasto_no_deducible", "depreciacion_irregular",
        "credito_iva_irrecuperable", "retencion_inconsistente",
        "impuesto_a_pagar_anomalo", "exportacion_sin_respaldo",
        "inventario_variacion_atipica", "beneficio_mal_aplicado",
        "conciliacion_inconsistente", "otra",
    ]
    titulo: str = Field(max_length=120)
    descripcion_tecnica: str
    implicacion_tributaria: str
    recomendacion: str
    monto_disputa: Optional[Decimal] = None
    casilleros_afectados: list[str] = []

class AnexoInterpretation(BaseModel):
    anexo_codigo: str
    anexo_nombre: str
    resumen_ejecutivo: str = Field(max_length=500)
    findings: list[AnexoFinding]
    confianza_modelo: Literal["alta", "media", "baja"]
    requiere_revision_humana: bool
    timestamp_analisis: datetime
    modelo_usado: str            # "claude-sonnet-4-7-20260101"
    tokens_consumidos: int
```

---

## 4. Layout visual de los artefactos

### 4.1 Hoja `VERIFICACIÓN A1`

```
┌────────────────────────────────────────────────────────────────────────┐
│ [LOGO]   AUDITBRAIN · PAPEL DE TRABAJO DEL AUDITOR                    │
│          VERIFICACIÓN ANEXO A1 · MAPEO DEL BALANCE                    │
│          PROPHAR S.A. · RUC 1791859596001 · Período 2025              │
└────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│ ACTIVO TOTAL        │ │ PASIVO + PATRIMONIO │ │ DIFERENCIA A=P+Pa   │
│                     │ │                     │ │                     │
│   $ 21,671,880.68   │ │   $ 21,671,880.68   │ │      $ 0.00      🟢│
│                     │ │                     │ │   Cuadra perfecto   │
│   F-101 cas 499     │ │   F-101 cas 699     │ │                     │
└─────────────────────┘ └─────────────────────┘ └─────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ COBERTURA DE MAPEO F-101 ↔ BALANCE CONTABLE                          │
│   ███████████████████████████░░░░░  87%  (47 de 54 cas con balance)  │
│   ⚠ 7 casilleros declarados sin contrapartida contable                │
└────────────────────────────────────────────────────────────────────────┘

[Sección 6.5 actual: 🔬 ARTEFACTO · DIFERENCIAS POR REVISAR — sin cambios]

[NUEVA sección 7: 🤖 INTERPRETACIÓN A1 · Análisis del agente]
  Bloque con: AnexoInterpretation de A1 renderizado como tarjetas de findings
```

### 4.2 Hoja `AUDITORÍA DE ANEXOS`

```
[Banner ejecutivo igual al de A1, pero "AUDITORÍA INTEGRAL A1..A9"]

┌────────────────────────────────────────────────────────────────────────┐
│ MATRIZ DE ESTADO POR ANEXO                                            │
│   [Grid 3×3 con 9 cuadros — cada uno: código, semáforo, monto/obs]    │
│   Leyenda: 🟢 OK · 🟧 Revisar · 🔴 Crítico · ⚪ N/A                   │
└────────────────────────────────────────────────────────────────────────┘

[Sección actual: detalle por anexo — sin cambios]

[NUEVA sección: 🤖 INTERPRETACIÓN POR ANEXO]
  Por cada A1..A9:
    ▸ A2 — Conciliación de Ingresos [Confianza: 🟢 Alta]
       Resumen ejecutivo: ...
       [Tarjetas de findings — una por finding del AnexoInterpretation]
```

### 4.3 Renderizado de `build_finding_box`

Cada `AnexoFinding` se renderiza como un bloque con borde según severity:

```
┌──────────────────────────────────────────────────────────────────────┐
│ {emoji_severity} {SEVERITY UPPER} · {titulo}                         │
│                                                                      │
│ Descripción técnica: {descripcion_tecnica}                          │
│                                                                      │
│ Implicación tributaria: {implicacion_tributaria}                    │
│                                                                      │
│ Recomendación: {recomendacion}                                       │
│                                                                      │
│ Casilleros: {casilleros_afectados}                                  │
│ Monto disputa: {monto_disputa}                                       │
└──────────────────────────────────────────────────────────────────────┘
```

Colores de borde:
- `critico` → borde rojo (#C0392B) grosor 2px
- `material` → borde naranja (#E67E22) grosor 2px
- `leve` → borde amarillo (#F1C40F) grosor 1px
- `informativo` → borde azul (#3498DB) grosor 1px

---

## 5. Motor LLM — `interpreter.py`

### 5.1 Prompt template

`backend/app/ict/audit/prompts/auditor_tributario_ec.md`:

```markdown
# ROL
Eres un auditor tributario senior con 15 años de experiencia en Ecuador,
especializado en el ICT (Informe de Cumplimiento Tributario) del SRI.
Conoces a fondo la LORTI, su reglamento, las resoluciones del SRI y la
NIIF aplicable.

# TAREA
Analiza los datos del anexo {anexo_codigo} ({anexo_nombre}) del cliente
{razon_social} (RUC {ruc}) para el período fiscal {periodo}.

Identifica entre 0 y 5 hallazgos materiales que un auditor revisor
debería conocer. Para cada hallazgo, sigue la estructura
Condición-Criterio-Causa-Efecto-Evidencia-Recomendación.

# DATOS DEL ANEXO
{anexo_data_json}

# DATOS DE REFERENCIA (para conciliación cruzada)
{referencia_a1_json}
{catalogo_casilleros_relevantes}

# SALIDA
Devuelve EXCLUSIVAMENTE un JSON válido que cumpla este schema:
{pydantic_schema}

# REGLAS CRÍTICAS
1. Si NO detectas hallazgos materiales, devuelve findings: []
2. Si los datos son insuficientes o ambiguos, marca requiere_revision_humana: true
3. Calibra `confianza_modelo`:
   - alta = patrón claro con respaldo de datos numéricos
   - media = sospecha pero datos parciales
   - baja = inferencia con riesgo de error
4. `monto_disputa` debe ser cuantificable, no estimado
5. NO inventes casilleros que no estén en el catálogo oficial
6. Toda implicación tributaria debe citar el artículo de LORTI/RLORTI
   o resolución SRI aplicable
```

### 5.2 Llamada al LLM

```python
async def interpret_anexo(
    anexo_codigo: str,
    anexo_data: dict,
    contexto: dict,
) -> AnexoInterpretation:
    prompt = render_prompt(anexo_codigo, anexo_data, contexto)
    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-7-20260101",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        tools=[{
            "name": "save_interpretation",
            "input_schema": AnexoInterpretation.model_json_schema(),
        }],
        tool_choice={"type": "tool", "name": "save_interpretation"},
        timeout=30.0,
    )
    raw = response.content[0].input
    return AnexoInterpretation.model_validate(raw)
```

### 5.3 Paralelización

```python
async def interpret_all_anexos(wb) -> dict[str, AnexoInterpretation]:
    tasks = [
        interpret_anexo(code, extract_anexo_data(wb, code), contexto)
        for code in ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    interpretations = {}
    for code, result in zip(anexo_codes, results):
        if isinstance(result, Exception):
            log.warning(f"Interpretación {code} falló: {result}")
            interpretations[code] = _fallback_interpretation(code)
        else:
            interpretations[code] = result
    return interpretations
```

---

## 6. Garantías anti-alucinación y resilience

### 6.1 Defensa en profundidad
1. **Pydantic validation** — JSON inválido → reintento (max 2) → fallback
2. **Tool use forzado** — el LLM debe usar la tool `save_interpretation` con schema explícito
3. **QA evaluator** — cada `AnexoInterpretation` pasa por skill `auditbrain-ai-response-quality-evaluator` ANTES de escribir al Excel.
   ⚠️ Nota de costo: el QA evaluator es un segundo call a la API. Estimación revisada: ~$0.04/sesión (no $0.02). Si el costo excede $0.05 en producción, evaluar (a) hacer QA solo sobre findings con `severity in ["critico", "material"]`, o (b) usar Haiku para el QA
4. **Confianza autoreportada** — si `confianza_modelo == "baja"`, el filler marca el bloque con borde rojo + leyenda "⚠ Revisar manualmente"
5. **`requiere_revision_humana`** — si `True`, el bloque queda con ícono dedicado
6. **Audit trail obligatorio** — cada interpretación registra (modelo, tokens, timestamp, hash_input) via `auditbrain-audit-trail-generator`
7. **Disclaimer al pie** — todas las hojas tienen footer: "Análisis generado por IA. La interpretación debe ser validada por el auditor responsable antes de cualquier decisión."

### 6.2 Resilience
- API Anthropic falla → papel de trabajo se genera sin interpretación + banner amarillo "⚠ Análisis IA no disponible esta sesión"
- Timeout 30s por anexo
- Reintentos: 3 con exponential backoff (1s, 2s, 4s)
- Cache: hash(anexo_data) → AnexoInterpretation (TTL 7 días) para reintentos idempotentes y debugging
- El Excel SRI **siempre** se entrega, aunque la interpretación falle

---

## 7. Endpoints y frontend

### 7.1 Backend
- `service.generate_excel(session_id)` cambia firma:
  - Antes: `→ bytes` (un archivo)
  - Después: `→ tuple[bytes_sri, bytes_papel_trabajo]`
- ⚠️ **Cambio breaking**: todos los callers de `service.generate_excel` deben adaptarse.
  Identificados hasta ahora: `router.py` (endpoint de descarga), `cleanup.py` (regeneración
  on-demand), y los E2E tests. Buscar con `grep -r "generate_excel" backend/` antes del
  refactor y migrar caller por caller.
- Endpoint actual `GET /ict/sessions/{id}/excel` → devuelve `bytes_sri` (limpio)
- Endpoint nuevo `GET /ict/sessions/{id}/papel-trabajo` → devuelve `bytes_papel_trabajo`
- Ambos almacenan en disco bajo `data/ict/{session_id}/` con nombres descriptivos:
  `ICT_{ruc}_{periodo}_SRI.xlsx` y `ICT_{ruc}_{periodo}_PAPEL_TRABAJO.xlsx`

### 7.2 Frontend (`frontend-clientes/`)
En la pantalla final de la sesión ICT, 2 botones diferenciados:

```tsx
<Button variant="primary" size="lg" onClick={downloadSri}>
  📤 Descargar Excel para el SRI
  <Tooltip>Archivo limpio listo para cargar al portal del SRI Ecuador</Tooltip>
</Button>

<Button variant="secondary" size="md" onClick={downloadPapelTrabajo}>
  📋 Descargar papel de trabajo del auditor
  <Tooltip>Incluye verificación de A1, auditoría de anexos e interpretación IA</Tooltip>
</Button>
```

---

## 8. Estrategia de testing

### 8.1 Tests existentes
Los tests de A1..A9 y catálogos siguen igual. Las pruebas que afirman "Excel ICT incluye hoja VERIFICACIÓN A1" se mueven a verificar **`papel_trabajo.xlsx`**, no el principal.

### 8.2 Tests nuevos
1. **`test_audit_metrics.py`** — unit tests puros (sin Excel):
   - `compute_a1_metrics` con fixture PROPHAR → assert valores conocidos
   - `compute_anexos_metrics` → 9 statuses correctos
   - `classifiers.semaforo_from_diff` casos límite
2. **`test_audit_interpreter.py`** — integración LLM:
   - Mock Anthropic client → assert que el prompt incluye datos correctos
   - Schema validation: respuesta inválida → reintento
   - Timeout → fallback
3. **`test_papel_trabajo_excel.py`** — E2E:
   - Genera papel de trabajo con PROPHAR
   - Verifica que el Excel SRI NO contiene hojas auditoría
   - Verifica que papel_trabajo.xlsx SÍ contiene VERIFICACIÓN A1 + AUDITORÍA + interpretaciones
   - Verifica que el Excel SRI no levanta cuadro "Reparaciones" al abrirse
4. **`test_kpi_components.py`** — visuales:
   - `build_kpi_card` renderiza colores correctos por Status
   - `build_traffic_light_grid` 9 cuadros con anclajes correctos
5. **Regression existente**: `test_ict_catalogos_no_heredan_nombres.py` sigue pasando.

### 8.3 Verificación empírica (regla suprema CLAUDE.md)
Antes de declarar terminado:
- Generar el papel de trabajo con PROPHAR S.A. real
- Abrir manualmente en Excel local
- Verificar visualmente: KPIs visibles, semáforos correctos, findings legibles
- Confirmar que el Excel SRI no levanta cuadro de reparaciones
- Confirmar que la suma de findings en el papel de trabajo es coherente con las diferencias ya conocidas (56 del A1)

---

## 9. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| LLM alucina hallazgos | Media | Alto | Pydantic + QA evaluator + confianza autoreportada + disclaimer + revisión humana obligatoria |
| Costo Anthropic API > esperado | Baja | Medio | Cache por hash, alerta si supera $0.10/sesión |
| Latencia +45s degrada UX | Baja | Medio | Paralelización con `asyncio.gather`, latencia esperada ~8s |
| API Anthropic down | Baja | Bajo | Fallback graceful: papel sin interpretación, Excel SRI intacto |
| Cliente confunde los 2 Excels | Media | Alto | Nombres MUY distintos: `..._SRI.xlsx` vs `..._PAPEL_TRABAJO.xlsx` + tooltips + colores distintos en UI |
| El Excel SRI queda con dirty state al separar hojas | Baja | Alto | Tests específicos verifican que el Excel SRI no contenga rastros (named ranges, links, defined names) de las hojas removidas |

---

## 10. Consecuencias

### Lo que se vuelve más fácil
- Generar reportes de auditoría profesionales sin contaminar el archivo SRI
- Agregar nuevos KPIs reutilizando `kpi_components.py`
- Agregar nuevas presentaciones (PDF, dashboard web) consumiendo `audit/metrics.py` + `audit/interpreter.py`
- Auditar la calidad del análisis IA via audit trail

### Lo que se vuelve más difícil
- Mantenimiento del prompt template (versionar, revisar cuando SRI cambia)
- Costos operacionales (Anthropic API)
- Latencia del flujo de generación
- Más superficie de tests (5 archivos nuevos)

### Lo que habrá que revisar después
- Si los tokens consumidos exceden lo previsto, mover a Haiku para anexos con `confianza` esperada alta
- Si los findings se vuelven repetitivos, agregar pocos-shot examples al prompt
- Cuando se agreguen anexos del 2026 (si SRI cambia el ICT), revisar el prompt template

---

## 11. Action Items para writing-plans

(El detalle granular saldrá del writing-plans skill, pero el spec ya identifica el build sequence de alto nivel)

1. [ ] Crear `backend/app/ict/audit/schemas.py` (Pydantic models)
2. [ ] Crear `backend/app/ict/audit/classifiers.py` (semaforos, umbrales)
3. [ ] Crear `backend/app/ict/audit/metrics.py` (compute_a1, compute_anexos)
4. [ ] Tests unitarios de schemas + classifiers + metrics
5. [ ] Crear `backend/app/ict/audit/prompts/auditor_tributario_ec.md`
6. [ ] Crear `backend/app/ict/audit/interpreter.py` con Anthropic SDK
7. [ ] Tests de interpreter con mock + caso real PROPHAR (registro de respuesta para snapshot)
8. [ ] Crear `backend/app/ict/fillers/kpi_components.py`
9. [ ] Tests visuales de kpi_components
10. [ ] Refactor `verification.py` (consume metrics + kpi + interpretation A1)
11. [ ] Refactor `auditoria_anexos.py` (consume metrics + kpi + interpretation A1..A9)
12. [ ] Refactor `service.py` para devolver tuple[bytes_sri, bytes_papel]
13. [ ] Endpoint `GET /ict/sessions/{id}/papel-trabajo`
14. [ ] Migrar tests existentes que asumían hojas auditoría en Excel SRI → papel_trabajo
15. [ ] Frontend: 2 botones de descarga + tooltips
16. [ ] Verificación empírica con PROPHAR + commit + push
17. [ ] Actualizar `CLAUDE.md` con dos reglas nuevas:
    - **Regla "separación SRI vs auditoría"**: El Excel que se entrega para cargar al SRI
      NUNCA contiene hojas internas (VERIFICACIÓN A1, AUDITORÍA DE ANEXOS, debug, logs).
      Si una hoja existe SOLO para uso interno del auditor, debe ir en el archivo
      `..._PAPEL_TRABAJO.xlsx` separado.
    - **Regla "interpretación IA con disclaimer"**: toda interpretación generada por LLM
      en artefactos del ICT debe (a) pasar por QA evaluator, (b) registrar audit trail,
      (c) llevar disclaimer visible, (d) exponer campo `confianza_modelo` al usuario.
18. [ ] Update endpoints documentation (OpenAPI/Swagger) con el nuevo endpoint
    `/papel-trabajo`

---

## 12. Documentos de referencia

- Spec ICT 2025: `docs/superpowers/specs/2026-05-30-ict-2025-design.md`
- Regla suprema verificación: `CLAUDE.md` sección 1
- Formato profesional anexos: `CLAUDE.md` sección "Formato de los anexos del ICT"
- Catálogos SRI oficiales: `backend/app/ict/catalogo_f101.py`, `f103.py`, `f104.py`
- Skills AuditBrain reutilizadas:
  - `auditbrain-audit-findings` (Skill ID 006) — estructura Condición-Criterio-Causa-Efecto
  - `auditbrain-ai-response-quality-evaluator` (Skill ID 050) — QA del output LLM
  - `auditbrain-audit-trail-generator` (Skill ID 049) — bitácora obligatoria
  - `auditbrain-financial-variance-analysis` — análisis de variaciones
- Skills externos:
  - `finance:reconciliation`, `finance:audit-support`, `finance:variance-analysis`
  - `data:validate-data`, `data:data-visualization`
  - `superpowers:verification-before-completion` (regla suprema)
