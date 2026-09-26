"""Base legal tributaria SUGERIDA por herramienta NIIF (Ecuador).

Pre-llena el recuadro «Tratamiento tributario revisado y su sustento» de la vista
de trabajo. La sugerencia viaja en la definición de cada procesador (campo
``tributario_sugerido``), se puede editar, y el auditor debe marcar «Revisé la
base legal sugerida y estoy conforme» antes de «Confirmar base técnica».

REGLA (decisión del socio): cada cita se verifica contra fuente oficial (SRI /
Registro Oficial / normativa vigente al ejercicio) ANTES de dejarla. Lo que no se
pudo confirmar aquí va marcado ``verificar=True`` y se presenta con el prefijo
«VERIFICAR — …»; NO se presenta como vigente y el gate de confirmación no se
habilita mientras quede un «VERIFICAR» sin resolver. NO se inventan artículos ni
porcentajes: si no hay certeza, se marca para verificación humana.

Estructura de cada cita: {norma, ref, dice, efecto, url, verificar}.
"""
from __future__ import annotations

SRI = "https://www.sri.gob.ec/normativa-tributaria"
LEY_CIAS = "https://www.supercias.gob.ec/portalscvs/ (Ley de Compañías)"

# Citas confirmadas (verificar=False) y por confirmar (verificar=True).
BASE_LEGAL: dict[str, list[dict]] = {
    # --- Cartera / incobrables: régimen bien establecido -------------------
    "perdidas_incurridas_s11": [
        {"norma": "LRTI", "ref": "Art. 10 núm. 11 y Reglamento LRTI",
         "dice": "Provisiones para créditos incobrables: deducibles hasta el 1 % anual de los créditos comerciales concedidos y pendientes de recaudación al cierre, sin que la provisión acumulada exceda el 10 % de la cartera total.",
         "efecto": "Limita el gasto por deterioro deducible; el exceso es no deducible y genera diferencia temporaria.",
         "url": SRI, "verificar": False},
        {"norma": "NIIF para las PYMES", "ref": "Sección 29 (NIC 12 en NIIF completas)",
         "dice": "Impuesto diferido por diferencias temporarias entre el deterioro contable y el fiscalmente deducible.",
         "efecto": "Activo por impuesto diferido sobre la parte no deducible mientras sea recuperable.",
         "url": SRI, "verificar": False},
    ],
    "pce_simplificada_niif9": [
        {"norma": "LRTI", "ref": "Art. 10 núm. 11 y Reglamento LRTI",
         "dice": "Provisiones para créditos incobrables: deducibles hasta el 1 % anual de los créditos comerciales pendientes al cierre, tope acumulado del 10 % de la cartera.",
         "efecto": "La pérdida esperada (NIIF 9) que exceda el límite fiscal es no deducible; diferencia temporaria.",
         "url": SRI, "verificar": False},
        {"norma": "NIC 12 / Sección 29 PYMES", "ref": "impuesto diferido",
         "dice": "Diferencia temporaria entre la PCE contable y el deterioro fiscalmente admitido.",
         "efecto": "Activo por impuesto diferido sobre lo no deducible.", "url": SRI, "verificar": False},
    ],
    "cxc_cartera": [
        {"norma": "LRTI", "ref": "Art. 10 núm. 11 y Reglamento LRTI",
         "dice": "Créditos incobrables: provisión deducible hasta el 1 % anual, tope acumulado del 10 % de la cartera.",
         "efecto": "Acota el deterioro deducible; el exceso es diferencia temporaria.", "url": SRI, "verificar": False},
    ],
    # --- Gastos / nómina / provisiones / patrimonio / impuestos -----------
    "gastos_analisis": [
        {"norma": "LRTI", "ref": "Art. 10 (regla general de deducibilidad)",
         "dice": "Son deducibles los costos y gastos necesarios para obtener, mantener y mejorar la renta gravada, debidamente sustentados.",
         "efecto": "Los gastos sin sustento o no relacionados con la renta gravada son no deducibles.",
         "url": SRI, "verificar": False},
        {"norma": "Reglamento para la aplicación de la LRTI", "ref": "Art. 27 (bancarización, reforma 2024)",
         "dice": "Los costos y gastos superiores al umbral pagados sin usar el sistema financiero no son deducibles.",
         "efecto": "Revisar el medio de pago de los gastos relevantes antes de deducirlos.",
         "url": SRI, "verificar": False},
        {"norma": "LRTI · precios de transferencia / partes relacionadas", "ref": "artículo/numeral por confirmar",
         "dice": "Gastos con partes relacionadas: sujetos a principio de plena competencia y límites específicos.",
         "efecto": "Puede limitar la deducibilidad de gastos con relacionadas.", "url": SRI, "verificar": True},
    ],
    "nomina_beneficios": [
        {"norma": "LRTI", "ref": "Art. 10 núm. 9",
         "dice": "Sueldos, salarios y beneficios sociales son deducibles siempre que se haya aportado al IESS sobre ellos.",
         "efecto": "La remuneración sobre la que no se aportó al IESS es no deducible.", "url": SRI, "verificar": False},
        {"norma": "LRTI · provisiones de jubilación patronal y desahucio", "ref": "numeral y condiciones por confirmar",
         "dice": "Deducibles con estudio actuarial y para trabajadores con el tiempo mínimo de servicio que fija la norma.",
         "efecto": "Sin estudio actuarial o sin el tiempo mínimo, la provisión es no deducible.", "url": SRI, "verificar": True},
    ],
    "provisiones_contingencias": [
        {"norma": "LRTI", "ref": "Art. 10 (deducibilidad)",
         "dice": "Las provisiones y estimaciones no son deducibles salvo las expresamente permitidas por la ley; se deducen al realizarse el gasto.",
         "efecto": "La provisión contable genera diferencia temporaria hasta que el gasto se realiza y cumple los requisitos.",
         "url": SRI, "verificar": False},
    ],
    "patrimonio": [
        {"norma": "Ley de Compañías", "ref": "Art. 297 (S.A.) y Art. 109 (Cía. Ltda.)",
         "dice": "Reserva legal: la S.A. segrega el 10 % de las utilidades hasta alcanzar el 50 % del capital; la Cía. Ltda., el 5 % hasta el 20 % del capital.",
         "efecto": "Delimita lo distribuible; los ajustes de transición a NIIF quedan fuera de lo distribuible.",
         "url": LEY_CIAS, "verificar": False},
    ],
    "impuesto_corriente_diferido": [
        {"norma": "NIC 12 / Sección 29 PYMES", "ref": "impuesto diferido",
         "dice": "Reconocimiento de activos y pasivos por impuesto diferido sobre diferencias temporarias.",
         "efecto": "Mide el diferido; su recuperación depende de rentas gravadas futuras.", "url": SRI, "verificar": False},
        {"norma": "LRTI · tarifa de sociedades y conciliación tributaria", "ref": "tarifa base 25 %; recargo y artículos por confirmar",
         "dice": "Tarifa general del impuesto a la renta de sociedades del 25 %; puede variar por composición societaria/paraísos fiscales.",
         "efecto": "Fija la tasa del cálculo del diferido; confirmar recargos aplicables al ejercicio.", "url": SRI, "verificar": True},
    ],
    # --- Herramientas cuyo detalle fiscal se deja para verificación --------
    "inventarios_costos": [
        {"norma": "NIC 2 / Sección 13 PYMES", "ref": "medición al menor entre costo y VNR",
         "dice": "El inventario se mide al menor entre el costo y el valor neto de realización.",
         "efecto": "Base contable de la pérdida por deterioro.", "url": SRI, "verificar": False},
        {"norma": "Reglamento LRTI · mermas y bajas de inventario", "ref": "artículo y condiciones por confirmar",
         "dice": "Deducibilidad de mermas y bajas sujeta a los límites y formalidades del reglamento.",
         "efecto": "La pérdida de inventario puede ser no deducible sin el sustento exigido.", "url": SRI, "verificar": True},
    ],
    "ppe_propiedad_planta": [
        {"norma": "Reglamento LRTI · depreciación", "ref": "porcentajes máximos por tipo de activo (por confirmar)",
         "dice": "La depreciación es deducible hasta los porcentajes máximos que fija el reglamento por tipo de activo.",
         "efecto": "La depreciación contable que exceda el máximo fiscal es diferencia temporaria.", "url": SRI, "verificar": True},
        {"norma": "NIIF · costos por préstamos", "ref": "NIC 23 / Sección 25 PYMES",
         "dice": "En PYMES los costos por préstamos se reconocen como gasto; en NIIF completas pueden capitalizarse en activos aptos.",
         "efecto": "Afecta la base del activo y la depreciación deducible.", "url": SRI, "verificar": False},
    ],
    "propiedades_inversion": [
        {"norma": "NIC 40 / Sección 16 PYMES", "ref": "valor razonable",
         "dice": "Las propiedades de inversión pueden medirse a valor razonable con cambios en resultados.",
         "efecto": "Los cambios de valor razonable no realizados no son renta gravada hasta su realización (confirmar).",
         "url": SRI, "verificar": True},
    ],
    "arrendamientos": [
        {"norma": "NIIF 16 / Sección 20 PYMES", "ref": "reconocimiento del arrendamiento",
         "dice": "Reconocimiento del derecho de uso y el pasivo (NIIF 16) o financiero/operativo (PYMES).",
         "efecto": "El tratamiento fiscal del arrendamiento en Ecuador puede diferir de NIIF 16: confirmar deducibilidad del gasto.",
         "url": SRI, "verificar": True},
    ],
    "intangibles_goodwill": [
        {"norma": "NIC 38 / NIIF 3 / Secciones 18-19 PYMES", "ref": "amortización y plusvalía",
         "dice": "Amortización de intangibles de vida definida; la plusvalía se somete a deterioro (o se amortiza en PYMES).",
         "efecto": "Deducibilidad de la amortización y tratamiento fiscal de la plusvalía: confirmar.", "url": SRI, "verificar": True},
    ],
    "activos_biologicos": [
        {"norma": "NIC 41 / Sección 34 PYMES", "ref": "valor razonable menos costos de venta",
         "dice": "Los activos biológicos se miden a valor razonable menos costos de venta cuando es medible con fiabilidad.",
         "efecto": "Tratamiento fiscal del cambio de valor razonable no realizado: confirmar.", "url": SRI, "verificar": True},
    ],
    "seguros_cobertura": [
        {"norma": "NIIF 17 / NIIF 9", "ref": "contratos de seguro y cobertura",
         "dice": "Medición de contratos de seguro y contabilidad de coberturas.",
         "efecto": "Deducibilidad de primas y reservas técnicas y su momento fiscal: confirmar.", "url": SRI, "verificar": True},
    ],
    "proveedores_cxp": [
        {"norma": "Reglamento LRTI · bancarización y retenciones", "ref": "Art. 27 (bancarización); retenciones por confirmar",
         "dice": "Costos y gastos por sobre el umbral deben pagarse por el sistema financiero para ser deducibles; aplicar retenciones en la fuente.",
         "efecto": "Pagos sin bancarizar o sin retención pueden ser no deducibles.", "url": SRI, "verificar": True},
    ],
    "inversiones_instrumentos": [
        {"norma": "NIIF 9 / Sección 11-12 PYMES", "ref": "instrumentos financieros",
         "dice": "Clasificación y medición de inversiones (costo amortizado o valor razonable).",
         "efecto": "Rendimientos gravados y tratamiento del valor razonable no realizado: confirmar.", "url": SRI, "verificar": True},
    ],
    "efectivo_equivalentes": [
        {"norma": "NIC 21 / Sección 30 PYMES", "ref": "diferencias de cambio",
         "dice": "Conversión de partidas en moneda extranjera y reconocimiento de diferencias de cambio.",
         "efecto": "Tratamiento fiscal de las diferencias de cambio realizadas/no realizadas: confirmar.", "url": SRI, "verificar": True},
    ],
    "ingresos_contratos": [
        {"norma": "NIIF 15 / Sección 23 PYMES", "ref": "reconocimiento de ingresos",
         "dice": "El ingreso se reconoce al transferirse el control de bienes/servicios (5 pasos).",
         "efecto": "El momento fiscal del ingreso (devengado) y el tratamiento de anticipos: confirmar.", "url": SRI, "verificar": True},
    ],
    # --- Planificación de la auditoría ------------------------------------
    "planificacion_nia": [
        {"norma": "LRTI · Informe de cumplimiento tributario", "ref": "Art. 102 y Reglamento LRTI (artículo por confirmar)",
         "dice": "Los auditores externos emiten, junto con el informe de auditoría, un informe sobre el cumplimiento de las obligaciones tributarias del sujeto auditado.",
         "efecto": "Planificar en la estrategia global los procedimientos y el calendario del Informe de Cumplimiento Tributario.",
         "url": SRI, "verificar": True},
        {"norma": "Ley de Compañías y resoluciones de la Superintendencia de Compañías", "ref": "obligación de auditoría externa (umbral por confirmar)",
         "dice": "Las compañías que superan el umbral de activos fijado por la Superintendencia deben someter sus estados financieros a auditoría externa.",
         "efecto": "Confirmar la obligación, el plazo de presentación y el marco (NIIF completas o PYMES) en la aceptación y la estrategia del encargo.",
         "url": LEY_CIAS, "verificar": True},
    ],
    "prestamos_obligaciones": [
        {"norma": "LRTI · deducibilidad de intereses", "ref": "Art. 10 núm. 2 y regla de subcapitalización (por confirmar)",
         "dice": "Los intereses de deudas para la actividad son deducibles; existe un límite por subcapitalización con partes relacionadas.",
         "efecto": "Los intereses sobre el límite de subcapitalización son no deducibles; confirmar el ratio vigente.",
         "url": SRI, "verificar": True},
        {"norma": "NIIF 9 / Sección 11 PYMES", "ref": "costo amortizado / prueba del 10 %",
         "dice": "Las obligaciones se miden a costo amortizado; una modificación sustancial (prueba del 10 %) puede dar de baja el pasivo.",
         "efecto": "Efecto en resultados de la modificación; su tratamiento fiscal: confirmar.", "url": SRI, "verificar": True},
    ],
}


def _linea(c: dict) -> str:
    cuerpo = f"{c['norma']} · {c['ref']}: {c['dice']} Efecto en la prueba: {c['efecto']}"
    return ("VERIFICAR — " + cuerpo + " (confirmar artículo/numeral y vigencia en fuente oficial)") if c.get("verificar") else cuerpo


def citas(processor: str) -> list[dict]:
    return BASE_LEGAL.get(processor or "", [])


def texto_sugerido(processor: str) -> str:
    """Texto pre-llenado del recuadro tributario para una herramienta."""
    cs = citas(processor)
    if not cs:
        return ""
    intro = "Base legal sugerida (revísela y confírmela contra la fuente oficial antes de aceptar):"
    return intro + "\n" + "\n".join(f"• {_linea(c)}" for c in cs)


def sugerencia(processor: str) -> dict | None:
    """El objeto que viaja en la definición del procesador (``tributario_sugerido``)."""
    cs = citas(processor)
    if not cs:
        return None
    return {"citas": cs, "texto": texto_sugerido(processor),
            "tiene_verificar": any(c.get("verificar") for c in cs)}
