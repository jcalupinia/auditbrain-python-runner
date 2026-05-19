"""Catálogo de módulos sectoriales y su identidad cognitiva.

Cada módulo expone:
- ``code``: ID corto que aparece en sidebar y crumb (ADV, AUD, ...).
- ``label``: nombre comercial.
- ``tagline``: una línea para el header del módulo.
- ``description``: 1-2 líneas para la landing.
- ``system_prompt``: instrucciones especializadas que se concatenan al
  system prompt base del agente.
- ``suggested_actions``: prompts/acciones recomendadas (sugerencias
  clickables en la UI; no son comandos automáticos).
- ``kpi_hints``: KPIs típicos que la UI puede pintar; valores reales
  llegarán cuando haya datos del proyecto (Fase 2+ avanzada).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleDef:
    code: str
    label: str
    tagline: str
    description: str
    system_prompt: str
    suggested_actions: tuple[str, ...]
    kpi_hints: tuple[str, ...]


MODULES: tuple[ModuleDef, ...] = (
    ModuleDef(
        code="ADV",
        label="Executive Advisory",
        tagline="Consejo ejecutivo y estrategia",
        description=(
            "Asistencia a comités, planes estratégicos, due diligence y "
            "decisiones de inversión a nivel C-suite."
        ),
        system_prompt=(
            "Actúas como Executive Advisor senior. Responde con framing "
            "ejecutivo: tesis principal, riesgos, decisión recomendada y "
            "próximos pasos. Usa marcos como SWOT, Porter, MECE cuando aporten."
        ),
        suggested_actions=(
            "Resumen ejecutivo del proyecto activo",
            "Riesgos críticos a 90 días",
            "Decisión recomendada con trade-offs",
        ),
        kpi_hints=("ROI", "Payback", "TIR", "Riesgo agregado"),
    ),
    ModuleDef(
        code="AUD",
        label="External Audit",
        tagline="Auditoría financiera externa",
        description=(
            "Planificación, ejecución y opinión de auditoría conforme NIA. "
            "Detección de riesgos, materialidad y muestreo."
        ),
        system_prompt=(
            "Actúas como Auditor externo certificado. Refiere NIA/IFRS cuando "
            "aplique. Sé explícito sobre materialidad, hallazgos, control "
            "interno y opiniones (limpia, con salvedades, adversa, abstención)."
        ),
        suggested_actions=(
            "Plan de auditoría para el período activo",
            "Pruebas sustantivas sobre cuentas clave",
            "Borrador de carta de gerencia",
        ),
        kpi_hints=("Materialidad", "Cobertura", "Hallazgos críticos", "Tiempo restante"),
    ),
    ModuleDef(
        code="TAX",
        label="Tax Structuring",
        tagline="Estructuración fiscal",
        description=(
            "Optimización fiscal corporativa, precios de transferencia y "
            "cumplimiento BEPS/Pillar Two."
        ),
        system_prompt=(
            "Actúas como Tax Partner. Sé preciso con la jurisdicción: si no "
            "se especifica, pídela. Cita el código tributario aplicable cuando "
            "puedas y marca claramente cuando una sugerencia requiere ruling."
        ),
        suggested_actions=(
            "Análisis de impacto fiscal de la operación",
            "Riesgos de precios de transferencia",
            "Checklist BEPS/Pillar Two",
        ),
        kpi_hints=("Tasa efectiva", "Ahorro estimado", "Riesgo regulatorio"),
    ),
    ModuleDef(
        code="LEG",
        label="Legal Intelligence",
        tagline="Inteligencia legal",
        description=(
            "Análisis de contratos, due diligence legal, cumplimiento "
            "normativo y litigios."
        ),
        system_prompt=(
            "Actúas como Counsel senior. Aclara siempre si una respuesta es "
            "general o requiere asesoría legal jurisdiccional. Identifica "
            "cláusulas críticas y riesgos contractuales."
        ),
        suggested_actions=(
            "Resumen de cláusulas críticas del contrato",
            "Riesgos legales del proyecto activo",
            "Checklist de cumplimiento sectorial",
        ),
        kpi_hints=("Riesgos abiertos", "Cláusulas sensibles", "Litigios activos"),
    ),
    ModuleDef(
        code="FIN",
        label="CFO Intelligence",
        tagline="Finanzas corporativas",
        description=(
            "FP&A, modelos de valoración, cash management y reporting al "
            "directorio."
        ),
        system_prompt=(
            "Actúas como CFO advisor. Habla en términos de EBITDA, free cash "
            "flow, working capital y palancas de valor. Aporta sensibilidades "
            "cuando proyectes."
        ),
        suggested_actions=(
            "Modelo de valoración DCF rápido",
            "Análisis de working capital",
            "Forecast 13 semanas de caja",
        ),
        kpi_hints=("EBITDA", "FCF", "DSCR", "Liquidez"),
    ),
    ModuleDef(
        code="CYB",
        label="Cybersecurity & IT Audit",
        tagline="Ciberseguridad y auditoría TI",
        description=(
            "Madurez NIST/ISO 27001, evaluación de controles, gestión de "
            "vulnerabilidades y resiliencia."
        ),
        system_prompt=(
            "Actúas como CISO advisor. Mapea hallazgos a controles NIST CSF / "
            "ISO 27001. Distingue claramente entre riesgo aceptable, mitigable "
            "y transferible."
        ),
        suggested_actions=(
            "Evaluación NIST CSF de la organización",
            "Plan de remediación de vulnerabilidades",
            "Postura ante un ransomware genérico",
        ),
        kpi_hints=("Madurez NIST", "Vulnerabilidades críticas", "Tiempo de detección"),
    ),
    ModuleDef(
        code="DATA",
        label="Data & BI Intelligence",
        tagline="Datos y BI",
        description=(
            "Modelado analítico, calidad de datos, governance y construcción "
            "de dashboards ejecutivos."
        ),
        system_prompt=(
            "Actúas como Data & Analytics lead. Razona en términos de "
            "métricas, dimensiones, granularidad y calidad de datos. Sugiere "
            "visualizaciones específicas para cada pregunta."
        ),
        suggested_actions=(
            "Modelo dimensional para el caso de uso",
            "Issues de calidad de datos a vigilar",
            "Dashboards ejecutivos prioritarios",
        ),
        kpi_hints=("Cobertura métrica", "% datos completos", "Latencia"),
    ),
    ModuleDef(
        code="AUT",
        label="Automation Core",
        tagline="Automatización de procesos",
        description=(
            "Identificación de procesos automatizables, RPA, scripts Python "
            "y orquestación documental."
        ),
        system_prompt=(
            "Actúas como Automation lead. Cuando proceda, propón scripts "
            "concretos (puedes invocar el Motor de Ejecución del propio "
            "AuditBrain) o flujos RPA. Estima ahorro de horas."
        ),
        suggested_actions=(
            "Procesos candidatos a automatización",
            "Script Python de muestreo estadístico",
            "ROI estimado de la automatización",
        ),
        kpi_hints=("Horas ahorradas", "Procesos automatizados", "Backlog"),
    ),
    ModuleDef(
        code="GOV",
        label="Governance Layer",
        tagline="Gobierno corporativo",
        description=(
            "Buenas prácticas de gobierno, matrices de delegación, comités, "
            "ESG y reporte al directorio."
        ),
        system_prompt=(
            "Actúas como advisor de Gobierno Corporativo. Refiere códigos de "
            "buen gobierno aplicables y separa claramente recomendaciones "
            "mandatorias vs. mejores prácticas."
        ),
        suggested_actions=(
            "Matriz RACI del proyecto activo",
            "Estado de cumplimiento ESG",
            "Agenda recomendada del próximo comité",
        ),
        kpi_hints=("Cumplimiento normativo", "Riesgos ESG", "Cobertura comités"),
    ),
    ModuleDef(
        code="MKT",
        label="Marketing Intelligence",
        tagline="Inteligencia de marketing",
        description=(
            "Análisis de mercado, posicionamiento, embudo y atribución."
        ),
        system_prompt=(
            "Actúas como CMO advisor. Razona en términos de TAM/SAM/SOM, "
            "ICP, embudo y unit economics de adquisición (CAC, LTV)."
        ),
        suggested_actions=(
            "Análisis TAM/SAM/SOM",
            "Buyer personas e ICP",
            "Métricas de embudo a vigilar",
        ),
        kpi_hints=("CAC", "LTV", "Tasa de conversión", "Share of voice"),
    ),
    ModuleDef(
        code="CRE",
        label="Creative Studio",
        tagline="Estudio creativo",
        description=(
            "Generación de contenidos ejecutivos, presentaciones, narrativas "
            "y mensajes para stakeholders."
        ),
        system_prompt=(
            "Actúas como Creative Director ejecutivo. Genera narrativas, "
            "outlines de presentación, slides recomendadas y mensajes clave. "
            "Sé claro, directo, sin floritura corporativa."
        ),
        suggested_actions=(
            "Outline de presentación para el directorio",
            "Mensajes clave para stakeholders",
            "Narrativa del caso de negocio",
        ),
        kpi_hints=("Piezas en producción", "Aprobaciones pendientes"),
    ),
)


_BY_CODE = {m.code: m for m in MODULES}


def get_module(code: str | None) -> ModuleDef | None:
    if not code:
        return None
    return _BY_CODE.get(code.upper())


def all_modules() -> tuple[ModuleDef, ...]:
    return MODULES
