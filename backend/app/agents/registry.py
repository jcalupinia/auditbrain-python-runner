"""Catálogo estático de agentes especializados.

Cada agente declara: code, label, descripción, módulo al que pertenece,
prompt de sistema (server-only), forma de los inputs y ejemplo.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentInput:
    name: str
    label: str
    kind: str = "text"          # text | textarea | number | select
    required: bool = True
    options: tuple[str, ...] = field(default_factory=tuple)
    placeholder: str = ""


@dataclass(frozen=True)
class AgentDef:
    code: str                   # ej. "AUD.plan-de-auditoria"
    module_code: str            # ADV / AUD / TAX ...
    label: str
    description: str
    system_prompt: str          # server-only
    inputs: tuple[AgentInput, ...]
    output_hint: str = ""       # qué esperar en el output (para la UI)


AGENTS: tuple[AgentDef, ...] = (
    AgentDef(
        code="ADV.resumen-ejecutivo",
        module_code="ADV",
        label="Resumen ejecutivo",
        description=(
            "Genera un resumen ejecutivo a partir de un brief, con tesis, "
            "riesgos, decisión recomendada y próximos pasos."
        ),
        system_prompt=(
            "Eres un Executive Advisor. Devuelve un resumen ejecutivo en "
            "Markdown con estas secciones EXACTAS: ## Tesis, ## Riesgos "
            "clave, ## Decisión recomendada, ## Próximos pasos. Conciso y directo."
        ),
        inputs=(
            AgentInput("brief", "Brief / situación", kind="textarea",
                       placeholder="Describe el contexto, la decisión a tomar y los datos clave…"),
            AgentInput("horizon", "Horizonte temporal", kind="select",
                       options=("30 días", "90 días", "12 meses"), required=False),
        ),
        output_hint="Markdown estructurado",
    ),
    AgentDef(
        code="AUD.plan-de-auditoria",
        module_code="AUD",
        label="Plan de auditoría",
        description=(
            "Esboza un plan de auditoría externa para el período indicado, "
            "alineado a NIA, con áreas críticas, materialidad orientativa y "
            "pruebas sugeridas."
        ),
        system_prompt=(
            "Eres un Auditor externo certificado. Devuelve un plan de "
            "auditoría en Markdown con: ## Alcance, ## Materialidad orientativa, "
            "## Riesgos significativos, ## Pruebas sustantivas, ## Cronograma. "
            "Referencia NIA donde aplique."
        ),
        inputs=(
            AgentInput("entity", "Entidad auditada", placeholder="Razón social"),
            AgentInput("period", "Período", placeholder="AF 2026 / Q1 2026"),
            AgentInput("sector", "Sector", required=False, placeholder="Industria, retail, banca…"),
            AgentInput("notes", "Notas adicionales", kind="textarea", required=False,
                       placeholder="Riesgos conocidos, sistemas, equipo…"),
        ),
        output_hint="Plan de auditoría en Markdown",
    ),
    AgentDef(
        code="TAX.impacto-fiscal",
        module_code="TAX",
        label="Impacto fiscal de una operación",
        description=(
            "Analiza el impacto fiscal estimado de una operación corporativa "
            "en la jurisdicción indicada."
        ),
        system_prompt=(
            "Eres un Tax Partner. Devuelve análisis en Markdown con: "
            "## Hechos relevantes, ## Tratamiento fiscal, ## Riesgos, "
            "## Recomendaciones. Si la jurisdicción no es clara, pídela."
        ),
        inputs=(
            AgentInput("jurisdiction", "Jurisdicción", placeholder="País o subdivisión"),
            AgentInput("operation", "Operación", kind="textarea",
                       placeholder="Describe la operación (M&A, reorg, dividendo…)."),
        ),
        output_hint="Análisis fiscal en Markdown",
    ),
    AgentDef(
        code="LEG.revision-clausulas",
        module_code="LEG",
        label="Revisión de cláusulas críticas",
        description=(
            "Identifica cláusulas críticas y riesgos en un texto contractual."
        ),
        system_prompt=(
            "Eres Counsel senior. Devuelve análisis en Markdown con: "
            "## Cláusulas críticas (lista numerada con cita corta), "
            "## Riesgos legales, ## Recomendaciones de redacción."
        ),
        inputs=(
            AgentInput("text", "Texto del contrato (o extracto)", kind="textarea",
                       placeholder="Pega el clausulado relevante…"),
            AgentInput("jurisdiction", "Jurisdicción", required=False),
        ),
        output_hint="Análisis legal en Markdown",
    ),
    AgentDef(
        code="FIN.dcf-rapido",
        module_code="FIN",
        label="DCF rápido",
        description=(
            "Esboza una valoración por DCF a partir de FCF, g y WACC."
        ),
        system_prompt=(
            "Eres un CFO advisor. A partir de los inputs, calcula y explica "
            "una valoración DCF rápida en Markdown: ## Supuestos, "
            "## Cálculo (paso a paso, con fórmulas), ## Sensibilidad ±1% "
            "WACC y g, ## Limitaciones."
        ),
        inputs=(
            AgentInput("fcf", "FCF base (anual)", placeholder="ej. 1000000"),
            AgentInput("growth", "Crecimiento perpetuo g (%)", placeholder="ej. 2.5"),
            AgentInput("wacc", "WACC (%)", placeholder="ej. 8.5"),
        ),
        output_hint="Valoración DCF en Markdown",
    ),
    AgentDef(
        code="CYB.eval-nist",
        module_code="CYB",
        label="Evaluación NIST CSF rápida",
        description=(
            "Evalúa madurez NIST CSF (Identify/Protect/Detect/Respond/Recover) "
            "a partir de una descripción del entorno."
        ),
        system_prompt=(
            "Eres CISO advisor. Devuelve evaluación NIST CSF en Markdown "
            "con tabla de madurez (1-5) por función y recomendaciones top 5."
        ),
        inputs=(
            AgentInput("environment", "Descripción del entorno", kind="textarea",
                       placeholder="Tamaño, stack, controles actuales, incidentes…"),
        ),
        output_hint="Evaluación NIST CSF en Markdown",
    ),
    AgentDef(
        code="DATA.modelo-dimensional",
        module_code="DATA",
        label="Modelo dimensional",
        description=(
            "Diseña un modelo dimensional (hechos + dimensiones) para el caso "
            "de uso descrito."
        ),
        system_prompt=(
            "Eres Data lead. Devuelve diseño en Markdown con: "
            "## Hechos (granularidad), ## Dimensiones, ## Métricas, ## DDL SQL."
        ),
        inputs=(
            AgentInput("use_case", "Caso de uso", kind="textarea",
                       placeholder="Pregunta de negocio y datos disponibles…"),
        ),
        output_hint="Diseño dimensional en Markdown",
    ),
    AgentDef(
        code="AUT.candidatos-rpa",
        module_code="AUT",
        label="Candidatos a automatización",
        description=(
            "Identifica procesos candidatos a automatización con ROI estimado."
        ),
        system_prompt=(
            "Eres Automation lead. Devuelve tabla en Markdown con columnas: "
            "Proceso · Frecuencia · Horas/mes · Esfuerzo automatización · "
            "Ahorro estimado · Prioridad."
        ),
        inputs=(
            AgentInput("processes", "Procesos manuales actuales", kind="textarea",
                       placeholder="Lista los procesos repetitivos del equipo…"),
        ),
        output_hint="Tabla de candidatos RPA",
    ),
    AgentDef(
        code="GOV.matriz-raci",
        module_code="GOV",
        label="Matriz RACI",
        description=(
            "Construye una matriz RACI para el proyecto o proceso descrito."
        ),
        system_prompt=(
            "Eres advisor de Gobierno. Devuelve matriz RACI en Markdown "
            "(tabla con actividades en filas y roles en columnas)."
        ),
        inputs=(
            AgentInput("activities", "Actividades", kind="textarea",
                       placeholder="Una por línea"),
            AgentInput("roles", "Roles", kind="textarea",
                       placeholder="Una por línea (ej. CFO, Controller, Auditor…)"),
        ),
        output_hint="Matriz RACI en Markdown",
    ),
    AgentDef(
        code="MKT.tam-sam-som",
        module_code="MKT",
        label="Análisis TAM/SAM/SOM",
        description=(
            "Estima TAM/SAM/SOM para un negocio y mercado dados, con metodología."
        ),
        system_prompt=(
            "Eres CMO advisor. Devuelve análisis TAM/SAM/SOM en Markdown con "
            "## Definiciones, ## Metodología, ## Estimaciones (con supuestos), "
            "## Limitaciones."
        ),
        inputs=(
            AgentInput("product", "Producto/servicio", kind="textarea"),
            AgentInput("market", "Mercado / geografía", kind="textarea"),
        ),
        output_hint="Análisis de mercado en Markdown",
    ),
    AgentDef(
        code="CRE.outline-presentacion",
        module_code="CRE",
        label="Outline de presentación",
        description=(
            "Genera el outline de una presentación ejecutiva (8-12 slides)."
        ),
        system_prompt=(
            "Eres Creative Director ejecutivo. Devuelve outline en Markdown: "
            "una sección por slide con número, título, bullets clave y "
            "mensaje a recordar. 8 a 12 slides."
        ),
        inputs=(
            AgentInput("topic", "Tema / objetivo", kind="textarea",
                       placeholder="A quién y para qué…"),
            AgentInput("duration", "Duración objetivo (min)", required=False,
                       placeholder="ej. 20"),
        ),
        output_hint="Outline de slides en Markdown",
    ),
)


_BY_CODE = {a.code: a for a in AGENTS}


def get_agent(code: str) -> AgentDef | None:
    return _BY_CODE.get(code)


def list_agents(module_code: str | None = None) -> list[AgentDef]:
    if not module_code:
        return list(AGENTS)
    code = module_code.upper()
    return [a for a in AGENTS if a.module_code == code]
