"""Planificación de la auditoría con los documentos de entrada del encargo (NIA 300, 315, 320, 240, 570, 330, 510).

Versión 2 (2026-09-26, pedido del dueño: «los documentos de entrada de la planificación son los del
cronograma del artefacto»). Replica el flujo del «Análisis de auditoría» (artefacto AuditBrain, v19) y del
módulo FIN-AP (Análisis financiero y revisión analítica preliminar):

Documentos de entrada (requerimientos al cliente):

- ``balance_anterior`` (obligatorio): balance de comprobación al cierre del año anterior (auditado), tal
  como lo exporta el sistema contable: código, nombre y saldo de TODAS las cuentas (con sus niveles).
- ``balance_actual`` (obligatorio, principal): balance de comprobación a la fecha de corte que se audita
  (diciembre en la auditoría final; el corte de la visita en la preliminar).
- ``resultados_mismo_corte`` (opcional): estado de resultados del año anterior AL MISMO CORTE (revisión preliminar).
  Si no se entrega, el ERI anterior se prorratea: diciembre ÷ 12 × meses transcurridos.
- ``carta_control_interno`` (opcional): hallazgos de la carta de control interno → matriz de riesgos
  (probabilidad × impacto = riesgo inherente; el control lo reduce al residual).
- ``informe_anterior`` (opcional): informe de auditoría del año anterior → perfil del encargo (identificación,
  opinión, salvedades, énfasis, empresa en funcionamiento, asuntos clave).
- ``notas_estados_financieros`` (opcional): notas a los estados financieros auditados del año anterior → notas
  comparativas y control de saldos de apertura (NIA 510).

Cálculo (todo en fórmulas de Excel, sin cifras pegadas):

1. Mapa de cuentas: la sección y la clasificación (corriente / no corriente) salen del prefijo del código
   (el prefijo más largo del mapa gana); nivel y cuentas de detalle, de la jerarquía de los códigos.
   Convención de signos automática por sección (se presentan en positivo por naturaleza).
2. Análisis horizontal y vertical de TODAS las cuentas; estados resumidos; cuadre del balance.
3. Índices (liquidez, actividad en días del período, endeudamiento, rentabilidad y DuPont) con semáforo
   y lectura.
4. Materialidad (NIA 320): base y porcentaje de la firma; desempeño 50 % y trivial 5 % por defecto
   (práctica, no prescritos por la NIA). En la revisión preliminar la base es el año anterior auditado.
5. Riesgos: matriz de la carta de control interno; posibles riesgos detectados en los balances; presunción
   de fraude en ingresos y elusión de controles (NIA 240); indicios de empresa en funcionamiento (NIA 570); asuntos
   del informe anterior. Control de calidad, anomalías, cuentas principales a revisar, programa (NIA 330),
   narrativa y estrategia global (NIA 300).

Las NIA se citan por su numeración en la versión en español del IAASB (NIA clarificadas; NIA 315 Revisada
2019). Pendiente M03: cotejar cada párrafo citado con el texto oficial vigente (VERIFICAR).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from backend.app.aud.niif.procesadores import planificacion_calidad as cal_m
from backend.app.aud.niif.procesadores import planificacion_enfoque as enf_m
from backend.app.aud.niif.procesadores import planificacion_encargo as enc_m
from backend.app.aud.niif.procesadores import problemas as _pr
from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num lo usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_fecha, a_num, campo, edicion_pymes, es_pymes, fx, hoja, m, n2, norm, problema, r2, ref, req,
    validar_campos, validar_definicion_generica,
)
from backend.app.aud.niif.procesadores.base import filas_mapeadas as _filas_mapeadas

VERSION = "planificacion_nia 2.0"
RUBRO = "PLANIFICACION"


def _sin_tildes(t) -> str:
    t = unicodedata.normalize("NFD", str(t or ""))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _si(v) -> bool:
    return _sin_tildes(v).strip().lower() in ("si", "s", "yes", "y", "x", "true", "1", "verdadero")


def _no(v) -> bool:
    return norm(v) in ("no", "n", "false", "0", "falso")


def _cod(v) -> str:
    """Código de cuenta como texto: 1101.0 (celda numérica de Excel) → 1101."""
    s = str(v if v is not None else "").strip()
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".")[0]
    return s


def _xr(x, d=2):
    """ROUND de Excel (mitad hacia afuera) sobre el número tal como Excel lo guarda (15 cifras)."""
    if x is None or x == "":
        return x
    q = Decimal(1).scaleb(-d)
    return float(Decimal(format(float(x), ".15g")).quantize(q, rounding=ROUND_HALF_UP))


def _div(a, b):
    return None if b in (0, None) or a is None else a / b


# --- herramientas del catálogo que responden a cada área (NIA 330) ------------------------------------------

HERRAMIENTAS = {
    "Caja y bancos": "Efectivo y equivalentes de efectivo",
    "Inversiones": "Inversiones e instrumentos financieros",
    "Cuentas por cobrar": "Cuentas por cobrar y deterioro",
    "Inventarios": "Inventarios, producción y costo de ventas",
    "Propiedad, planta y equipo": "Propiedad, planta y equipo",
    "Arrendamientos": "Arrendamientos",
    "Propiedades de inversión": "Propiedades de inversión",
    "Activos intangibles": "Activos intangibles y goodwill",
    "Activos biológicos": "Activos biológicos y agricultura",
    "Seguros": "Cobertura de seguros de activos",
    "Proveedores y cuentas por pagar": "Proveedores y cuentas por pagar",
    "Préstamos y obligaciones financieras": "Préstamos y obligaciones financieras",
    "Beneficios a empleados y nómina": "Beneficios sociales y nómina",
    "Provisiones y contingencias": "Provisiones y contingencias",
    "Impuestos": "Impuesto corriente y diferido",
    "Patrimonio": "Patrimonio",
    "Ingresos": "Ingresos · contratos con clientes",
    "Costos y gastos": "Gastos · análisis global",
    "Asientos de diario": "Motor de auditoría analítica (pruebas de asientos de diario)",
}
SIN_HERRAMIENTA = "Procedimientos del auditor (sin herramienta del catálogo)"

# Área por palabras clave (nombre de la cuenta o proceso de la carta de control interno, sin tildes).
_PALABRAS_AREA = [
    (("caja", "banco", "efectivo", "tesoreria"), "Caja y bancos"),
    (("inversion temporal", "inversiones temporales", "inversiones financieras", "instrumento"), "Inversiones"),
    (("cobrar", "cliente", "cartera", "incobrable"), "Cuentas por cobrar"),
    (("inventario", "mercader", "existencia", "bodega", "kardex", "costo de venta", "importacion"), "Inventarios"),
    (("derecho de uso", "arrendamiento"), "Arrendamientos"),
    (("propiedad de inversion", "propiedades de inversion"), "Propiedades de inversión"),
    (("propiedad", "planta", "equipo", "vehicul", "maquinari", "edificio", "terreno", "depreciacion", "activo fijo",
      "activos fijos"), "Propiedad, planta y equipo"),
    (("intangible", "software", "licencia", "goodwill", "plusvalia", "amortizacion"), "Activos intangibles"),
    (("biologic", "plantacion", "ganado"), "Activos biológicos"),
    (("seguro", "poliza"), "Seguros"),
    (("impuesto", " iva", "retencion", "tributari", "fiscal"), "Impuestos"),
    (("sueldo", "beneficio", "nomina", "iess", "jubilacion", "desahucio", "decimo", "vacacion", "participacion",
      "empleado", "trabajador", "actuarial"), "Beneficios a empleados y nómina"),
    (("proveedor", "por pagar", "compras"), "Proveedores y cuentas por pagar"),
    (("prestamo", "obligaciones bancarias", "obligaciones financieras", "sobregiro", "bancari", "financier", "interes"),
     "Préstamos y obligaciones financieras"),
    (("provision", "contingencia", "litigio", "juicio", "garantia"), "Provisiones y contingencias"),
    (("capital", "reserva", "patrimonio", "dividendo", "resultados acumulados"), "Patrimonio"),
    (("gasto", "publicidad", "honorario", "servicio"), "Costos y gastos"),
    (("venta", "ingreso", "factura", "promocion", "descuento", "nota de credito", "notas de credito"), "Ingresos"),
    (("asiento", "diario", "elusion", " ti ", "erp", "sistema", "acceso"), "Asientos de diario"),
]


def _area(texto: str, seccion: str = "") -> str:
    n = " " + _sin_tildes(texto).lower() + " "
    for claves, area in _PALABRAS_AREA:
        if any(k in n for k in claves):
            return area
    return {"Patrimonio": "Patrimonio", "Ingresos": "Ingresos", "Costos": "Costos y gastos", "Gastos": "Costos y gastos"}.get(seccion, "")


def _herramienta(texto: str, seccion: str = "") -> str:
    return HERRAMIENTAS.get(_area(texto, seccion), SIN_HERRAMIENTA)


# --- anexos ---------------------------------------------------------------------------------------------------

_ALIAS_COD = ("codigo", "código", "cuenta contable", "codigo cuenta", "código de cuenta", "cta", "cod")
_ALIAS_NOM = ("nombre", "descripcion", "descripción", "nombre de la cuenta", "nombre cuenta", "detalle", "cuenta")


def _balance(key, label, alias, ejemplo):
    return [
        campo("codigo", "Código de cuenta", alias=_ALIAS_COD, ejemplo="110301"),
        campo("cuenta", "Nombre de la cuenta", alias=_ALIAS_NOM, ejemplo="Clientes locales"),
        campo(key, label, "number", alias=alias, ejemplo=ejemplo),
    ]


_BAL_ANT = _balance("saldo_anterior", "Saldo al cierre anterior",
                    ("saldo", "saldo final", "saldo anterior", "saldo al cierre", "diciembre", "saldo dic"), "690500.00")
_BAL_ACT = _balance("saldo_actual", "Saldo al corte",
                    ("saldo", "saldo final", "saldo actual", "saldo al corte", "saldo a la fecha"), "812300.00")
_ERI_ANT = _balance("saldo_eri", "Saldo al mismo corte del año anterior",
                    ("saldo", "saldo final", "saldo al mismo corte", "saldo año anterior", "saldo ano anterior"), "-2980000.00")
_CARTA = [
    campo("id", "Código del hallazgo", alias=("codigo", "código", "id", "n°", "no", "numero", "número", "ref"), ejemplo="R01"),
    campo("proceso", "Proceso o área", alias=("proceso", "area", "área", "ciclo", "rubro"), ejemplo="Inventarios"),
    campo("hallazgo", "Hallazgo o riesgo", alias=("hallazgo", "riesgo", "condicion", "condición", "descripcion", "descripción",
                                                  "observacion", "observación"),
          ejemplo="No se realizan tomas físicas periódicas y las diferencias con el kárdex no se concilian."),
    campo("aseveraciones", "Aseveraciones", requerido=False, alias=("aseveraciones", "afirmaciones", "asercion", "aserción"),
          ejemplo="Existencia; valuación"),
    campo("probabilidad", "Probabilidad (1–5)", "number", requerido=False, alias=("probabilidad", "p", "prob"), ejemplo="4"),
    campo("impacto", "Impacto (1–5)", "number", requerido=False, alias=("impacto", "i", "magnitud"), ejemplo="4"),
    campo("control", "Control (1–5)", "number", requerido=False, alias=("control", "c", "efectividad del control"), ejemplo="2"),
    campo("respuesta", "Respuesta de auditoría", requerido=False,
          alias=("respuesta", "procedimiento", "respuesta de auditoria", "recomendacion", "recomendación"),
          ejemplo="Observar la toma física al cierre y conciliar el kárdex con la contabilidad."),
    campo("probar_control", "¿Se probará la eficacia del control? (Sí/No)", requerido=False,
          alias=("probar control", "prueba de controles", "se probara el control", "confianza en el control", "probar"),
          ejemplo="No"),
]
TIPOS_INFORME = ("Identificación", "Entendimiento", "Contexto", "Opinión", "Salvedad", "Desfavorable", "Abstención", "Énfasis",
                 "Empresa en funcionamiento", "Asunto clave", "Otro asunto")
# Otros nombres con que llega el tipo (NIA 705: opinión con salvedades, desfavorable o adversa, denegación o abstención).
ALIAS_INFORME = {"consalvedades": "Salvedad", "salvedades": "Salvedad", "adversa": "Desfavorable", "opinionadversa": "Desfavorable",
                 "opiniondesfavorable": "Desfavorable", "denegacion": "Abstención", "abstenciondeopinion": "Abstención",
                 "denegaciondeopinion": "Abstención",
                 # Término único de la NIA 570: «empresa en funcionamiento»; se acepta el nombre anterior.
                 "empresaenmarcha": "Empresa en funcionamiento", "negocioenmarcha": "Empresa en funcionamiento"}   # claves en la forma de ``norm`` (sin tildes ni espacios)
_INFORME = [
    campo("concepto", "Concepto", alias=("concepto", "asunto", "tema"), ejemplo="Jubilación patronal"),
    campo("tipo", "Tipo", alias=("tipo", "clase", "categoria", "categoría"), ejemplo="Salvedad"),
    campo("detalle", "Detalle", alias=("detalle", "descripcion", "descripción", "texto"),
          ejemplo="La provisión no se ajustó al cálculo actuarial al cierre."),
    campo("importe", "Importe (USD)", "number", requerido=False, alias=("importe", "monto", "valor", "efecto"), ejemplo="18500.00"),
    campo("fuente", "Fuente o referencia", requerido=False, alias=("fuente", "referencia", "pagina", "página", "parrafo", "párrafo"),
          ejemplo="Informe 2024 · Fundamento de la opinión"),
    campo("enfoque", "Efecto en el enfoque", requerido=False,
          alias=("efecto en el enfoque", "enfoque", "riesgo derivado", "consecuencia", "respuesta"),
          ejemplo="Ampliar las pruebas de las transacciones con partes relacionadas (NIA 550)."),
]
_NOTAS = [
    campo("nota", "Nota", alias=("nota", "n°", "numero", "número", "no"), ejemplo="4"),
    campo("titulo", "Título de la nota", alias=("titulo", "título", "nombre", "descripcion", "descripción"),
          ejemplo="Cuentas por cobrar comerciales y otras"),
    campo("codigos", "Cuentas del balance (códigos)", alias=("codigos", "códigos", "cuentas", "codigo", "código", "prefijos"),
          ejemplo="1103, 1106"),
    campo("saldo_auditado", "Saldo auditado según la nota", "number",
          alias=("saldo", "saldo auditado", "total", "importe", "saldo segun nota"), ejemplo="656500.00"),
]
TIPOS_LINEA = ("Saldo", "Movimiento", "Total")
_NOTAS_DET = [
    campo("nota", "Nota", alias=("nota", "n°", "numero", "número", "no"), ejemplo="4"),
    campo("concepto", "Concepto o línea de la nota", alias=("concepto", "detalle", "descripcion", "descripción", "linea", "línea",
                                                            "cuenta", "partida"), ejemplo="Clientes locales"),
    campo("importe", "Importe auditado", "number", alias=("importe", "saldo", "valor", "monto", "saldo auditado"), ejemplo="690500.00"),
    campo("tipo", "Tipo de línea", requerido=False, alias=("tipo", "clase"), ejemplo="Saldo"),
]
# Certificado del RUC (SRI): identificación oficial de la entidad, su actividad y obligaciones. Una sola fila.
_RUC = [
    campo("razon_social", "Razón social", requerido=False, alias=("razon social", "razón social", "entidad", "contribuyente", "nombre"),
          ejemplo="LANSEY S.A."),
    campo("ruc", "Número de RUC", requerido=False, alias=("ruc", "numero ruc", "número ruc", "nro ruc", "no ruc"), ejemplo="0991248021001"),
    campo("representante_legal", "Representante legal", requerido=False, alias=("representante legal", "representante", "rep legal"),
          ejemplo="PACINI DE LA ROSA ORLANDO ALBERTO"),
    campo("actividad_principal", "Actividad económica principal", requerido=False,
          alias=("actividad principal", "actividad economica principal", "actividad"), ejemplo="FABRICACIÓN DE COSMÉTICOS"),
    campo("actividades", "Actividades económicas (todas)", requerido=False, alias=("actividades economicas", "actividades", "ciiu"),
          ejemplo="C20233102 Fabricación de cosméticos; L68100101 Inmobiliaria"),
    campo("obligado_contabilidad", "Obligado a llevar contabilidad", requerido=False,
          alias=("obligado a llevar contabilidad", "obligado contabilidad", "lleva contabilidad"), ejemplo="SI"),
    campo("tipo_contribuyente", "Tipo de contribuyente", requerido=False, alias=("tipo", "tipo contribuyente", "clase contribuyente"),
          ejemplo="SOCIEDADES"),
    campo("agente_retencion", "Agente de retención", requerido=False, alias=("agente de retencion", "agente retencion"), ejemplo="SI"),
    campo("contribuyente_especial", "Contribuyente especial", requerido=False, alias=("contribuyente especial", "especial"), ejemplo="SI"),
    campo("obligaciones_tributarias", "Obligaciones tributarias", requerido=False, alias=("obligaciones tributarias", "obligaciones"),
          ejemplo="IVA mensual; Retenciones en la fuente; Renta sociedades; ATS; REBEFICS; ADI"),
    campo("establecimientos", "Establecimientos (abiertos/cerrados)", requerido=False,
          alias=("establecimientos", "establecimientos abiertos"), ejemplo="2 abiertos, 1 cerrado"),
    campo("jurisdiccion", "Jurisdicción / domicilio tributario", requerido=False,
          alias=("jurisdiccion", "jurisdicción", "domicilio", "domicilio tributario", "ubicacion"), ejemplo="ZONA 9 / PICHINCHA / QUITO"),
    campo("inicio_actividades", "Inicio de actividades", requerido=False, alias=("inicio de actividades", "inicio actividades"),
          ejemplo="12/11/1992"),
    campo("estado_contribuyente", "Estado del contribuyente", requerido=False, alias=("estado", "estado contribuyente"), ejemplo="ACTIVO"),
]
CAMPOS = {"balance_anterior": _BAL_ANT, "balance_actual": _BAL_ACT, "resultados_mismo_corte": _ERI_ANT, "carta_control_interno": _CARTA,
          "informe_anterior": _INFORME, "notas_estados_financieros": _NOTAS, "notas_detalle": _NOTAS_DET, "ruc_certificado": _RUC}
TIPOS = {k: k for k in CAMPOS}
DATASETS = tuple(TIPOS)
PRINCIPAL = "balance_actual"
CONTROL = "saldo_actual"

# Datasets narrativos que además de la transcripción en Excel/CSV se pueden extraer
# por IA desde el documento firmado (PDF/Word): la carta de control interno y el
# informe del año anterior. El auditor revisa y confirma la tabla extraída antes de
# que alimente la herramienta (la IA no decide sola). Lo usa ciclo/servicio.py.
EXTRACCION_DATASETS = ("carta_control_interno", "informe_anterior", "notas_estados_financieros", "ruc_certificado")
# Valores permitidos por campo, para forzar el esquema de la extracción (el tipo del
# informe debe caer en TIPOS_INFORME; la carta no tiene enumerados).
EXTRACCION_ENUMS = {"informe_anterior": {"tipo": list(TIPOS_INFORME)}}
# Instrucción específica por documento para guiar (no forzar) a la IA.
EXTRACCION_INSTRUCCIONES = {
    "carta_control_interno":
        "El documento es una CARTA DE CONTROL INTERNO: una fila por hallazgo o deficiencia de control. "
        "probabilidad, impacto y control son enteros de 1 a 5 SOLO si el documento los califica explícitamente; "
        "si no aparecen, déjalos vacíos (no los inventes). No incluyas párrafos de introducción ni de cierre.",
    "informe_anterior":
        "El documento es el INFORME DE AUDITORÍA del año anterior. Genera una fila por cada dato de identificación "
        "(entidad, auditor, período), por el tipo de opinión, por cada salvedad o énfasis, por cada asunto clave y por "
        "los indicios de empresa en funcionamiento. El importe solo si el texto lo declara; si no, vacío.",
    "notas_estados_financieros":
        "El documento son las NOTAS a los estados financieros del año anterior. Genera una fila por cada nota de balance: "
        "número de nota, título, los códigos de cuenta del balance que la forman (separados por coma) y el saldo auditado "
        "total de la nota. Solo notas de rubros del balance con su total; no incluyas notas de políticas contables.",
    "ruc_certificado":
        "El documento es el CERTIFICADO del Registro Único de Contribuyentes (RUC) del SRI (Ecuador). Genera UNA sola fila con: "
        "razón social, número de RUC, representante legal, actividad económica principal y TODAS las actividades económicas (con su "
        "código CIIU, separadas por «; »), si está obligado a llevar contabilidad (SI/NO), el tipo de contribuyente, si es agente de "
        "retención (SI/NO), si es contribuyente especial (SI/NO), las obligaciones tributarias (separadas por «; »), los "
        "establecimientos (abiertos/cerrados), la jurisdicción o domicilio tributario, la fecha de inicio de actividades y el estado. "
        "Transcribe solo lo que el certificado dice; lo que no conste, déjalo vacío.",
}

# --- parámetros ---------------------------------------------------------------------------------------------------

CLASIFICACIONES = ("Activo", "Activo corriente", "Activo no corriente", "Pasivo", "Pasivo corriente", "Pasivo no corriente",
                   "Patrimonio", "Ingresos", "Costos", "Gastos", "Otros")
SECCIONES = ("Activo", "Pasivo", "Patrimonio", "Ingresos", "Costos", "Gastos", "Otros")
MAPA_DEFECTO = ("1=Activo; 11=Activo corriente; 12=Activo no corriente; 101=Activo corriente; 102=Activo no corriente; "
                "2=Pasivo; 21=Pasivo corriente; 22=Pasivo no corriente; 201=Pasivo corriente; 202=Pasivo no corriente; "
                "3=Patrimonio; 4=Ingresos; 5=Gastos; 6=Costos; 7=Gastos")
UAI = "Utilidad antes de participación e impuestos"
BASES = ("Ingresos", "Activos totales", "Patrimonio", "Gastos totales", UAI)
BASES_FLUJO = ("Ingresos", "Gastos totales", UAI)   # bases de resultados: se anualizan en la preliminar al corte actual (D9)
_ALIAS_BASE = {"ingresos": "Ingresos", "ventas": "Ingresos", "activos": "Activos totales", "activostotales": "Activos totales",
               "activo": "Activos totales", "patrimonio": "Patrimonio", "gastos": "Gastos totales", "gastostotales": "Gastos totales",
               "costosygastos": "Gastos totales", "utilidadantesdeimpuestos": UAI, "uai": UAI,
               "utilidadantesdeparticipacioneimpuestos": UAI}
PERIODOS_BASE = ("Automático", "Año anterior", "Corte actual")
# La plataforma inyecta los registros del encargo (ciclo/servicio.py) en parametros["_encargo"].
USA_REGISTROS_ENCARGO = True

PARAMETROS = {
    "tipoRevision": "Final", "mesesTranscurridos": 12, "mapaCuentas": MAPA_DEFECTO,
    "baseMaterialidad": "Ingresos", "periodoBase": "Automático",
    "pctIngresos": 1, "pctActivos": 1, "pctPatrimonio": 1, "pctGastos": 0.5, "pctUAI": 5,
    "pctDesempeno": 50, "pctTrivial": 5, "justificacion": "",
    "umbralVarPct": 15, "umbralVarExtrema": 100, "umbralAlto": 15, "umbralMedio": 8, "umbralDiasRotacion": 15,
    "umbralSignificativo": 20,
    "encargoInicial": "No", "interesPublico": "No",
    "refutarIngresos": "No", "motivoRefutacion": "",
    "enfoque": "",
    "fechaPreliminar": "", "fechaFinal": "", "fechaInforme": "",
    "socio": "", "gerente": "", "expertos": "",
    **enc_m.PARAMETROS,
    **cal_m.PARAMETROS,
}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "tipoRevision": "Tipo de revisión (Final: diciembre contra diciembre / Preliminar: diciembre anterior contra el corte)",
    "mesesTranscurridos": "Meses transcurridos del ejercicio al corte (revisión preliminar; 12 en la final)",
    "mapaCuentas": "Mapa de cuentas: prefijo del código = clasificación (el prefijo más largo gana)",
    "baseMaterialidad": "Base de la materialidad (" + " / ".join(BASES) + ")",
    "periodoBase": "Período de la base (Automático: año anterior en la preliminar, corte actual en la final)",
    "pctIngresos": "Porcentaje sobre ingresos (política de la firma)",
    "pctActivos": "Porcentaje sobre activos totales (política de la firma)",
    "pctPatrimonio": "Porcentaje sobre patrimonio (política de la firma)",
    "pctGastos": "Porcentaje sobre gastos totales (política de la firma)",
    "pctUAI": "Porcentaje sobre utilidad antes de participación e impuestos (política de la firma)",
    "pctDesempeno": "Materialidad de desempeño: % de la global (práctica: 50 %–75 %)",
    "pctTrivial": "Errores claramente insignificantes: % de la global (práctica: 5 %)",
    "justificacion": "Justificación de la base (vacío = texto automático según la base)",
    "umbralVarPct": "Umbral de variación para observar un rubro de los estados resumidos (%)",
    "umbralVarExtrema": "Variación extrema de una cuenta para la revisión de anomalías (%)",
    "umbralDiasRotacion": "Aumento de días de cartera o de inventario que se reporta como deterioro de la rotación",
    "umbralAlto": "Matriz de riesgos: riesgo valorado desde el cual el nivel es Alto (escala 1–25)",
    "umbralMedio": "Matriz de riesgos: riesgo valorado desde el cual el nivel es Medio (escala 1–25)",
    "umbralSignificativo": "Matriz de riesgos: riesgo INHERENTE desde el cual el riesgo es significativo (escala 1–25)",
    "encargoInicial": "Encargo inicial: primer año de auditoría (Sí / No)",
    "interesPublico": "Entidad de interés público o cotizada (Sí / No)",
    "refutarIngresos": "Se refuta la presunción de fraude en el reconocimiento de ingresos (Sí / No)",
    "motivoRefutacion": "Motivo documentado de la refutación (NIA 240 párr. 47)",
    "enfoque": "Enfoque general de la auditoría (vacío = se deduce del enfoque por ciclo de la hoja 45)",
    "fechaPreliminar": "Fecha de la visita preliminar",
    "fechaFinal": "Fecha de la visita final",
    "fechaInforme": "Fecha prevista de entrega del informe",
    "socio": "Socio del encargo", "gerente": "Gerente o encargado del equipo",
    "expertos": "Uso de expertos (actuario, tasador, especialista en TI…)",
    **enc_m.ETIQUETAS,
    **cal_m.ETIQUETAS,
}
TOTAL_EJEMPLO = "materialidad"

JUSTIFICACION = {
    "Ingresos": ("Se toman los INGRESOS como referencia porque la utilidad es baja o volátil frente al volumen de operación; "
                 "las ventas representan mejor la dimensión del negocio y las decisiones de los usuarios (NIA 320 párr. A4)."),
    "Activos totales": ("Se toman los ACTIVOS TOTALES como referencia porque el negocio es intensivo en activos y los usuarios se "
                        "concentran en la inversión y la capacidad financiera más que en la rentabilidad anual (NIA 320 párr. A4)."),
    "Patrimonio": ("Se toma el PATRIMONIO como referencia porque el principal interés de los usuarios está en el capital y la "
                   "solvencia más que en el resultado del ejercicio (NIA 320 párr. A4)."),
    "Gastos totales": ("Se toman los GASTOS TOTALES como referencia porque el desempeño de la entidad se mide por los recursos "
                       "ejecutados (por ejemplo, sin fines de lucro) (NIA 320 párr. A4)."),
    UAI: ("Se toma la UTILIDAD ANTES DE PARTICIPACIÓN E IMPUESTOS como referencia porque la entidad es lucrativa, con "
          "resultados positivos y estables, y la rentabilidad es lo que observan los accionistas (NIA 320 párr. A4)."),
}


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def filas_mapeadas(sheet: dict, header: int, mapping: dict, campos: list, archivo: dict) -> dict:
    """Las del ciclo (``ciclo/servicio.py``), con el código de cuenta como texto: una celda numérica 1101 llega como
    «1101.0» y la hoja «Datos del cliente» debe mostrar el mismo código que las cédulas."""
    out = _filas_mapeadas(sheet, header, mapping, campos, archivo)
    if any(c["key"] == "codigo" for c in campos):
        for f in out["rows"]:
            f["codigo"] = _cod(f.get("codigo"))
    return out


def _tipo_linea(v) -> str | None:
    """Tipo de línea de la composición de una nota: Saldo (forma el saldo), Movimiento (conciliación del año) o Total."""
    k = norm(v)
    if not k:
        return "Saldo"
    return next((t for t in TIPOS_LINEA if norm(t) == k or k.startswith(norm(t)[:4])), None)


def _tipo_informe(v) -> str | None:
    k = norm(v)
    return next((t for t in TIPOS_INFORME if norm(t) == k), None) or ALIAS_INFORME.get(k)


def _opinion_modificada(detalle) -> str | None:
    """D10 (NIA 705 y 710): tipo de opinión modificada que declara la fila «Opinión» del informe anterior; None si no lo es
    («Sin salvedades», «No modificada», «Favorable»). ``norm`` quita tildes y espacios."""
    k = norm(detalle)
    if re.search(r"abstenc|abstien|abstuvo|denegac|deniega", k):
        return "Abstención"
    if re.search(r"desfavorable|adversa", k):
        return "Desfavorable"
    if re.search(r"salvedad|reserva", k) and not re.search(r"sinsalvedad|sinreserva|nomodificada", k):
        return "Salvedad"
    return None


def validar_filas(tipo: str, filas: list) -> dict:
    unico = {"carta_control_interno": "id", "notas_estados_financieros": "nota"}.get(tipo)
    out = validar_campos(CAMPOS[tipo], filas, unico=unico)
    if tipo in ("balance_anterior", "balance_actual", "resultados_mismo_corte"):
        vistos = {}
        for f in filas:
            c = _cod(f.get("codigo"))
            if c and c in vistos:
                out["errors"].append({"row": f.get("_row"), "field": "codigo",
                                      "message": f"Código repetido: {c} (también en la fila {vistos[c]})."})
            vistos.setdefault(c, f.get("_row"))
    elif tipo == "carta_control_interno":
        for f in filas:
            for k in ("probabilidad", "impacto", "control"):
                v = str(f.get(k, "") or "").strip()
                x = a_num(v) if v else None
                if v and (x is None or float(x) != int(float(x)) or not 1 <= float(x) <= 5):
                    out["errors"].append({"row": f.get("_row"), "field": k, "message": "Califique de 1 a 5 (número entero)."})
    elif tipo == "notas_detalle":
        for f in filas:
            if _tipo_linea(f.get("tipo")) is None:
                out["errors"].append({"row": f.get("_row"), "field": "tipo", "message": "Tipo: use " + ", ".join(TIPOS_LINEA) + "."})
    elif tipo == "informe_anterior":
        for f in filas:
            if _tipo_informe(f.get("tipo")) is None:
                out["errors"].append({"row": f.get("_row"), "field": "tipo", "message": "Tipo: use " + ", ".join(TIPOS_INFORME) + "."})
    out["ok"] = not out["errors"]
    return out


# --- mapa de cuentas y jerarquía (misma regla que las fórmulas de Excel) ---------------------------------------

def _mapa(texto: str) -> list[tuple[str, str]]:
    """«1=Activo; 11=Activo corriente» → [(prefijo, clasificación)] ordenado por largo del prefijo (LOOKUP de Excel
    devuelve la ÚLTIMA fila que coincide: la del prefijo más largo)."""
    out = {}
    for parte in re.split(r"[;\n]+", str(texto or "")):
        if not parte.strip():
            continue
        if "=" not in parte:
            raise ValueError(f"Mapa de cuentas: «{parte.strip()}» no tiene la forma prefijo=clasificación.")
        pre, cla = (x.strip() for x in parte.split("=", 1))
        pre = pre.replace(".", "")
        clas = next((c for c in CLASIFICACIONES if norm(c) == norm(cla)), None)
        if not re.fullmatch(r"\d+", pre) or clas is None:
            raise ValueError(f"Mapa de cuentas: «{parte.strip()}»: use un prefijo numérico y una de {', '.join(CLASIFICACIONES)}.")
        out[pre] = clas
    if not out:
        raise ValueError("Mapa de cuentas: indique al menos un prefijo (por ejemplo 1=Activo).")
    return sorted(out.items(), key=lambda kv: (len(kv[0]), kv[0]))


def _clasificar(cod: str, mapa: list) -> str:
    nd = cod.replace(".", "")
    hit = "Otros"
    for pre, cla in mapa:
        if nd.startswith(pre):
            hit = cla
    return hit


def _seccion_de(clas: str) -> str:
    return "Activo" if clas.startswith("Activo") else "Pasivo" if clas.startswith("Pasivo") else clas


def _debajo(x: str, c: str) -> bool:
    """x es c o una subcuenta de c (regla del código de la fila c: con puntos, por segmentos)."""
    return (x + ".").startswith(c + ".") if "." in c else x.startswith(c)


def _ancestro(a: str, c: str) -> bool:
    """a es una cuenta superior de c. Se decide con la MISMA regla que `_debajo` (la del código del
    posible padre `a`): así un código con sufijo de punto como «11010103.01» sigue anidando bajo sus
    prefijos numéricos (110101, 1101, 11, 1), no solo bajo «11010103». Antes se usaba el formato del
    hijo, que al tener punto cambiaba a segmentos y rompía el nivel (quedaba en 1) y la cuadratura."""
    return len(a) < len(c) and _debajo(c, a)


def _estructura(codes: list[str]) -> dict:
    """Nivel (cuentas superiores presentes + 1) y cuenta de detalle (sin subcuentas) de cada código."""
    out = {}
    for c in codes:
        anc = sum(1 for a in codes if _ancestro(a, c))
        hijos = any(len(x) > len(c) and _debajo(x, c) for x in codes)
        out[c] = {"nivel": anc + 1, "detalle": "No" if hijos else "Sí"}
    return out


def _superior(x: dict, filas: list, clave: str) -> str:
    """«Sí» si ninguna cuenta superior de x (en las mismas filas) tiene el mismo valor de ``clave``: es la cuenta más alta
    de su sección, clasificación o rubro, la que se suma (R1: su saldo propio ya incluye el de sus subcuentas)."""
    return "No" if any(a[clave] == x[clave] and _ancestro(a["codigo"], x["codigo"]) for a in filas) else "Sí"


def _busca(nombre: str, *claves) -> bool:
    n = str(nombre or "").lower()
    return any(k in n for k in claves)


def _rubro_eri(cod: str, nombre: str, sec: str) -> str:
    if sec == "Ingresos":
        return "Ventas" if cod.replace(".", "")[:2] in ("41", "42") else "Otros ingresos"
    if sec == "Costos":
        return "Costo de ventas"
    if sec == "Gastos":
        if _busca(nombre, "financ", "interes", "interés"):
            return "Gastos financieros"
        if _busca(nombre, "impuesto a la renta", "participaci"):
            return "Impuestos y participación"
        return "Gastos operativos"
    return ""


def _rubro_indice(nombre: str, sec: str) -> str:
    if sec == "Activo":
        if _busca(nombre, "efectivo", "caja", "banco") and not _busca(nombre, "restringid"):
            return "Efectivo"
        if _busca(nombre, "cobrar", "cliente") and not _busca(nombre, *NO_COMERCIAL_CXC):
            return "Cuentas por cobrar"
        if _busca(nombre, "inventario", "mercader", "existencia"):
            return "Inventarios"
    if sec == "Pasivo":
        if _busca(nombre, "bancari", "financ", "préstamo", "prestamo", "sobregiro", "obligacion", "obligación"):
            return "Obligaciones financieras"
        if _busca(nombre, "pagar", "proveedor") and not _busca(nombre, *NO_COMERCIAL_CXP):
            return "Cuentas por pagar"
    return ""


# R6 / revisor M1: solo cuentas comerciales en cartera y proveedores (días de cartera y de proveedores).
NO_COMERCIAL_CXC = ("proveedor", "anticipo", "empleado", "impuesto", "otras")
NO_COMERCIAL_CXP = ("impuesto", "beneficio", "iess", "participaci", "dividendo", "sueldo", "empleado")
_CONTRA = re.compile(r"\(-\)|deprec|dep\.|amortiz|provisi|deterior|estimac|incobrab|acum|reserva|ajuste|revaluac|superavit")


# --- cálculo --------------------------------------------------------------------------------------------------

def _pnum(p, k, minimo=0.0, maximo=100.0):
    v = a_num(p.get(k))
    if v is None or not minimo < float(v) <= maximo:
        raise ValueError(f"{ETIQUETAS_PARAM[k]}: use un valor mayor que {minimo:g} y hasta {maximo:g}.")
    return float(v)


def _psino(p, k) -> str:
    v = str(p.get(k) or "No").strip()
    if _si(v):
        return "Sí"
    if _no(v):
        return "No"
    raise ValueError(f"{ETIQUETAS_PARAM[k]}: responda Sí o No.")


def _fuente(filas, key) -> list[dict]:
    out = []
    for f in filas or []:
        c = _cod(f.get("codigo"))
        if not c:
            continue
        # La hoja «Datos del cliente» usa la misma fila: el código queda como texto (1101.0 de una celda numérica → 1101)
        # para que las cédulas la encuentren por su código.
        f["codigo"] = c
        v = a_num(f.get(key))
        out.append({"codigo": c, "cuenta": str(f.get("cuenta", "") or "").strip() or c,
                    "saldo": float(v) if v is not None else 0.0, "posteado": v is not None, "_row": f.get("_row")})
    return out


ETQ_BC = {"ant": "Balance del cierre anterior", "act": "Balance al corte"}
ACREEDORAS = ("Pasivo", "Patrimonio", "Ingresos")


def _es_firmado(b: dict) -> bool:
    """El balance viene con signo (deudor +, acreedor −) si la suma de las secciones se acerca más a cero que la ecuación."""
    firmada = b["Activo"] + b["Pasivo"] + b["Patrimonio"] + b["Ingresos"] + b["Costos"] + b["Gastos"]
    natural = b["Activo"] - b["Pasivo"] - b["Patrimonio"] - b["Ingresos"] + b["Costos"] + b["Gastos"]
    return abs(firmada) <= abs(natural)


def _f_firmado() -> str:
    c = {k: f"$C${F7[k]}" for k in ("Activo", "Pasivo", "Patrimonio", "Ingresos", "Costos", "Gastos")}
    return (f"ABS({c['Activo']}+{c['Pasivo']}+{c['Patrimonio']}+{c['Ingresos']}+{c['Costos']}+{c['Gastos']})<="
            f"ABS({c['Activo']}-{c['Pasivo']}-{c['Patrimonio']}-{c['Ingresos']}+{c['Costos']}+{c['Gastos']})")


SEV_INFORME = {"Salvedad": "Alto", "Desfavorable": "Alto", "Abstención": "Alto", "Empresa en funcionamiento": "Alto", "Énfasis": "Medio", "Asunto clave": "Medio", "Otro asunto": "Bajo"}
NORMA_INFORME = {"Salvedad": "NIA 705 y 710", "Desfavorable": "NIA 705 y 710", "Abstención": "NIA 705 y 710", "Empresa en funcionamiento": "NIA 570", "Énfasis": "NIA 706", "Asunto clave": "NIA 701",
                 "Otro asunto": "NIA 706"}
EFECTO_INFORME = {
    "Identificación": "Dato del perfil del encargo (entidad, actividad, marco, período).",
    "Entendimiento": "Evaluar su efecto en los riesgos de incorrección material y en la respuesta (NIA 315 párr. 19 y 25).",
    "Contexto": "Contexto del encargo: considerarlo en la evaluación del riesgo (NIA 315 párr. 19).",
    "Opinión": "Punto de partida: si la opinión fue modificada, evaluar si la causa persiste (NIA 710).",
    "Salvedad": "Riesgo alto: verificar si el asunto se corrigió; si persiste, afecta la opinión de este año (NIA 705 y 710).",
    "Desfavorable": ("Riesgo alto: la opinión anterior fue desfavorable; verificar si las incorrecciones generalizadas se "
                     "corrigieron y su efecto en las cifras comparativas (NIA 705 y 710)."),
    "Abstención": ("Riesgo alto: el auditor anterior se abstuvo de opinar; los saldos de apertura carecen de evidencia suficiente "
                   "y deben probarse (NIA 510, 705 y 710)."),
    "Énfasis": "Evaluar si el asunto sigue vigente y su revelación (NIA 706).",
    "Empresa en funcionamiento": "Riesgo alto: actualizar la evaluación de la administración y la revelación (NIA 570).",
    "Asunto clave": "Considerar como posible riesgo significativo del año (NIA 701 y 315).",
    "Otro asunto": "Tener presente en la planificación (NIA 706).",
}
# Las citas de los textos están en NIIF completas; con NIIF para las PYMES se reemplazan por su sección (el cliente
# aplica un solo marco, el de la ficha del encargo).
NORMAS_PYMES = {"(NIC 36)": "(Sección 27)", "(NIIF 9)": "(Sección 11)", "(NIC 2)": "(Secciones 13 y 27)", "(NIC 8)": "(Sección 10)",
                "modelo de pérdida crediticia esperada": "evidencia objetiva de deterioro (pérdida incurrida)",
                "cálculo de la pérdida crediticia esperada": "cálculo de la pérdida por deterioro incurrida"}
DETERIORO_CARTERA = {MARCO_COMPLETAS: "Pérdida crediticia esperada · enfoque simplificado (NIIF 9)",
                     MARCO_PYMES: "Deterioro de cuentas por cobrar · pérdidas incurridas (Sección 11)"}


EDICION_COMPLETAS = "Vigentes al corte"
DESEMP_SUGERIDO = "Desempeño sugerido por factores (NIA 320 párr. A12)"
AVISO_SIGNO = "Saldos con signo contrario en la base y los índices (hoja 17)"


def segun_marco(texto: str, marco: str) -> str:
    """El texto con las citas del marco del cliente (NIIF completas o NIIF para las PYMES)."""
    if marco != MARCO_PYMES:
        return texto
    for a, b in NORMAS_PYMES.items():
        texto = texto.replace(a, b)
    return texto


OPINION_TXT = {"Salvedad": "con salvedades", "Desfavorable": "desfavorable", "Abstención": "abstención de opinión"}
# Posibles riesgos: (código interno, origen, rubro, condición, posible riesgo, severidad, norma, respuesta, herramienta)
_RIESGOS_BALANCE = [
    ("presuncion", "NIA 240", "Ingresos", "Presunción de fraude en el reconocimiento de ingresos",
     "Incorrección material por fraude en ingresos (ocurrencia y corte)", "Significativo", "NIA 240",
     "Pruebas de corte de ventas, notas de crédito posteriores al cierre, confirmaciones y asientos manuales de ingresos.",
     HERRAMIENTAS["Ingresos"]),
    ("elusion", "NIA 240", "Todas las áreas", "Riesgo de elusión de los controles por la dirección",
     "Asientos y estimaciones sesgadas o transacciones inusuales", "Significativo", "NIA 240",
     "Pruebas de asientos de diario con criterios de riesgo, revisión retrospectiva de estimaciones y de transacciones inusuales.",
     HERRAMIENTAS["Asientos de diario"]),
    ("ct", "Balances", "Capital de trabajo", "Capital de trabajo negativo", "Riesgo de liquidez y de empresa en funcionamiento", "Alto",
     "NIA 570", "Evaluar la capacidad de pago: flujos proyectados, financiamiento disponible y hechos posteriores.", SIN_HERRAMIENTA),
    ("rc", "Balances", "Liquidez", "Razón corriente menor a 1", "El activo corriente no cubre el pasivo corriente", "Alto", "NIA 570",
     "Analizar el calce de vencimientos y el plan de la administración para atender el corto plazo.", SIN_HERRAMIENTA),
    ("end", "Balances", "Endeudamiento", "Endeudamiento del activo superior al 70 %",
     "Alto apalancamiento y presión financiera; revisar las condiciones de los préstamos", "Alto", "NIA 315",
     "Revisar covenants, vencimientos y garantías de las obligaciones.", HERRAMIENTAS["Préstamos y obligaciones financieras"]),
    ("end80", "Balances", "Endeudamiento", "Endeudamiento del activo superior al 80 %",
     "Dependencia de terceros: indicio sobre la empresa en funcionamiento", "Alto", "NIA 570",
     "Evaluar el financiamiento disponible, los vencimientos y los planes de la administración.", HERRAMIENTAS["Préstamos y obligaciones financieras"]),
    ("perdida", "Balances", "Resultado del ejercicio", "Resultado del período negativo",
     "Pérdidas: indicio de deterioro (NIC 36) y de empresa en funcionamiento", "Alto", "NIA 570",
     "Evaluar la hipótesis de empresa en funcionamiento y el deterioro de los activos de larga vida.", SIN_HERRAMIENTA),
    ("patrimonio", "Balances", "Patrimonio", "Patrimonio total nulo o negativo",
     "Patrimonio comprometido: causal de disolución y duda sobre la empresa en funcionamiento", "Alto", "NIA 570",
     "Evaluar los planes de capitalización y la revelación de la incertidumbre material.", HERRAMIENTAS["Patrimonio"]),
    ("cartera", "Balances", "Cuentas por cobrar", "Días de cartera (ajustados al período) superiores a 90",
     "Posible incobrabilidad: evaluar el deterioro de la cartera (NIIF 9)", "Medio", "NIA 540",
     "Antigüedad de saldos, cobros posteriores y modelo de pérdida crediticia esperada.", HERRAMIENTAS["Cuentas por cobrar"]),
    ("inventario", "Balances", "Inventarios", "Días de inventario (ajustados al período) superiores a 120",
     "Lento movimiento: posible obsolescencia y ajuste al valor neto realizable (NIC 2)", "Medio", "NIA 501",
     "Rotación por ítem, valor neto realizable y observación de la toma física.", HERRAMIENTAS["Inventarios"]),
    ("rotCartera", "Balances", "Cuentas por cobrar", "Los días de cartera (ajustados al período) aumentaron más que el umbral de la hoja 02",
     "Deterioro de la cobranza: posible incobrabilidad (NIIF 9)", "Medio", "NIA 540",
     "Comparar la antigüedad de la cartera entre períodos y los cobros posteriores al corte.", HERRAMIENTAS["Cuentas por cobrar"]),
    ("rotInventario", "Balances", "Inventarios", "Los días de inventario (ajustados al período) aumentaron más que el umbral de la hoja 02",
     "Deterioro de la rotación: posible obsolescencia (NIC 2)", "Medio", "NIA 501",
     "Identificar los ítems de lenta rotación y evaluar su valor neto realizable.", HERRAMIENTAS["Inventarios"]),
]


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = a_fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    tr = norm(p["tipoRevision"])
    tipo = "Preliminar" if tr.startswith("prelim") else "Final" if tr.startswith("final") else None
    if tipo is None:
        raise ValueError("Tipo de revisión: use Final o Preliminar.")
    meses = a_num(p.get("mesesTranscurridos"))
    if meses is None or float(meses) != int(float(meses)) or not 1 <= float(meses) <= 12:
        raise ValueError(f"{ETIQUETAS_PARAM['mesesTranscurridos']}: use un número entero de 1 a 12.")
    meses = int(float(meses))
    mapa = _mapa(p["mapaCuentas"])
    base_nombre = _ALIAS_BASE.get(norm(p["baseMaterialidad"])) or next(
        (b for b in BASES if norm(b) == norm(p["baseMaterialidad"])), None)
    if base_nombre is None:
        raise ValueError("Base de la materialidad: elija " + ", ".join(BASES) + ".")
    periodo_param = next((x for x in PERIODOS_BASE if norm(x) == norm(p["periodoBase"])), None)
    if periodo_param is None:
        raise ValueError("Período de la base: use " + ", ".join(PERIODOS_BASE) + ".")
    pct = {k: _pnum(p, k) for k in ("pctIngresos", "pctActivos", "pctPatrimonio", "pctGastos", "pctUAI", "pctDesempeno", "pctTrivial")}
    umbral_var, umbral_ext = _pnum(p, "umbralVarPct", 0, 1000), _pnum(p, "umbralVarExtrema", 0, 100000)
    u_alto, u_medio = _pnum(p, "umbralAlto", 0, 25), _pnum(p, "umbralMedio", 0, 25)
    u_sig = _pnum(p, "umbralSignificativo", 0, 25)
    u_dias = _pnum(p, "umbralDiasRotacion", 0, 3650)
    if u_medio > u_alto:
        raise ValueError("Matriz de riesgos: el umbral Medio no puede superar al Alto.")
    sino = {k: _psino(p, k) for k in ("encargoInicial", "interesPublico", "refutarIngresos")}
    pe = enc_m.parametros(p)          # parámetros del encargo (año anterior, rotación, materialidad específica, muestreo)
    reg = enc_m.registros(p)          # registros con un clic en la plataforma (independencia, aceptación, carta, discusión…)
    pc = cal_m.parametros(p)          # M2 y M11: horas, umbral de los analíticos y cierre del archivo (política de la firma)
    v_ant = cal_m.version_anterior(p)   # M4: la versión anterior de la planificación (la entrega la plataforma)
    # D6/A1: socio y gerente, si la hoja 02 no los trae, son los integrantes con ese rol que confirmaron su independencia.
    for k, rol in (("socio", "Socio"), ("gerente", "Gerente")):
        if not str(p.get(k) or "").strip():
            p[k] = next((x["integrante"] for x in reg["equipo"] if x["rol"] == rol), "")
    fechas = {}
    for k in ("fechaPreliminar", "fechaFinal", "fechaInforme"):
        v = str(p.get(k) or "").strip()
        if v and a_fecha(v) is None:
            raise ValueError(f"{ETIQUETAS_PARAM[k]}: fecha inválida.")
        fechas[k] = a_fecha(v).isoformat() if v else None
    marco = MARCO_PYMES if es_pymes(p) else MARCO_COMPLETAS
    # NIIF para las PYMES: 2015 o 2025 (3.ª edición, rige desde 2027) según la ficha; NIIF completas: las vigentes al corte.
    edicion = edicion_pymes(p) if marco == MARCO_PYMES else EDICION_COMPLETAS
    prelim = tipo == "Preliminar"

    # 1 · balances de comprobación (cada uno con su jerarquía, clasificación y rubro del ERI)
    fuentes = {"ant": _fuente(datasets.get("balance_anterior"), "saldo_anterior"),
               "act": _fuente(datasets.get("balance_actual"), "saldo_actual"),
               "eri": _fuente(datasets.get("resultados_mismo_corte"), "saldo_eri")}
    if not fuentes["act"]:
        raise ValueError("Cargue el balance de comprobación a la fecha de corte.")
    if not fuentes["ant"]:
        raise ValueError("Cargue el balance de comprobación al cierre del año anterior.")
    for filas in fuentes.values():
        est = _estructura([x["codigo"] for x in filas])
        for x in filas:
            x.update(est[x["codigo"]])
            x["clas"] = _clasificar(x["codigo"], mapa)
            x["sec"] = _seccion_de(x["clas"])
            x["rubro"] = _rubro_eri(x["codigo"], x["cuenta"], x["sec"])
        for x in filas:
            x["supsec"] = _superior(x, filas, "sec")
            x["difsub"] = 0.0 if x["detalle"] == "Sí" else x["saldo"] - sum(
                y["saldo"] for y in filas if y["nivel"] == x["nivel"] + 1 and _debajo(y["codigo"], x["codigo"]))
    hay_eri = bool(fuentes["eri"])

    # 2 · secciones: total bruto (cuentas de detalle), signo de presentación y cuadre por balance
    bruto = {k: {s: sum(x["saldo"] for x in fuentes[k] if x["sec"] == s and x["supsec"] == "Sí") for s in SECCIONES}
             for k in fuentes}
    # R2: la convención es la del balance al corte entero, no la de cada sección (un patrimonio en déficit debe seguir
    # negativo). Con signo (deudor + / acreedor −) la suma de las secciones da cero; por naturaleza, la da la ecuación contable.
    b = bruto["act"]
    firmado = _es_firmado(b)
    signo = {s: (-1 if firmado and s in ACREEDORAS else 1) for s in SECCIONES}
    for filas in fuentes.values():
        for x in filas:
            x["pres"] = x["saldo"] * signo[x["sec"]]
    sec7 = {}
    for k in fuentes:
        t = {s: bruto[k][s] * signo[s] for s in SECCIONES}
        t["Impuestos y participación"] = sum(x["pres"] for x in fuentes[k]
                                             if x["rubro"] == "Impuestos y participación" and x["detalle"] == "Sí")
        t["Resultado del balance"] = t["Ingresos"] - t["Costos"] - t["Gastos"]
        t[UAI] = t["Resultado del balance"] + t["Impuestos y participación"]
        t["Gastos totales"] = t["Costos"] + t["Gastos"]
        t["Pasivo + patrimonio + resultado"] = t["Pasivo"] + t["Patrimonio"] + t["Resultado del balance"]
        t["Diferencia de cuadre"] = t["Activo"] - t["Pasivo + patrimonio + resultado"]
        sec7[k] = t

    # 3 · análisis horizontal de TODAS las cuentas (unión de códigos, orden de texto = cuenta superior antes que sus subcuentas)
    nombres = {}
    for k in ("act", "ant", "eri"):
        for x in fuentes[k]:
            nombres.setdefault(x["codigo"], x["cuenta"])
    codes = sorted(nombres)
    est = _estructura(codes)

    def psum(k, c):
        """R1: el saldo propio de la cuenta de detalle; para una cuenta SUPERIOR, su saldo si el balance lo trae,
        y si viene vacío (0), la suma de sus subcuentas de detalle. Muchos balances dejan los padres en blanco y
        solo llenan las hojas (p. ej. el balance al corte de LANSEY): sin esto, los totales de padre quedan en 0."""
        propio = [x for x in fuentes[k] if x["codigo"] == c]
        if not propio:
            return 0.0                       # código ausente en este balance: vale 0 (no se infiere de sus hijas)
        if propio[0]["detalle"] == "Sí" or propio[0]["posteado"]:
            return propio[0]["pres"]          # hoja, o padre con saldo propio posteado (aunque sea 0 explícito)
        # Padre SIN saldo propio (celda en blanco): suma la postación PROPIA de todos sus descendientes (no solo las
        # hojas). Así una cuenta intermedia que postea y además tiene subcuentas (p. ej. «CAJA MENOR GESTIÓN HUMANA»
        # 400 con dos subcajas .01/.02) cuenta su saldo y el de sus hijas, igual que el balance de comprobación.
        return sum(x["pres"] for x in fuentes[k] if x["codigo"] != c and _debajo(x["codigo"], c))

    cuentas = []
    for c in codes:
        clas = _clasificar(c, mapa)
        sec = _seccion_de(clas)
        s_ant, s_act = psum("ant", c), psum("act", c)
        if prelim and sec in ("Ingresos", "Costos", "Gastos"):
            ant = psum("eri", c) if hay_eri else s_ant * meses / 12
        else:
            ant = s_ant
        cuentas.append({"codigo": c, "cuenta": nombres[c], "nivel": est[c]["nivel"], "detalle": est[c]["detalle"], "clas": clas,
                        "sec": sec, "ant": ant, "act": s_act, "rubro": _rubro_eri(c, nombres[c], sec),
                        "rind": _rubro_indice(nombres[c], sec)})
    for x in cuentas:
        x["pind"] = "" if not x["rind"] else _superior(x, cuentas, "rind")
        x["supsec"], x["supclas"] = _superior(x, cuentas, "sec"), _superior(x, cuentas, "clas")
        x["suprubro"] = "" if not x["rubro"] else _superior(x, cuentas, "rubro")
        x["var"] = x["act"] - x["ant"]
        x["varPct"] = None if x["ant"] == 0 else x["var"] / abs(x["ant"])

    def cs(k, **filtro):
        return sum(x[k] for x in cuentas if all(x[a] == b for a, b in filtro.items()))

    # 4 · estados resumidos (mismos conceptos que la hoja 09)
    est9 = {}
    v41 = {k: cs(k, rubro="Ventas", suprubro="Sí") for k in ("ant", "act")}
    todas_cero = v41["ant"] == 0 and v41["act"] == 0
    for k in ("ant", "act"):
        e = {}
        e["TOTAL ACTIVO"] = cs(k, sec="Activo", supsec="Sí")
        e["Activo no corriente"] = cs(k, clas="Activo no corriente", supclas="Sí")
        e["Activo corriente"] = e["TOTAL ACTIVO"] - e["Activo no corriente"]
        e["Efectivo y equivalentes"] = cs(k, rind="Efectivo", pind="Sí")
        e["Cuentas por cobrar"] = cs(k, rind="Cuentas por cobrar", pind="Sí")
        e["Inventarios"] = cs(k, rind="Inventarios", pind="Sí")
        e["TOTAL PASIVO"] = cs(k, sec="Pasivo", supsec="Sí")
        e["Pasivo no corriente"] = cs(k, clas="Pasivo no corriente", supclas="Sí")
        e["Pasivo corriente"] = e["TOTAL PASIVO"] - e["Pasivo no corriente"]
        e["Cuentas por pagar"] = cs(k, rind="Cuentas por pagar", pind="Sí")
        e["Obligaciones financieras"] = cs(k, rind="Obligaciones financieras", pind="Sí")
        e["PATRIMONIO (sin resultado del período)"] = cs(k, sec="Patrimonio", supsec="Sí")
        e["Resultado del período (según el balance)"] = sec7[k]["Resultado del balance"]
        e["PATRIMONIO TOTAL"] = e["PATRIMONIO (sin resultado del período)"] + e["Resultado del período (según el balance)"]
        e["PASIVO + PATRIMONIO TOTAL"] = e["TOTAL PASIVO"] + e["PATRIMONIO TOTAL"]
        e["Diferencia de cuadre"] = e["TOTAL ACTIVO"] - e["PASIVO + PATRIMONIO TOTAL"]
        ing = cs(k, sec="Ingresos", supsec="Sí")
        gas = cs(k, sec="Gastos", supsec="Sí")
        e["Ventas netas"] = ing if todas_cero else v41[k]
        e["(−) Costo de ventas"] = cs(k, sec="Costos", supsec="Sí")
        e["Utilidad bruta"] = e["Ventas netas"] - e["(−) Costo de ventas"]
        e["(−) Gastos financieros"] = cs(k, rubro="Gastos financieros", detalle="Sí")
        e["(−) Participación e impuestos"] = cs(k, rubro="Impuestos y participación", detalle="Sí")
        e["(−) Gastos operativos"] = gas - e["(−) Gastos financieros"] - e["(−) Participación e impuestos"]
        e["Utilidad operativa"] = e["Utilidad bruta"] - e["(−) Gastos operativos"]
        e["(+) Otros ingresos"] = ing - e["Ventas netas"]
        e[UAI] = e["Utilidad operativa"] + e["(+) Otros ingresos"] - e["(−) Gastos financieros"]
        e["Utilidad neta"] = e[UAI] - e["(−) Participación e impuestos"]
        est9[k] = e
    tot_act, ventas_act = est9["act"]["TOTAL ACTIVO"], est9["act"]["Ventas netas"]
    for x in cuentas:
        if x["sec"] in ("Activo", "Pasivo", "Patrimonio"):
            x["vert"] = _div(x["act"], tot_act)
        elif x["sec"] in ("Ingresos", "Costos", "Gastos"):
            x["vert"] = _div(x["act"], ventas_act)
        else:
            x["vert"] = None

    # 4b · orígenes y aplicaciones de efectivo (lectura causa-efecto): cuentas de nivel 3 del balance (o de detalle más
    # arriba) sin el efectivo; un activo que sube aplica efectivo y un pasivo o patrimonio que sube lo origina.
    origenes = [x for x in cuentas if x["sec"] in ("Activo", "Pasivo", "Patrimonio") and x["rind"] != "Efectivo"
                and (x["nivel"] == 3 or (x["nivel"] < 3 and x["detalle"] == "Sí"))]
    for x in origenes:
        x["efecto"] = 0.0 - x["var"] if x["sec"] == "Activo" else x["var"]
    origenes.sort(key=lambda x: -x["efecto"])
    d_res = est9["act"]["Resultado del período (según el balance)"] - est9["ant"]["Resultado del período (según el balance)"]
    d_caja = est9["act"]["Efectivo y equivalentes"] - est9["ant"]["Efectivo y equivalentes"]
    puente = {"resultado": d_res, "total": sum(x["efecto"] for x in origenes) + d_res, "caja": d_caja}
    puente["dif"] = puente["total"] - d_caja
    archivos = {}
    for ds in CAMPOS:
        filas_ = datasets.get(ds) or []
        f0 = filas_[0] if filas_ else {}
        txt = " · ".join(str(v).strip() for v in (f0.get("_file"), f0.get("_sheet")) if str(v or "").strip())
        archivos[ds] = (txt or ("Entregado por el cliente" if filas_ else "No entregado"), len(filas_), _huella(filas_))
    # Prioridad baja (NIA 230): nombre y huella SHA-256 de cada archivo subido a la plataforma (la plataforma los entrega).
    arch_plat = [{k: str(x.get(k) or "") for k in ("requerimiento", "nombre", "sha256", "subido_por", "subido_en")}
                 for x in (parametros or {}).get("_archivos") or [] if isinstance(x, dict) and x.get("sha256")]

    # 5 · índices (redondeados a 2 decimales como en la hoja 10). R4: días sobre 365 también en cortes parciales
    # (con ventas de pocos meses los días salen mayores: se declara en la lectura).
    dias = 365
    ind = {k: _indices(est9[k], dias) for k in ("ant", "act")}

    # 6 · materialidad (NIA 320)
    periodo = ("Año anterior" if prelim else "Corte actual") if periodo_param == "Automático" else periodo_param
    kb = "ant" if periodo == "Año anterior" else "act"
    bases = {"Ingresos": sec7[kb]["Ingresos"], "Activos totales": sec7[kb]["Activo"], "Patrimonio": sec7[kb]["Patrimonio"],
             "Gastos totales": sec7[kb]["Gastos totales"], UAI: sec7[kb][UAI]}
    pct_base = {"Ingresos": pct["pctIngresos"], "Activos totales": pct["pctActivos"], "Patrimonio": pct["pctPatrimonio"],
                "Gastos totales": pct["pctGastos"], UAI: pct["pctUAI"]}
    # D9 (NIA 320): en la preliminar, las bases de resultados al corte actual cubren solo los meses transcurridos; se anualizan
    # (× 12 ÷ meses) para que la materialidad corresponda al ejercicio completo. Las bases de balance no se anualizan.
    anualiza = prelim and kb == "act" and meses < 12
    if anualiza:
        bases = {b: v * 12 / meses if b in BASES_FLUJO else v for b, v in bases.items()}
    base_valor = bases[base_nombre]
    # Base ≤ 0 (pérdida, patrimonio negativo): no hay materialidad y nada se marca como material hasta elegir otra base.
    mat = base_valor * pct_base[base_nombre] / 100 if base_valor > 0 else None
    desemp = None if mat is None else mat * pct["pctDesempeno"] / 100
    triv = None if mat is None else mat * pct["pctTrivial"] / 100

    def alcanza(v, fr=1.0):
        return desemp is not None and abs(v) >= desemp * fr
    for x in cuentas:
        x["material"] = "Sí" if alcanza(x["act"]) else "No"
        x["varMaterial"] = "Sí" if alcanza(x["var"]) else "No"
    justif = str(p.get("justificacion") or "").strip() or JUSTIFICACION[base_nombre]

    # 7 · matriz de la carta de control interno
    carta = []
    for f in datasets.get("carta_control_interno") or []:
        def n_(k, f=f):
            v = a_num(f.get(k)) if str(f.get(k, "") or "").strip() else None
            return None if v is None else float(v)
        pr, im, co = n_("probabilidad"), n_("impacto"), n_("control")
        inh = None if pr is None or im is None else pr * im
        # NIA 315 (rev.) y NIA 330: el control solo rebaja el riesgo si el auditor probará su eficacia operativa. Si no se
        # prueba, el riesgo de incorrección material valorado es el inherente.
        probar = "Sí" if norm(f.get("probar_control")) in ("si", "s", "yes", "true", "1", "x") else "No"
        # Riesgo significativo (NIA 315 párr. 32 y NIA 330 párr. 21): se juzga sobre el riesgo INHERENTE, antes de los
        # controles; un control fuerte no lo vuelve «Bajo». Lleva el nivel al menos a Alto.
        # A7 (NIA 240): un hallazgo de la carta que menciona fraude es riesgo significativo, cualquiera sea su calificación.
        fraude = "fraude" in (str(f.get("proceso", "") or "") + " " + str(f.get("hallazgo", "") or "")).lower()
        sig = "Sí" if fraude or (inh is not None and inh >= u_sig) else "No" if inh is not None else ""
        proceso = str(f.get("proceso", "") or "").strip()
        hallazgo = str(f.get("hallazgo", "") or "").strip()
        comp, ti = enc_m.clasifica(proceso + " " + hallazgo)
        carta.append({"id": str(f.get("id", "")).strip(), "proceso": proceso, "hallazgo": hallazgo,
                      "aser": str(f.get("aseveraciones", "") or "").strip(), "p": pr, "i": im, "c": co, "inh": inh,
                      "sig": sig, "probarDs": probar, "respuesta": str(f.get("respuesta", "") or "").strip(), "comp": comp, "ti": ti,
                      "area": _area(proceso + " " + hallazgo), "bastan": cal_m.bastan(proceso + " " + hallazgo, ti) == cal_m.SI_BASTAN,
                      "herramienta": _herramienta(proceso + " " + hallazgo)})
    # Enfoque por ciclo (hoja 45): sustantivo por política de la firma, salvo que el socio registre «Confiar en controles» para el
    # ciclo (decisión del dueño, 2026-09-27). Confiar en los controles del ciclo obliga a probar
    # su eficacia: el hallazgo pasa a «¿Se probará el control?» = Sí y su riesgo valorado considera el control.
    enf = enf_m.enfoque(carta, u_alto, {x["ciclo"]: x["decision"] for x in reg.get("enfoque") or []})
    for x in carta:
        e = next((y for y in enf if y["ciclo"] == enf_m.ciclo_de(x["area"])), None)
        x["probar"] = "Sí" if x["probarDs"] == "Sí" or (e and e["confia"]) else "No"
        inh, co = x["inh"], x["c"]
        x["res"] = res = (None if inh is None else inh if x["probar"] != "Sí" else None if co is None else inh * (6 - co) / 5)
        x["nivel"] = ("Pendiente de calificación" if res is None else "Alto" if x["sig"] == "Sí" or res >= u_alto
                      else "Medio" if res >= u_medio else "Bajo")

    # 8 · informe del año anterior y notas
    informe = []
    for f in datasets.get("informe_anterior") or []:
        t = _tipo_informe(f.get("tipo")) or "Otro asunto"
        v = a_num(f.get("importe")) if str(f.get("importe", "") or "").strip() else None
        informe.append({"concepto": str(f.get("concepto", "") or "").strip(), "tipo": t, "detalle": str(f.get("detalle", "") or "").strip(),
                        "importe": None if v is None else float(v), "fuente": str(f.get("fuente", "") or "").strip(),
                        "enfoque": str(f.get("enfoque", "") or "").strip()})
    notas = []
    for f in datasets.get("notas_estados_financieros") or []:
        pref = [_cod(x) for x in re.split(r"[,;/\s]+", str(f.get("codigos", "") or "")) if _cod(x)]
        aud = a_num(f.get("saldo_auditado"))
        n = {"nota": str(f.get("nota", "")).strip(), "titulo": str(f.get("titulo", "") or "").strip(),
             "codigos": str(f.get("codigos", "") or "").strip(), "pref": pref, "auditado": float(aud or 0)}
        n["ant"] = sum(psum("ant", c) for c in pref)
        n["act"] = sum(psum("act", c) for c in pref)
        n["dif"] = n["ant"] - n["auditado"]
        n["var"] = n["act"] - n["ant"]
        n["varPct"] = None if n["ant"] == 0 else n["var"] / abs(n["ant"])
        notas.append(n)
    # Composición auditada de cada nota (líneas del informe): suma de las líneas de saldo contra el saldo de la nota.
    notas_det = []
    for f in datasets.get("notas_detalle") or []:
        v = a_num(f.get("importe"))
        notas_det.append({"nota": str(f.get("nota", "")).strip(), "concepto": str(f.get("concepto", "") or "").strip(),
                          "tipo": _tipo_linea(f.get("tipo")) or "Saldo", "importe": float(v or 0)})
    for n in notas:
        ls = [x for x in notas_det if x["nota"] == n["nota"]]
        n["det"] = bool(ls)
        n["suma"] = sum(x["importe"] for x in ls if x["tipo"] == "Saldo")
        n["difDet"] = n["suma"] - n["auditado"] if ls else 0.0

    # Certificado de RUC (RQ-008): identificación oficial de la entidad, su actividad (CIIU) y obligaciones (SRI).
    ruc = (datasets.get("ruc_certificado") or [{}])[0] or {}

    # 9 · posibles riesgos (NIA 240, 570, balances e informe anterior) — mismo orden que la hoja 13
    ia, ip = ind["act"], est9["act"]
    # A2: en un corte parcial los días sobre 365 salen mayores; los umbrales se comparan con días × meses ÷ 12.
    fac = meses / 12 if prelim else 1.0

    def dvar(k):
        return None if ind["act"][k] is None or ind["ant"][k] is None else _xr(ind["act"][k] - ind["ant"][k], 2)

    def aj(v):   # días ajustados al período (hoja 10, columnas I y J): × meses ÷ 12 en la preliminar
        return None if v is None else _xr(v * fac, 2)
    valor = {"presuncion": ip["Ventas netas"], "elusion": None, "ct": ia["capitalTrabajo"], "rc": ia["razonCorriente"],
             "end": ia["endTotal"], "end80": ia["endTotal"], "perdida": ip["Utilidad neta"], "patrimonio": ip["PATRIMONIO TOTAL"],
             "cartera": aj(ia["diasCartera"]), "inventario": aj(ia["diasInventario"]), "rotCartera": aj(dvar("diasCartera")),
             "rotInventario": aj(dvar("diasInventario"))}

    def presenta(cod_, v):
        if cod_ == "presuncion":
            return "No (refutada)" if sino["refutarIngresos"] == "Sí" else "Sí"
        if cod_ == "elusion":
            return "Sí"
        if v is None:
            return "No"
        return "Sí" if {"ct": v < 0, "rc": v < 1, "end": v > 70, "end80": v > 80, "perdida": v < 0, "patrimonio": v <= 0,
                        "cartera": v > 90, "inventario": v > 120, "rotCartera": v > u_dias,
                        "rotInventario": v > u_dias}[cod_] else "No"

    riesgos = []
    for cod_, origen, rubro, cond, rsg, sev, norma, resp, herr in _RIESGOS_BALANCE:
        if cod_ in ("cartera", "rotCartera"):
            herr = f"{herr}; {DETERIORO_CARTERA[marco]}"   # la herramienta de deterioro depende del marco del cliente
        riesgos.append({"cod": cod_, "origen": origen, "rubro": rubro, "cond": cond, "valor": valor[cod_],
                        "presenta": presenta(cod_, valor[cod_]), "riesgo": segun_marco(rsg, marco), "sev": sev, "norma": norma,
                        "resp": segun_marco(resp, marco), "herr": herr})
    nivel3 = [x for x in cuentas if x["nivel"] == 3 and x["sec"] in SECCIONES[:6]]
    top_var = sorted([x for x in nivel3 if alcanza(x["var"])], key=lambda x: -abs(x["var"]))[:6]
    for x in top_var:
        riesgos.append({"cod": "variacion", "cuenta": x["codigo"], "origen": "Balances", "rubro": f"{x['codigo']} {x['cuenta']}",
                        "cond": "Variación superior a la materialidad de desempeño", "valor": x["var"], "presenta": "Sí",
                        "riesgo": "Variación material sin explicación documentada; requiere sustento", "sev": "Medio",
                        "norma": "NIA 520", "resp": "Obtener y corroborar la explicación de la administración.",
                        "herr": _herramienta(x["cuenta"], x["sec"])})
    for j, x in enumerate(informe):
        if x["tipo"] == "Entendimiento":     # hallazgo del entendimiento de la entidad → riesgo del año (NIA 315 párr. 19)
            riesgos.append({"cod": "entendimiento", "idx": j, "origen": "Entendimiento de la entidad", "rubro": x["concepto"],
                            "cond": "Hallazgo del entendimiento de la entidad y su entorno (hoja 14)", "valor": x["importe"],
                            "presenta": "Sí", "riesgo": x["enfoque"] or EFECTO_INFORME["Entendimiento"], "sev": "Medio",
                            "norma": "NIA 315", "resp": x["enfoque"] or "Diseñar la respuesta al riesgo identificado (NIA 330).",
                            "herr": _herramienta(x["concepto"] + " " + x["detalle"])})
        elif x["tipo"] == "Opinión" and _opinion_modificada(x["detalle"]):
            # D10: la opinión modificada del año anterior es un riesgo del año (la causa puede persistir, NIA 710).
            t_ = _opinion_modificada(x["detalle"])
            riesgos.append({"cod": "informe", "idx": j, "origen": "Informe anterior", "rubro": x["concepto"],
                            "cond": f"Opinión modificada del año anterior ({OPINION_TXT[t_]})", "valor": x["importe"],
                            "presenta": "Sí", "riesgo": "Verificar si la causa de la opinión modificada persiste y su efecto en la "
                                                        "opinión de este año y en las cifras comparativas",
                            "sev": "Alto", "norma": NORMA_INFORME[t_],
                            "resp": ("Identificar la causa de la modificación, comprobar si se corrigió y evaluar el efecto en los "
                                     "saldos de apertura, las cifras comparativas y el informe actual."),
                            "herr": _herramienta(x["concepto"] + " " + x["detalle"])})
        elif x["tipo"] in SEV_INFORME:
            riesgos.append({"cod": "informe", "idx": j, "origen": "Informe anterior", "rubro": x["concepto"],
                            "cond": f"{x['tipo']} del informe de auditoría del año anterior", "valor": x["importe"], "presenta": "Sí",
                            "riesgo": "Verificar si el asunto persiste y su efecto en la opinión de este año",
                            "sev": SEV_INFORME[x["tipo"]], "norma": NORMA_INFORME[x["tipo"]],
                            "resp": "Revisar la corrección del asunto, sus saldos al cierre y el efecto en el informe actual.",
                            "herr": _herramienta(x["concepto"] + " " + x["detalle"])})
    riesgos.append({"cod": "inicial", "origen": "Encargo", "rubro": "Saldos de apertura", "cond": "Encargo inicial (primer año de auditoría)",
                    "valor": None, "presenta": sino["encargoInicial"],
                    "riesgo": "Saldos de apertura con incorrecciones o políticas no uniformes", "sev": "Medio", "norma": "NIA 510",
                    "resp": "Revisar los papeles del auditor predecesor o aplicar procedimientos a los saldos de apertura.",
                    "herr": SIN_HERRAMIENTA})
    # A17 (NIA 510 y 710): estados del año anterior auditados por otro auditor o no auditados.
    ea = pe["estadosAnteriores"]
    riesgos.append({"cod": "anterior_otro", "origen": "Encargo", "rubro": "Saldos de apertura",
                    "cond": "Estados del año anterior auditados por otro auditor", "valor": None,
                    "presenta": "Sí" if ea == "Auditados por otro auditor" else "No",
                    "riesgo": "Saldos de apertura auditados por otro auditor: revisar sus papeles de trabajo y evaluar su opinión",
                    "sev": "Medio", "norma": "NIA 510",
                    "resp": ("Revisar los papeles del auditor predecesor (NIA 510 párr. 6) y considerar el párrafo de otras "
                             "cuestiones sobre las cifras comparativas (NIA 710 párr. 13 — VERIFICAR)."), "herr": SIN_HERRAMIENTA})
    riesgos.append({"cod": "anterior_no", "origen": "Encargo", "rubro": "Saldos de apertura",
                    "cond": "Estados del año anterior no auditados", "valor": None,
                    "presenta": "Sí" if ea == "No auditados" else "No",
                    "riesgo": "Saldos de apertura sin auditar: pueden contener incorrecciones que afecten el período actual",
                    "sev": "Alto", "norma": "NIA 510",
                    "resp": ("Aplicar procedimientos sustantivos a los saldos de apertura (NIA 510 párr. 6) e indicar en el informe "
                             "que las cifras comparativas no fueron auditadas (NIA 710 párr. 14 — VERIFICAR)."),
                    "herr": SIN_HERRAMIENTA})
    for k, r_ in enumerate(riesgos):
        r_["codigo"] = f"RB-{k + 1:02d}"
    # A1–A19 · evaluaciones automáticas (hojas 24, 26 y 27): su alerta es un riesgo más de la hoja 13.
    filas_reg, pos_reg = enc_m.filas_registros(reg)
    eq_est = [enc_m.estado_equipo(x, sino["interesPublico"], pe["aniosRotacionSocio"]) for x in reg["equipo"]]
    ip_ant = est9["ant"]
    vp_ven = None if not ip_ant["Ventas netas"] else (ip["Ventas netas"] - ip_ant["Ventas netas"]) / abs(ip_ant["Ventas netas"])
    ctx = {"reg": reg, "pos": pos_reg, "n_reg": len(filas_reg), "R12": R12, "R13": R13, "H8": H8, "E9": E9, "F9": F9, "I10": I10,
           "F10": F10, "par": _par, "n12": len(carta), "n13": len(riesgos), "n8": len(cuentas), "n_inf": len(informe),
           "carta": carta, "riesgos": riesgos, "cuentas": cuentas, "marco": marco, "n_eq": len(reg["equipo"]), "eq_estados": eq_est,
           "fila27": f"'{enc_m.H27}'!$I${FILA0}:$I${FILA0 + len(enc_m.COMPONENTES) + len(enc_m.TI) - 1}",
           "alertas27": bool(carta), "datos": {"ut": ip["Utilidad neta"], "pat": ip["PATRIMONIO TOTAL"], "end": ia["endTotal"],
                                              "vven": vp_ven, "umbral": umbral_var}}
    evals = enc_m.evaluaciones(ctx)
    base_rb = len(riesgos)
    riesgos += enc_m.riesgos(evals, SIN_HERRAMIENTA)
    for k, r_ in enumerate(riesgos[base_rb:], start=base_rb):
        r_["codigo"] = f"RB-{k + 1:02d}"
    pe["estadosAnteriores"] = enc_m.estados_anteriores(pe["estadosAnteriores"], sino["encargoInicial"], bool(informe))
    # M12, M14, M15 y M19: estimaciones, partes relacionadas, indicios no financieros de empresa en funcionamiento y uniformidad.
    est_items = cal_m.estimaciones(cuentas, desemp)
    partes_items = cal_m.partes(cuentas, desemp)
    nofin = cal_m.em_no_financieros(carta, informe, notas)
    n40 = len(partes_items) + len(cal_m.partes_textos(informe, notas)) + 1
    unif = cal_m.uniformidad(informe, notas, marco)
    base_rb = len(riesgos)
    riesgos += [
        {"cod": "estimacion", "origen": "Balances", "rubro": "Estimaciones contables (hoja 38)",
         "cond": "Estimaciones con incertidumbre alta por su importe o su subjetividad", "valor": None,
         "presenta": "Sí" if any(y["inc"] == "Alta" for y in est_items) else "No",
         "f_pres": f'IF(COUNTIF({cal_m.rng(cal_m.H38, "H", len(est_items))},"Alta")>0,"Sí","No")',
         "riesgo": "Estimaciones contables con incertidumbre alta: posible sesgo de la dirección", "sev": "Alto", "norma": "NIA 540",
         "resp": ("Probar el método, los datos y los supuestos; desarrollar una estimación puntual o un rango y hacer la revisión "
                  "retrospectiva (NIA 540 párr. 13, 14 y 18 — VERIFICAR)."), "herr": SIN_HERRAMIENTA},
        {"cod": "partes", "origen": "Balances", "rubro": "Partes relacionadas (hoja 40)",
         "cond": "Cuenta con partes relacionadas nueva o con variación material (fuera del curso normal)", "valor": None,
         "presenta": "Sí" if any(y["fuera"] for y in partes_items) else "No",
         "f_pres": f'IF(COUNTIF({cal_m.rng(cal_m.H40, "G", n40)},"Sí*")>0,"Sí","No")',
         "riesgo": "Transacciones con partes relacionadas fuera del curso normal de los negocios", "sev": "Significativo",
         "norma": "NIA 550", "resp": ("Inspeccionar los contratos, la autorización y las condiciones; confirmar los saldos con la "
                                      "parte relacionada y evaluar su revelación (NIA 550 párr. 23 — VERIFICAR)."),
         "herr": HERRAMIENTAS["Costos y gastos"]},
        {"cod": "em_nofin", "origen": "Documentos del año anterior", "rubro": cal_m.EM_RUBRO,
         "cond": "Indicios no financieros en la carta, el informe o las notas (litigios, clientes clave, licencias, sanciones)",
         "valor": None, "presenta": "Sí" if nofin else "No",
         "f_pres": (f"IF(COUNTIF('{cal_m.H41}'!$D${FILA0 + 1}:$D${FILA0 + max(len(nofin), 1)},\"Sí\")>0,\"Sí\",\"No\")"),
         "riesgo": "Indicios no financieros sobre la capacidad de continuar como empresa en funcionamiento", "sev": "Alto",
         "norma": "NIA 570", "resp": "Obtener la evaluación de la dirección y sus planes; evaluar la revelación (NIA 570).",
         "herr": SIN_HERRAMIENTA},
        {"cod": "uniformidad", "origen": "Documentos del año anterior", "rubro": "Políticas contables",
         "cond": unif["cond"], "valor": None, "presenta": unif["presenta"],
         "riesgo": "Políticas contables no uniformes o cambio de marco: comparabilidad de las cifras (NIA 510 párr. 7)",
         "sev": "Medio", "norma": "NIA 510",
         "resp": segun_marco("Verificar que las políticas se aplicaron de forma uniforme o que el cambio se contabilizó y reveló "
                             "(NIC 8).", marco), "herr": SIN_HERRAMIENTA},
    ]
    for k, r_ in enumerate(riesgos[base_rb:], start=base_rb):
        r_["codigo"] = f"RB-{k + 1:02d}"

    # 10 · anomalías (sobre las cuentas de detalle del análisis horizontal)
    anomalias = []
    for x in cuentas:
        if x["detalle"] != "Sí":
            continue
        nm = _sin_tildes(x["cuenta"]).lower()
        if x["act"] < -0.005 and not _CONTRA.search(nm) and x["sec"] in ("Activo", "Pasivo") and alcanza(x["act"], 0.5):
            anomalias.append({"tipo": "Signo", "x": x, "col": "act", "sev": "Alto",
                              "det": f"Saldo negativo en una cuenta de {x['sec'].lower()} que por naturaleza debería ser positiva; "
                                     "verificar si es una cuenta correctora."})
        if x["ant"] == 0 and alcanza(x["act"]):
            anomalias.append({"tipo": "Nueva", "x": x, "col": "act", "sev": "Medio",
                              "det": "Cuenta sin saldo en el período anterior y con saldo material en el actual."})
        if x["act"] == 0 and alcanza(x["ant"]):
            anomalias.append({"tipo": "Baja", "x": x, "col": "ant", "sev": "Medio",
                              "det": "Cuenta con saldo material en el período anterior y sin saldo en el actual."})
        if x["varPct"] is not None and abs(x["varPct"]) * 100 >= umbral_ext and alcanza(x["var"]):
            anomalias.append({"tipo": "Variación", "x": x, "col": "var", "sev": "Medio",
                              "det": "Variación extrema entre períodos: supera el umbral de anomalías y la materialidad de desempeño."})
    grupos = {}
    for x in cuentas:
        if x["detalle"] == "Sí" and alcanza(x["act"]):
            grupos.setdefault(round(x["act"], 2), []).append(x)
    for g in grupos.values():
        if len(g) >= 2:
            anomalias.append({"tipo": "Duplicado", "x": g[0], "col": "act", "sev": "Bajo", "grupo": [y["codigo"] for y in g],
                              "det": f"Mismo importe en {len(g)} cuentas distintas; verificar posible duplicidad."})
    orden = {"Alto": 0, "Medio": 1, "Bajo": 2}
    n_anom = len(anomalias)
    anomalias = sorted(anomalias, key=lambda a: orden[a["sev"]])[:MAX_ANOMALIAS]

    # 11 · cuentas principales a revisar (nivel 3, o nivel 2 si hay menos de 3)
    lvl = 3 if len(nivel3) >= 3 else 2
    revisar = []
    for x in cuentas:
        if x["nivel"] != lvl or x["sec"] not in SECCIONES[:6]:
            continue
        area_x = _area(x["cuenta"], x["sec"])
        rk = next((r_ for r_ in carta if area_x and _area(r_["proceso"] + " " + r_["hallazgo"]) == area_x), None)
        # Todas las cuentas del nivel quedan en la hoja 18 con su marca por fórmula: si el auditor cambia la
        # materialidad, cambia cuáles se revisan.
        rbi = _riesgos_de(x, riesgos)
        rb = " ".join(riesgos[i]["codigo"] for i in rbi if riesgos[i]["presenta"] == "Sí")
        revisar.append({"x": x, "riesgo": rk["id"] if rk else "", "rbi": rbi, "rb": rb, "herr": _herramienta(x["cuenta"], x["sec"]),
                        "revisa": "Sí" if x["material"] == "Sí" or x["varMaterial"] == "Sí" or rk or rb else "No"})
    revisar.sort(key=lambda r_: -abs(r_["x"]["act"]))
    # M11: analíticos sustantivos de las cuentas de resultados del mismo nivel.
    an_items = cal_m.analiticos([x for x in cuentas if x["nivel"] == lvl and x["sec"] in ("Ingresos", "Costos", "Gastos")],
                                (est9["ant"]["Ventas netas"], est9["act"]["Ventas netas"]), desemp, pc["pctUmbralAnalitico"])

    # 12 · asuntos para la planificación
    probs = _problemas(p, sino, base_nombre, periodo, base_valor, sec7, riesgos, carta, anomalias, notas, informe, fuentes["act"])
    for k, etq in (("ant", ETQ_BC["ant"]), ("act", ETQ_BC["act"])):
        for x in [y for y in fuentes[k] if abs(y["difsub"]) >= 0.01][:10]:
            probs.append(problema("JERARQUIA_NO_SUMA", f"{etq} · {x['codigo']} {x['cuenta']}: la cuenta no suma sus subcuentas "
                                                       f"(diferencia {m(x['difsub'])}); se usa su saldo propio (R1). Verifique el "
                                                       "archivo del cliente.", x["difsub"]))
    if not str(p.get("justificacion") or "").strip():
        probs.append(problema("JUSTIFICACION_AUTOMATICA", "La justificación de la base de la materialidad es el texto automático: "
                                                          "confírmela o reescríbala con los hechos del encargo (NIA 320 párr. 14).", 0))
    if prelim and meses != corte_a.month:
        probs.append(problema("MESES_NO_COINCIDEN", f"Revisión preliminar con {meses} meses transcurridos y corte en el mes "
                                                    f"{corte_a.month}: confirme los meses (prorrateo del año anterior).", 0))
    difs = enc_m.diferencias(notas, informe, {j: j for j in range(len(informe))}, {"N15": "", "P14": ""})
    dres = enc_m.calcula_diferencias(difs, {"trivial": triv, "desempeno": desemp, "global": mat})
    probs += _problemas_encargo(reg, evals, eq_est, sino, pe, fechas, corte_a, tipo, dres, mat, desemp)
    if hay_eri and not prelim:
        probs.append(problema("ERI_NO_USADO", "Se entregó el estado de resultados del año anterior al mismo corte, pero la revisión "
                                              "es final: los resultados se comparan diciembre contra diciembre y ese anexo no se usa.", 0))

    n_altos = sum(1 for r_ in carta if r_["nivel"] == "Alto") + sum(
        1 for r_ in riesgos if r_["presenta"] == "Sí" and r_["sev"] in ("Alto", "Significativo"))
    sug = _desempeno_sugerido(sino, dres, triv, carta, riesgos)
    probs += _problemas_calidad(carta, an_items, anomalias, sug, pct["pctDesempeno"], reg, nofin, bool(riesgos_em(riesgos)))
    if n_anom > MAX_ANOMALIAS:
        probs.append(problema("ANOMALIAS_CORTADAS", f"Se detectaron {n_anom} anomalías y la hoja 17 muestra las {MAX_ANOMALIAS} más "
                                                    f"severas; las otras {n_anom - MAX_ANOMALIAS} (de severidad igual o menor) se "
                                                    "revisan en las hojas 04, 05 y 08.", 0))
    for e in enf:
        if e["prop"] == enf_m.PROP_REVISAR:
            probs.append(problema("ENFOQUE_REVISAR", f"{e['ciclo']}: los procedimientos sustantivos no bastan y hay deficiencias de "
                                                     "control; evalúe si hay una limitación al alcance (NIA 330 párr. 8 b); NIA 705).", 0))
    totales = {"activos": r2(ip["TOTAL ACTIVO"]), "pasivos": r2(ip["TOTAL PASIVO"]), "patrimonio": r2(ip["PATRIMONIO TOTAL"]),
               "ventas": r2(ip["Ventas netas"]), "resultado": r2(ip["Utilidad neta"]), "materialidad": r2(mat or 0),
               "desempeno": r2(desemp or 0), "trivial": r2(triv or 0), "riesgosAltos": r2(n_altos),
               "cuentasRevisar": r2(sum(1 for r_ in revisar if r_["revisa"] == "Sí"))}
    etiquetas = {"activos": "Activo total", "pasivos": "Pasivo total", "patrimonio": "Patrimonio total", "ventas": "Ventas netas",
                 "resultado": "Utilidad neta del período", "materialidad": "Materialidad global", "desempeno": "Materialidad de desempeño",
                 "trivial": "Umbral de errores claramente insignificantes", "riesgosAltos": "Riesgos altos o significativos",
                 "cuentasRevisar": "Cuentas principales a revisar"}
    filas = [{"id": x["codigo"], "cuenta": x["cuenta"], "seccion": x["sec"], "saldo_anterior": r2(x["ant"]), "saldo_actual": r2(x["act"]),
              "variacion": r2(x["var"]), "material": x["material"]} for x in cuentas]
    detalle = {"corte": corte_a.isoformat(), "marco": marco, "edicion": edicion, "tipo": tipo, "meses": meses, "dias": dias, "mapa": mapa,
               "base": base_nombre, "periodo": periodo, "periodoParam": periodo_param, "anualiza": anualiza, "pct": pct, "bases": bases,
               "pctBase": pct_base, "umbrales": {"var": umbral_var, "ext": umbral_ext, "alto": u_alto, "medio": u_medio, "dias": u_dias, "sig": u_sig},
               "sino": sino, "fechas": fechas, "fuentes": fuentes, "hayEri": hay_eri, "bruto": bruto, "signo": signo, "sec7": sec7,
               "cuentas": cuentas, "est9": est9, "ind": ind,
               "materialidad": {"base": base_valor, "global": mat, "desempeno": desemp, "trivial": triv},
               "justificacion": justif, "carta": carta, "informe": informe, "notas": notas, "notasDet": notas_det, "ruc": ruc,
               "sinNota": _sin_nota(cuentas, notas), "riesgos": riesgos, "reg": reg, "evals": evals, "eqEst": eq_est, "pe": pe, "difs": difs, "dres": dres,
               "anomalias": anomalias, "revisar": revisar, "nivelRevisar": lvl, "parametros": p,
               "origenes": origenes, "puente": puente, "archivos": archivos, "arch_plat": arch_plat, "fac": fac,
               "otrosAbs": sum(abs(x["saldo"]) for x in fuentes["act"] if x["sec"] == "Otros" and x["detalle"] == "Sí"),
               "pc": pc, "ant": v_ant, "enf": enf, "est": est_items, "partes": partes_items, "nofin": nofin, "an": an_items, "sug": sug,
               "n40": n40}
    return {"engine": VERSION, "rows": filas, "totals": totales, "labels": etiquetas, "primary": "materialidad",
            "exceptions": probs, "schedule": [], "detalle": detalle}


def _indices(e: dict, dias: float) -> dict:
    """Índices del período con el mismo redondeo (ROUND 2) que la hoja 10."""
    ac, pc, inv, cxc, cxp = e["Activo corriente"], e["Pasivo corriente"], e["Inventarios"], e["Cuentas por cobrar"], e["Cuentas por pagar"]
    act_, pas, pnc, patt, obl = e["TOTAL ACTIVO"], e["TOTAL PASIVO"], e["Pasivo no corriente"], e["PATRIMONIO TOTAL"], e["Obligaciones financieras"]
    # Denominador patrimonial de los índices (endeudamiento financiero/patrimonial, apalancamiento, ROE y DuPont):
    # patrimonio SIN resultado + la utilidad neta CALCULADA del período (ERI), como el artefacto HTML. En un corte
    # preliminar el balance puede traer en el patrimonio un resultado distinto del que arroja el estado de resultados.
    patg = e["PATRIMONIO (sin resultado del período)"] + e["Utilidad neta"]
    ven, cos, ub, uo, un = e["Ventas netas"], e["(−) Costo de ventas"], e["Utilidad bruta"], e["Utilidad operativa"], e["Utilidad neta"]

    def q(a, b, f=1.0):
        v = _div(a, b)
        return None if v is None else _xr(v * f, 2)
    i = {"dias": _xr(dias, 2)}
    i["razonCorriente"] = q(ac, pc)
    i["pruebaAcida"] = q(ac - inv, pc)
    i["capitalTrabajo"] = _xr(ac - pc, 2)
    i["diasCartera"] = q(cxc * i["dias"], ven)
    i["diasInventario"] = q(inv * i["dias"], cos)
    i["diasProveedores"] = q(cxp * i["dias"], cos)
    i["ciclo"] = None if None in (i["diasCartera"], i["diasInventario"], i["diasProveedores"]) else _xr(
        i["diasCartera"] + i["diasInventario"] - i["diasProveedores"], 2)
    i["rotacionActivo"] = q(ven, act_)
    i["endTotal"] = q(pas, act_, 100)
    i["endLP"] = q(pnc, act_, 100)
    i["endFinanciero"] = q(obl, patg)
    i["endPatrimonial"] = q(pas, patg)
    i["multiplicador"] = q(act_, patg)
    i["margenBruto"] = q(ub, ven, 100)
    i["margenOperativo"] = q(uo, ven, 100)
    i["margenNeto"] = q(un, ven, 100)
    i["roi"] = q(uo, act_, 100)
    i["roe"] = q(un, patg, 100)
    # R5: el margen operativo es utilidad operativa ÷ ventas para que el DuPont reproduzca el ROI.
    # Los componentes del DuPont se multiplican sin redondear, para que reproduzcan el ROI y el ROE.
    i["dupontRoi"] = None if not ven or not act_ else _xr(uo / ven * 100 * (ven / act_), 2)
    i["dupont"] = None if not ven or not act_ or not patg else _xr(un / ven * 100 * (ven / act_) * (act_ / patg), 2)
    return i


def _problemas(p, sino, base_nombre, periodo, base_valor, sec7, riesgos, carta, anomalias, notas, informe, fuentes_act) -> list:
    probs = []
    if base_valor <= 0:
        probs.append(problema("BASE_NO_VALIDA", f"Base elegida ({base_nombre}, {periodo.lower()}): {m(base_valor)}; no sirve para la "
                                                "materialidad, elija otra base (NIA 320 párr. A4–A5).", base_valor))
    for k, cod_, txt in (("act", "ESF_NO_CUADRA", "al corte"), ("ant", "ESF_ANTERIOR_NO_CUADRA", "del cierre anterior")):
        dif = sec7[k]["Diferencia de cuadre"]
        if abs(dif) >= 0.01:
            probs.append(problema(cod_, f"El balance de comprobación {txt} no cuadra: activo − (pasivo + patrimonio + resultado) = "
                                        f"{m(dif)}. Revise el mapa de cuentas y el archivo del cliente.", dif))
    otros_abs = sum(abs(x["saldo"]) for x in fuentes_act if x["sec"] == "Otros" and x["detalle"] == "Sí")
    if otros_abs >= 0.01:
        probs.append(problema("CUENTAS_SIN_SECCION", f"Hay {m(otros_abs)} (en valor absoluto) en cuentas cuyo código no está en el "
                                                     "mapa de cuentas (sección «Otros»): complete el mapa.", otros_abs))
    for r_ in riesgos:
        if r_["presenta"] != "Sí":
            continue
        c_ = r_["cod"]
        if c_ == "presuncion":
            probs.append(problema("RIESGO_FRAUDE_INGRESOS", f"{r_['codigo']}: riesgo significativo presunto de fraude en el reconocimiento "
                                                            f"de ingresos ({m(r_['valor'])} de ventas): respuesta específica "
                                                            "(NIA 240 párr. 26 y 30).", r_["valor"]))
        elif c_ == "elusion":
            probs.append(problema("ELUSION_CONTROLES", f"{r_['codigo']}: riesgo de elusión de controles por la dirección: pruebas de "
                                                       "asientos, estimaciones y transacciones inusuales en todo encargo (NIA 240 párr. 31–33).", 0))
        elif c_ in ("ct", "perdida", "patrimonio"):
            code = {"ct": "CAPITAL_TRABAJO_NEGATIVO", "perdida": "PERDIDA_EJERCICIO", "patrimonio": "PATRIMONIO_NEGATIVO"}[c_]
            probs.append(problema(code, f"{r_['codigo']}: {r_['cond']} ({m(r_['valor'])}): indicio sobre la empresa en funcionamiento "
                                        "(NIA 570 párr. 10).", r_["valor"]))
        elif c_ in ("rc", "end", "end80", "cartera", "inventario", "rotCartera", "rotInventario"):
            code = {"rc": "RAZON_CORRIENTE_BAJA", "end": "ENDEUDAMIENTO_ALTO", "end80": "ENDEUDAMIENTO_ALTO",
                    "cartera": "DIAS_CARTERA_ALTOS", "inventario": "DIAS_INVENTARIO_ALTOS", "rotCartera": "ROTACION_CARTERA",
                    "rotInventario": "ROTACION_INVENTARIO"}[c_]
            probs.append(problema(code, f"{r_['codigo']}: {r_['cond']}: {r_['riesgo'][0].lower()}{r_['riesgo'][1:]}.", 0))
        elif c_ == "variacion":
            probs.append(problema("VARIACION_MATERIAL", f"{r_['rubro']}: variación de {m(r_['valor'])}, superior a la materialidad de "
                                                        "desempeño; obtenga y corrobore la explicación (NIA 520).", r_["valor"]))
        elif c_ == "informe":
            probs.append(problema("INFORME_ANTERIOR", f"{r_['rubro']}: {r_['cond'][0].lower()}{r_['cond'][1:]}; verifique si persiste "
                                                      f"({r_['norma']}).", r_["valor"] or 0))
        elif c_ == "inicial":
            probs.append(problema("ENCARGO_INICIAL", "Encargo inicial: planifique los procedimientos sobre saldos de apertura "
                                                     "(NIA 510 párr. 6; NIA 300 párr. 13).", 0))
        elif c_ in ("anterior_otro", "anterior_no"):
            probs.append(problema("ESTADOS_ANTERIORES", f"{r_['codigo']}: {r_['cond']}: {r_['resp']}", 0))
        elif c_ == "cuestionario":
            probs.append(problema("CUESTIONARIO_ALERTA", f"{r_['codigo']} · {r_['q']}: {r_['riesgo']}", 0))
    if sino["refutarIngresos"] == "Sí" and not str(p.get("motivoRefutacion") or "").strip():
        probs.append(problema("REFUTACION_SIN_MOTIVO", "Se refutó la presunción de fraude en ingresos sin documentar el motivo "
                                                       "(NIA 240 párr. 47).", 0))
    for r_ in carta:
        if r_["nivel"] == "Alto":
            que = ("riesgo significativo (inherente alto aunque el control lo reduzca; NIA 315 párr. 32)" if r_["sig"] == "Sí"
                   else "riesgo valorado alto")
            probs.append(problema("RIESGO_CCI_ALTO", f"{r_['id']}: {r_['proceso']} · {que} en la carta de control interno; "
                                                     "respuesta específica en el programa (NIA 330).", 0))
        elif r_["nivel"].startswith("Pendiente"):
            probs.append(problema("RIESGO_CCI_PENDIENTE", f"{r_['id']}: {r_['proceso']} · pendiente de calificación del socio "
                                                          "(probabilidad, impacto y control).", 0))
    for a in anomalias:
        cods = ", ".join(a.get("grupo") or [a["x"]["codigo"]])
        probs.append(problema("ANOMALIA", f"{cods} {a['x']['cuenta']} · {a['tipo']}: {a['det']}", a["x"][a["col"]]))
    for n in notas:
        if abs(n["dif"]) >= 0.01:
            probs.append(problema("NOTA_NO_CONCILIA", f"Nota {n['nota']}: el balance del cierre anterior difiere de la nota auditada en "
                                                      f"{m(n['dif'])} (saldos de apertura, NIA 510 párr. 6).", n["dif"]))
    if not carta:
        probs.append(problema("SIN_CARTA_CI", "No se cargó la carta de control interno: la matriz de riesgos solo tiene los riesgos "
                                              "detectados en los balances (NIA 315 párr. 21–22; NIA 265).", 0))
    if not informe:
        probs.append(problema("SIN_INFORME_ANTERIOR", "No se cargó el informe de auditoría del año anterior: documente el perfil del "
                                                      "encargo y los asuntos previos (NIA 300 párr. 13; NIA 510).", 0))
    if not notas:
        probs.append(problema("SIN_NOTAS_ANTERIOR", "No se cargaron las notas a los estados financieros del año anterior: los saldos "
                                                    "de apertura no se cotejan con los estados auditados (NIA 510 párr. 6).", 0))
    return probs


def calendario(fechas: dict, corte: str, tipo: str) -> str:
    """A16 (NIA 300): visita preliminar ≤ visita final ≤ informe; en la revisión final, la visita final y el informe después
    del corte. «Revisar» si falta una fecha o el orden no es coherente (espejo del control 20 de la hoja 16)."""
    fp, ff, fi = (fechas.get(k) for k in ("fechaPreliminar", "fechaFinal", "fechaInforme"))
    if not (fp and ff and fi):
        return "Revisar"
    ok = fp <= ff <= fi and (tipo != "Final" or (ff >= corte and fi >= corte))
    return "Conforme" if ok else "Revisar"


def _problemas_encargo(reg, evals, eq_est, sino, pe, fechas, corte_a, tipo, dres, mat, desemp) -> list:
    """Asuntos del encargo (A1–A19): registros pendientes en la plataforma, independencia, revisor de calidad, año anterior,
    calendario y diferencias acumuladas. Las alertas con riesgo ya salen como CUESTIONARIO_ALERTA desde la hoja 13."""
    probs = []
    pend = [x["codigo"] for x in evals if x["estado"] == "Pendiente"]
    if pend:
        probs.append(problema("REGISTROS_PENDIENTES", f"Planificación: {len(pend)} evaluaciones pendientes ({', '.join(pend)}); "
                                                      "complete los registros de la plataforma o los documentos de entrada "
                                                      "(hojas 24, 26 y 27).", 0))
    if not reg["equipo"]:
        probs.append(problema("EQUIPO_NO_DOCUMENTADO", "Nadie confirmó su independencia en la plataforma (Código IESBA; NIA 220).", 0))
    for x, e in zip(reg["equipo"], eq_est):
        if e.startswith("Alerta"):
            probs.append(problema("INDEPENDENCIA", f"{x['integrante']} ({x['rol']}): {e[len('Alerta · '):]} (hoja 25).", 0))
    if sino["interesPublico"] == "Sí" and not any(x["rol"] == "Revisor de calidad" for x in reg["equipo"]):
        probs.append(problema("REVISOR_CALIDAD", "Entidad de interés público sin revisor de calidad del encargo registrado en la "
                                                 "plataforma (NIGC 2; NIA 220 párr. 36 — VERIFICAR).", 0))
    ea = pe["estadosAnteriores"]
    if not ea:
        probs.append(problema("ESTADOS_ANTERIORES_PENDIENTE", "Encargo inicial sin informe del año anterior: indique en la hoja 02 si "
                                                              "los estados anteriores no fueron auditados (NIA 510; NIA 710).", 0))
    elif (sino["encargoInicial"] == "No") != (ea == "Auditados por nosotros"):
        probs.append(problema("ESTADOS_ANTERIORES_INCOHERENTE", f"Estados del año anterior «{ea}» con encargo inicial "
                                                                f"«{sino['encargoInicial']}»: revise ambos datos de la hoja 02.", 0))
    if calendario(fechas, corte_a.isoformat(), tipo) != "Conforme":
        probs.append(problema("CALENDARIO_INCOHERENTE", "Calendario del encargo incompleto o incoherente: la visita preliminar debe "
                                                        "ir antes de la final y esta antes del informe; en la revisión final, la visita "
                                                        "final y el informe después del corte (NIA 300 párr. 8 c)).", 0))
    if mat and desemp and abs(dres["total"]) >= desemp - 1e-9:
        probs.append(problema("DIFERENCIAS_MATERIALES", f"Diferencias acumuladas no corregidas de {m(dres['total'])}: "
                                                        f"{dres['conclusion'].split(' · ', 1)[-1]} (hoja 30).", dres["total"]))
    return probs


def _huella(filas_: list) -> str:
    """SHA-256 de las filas leídas de un documento (JSON con claves ordenadas): identifica los datos exactos de la ejecución."""
    return hashlib.sha256(json.dumps(filas_, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def riesgos_em(riesgos: list, financieros: bool = False) -> list:
    """Indicios de empresa en funcionamiento presentes en la hoja 13; con ``financieros``, sin el indicio no financiero (hoja 41)."""
    return [x for x in riesgos if x["norma"] == "NIA 570" and x["presenta"] == "Sí" and not (financieros and x["cod"] == "em_nofin")]


def _desempeno_sugerido(sino: dict, dres: dict, triv, carta: list, riesgos: list) -> dict:
    """M9 (NIA 320 párr. A12): el porcentaje de desempeño baja con el encargo inicial, el historial de diferencias y los
    riesgos significativos (política de la firma: 75 % sin factores, 60 % con uno y 50 % con dos o más)."""
    f = []
    if sino["encargoInicial"] == "Sí":
        f.append("encargo inicial")
    if triv and abs(dres["total"]) >= triv:
        f.append("diferencias del año anterior sobre el umbral trivial")
    if any(x["sig"] == "Sí" for x in carta) or any(x["presenta"] == "Sí" and x["sev"] == "Significativo" for x in riesgos):
        f.append("riesgos significativos")
    return {"factores": f, "pct": 75.0 if not f else 60.0 if len(f) == 1 else 50.0}


def _problemas_calidad(carta, an_items, anomalias, sug, pct_desemp, reg, nofin, em_hay) -> list:
    """Asuntos de M1–M21: controles que deben probarse, analíticos por investigar, signos contrarios en la base,
    desempeño sobre el sugerido, consultas abiertas y evaluación de empresa en funcionamiento pendiente."""
    probs = []
    for x in cal_m.controles_necesarios(carta):
        probs.append(problema("CONTROLES_NECESARIOS", f"{x['id']} · {x['proceso']}: proceso automatizado o de alto volumen; los "
                                                      "procedimientos sustantivos solos no bastan: marque «¿Se probará el control?» "
                                                      "en la carta (NIA 315 párr. 33; hoja 34).", 0))
    n_inv = sum(1 for y in an_items if y["res"] == cal_m.AN_INV)
    if n_inv:
        probs.append(problema("ANALITICOS_INVESTIGAR", f"{n_inv} cuentas de resultados difieren de su expectativa más que el umbral: "
                                                       "obtener y corroborar la explicación (NIA 520; hoja 37).", 0))
    n_sig = sum(1 for a in anomalias if a["tipo"] == "Signo")
    if n_sig:
        probs.append(problema("SIGNO_EN_BASE", f"{n_sig} cuentas con signo contrario a su naturaleza afectan la base de la "
                                               "materialidad y los índices: revíselas antes de fijar la materialidad (NIA 320; "
                                               "hojas 11 y 17).", 0))
    if pct_desemp > sug["pct"] + 1e-9:
        probs.append(problema("DESEMPENO_SOBRE_SUGERIDO", f"El porcentaje de desempeño de la hoja 02 ({_num(pct_desemp)} %) supera el "
                                                          f"sugerido por los factores del encargo ({_num(sug['pct'])} %: "
                                                          f"{', '.join(sug['factores'])}); justifíquelo (NIA 320 párr. A12).", 0))
    abiertas = [x for x in reg.get("consultas") or [] if x["estado"] == enc_m.ABIERTA]
    if abiertas:
        probs.append(problema("CONSULTAS_ABIERTAS", f"{len(abiertas)} consultas o diferencias de opinión abiertas: la planificación "
                                                    "no se aprueba hasta resolverlas (NIA 220; hoja 00_Registros).", 0))
    if em_hay and not any(x["tema"] == cal_m.EM_TEMA for x in reg.get("indagaciones") or []):
        probs.append(problema("EM_EVALUACION_PENDIENTE", "Hay indicios de empresa en funcionamiento y no se documentó la evaluación de la "
                                                         "dirección: regístrela en la plataforma como indagación (NIA 570; hoja 41).",
                              0))
    return probs


def _estrategia_encargo(d: dict, carta: list, riesgos: list, afirm: list, n_eeff: int) -> list:
    """A16 (NIA 300 párr. 8–10): riesgos significativos por nombre, empresa en funcionamiento, año anterior, calendario, equipo e
    independencia, revisor de calidad, respuestas globales y diferencias."""
    partes_f, partes_v = [], []
    for i, x in enumerate(carta):
        r = FILA0 + i
        partes_f.append(f'IF({R12}M{r}="Sí",{R12}A{r}&" · "&{R12}B{r}&"; ","")')
        if x["sig"] == "Sí":
            partes_v.append(f"{x['id']} · {x['proceso']}; ")
    for j, x in enumerate(riesgos):
        if x["sev"] != "Significativo":
            continue
        r = FILA0 + j
        partes_f.append(f'IF(AND({R13}F{r}="Sí",{R13}H{r}="Significativo"),{R13}A{r}&" · "&{R13}C{r}&"; ","")')
        if x["presenta"] == "Sí":
            partes_v.append(f"{x['codigo']} · {x['rubro']}; ")
    todo_f = "&".join(partes_f) if partes_f else '""'
    todo_v = "".join(partes_v)
    sig_v = todo_v[:-2] if todo_v else "Ninguno identificado"
    ind570 = sum(1 for x in riesgos if x["norma"] == "NIA 570" and x["presenta"] == "Sí")
    n570 = f'COUNTIFS({_rng(R13, "I", len(riesgos))},"NIA 570",{_rng(R13, "F", len(riesgos))},"Sí")'
    ea = d["pe"]["estadosAnteriores"]
    ctl = lambda k: f"{H16}D{FILA0 + k}"  # noqa: E731
    est_eq = "Revisar" if any(e != "Conforme" for e in d["eqEst"]) or not d["reg"]["equipo"] else "Conforme"
    rev_ = ("No aplica" if d["sino"]["interesPublico"] == "No" else
            "Conforme" if any(x["rol"] == "Revisor de calidad" for x in d["reg"]["equipo"]) else "Revisar")
    cal = calendario(d["fechas"], d["corte"], d["tipo"])
    rg_af = f"'{enc_m.H28}'!$K${FILA0}:$K${FILA0 + max(n_eeff, 1) - 1}"
    glob_v = enc_m.RESP_GLOBAL if n_eeff and any(
        (f[len(enc_m.AFIRMACIONES) + 4]["v"] if isinstance(f[len(enc_m.AFIRMACIONES) + 4], dict) else "") != "No se presenta"
        for f in afirm[:n_eeff]) else "No se requieren respuestas globales adicionales"
    f_glob = (f'IF(COUNTIF({rg_af},"No se presenta")<{n_eeff},"{enc_m.RESP_GLOBAL}","No se requieren respuestas globales adicionales")'
              if n_eeff else '"No se requieren respuestas globales adicionales"')
    dres = d["dres"]
    return [
        ["Riesgos significativos (por nombre)", fx(f'IF({todo_f}="","Ninguno identificado",LEFT({todo_f},LEN({todo_f})-2))', sig_v),
         "NIA 300 párr. 9; NIA 315 párr. 32; NIA 330 párr. 21"],
        ["Empresa en funcionamiento (NIA 570)", fx(f'IF({n570}>0,{n570}&" indicios: evaluar la capacidad de continuar y los planes de la '
                                           f'dirección","Sin indicios en los indicadores evaluados")',
                                           f"{ind570} indicios: evaluar la capacidad de continuar y los planes de la dirección"
                                           if ind570 else "Sin indicios en los indicadores evaluados"), "NIA 570 párr. 10; NIA 300 párr. 8"],
        ["Estados del año anterior", fx(f'IF({_par("estadosAnteriores")}="","{enc_m.PENDIENTE}",{_par("estadosAnteriores")})',
                                        ea or enc_m.PENDIENTE), "NIA 510 párr. 6; NIA 710"],
        ["Calendario del encargo", fx(ctl(20), cal), "NIA 300 párr. 8 c)"],
        ["Equipo e independencia (hoja 25)", fx(ctl(17), est_eq), "Código IESBA; NIA 220 (Revisada)"],
        ["Revisor de calidad del encargo", fx(ctl(18), rev_), "NIGC 2"],
        ["Respuestas globales a los riesgos a nivel de estados financieros", fx(f_glob, glob_v), "NIA 330 párr. 5; NIA 240 párr. 29"],
        ["Diferencias acumuladas (NIA 450)", fx(f"'{enc_m.H30}'!J{FILA0 + len(d['difs']) + 5}", dres["conclusion"]),
         "NIA 450 párr. 5 y 11"],
    ]


DEF_SIGNIFICATIVA = "Deficiencia significativa: comunicar por escrito al gobierno (NIA 265 párr. 9)"
DEF_OTRA = "Otra deficiencia: comunicar a la dirección (NIA 265 párr. 10)"
DEF_PENDIENTE = "Pendiente de calificación"
SEGUIMIENTO = "Hallazgo del año anterior: verificar si se corrigió y, si persiste, volver a comunicarlo (NIA 265)"


def _conocimiento(d: dict, perfil: list, ent_h: list, matriz_h: list, mt: dict, e9: dict, ind: dict) -> dict:
    """Datos del papel de conocimiento del negocio (hoja 47): todo por fórmula a su hoja de origen."""
    v = lambda c: c.get("v") if isinstance(c, dict) else c  # noqa: E731
    ident = [(FILA0 + i, f[1], v(f[2])) for i, f in enumerate(perfil) if f[0] == "Identificación"]
    entend = [(f[0], v(f[2])) for f in ent_h[:len(cal_m.ASPECTOS)]]
    ea, ia = e9["act"], ind["act"]
    cifras = [("Activo total", f"{E9}D{F9['TOTAL ACTIVO']}", n2(ea["TOTAL ACTIVO"])),
              ("Pasivo total", f"{E9}D{F9['TOTAL PASIVO']}", n2(ea["TOTAL PASIVO"])),
              ("Patrimonio total", f"{E9}D{F9['PATRIMONIO TOTAL']}", n2(ea["PATRIMONIO TOTAL"])),
              ("Ventas netas", f"{E9}D{F9['Ventas netas']}", n2(ea["Ventas netas"])),
              ("Utilidad neta del período", f"{E9}D{F9['Utilidad neta']}", n2(ea["Utilidad neta"])),
              ("Razón corriente", f"{I10}E{F10['razonCorriente']}", "" if ia["razonCorriente"] is None else ia["razonCorriente"]),
              ("Endeudamiento del activo (%)", f"{I10}E{F10['endTotal']}", "" if ia["endTotal"] is None else ia["endTotal"]),
              ("Materialidad global", f"{M11}D{F11['Materialidad global']}", "" if mt["global"] is None else n2(mt["global"])),
              ("Materialidad de desempeño", DESEMP, "" if mt["desempeno"] is None else n2(mt["desempeno"]))]
    rk, rl, rj = (enf_m.rng46(c, len(matriz_h)) for c in "KLJ")
    sig = sum(1 for f in matriz_h if v(f[10]) == "Significativo" and v(f[11]) == "Sí")
    alto = sum(1 for f in matriz_h if v(f[10]) == "Alto" and v(f[11]) == "Sí")
    bajo = sum(1 for f in matriz_h if str(v(f[9])).startswith("Bajo") and v(f[11]) == "Sí")
    riesgos = [("Riesgos significativos presentes", f'COUNTIFS({rk},"Significativo",{rl},"Sí")', float(sig)),
               ("Riesgos altos presentes", f'COUNTIFS({rk},"Alto",{rl},"Sí")', float(alto)),
               ("Riesgos con confianza en los controles", f'COUNTIFS({rj},"Bajo*",{rl},"Sí")', float(bajo))]
    return {"ident": ident, "entend": entend, "cifras": cifras, "enf": d["enf"], "riesgos": riesgos}


ENFOQUE_SUSTANTIVO = "Sustantivo en todos los ciclos (política de la firma: sin confianza en los controles)"


def _enfoque_general_v(enf: list) -> str:
    n_c = sum(1 for e in enf if e["confia"])
    if not n_c:
        return ENFOQUE_SUSTANTIVO
    return f"Combinado: confianza en los controles de {n_c} ciclos y sustantivo en {len(enf) - n_c}"


def _f_enfoque_general(d: dict):
    """Estrategia: el enfoque general sale del enfoque por ciclo (hoja 45), salvo que la hoja 02 traiga otro. Sin ciclos
    con confianza en los controles, es sustantivo en todos (política de la firma)."""
    rh = enf_m.rng45("H", len(d["enf"]))
    f_ = (f'IF({_par("enfoque")}<>"",{_par("enfoque")},IF(COUNTIF({rh},"Confiar*")=0,"{ENFOQUE_SUSTANTIVO}",'
          f'"Combinado: confianza en los controles de "&COUNTIF({rh},"Confiar*")&'
          f'" ciclos y sustantivo en "&(ROWS({rh})-COUNTIF({rh},"Confiar*"))))')
    pv = str((d["parametros"] or {}).get("enfoque") or "").strip()
    return fx(f_, pv or _enfoque_general_v(d["enf"]))


def _f_probar(enf: list, x: dict):
    """Hoja 12, «¿Se probará el control?»: lo que dice la carta o, si el ciclo confía en los controles (hoja 45), «Sí»."""
    rf = enf_m.ref_final(enf, enf_m.ciclo_de(x["area"]))
    if not rf:
        return x["probar"]
    return fx(f'IF(OR("{x["probarDs"]}"="Sí",LEFT({rf},7)="Confiar"),"Sí","No")', x["probar"])


def _clase_def(x: dict) -> str:
    """M17 (NIA 265): significativa si el hallazgo es riesgo significativo o de nivel alto."""
    if x["sig"] == "Sí" or x["nivel"] == "Alto":
        return DEF_SIGNIFICATIVA
    return DEF_PENDIENTE if x["nivel"].startswith("Pendiente") else DEF_OTRA


def _imprevisible(rev: list, corte: str) -> dict | None:
    """M6: una cuenta del balance que no se revisa por su importe; cambia cada año (año del corte módulo el número de
    candidatas), para que la dirección no pueda anticiparla."""
    bal = [x for x in rev if x["x"]["sec"] in ("Activo", "Pasivo") and abs(x["x"]["act"]) > 0.005]
    cand = sorted((x["x"] for x in bal if x["revisa"] == "No"), key=lambda c: c["codigo"])
    if not cand:   # todas se revisan: una de las tres de menor importe (la de mayor importe siempre se prueba)
        cand = sorted(sorted((x["x"] for x in bal), key=lambda c: abs(c["act"]))[:3], key=lambda c: c["codigo"])
    return cand[int(corte[:4]) % len(cand)] if cand else None


def _f_sig(n12: int, n13: int) -> str:
    return (f'COUNTIF({_rng(R12, "M", n12)},"Sí")+COUNTIFS({_rng(R13, "F", n13)},"Sí",{_rng(R13, "H", n13)},"Significativo")')


def _estrategia_calidad(d: dict, carta: list, riesgos: list, programa: list, cambios: list, impr: dict | None, horas_h: list) -> list:
    """M1, M2, M4 y M6: respuestas globales, cambios frente a la versión anterior, horas y cierre del archivo."""
    fs = _f_sig(len(carta), len(riesgos))
    n_sig = sum(1 for x in carta if x["sig"] == "Sí") + sum(1 for x in riesgos if x["presenta"] == "Sí" and x["sev"] == "Significativo")

    def si_sig(a, b):
        return fx(f'IF({fs}>0,"{a}","{b}")', a if n_sig else b)
    pt = next((f[0] for f in programa if f[2] == "Imprevisibilidad (NIA 240)"), "")
    imp = (f"Prueba sin aviso sobre la cuenta {impr['codigo']} {impr['cuenta']} ({pt}); cambia cada año" if impr else
           "Variar la oportunidad de los procedimientos: todas las cuentas se revisan por su importe")
    n_cam = cal_m.n_cambios(cambios)
    f_cam = f'COUNTIF({cal_m.rng(cal_m.H42, "D", len(cambios))},"<>{cal_m.SIN_CAMBIO}")'
    h43 = ref(cal_m.H43)
    tot = FILA0 + len(cal_m.ROLES_HORAS)

    def hv(r, k):
        v = horas_h[r - FILA0][k]
        return v["v"] if isinstance(v, dict) else v
    return [
        ["Respuesta global · escepticismo profesional",
         si_sig("Reforzado: corroborar las explicaciones de la dirección con evidencia externa",
                "Normal: actitud crítica y corroboración de las explicaciones"), "NIA 200 párr. 15; NIA 330 párr. 5 y A1"],
        ["Respuesta global · asignación del personal",
         si_sig("Senior o gerente con experiencia en las áreas de riesgo significativo", "Según el programa (hoja 19)"),
         "NIA 330 párr. A1; NIA 240 párr. 29 a)"],
        ["Respuesta global · supervisión",
         si_sig("El socio revisa las cédulas de riesgos significativos y el gerente todas", "El gerente revisa todas las cédulas"),
         "NIA 220 (Revisada) párr. 30; NIA 330 párr. A1"],
        ["Respuesta global · imprevisibilidad", imp, "NIA 240 párr. 29 c); NIA 330 párr. A1"],
        ["Cambios frente a la versión anterior (hoja 42)",
         fx(f'IF({f_cam}>0,{f_cam}&" cambios: actualizar la estrategia y el programa","Sin cambios o primera versión")',
            f"{n_cam} cambios: actualizar la estrategia y el programa" if n_cam else "Sin cambios o primera versión"),
         "NIA 300 párr. 10 y 12; NIA 320 párr. 12"],
        ["Presupuesto de horas (hoja 43)", fx(f'FIXED({h43}D{tot},0)&" horas · "&{h43}G{tot}',
                                              f"{_num(hv(tot, 3), 0)} horas · {hv(tot, 6)}"), "NIA 300 párr. 8 e) y 9"],
        ["Supervisión planificada (hoja 43)",
         fx(f'{h43}E{tot + 1}&" procedimientos con revisión del socio y "&{h43}E{tot + 2}&" con revisión del gerente"',
            f"{int(hv(tot + 1, 4))} procedimientos con revisión del socio y {int(hv(tot + 2, 4))} con revisión del gerente"),
         "NIA 220 (Revisada) párr. 30; NIA 300 párr. 11"],
        ["Cierre del archivo (hoja 43)", fx(f'"Dentro de "&{_par("diasCierreArchivo")}&" días desde la fecha del informe"',
                                            f"Dentro de {int(d['pc']['diasCierreArchivo'])} días desde la fecha del informe"),
         "NIA 230 párr. 14 y A21"],
    ]


def _controles_calidad(d: dict, n17: int, n12: int) -> list:
    """Controles 23–33 de la hoja 16 (M1–M21)."""
    r0 = FILA0 + 23
    reg = enc_m.REG
    n_reg = len(enc_m.filas_registros(d["reg"])[0])
    ra, rf = f"'{reg}'!$A${FILA0}:$A${FILA0 + max(n_reg, 1) - 1}", f"'{reg}'!$F${FILA0}:$F${FILA0 + max(n_reg, 1) - 1}"
    abiertas = sum(1 for x in d["reg"].get("consultas") or [] if x["estado"] == enc_m.ABIERTA)
    rev, notas, an, est, partes = d["revisar"], d["notas"], d["an"], d["est"], d["partes"]
    n_sb = sum(1 for x in rev if (x["x"]["material"] == "Sí" or x["x"]["varMaterial"] == "Sí") and not (x["riesgo"] or x["rb"]))
    n_inv = sum(1 for y in an if y["res"] == cal_m.AN_INV)
    n_alta = sum(1 for y in est if y["inc"] == "Alta")
    n_fuera = sum(1 for y in partes if y["fuera"])
    n_ctl = len(cal_m.controles_necesarios(d["carta"]))
    n_sg = sum(1 for a in d["anomalias"] if a["tipo"] == "Signo")
    r41 = FILA0 + 1 + max(len(d["nofin"]), 1) + 1
    em_v = cal_m.filas_empresa_marcha(d["nofin"], len(riesgos_em(d["riesgos"], True)), {
        "R13": R13, "n13": len(d["riesgos"]), "par": _par, "corte": d["corte"], "n_reg": n_reg, "R_": enc_m.R_,
        "indag": [(0, x) for x in d["reg"].get("indagaciones") or []]})[0][-1][5]
    em_v = em_v["v"] if isinstance(em_v, dict) else em_v
    sug_ok = d["pct"]["pctDesempeno"] <= d["sug"]["pct"] + 1e-9

    def cnt(f_, n, det, nombre, revisar="Revisar"):
        k = len(filas)
        filas.append([nombre, None, fx(f_, float(n)), fx(f'IF(C{r0 + k}>0,"{revisar}","Conforme")', revisar if n else "Conforme"), det])
    filas = []
    cnt(f'COUNTIFS({_rng(A17, "A", n17)},"Signo",{_rng(A17, "F", n17)},"Sí")', n_sg,
        "Cuentas con signo contrario a su naturaleza que distorsionan la base de la materialidad y los índices (hojas 11 y 17).",
        CONTROLES[23])
    cnt(f'COUNTIFS({ra},"{enc_m.TIPO_CONSULTA}",{rf},"{enc_m.ABIERTA}")+COUNTIFS({ra},"{enc_m.TIPO_DIFERENCIA}",{rf},"{enc_m.ABIERTA}")',
        abiertas, "Consultas técnicas y diferencias de opinión registradas en la plataforma sin resolver: bloquean la aprobación.",
        CONTROLES[24])
    cnt(f'COUNTIF({cal_m.rng(cal_m.H36, "G", len(rev) + len(notas))},"Material sin riesgo*")', n_sb,
        "Cuentas materiales sin riesgo identificado: reciben procedimientos sustantivos y se confirma la valoración (hoja 36).",
        CONTROLES[25])
    cnt(f'COUNTIF({cal_m.rng(cal_m.H37, "J", len(an))},"Investigar*")', n_inv,
        "Cuentas de resultados que se apartan de su expectativa más que el umbral (hoja 37).", CONTROLES[26])
    cnt(f'COUNTIF({cal_m.rng(cal_m.H38, "H", len(est))},"Alta")', n_alta,
        "Estimaciones con incertidumbre alta: riesgo de la hoja 13 y respuesta en el programa (hoja 38).", CONTROLES[27])
    cnt(f'COUNTIF({cal_m.rng(cal_m.H40, "G", d["n40"])},"Sí*")', n_fuera,
        "Cuentas con partes relacionadas nuevas o con variación material: riesgo significativo (hoja 40).", CONTROLES[28])
    filas.append([CONTROLES[29], None, None,
                  fx(f"IF(LEFT('{cal_m.H41}'!F{r41},{len(cal_m.PENDIENTE)})=\"{cal_m.PENDIENTE}\",\"Revisar\",\"Conforme\")",
                     "Revisar" if str(em_v).startswith(cal_m.PENDIENTE) else "Conforme"),
                  "Con indicios de empresa en funcionamiento, la evaluación de la dirección debe estar documentada (hoja 41)."])
    filas.append([CONTROLES[30], None, None, fx(f"IF(LEFT({M11}G{F11[DESEMP_SUGERIDO]},8)=\"Conforme\",\"Conforme\",\"Revisar\")",
                                                  "Conforme" if sug_ok else "Revisar"),
                  "Porcentaje de desempeño de la hoja 02 frente al sugerido por los factores del encargo (hoja 11)."])
    tot = FILA0 + len(cal_m.ROLES_HORAS)
    filas.append([CONTROLES[31], None, None, fx(f"IF(COUNTIF('{cal_m.H43}'!$G${FILA0}:$G${tot},\"Revisar*\")>0,\"Revisar\",\"Conforme\")",
                                                  _estado_horas(d)),
                  "Horas por rol con integrantes registrados y porcentajes que suman 100 (hoja 43)."])
    cnt(f'SUMPRODUCT((LEFT({cal_m.rng(cal_m.H34, "L", n12)},3)="No:")*({_rng(R12, "N", n12)}="No"))' if n12 else "0", n_ctl,
        "Hallazgos de procesos automatizados cuyo control no se marcó para probar: los sustantivos solos no bastan (hoja 34).",
        CONTROLES[32])
    cnt(f'COUNTIF({cal_m.rng(cal_m.H42, "D", len(d["cambios"]))},"<>{cal_m.SIN_CAMBIO}")', cal_m.n_cambios(d["cambios"]),
        "Cambios de materialidad o de riesgos frente a la versión anterior: actualizar la estrategia y el programa (hoja 42).",
        CONTROLES[33])
    cnt(f'COUNTIF({enf_m.rng45("H", len(d["enf"]))},"")', 0,
        "Ciclos sin enfoque: sin decisión del socio rige «Sustantivo» por política de la firma, así que nada queda pendiente (hoja 45).",
        CONTROLES[34])
    cnt(f'COUNTIF({enf_m.rng45("F", len(d["enf"]))},"Revisar*")', sum(1 for e in d["enf"] if e["prop"] == enf_m.PROP_REVISAR),
        "Procesos automatizados con deficiencias de control: posible limitación al alcance (hoja 45).", CONTROLES[35])
    return filas


def _estado_horas(d: dict) -> str:
    """Espejo del control de horas: un rol con horas y sin integrante registrado con ese rol (hoja 43)."""
    eq = d["reg"]["equipo"]
    return "Revisar" if any(d["pc"][k] > 0 and not any(x["rol"] == rol for x in eq) for rol, k, _d in cal_m.ROLES_HORAS) \
        else "Conforme"


def _controles_encargo(d: dict) -> list:
    """Controles 15–22 de la hoja 16 (A1–A19): evaluaciones pendientes y alertas, independencia, revisor de calidad, año
    anterior, calendario, diferencias y comunicación con el gobierno."""
    evals, pe, sino, fch = d["evals"], d["pe"], d["sino"], d["fechas"]
    r0 = FILA0 + 15
    pend = sum(1 for x in evals if x["estado"] == "Pendiente")
    alert = sum(1 for x in evals if x["estado"] == "Alerta")
    n_h = {h: sum(1 for x in evals if x["hoja"] == h) for h in (enc_m.H24, enc_m.H26, enc_m.H27)}
    cnt = lambda v: "+".join(f"COUNTIF('{h}'!$I${FILA0}:$I${FILA0 + n - 1},\"{v}\")" for h, n in n_h.items())  # noqa: E731
    n_eq = len(d["reg"]["equipo"])
    malos = sum(1 for e in d["eqEst"] if e != "Conforme")
    f_malos = (f'COUNTIF({enc_m.rango_equipo("H", n_eq)},"Alerta*")+COUNTIF({enc_m.rango_equipo("H", n_eq)},"Pendiente")'
               if n_eq else "0")
    n_rev = sum(1 for x in d["reg"]["equipo"] if x["rol"] == "Revisor de calidad")
    f_rev = f'COUNTIF({enc_m.rango_equipo("B", n_eq)},"Revisor de calidad")' if n_eq else "0"
    ea, ini = pe["estadosAnteriores"], sino["encargoInicial"]
    est_ea = "Revisar" if not ea or ((ini == "No") != (ea == "Auditados por nosotros")) else "Conforme"
    pa, pi = _par("estadosAnteriores"), _par("encargoInicial")
    fp, ff, fi, fc = (_par(k) for k in ("fechaPreliminar", "fechaFinal", "fechaInforme", "corte"))
    cal = calendario(fch, d["corte"], d["tipo"])
    dres = d["dres"]
    r30 = FILA0 + len(d["difs"])
    concl = f"'{enc_m.H30}'!J{r30 + 5}"
    est_dif = "Conforme" if dres["conclusion"].startswith("Conforme") else "No evaluado" if dres["conclusion"].startswith("Pendiente") \
        else "Revisar"
    c1 = enc_m.ref_estado(enc_m.fila_de(evals), "COM-01")
    e_c1 = next(x["estado"] for x in evals if x["codigo"] == "COM-01")
    return [
        [CONTROLES[15], None, fx(cnt("Pendiente"), pend), fx(f'IF(C{r0}>0,"Revisar","Conforme")', "Revisar" if pend else "Conforme"),
         "Evaluaciones sin su registro en la plataforma o sin el documento de entrada: quedan [PENDIENTE] en las hojas 24, 26 y 27."],
        [CONTROLES[16], None, fx(cnt("Alerta"), alert), fx(f'IF(C{r0 + 1}>0,"Revisar","Conforme")', "Revisar" if alert else "Conforme"),
         "Resultados con alerta: los que son un riesgo pasan a la hoja 13 y al programa."],
        [CONTROLES[17], None, fx(f_malos, malos),
         fx(f'IF(OR(C{r0 + 2}>0,{n_eq}=0),"Revisar","Conforme")', "Revisar" if malos or not n_eq else "Conforme"),
         "Integrantes con amenazas sin salvaguarda o socio que debe rotar (hoja 25); «Revisar» si nadie confirmó en la plataforma."],
        [CONTROLES[18], None, fx(f_rev, n_rev),
         fx(f'IF({_par("interesPublico")}="No","No aplica",IF(C{r0 + 3}>0,"Conforme","Revisar"))',
            "No aplica" if sino["interesPublico"] == "No" else "Conforme" if n_rev else "Revisar"),
         "Obligatorio en entidades de interés público: un integrante con rol «Revisor de calidad» en la plataforma (hoja 25)."],
        [CONTROLES[19], None, None,
         fx(f'IF({pa}="","Revisar",IF(OR(AND({pi}="No",{pa}<>"Auditados por nosotros"),AND({pi}="Sí",{pa}="Auditados por nosotros")),'
            f'"Revisar","Conforme"))', est_ea),
         "Se deduce del encargo inicial y del informe anterior (hoja 02); coherente con «Encargo inicial»."],
        [CONTROLES[20], None, None,
         fx(f'IF(OR({fp}="",{ff}="",{fi}=""),"Revisar",IF(AND({fp}<={ff},{ff}<={fi},OR({_par("tipoRevision")}<>"Final",'
            f'AND({ff}>={fc},{fi}>={fc}))),"Conforme","Revisar"))', cal),
         "Visita preliminar ≤ visita final ≤ informe; en la revisión final, la visita final y el informe después del corte."],
        [CONTROLES[21], fx(f"'{enc_m.H30}'!G{r30 + 2}", n2(dres["total"])), None,
         fx(f'IF(LEFT({concl},8)="Conforme","Conforme",IF(LEFT({concl},9)="Pendiente","No evaluado","Revisar"))', est_dif),
         "Total acumulado de las diferencias no corregidas (hoja 30) frente a la materialidad de desempeño y la global."],
        [CONTROLES[22], None, None, fx(f'IF({c1}="Pendiente","Revisar","Conforme")', "Revisar" if e_c1 == "Pendiente" else "Conforme"),
         "Envío de la carta de planificación generada por la plataforma a los responsables del gobierno (hoja 24, COM-01)."],
    ]


# --- cédulas con fórmulas ------------------------------------------------------------------------------------

PROBLEMAS = "48_Problemas"
CEDULAS = [
    ("01_Resumen", "Resumen de la planificación"), ("02_Parametros", "Parámetros"),
    ("03_Mapa", "Mapa de cuentas (prefijo del código → clasificación)"),
    ("04_BC_Anterior", "Balance de comprobación al cierre anterior"), ("05_BC_Corte", "Balance de comprobación al corte"),
    ("06_ERI_Anterior", "Estado de resultados del año anterior al mismo corte"),
    ("07_Secciones", "Totales por sección, signo de presentación y cuadre"),
    ("08_Horizontal", "Análisis horizontal y vertical de todas las cuentas"),
    ("08S_Sumarias", "Sumarias por rubro: subcuentas, anterior, corte, ajustes y cuadre"),
    ("08A_ESF_Detalle", "Estado de situación financiera detallado: todas las cuentas por nivel"),
    ("08B_ERI_Detalle", "Estado de resultados detallado: todas las cuentas por nivel"),
    ("09_Estados", "Estados financieros resumidos"), ("10_Indices", "Índices financieros"),
    ("11_Materialidad", "Materialidad (NIA 320 y 450)"), ("12_Riesgos_CCI", "Matriz de riesgos de la carta de control interno"),
    ("13_Riesgos_Balance", "Posibles riesgos: NIA 240, empresa en funcionamiento, balances e informe anterior"),
    ("14_Perfil", "Perfil del encargo (NIA 315): identificación, entendimiento de la entidad y asuntos del informe anterior"),
    ("15_Notas", "Notas comparativas y saldos de apertura (NIA 510)"),
    ("15D_Notas_Detalle", "Notas: detalle comparativo por cuenta (anterior, corte y conciliación con la nota)"),
    ("15C_Composicion", "Notas: composición auditada del año anterior y su cuadre"),
    ("16_Control", "Control de calidad del análisis"),
    ("17_Anomalias", "Anomalías en las cuentas"), ("18_Cuentas_Revisar", "Cuentas principales a revisar"),
    ("19_Programa", "Programa de procedimientos (NIA 330)"), ("20_Narrativa", "Narrativa ejecutiva"),
    ("21_Estrategia", "Estrategia global de auditoría (NIA 300)"),
    ("22_Origenes", "Orígenes y aplicaciones de efectivo (lectura causa-efecto)"), ("23_Audit_trail", "Audit trail (NIA 230)"),
    *enc_m.CEDULAS,
    *cal_m.CEDULAS[:8],
    (cal_m.VERSION_ANT, "Versión anterior de la planificación (cifras y riesgos que entrega la plataforma)"),
    *cal_m.CEDULAS[8:],
    *enf_m.CEDULAS,
    ("00_Nota_metodologica", "Nota metodológica: citas por cotejar con el texto oficial vigente (marca †)"),
    ("48_Problemas", "Asuntos para la planificación"),
]
_ETQ = dict(CEDULAS)
_PAR = ["corte", "marco", "edicionMarco", "tipoRevision", "mesesTranscurridos", "mapaCuentas", "baseMaterialidad", "periodoBase", "pctIngresos",
        "pctActivos", "pctPatrimonio", "pctGastos", "pctUAI", "pctDesempeno", "pctTrivial", "justificacion", "umbralVarPct",
        "umbralVarExtrema", "umbralDiasRotacion", "umbralAlto", "umbralMedio", "encargoInicial", "interesPublico", "refutarIngresos",
        "motivoRefutacion", "enfoque", "fechaPreliminar", "fechaFinal", "fechaInforme", "socio", "gerente", "expertos",
        "umbralSignificativo", *enc_m.PARAMETROS, *cal_m.PARAMETROS]
PAR = {k: FILA0 + i for i, k in enumerate(_PAR)}
SEC_FILAS = list(SECCIONES) + ["Impuestos y participación", "Resultado del balance", UAI, "Gastos totales",
                               "Pasivo + patrimonio + resultado", "Diferencia de cuadre"]
F7 = {k: FILA0 + i for i, k in enumerate(SEC_FILAS)}
ESF = ["Activo corriente", "Efectivo y equivalentes", "Cuentas por cobrar", "Inventarios", "Activo no corriente", "TOTAL ACTIVO", "Pasivo corriente",
       "Cuentas por pagar", "Obligaciones financieras", "Pasivo no corriente", "TOTAL PASIVO", "PATRIMONIO (sin resultado del período)",
       "Resultado del período (según el balance)", "PATRIMONIO TOTAL", "PASIVO + PATRIMONIO TOTAL", "Diferencia de cuadre"]
ERI = ["Ventas netas", "(−) Costo de ventas", "Utilidad bruta", "(−) Gastos operativos", "Utilidad operativa", "(+) Otros ingresos",
       "(−) Gastos financieros", UAI, "(−) Participación e impuestos", "Utilidad neta"]
F9 = {k: FILA0 + i for i, k in enumerate(ESF + ERI)}
# Índices: clave, nombre, categoría, cómo se calcula (texto)
INDICES = [
    ("dias", "Base de días (R4)", "Base", "365 días también en cortes parciales (se declara en la lectura)"),
    ("razonCorriente", "Razón corriente (veces)", "Liquidez", "Activo corriente ÷ pasivo corriente"),
    ("pruebaAcida", "Prueba ácida (veces)", "Liquidez", "(Activo corriente − inventarios) ÷ pasivo corriente"),
    ("capitalTrabajo", "Capital de trabajo (USD)", "Liquidez", "Activo corriente − pasivo corriente"),
    ("diasCartera", "Días de cartera", "Actividad", "Cuentas por cobrar × 365 ÷ ventas netas"),
    ("diasInventario", "Días de inventario", "Actividad", "Inventarios × 365 ÷ costo de ventas"),
    ("diasProveedores", "Días de proveedores", "Actividad", "Cuentas por pagar × 365 ÷ costo de ventas (R6)"),
    ("ciclo", "Ciclo de conversión del efectivo (días)", "Actividad", "Días de cartera + días de inventario − días de proveedores"),
    ("rotacionActivo", "Rotación del activo (veces)", "Actividad", "Ventas netas ÷ activo total"),
    ("endTotal", "Endeudamiento del activo (%)", "Endeudamiento", "Pasivo total ÷ activo total × 100"),
    ("endLP", "Endeudamiento de largo plazo (%)", "Endeudamiento", "Pasivo no corriente ÷ activo total × 100"),
    ("endFinanciero", "Endeudamiento financiero (veces)", "Endeudamiento", "Obligaciones financieras ÷ patrimonio total"),
    ("endPatrimonial", "Endeudamiento patrimonial (veces)", "Endeudamiento", "Pasivo total ÷ patrimonio total"),
    ("multiplicador", "Multiplicador de apalancamiento (veces)", "Endeudamiento", "Activo total ÷ patrimonio total"),
    ("margenBruto", "Margen bruto (%)", "Rentabilidad", "Utilidad bruta ÷ ventas netas × 100"),
    ("margenOperativo", "Margen operativo (%)", "Rentabilidad", "Utilidad operativa ÷ ventas netas × 100 (R5)"),
    ("margenNeto", "Margen neto (%)", "Rentabilidad", "Utilidad neta ÷ ventas netas × 100"),
    ("roi", "ROI operativo (%)", "Rentabilidad", "Utilidad operativa ÷ activo total × 100"),
    ("dupontRoi", "ROI por DuPont (%)", "Rentabilidad", "Margen operativo × rotación del activo (sin redondear los factores)"),
    ("roe", "ROE (%)", "Rentabilidad", "Utilidad neta ÷ patrimonio total × 100"),
    ("dupont", "ROE por DuPont (%)", "Rentabilidad",
     "Margen neto × rotación del activo × multiplicador de apalancamiento (sin redondear los factores)"),
]
F10 = {k: FILA0 + i for i, (k, *_r) in enumerate(INDICES)}
# Semáforo: (verde si, amarillo si, etiquetas verde/amarillo/rojo); None = referencia.
ZONAS = {
    "razonCorriente": (">=1.5", ">=1", ("Cómodo", "Ajustado", "Alerta")),
    "pruebaAcida": (">=1", ">=0.8", ("Sólido", "Ajustado", "Débil")),
    "capitalTrabajo": (">0", "=0", ("Positivo", "En cero", "Negativo")),
    "diasCartera": ("<=60", "<=90", ("Ágil", "Moderado", "Lento")),
    "diasInventario": ("<=90", "<=120", ("Ágil", "Moderado", "Lento")),
    "ciclo": ("<=30", "<=60", ("Corto", "Moderado", "Largo")),
    "rotacionActivo": (">=1", ">=0.5", ("Alta", "Media", "Baja")),
    "endTotal": ("<50", "<=70", ("Conservador", "Moderado", "Alto")),
    "endLP": ("<30", "<=50", ("Bajo", "Moderado", "Alto")),
    "endFinanciero": ("<1", "<=2", ("Bajo", "Moderado", "Elevado")),
    "endPatrimonial": ("<1", "<=2", ("Conservador", "Moderado", "Elevado")),
    "multiplicador": ("<2", "<=4", ("Bajo", "Moderado", "Alto")),
}
_RENT = ("margenBruto", "margenOperativo", "margenNeto", "roi", "dupontRoi", "roe", "dupont")
# Índices que dividen para el patrimonio: con patrimonio cero o negativo no son interpretables (un endeudamiento
# negativo no es «conservador»); se marcan en rojo como no significativos y la lectura remite a NIA 570.
_PAT = ("endFinanciero", "endPatrimonial", "multiplicador", "roe", "dupont")
NO_SIGNIFICATIVO = "Rojo · No significativo (patrimonio ≤ 0)"
LECTURA_PATRIMONIO = ("Con patrimonio cero o negativo el indicador no es interpretable: la entidad está en déficit patrimonial "
                      "(indicio de empresa en funcionamiento, NIA 570).")
# Lectura de cada índice con su cifra (artefacto: «Por cada US$1…»): texto antes y después de la cifra. En los días la cifra
# es la ajustada al período (hoja 10, columna I). En el Excel la cifra va con FIXED(), que usa los separadores del equipo.
LECTURA = {
    "razonCorriente": ("Por cada US$ 1 de pasivo corriente hay US$ ", " de activo corriente"),
    "pruebaAcida": ("Sin inventarios, por cada US$ 1 de pasivo corriente hay US$ ", " de activos líquidos"),
    "capitalTrabajo": ("Capital de trabajo de US$ ", ""),
    "diasCartera": ("La empresa tarda ", " días en cobrar a sus clientes (ajustado al período, sobre 365 días)."),
    "diasInventario": ("El inventario permanece ", " días en bodega antes de venderse (ajustado al período)."),
    "diasProveedores": ("La empresa se financia ", " días con sus proveedores (sobre el costo de ventas, ajustado al período)."),
    "ciclo": ("El efectivo queda inmovilizado ", " días en el ciclo operativo (cartera + inventario − proveedores, ajustado al período)."),
    "rotacionActivo": ("Cada US$ 1 de activos genera US$ ", " de ventas en el período."),
    "endTotal": ("El ", " % de los activos se financia con deuda de terceros."),
    "endLP": ("El ", " % de los activos se financia con deuda de largo plazo."),
    "endFinanciero": ("Hay US$ ", " de deuda financiera (bancos y obligaciones) por cada US$ 1 de patrimonio."),
    "endPatrimonial": ("Hay US$ ", " de deuda con terceros por cada US$ 1 de patrimonio."),
    "multiplicador": ("Los activos equivalen a ", " veces el patrimonio (multiplicador de apalancamiento)."),
    "margenBruto": ("De cada US$ 100 vendidos quedan US$ ", " después del costo de ventas."),
    "margenOperativo": ("De cada US$ 100 vendidos quedan US$ ", " como utilidad operativa."),
    "margenNeto": ("De cada US$ 100 vendidos, US$ ", " se convierten en utilidad final."),
    "roi": ("La utilidad operativa es de US$ ", " por cada US$ 100 de activos."),
    "dupontRoi": ("Margen operativo × rotación del activo = ", " %: debe reproducir el ROI."),
    "roe": ("La utilidad neta es de US$ ", " por cada US$ 100 de patrimonio."),
    "dupont": ("Margen neto × rotación del activo × multiplicador = ", " %: debe reproducir el ROE."),
}
LECTURA_COND = {
    "razonCorriente": ("<1", ": no alcanza a cubrir el corto plazo.", ": cubre el corto plazo."),
    "pruebaAcida": ("<1", ": no cubren el pasivo corriente.", ": cubren el pasivo corriente."),
    "capitalTrabajo": ("<0", ": déficit, el pasivo corriente supera al activo corriente (presión de liquidez).",
                       ": el activo corriente supera al pasivo corriente, hay margen para operar."),
}
# Sentido favorable de cada índice (para la columna «Tendencia» de la hoja 10).
MEJOR = {**{k: "alto" for k in ("razonCorriente", "pruebaAcida", "capitalTrabajo", "rotacionActivo", "margenBruto",
                                 "margenOperativo", "margenNeto", "roi", "dupontRoi", "roe", "dupont")},
         **{k: "bajo" for k in ("diasCartera", "diasInventario", "ciclo", "endTotal", "endLP", "endFinanciero",
                                "endPatrimonial", "multiplicador")}}
SIN_DATO = "No hay datos suficientes para calcular este indicador."
LECTURA_DIAS = ("Año completo: los días se calculan sobre 365.",
                "Corte parcial: con ventas y costos de pocos meses sobre 365 días, los días salen mayores que los reales (R4).")
_MAT = ["Período de la base"] + list(BASES) + ["Materialidad global", "Materialidad de desempeño",
                                               "Umbral de errores claramente insignificantes", "Justificación de la base",
                                               "Materialidad específica", DESEMP_SUGERIDO, AVISO_SIGNO]
F11 = {k: FILA0 + i for i, k in enumerate(_MAT)}
_REF_BASE7 = {"Ingresos": "Ingresos", "Activos totales": "Activo", "Patrimonio": "Patrimonio", "Gastos totales": "Gastos totales", UAI: UAI}
_PCT_BASE = {"Ingresos": "pctIngresos", "Activos totales": "pctActivos", "Patrimonio": "pctPatrimonio", "Gastos totales": "pctGastos",
             UAI: "pctUAI"}
CONTROLES = ["Cuadre del balance al corte", "Cuadre del balance del cierre anterior", "Cuentas fuera del mapa (sección «Otros»)",
             "Materialidad definida", "Anomalías de severidad alta", "Notas del año anterior cargadas",
             "Notas que no concilian con el balance anterior (NIA 510)", "Indicios de empresa en funcionamiento (NIA 570)",
             "Riesgos de la carta de control interno pendientes de calificación", "Carta de control interno cargada",
             "Informe de auditoría del año anterior cargado", "Cuentas superiores que no suman sus subcuentas (R1)",
             "Composición de las notas que no suma el saldo auditado", "Rubros del balance sin nota del año anterior",
             "Datos de gobierno del encargo completos (NIA 300)",
             "Evaluaciones de la planificación completas (hojas 24, 26 y 27)", "Alertas de la planificación (hojas 24, 26 y 27)",
             "Independencia del equipo confirmada en la plataforma (Código IESBA; NIA 220)",
             "Revisor de calidad del encargo en entidades de interés público (NIGC 2)",
             "Estados del año anterior: auditor definido y coherente con el encargo inicial (NIA 510)",
             "Calendario del encargo coherente (NIA 300)", "Diferencias acumuladas frente a la materialidad (NIA 450)",
             "Comunicación de la planificación al gobierno (NIA 260)",
             "Saldos con signo contrario en la base de la materialidad y los índices (NIA 320)",
             "Consultas y diferencias de opinión abiertas (NIA 220)",
             "Cuentas materiales sin riesgo identificado · stand-back (NIA 315 y 330)",
             "Analíticos sustantivos por investigar (NIA 520)", "Estimaciones con incertidumbre alta (NIA 540)",
             "Partes relacionadas fuera del curso normal (NIA 550)", "Evaluación de la dirección sobre empresa en funcionamiento (NIA 570)",
             "Porcentaje de desempeño frente al sugerido por factores (NIA 320)", "Presupuesto de horas por rol (NIA 300 y 220)",
             "Controles que deben probarse en procesos automatizados (NIA 315 y 330)",
             "Cambios frente a la versión anterior de la planificación (NIA 300)",
             "Enfoque por ciclo definido: sustantivo por política o decisión del socio (NIA 300 y 330)",
             "Ciclos donde los sustantivos no bastan y hay deficiencias de control (NIA 330)"]
# D6: datos de la hoja 02 que la estrategia y el programa necesitan; si faltan, quedan [PENDIENTE] y el control avisa.
GOBIERNO = ("socio", "gerente", "fechaPreliminar", "fechaFinal", "fechaInforme")
OPORTUNIDAD_ALTO = "Visita preliminar (controles) y visita final (detalle al corte)"
OPORTUNIDAD_MEDIO = "Visita final con pruebas de detalle"
OPORTUNIDAD_BAJO = "Visita final (analíticos sustantivos)"
RESPUESTA_DEFECTO = "Por definir por el equipo según el nivel del riesgo (NIA 330)."
RECOMENDACIONES = [
    ("Liquidez", "rc", "<1", "Reforzar la liquidez: plan de cobranza y calce de vencimientos de corto plazo.",
     "No aplica: la razón corriente es de 1 o más."),
    ("Endeudamiento", "end", ">70", "Evaluar el reperfilamiento de la deuda y el fortalecimiento patrimonial.",
     "No aplica: endeudamiento del activo del 70 % o menos."),
    ("Cartera", "cartera", ">90", "Intensificar la gestión de cartera y evaluar el deterioro (NIIF 9).",
     "No aplica: cartera de 90 días o menos."),
    ("Inventarios", "inventario", ">120", "Revisar el inventario de lento movimiento y su valor neto realizable (NIC 2).",
     "No aplica: inventario de 120 días o menos."),
]

C15, D15 = ref("15C_Composicion"), ref("15D_Notas_Detalle")
P_, MP, B4, B5, B6, S7, H8, E9, I10, M11, R12, R13, P14, N15, A17, C18 = (ref(n) for n in (
    "02_Parametros", "03_Mapa", "04_BC_Anterior", "05_BC_Corte", "06_ERI_Anterior", "07_Secciones", "08_Horizontal", "09_Estados",
    "10_Indices", "11_Materialidad", "12_Riesgos_CCI", "13_Riesgos_Balance", "14_Perfil", "15_Notas", "17_Anomalias",
    "18_Cuentas_Revisar"))
DESEMP = f"{M11}$D${F11['Materialidad de desempeño']}"
GLOBAL = f"{M11}$D${F11['Materialidad global']}"
TRIVIAL = f"{M11}$D${F11['Umbral de errores claramente insignificantes']}"
P19, P29, H16 = ref("19_Programa"), ref(enc_m.H29), ref("16_Control")


def _ge(expr: str, factor: str = "") -> str:
    """|expr| ≥ materialidad de desempeño; falso si no hay materialidad (base ≤ 0)."""
    return f'AND({DESEMP}<>"",ABS({expr})>={DESEMP}{factor})'


def _par(k):
    return f"{P_}$B${PAR[k]}"


PRELIM = f'{_par("tipoRevision")}="Preliminar"'
FAC = f'IF({PRELIM},{_par("mesesTranscurridos")}/12,1)'
RESULTADO_NETO_TRASPASOS = "Resultado del período neto de traspasos y distribuciones"
TRASPASO = "Traspaso de resultados"


def _es_resultado_patrimonio(x: dict) -> bool:
    """D11: cuenta de patrimonio que acumula resultados (resultados acumulados, utilidades retenidas, pérdidas acumuladas)."""
    return x["sec"] == "Patrimonio" and bool(re.search(r"resultad|utilidad|perdida|ganancia|retenid", norm(x["cuenta"])))
ANUAL = f'IF({PRELIM},12/{_par("mesesTranscurridos")},1)'   # D9: anualización de las bases de resultados al corte actual
ANUALIZADA = ", anualizada × 12 ÷ "
ES_FLUJO = "OR(" + ",".join(f'{_par("baseMaterialidad")}="{b}"' for b in BASES_FLUJO) + ")"


def _rng(pref: str, col: str, n: int) -> str:
    return f"{pref}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _desc(rango: str, celda: str, punto: bool) -> str:
    """Filas del rango que son la cuenta de ``celda`` o sus subcuentas (misma regla que ``_debajo``)."""
    if punto:
        return f'(LEFT({rango}&".",LEN({celda})+1)={celda}&".")'
    return f"(LEFT({rango},LEN({celda}))={celda})"


def _desc_lit(rango: str, pre: str) -> str:
    if "." in pre:
        return f'(LEFT({rango}&".",{len(pre) + 1})="{pre}.")'
    return f'(LEFT({rango},{len(pre)})="{pre}")'


def _anc(rango: str, celda: str, punto: bool) -> str:
    """Filas del rango que son cuentas superiores de ``celda`` (misma regla que ``_ancestro``)."""
    if punto:
        return f'(LEFT({celda}&".",LEN({rango})+1)={rango}&".")*(LEN({rango})<LEN({celda}))'
    return f"(LEFT({celda},LEN({rango}))={rango})*(LEN({rango})<LEN({celda}))"


def _s(celda: str, *claves) -> str:
    return "OR(" + ",".join(f'ISNUMBER(SEARCH("{k}",{celda}))' for k in claves) + ")"


def _f_rubro_eri(a: str, b: str, g: str) -> str:
    nd = f'LEFT(SUBSTITUTE({a},".",""),2)'
    return (f'IF({g}="Ingresos",IF(OR({nd}="41",{nd}="42"),"Ventas","Otros ingresos"),IF({g}="Costos","Costo de ventas",'
            f'IF({g}="Gastos",IF({_s(b, "financ", "interes", "interés")},"Gastos financieros",'
            f'IF({_s(b, "impuesto a la renta", "participaci")},"Impuestos y participación","Gastos operativos")),"")))')


def _f_rubro_ind(b: str, f: str) -> str:
    return (f'IF({f}="Activo",IF(AND({_s(b, "efectivo", "caja", "banco")},NOT({_s(b, "restringid")})),"Efectivo",'
            f'IF(AND({_s(b, "cobrar", "cliente")},NOT({_s(b, *NO_COMERCIAL_CXC)})),"Cuentas por cobrar",'
            f'IF({_s(b, "inventario", "mercader", "existencia")},"Inventarios",""))),'
            f'IF({f}="Pasivo",IF({_s(b, "bancari", "financ", "préstamo", "prestamo", "sobregiro", "obligacion", "obligación")},"Obligaciones financieras",'
            f'IF(AND({_s(b, "pagar", "proveedor")},NOT({_s(b, *NO_COMERCIAL_CXP)})),"Cuentas por pagar","")),""))')


def _f_clasif(a: str, nm: int) -> str:
    ma, mb = _rng(MP, "A", nm), _rng(MP, "B", nm)
    return f'IFERROR(LOOKUP(2,1/(LEFT(SUBSTITUTE({a},".",""),LEN({ma}))={ma}),{mb}),"Otros")'


def _f_seccion(f: str) -> str:
    return f'IF(LEFT({f},6)="Activo","Activo",IF(LEFT({f},6)="Pasivo","Pasivo",{f}))'


def _hoja_bc(nombre: str, etiqueta: str, filas: list, col_saldo: str, nm: int, guia: str) -> dict:
    n = len(filas)
    A = f"$A${FILA0}:$A${FILA0 + max(n, 1) - 1}"
    C, D, G = (f"${c}${FILA0}:${c}${FILA0 + max(n, 1) - 1}" for c in "CDG")
    sig_a, sig_e = _rng(S7, "A", len(SECCIONES)), _rng(S7, "E", len(SECCIONES))
    rows = []
    for i, x in enumerate(filas):
        r = FILA0 + i
        dot = "." in x["codigo"]
        rows.append([
            x["codigo"], x["cuenta"], n2(x["saldo"]),
            fx(f"SUMPRODUCT({_anc(A, f'A{r}', dot)})+1", x["nivel"]),
            fx(f'IF(SUMPRODUCT({_desc(A, f"A{r}", dot)}*(LEN({A})>LEN(A{r})))>0,"No","Sí")', x["detalle"]),
            fx(_f_clasif(f"A{r}", nm), x["clas"]), fx(_f_seccion(f"F{r}"), x["sec"]),
            fx(_f_rubro_eri(f"A{r}", f"B{r}", f"G{r}"), x["rubro"]),
            fx(f"C{r}*INDEX({sig_e},MATCH(G{r},{sig_a},0))", n2(x["pres"])),
            fx(f'IF(SUMPRODUCT({_anc(A, f"A{r}", dot)}*({G}=G{r}))>0,"No","Sí")', x["supsec"]),
            fx(f'IF(E{r}="Sí",0,C{r}-SUMPRODUCT({_desc(A, f"A{r}", dot)}*({D}=D{r}+1)*{C}))', n2(x["difsub"])),
        ])
    return hoja(nombre, etiqueta, [["Código de cuenta", "t"], ["Nombre de la cuenta", "t"], [col_saldo, "n"], ["Nivel", "i"],
                                   ["Detalle", "t"], ["Clasificación", "t"], ["Sección", "t"], ["Rubro del ERI", "t"],
                                   ["Saldo presentado", "n"], ["Superior de la sección", "t"], ["Diferencia con subcuentas", "n"]],
                rows, explica=EXPLICA["BC"], guia=guia)


def _txt(v):
    return "" if v is None else v


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p, fu, cu, e9, ind = d["parametros"], d["fuentes"], d["cuentas"], d["est9"], d["ind"]
    nm, n4, n5, n6, n8 = len(d["mapa"]), len(fu["ant"]), len(fu["act"]), len(fu["eri"]), len(cu)
    carta, informe, notas, riesgos, anom, rev = d["carta"], d["informe"], d["notas"], d["riesgos"], d["anomalias"], d["revisar"]
    ruc = d.get("ruc") or {}
    mt = d["materialidad"]
    pv = lambda k: None if p.get(k) in (None, "") else p.get(k)  # noqa: E731

    # 02 · parámetros (valores del encargo y juicio del auditor)
    fch = d["fechas"]
    val = {"corte": d["corte"], "marco": d["marco"], "edicionMarco": d["edicion"], "tipoRevision": d["tipo"], "mesesTranscurridos": d["meses"],
           "mapaCuentas": "; ".join(f"{a}={b}" for a, b in d["mapa"]), "baseMaterialidad": d["base"], "periodoBase": d["periodoParam"],
           **{k: d["pct"][k] for k in d["pct"]}, "justificacion": pv("justificacion"), "umbralVarPct": d["umbrales"]["var"],
           "umbralVarExtrema": d["umbrales"]["ext"], "umbralDiasRotacion": d["umbrales"]["dias"],
           "umbralAlto": d["umbrales"]["alto"], "umbralMedio": d["umbrales"]["medio"], "umbralSignificativo": d["umbrales"]["sig"],
           **d["sino"], "motivoRefutacion": pv("motivoRefutacion"), "enfoque": pv("enfoque"), **fch,
           "socio": pv("socio"), "gerente": pv("gerente"), "expertos": pv("expertos"),
           **{k: (None if d["pe"][k] in ("", None) else d["pe"][k]) for k in enc_m.PARAMETROS}, **d["pc"]}
    sustento = {"corte": "Ficha del encargo", "marco": "Ficha del encargo", "edicionMarco": "Ficha del encargo", "tipoRevision": "Cronograma del encargo",
                "mesesTranscurridos": "Solo prorratea el ERI del año anterior si no se entrega al mismo corte",
                "mapaCuentas": "Plan de cuentas del cliente; la hoja 03 lo muestra como tabla (edítela allí)",
                "baseMaterialidad": "NIA 320 párr. A3–A5: juicio profesional", "periodoBase": "NIA 320 párr. A5–A6",
                "pctDesempeno": "NIA 320 párr. 11 y A12: política de la firma", "pctTrivial": "NIA 450 párr. 5 y A2: política de la firma",
                "justificacion": "NIA 320 párr. 14 (documentación)", "umbralAlto": "Política de la firma (mapa de calor 5 × 5)",
                "umbralMedio": "Política de la firma (mapa de calor 5 × 5)", "encargoInicial": "NIA 300 párr. 13 y NIA 510",
                "umbralSignificativo": "NIA 315 párr. 12 l) y 32; NIA 330 párr. 21 — política de la firma (VERIFICAR)",
                "interesPublico": "NIA 701", "refutarIngresos": "NIA 240 párr. 26 y 47",
                "motivoRefutacion": "NIA 240 párr. 47", "enfoque": "NIA 300 párr. 8", "socio": "NIA 220", "gerente": "NIA 220",
                "expertos": "NIA 300 párr. 8 e) y NIA 620", **enc_m.SUSTENTO, **cal_m.SUSTENTO}
    parametros = [[ETIQUETAS_PARAM.get(k, {"corte": "Corte del ejercicio", "marco": "Marco de información financiera",
                                              "edicionMarco": "Edición del marco (PYMES: 2015 o 2025)"}.get(k, k)),
                   val.get(k), sustento.get(k, "Política de la firma" if k.startswith(("pct", "umbral")) else "Cronograma del encargo")]
                  for k in _PAR]

    # 03 · mapa
    mapa = [[a, b, fx(_f_seccion(f"B{FILA0 + i}"), _seccion_de(b))] for i, (a, b) in enumerate(d["mapa"])]

    # 04 / 05 / 06 · balances de comprobación
    bc_ant = _hoja_bc("04_BC_Anterior", _ETQ["04_BC_Anterior"], fu["ant"], "Saldo al cierre anterior", nm,
                      "Balance de comprobación al cierre del año anterior (auditado), exportado del sistema contable.")
    bc_act = _hoja_bc("05_BC_Corte", _ETQ["05_BC_Corte"], fu["act"], "Saldo al corte", nm,
                      "Balance de comprobación a la fecha de corte que se audita, exportado del sistema contable.")
    bc_eri = _hoja_bc("06_ERI_Anterior", _ETQ["06_ERI_Anterior"], fu["eri"], "Saldo al mismo corte del año anterior", nm,
                      "Estado de resultados del año anterior al mismo corte (solo en la revisión preliminar).")

    # 07 · secciones
    rng4 = {c: _rng(B4, c, n4) for c in "CEGHIJK"}
    rng5 = {c: _rng(B5, c, n5) for c in "CEGHIJK"}
    rng6 = {c: _rng(B6, c, n6) for c in "CEGHIJK"}
    s7 = d["sec7"]
    secciones = []
    for k in SEC_FILAS:
        r = F7[k]
        if k in SECCIONES:
            b = [fx(f'SUMIFS({rg["C"]},{rg["G"]},A{r},{rg["J"]},"Sí")', n2(d["bruto"][q][k])) for rg, q in ((rng4, "ant"), (rng5, "act"),
                                                                                                           (rng6, "eri"))]
            sg = fx(f"IF({_f_firmado()},-1,1)", d["signo"][k]) if k in ACREEDORAS else fx("1", 1)
            pres = [fx(f"{c1}{r}*E{r}", n2(s7[q][k])) for c1, q in (("B", "ant"), ("C", "act"), ("D", "eri"))]
            secciones.append([k, *b, sg, *pres])
            continue
        if k == "Impuestos y participación":
            pres = [fx(f'SUMIFS({rg["I"]},{rg["H"]},"Impuestos y participación",{rg["E"]},"Sí")', n2(s7[q][k]))
                    for rg, q in ((rng4, "ant"), (rng5, "act"), (rng6, "eri"))]
        else:
            expr = {"Resultado del balance": "{c}%d-{c}%d-{c}%d" % (F7["Ingresos"], F7["Costos"], F7["Gastos"]),
                    UAI: "{c}%d+{c}%d" % (F7["Resultado del balance"], F7["Impuestos y participación"]),
                    "Gastos totales": "{c}%d+{c}%d" % (F7["Costos"], F7["Gastos"]),
                    "Pasivo + patrimonio + resultado": "{c}%d+{c}%d+{c}%d" % (F7["Pasivo"], F7["Patrimonio"], F7["Resultado del balance"]),
                    "Diferencia de cuadre": "{c}%d-{c}%d" % (F7["Activo"], F7["Pasivo + patrimonio + resultado"])}[k]
            pres = [fx(expr.replace("{c}", c1), n2(s7[q][k])) for c1, q in (("F", "ant"), ("G", "act"), ("H", "eri"))]
        secciones.append([k, None, None, None, None, *pres])

    # 08 · análisis horizontal
    A8 = f"$A${FILA0}:$A${FILA0 + max(n8, 1) - 1}"
    M8, F8, E8, L8 = (f"${c}${FILA0}:${c}${FILA0 + max(n8, 1) - 1}" for c in "MFEL")
    ta, ven = f"{E9}$D${F9['TOTAL ACTIVO']}", f"{E9}$D${F9['Ventas netas']}"
    hay_eri = f"COUNTA({_rng(B6, 'A', n6)})>0"
    horizontal = []
    for i, x in enumerate(cu):
        r, dot = FILA0 + i, "." in x["codigo"]

        def ps(pref, n, r=r, dot=dot):
            a_, i_ = _rng(pref, "A", n), _rng(pref, "I", n)
            return (f'IF(SUMPRODUCT(({a_}=A{r})*1)>0,SUMPRODUCT(({a_}=A{r})*{i_}),'
                    f'SUMPRODUCT({_desc(a_, f"A{r}", dot)}*({_rng(pref, "E", n)}="Sí")*{i_}))')
        horizontal.append([
            x["codigo"], x["cuenta"],
            fx(f"SUMPRODUCT({_anc(A8, f'A{r}', dot)})+1", x["nivel"]),
            fx(f'IF(SUMPRODUCT({_desc(A8, f"A{r}", dot)}*(LEN({A8})>LEN(A{r})))>0,"No","Sí")', x["detalle"]),
            fx(_f_clasif(f"A{r}", nm), x["clas"]), fx(_f_seccion(f"E{r}"), x["sec"]),
            fx(f'IF(AND({PRELIM},OR(F{r}="Ingresos",F{r}="Costos",F{r}="Gastos")),IF({hay_eri},{ps(B6, n6)},'
               f'{ps(B4, n4)}*{_par("mesesTranscurridos")}/12),{ps(B4, n4)})', n2(x["ant"])),
            fx(ps(B5, n5), n2(x["act"])),
            fx(f"H{r}-G{r}", n2(x["var"])), fx(f'IF(G{r}=0,"",I{r}/ABS(G{r}))', x["varPct"]),
            fx(f'IF(OR(F{r}="Activo",F{r}="Pasivo",F{r}="Patrimonio"),IF({ta}=0,"",H{r}/{ta}),'
               f'IF(OR(F{r}="Ingresos",F{r}="Costos",F{r}="Gastos"),IF({ven}=0,"",H{r}/{ven}),""))', x["vert"]),
            fx(_f_rubro_eri(f"A{r}", f"B{r}", f"F{r}"), x["rubro"]), fx(_f_rubro_ind(f"B{r}", f"F{r}"), x["rind"]),
            fx(f'IF(M{r}="","",IF(SUMPRODUCT({_anc(A8, f"A{r}", dot)}*({M8}=M{r}))>0,"No","Sí"))', x["pind"]),
            fx(f'IF({_ge(f"H{r}")},"Sí","No")', x["material"]), fx(f'IF({_ge(f"I{r}")},"Sí","No")', x["varMaterial"]),
            fx(f'IF(SUMPRODUCT({_anc(A8, f"A{r}", dot)}*({F8}=F{r}))>0,"No","Sí")', x["supsec"]),
            fx(f'IF(SUMPRODUCT({_anc(A8, f"A{r}", dot)}*({E8}=E{r}))>0,"No","Sí")', x["supclas"]),
            fx(f'IF(L{r}="","",IF(SUMPRODUCT({_anc(A8, f"A{r}", dot)}*({L8}=L{r}))>0,"No","Sí"))', x["suprubro"]),
        ])

    # 08S · sumarias por rubro
    sumarias, estilos_s = _sumarias(cu, notas, d["umbrales"]["var"])
    # 08A / 08B · estados detallados con todas las cuentas por nivel
    esf_det, est_a = _estado_detalle(cu, ("Activo", "Pasivo", "Patrimonio"), d["sec7"], d["tipo"] == "Preliminar", d["hayEri"],
                                     d["meses"], hay_eri)
    eri_det, est_b = _estado_detalle(cu, ("Ingresos", "Costos", "Gastos"), d["sec7"], d["tipo"] == "Preliminar", d["hayEri"],
                                     d["meses"], hay_eri)
    f_a, f_c = _fechas_estados(d)

    # 09 · estados resumidos
    R8 = {c: _rng(H8, c, n8) for c in "DEFGHLMNQRS"}

    def sif(col, **crit):
        cols = {"sec": "F", "clas": "E", "rubro": "L", "rind": "M", "pind": "N", "det": "D", "ss": "Q", "sc": "R", "sr": "S"}
        return "SUMIFS(" + R8[col] + "," + ",".join(f'{R8[cols[k]]},"{v}"' for k, v in crit.items()) + ")"
    estados = []
    for k in ESF + ERI:
        r = F9[k]
        fila = [k, "Situación financiera" if k in ESF else "Resultados"]
        for c9, c8, q in (("C", "G", "ant"), ("D", "H", "act")):
            f_ = {
                "TOTAL ACTIVO": sif(c8, sec="Activo", ss="Sí"),
                "Activo no corriente": sif(c8, clas="Activo no corriente", sc="Sí"),
                "Activo corriente": f"{c9}{F9['TOTAL ACTIVO']}-{c9}{F9['Activo no corriente']}",
                "Efectivo y equivalentes": sif(c8, rind="Efectivo", pind="Sí"),
                "Cuentas por cobrar": sif(c8, rind="Cuentas por cobrar", pind="Sí"),
                "Inventarios": sif(c8, rind="Inventarios", pind="Sí"),
                "TOTAL PASIVO": sif(c8, sec="Pasivo", ss="Sí"),
                "Pasivo no corriente": sif(c8, clas="Pasivo no corriente", sc="Sí"),
                "Pasivo corriente": f"{c9}{F9['TOTAL PASIVO']}-{c9}{F9['Pasivo no corriente']}",
                "Cuentas por pagar": sif(c8, rind="Cuentas por pagar", pind="Sí"),
                "Obligaciones financieras": sif(c8, rind="Obligaciones financieras", pind="Sí"),
                "PATRIMONIO (sin resultado del período)": sif(c8, sec="Patrimonio", ss="Sí"),
                "Resultado del período (según el balance)": f"{S7}{'F' if q == 'ant' else 'G'}{F7['Resultado del balance']}",
                "PATRIMONIO TOTAL": f"{c9}{F9['PATRIMONIO (sin resultado del período)']}+{c9}{F9['Resultado del período (según el balance)']}",
                "PASIVO + PATRIMONIO TOTAL": f"{c9}{F9['TOTAL PASIVO']}+{c9}{F9['PATRIMONIO TOTAL']}",
                "Diferencia de cuadre": f"{c9}{F9['TOTAL ACTIVO']}-{c9}{F9['PASIVO + PATRIMONIO TOTAL']}",
                "Ventas netas": (f'IF(AND({sif("G", rubro="Ventas", sr="Sí")}=0,{sif("H", rubro="Ventas", sr="Sí")}=0),'
                                 f'{sif(c8, sec="Ingresos", ss="Sí")},{sif(c8, rubro="Ventas", sr="Sí")})'),
                "(−) Costo de ventas": sif(c8, sec="Costos", ss="Sí"),
                "Utilidad bruta": f"{c9}{F9['Ventas netas']}-{c9}{F9['(−) Costo de ventas']}",
                "(−) Gastos operativos": (f"{sif(c8, sec='Gastos', ss='Sí')}-{c9}{F9['(−) Gastos financieros']}"
                                          f"-{c9}{F9['(−) Participación e impuestos']}"),
                "Utilidad operativa": f"{c9}{F9['Utilidad bruta']}-{c9}{F9['(−) Gastos operativos']}",
                "(+) Otros ingresos": f"{sif(c8, sec='Ingresos', ss='Sí')}-{c9}{F9['Ventas netas']}",
                "(−) Gastos financieros": sif(c8, rubro="Gastos financieros", det="Sí"),
                UAI: f"{c9}{F9['Utilidad operativa']}+{c9}{F9['(+) Otros ingresos']}-{c9}{F9['(−) Gastos financieros']}",
                "(−) Participación e impuestos": sif(c8, rubro="Impuestos y participación", det="Sí"),
                "Utilidad neta": f"{c9}{F9[UAI]}-{c9}{F9['(−) Participación e impuestos']}",
            }[k]
            fila.append(fx(f_, n2(e9[q][k])))
        a_, c_ = e9["ant"][k], e9["act"][k]
        vp = None if a_ == 0 else (c_ - a_) / abs(a_)
        den_ref, den = (F9["TOTAL ACTIVO"], e9["act"]["TOTAL ACTIVO"]) if k in ESF else (F9["Ventas netas"], e9["act"]["Ventas netas"])
        obs = "" if vp is None or abs(vp) < d["umbrales"]["var"] / 100 else OBS_VARIACION
        den_a = e9["ant"]["TOTAL ACTIVO"] if k in ESF else e9["ant"]["Ventas netas"]
        fila += [fx(f"D{r}-C{r}", n2(c_ - a_)), fx(f'IF(C{r}=0,"",E{r}/ABS(C{r}))', vp),
                 fx(f'IF($D${den_ref}=0,"",D{r}/$D${den_ref})', _div(c_, den)),
                 fx(f'IF($C${den_ref}=0,"",C{r}/$C${den_ref})', _div(a_, den_a)),
                 fx(f'IF(F{r}="","",IF(ABS(F{r})>={_par("umbralVarPct")}/100,"{OBS_VARIACION}",""))', obs)]
        estados.append(fila)

    # 10 · índices
    def e(k, c9):
        return f"{E9}{c9}{F9[k]}"
    indices = []
    for k, nombre, cat, como in INDICES:
        r = F10[k]
        fila = [nombre, cat, como]
        for c10, c9, q in (("D", "C", "ant"), ("E", "D", "act")):
            dd = f"${c10}${F10['dias']}"
            ac, pc, inv = e("Activo corriente", c9), e("Pasivo corriente", c9), e("Inventarios", c9)
            ta_, tp, pnc = e("TOTAL ACTIVO", c9), e("TOTAL PASIVO", c9), e("Pasivo no corriente", c9)
            # Denominador patrimonial de los índices: patrimonio sin resultado + utilidad neta del ERI (igual que _indices / el HTML).
            pt = f'({e("PATRIMONIO (sin resultado del período)", c9)}+{e("Utilidad neta", c9)})'
            vn, cv = e("Ventas netas", c9), e("(−) Costo de ventas", c9)

            def q_(num, den):
                return f'IF({den}=0,"",ROUND({num}/{den},2))'
            f_ = {
                "dias": "365",
                "razonCorriente": q_(ac, pc), "pruebaAcida": q_(f"({ac}-{inv})", pc), "capitalTrabajo": f"ROUND({ac}-{pc},2)",
                "diasCartera": q_(f"{e('Cuentas por cobrar', c9)}*{dd}", vn), "diasInventario": q_(f"{inv}*{dd}", cv),
                "diasProveedores": q_(f"{e('Cuentas por pagar', c9)}*{dd}", cv),
                "ciclo": (f'IF(OR({c10}{F10["diasCartera"]}="",{c10}{F10["diasInventario"]}="",{c10}{F10["diasProveedores"]}=""),"",'
                          f'ROUND({c10}{F10["diasCartera"]}+{c10}{F10["diasInventario"]}-{c10}{F10["diasProveedores"]},2))'),
                "rotacionActivo": q_(vn, ta_), "endTotal": q_(tp, f"{ta_}") .replace("/" + ta_ + ",2)", "/" + ta_ + "*100,2)"),
                "endLP": q_(pnc, ta_).replace(f"/{ta_},2)", f"/{ta_}*100,2)"),
                "endFinanciero": q_(e("Obligaciones financieras", c9), pt), "endPatrimonial": q_(tp, pt), "multiplicador": q_(ta_, pt),
                "margenBruto": q_(e("Utilidad bruta", c9), vn).replace(f"/{vn},2)", f"/{vn}*100,2)"),
                "margenOperativo": q_(e("Utilidad operativa", c9), vn).replace(f"/{vn},2)", f"/{vn}*100,2)"),
                "margenNeto": q_(e("Utilidad neta", c9), vn).replace(f"/{vn},2)", f"/{vn}*100,2)"),
                "roi": q_(e("Utilidad operativa", c9), ta_).replace(f"/{ta_},2)", f"/{ta_}*100,2)"),
                "dupontRoi": (f'IF(OR({vn}=0,{ta_}=0),"",ROUND({e("Utilidad operativa", c9)}/{vn}*100*({vn}/{ta_}),2))'),
                "roe": q_(e("Utilidad neta", c9), pt).replace(f"/{pt},2)", f"/{pt}*100,2)"),
                "dupont": (f'IF(OR({vn}=0,{ta_}=0,{pt}=0),"",'
                           f'ROUND({e("Utilidad neta", c9)}/{vn}*100*({vn}/{ta_})*({ta_}/{pt}),2))'),
            }[k]
            v = ind[q][k]
            fila.append(fx(f_, "" if v is None else v))
        va, vc = ind["ant"][k], ind["act"][k]
        fila.append(fx(f'IF(OR(D{r}="",E{r}=""),"",E{r}-D{r})', "" if va is None or vc is None else _xr(vc - va, 2)))
        pat_ref, pat_v = f"{E9}$D${F9['PATRIMONIO TOTAL']}", d["est9"]["act"]["PATRIMONIO TOTAL"]
        fila.append(fx(_f_semaforo(k, f"E{r}", pat_ref), _semaforo(k, vc, d["fac"], pat_v)))
        if k == "dias":
            fila.append(fx(f'IF({PRELIM},"{LECTURA_DIAS[1]}","{LECTURA_DIAS[0]}")', LECTURA_DIAS[d["tipo"] == "Preliminar"]))
        else:
            fila.append(fx(_f_lectura(k, f"E{r}", pat_ref, f"I{r}"), _lectura(k, vc, pat_v, d["fac"])))
        if k in _DIAS_AJ:   # días ajustados al período: en la preliminar, × meses ÷ 12 (comparables con un año)
            fac_ = d["fac"]
            fila += [fx(f'IF(E{r}="","",ROUND(E{r}*{FAC},2))', "" if vc is None else _xr(vc * fac_, 2)),
                     fx(f'IF(F{r}="","",ROUND(F{r}*{FAC},2))', "" if va is None or vc is None else _xr(_xr(vc - va, 2) * fac_, 2))]
        else:
            fila += [None, None]
        f_t = _f_tendencia(k, r, pat_ref)
        fila.append(None if f_t is None else fx(f_t, _tendencia(k, va, vc, pat_v)))
        indices.append(fila)

    # 11 · materialidad
    per = f"$E${F11['Período de la base']}"
    rb = f"$A${F11[BASES[0]]}:$A${F11[BASES[-1]]}"
    materialidad = [["Período de la base", None, None, None,
                     fx(f'IF({_par("periodoBase")}="Automático",IF({PRELIM},"Año anterior","Corte actual"),{_par("periodoBase")})',
                        d["periodo"]), None, None]]
    for b in BASES:
        r = F11[b]
        f7 = F7[_REF_BASE7[b]]
        f_b = (f'IF({per}="Año anterior",{S7}F{f7},{S7}G{f7}*{ANUAL})' if b in BASES_FLUJO
               else f'IF({per}="Año anterior",{S7}F{f7},{S7}G{f7})')
        materialidad.append([b, fx(f_b, n2(d["bases"][b])),
                             fx(_par(_PCT_BASE[b]), d["pctBase"][b]), fx(f"B{r}*C{r}/100", n2(d["bases"][b] * d["pctBase"][b] / 100)),
                             SUSTENTO_PCT, *_rango(b, f"C{r}", d["pctBase"][b])])
    rg, rd = F11["Materialidad global"], F11["Materialidad de desempeño"]
    rt_ = F11["Umbral de errores claramente insignificantes"]
    materialidad += [
        ["Materialidad global", fx(f"INDEX($B${F11[BASES[0]]}:$B${F11[BASES[-1]]},MATCH({_par('baseMaterialidad')},{rb},0))", n2(mt["base"])),
         fx(f"INDEX($C${F11[BASES[0]]}:$C${F11[BASES[-1]]},MATCH({_par('baseMaterialidad')},{rb},0))", d["pctBase"][d["base"]]),
         fx(f'IF(B{rg}<=0,"",B{rg}*C{rg}/100)', n2(mt["global"])),
         fx(f'"Base elegida: "&{_par("baseMaterialidad")}&" ("&LOWER({per})&IF(AND({per}="Corte actual",{ANUAL}<>1,'
            f'{ES_FLUJO}),"{ANUALIZADA}"&{_par("mesesTranscurridos")},"")'
            f'&"); NIA 320 párr. 10"',
            _txt_base(d)),
         fx(f"INDEX($F${F11[BASES[0]]}:$F${F11[BASES[-1]]},MATCH({_par('baseMaterialidad')},{rb},0))", _rango(d["base"], "", 0)[0]),
         fx(f"INDEX($G${F11[BASES[0]]}:$G${F11[BASES[-1]]},MATCH({_par('baseMaterialidad')},{rb},0))",
            _rango(d["base"], "", d["pctBase"][d["base"]])[1]["v"])],
        ["Materialidad de desempeño", fx(f"D{rg}", n2(mt["global"])), fx(_par("pctDesempeno"), d["pct"]["pctDesempeno"]),
         fx(f'IF(B{rd}="","",B{rd}*C{rd}/100)', n2(mt["desempeno"])), "NIA 320 párr. 11 y A12 (práctica: 50 %–75 %)",
         *_rango("desempeno", f"C{rd}", d["pct"]["pctDesempeno"])],
        ["Umbral de errores claramente insignificantes", fx(f"D{rg}", n2(mt["global"])), fx(_par("pctTrivial"), d["pct"]["pctTrivial"]),
         fx(f'IF(B{F11["Umbral de errores claramente insignificantes"]}="","",B{F11["Umbral de errores claramente insignificantes"]}'
            f'*C{F11["Umbral de errores claramente insignificantes"]}/100)',
            n2(mt["trivial"])), "NIA 450 párr. 5 y A2: no se acumulan los errores menores",
         *_rango("trivial", f"C{rt_}", d["pct"]["pctTrivial"])],
        ["Justificación de la base", None, None, None,
         fx(f'IF({_par("justificacion")}<>"",{_par("justificacion")},"Base "&{_par("baseMaterialidad")}&" de US$ "&FIXED(B{rg},2)&'
            f'IF(D{rg}="",": sin materialidad (base cero o negativa). "," × "&FIXED(C{rg},2)&" % = US$ "&FIXED(D{rg},2)&": ")&' + "".join(
             f'IF({_par("baseMaterialidad")}="{b}","{JUSTIFICACION[b]}",' for b in BASES[:-1]) + f'"{JUSTIFICACION[BASES[-1]]}"'
            + ")" * (len(BASES) - 1) + ")", _justif_cifras(d, mt, pv("justificacion"))), None, None],
    ]
    # A10 · materialidad específica (NIA 320 párr. 10): automática si el balance tiene cuentas de partes relacionadas,
    # accionistas o remuneraciones (hoja 24, MES-01); el importe es el % de la global de la política de la firma.
    pos_ev = enc_m.fila_de(d["evals"])
    mes1 = enc_m.ref_resultado(pos_ev, "MES-01")
    v1 = next(x["res"]["v"] for x in d["evals"] if x["codigo"] == "MES-01")
    r_me, r_g = F11["Materialidad específica"], F11["Materialidad global"]
    pct_me = d["pe"]["pctMatEspecifica"]
    v3 = mt["global"] * pct_me / 100 if v1 == "Sí" and mt["global"] else None
    sus_me = (f"Partes relacionadas, accionistas o remuneraciones: {_num(pct_me)} % de la global (política de la firma)"
              if v1 == "Sí" else "No aplica: sin cuentas de partes relacionadas, accionistas o remuneraciones (hoja 24)")
    materialidad.append([
        "Materialidad específica (NIA 320 párr. 10)", None, fx(_par("pctMatEspecifica"), pct_me),
        fx(f'IF(AND({mes1}="Sí",D{r_g}<>""),D{r_g}*C{r_me}/100,"")', "" if v3 is None else n2(v3)),
        fx(f'IF({mes1}="Sí","Partes relacionadas, accionistas o remuneraciones: "&FIXED(C{r_me},2)&" % de la global (política de la '
           f'firma)","No aplica: sin cuentas de partes relacionadas, accionistas o remuneraciones (hoja 24)")', sus_me), None,
        fx(f'IF(OR(D{r_me}="",D{r_g}=""),"",IF(D{r_me}<D{r_g},"Conforme","Revisar"))',
           "" if v3 is None else "Conforme" if v3 < mt["global"] else "Revisar")])
    # M9 (NIA 320 párr. A12): porcentaje de desempeño sugerido por los factores del encargo.
    r_su = F11[DESEMP_SUGERIDO]
    tot30 = f"'{enc_m.H30}'!G{FILA0 + len(d['difs']) + 2}"
    n12_, n13_ = len(carta), len(riesgos)
    fac = [(f'{_par("encargoInicial")}="Sí"', "encargo inicial"),
           (f'AND({TRIVIAL}<>"",ABS(N({tot30}))>=N({TRIVIAL}))', "diferencias del año anterior sobre el umbral trivial"),
           (f'COUNTIF({_rng(R12, "M", n12_)},"Sí")+COUNTIFS({_rng(R13, "F", n13_)},"Sí",{_rng(R13, "H", n13_)},"Significativo")>0',
            "riesgos significativos")]
    n_fac = "(" + "+".join(f"({c_})*1" for c_, _t in fac) + ")"
    sug = d["sug"]
    t_fac = "&".join(f'IF({c_},"{t_}; ","")' for c_, t_ in fac)
    materialidad.append([
        DESEMP_SUGERIDO, None, fx(f"IF({n_fac}=0,75,IF({n_fac}=1,60,50))", sug["pct"]), None,
        fx(f'IF({t_fac}="","Sin factores que reduzcan el porcentaje (política de la firma: 75 %)","Factores: "&LEFT({t_fac},LEN({t_fac})-2)'
           f'&" (política de la firma: 60 % con uno, 50 % con dos o más)")',
           ("Factores: " + "; ".join(sug["factores"]) + " (política de la firma: 60 % con uno, 50 % con dos o más)") if sug["factores"]
           else "Sin factores que reduzcan el porcentaje (política de la firma: 75 %)"), None,
        fx(f'IF({_par("pctDesempeno")}<=C{r_su},"Conforme","Revisar: el porcentaje de la hoja 02 supera el sugerido")',
           "Conforme" if d["pct"]["pctDesempeno"] <= sug["pct"] + 1e-9 else "Revisar: el porcentaje de la hoja 02 supera el sugerido")])
    # M21: saldos con signo contrario que distorsionan la base y los índices.
    n_sg = sum(1 for a in anom if a["tipo"] == "Signo")
    f_sg = f'COUNTIFS({_rng(A17, "A", len(anom))},"Signo",{_rng(A17, "F", len(anom))},"Sí")'
    txt_sg = " cuentas con signo contrario afectan la base y los índices: revíselas antes de fijar la materialidad (NIA 320)"
    materialidad.append([
        AVISO_SIGNO, None, None, None,
        fx(f'IF({f_sg}>0,{f_sg}&"{txt_sg}","Sin saldos con signo contrario a su naturaleza")',
           f"{n_sg}{txt_sg}" if n_sg else "Sin saldos con signo contrario a su naturaleza"), None,
        fx(f'IF({f_sg}>0,"Revisar","Conforme")', "Revisar" if n_sg else "Conforme")])

    # 12 · matriz de la carta de control interno
    matriz = []
    for i, x in enumerate(carta):
        r = FILA0 + i
        matriz.append([x["id"], x["proceso"], x["hallazgo"], x["aser"], x["p"], x["i"], x["c"],
                       fx(f'IF(OR(E{r}="",F{r}=""),"",E{r}*F{r})', _txt(x["inh"])),
                       fx(f'IF(H{r}="","",IF(N{r}="Sí",IF(G{r}="","",H{r}*(6-G{r})/5),H{r}))', _txt(x["res"])),
                       fx(f'IF(I{r}="","Pendiente de calificación",IF(OR(M{r}="Sí",I{r}>={_par("umbralAlto")}),"Alto",'
                          f'IF(I{r}>={_par("umbralMedio")},"Medio","Bajo")))', x["nivel"]),
                       x["respuesta"] or RESPUESTA_DEFECTO, x["herramienta"],
                       fx(f'IF(ISNUMBER(SEARCH("fraude",B{r}&" "&C{r})),"Sí",IF(H{r}="","",IF(H{r}>={_par("umbralSignificativo")},'
                          f'"Sí","No")))', x["sig"]), _f_probar(d["enf"], x), x["comp"], x["ti"],
                       fx(f'IF(OR(M{r}="Sí",J{r}="Alto"),"{DEF_SIGNIFICATIVA}",IF(LEFT(J{r},9)="Pendiente","{DEF_PENDIENTE}",'
                          f'"{DEF_OTRA}"))', _clase_def(x)), SEGUIMIENTO])

    # 14 · perfil del encargo (se arma antes de la 13, que remite a sus importes)
    perfil, estilos_p, fila14 = _perfil(informe, d, pv, ruc)

    # 13 · posibles riesgos
    fila8 = {x["codigo"]: FILA0 + i for i, x in enumerate(cu)}
    ref_valor = {"presuncion": f"{E9}D{F9['Ventas netas']}", "ct": f"{I10}E{F10['capitalTrabajo']}", "rc": f"{I10}E{F10['razonCorriente']}",
                 "end": f"{I10}E{F10['endTotal']}", "perdida": f"{E9}D{F9['Utilidad neta']}", "patrimonio": f"{E9}D{F9['PATRIMONIO TOTAL']}",
                 "cartera": f"{I10}I{F10['diasCartera']}", "inventario": f"{I10}I{F10['diasInventario']}",
                 "end80": f"{I10}E{F10['endTotal']}", "rotCartera": f"{I10}J{F10['diasCartera']}",
                 "rotInventario": f"{I10}J{F10['diasInventario']}"}
    cond_f = {"ct": "E{r}<0", "perdida": "E{r}<0", "patrimonio": "E{r}<=0"}
    cond_v = {"rc": "E{r}<1", "end": "E{r}>70", "end80": "E{r}>80", "cartera": "E{r}>90",
              "inventario": "E{r}>120", "rotCartera": "E{r}>" + _par("umbralDiasRotacion"),
              "rotInventario": "E{r}>" + _par("umbralDiasRotacion")}
    posibles = []
    for i, x in enumerate(riesgos):
        r = FILA0 + i
        c_ = x["cod"]
        if c_ in ref_valor:
            valor = fx(ref_valor[c_], "" if x["valor"] is None else (x["valor"] if c_ in cond_v else n2(x["valor"])))
        elif c_ == "variacion":
            valor = fx(f"{H8}I{fila8[x['cuenta']]}", n2(x["valor"]))
        elif c_ == "informe" and x["valor"] is not None:
            valor = fx(f"{P14}D{fila14[x['idx']]}", n2(x["valor"]))
        else:
            valor = None
        if c_ == "presuncion":
            pres = fx(f'IF({_par("refutarIngresos")}="Sí","No (refutada)","Sí")', x["presenta"])
        elif c_ in cond_f:
            pres = fx(f'IF({cond_f[c_].format(r=r)},"Sí","No")', x["presenta"])
        elif c_ in cond_v:
            pres = fx(f'IF(E{r}="","No",IF({cond_v[c_].format(r=r)},"Sí","No"))', x["presenta"])
        elif c_ == "variacion":
            pres = fx(f'IF({_ge(f"E{r}")},"Sí","No")', x["presenta"])
        elif c_ == "inicial":
            pres = fx(_par("encargoInicial"), x["presenta"])
        elif c_ in ("anterior_otro", "anterior_no"):
            ea = "Auditados por otro auditor" if c_ == "anterior_otro" else "No auditados"
            pres = fx(f'IF({_par("estadosAnteriores")}="{ea}","Sí","No")', x["presenta"])
        elif c_ == "cuestionario":
            pres = fx(f'IF({enc_m.ref_estado(enc_m.fila_de(d["evals"]), x["q"])}="Alerta","Sí","No")', x["presenta"])
        elif x.get("f_pres"):
            pres = fx(x["f_pres"], x["presenta"])
        else:
            pres = x["presenta"]
        posibles.append([x["codigo"], x["origen"], x["rubro"], x["cond"], valor, pres, x["riesgo"], x["sev"], x["norma"]])

    # 15 · notas
    notas_h = []
    for i, x in enumerate(notas):
        r = FILA0 + i

        def pn(pref, n, x=x):
            if not x["pref"]:
                return "0"
            a_, e_, i_ = _rng(pref, "A", n), _rng(pref, "E", n), _rng(pref, "I", n)
            return "+".join(f'IF(SUMPRODUCT(({a_}="{c}")*1)>0,SUMPRODUCT(({a_}="{c}")*{i_}),'
                            f'SUMPRODUCT({_desc_lit(a_, c)}*({e_}="Sí")*{i_}))' for c in x["pref"])
        notas_h.append([x["nota"], x["titulo"], x["codigos"], n2(x["auditado"]), fx(pn(B4, n4), n2(x["ant"])),
                        fx(f"E{r}-D{r}", n2(x["dif"])), fx(pn(B5, n5), n2(x["act"])), fx(f"G{r}-E{r}", n2(x["var"])),
                        fx(f'IF(E{r}=0,"",H{r}/ABS(E{r}))', x["varPct"])])

    # 17 · anomalías (antes que 16, que las cuenta)
    anomalias = []
    for x in anom:
        rr = fila8[x["x"]["codigo"]]
        col = {"act": "H", "ant": "G", "var": "I"}[x["col"]]
        h_, g_, i_, j_ = (f"{H8}{c}{rr}" for c in "HGIJ")
        pres = {"Signo": f'IF(AND({h_}<-0.005,{_ge(h_, "*0.5")}),"Sí","No")',
                "Nueva": f'IF(AND({g_}=0,{_ge(h_)}),"Sí","No")',
                "Baja": f'IF(AND({h_}=0,{_ge(g_)}),"Sí","No")',
                "Variación": f'IF({j_}="","No",IF(AND(ABS({j_})*100>={_par("umbralVarExtrema")},{_ge(i_)}),"Sí","No"))',
                "Duplicado": f'IF(AND({_ge(h_)},COUNTIFS({R8["H"]},{h_},{R8["D"]},"Sí")>=2),"Sí","No")'}[x["tipo"]]
        anomalias.append([x["tipo"], ", ".join(x.get("grupo") or [x["x"]["codigo"]]), x["x"]["cuenta"], x["det"],
                          fx(f"{H8}{col}{rr}", n2(x["x"][x["col"]])), fx(pres, "Sí"), x["sev"]])

    # 34–42 · pendientes M1–M21 (planificacion_calidad): factores, entendimiento, stand-back, analíticos, estimaciones,
    # leyes, partes relacionadas, empresa en funcionamiento y cambios frente a la versión anterior.
    reg_h, pos_r = enc_m.filas_registros(d["reg"])
    c_cal = {"H8": H8, "E9": E9, "F9": F9, "I10": I10, "F10": F10, "M11": M11, "F11": F11, "R12": R12, "R13": R13, "C18": C18,
             "N15": N15, "P19": P19, "DESEMP": DESEMP, "GLOBAL": GLOBAL, "par": _par, "fila8": fila8, "n_reg": len(reg_h),
             "R_": enc_m.R_, "indag": list(zip(pos_r["indagaciones"], d["reg"].get("indagaciones") or [])),
             "mat": mt["global"], "n13": len(riesgos), "corte": d["corte"], "H25": enc_m.H25}
    factores_h = cal_m.filas_factores(carta, riesgos, R12, R13)
    ficha = d["reg"].get("ficha") or {}
    cap = [x for x in cu if x["sec"] == "Patrimonio" and x["detalle"] == "Sí" and cal_m._hay(x["cuenta"], ("capital", "aporte"))]
    unif = cal_m.uniformidad(informe, notas, d["marco"])
    ia_, ip_ = ind["act"], e9["act"]
    fm = lambda v, dec=2: "sin dato" if v is None else _num(v, dec)  # noqa: E731
    vv = None if not e9["ant"]["Ventas netas"] else (ip_["Ventas netas"] - e9["ant"]["Ventas netas"]) / abs(e9["ant"]["Ventas netas"])
    ent_h = cal_m.filas_entendimiento({
        **c_cal, "ficha": ficha, "informe": informe, "notas": notas, "carta": carta,
        "capital": {"refs": [f"{H8}H{fila8[x['codigo']]}" for x in cap], "txt": cal_m._m(sum(x["act"] for x in cap))},
        "desempeno_v": (f"Margen neto: {fm(ia_['margenNeto'])}{' %' if ia_['margenNeto'] is not None else ''}; ROE: {fm(ia_['roe'])}"
                        f"{' %' if ia_['roe'] is not None else ''}; variación de las ventas: "
                        f"{'sin dato' if vv is None else fm(vv * 100, 1) + ' %'}"),
        "politicas_v": (f"Marco: {d['marco']} (edición: {d['edicion']}); notas del año anterior: {len(notas)}; {unif['txt']}"),
        "cambios_v": unif["txt"],
        "financ_v": (f"Endeudamiento del activo: {fm(ia_['endTotal'])}{' %' if ia_['endTotal'] is not None else ''}; obligaciones "
                     f"financieras: US$ {fm(ip_['Obligaciones financieras'])}")})
    stand_h = cal_m.filas_stand_back(rev, notas, c_cal)
    an_h = cal_m.filas_analiticos(d["an"], c_cal)
    est_h = cal_m.filas_estimaciones(d["est"], c_cal)
    act_txt = " ".join([str(ficha.get("activity") or "")] + [x["detalle"] for x in informe if cal_m._hay(x["concepto"], ("actividad",))]
                       + [str(ruc.get("actividades") or ""), str(ruc.get("actividad_principal") or "")])
    leyes_h = cal_m.filas_leyes(cu, act_txt, c_cal)
    partes_h = cal_m.filas_partes(d["partes"], cal_m.partes_textos(informe, notas), c_cal)
    assert len(partes_h) == d["n40"]
    em_h, _n_nofin = cal_m.filas_empresa_marcha(d["nofin"], len(riesgos_em(riesgos, True)), c_cal)
    cambios = cal_m.filas_cambios(d["ant"], riesgos, mt, c_cal)
    d["cambios"] = cambios
    va_h = cal_m.filas_version_anterior(d["ant"])

    # 16 · control de calidad
    n12, n13, n14, n15, n17 = len(carta), len(riesgos), len(informe), len(notas), len(anom)
    dif_act, dif_ant, otros = d["sec7"]["act"]["Diferencia de cuadre"], d["sec7"]["ant"]["Diferencia de cuadre"], d["otrosAbs"]

    def est_cuadre(v, activo):
        return "Conforme" if abs(v) < 0.01 else "Revisar" if abs(v) <= abs(activo) * 0.01 else "Crítico"
    altas = sum(1 for x in anom if x["sev"] == "Alto")
    ind570 = sum(1 for x in riesgos if x["norma"] == "NIA 570" and x["presenta"] == "Sí")
    pend = sum(1 for x in carta if x["nivel"].startswith("Pendiente"))
    no_conc = sum(1 for x in notas if abs(x["dif"]) >= 0.01)
    notas_det_h, est_d = _notas_detalle(notas, cu, d["sinNota"], d["umbrales"]["var"])
    comp, est_c = _composicion(notas, d["notasDet"])
    n_comp = sum(1 for f in comp if isinstance(f[4], dict) and f[4].get("v") == "Revisar")
    n_jer = sum(1 for k in ("ant", "act") for x in fu[k] if abs(x["difsub"]) >= 0.01)
    fch_ = d["fechas"]
    faltan_gob = sum(1 for k in GOBIERNO if (fch_.get(k) if k.startswith("fecha") else pv(k)) in (None, ""))
    control = [
        [CONTROLES[0], fx(f"{S7}G{F7['Diferencia de cuadre']}", n2(dif_act)), None,
         fx(f'IF(ABS(B{FILA0})<0.01,"Conforme",IF(ABS(B{FILA0})<=ABS({S7}G{F7["Activo"]})*0.01,"Revisar","Crítico"))',
            est_cuadre(dif_act, d["sec7"]["act"]["Activo"])), "Activo − (pasivo + patrimonio + resultado) del balance al corte."],
        [CONTROLES[1], fx(f"{S7}F{F7['Diferencia de cuadre']}", n2(dif_ant)), None,
         fx(f'IF(ABS(B{FILA0 + 1})<0.01,"Conforme",IF(ABS(B{FILA0 + 1})<=ABS({S7}F{F7["Activo"]})*0.01,"Revisar","Crítico"))',
            est_cuadre(dif_ant, d["sec7"]["ant"]["Activo"])), "Activo − (pasivo + patrimonio + resultado) del balance anterior."],
        [CONTROLES[2], fx(f'SUMPRODUCT(({_rng(B5, "G", n5)}="Otros")*({_rng(B5, "E", n5)}="Sí")*ABS({_rng(B5, "C", n5)}))',
                          n2(otros)), None,
         fx(f'IF(ABS(B{FILA0 + 2})<0.01,"Conforme",IF(ABS(B{FILA0 + 2})<=ABS({S7}G{F7["Activo"]})*0.01,"Revisar","Crítico"))',
            est_cuadre(otros, d["sec7"]["act"]["Activo"])), "Saldo de cuentas cuyo código no está en el mapa de cuentas."],
        [CONTROLES[3], fx(f"{M11}D{F11['Materialidad global']}", n2(mt["global"])), None,
         fx(f'IF(N(B{FILA0 + 3})>0,"Conforme","Crítico")', "Conforme" if mt["global"] else "Crítico"),
         "La materialidad global debe ser positiva."],
        [CONTROLES[4], None, fx(f'COUNTIFS({_rng(A17, "G", n17)},"Alto",{_rng(A17, "F", n17)},"Sí")', altas),
         fx(f'IF({DESEMP}="","No evaluado",IF(C{FILA0 + 4}>0,"Crítico",IF(COUNTIF({_rng(A17, "F", n17)},"Sí")>0,"Revisar","Conforme")))',
            "No evaluado" if not mt["desempeno"] else "Crítico" if altas else "Revisar" if anom else "Conforme"),
         "Alta = saldo negativo por naturaleza que no es cuenta correctora; «Revisar» si hay otras anomalías presentes."],
        [CONTROLES[5], None, fx(f"COUNTA({_rng(N15, 'A', n15)})", n15), fx(f'IF(C{FILA0 + 5}>0,"Conforme","Revisar")',
                                                                         "Conforme" if n15 else "Revisar"),
         "Notas auditadas del año anterior entregadas por el cliente."],
        [CONTROLES[6], None, fx(f"SUMPRODUCT((ABS({_rng(N15, 'F', n15)})>=0.01)*1)", no_conc),
         fx(f'IF(C{FILA0 + 6}>0,"Revisar","Conforme")', "Revisar" if no_conc else "Conforme"),
         "Diferencias entre el balance del cierre anterior y las notas auditadas."],
        [CONTROLES[7], None, fx(f'COUNTIFS({_rng(R13, "I", n13)},"NIA 570",{_rng(R13, "F", n13)},"Sí")', ind570),
         fx(f'IF(C{FILA0 + 7}>0,"Revisar","Conforme")', "Revisar" if ind570 else "Conforme"),
         "Capital de trabajo, liquidez, endeudamiento, pérdidas y patrimonio."],
        [CONTROLES[8], None, fx(f'COUNTIF({_rng(R12, "J", n12)},"Pendiente de calificación")', pend),
         fx(f'IF(C{FILA0 + 8}>0,"Revisar","Conforme")', "Revisar" if pend else "Conforme"),
         "Hallazgos sin probabilidad, impacto o control calificados por el socio."],
        [CONTROLES[9], None, fx(f"COUNTA({_rng(R12, 'A', n12)})", n12), fx(f'IF(C{FILA0 + 9}>0,"Conforme","Revisar")',
                                                                         "Conforme" if n12 else "Revisar"),
         "Hallazgos de la carta de control interno del año anterior."],
        [CONTROLES[10], None, fx(f'COUNTIF({P14}$G${FILA0}:$G${FILA0 + len(perfil) - 1},"{ORIGEN_INFORME}")', n14), fx(f'IF(C{FILA0 + 10}>0,"Conforme","Revisar")',
                                                                           "Conforme" if n14 else "Revisar"),
         "Identificación, opinión y asuntos del informe de auditoría anterior."],
        [CONTROLES[11], None,
         fx(f"SUMPRODUCT((ABS({_rng(B4, 'K', n4)})>=0.01)*1)+SUMPRODUCT((ABS({_rng(B5, 'K', n5)})>=0.01)*1)", n_jer),
         fx(f'IF(C{FILA0 + 11}>0,"Revisar","Conforme")', "Revisar" if n_jer else "Conforme"),
         "Se usa el saldo propio de la cuenta; la diferencia se muestra en las hojas 04 y 05 y no se fuerza."],
        [CONTROLES[12], None, fx(f'COUNTIF({_rng(C15, "E", len(comp))},"Revisar")', n_comp),
         fx(f'IF(COUNTA({_rng(C15, "B", len(comp))})=0,"No evaluado",IF(C{FILA0 + 12}>0,"Revisar","Conforme"))',
            "No evaluado" if not comp else "Revisar" if n_comp else "Conforme"),
         "Suma de las líneas de saldo de la composición auditada (hoja 15C) frente al saldo de cada nota."],
        [CONTROLES[13], None, fx(f'COUNTIF({_rng(D15, "I", len(notas_det_h))},"Sin nota")', len(d["sinNota"])),
         fx(f'IF({n15}=0,"No evaluado",IF(C{FILA0 + 13}>0,"Revisar","Conforme"))',
            "No evaluado" if not n15 else "Revisar" if d["sinNota"] else "Conforme"),
         "Rubros del balance sin nota que los cubra (al final de la hoja 15D); confirmar que no requerían revelación."],
        [CONTROLES[14], None, fx("+".join(f'IF({_par(k)}="",1,0)' for k in GOBIERNO), faltan_gob),
         fx(f'IF(C{FILA0 + 14}>0,"Revisar","Conforme")', "Revisar" if faltan_gob else "Conforme"),
         "Socio, gerente, enfoque y fechas de las visitas y del informe en la hoja 02; lo que falta queda [PENDIENTE] en la "
         "estrategia y en el programa."],
    ]
    control += _controles_encargo(d)
    control += _controles_calidad(d, len(anom), len(carta))

    # 18 · cuentas a revisar
    cuentas_rev = []
    for i, x in enumerate(rev):
        rr, r = fila8[x["x"]["codigo"]], FILA0 + i
        f_rb = "&".join(f'IF({R13}F{FILA0 + j}="Sí","{riesgos[j]["codigo"]} ","")' for j in x["rbi"])
        cuentas_rev.append([x["x"]["codigo"], x["x"]["cuenta"], fx(f"{H8}F{rr}", x["x"]["sec"]), fx(f"{H8}H{rr}", n2(x["x"]["act"])),
                            fx(f"{H8}I{rr}", n2(x["x"]["var"])), fx(f"{H8}O{rr}", x["x"]["material"]),
                            fx(f"{H8}P{rr}", x["x"]["varMaterial"]), x["riesgo"],
                            fx(f"TRIM({f_rb})", x["rb"]) if x["rbi"] else "", x["herr"],
                            fx(f'IF(OR(F{r}="Sí",G{r}="Sí",H{r}<>"",I{r}<>""),"Sí","No")', x["revisa"])])

    # 19 · programa (NIA 330)
    def alto_(v):   # D7: un riesgo pendiente de calificación se trata como alto hasta que el socio lo califique
        return v in ("Alto", "Significativo") or str(v).startswith("Pendiente")

    def oport(celda, v):
        f_ = (f'IF(OR({celda}="Alto",{celda}="Significativo",LEFT({celda},9)="Pendiente"),"{OPORTUNIDAD_ALTO}",'
              f'IF({celda}="Medio","{OPORTUNIDAD_MEDIO}","{OPORTUNIDAD_BAJO}"))')
        return fx(f_, OPORTUNIDAD_ALTO if alto_(v) else OPORTUNIDAD_MEDIO if v == "Medio" else OPORTUNIDAD_BAJO)
    programa = []

    def resp_(nivel):
        # D6: el responsable es el de la hoja 02; si falta, queda [PENDIENTE] (no un rótulo que parezca un nombre).
        k, pend = ("socio", PENDIENTE_SOCIO) if alto_(nivel) else ("gerente", PENDIENTE_GERENTE)
        return fx(f'IF({_par(k)}="","{pend}",{_par(k)})', pv(k) or pend)

    def aplica(f_, v):   # D5: sin materialidad el alcance no está definido
        return fx(f'IF({DESEMP}="","{NO_APLICA_SIN_MAT}",{f_})', NO_APLICA_SIN_MAT if not mt["desempeno"] else v)

    def evid(r, nv, base):   # D8: un riesgo significativo exige pruebas de detalle
        return fx(f'IF(D{r}="Significativo","{EVIDENCIA_SIGNIFICATIVO}{base}","{base}")',
                  (EVIDENCIA_SIGNIFICATIVO + base) if nv == "Significativo" else base)
    # 28 · valoración por afirmación (A5): antes del programa, porque el muestreo toma el nivel más alto de cada cuenta.
    eeff = [(j, x) for j, x in enumerate(riesgos) if x["cod"] == "elusion" or x["norma"] == "NIA 570" or x.get("eeff")]
    af_cuentas = []
    for i, x in enumerate(rev):
        if x["revisa"] != "Sí":
            continue
        c = x["x"]
        area_x = _area(c["cuenta"], c["sec"])
        vinc = []
        for ci, y in enumerate(carta):
            if area_x and _area(y["proceso"] + " " + y["hallazgo"]) == area_x:
                nv_ = ("Significativo" if y["sig"] == "Sí" else "Alto" if y["nivel"] == "Alto" or y["nivel"].startswith("Pendiente")
                       else y["nivel"])
                vinc.append(("12", FILA0 + ci, nv_, y["aser"] or ASEVERACIONES_AREA.get(area_x, "Todas"), y["id"], y["probar"]))
        for j in x["rbi"]:
            y = riesgos[j]
            vinc.append(("13", FILA0 + j, y["sev"] if y["presenta"] == "Sí" else None, _aser_riesgo(y, cu), y["codigo"], ""))
        sec_txt = norm(ASEVERACIONES_SECCION.get(c["sec"], ""))
        af_cuentas.append({"codigo": c["codigo"], "cuenta": c["cuenta"], "sec": c["sec"], "r18": FILA0 + i,
                           "material": c["material"] == "Sí" or c["varMaterial"] == "Sí", "vinc": vinc,
                           "relevantes": {n_ for n_, claves in enc_m.AFIRMACIONES if any(k in sec_txt for k in claves)}})
    afirm = enc_m.filas_afirmaciones(eeff, af_cuentas, {"R12": R12, "R13": R13, "C18": C18})
    nivel28 = {c["codigo"]: (FILA0 + len(eeff) + k, afirm[len(eeff) + k][len(enc_m.AFIRMACIONES) + 4])
               for k, c in enumerate(af_cuentas)}
    cubiertas_area, cubiertos_cod = set(), set()
    for i, x in enumerate(carta):
        r12, r = FILA0 + i, FILA0 + len(programa)
        area_c = _area(x["proceso"] + " " + x["hallazgo"])
        cubiertas_area.add(area_c)
        nv = "Significativo" if x["sig"] == "Sí" else x["nivel"]
        base = EVIDENCIA_CARTA if x["probar"] == "Sí" else EVIDENCIA_DEFECTO
        # A13: si la carta no trae aseveraciones, las del área del hallazgo (no «Todas»).
        aser_a = ASEVERACIONES_AREA.get(area_c, "Todas")
        programa.append([f"PT-{len(programa) + 1:02d}", x["proceso"], x["id"], fx(f'IF({R12}M{r12}="Sí","Significativo",{R12}J{r12})', nv),
                         fx(f"{R12}K{r12}", x["respuesta"] or RESPUESTA_DEFECTO), fx(f"{R12}L{r12}", x["herramienta"]),
                         oport(f"D{r}", nv), fx(f'IF({R12}D{r12}="","{aser_a}",{R12}D{r12})', x["aser"] or aser_a),
                         evid(r, nv, base), resp_(nv), aplica('"Sí"', "Sí")])
    for i, x in enumerate(riesgos):
        if x["presenta"] != "Sí":
            continue
        r = FILA0 + len(programa)
        cubiertos_cod.add(x["rubro"].split(" ")[0])
        if x["norma"] != "NIA 570":
            cubiertas_area.add(_area(x["rubro"]))
        programa.append([f"PT-{len(programa) + 1:02d}", x["rubro"], x["codigo"], fx(f"{R13}H{FILA0 + i}", x["sev"]), x["resp"], x["herr"],
                         oport(f"D{r}", x["sev"]), _aser_riesgo(x, cu),
                         evid(r, x["sev"], segun_marco(EVIDENCIA_RIESGO.get(x["norma"], EVIDENCIA_DEFECTO), d["marco"])), resp_(x["sev"]),
                         aplica(f"{R13}F{FILA0 + i}", "Sí")])
    # Cobertura (NIA 330 párr. 18, D4): toda cuenta material (por saldo o por variación) lleva su propio procedimiento
    # sustantivo, aunque haya un riesgo de su área: una indagación o la explicación de una variación no son pruebas
    # sustantivas del saldo. Las cuentas a revisar solo por un riesgo quedan cubiertas por la respuesta a ese riesgo.
    cuentas_pt = []
    for i, x in enumerate(rev):
        c = x["x"]
        material = c["material"] == "Sí" or c["varMaterial"] == "Sí"
        if x["revisa"] != "Sí" or (not material and (c["codigo"] in cubiertos_cod
                                                      or (_area(c["cuenta"], c["sec"]) or "·") in cubiertas_area)):
            continue
        r, r18 = FILA0 + len(programa), FILA0 + i
        nivel = "Medio" if material else "Bajo"
        r28, k28 = nivel28[c["codigo"]]
        e_ = next((y for y in d["enf"] if y["ciclo"] == enf_m.ciclo_de(_area(c["cuenta"], c["sec"]))), None)
        cuentas_pt.append({"pt": f"PT-{len(programa) + 1:02d}", "codigo": c["codigo"], "cuenta": c["cuenta"],
                           "nivel": k28["v"] if isinstance(k28, dict) else k28, "r28": r28, "r08": fila8[c["codigo"]], "saldo": c["act"],
                           "r19": r, "r45": enf_m.ref_final(d["enf"], e_["ciclo"]) if e_ else None,
                           "confia": bool(e_ and e_["confia"])})
        programa.append([f"PT-{len(programa) + 1:02d}", c["cuenta"], f"Cuenta {c['codigo']}",
                         fx(f'IF(OR({C18}F{r18}="Sí",{C18}G{r18}="Sí"),"Medio","Bajo")', nivel),
                         RESPUESTA_SECCION.get(c["sec"], RESPUESTA_CUENTA), x["herr"],
                         oport(f"D{r}", nivel), ASEVERACIONES_SECCION.get(c["sec"], "Existencia; integridad; valuación"),
                         EVIDENCIA_DEFECTO, resp_(nivel), aplica(f"{C18}K{r18}", "Sí")])
    # A14 · plan de confirmaciones (NIA 505) y observación del recuento físico (NIA 501) de las cuentas materiales por saldo.
    for clave, (norma, proc, evid_, aser, oport_) in CONFIRMACIONES.items():
        filas18 = [(FILA0 + i, x["x"]) for i, x in enumerate(rev) if x["revisa"] == "Sí" and x["x"]["material"] == "Sí"
                   and x["x"]["sec"] in ("Activo", "Pasivo")
                   and (_area(x["x"]["cuenta"], x["x"]["sec"]) == clave if clave != "Partes relacionadas"
                        else "relacionad" in _sin_tildes(x["x"]["cuenta"]).lower())]
        if not filas18:
            continue
        r = FILA0 + len(programa)
        cods = ", ".join(c["codigo"] for _r, c in filas18)
        f_ap = "OR(" + ",".join(f'{C18}F{r18}="Sí"' for r18, _c in filas18) + ")"
        programa.append([f"PT-{len(programa) + 1:02d}", clave, f"{norma} · {cods}", fx(f'IF({f_ap},"Medio","Bajo")', "Medio"),
                         proc, _herramienta(clave), oport_, aser, evid_, resp_("Medio"), aplica(f'IF({f_ap},"Sí","No")', "Sí")])
    for area_, norma, proc, evid_, aser in PROC_ENCARGO:
        programa.append([f"PT-{len(programa) + 1:02d}", area_, norma, "Todo encargo", proc, _herramienta(area_),
                         OPORTUNIDAD_ENCARGO, aser, evid_, resp_("Medio"), "Sí"])
    # M19 (NIA 510): evidencia propia de los saldos de apertura, en la visita preliminar, si el año anterior no lo auditamos.
    ap_f = f'IF(OR({_par("encargoInicial")}="Sí",{_par("estadosAnteriores")}<>"{enc_m.ESTADOS_ANTERIORES[0]}"),"Sí","No")'
    ap_v = "Sí" if d["sino"]["encargoInicial"] == "Sí" or d["pe"]["estadosAnteriores"] != enc_m.ESTADOS_ANTERIORES[0] else "No"
    programa.append([f"PT-{len(programa) + 1:02d}", "Saldos de apertura", "NIA 510", "Medio", PROC_APERTURA, SIN_HERRAMIENTA,
                     "Visita preliminar", "Existencia; integridad; valuación", EVID_APERTURA, resp_("Medio"), aplica(ap_f, ap_v)])
    # Prioridad baja (NIA 610): si la carta menciona la auditoría interna, evaluarla antes de usar su trabajo (hoja 27, AI-01).
    ai_v = next((x["res"]["v"] if isinstance(x["res"], dict) else x["res"] for x in d["evals"] if x["codigo"] == "AI-01"), "")
    ai_f = f'IF(LEFT({enc_m.ref_resultado(enc_m.fila_de(d["evals"]), "AI-01")},2)="Sí","Sí","No")'
    programa.append([f"PT-{len(programa) + 1:02d}", "Auditoría interna", "NIA 610", "Bajo", enc_m.PROC_AUDITORIA_INTERNA,
                     SIN_HERRAMIENTA, "Visita preliminar", "Todas", enc_m.EVID_AUDITORIA_INTERNA, resp_("Bajo"),
                     aplica(ai_f, "Sí" if str(ai_v).startswith("Sí") else "No")])
    # M6 (NIA 240 y 330): elemento de imprevisibilidad sobre una cuenta que normalmente no se revisa (rota cada año).
    impr = _imprevisible(rev, d["corte"])
    if impr:
        programa.append([f"PT-{len(programa) + 1:02d}", impr["cuenta"], "Imprevisibilidad (NIA 240)", "Bajo", PROC_IMPREVISIBLE,
                         _herramienta(impr["cuenta"], impr["sec"]), "Visita final, sin aviso previo",
                         ASEVERACIONES_SECCION.get(impr["sec"], "Existencia; integridad; valuación"), EVIDENCIA_DEFECTO,
                         resp_("Bajo"), aplica('"Sí"', "Sí")])
    # A12 · extensión: tamaño de la muestra por cuenta (hoja 29) y, en los riesgos, según su nivel.
    refs_m = {"P19": P19, "P29": P29, "H8": H8, "DESEMP": DESEMP, "P28": ref(enc_m.H28)}
    muestreo, tam = enc_m.filas_muestreo(cuentas_pt, mt, d["pe"], refs_m, _par)
    cuenta_de = {c["r19"]: c["codigo"] for c in cuentas_pt}
    for k, fila_ in enumerate(programa):
        r = FILA0 + k
        nv_ = fila_[3]["v"] if isinstance(fila_[3], dict) else fila_[3]
        fila_.append(enc_m.extension(r, nv_, tam.get(cuenta_de.get(r)), refs_m))
    # M2 (NIA 300 y 220): horas presupuestadas y supervisión planificada de cada procedimiento.
    pc = d["pc"]
    for k, fila_ in enumerate(programa):
        r = FILA0 + k
        nv_ = fila_[3]["v"] if isinstance(fila_[3], dict) else fila_[3]
        ap_ = fila_[10]["v"] if isinstance(fila_[10], dict) else fila_[10]
        fila_ += [fx(cal_m.f_horas(r, _par), cal_m.horas_nivel(nv_, pc, ap_)), fx(cal_m.f_supervision(r), cal_m.supervision(nv_))]
    sup = {k: sum(1 for f in programa if f[13]["v"] == k) for k in (cal_m.SUP_SOCIO, cal_m.SUP_GERENTE)}
    horas_h = cal_m.filas_horas(sum(f[12]["v"] for f in programa), len(programa), d["reg"]["equipo"], sup, d["fechas"], pc, c_cal)
    # Prioridad baja (NIA 580): manifestaciones generales, las que exigen otras NIA y las específicas de los riesgos.
    n_d = len(d["difs"])
    man_h = cal_m.filas_manifestaciones({
        "R12": R12, "R13": R13, "carta": carta, "riesgos": riesgos,
        "n_est": (f'SUMPRODUCT(--(LEN({cal_m.rng(cal_m.H38, "A", len(d["est"]))})>0))', len(d["est"])),
        "n570": (f'COUNTIFS({_rng(R13, "I", len(riesgos))},"NIA 570",{_rng(R13, "F", len(riesgos))},"Sí")', len(riesgos_em(riesgos))),
        "dif": (f"COUNTIF('{enc_m.H30}'!$I${FILA0}:$I${FILA0 + n_d - 1},\"Sí\")" if n_d else "0",
                sum(1 for x in d["difs"] if x["acumula"] == "Sí"))})
    # 45–47 · enfoque por ciclo (sustantivo por política; el socio puede decidir confiar), matriz de riesgos consolidada y conocimiento del negocio
    ctas_ciclo = {}
    for x in rev:
        ci = enf_m.ciclo_de(_area(x["x"]["cuenta"], x["x"]["sec"]))
        if ci and x["revisa"] == "Sí":
            ctas_ciclo.setdefault(ci, []).append(x["x"]["codigo"])
    enfoque_h = enf_m.filas_enfoque(d["enf"], carta, ctas_ciclo, {
        "R12": R12, "H34": ref(cal_m.H34), "par": _par, "n12": len(carta), "R_": enc_m.R_, "pos_enfoque": pos_r["enfoque"],
        "ref_ci": enc_m.ref_estado(pos_ev, "CI-01"), "refs_ti": [enc_m.ref_estado(pos_ev, f"TI-0{k}") for k in (1, 2, 3)]})
    for x in riesgos:
        x.setdefault("area", _area(x["rubro"]))
        x.setdefault("aser", _aser_riesgo(x, cu))
    matriz_h = enf_m.filas_matriz(carta, riesgos, d["enf"], programa, {"R12": R12, "R13": R13, "P19": P19, "par": _par,
                                                                        "u_alto": d["umbrales"]["alto"], "u_medio": d["umbrales"]["medio"]})
    conoc_h, est_con = enf_m.filas_conocimiento(_conocimiento(d, perfil, ent_h, matriz_h, mt, e9, ind))

    # 00_Registros y 24–32 · documentación del encargo (A1–A19), todo automático
    reg, evals = d["reg"], d["evals"]
    pos_ev = enc_m.fila_de(evals)
    registros_h, pos_reg = enc_m.filas_registros(reg)
    q24, q26, q27 = (enc_m.filas_evaluacion(evals, h_) for h_ in (enc_m.H24, enc_m.H26, enc_m.H27))
    equipo, _est_eq = enc_m.filas_equipo(reg, pos_reg, d["sino"]["interesPublico"], d["pe"]["aniosRotacionSocio"], _par)
    difs = enc_m.diferencias(notas, informe, fila14, {"N15": N15, "P14": P14})
    assert [x["importe"] for x in difs] == [x["importe"] for x in d["difs"]]
    for x, y in zip(difs, d["difs"]):
        x["supera"], x["acumula"] = y["supera"], y["acumula"]
    dif_h, est_dif, _fd = enc_m.filas_diferencias(difs, d["dres"], mt, {"TRIVIAL": TRIVIAL, "DESEMP": DESEMP, "GLOBAL": GLOBAL})
    sig = [("12_Riesgos_CCI", FILA0 + i, "C", "M", "Sí", x["hallazgo"], x["id"]) for i, x in enumerate(carta) if x["sig"] == "Sí"]
    sig += [("13_Riesgos_Balance", FILA0 + j, "G", "F", "Sí", x["riesgo"], x["codigo"]) for j, x in enumerate(riesgos)
            if x["sev"] == "Significativo" and x["presenta"] == "Sí"]
    kam_ant = [(fila14[j], x["concepto"]) for j, x in enumerate(informe) if x["tipo"] == "Asunto clave" and j in fila14]
    comunic = enc_m.filas_comunicacion(pos_ev, {x["codigo"]: x["estado"] for x in evals},
                                       {x["codigo"]: x["res"]["v"] if isinstance(x["res"], dict) else x["res"] for x in evals},
                                       d["sino"], sig, kam_ant, [x["integrante"] for x in reg["equipo"] if x["rol"] == "Revisor de calidad"],
                                       {"GLOBAL": GLOBAL, "P14": P14, "mt_global": mt["global"]}, _par, d["fechas"], len(reg["equipo"]))

    n_def = sum(1 for x in carta if _clase_def(x) == DEF_SIGNIFICATIVA)
    f_def = f'COUNTIF({_rng(R12, "Q", len(carta))},"{DEF_SIGNIFICATIVA}")'
    comunic.append(["Deficiencias significativas del control interno",
                    fx(f'{f_def}&" deficiencias significativas: se comunican por escrito a los responsables del gobierno"',
                       f"{n_def} deficiencias significativas: se comunican por escrito a los responsables del gobierno"),
                    "NIA 265 párr. 9 (VERIFICAR)", fx(f'IF({f_def}>0,"Comunicar","No aplica")', "Comunicar" if n_def else "No aplica")])

    # 20 · narrativa
    ia, ip, ia_ant = ind["act"], e9["act"], e9["ant"]

    def i10(k, c="E"):
        return f"{I10}{c}{F10[k]}"
    va = None if ia_ant["TOTAL ACTIVO"] == 0 else (ip["TOTAL ACTIVO"] - ia_ant["TOTAL ACTIVO"]) / abs(ia_ant["TOTAL ACTIVO"])
    f_va = f"{E9}F{F9['TOTAL ACTIVO']}"
    dva = ip["TOTAL ACTIVO"] - ia_ant["TOTAL ACTIVO"]
    cif_act = "" if va is None else f" {_num(abs(va) * 100, 1)} % (US$ {_num(abs(dva))})"
    lect_act = ("Sin saldo comparable del período anterior." if va is None else
                f"El activo total se mantiene estable ({'+' if va >= 0 else '−'}{_num(abs(va) * 100, 1)} %) frente al período anterior."
                if abs(va) < 0.05 else
                f"El activo total creció{cif_act} respecto del período anterior." if va > 0 else
                f"El activo total disminuyó{cif_act} respecto del período anterior.")
    e_va = f"{E9}E{F9['TOTAL ACTIVO']}"
    t_cif = f'" "&FIXED(ABS({f_va})*100,1)&" % (US$ "&FIXED(ABS({e_va}),2)&")"'
    vu = None if ia_ant["Utilidad neta"] == 0 else (ip["Utilidad neta"] - ia_ant["Utilidad neta"]) / abs(ia_ant["Utilidad neta"])
    f_vu = f"{E9}F{F9['Utilidad neta']}"
    lect_res = (("Resultado negativo en el período" if ip["Utilidad neta"] < 0 else "Resultado positivo en el período")
                + ("." if vu is None else f" ({'+' if vu >= 0 else '−'}{_num(abs(vu) * 100, 1)} % frente al período anterior)."))
    n_alto_cci = sum(1 for x in carta if x["nivel"] == "Alto")
    n_pres = sum(1 for x in riesgos if x["presenta"] == "Sí")
    narrativa = [
        ["Hechos", "Activo total", fx(f"{E9}D{F9['TOTAL ACTIVO']}", n2(ip["TOTAL ACTIVO"])),
         fx(f'IF({f_va}="","Sin saldo comparable del período anterior.",IF(ABS({f_va})<0.05,"El activo total se mantiene estable ("&'
            f'IF({f_va}>=0,"+","−")&FIXED(ABS({f_va})*100,1)&" %) frente al período anterior.",IF({f_va}>0,"El activo total creció"&{t_cif}&'
            f'" respecto del período anterior.","El activo total disminuyó"&{t_cif}&" respecto del período anterior.")))', lect_act)],
        ["Hechos", "Pasivo total", fx(f"{E9}D{F9['TOTAL PASIVO']}", n2(ip["TOTAL PASIVO"])),
         fx(f'IF({i10("endTotal")}="","",IF({i10("endTotal")}>70,"Más del 70 % del activo se financia con terceros.",'
            f'"El financiamiento con terceros no supera el 70 % del activo."))',
            "" if ia["endTotal"] is None else "Más del 70 % del activo se financia con terceros." if ia["endTotal"] > 70 else
            "El financiamiento con terceros no supera el 70 % del activo.")],
        ["Hechos", "Patrimonio total", fx(f"{E9}D{F9['PATRIMONIO TOTAL']}", n2(ip["PATRIMONIO TOTAL"])),
         fx(f'IF(C{FILA0 + 2}<=0,"Patrimonio comprometido: indicio de empresa en funcionamiento (NIA 570).","Patrimonio positivo.")',
            "Patrimonio comprometido: indicio de empresa en funcionamiento (NIA 570)." if ip["PATRIMONIO TOTAL"] <= 0 else "Patrimonio positivo.")],
        ["Hechos", "Utilidad neta del período", fx(f"{E9}D{F9['Utilidad neta']}", n2(ip["Utilidad neta"])),
         fx(f'IF(C{FILA0 + 3}<0,"Resultado negativo en el período","Resultado positivo en el período")&IF({f_vu}="",".",'
            f'" ("&IF({f_vu}>=0,"+","−")&FIXED(ABS({f_vu})*100,1)&" % frente al período anterior).")', lect_res)],
    ]
    for k in ("razonCorriente", "endTotal", "margenNeto", "roe", "diasCartera", "diasInventario"):
        v = ia[k]
        nombre = next(n_ for kk, n_, *_r in INDICES if kk == k)
        # D11: en la preliminar el importe de los días es el ajustado al período (hoja 10, columna I), el mismo de la lectura.
        imp = (fx(i10(k, "I"), "" if v is None else _xr(v * d["fac"], 2)) if k in _DIAS_AJ
               else fx(i10(k), "" if v is None else v))
        narrativa.append(["Análisis", nombre, imp,
                          fx(f'{i10(k, "G")}&": "&{i10(k, "H")}',
                             f"{_semaforo(k, v, d['fac'], ip['PATRIMONIO TOTAL'])}: {_lectura(k, v, ip['PATRIMONIO TOTAL'], d['fac'])}")])
    narrativa += [
        ["Riesgos", "Riesgos altos de la carta de control interno", fx(f'COUNTIF({_rng(R12, "J", n12)},"Alto")', n_alto_cci),
         fx(f'IF(C{FILA0 + 10}>0,"Tienen respuesta específica en el programa (NIA 330).","Sin riesgos altos en la carta de control interno.")',
            "Tienen respuesta específica en el programa (NIA 330)." if n_alto_cci else "Sin riesgos altos en la carta de control interno.")],
        ["Riesgos", "Posibles riesgos presentes (NIA 240, balances e informe anterior)", fx(f'COUNTIF({_rng(R13, "F", n13)},"Sí")', n_pres),
         fx(f'IF(C{FILA0 + 11}>0,"Cada riesgo presente tiene su respuesta en el programa (hoja 19).","Sin riesgos adicionales.")',
            "Cada riesgo presente tiene su respuesta en el programa (hoja 19)." if n_pres else "Sin riesgos adicionales.")],
        ["Riesgos", "Indicios de empresa en funcionamiento (NIA 570)",
         fx(f'COUNTIFS({_rng(R13, "I", n13)},"NIA 570",{_rng(R13, "F", n13)},"Sí")', ind570),
         fx(f'IF(C{FILA0 + 12}>0,"Evaluar la capacidad de continuar y su revelación (NIA 570).","Sin indicios en los indicadores evaluados.")',
            "Evaluar la capacidad de continuar y su revelación (NIA 570)." if ind570 else "Sin indicios en los indicadores evaluados.")],
    ]
    # alertas por nombre (artefacto): cada riesgo alto de la carta y cada posible riesgo presente, con su texto y su norma
    for i, x in enumerate(carta):
        if x["nivel"] != "Alto":
            continue
        r12 = FILA0 + i
        nv_ = "Significativo" if x["sig"] == "Sí" else x["nivel"]
        narrativa.append(["Alertas", f"{x['id']} · {x['proceso']}", fx(f"{R12}I{r12}", _txt(x["res"])),
                          fx(f'IF(OR({R12}J{r12}="Alto",{R12}M{r12}="Sí"),{R12}C{r12}&" — nivel "&IF({R12}M{r12}="Sí","Significativo",'
                             f'{R12}J{r12}),"Ya no es de nivel alto con la calificación actual.")', f"{x['hallazgo']} — nivel {nv_}")])
    for i, x in enumerate(riesgos):
        if x["presenta"] != "Sí":
            continue
        r13, v13 = FILA0 + i, posibles[i][4]
        narrativa.append(["Alertas", f"{x['codigo']} · {x['rubro']}", fx(f"{R13}E{r13}", v13["v"]) if isinstance(v13, dict) else None,
                          fx(f'IF({R13}F{r13}="Sí",{R13}G{r13}&" ("&{R13}I{r13}&")","Ya no se presenta con los datos actuales.")',
                             f"{x['riesgo']} ({x['norma']})")])
    # causa-efecto (lectura de las variaciones del artefacto), sobre las variaciones de la hoja 09
    dv = {k: e9["act"][k] - e9["ant"][k] for k in ("Inventarios", "Ventas netas", "Efectivo y equivalentes", "Cuentas por cobrar",
                                                  "Cuentas por pagar", "Obligaciones financieras", "Utilidad neta")}
    ev = {k: f"{E9}E{F9[k]}" for k in dv}
    for concepto, clave, f_, v_ in _causa_efecto(ev, dv, d["marco"]):
        narrativa.append(["Causa-efecto", concepto, fx(ev[clave], n2(dv[clave])), fx(f_, v_)])
    # origen y destino del efectivo: las dos partidas que más originan y las dos que más aplican (hoja 22). D11: la variación
    # de «Resultados acumulados» es sobre todo el traspaso del resultado anterior, no efectivo: se suma al resultado del
    # período y se lee como «resultado neto de traspasos y distribuciones» (= resultado actual − dividendos).
    o22 = ref("22_Origenes")
    r_res22 = FILA0 + len(d["origenes"])
    acum = [j for j, x in enumerate(d["origenes"]) if _es_resultado_patrimonio(x)]
    cand = [(f"{o22}B{FILA0 + j}", x["cuenta"], f"{o22}E{FILA0 + j}", x["efecto"])
            for j, x in enumerate(d["origenes"]) if j not in acum]
    cand.append((f'"{RESULTADO_NETO_TRASPASOS}"', RESULTADO_NETO_TRASPASOS,
                 "+".join([f"{o22}E{r_res22}"] + [f"{o22}E{FILA0 + j}" for j in acum]),
                 d["puente"]["resultado"] + sum(d["origenes"][j]["efecto"] for j in acum)))
    fuentes = sorted([c for c in cand if c[3] > 0.005], key=lambda c: -c[3])[:2]
    usos = sorted([c for c in cand if c[3] < -0.005], key=lambda c: c[3])[:2]
    for concepto, sel, vacio in (("Origen del efectivo", fuentes, "Sin orígenes de efectivo en las cuentas del balance."),
                                 ("Destino del efectivo", usos, "Sin aplicaciones de efectivo en las cuentas del balance.")):
        if not sel:
            narrativa.append(["Causa-efecto", concepto, None, vacio])
            continue
        partes_f = [f'{nf}&" (US$ "&FIXED(ABS({ef}),2)&")"' for nf, _nv, ef, _ev in sel]
        partes_v = [f"{nv} (US$ {_num(abs(ev))})" for _nf, nv, _ef, ev in sel]
        pref = "Principales orígenes: " if concepto.startswith("Origen") else "Principales aplicaciones: "
        narrativa.append(["Causa-efecto", concepto, fx("+".join(f"({ef})" if "+" in ef else ef for _nf, _nv, ef, _ev in sel),
                                                          n2(sum(ev for *_x, ev in sel))),
                          fx(f'"{pref}"&' + '&" y "&'.join(partes_f) + '&"."', pref + " y ".join(partes_v) + ".")])

    ref_rec = {"rc": "razonCorriente", "end": "endTotal", "cartera": "diasCartera", "inventario": "diasInventario"}
    for nombre, k, cond, si, no in RECOMENDACIONES:
        si = segun_marco(si, d["marco"])
        v = ia[ref_rec[k]]
        dias_ = k in ("cartera", "inventario")          # A2: en un corte parcial, días × meses ÷ 12
        cumple = v is not None and eval(f"{v * d['fac'] if dias_ else v}{cond}")  # noqa: S307  (cond es una constante)
        c_ = f"{i10(ref_rec[k])}*{FAC}" if dias_ else i10(ref_rec[k])
        narrativa.append(["Recomendaciones", nombre, None,
                          fx(f'IF({i10(ref_rec[k])}="","{no}",IF({c_}{cond},"{si}","{no}"))', si if cumple else no)])
    narrativa.append(["Recomendaciones", "Resultados", None,
                      fx(f'IF({E9}D{F9["Utilidad neta"]}<0,"Analizar la estructura de costos y gastos ante el resultado negativo.",'
                         f'"No aplica: resultado positivo.")',
                         "Analizar la estructura de costos y gastos ante el resultado negativo." if ip["Utilidad neta"] < 0 else
                         "No aplica: resultado positivo.")])
    narrativa.append(["Recomendaciones", "Monitoreo", None, "Mantener el monitoreo periódico de los indicadores y covenants."])

    # 21 · estrategia
    def txt(k, valor):
        return fx(f'IF({_par(k)}="","",{_par(k)})', valor)
    sino = d["sino"]
    ref_ing = "No refutada: riesgo significativo (NIA 240 párr. 26)"
    n_rev = len(rev)
    riesgos_altos = float(res["totals"]["riesgosAltos"])
    estrategia = [
        ["Marco de información financiera", fx(f'{_par("marco")}&" · edición: "&{_par("edicionMarco")}', f'{d["marco"]} · edición: {d["edicion"]}'),
         "NIA 300 párr. 8 a)"],
        ["Tipo de revisión", fx(_par("tipoRevision"), d["tipo"]), "Cronograma del encargo"],
        ["Períodos comparados", fx(f'IF({PRELIM},"Balance: cierre anterior contra el corte; resultados: mismo corte de ambos años",'
                                   '"Balance y resultados: diciembre anterior contra diciembre actual")',
                                   "Balance: cierre anterior contra el corte; resultados: mismo corte de ambos años" if d["tipo"] == "Preliminar"
                                   else "Balance y resultados: diciembre anterior contra diciembre actual"), "NIA 315 párr. 14 b); NIA 520"],
        ["Enfoque general", _f_enfoque_general(d), "NIA 300 párr. 8; NIA 330 párr. 7–8 (hoja 45)"],
        ["Encargo inicial", fx(f'IF({_par("encargoInicial")}="Sí","Sí: procedimientos sobre saldos de apertura (NIA 510)","No")',
                               "Sí: procedimientos sobre saldos de apertura (NIA 510)" if sino["encargoInicial"] == "Sí" else "No"),
         "NIA 300 párr. 13"],
        ["Entidad de interés público o cotizada", fx(f'IF({_par("interesPublico")}="Sí","Sí: comunicar asuntos clave de auditoría (NIA 701)","No")',
                                                     "Sí: comunicar asuntos clave de auditoría (NIA 701)" if sino["interesPublico"] == "Sí" else "No"),
         "NIA 300 párr. 8 b)"],
        ["Base de la materialidad", fx(f'{_par("baseMaterialidad")}&" ("&LOWER({M11}$E${F11["Período de la base"]})&")"',
                                       f"{d['base']} ({d['periodo'].lower()})"), "NIA 320 párr. A3–A5"],
        ["Materialidad global", fx(f"{M11}$D${F11['Materialidad global']}", n2(mt["global"])), "NIA 320 párr. 10"],
        ["Materialidad de desempeño", fx(DESEMP, n2(mt["desempeno"])), "NIA 320 párr. 11"],
        ["Umbral de errores claramente insignificantes", fx(f"{M11}$D${F11['Umbral de errores claramente insignificantes']}", n2(mt["trivial"])),
         "NIA 450 párr. 5"],
        ["Riesgos altos o significativos", fx(f"{ref('01_Resumen')}B{FILA0 + list(res['labels']).index('riesgosAltos')}", riesgos_altos),
         "NIA 315 párr. 32; NIA 330 párr. 15 y 21"],
        ["Cuentas principales a revisar", fx(f'COUNTIF({_rng(C18, "K", n_rev)},"Sí")', float(res["totals"]["cuentasRevisar"])),
         "NIA 330 párr. 18"],
        ["Presunción de fraude en ingresos", fx(f'IF({_par("refutarIngresos")}="Sí","Refutada: "&{_par("motivoRefutacion")},"{ref_ing}")',
                                                ("Refutada: " + str(pv("motivoRefutacion") or "")) if sino["refutarIngresos"] == "Sí" else ref_ing),
         "NIA 240 párr. 26 y 47"],
        ["Visita preliminar", txt("fechaPreliminar", fch["fechaPreliminar"] or ""), "NIA 300 párr. 8 c)"],
        ["Visita final", txt("fechaFinal", fch["fechaFinal"] or ""), "NIA 300 párr. 8 c)"],
        ["Entrega del informe", txt("fechaInforme", fch["fechaInforme"] or ""), "NIA 300 párr. 8 b)"],
        ["Socio del encargo", fx(f'IF({_par("socio")}="","{PENDIENTE_SOCIO}",{_par("socio")})', pv("socio") or PENDIENTE_SOCIO),
         "NIA 220; NIA 300 párr. 8 e)"],
        ["Gerente o encargado", fx(f'IF({_par("gerente")}="","{PENDIENTE_GERENTE}",{_par("gerente")})', pv("gerente") or PENDIENTE_GERENTE),
         "NIA 300 párr. 8 e) y 11"],
        ["Uso de expertos", txt("expertos", pv("expertos") or ""), "NIA 300 párr. 8 e) y NIA 620"],
        ["Comunicación con los responsables del gobierno",
         fx(f'IF({enc_m.ref_estado(pos_ev, "COM-01")}="Pendiente","{enc_m.PENDIENTE} comunicar el alcance, el momento y los riesgos '
            f'significativos (hoja 32)","Comunicada: alcance, momento y riesgos significativos (hoja 32)")',
            f"{enc_m.PENDIENTE} comunicar el alcance, el momento y los riesgos significativos (hoja 32)"
            if next(x["estado"] for x in d["evals"] if x["codigo"] == "COM-01") == "Pendiente"
            else "Comunicada: alcance, momento y riesgos significativos (hoja 32)"),
         "NIA 260 (Revisada) párr. 15"],
    ]
    estrategia += _estrategia_encargo(d, carta, riesgos, afirm, len(eeff))
    estrategia += _estrategia_calidad(d, carta, riesgos, programa, cambios, impr, horas_h)

    # 22 · orígenes y aplicaciones
    origenes_h = []
    for x in d["origenes"]:
        r, rr = FILA0 + len(origenes_h), fila8[x["codigo"]]
        origenes_h.append([x["codigo"], x["cuenta"], fx(f"{H8}F{rr}", x["sec"]), fx(f"{H8}I{rr}", n2(x["var"])),
                           fx(f'IF(C{r}="Activo",-D{r},D{r})', n2(x["efecto"])),
                           TRASPASO if _es_resultado_patrimonio(x) else fx(_f_tipo(f"E{r}"), _tipo_efecto(x["efecto"]))])
    pu, n_o = d["puente"], len(origenes_h)
    r_res = FILA0 + n_o
    origenes_h += [
        ["", "Resultado del período (según el balance)", "Resultados",
         fx(f"{E9}E{F9['Resultado del período (según el balance)']}", n2(pu["resultado"])), fx(f"D{r_res}", n2(pu["resultado"])),
         fx(_f_tipo(f"E{r_res}"), _tipo_efecto(pu["resultado"]))],
        ["", "Total orígenes menos aplicaciones", "", None, fx(f"SUM(E{FILA0}:E{r_res})", n2(pu["total"])), ""],
        ["", "Variación del efectivo y equivalentes", "Activo", None, fx(f"{E9}E{F9['Efectivo y equivalentes']}", n2(pu["caja"])), ""],
        ["", "Diferencia (cero si ambos balances cuadran)", "", None, fx(f"E{r_res + 1}-E{r_res + 2}", n2(pu["dif"])),
         fx(f'IF(ABS(E{r_res + 3})<0.01,"Cuadra","Revisar")', "Cuadra" if abs(pu["dif"]) < 0.01 else "Revisar")],
    ]

    # 23 · audit trail (NIA 230)
    arch = d["archivos"]
    signo_txt = {k: (f'IF({S7}E{F7[k]}=-1,"{k.lower()}: saldo acreedor, se invierte","{k.lower()}: saldo deudor")',
                     f"{k.lower()}: saldo acreedor, se invierte" if d["signo"][k] == -1 else f"{k.lower()}: saldo deudor")
                 for k in ("Activo", "Pasivo", "Patrimonio", "Ingresos", "Costos", "Gastos")}
    comp_txt = ("Mismo corte del año anterior (RQ-003)" if d["hayEri"] else "Prorrateo: diciembre ÷ 12 × meses transcurridos") \
        if d["tipo"] == "Preliminar" else "Diciembre anterior contra diciembre actual"
    n_inf = f'COUNTIF({P14}$G${FILA0}:$G${FILA0 + len(perfil) - 1},"{ORIGEN_INFORME}")'
    trail = [[f"{etq} ({rq})", arch[ds][0], fx(f"COUNTA({_rng(pref, 'A', n)})" if pref else n_inf, n)]
             for etq, rq, ds, pref, n in (
                 ("Balance de comprobación del cierre anterior", "RQ-001", "balance_anterior", B4, n4),
                 ("Balance de comprobación al corte", "RQ-002", "balance_actual", B5, n5),
                 ("Resultados del año anterior al mismo corte", "RQ-003", "resultados_mismo_corte", B6, n6),
                 ("Carta de control interno", "RQ-004", "carta_control_interno", R12, len(carta)),
                 ("Informe de auditoría del año anterior", "RQ-005", "informe_anterior", None, len(informe)),
                 ("Notas a los estados financieros del año anterior", "RQ-006", "notas_estados_financieros", N15, len(notas)))]
    # Huella de los datos leídos de cada documento (SHA-256 de sus filas) y, si la plataforma los entrega, de los archivos.
    trail += [[f"Huella de los datos leídos · {rq}", f"SHA-256 {arch[ds][2]}" if arch[ds][1] else "Sin datos", None]
              for rq, ds in (("RQ-001", "balance_anterior"), ("RQ-002", "balance_actual"), ("RQ-003", "resultados_mismo_corte"),
                             ("RQ-004", "carta_control_interno"), ("RQ-005", "informe_anterior"),
                             ("RQ-006", "notas_estados_financieros"))]
    trail += [[f"Archivo entregado · {x['requerimiento']} · {x['nombre']}",
               f"SHA-256 {x['sha256']} · subido por {x['subido_por'] or 'sin registro'} el {x['subido_en'][:19].replace('T', ' ')}",
               None] for x in d["arch_plat"]] or [
        ["Archivos entregados (SHA-256)", ("La plataforma registra el nombre y la huella de cada archivo al subirlo y los lista aquí "
                                           "al ejecutar la prueba; esta ejecución no recibió archivos de la plataforma."), None]]
    trail += [
        ["Tipo de revisión", fx(_par("tipoRevision"), d["tipo"]), fx(_par("mesesTranscurridos"), d["meses"])],
        ["Comparativo de resultados", fx(f'IF({PRELIM},IF({hay_eri},"Mismo corte del año anterior (RQ-003)",'
                                         '"Prorrateo: diciembre ÷ 12 × meses transcurridos"),"Diciembre anterior contra diciembre actual")',
                                         comp_txt), None],
        ["Convención de signos (R2)", fx("&\"; \"&".join(f for f, _ in signo_txt.values()), "; ".join(v for _, v in signo_txt.values())),
         None],
        ["Valor de cada cuenta (R1)", "Saldo propio de la cuenta; si no está en el balance, la suma de sus subcuentas. El cuadre se "
                                      "verifica y no se fuerza.", None],
        ["Mapa de cuentas", "Hoja 03: el prefijo más largo del código define la clasificación", fx(f"COUNTA({_rng(MP, 'A', nm)})", nm)],
        ["Base de días (R4)", fx(f"{I10}H{F10['dias']}", LECTURA_DIAS[d["tipo"] == "Preliminar"]), fx(f"{I10}E{F10['dias']}", 365)],
        ["Materialidad (NIA 320)", fx(f"{M11}E{F11['Materialidad global']}", _txt_base(d)),
         fx(f"{M11}D{F11['Materialidad global']}", n2(mt["global"]))],
        ["Motor de cálculo", VERSION, None],
        ["Aprobación (R10)", ("El ciclo del Command Center registra quién envió a revisión y quién aprobó, con fecha (carátula y "
                              "control de revisión); si es la misma persona, la carátula lo advierte (NIA 220)."), None],
    ]

    # 01 · resumen
    ref_res = {"activos": f"{E9}D{F9['TOTAL ACTIVO']}", "pasivos": f"{E9}D{F9['TOTAL PASIVO']}",
               "patrimonio": f"{E9}D{F9['PATRIMONIO TOTAL']}", "ventas": f"{E9}D{F9['Ventas netas']}",
               "resultado": f"{E9}D{F9['Utilidad neta']}", "materialidad": f"N({M11}D{F11['Materialidad global']})",
               "desempeno": f"N({DESEMP})", "trivial": f"N({M11}D{F11['Umbral de errores claramente insignificantes']})",
               "riesgosAltos": (f'COUNTIF({_rng(R12, "J", n12)},"Alto")+COUNTIFS({_rng(R13, "F", n13)},"Sí",{_rng(R13, "H", n13)},"Alto")'
                                f'+COUNTIFS({_rng(R13, "F", n13)},"Sí",{_rng(R13, "H", n13)},"Significativo")'),
               "cuentasRevisar": f'COUNTIF({_rng(C18, "K", n_rev)},"Sí")'}
    t = {k: float(v) for k, v in res["totals"].items()}
    resumen = [[res["labels"][k], fx(ref_res[k], n2(t[k]))] for k in res["labels"]]

    return _nota_metodologica([
        hoja("01_Resumen", _ETQ["01_Resumen"], [["Concepto", "t"], ["Importe", "n"]], resumen, explica=EXPLICA["01_Resumen"]),
        hoja("02_Parametros", _ETQ["02_Parametros"], [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Mapa", _ETQ["03_Mapa"], [["Prefijo del código", "t"], ["Clasificación", "t"], ["Sección", "t"]], mapa,
             explica=EXPLICA["03_Mapa"]),
        bc_ant, bc_act, bc_eri,
        hoja("07_Secciones", _ETQ["07_Secciones"], [["Concepto", "t"], ["Bruto BC anterior", "n"], ["Bruto BC corte", "n"],
                                            ["Bruto ERI anterior", "n"], ["Signo", "i"], ["BC anterior", "n"], ["BC corte", "n"],
                                            ["ERI anterior", "n"]], secciones, explica=EXPLICA["07_Secciones"]),
        hoja("08_Horizontal", _ETQ["08_Horizontal"], [["Código", "t"], ["Cuenta", "t"], ["Nivel", "i"], ["Detalle", "t"], ["Clasificación", "t"],
                                             ["Sección", "t"], ["Anterior", "n"], ["Actual", "n"], ["Variación", "n"], ["Variación %", "p"],
                                             ["Peso vertical", "p"], ["Rubro del ERI", "t"], ["Rubro para índices", "t"],
                                             ["Cuenta para índices", "t"], ["Monto material", "t"], ["Variación material", "t"],
                                             ["Superior de la sección", "t"], ["Superior de la clasificación", "t"],
                                             ["Superior del rubro del ERI", "t"]],
             horizontal, explica=EXPLICA["08_Horizontal"]),
        hoja("08S_Sumarias", _ETQ["08S_Sumarias"], COLS_SUMARIA, sumarias, explica=EXPLICA["08S_Sumarias"], estilos=estilos_s),
        hoja("08A_ESF_Detalle", _ETQ["08A_ESF_Detalle"], _cols_detalle(f_a["esf"], f_c), esf_det,
             explica=_explica_detalle(f_a["esf"], f_c, "total del activo (hoja 09)"), estilos=est_a),
        hoja("08B_ERI_Detalle", _ETQ["08B_ERI_Detalle"], _cols_detalle(f_a["eri"], f_c), eri_det,
             explica=_explica_detalle(f_a["eri"], f_c, "ventas netas (hoja 09)"), estilos=est_b),
        hoja("09_Estados", _ETQ["09_Estados"], [["Concepto", "t"], ["Estado", "t"], ["Anterior", "n"], ["Actual", "n"], ["Variación", "n"],
                                          ["Variación %", "p"], ["Vertical actual", "p"], ["Vertical anterior", "p"],
                                          ["Observación", "t"]], estados,
             explica=EXPLICA["09_Estados"]),
        hoja("10_Indices", _ETQ["10_Indices"], [["Indicador", "t"], ["Categoría", "t"], ["Cómo se calcula", "t"], ["Anterior", "n"],
                                          ["Actual", "n"], ["Variación", "n"], ["Semáforo", "t"], ["Lectura", "t"],
                                          ["Actual ajustado al período", "n"], ["Variación ajustada", "n"], ["Tendencia", "t"]],
             indices, explica=EXPLICA["10_Indices"], colores=["Semáforo", "Tendencia"]),
        hoja("11_Materialidad", _ETQ["11_Materialidad"], [["Concepto", "t"], ["Importe", "n"], ["Porcentaje", "n"], ["Materialidad", "n"],
                                                ["Sustento", "t"], ["Rango de práctica", "t"], ["¿Dentro del rango?", "t"]],
             materialidad, explica=EXPLICA["11_Materialidad"], colores=["¿Dentro del rango?"]),
        hoja("12_Riesgos_CCI", _ETQ["12_Riesgos_CCI"], [["Código del hallazgo", "t"], ["Proceso o área", "t"], ["Hallazgo o riesgo", "t"],
                                               ["Aseveraciones", "t"], ["Probabilidad (1–5)", "i"], ["Impacto (1–5)", "i"],
                                               ["Control (1–5)", "i"], ["Riesgo inherente", "n"], ["Riesgo valorado", "n"], ["Nivel", "t"],
                                               ["Respuesta de auditoría", "t"], ["Herramienta del catálogo", "t"],
                                               ["¿Riesgo significativo?", "t"], ["¿Se probará el control?", "t"],
                                               ["Componente del control interno", "t"], ["Control general de TI", "t"],
                                               ["Clasificación de la deficiencia (NIA 265)", "t"], ["Seguimiento", "t"]], matriz,
             explica=EXPLICA["12_Riesgos_CCI"], colores=["Nivel"]),
        hoja("13_Riesgos_Balance", _ETQ["13_Riesgos_Balance"], [["Código", "t"], ["Origen", "t"], ["Rubro o área", "t"], ["Condición observada", "t"],
                                                   ["Valor observado", "n"], ["¿Se presenta?", "t"], ["Posible riesgo", "t"],
                                                   ["Severidad", "t"], ["Norma", "t"]], posibles, explica=EXPLICA["13_Riesgos_Balance"],
             colores=["Severidad"]),
        hoja("14_Perfil", _ETQ["14_Perfil"], [["Tipo", "t"], ["Concepto", "t"], ["Detalle", "x"], ["Importe (USD)", "n"],
                                          ["Fuente o referencia", "t"], ["Efecto en la planificación", "t"], ["Origen", "t"]], perfil,
             explica=EXPLICA["14_Perfil"], estilos=estilos_p),
        hoja("15_Notas", _ETQ["15_Notas"], [["Nota", "t"], ["Título de la nota", "t"], ["Cuentas del balance (códigos)", "t"],
                                         ["Saldo auditado según la nota", "n"], ["Saldo del balance anterior", "n"], ["Diferencia", "n"],
                                         ["Saldo al corte", "n"], ["Variación", "n"], ["Variación %", "p"]], notas_h,
             explica=EXPLICA["15_Notas"]),
        hoja("15D_Notas_Detalle", _ETQ["15D_Notas_Detalle"], COLS_NOTAS_DET, notas_det_h, explica=EXPLICA["15D_Notas_Detalle"],
             estilos=est_d),
        hoja("15C_Composicion", _ETQ["15C_Composicion"], COLS_COMPOSICION, comp, explica=EXPLICA["15C_Composicion"], estilos=est_c,
             guia="Composición de cada nota tal como la presenta el informe auditado del año anterior (RQ-009): una fila por "
                  "línea, con su importe y su tipo (Saldo, Movimiento o Total)."),
        hoja("16_Control", _ETQ["16_Control"], [["Control", "t"], ["Importe", "n"], ["Cantidad", "i"], ["Estado", "t"], ["Detalle", "t"]],
             control, explica=EXPLICA["16_Control"], colores=["Estado"]),
        hoja("17_Anomalias", _ETQ["17_Anomalias"], [["Tipo", "t"], ["Código", "t"], ["Cuenta", "t"], ["Detalle", "t"], ["Importe", "n"],
                                             ["¿Se presenta?", "t"], ["Severidad", "t"]], anomalias, explica=EXPLICA["17_Anomalias"],
             colores=["Severidad"]),
        hoja("18_Cuentas_Revisar", _ETQ["18_Cuentas_Revisar"], [["Código", "t"], ["Cuenta", "t"], ["Sección", "t"], ["Saldo actual", "n"],
                                                   ["Variación", "n"], ["Monto material", "t"], ["Variación material", "t"],
                                                   ["Riesgo de la carta de CI", "t"], ["Riesgos de la hoja 13", "t"], ["Herramienta del catálogo", "t"],
                                                   ["¿Se revisa?", "t"]], cuentas_rev, explica=EXPLICA["18_Cuentas_Revisar"]),
        hoja("19_Programa", _ETQ["19_Programa"], [["PT", "t"], ["Área o rubro", "t"], ["Riesgo", "t"], ["Nivel", "t"],
                                            ["Respuesta de auditoría (NIA 330)", "t"], ["Herramienta del catálogo", "t"], ["Oportunidad", "t"],
                                            ["Aseveraciones", "t"], ["Evidencia a obtener (PBC)", "t"], ["Responsable", "t"],
                                            ["¿Aplica?", "t"], ["Extensión (NIA 330 y 530)", "t"], ["Horas presupuestadas", "n"],
                                            ["Supervisión", "t"]],
             programa, explica=EXPLICA["19_Programa"], colores=["Nivel"]),
        hoja("20_Narrativa", _ETQ["20_Narrativa"], [["Bloque", "t"], ["Concepto", "t"], ["Importe", "n"], ["Lectura", "t"]], narrativa,
             explica=EXPLICA["20_Narrativa"]),
        hoja("21_Estrategia", _ETQ["21_Estrategia"], [["Aspecto", "t"], ["Decisión", "x"], ["Sustento", "t"]], estrategia,
             explica=EXPLICA["21_Estrategia"]),
        hoja("22_Origenes", _ETQ["22_Origenes"], [["Código", "t"], ["Cuenta", "t"], ["Sección", "t"], ["Variación", "n"],
                                            ["Efecto en el efectivo", "n"], ["Tipo", "t"]], origenes_h, explica=EXPLICA["22_Origenes"]),
        hoja("23_Audit_trail", _ETQ["23_Audit_trail"], [["Concepto", "t"], ["Detalle", "t"], ["Valor", "n"]], trail,
             explica=EXPLICA["23_Audit_trail"]),
        hoja(enc_m.REG, _ETQ[enc_m.REG], enc_m.COLS_REGISTROS, registros_h, guia=enc_m.GUIA_REGISTROS),
        hoja(enc_m.H24, _ETQ[enc_m.H24], enc_m.COLS_EVALUACION, q24, explica=enc_m.EXPLICA[enc_m.H24], colores=["Estado"]),
        hoja(enc_m.H25, _ETQ[enc_m.H25], enc_m.COLS_EQUIPO, equipo, explica=enc_m.EXPLICA[enc_m.H25], colores=["Estado"]),
        hoja(enc_m.H26, _ETQ[enc_m.H26], enc_m.COLS_EVALUACION, q26, explica=enc_m.EXPLICA[enc_m.H26], colores=["Estado"]),
        hoja(enc_m.H27, _ETQ[enc_m.H27], enc_m.COLS_EVALUACION, q27, explica=enc_m.EXPLICA[enc_m.H27], colores=["Estado"]),
        hoja(enc_m.H28, _ETQ[enc_m.H28], enc_m.COLS_AFIRMACIONES, afirm, explica=enc_m.EXPLICA[enc_m.H28],
             colores=[a for a, _ in enc_m.AFIRMACIONES] + ["Nivel más alto"]),
        hoja(enc_m.H29, _ETQ[enc_m.H29], enc_m.COLS_MUESTREO, muestreo, explica=enc_m.EXPLICA[enc_m.H29], colores=["Nivel"]),
        hoja(enc_m.H30, _ETQ[enc_m.H30], enc_m.COLS_DIF, dif_h, explica=enc_m.EXPLICA[enc_m.H30], estilos=est_dif,
             colores=["Evaluación"]),
        hoja(enc_m.H32, _ETQ[enc_m.H32], enc_m.COLS_COMUNICACION, comunic, explica=enc_m.EXPLICA[enc_m.H32], colores=["Estado"]),
        hoja(cal_m.H34, _ETQ[cal_m.H34], cal_m.COLS_FACTORES, factores_h, explica=cal_m.EXPLICA[cal_m.H34], colores=["Nivel"]),
        hoja(cal_m.H35, _ETQ[cal_m.H35], cal_m.COLS_ENTENDIMIENTO, ent_h, explica=cal_m.EXPLICA[cal_m.H35], colores=["Estado"]),
        hoja(cal_m.H36, _ETQ[cal_m.H36], cal_m.COLS_STAND, stand_h, explica=cal_m.EXPLICA[cal_m.H36]),
        hoja(cal_m.H37, _ETQ[cal_m.H37], cal_m.COLS_ANALITICOS, an_h, explica=cal_m.EXPLICA[cal_m.H37]),
        hoja(cal_m.H38, _ETQ[cal_m.H38], cal_m.COLS_ESTIMACIONES, est_h, explica=cal_m.EXPLICA[cal_m.H38]),
        hoja(cal_m.H39, _ETQ[cal_m.H39], cal_m.COLS_LEYES, leyes_h, explica=cal_m.EXPLICA[cal_m.H39]),
        hoja(cal_m.H40, _ETQ[cal_m.H40], cal_m.COLS_PARTES, partes_h, explica=cal_m.EXPLICA[cal_m.H40]),
        hoja(cal_m.H41, _ETQ[cal_m.H41], cal_m.COLS_EM, em_h, explica=cal_m.EXPLICA[cal_m.H41]),
        hoja(cal_m.VERSION_ANT, _ETQ[cal_m.VERSION_ANT], cal_m.COLS_VERSION_ANT, va_h,
             guia="La entrega la plataforma: cifras y riesgos de la versión anterior aprobada de esta planificación."),
        hoja(cal_m.H42, _ETQ[cal_m.H42], cal_m.COLS_CAMBIOS, cambios, explica=cal_m.EXPLICA[cal_m.H42]),
        hoja(cal_m.H43, _ETQ[cal_m.H43], cal_m.COLS_HORAS, horas_h, explica=cal_m.EXPLICA[cal_m.H43], colores=["Estado"]),
        hoja(cal_m.H44, _ETQ[cal_m.H44], cal_m.COLS_MANIFESTACIONES, man_h, explica=cal_m.EXPLICA[cal_m.H44]),
        hoja(enf_m.H45, _ETQ[enf_m.H45], enf_m.COLS_ENFOQUE, enfoque_h, explica=enf_m.EXPLICA[enf_m.H45]),
        hoja(enf_m.H46, _ETQ[enf_m.H46], enf_m.COLS_MATRIZ, matriz_h, explica=enf_m.EXPLICA[enf_m.H46],
             colores=["Riesgo inherente", "Riesgo de incorrección material"]),
        hoja(enf_m.H47, _ETQ[enf_m.H47], enf_m.COLS_CONOCIMIENTO, conoc_h, explica=enf_m.EXPLICA[enf_m.H47], estilos=est_con),
        hoja(PROBLEMAS, _ETQ[PROBLEMAS], [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e_["code"], e_["message"], n2(float(e_["amount"]))] for e_ in res["exceptions"]]),
    ])


# M20 (control de calidad): las citas de párrafos no cotejadas con el texto oficial vigente no se muestran como «VERIFICAR» en
# las hojas entregables; llevan la marca «†» y se listan en la nota metodológica (00_Nota_metodologica), con las hojas donde
# aparecen. El auditor las coteja con el Manual del IAASB vigente (edición en español) antes de emitir.
MARCA = "†"
NOTA = "00_Nota_metodologica"
_RE_VERIFICAR = re.compile(r"\s*(?:\(VERIFICAR\)|[—-]\s*VERIFICAR)")
_RE_NORMA = re.compile(r"(?:NIA|NIGC|NIC|NIIF|IESBA|Sección)\s(?:[^;()«»]|\(Revisad[^)]*\)|(?<=\s)[a-z]\))*")
COLS_NOTA = [["Marca", "t"], ["Cita por cotejar", "t"], ["Hojas donde aparece", "t"], ["Qué hacer", "t"]]
NOTA_NORMA = "Cotejar el párrafo con el Manual del IAASB vigente (edición en español) antes de emitir el informe."
NOTA_POLITICA = "Confirmar que es la política vigente de la firma (porcentaje, factor o plazo)."
NOTA_COTEJADAS = [
    ("NIA 300 párr. 8", "Estrategia global: características del encargo, objetivos de información, factores significativos, "
                        "actividades preliminares y recursos. Se usa con sus literales a) a e).", "Revisada"),
    ("NIA 315 (Revisada 2019) párr. 12 l)", "Definición de riesgo significativo.", "Revisada"),
    ("NIA 315 (Revisada 2019) párr. 25", "Sistema de información y comunicación: se usa solo para ese componente (hoja 27); "
                                         "el hallazgo del entendimiento cita el párr. 19.", "Corregida"),
    ("NIA 240 párr. 30", "No se cita en el papel; las respuestas globales citan el párr. 29 (con †: la NIA 240 revisada cambia la "
                         "numeración).", "Revisada"),
]


def _sin_verificar(t):
    return _RE_VERIFICAR.sub(f" {MARCA}", t) if isinstance(t, str) and "VERIFICAR" in t else t


def _cita(texto: str) -> str:
    pre = texto[:texto.find("VERIFICAR")]
    normas = _RE_NORMA.findall(pre)
    return (normas[-1].strip(" —-") if normas else "Política de la firma")


def _nota_metodologica(hojas_: list) -> list:
    citas: dict[str, list] = {}
    for h in hojas_:
        for f in h["rows"]:
            for j, c in enumerate(f):
                t = c.get("v") if isinstance(c, dict) else c
                if isinstance(t, str) and "VERIFICAR" in t:
                    for trozo in re.split(r"(?<=VERIFICAR\))|(?<=VERIFICAR)", t):
                        if "VERIFICAR" in trozo:
                            citas.setdefault(_cita(trozo), [])
                            if h["name"] not in citas[_cita(trozo)]:
                                citas[_cita(trozo)].append(h["name"])
                if isinstance(c, dict):
                    f[j] = {**c, "v": _sin_verificar(c.get("v")), **({"f": _sin_verificar(c["f"])} if c.get("f") else {})}
                else:
                    f[j] = _sin_verificar(c)
        h["explica"] = {k: _sin_verificar(v) for k, v in (h.get("explica") or {}).items()}
    filas = [[MARCA, cita, ", ".join(hs), NOTA_POLITICA if cita == "Política de la firma" else NOTA_NORMA]
             for cita, hs in sorted(citas.items())]
    filas += [["Revisión de control de calidad", f"{c} · {det}", "", est] for c, det, est in NOTA_COTEJADAS]
    nota = hoja(NOTA, _ETQ[NOTA], COLS_NOTA, filas,
                guia=("Citas de párrafos de las NIA y porcentajes de política de la firma marcados con «†» en las hojas: se cotejan "
                      "con el texto oficial vigente antes de emitir. Las últimas filas muestran las citas que la revisión de "
                      "control de calidad pidió cotejar y su resultado."))
    return hojas_[:-1] + [nota, hojas_[-1]]


OBS_VARIACION = "Variación superior al umbral: revisar el rubro y su documentación de respaldo."

COLS_SUMARIA = [["Ref. PT", "t"], ["Código", "t"], ["Cuenta", "t"], ["Nivel", "i"], ["Detalle", "t"],
                ["Saldo al cierre anterior", "n"], ["Saldo al corte", "n"], ["Ajustes del auditor", "n"], ["Saldo ajustado", "n"],
                ["Variación", "n"], ["Variación %", "p"], ["Nota del año anterior", "t"], ["Marca", "t"]]
TXT_TOTAL_SUMARIA = "Total de las cuentas de detalle"
TXT_CUADRE_SUMARIA = "Cuadre: rubro − cuentas de detalle (debe dar 0)"


COLS_NOTAS_DET = [["Nota", "t"], ["Código", "t"], ["Cuenta", "t"], ["Nivel", "i"], ["Saldo al cierre anterior", "n"],
                  ["Saldo al corte", "n"], ["Variación", "n"], ["Variación %", "p"], ["Marca", "t"]]
COLS_COMPOSICION = [["Nota", "t"], ["Concepto", "t"], ["Tipo", "t"], ["Importe auditado", "n"], ["Control", "t"]]
TXT_TOTAL_NOTA = "Total de la nota según el balance"
TXT_AUDITADO_NOTA = "Saldo auditado según la nota (hoja 15)"
TXT_DIF_NOTA = "Diferencia: balance anterior − nota auditada (NIA 510)"
TXT_SUMA_COMP = "Suma de las líneas de saldo"
TXT_TOTAL_COMP = "Total que presenta la nota"
TXT_DIF_COMP = "Diferencia: suma de las líneas − saldo auditado de la nota"
TXT_SIN_NOTA = "Rubros del balance sin nota del año anterior"


def _cubre(codigo: str, pref: str) -> bool:
    return codigo == pref or _debajo(codigo, pref) or _debajo(pref, codigo)


def _sin_nota(cuentas: list, notas: list) -> list:
    """Rubros del balance (activo, pasivo, patrimonio) que ninguna nota cubre; vacío si no se cargaron notas."""
    if not notas:
        return []
    return [x for x in cuentas if x["sec"] in ("Activo", "Pasivo", "Patrimonio") and _es_rubro(x)
            and not any(_cubre(x["codigo"], pf) for n in notas for pf in n["pref"])]


def _notas_detalle(notas: list, cu: list, sin_nota: list, umbral: float) -> tuple[list, list]:
    """Detalle comparativo de cada nota: sus cuentas y subcuentas del balance (anterior y corte, por fórmula a 08), el total
    de la nota según el balance y la conciliación con el saldo auditado de la nota (NIA 510). Al final, los rubros del
    balance que ninguna nota cubre."""
    filas, est = [], []
    idx = {x["codigo"]: i for i, x in enumerate(cu)}
    u = _par("umbralVarPct")

    def fila_cuenta(etq, x, r, marca_fija=None):
        r8 = FILA0 + idx[x["codigo"]]
        return [etq, x["codigo"], x["cuenta"], fx(f"{H8}C{r8}", x["nivel"]), fx(f"{H8}G{r8}", n2(x["ant"])),
                fx(f"{H8}H{r8}", n2(x["act"])), fx(f"F{r}-E{r}", n2(x["act"] - x["ant"])),
                fx(f'IF(E{r}=0,"",G{r}/ABS(E{r}))', None if x["ant"] == 0 else (x["act"] - x["ant"]) / abs(x["ant"])),
                marca_fija if marca_fija else fx(f'IF(E{r}=0,IF(F{r}<>0,"Nueva",""),IF(F{r}=0,"Baja",IF(ABS(G{r}/E{r})>={u}/100,'
                                                 f'"Supera el umbral","")))', _marca(x["ant"], x["act"], umbral))]
    for k, n in enumerate(notas):
        etq = f"Nota {n['nota']}"
        filas.append([etq, None, n["titulo"], None, None, None, None, None, None])
        est.append({"tipo": "titulo"})
        tops = []
        for pf in n["pref"]:
            base = next((x for x in cu if x["codigo"] == pf), None)
            cuentas = [x for x in cu if x["codigo"] == pf or _debajo(x["codigo"], pf)]
            for x in cuentas:
                r = FILA0 + len(filas)
                if x is base:
                    tops.append((r, x))
                filas.append(fila_cuenta(etq, x, r))
                est.append({"sangria": 1 + x["nivel"] - (base["nivel"] if base else x["nivel"]), "col": "Cuenta"})
            if base is None:
                filas.append([etq, pf, "(código de la nota que no está en el balance)", None, None, None, None, None, None])
                est.append({"tipo": "control"})
        rt = FILA0 + len(filas)
        ta, tc = sum(x["ant"] for _, x in tops), sum(x["act"] for _, x in tops)
        suma = lambda c: "+".join(f"{c}{r}" for r, _ in tops) or "0"  # noqa: E731
        filas.append([etq, None, TXT_TOTAL_NOTA, None, fx(suma("E"), n2(ta)), fx(suma("F"), n2(tc)), fx(f"F{rt}-E{rt}", n2(tc - ta)),
                      fx(f'IF(E{rt}=0,"",G{rt}/ABS(E{rt}))', None if ta == 0 else (tc - ta) / abs(ta)), None])
        est.append({"tipo": "total"})
        ra = rt + 1
        filas.append([etq, None, TXT_AUDITADO_NOTA, None, fx(f"{N15}D{FILA0 + k}", n2(n["auditado"])), None, None, None, None])
        est.append({"tipo": "control"})
        rd = ra + 1
        filas.append([etq, None, TXT_DIF_NOTA, None, fx(f"E{rt}-E{ra}", n2(ta - n["auditado"])), None, None, None,
                      fx(f'IF(ABS(E{rd})<0.005,"Coincide","Revisar (NIA 510)")',
                         "Coincide" if abs(ta - n["auditado"]) < 0.005 else "Revisar (NIA 510)")])
        est.append({"tipo": "control"})
    if sin_nota:
        filas.append([None, None, TXT_SIN_NOTA, None, None, None, None, None, None])
        est.append({"tipo": "titulo"})
        for x in sin_nota:
            filas.append(fila_cuenta(None, x, FILA0 + len(filas), "Sin nota"))
            est.append({"sangria": 1, "col": "Cuenta"})
    return filas, est


def _composicion(notas: list, det: list) -> tuple[list, list]:
    """Composición auditada de cada nota (RQ-009): sus líneas con el importe del informe, la suma de las líneas de saldo,
    el total que presenta la nota y la diferencia con el saldo auditado de la hoja 15."""
    filas, est = [], []
    orden = list(dict.fromkeys([n["nota"] for n in notas] + [x["nota"] for x in det]))
    fila15 = {n["nota"]: (FILA0 + k, n) for k, n in enumerate(notas)}
    for nota in orden:
        ls = [x for x in det if x["nota"] == nota]
        if not ls:
            continue
        titulo = fila15[nota][1]["titulo"] if nota in fila15 else "(nota sin fila en la hoja 15)"
        filas.append([f"Nota {nota}", titulo, None, None, None])
        est.append({"tipo": "titulo"})
        a = FILA0 + len(filas)
        for x in ls:
            filas.append([nota, x["concepto"], x["tipo"], n2(x["importe"]), None])
            est.append({"sangria": 1 if x["tipo"] == "Movimiento" else 0, "col": "Concepto"} if x["tipo"] != "Total" else {"tipo": "total"})
        b = FILA0 + len(filas) - 1
        suma = sum(x["importe"] for x in ls if x["tipo"] == "Saldo")
        rs = b + 1
        filas.append([f"Nota {nota}", TXT_SUMA_COMP, None, fx(f'SUMIFS(D{a}:D{b},C{a}:C{b},"Saldo")', n2(suma)), None])
        est.append({"tipo": "control"})
        totales = [x["importe"] for x in ls if x["tipo"] == "Total"]
        if totales:
            rt = FILA0 + len(filas)
            filas.append([f"Nota {nota}", TXT_TOTAL_COMP, None, fx(f'SUMIFS(D{a}:D{b},C{a}:C{b},"Total")', n2(sum(totales))),
                          fx(f'IF(ABS(D{rt}-D{rs})<0.005,"Coincide","Revisar")',
                             "Coincide" if abs(sum(totales) - suma) < 0.005 else "Revisar")])
            est.append({"tipo": "control"})
        if nota in fila15:
            r15, n = fila15[nota]
            ra = FILA0 + len(filas)
            filas.append([f"Nota {nota}", TXT_AUDITADO_NOTA, None, fx(f"{N15}D{r15}", n2(n["auditado"])), None])
            est.append({"tipo": "control"})
            rd = ra + 1
            filas.append([f"Nota {nota}", TXT_DIF_COMP, None, fx(f"D{rs}-D{ra}", n2(suma - n["auditado"])),
                          fx(f'IF(ABS(D{rd})<0.005,"Coincide","Revisar")', "Coincide" if abs(suma - n["auditado"]) < 0.005 else "Revisar")])
            est.append({"tipo": "control"})
    return filas, est


def _riesgos_de(x: dict, riesgos: list) -> list[int]:
    """Posibles riesgos de la hoja 13 que recaen en la cuenta: los de su código (variaciones) o de su misma área.
    Los de empresa en funcionamiento (NIA 570) y los que afectan a todas las áreas son de toda la entidad y no marcan cuentas."""
    area_x = _area(x["cuenta"], x["sec"])
    out = []
    for i, rk in enumerate(riesgos):
        if rk["norma"] == "NIA 570":
            continue
        rub = rk["rubro"]
        if rub.split(" ")[0] == x["codigo"] or (area_x and _area(rub) == area_x):
            out.append(i)
    return out


ASEVERACIONES_SECCION = {"Activo": "Existencia; valuación; derechos", "Pasivo": "Integridad; valuación; obligaciones",
                         "Patrimonio": "Integridad; presentación", "Ingresos": "Ocurrencia; corte; integridad",
                         "Costos": "Ocurrencia; integridad; clasificación", "Gastos": "Ocurrencia; integridad; clasificación"}
ASEVERACIONES_AREA = {
    "Caja y bancos": "Existencia; derechos; integridad", "Inversiones": "Existencia; valuación; derechos",
    "Cuentas por cobrar": "Existencia; valuación; derechos", "Inventarios": "Existencia; valuación; derechos",
    "Arrendamientos": "Integridad; valuación; presentación", "Propiedades de inversión": "Existencia; valuación",
    "Propiedad, planta y equipo": "Existencia; valuación; derechos", "Activos intangibles": "Existencia; valuación",
    "Activos biológicos": "Existencia; valuación", "Seguros": "Integridad; presentación",
    "Impuestos": "Integridad; exactitud; valuación", "Beneficios a empleados y nómina": "Ocurrencia; integridad; valuación",
    "Proveedores y cuentas por pagar": "Integridad; obligaciones; corte",
    "Préstamos y obligaciones financieras": "Integridad; obligaciones; valuación; presentación",
    "Provisiones y contingencias": "Integridad; valuación; presentación", "Patrimonio": "Integridad; presentación",
    "Costos y gastos": "Ocurrencia; integridad; corte; clasificación", "Ingresos": "Ocurrencia; corte; exactitud",
    "Asientos de diario": "Todas",
}
_OP_CONF = "Envío al cierre (o en la visita preliminar con pruebas de actualización); respuestas antes del informe"
CONFIRMACIONES = {
    "Caja y bancos": ("NIA 505", "Confirmar con cada banco los saldos, préstamos, garantías y firmas autorizadas al corte "
                      "(confirmación externa enviada y recibida por el auditor).", "Respuestas de los bancos y conciliaciones al corte.",
                      "Existencia; derechos; integridad", _OP_CONF),
    "Cuentas por cobrar": ("NIA 505", "Confirmar los saldos de los clientes seleccionados (confirmación positiva) y aplicar "
                           "procedimientos alternativos a las no respuestas (cobros posteriores).",
                           "Respuestas de clientes, cobros posteriores al corte y antigüedad de la cartera.", "Existencia; derechos",
                           _OP_CONF),
    "Préstamos y obligaciones financieras": ("NIA 505", "Confirmar con los acreedores financieros el saldo, las tasas, los vencimientos "
                                             "y las garantías.", "Respuestas de los acreedores y tablas de amortización.",
                                             "Integridad; obligaciones; presentación", _OP_CONF),
    "Proveedores y cuentas por pagar": ("NIA 505", "Confirmar los saldos de los proveedores principales, incluidos los de saldo cero o "
                                        "bajo (búsqueda de pasivos no registrados).",
                                        "Respuestas de los proveedores y pagos posteriores al corte.", "Integridad; obligaciones", _OP_CONF),
    "Partes relacionadas": ("NIA 505; NIA 550", "Confirmar los saldos y las transacciones con las partes relacionadas.",
                            "Respuestas de las partes relacionadas y contratos.", "Existencia; integridad; presentación", _OP_CONF),
    "Inventarios": ("NIA 501", "Presenciar el recuento físico de los inventarios al cierre (o en una fecha cercana con pruebas de "
                    "actualización) y probar el corte (NIA 501 párr. 4).", "Instrucciones del recuento, hojas de conteo y pruebas "
                    "del auditor.", "Existencia; condición", "Visita final: recuento físico al cierre o en una fecha cercana"),
}


def _aser_riesgo(x: dict, cu: list) -> str:
    """A13: aseveraciones del riesgo de la hoja 13 según su tipo, su área o la sección de la cuenta (no genéricas)."""
    if x["cod"] in ASEVERACIONES_RIESGO:
        return ASEVERACIONES_RIESGO[x["cod"]]
    if x["cod"] == "variacion":
        sec = next((c["sec"] for c in cu if c["codigo"] == x.get("cuenta")), "")
        return ASEVERACIONES_SECCION.get(sec, "Existencia; integridad; valuación")
    if x["cod"] in ("anterior_otro", "anterior_no", "inicial"):
        return "Existencia; integridad; valuación (saldos de apertura)"
    if x.get("eeff") or x["cod"] == "cuestionario":
        return "Todas" if x.get("eeff") else ASEVERACIONES_AREA.get(_area(x["rubro"]), "Todas")
    return ASEVERACIONES_AREA.get(_area(x["rubro"]), "Existencia; integridad; valuación")


ASEVERACIONES_RIESGO = {"presuncion": "Ocurrencia; corte", "elusion": "Todas", "cartera": "Valuación", "rotCartera": "Valuación",
                        "inventario": "Existencia; valuación", "rotInventario": "Existencia; valuación"}
EVIDENCIA_RIESGO = {
    "NIA 240": "Reporte de asientos de diario del período, notas de crédito posteriores al cierre y detalle de ventas de la última semana.",
    "NIA 570": "Presupuestos y flujos de caja proyectados, actas de la junta y detalle del financiamiento disponible.",
    "NIA 540": "Antigüedad de la cartera al corte, cobros posteriores y cálculo de la pérdida crediticia esperada.",
    "NIA 501": "Kárdex valorizado por ítem, rotación y actas de la toma física.",
}
EVIDENCIA_DEFECTO = "Mayor analítico de la cuenta al corte, análisis de la variación y soportes de las partidas seleccionadas."
EVIDENCIA_CARTA = "Documentación del proceso y evidencia de la ejecución del control (solicitud PBC del área)."
# NIA 330: la respuesta a un riesgo significativo incluye pruebas de detalle (no bastan analíticos ni indagación).
EVIDENCIA_SIGNIFICATIVO = "Pruebas de detalle del saldo y de las transacciones del riesgo significativo (NIA 330). "
RESPUESTA_CUENTA = ("Pruebas sustantivas de detalle del saldo al corte (NIA 330 párr. 18): conciliar el mayor, seleccionar partidas "
                    "y obtener evidencia de existencia, valuación y presentación.")
# Respuesta sustantiva por sección: en los pasivos lo crítico es la integridad (pasivos no registrados); en resultados, la
# ocurrencia y el corte (NIA 330).
RESPUESTA_SECCION = {
    "Activo": RESPUESTA_CUENTA,
    "Pasivo": ("Pruebas sustantivas de detalle del saldo al corte (NIA 330 párr. 18): conciliar el mayor, confirmar o cotejar con "
               "documentos del acreedor y buscar pasivos no registrados (pagos posteriores al corte): integridad y valuación."),
    "Patrimonio": ("Pruebas sustantivas del saldo (NIA 330 párr. 18): conciliar el mayor con las actas y la escritura, verificar los "
                   "movimientos del año y su presentación."),
    "Ingresos": ("Pruebas sustantivas de detalle (NIA 330 párr. 18): seleccionar transacciones del período, cotejar con documentos "
                 "de soporte y probar el corte de las últimas y primeras operaciones: ocurrencia, exactitud y corte."),
    "Costos": ("Pruebas sustantivas de detalle (NIA 330 párr. 18): cotejar partidas con documentos de soporte y probar el corte: "
               "ocurrencia, exactitud, corte y clasificación."),
    "Gastos": ("Pruebas sustantivas de detalle (NIA 330 párr. 18): cotejar partidas con documentos de soporte y probar el corte: "
               "ocurrencia, exactitud, corte y clasificación."),
}
PENDIENTE_SOCIO, PENDIENTE_GERENTE = "[PENDIENTE] socio del encargo", "[PENDIENTE] gerente del encargo"
NO_APLICA_SIN_MAT = "Pendiente: sin materialidad (NIA 320)"
# Procedimientos de todo encargo (no dependen de un riesgo identificado).
# La hoja 17 muestra las anomalías más severas hasta este tope; si hay más, el problema ANOMALIAS_CORTADAS lo avisa.
MAX_ANOMALIAS = 20
PROC_ENCARGO = [
    ("Hechos posteriores", "NIA 560", "Revisar hechos posteriores al cierre hasta la fecha del informe: actas, estados posteriores "
     "y consulta a la administración.", "Actas de junta, estados financieros posteriores y confirmación de la administración.",
     "Integridad; presentación"),
    ("Partes relacionadas", "NIA 550", "Identificar las partes relacionadas y sus transacciones; evaluar autorización, condiciones "
     "y revelación.", "Listado de partes relacionadas, contratos y saldos entre compañías.", "Integridad; presentación"),
    ("Litigios y reclamos", "NIA 501", "Enviar cartas a los abogados y evaluar las provisiones y revelaciones de contingencias.",
     "Cartas de abogados y listado de juicios y reclamos.", "Integridad; valuación"),
    ("Empresa en funcionamiento", "NIA 570", "Evaluar la hipótesis de empresa en funcionamiento para al menos doce meses desde el cierre.",
     "Presupuestos, flujos proyectados y financiamiento disponible.", "Presentación y revelación"),
    ("Impuestos", "NIA 250", "Revisar la conciliación tributaria, el impuesto corriente y diferido y el cumplimiento de las "
     "obligaciones fiscales.", "Conciliación tributaria y declaraciones del período.", "Valuación; integridad"),
    ("Manifestaciones escritas", "NIA 580", "Obtener la carta de representación de la administración a la fecha del informe, "
     "con las manifestaciones generales y las específicas de los riesgos del encargo (hoja 44).",
     "Carta de representación firmada por la administración.", "Todas"),
    ("Cierre de los estados financieros", "NIA 330", "Conciliar los estados financieros y sus notas con los registros contables y "
     "examinar los asientos de cierre y los ajustes significativos (NIA 330 párr. 20 — VERIFICAR).",
     "Estados financieros finales, notas, mayor general y asientos de cierre.", "Presentación; integridad"),
    ("Otra información", "NIA 720", "Leer el informe anual de la administración y la otra información y compararla con los estados "
     "financieros auditados (NIA 720 — VERIFICAR).", "Informe anual de la administración a la junta y demás documentos que "
     "acompañan a los estados financieros.", "Presentación"),
    ("Leyes y reglamentos", "NIA 250", "Indagar sobre el cumplimiento de las leyes y reglamentos, inspeccionar la correspondencia "
     "con los reguladores y evaluar las provisiones y revelaciones (hoja 39).", "Correspondencia con el SRI, la Superintendencia, el "
     "IESS y demás reguladores; actas y cartas de abogados.", "Integridad; presentación"),
]
PROC_APERTURA = ("Obtener evidencia propia de los saldos de apertura en la visita preliminar: revisar los papeles del auditor anterior "
                 "o aplicar procedimientos sustantivos a los saldos iniciales y verificar la uniformidad de las políticas (NIA 510 "
                 "párr. 6 y 7 — VERIFICAR).")
EVID_APERTURA = "Papeles del auditor anterior, balance inicial, cobros y pagos posteriores y políticas contables del año anterior."
PROC_IMPREVISIBLE = ("Elemento de imprevisibilidad: prueba sustantiva sin aviso previo sobre una cuenta que no se revisa por su "
                     "importe o, si todas se revisan, sobre una de las de menor importe (NIA 240 párr. 29 c) — VERIFICAR); rota "
                     "cada año.")
OPORTUNIDAD_ENCARGO = "Visita final y hasta la fecha del informe"


def _es_rubro(x: dict) -> bool:
    """Rubro de la sumaria: cuenta de nivel 3, o de nivel superior sin subcuentas (la jerarquía se acaba antes)."""
    return x["nivel"] == 3 or (x["nivel"] < 3 and x["detalle"] == "Sí")


def _marca(a: float, b: float, umbral: float) -> str:
    if abs(a) < 0.005:
        return "Nueva" if abs(b) >= 0.005 else ""
    if abs(b) < 0.005:
        return "Baja"
    return "Supera el umbral" if abs((b - a) / a) >= umbral / 100 else ""


def _fechas_estados(d: dict) -> tuple[dict, str]:
    """Rótulos de los períodos de los estados detallados: el balance anterior es el cierre del año anterior; en la
    preliminar, los resultados anteriores son el mismo corte del año anterior (o el prorrateo de diciembre)."""
    c = date.fromisoformat(d["corte"])
    cierre = date(c.year - 1, 12, 31)
    f = lambda x: x.strftime("%d/%m/%Y")  # noqa: E731
    if d["tipo"] != "Preliminar":
        eri = f(cierre)
    elif d["hayEri"]:
        eri = f(date(c.year - 1, c.month, c.day) if not (c.month == 2 and c.day == 29) else date(c.year - 1, 2, 28))
    else:
        eri = f"{f(cierre)} × {d['meses']}/12"
    return {"esf": f(cierre), "eri": eri}, f(c)


def _cols_detalle(f_ant: str, f_act: str) -> list:
    return [["Código", "t"], ["Cuenta", "t"], ["Nivel", "i"], ["Detalle", "t"], [f"Anterior ({f_ant})", "n"],
            [f"Actual ({f_act})", "n"], ["Variación", "n"], ["Variación %", "p"], ["Peso vertical", "p"]]


def _explica_detalle(f_ant: str, f_act: str, base: str) -> dict:
    return {
        "Nivel": "Trae de la hoja 08 el nivel de la cuenta en la jerarquía de los códigos (1 es la cuenta de la sección).",
        "Detalle": "Trae de la hoja 08 si es cuenta de detalle (no tiene subcuentas): solo esas se suman en el total.",
        f"Anterior ({f_ant})": ("Trae de la hoja 08 el saldo anterior de la cuenta; en el total, suma solo las cuentas de detalle y "
                                "en la diferencia la compara con el total de la sección de la hoja 07."),
        f"Actual ({f_act})": ("Trae de la hoja 08 el saldo al corte; en el total, suma solo las cuentas de detalle y en la "
                              "diferencia la compara con la hoja 07 (debe dar 0)."),
        "Variación": "Resta el saldo anterior del saldo actual de la misma cuenta (o del total de la sección).",
        "Variación %": "Divide la variación para el saldo anterior (en blanco si el anterior es cero).",
        "Peso vertical": f"Trae de la hoja 08 el peso del saldo actual sobre el {base}.",
    }


TXT_TOTAL_SECCION = "Total de las cuentas de detalle"
TXT_CUADRE_SECCION = "Diferencia con el total de la sección (hoja 07)"
TXT_RESULTADO_ERI = "Resultado del período (ingresos − costos − gastos)"
TXT_RESULTADO_ESF = "Resultado del período (según el balance)"
TXT_PASIVO_PATRIMONIO = "Pasivo + patrimonio + resultado del período"
TXT_DIF_ACTIVO = "Diferencia con el activo (debe ser 0)"


# Rango de práctica habitual de cada porcentaje (no lo prescribe la NIA 320: son ejemplos de la profesión; la firma los
# confirma en su política). Fuera del rango no es un error: obliga a documentar el porqué (NIA 320 párr. 14).
RANGO_PRACTICA = {"Ingresos": (0.5, 2), "Activos totales": (0.5, 2), "Patrimonio": (1, 5), "Gastos totales": (0.5, 2),
                  UAI: (3, 10), "desempeno": (50, 75), "trivial": (3, 5)}
SUSTENTO_PCT = "Política de la firma; NIA 320 párr. A4 y A7–A8 (ejemplos, no porcentajes prescritos) — VERIFICAR"
DENTRO, FUERA = "Dentro del rango", "Fuera del rango: documentar el porqué"


def _rango(k: str, celda: str, pct) -> list:
    """[rótulo del rango, fórmula ¿dentro del rango?] del porcentaje ``celda``."""
    lo, hi = RANGO_PRACTICA[k]
    rot = f"{_num(lo, 1 if lo % 1 else 0)} %–{_num(hi, 0)} % · práctica habitual (VERIFICAR)"
    v = "" if pct in (None, "") else DENTRO if lo <= float(pct) <= hi else FUERA
    return [rot, fx(f'IF({celda}="","",IF(AND({celda}>={lo},{celda}<={hi}),"{DENTRO}","{FUERA}"))', v)]


def _txt_base(d: dict) -> str:
    """Base elegida y su período (hojas 11 y 23); D9: dice si se anualizó."""
    anual = ANUALIZADA + str(d["meses"]) if d["anualiza"] and d["base"] in BASES_FLUJO else ""
    return f"Base elegida: {d['base']} ({d['periodo'].lower()}{anual}); NIA 320 párr. 10"


def _justif_cifras(d: dict, mt: dict, propia) -> str:
    """Justificación de la base con sus cifras (artefacto): la del auditor si la escribió; si no, la automática."""
    if propia not in (None, ""):
        return str(propia)
    base, pct = d["base"], d["pctBase"][d["base"]]
    cif = (": sin materialidad (base cero o negativa). " if not mt["global"] else
           f" × {_num(pct)} % = US$ {_num(mt['global'])}: ")
    return f"Base {base} de US$ {_num(mt['base'])}{cif}{JUSTIFICACION[base]}"


ORIGEN_INFORME = "Informe del año anterior (RQ-005)"
ORIGEN_PARAMETROS = "Parámetros del encargo (hoja 02)"
ORIGEN_PENDIENTE = "Sin soporte documental"
ORIGEN_RUC = "Certificado de RUC (RQ-008)"
PENDIENTE = "[PENDIENTE]"
MARCO_AUDITORIA = "Normas Internacionales de Auditoría (NIA)"
# Identificación mínima del encargo (artefacto: «Identificación del encargo»): concepto y cómo se obtiene. Lo que no tiene
# soporte queda [PENDIENTE]: no se completa por inferencia (regla de cero invención).
IDENT_INFORME = (("Entidad auditada", ("entidad",)), ("RUC", ("ruc",)), ("Actividad", ("actividad", "objetosocial")),
                 ("País y moneda funcional", ("pais", "moneda")))
IDENT_PARAM = (("Período auditado (fecha de corte)", "corte"), ("Tipo de revisión", "tipoRevision"),
               ("Marco de información financiera", "marco"), ("Edición del marco", "edicionMarco"),
               ("Encargo inicial (primer año)", "encargoInicial"), ("Socio del encargo", "socio"), ("Gerente del encargo", "gerente"))
TXT_ENTENDIMIENTO_PEND = ("Documente el entendimiento de la entidad y su entorno: modelo de negocio, estructura y propiedad, partes "
                          "relacionadas, sistema de información y marco normativo (NIA 315 párr. 19).")


def _perfil(informe: list, d: dict, pv, ruc: dict | None = None) -> tuple[list, list, dict]:
    """Hoja 14 (artefacto: «Perfil del encargo»): identificación del encargo, entendimiento de la entidad y su entorno,
    contexto y asuntos del informe anterior. La identificación prioriza el certificado de RUC (RQ-008) cuando está, por ser
    la fuente oficial del SRI; si no hay RUC, cae al informe o queda [PENDIENTE]. Devuelve las filas, sus estilos y la fila
    de cada dato del informe."""
    ruc = ruc or {}
    filas, estilos, fila = [], [], {}

    def titulo(txt):
        filas.append([txt, None, None, None, None, None, None])
        estilos.append({"tipo": "titulo"})

    def de_informe(j, x):
        fila[j] = FILA0 + len(filas)
        filas.append([x["tipo"], x["concepto"], x["detalle"], n2(x["importe"]), x["fuente"],
                      x["enfoque"] or EFECTO_INFORME[x["tipo"]], ORIGEN_INFORME])
        estilos.append(None)

    def de_ruc(concepto, valor):
        filas.append(["Identificación", concepto, str(valor).strip() or PENDIENTE, None, "Certificado de RUC (SRI)",
                      EFECTO_INFORME["Identificación"], ORIGEN_RUC])
        estilos.append(None)

    usados = set()
    titulo("Identificación del encargo")
    # El RUC es la fuente oficial de entidad, RUC y actividad: si lo trae, manda sobre el informe.
    _ruc_ident = {"Entidad auditada": ruc.get("razon_social"), "RUC": ruc.get("ruc"),
                  "Actividad": ruc.get("actividad_principal") or ruc.get("actividades")}
    for concepto, claves in IDENT_INFORME:
        j = next((j for j, x in enumerate(informe) if j not in usados and x["tipo"] == "Identificación"
                  and any(k in norm(x["concepto"]) for k in claves)), None)
        if str(_ruc_ident.get(concepto, "") or "").strip():
            if j is not None:          # el RUC manda: marca la fila equivalente del informe para no duplicarla
                usados.add(j)
            de_ruc(concepto, _ruc_ident[concepto])
            continue
        if j is None:
            filas.append(["Identificación", concepto, PENDIENTE, None, "No se completa por inferencia",
                          EFECTO_INFORME["Identificación"], ORIGEN_PENDIENTE])
            estilos.append(None)
        else:
            usados.add(j)
            de_informe(j, informe[j])
    j = next((j for j, x in enumerate(informe) if x["tipo"] == "Opinión"), None)
    if j is None:
        filas.append(["Opinión", "Opinión del año anterior", PENDIENTE, None, "No se completa por inferencia",
                      EFECTO_INFORME["Opinión"], ORIGEN_PENDIENTE])
        estilos.append(None)
    else:
        usados.add(j)
        de_informe(j, informe[j])
    for concepto, k in IDENT_PARAM:
        v = {"corte": d["corte"], "tipoRevision": d["tipo"], "marco": d["marco"], "edicionMarco": d["edicion"]}.get(k, d["sino"].get(k) if k in d["sino"] else pv(k))
        filas.append(["Identificación", concepto, fx(f'IF({_par(k)}="","{PENDIENTE}",{_par(k)})', PENDIENTE if v in (None, "") else v),
                      None, "Hoja 02 · Parámetros", EFECTO_INFORME["Identificación"], ORIGEN_PARAMETROS])
        estilos.append(None)
    filas.append(["Identificación", "Marco de auditoría", MARCO_AUDITORIA, None, "Política de la firma",
                  EFECTO_INFORME["Identificación"], ORIGEN_PARAMETROS])
    estilos.append(None)
    # Datos adicionales del certificado de RUC (NIA 315): solo las filas que el certificado trae.
    for concepto, clave in (("Representante legal", "representante_legal"),
                            ("Obligado a llevar contabilidad", "obligado_contabilidad"),
                            ("Tipo de contribuyente", "tipo_contribuyente"),
                            ("Agente de retención", "agente_retencion"),
                            ("Contribuyente especial", "contribuyente_especial"),
                            ("Establecimientos (abiertos/cerrados)", "establecimientos"),
                            ("Jurisdicción / domicilio tributario", "jurisdiccion"),
                            ("Inicio de actividades", "inicio_actividades"),
                            ("Obligaciones tributarias", "obligaciones_tributarias")):
        if str(ruc.get(clave, "") or "").strip():
            de_ruc(concepto, ruc.get(clave))
    for j, x in enumerate(informe):              # otros datos de identificación del informe
        if x["tipo"] == "Identificación" and j not in usados:
            usados.add(j)
            de_informe(j, x)
    titulo("Entendimiento de la entidad y su entorno (NIA 315)")
    ent = [(j, x) for j, x in enumerate(informe) if x["tipo"] == "Entendimiento"]
    for j, x in ent:
        usados.add(j)
        de_informe(j, x)
    if not ent:
        filas.append(["Entendimiento", "Entendimiento de la entidad", PENDIENTE, None, "No se completa por inferencia",
                      TXT_ENTENDIMIENTO_PEND, ORIGEN_PENDIENTE])
        estilos.append(None)
    ctx = [(j, x) for j, x in enumerate(informe) if x["tipo"] == "Contexto"]
    if ctx:
        titulo("Contexto de la entidad")
        for j, x in ctx:
            usados.add(j)
            de_informe(j, x)
    resto = [(j, x) for j, x in enumerate(informe) if j not in usados]
    if resto:
        titulo("Asuntos del informe del año anterior")
        for j, x in resto:
            de_informe(j, x)
    return filas, estilos, fila


def _estado_detalle(cu: list, secs: tuple, s7: dict, prelim: bool, hay_eri: bool, meses: int,
                    f_hay_eri: str) -> tuple[list, list]:
    """Estado completo (artefacto: renderStatement): todas las cuentas de las secciones en jerarquía, con la cuenta de nivel 1
    destacada, sangría por nivel y agrupación de Excel por nivel (los botones del esquema eligen el detalle). Saldos por
    fórmula a 08_Horizontal; por sección, el total de las cuentas de detalle y su diferencia con la hoja 07 (debe ser 0)."""
    filas, estilos = [], []
    idx = {x["codigo"]: FILA0 + i for i, x in enumerate(cu)}
    totales = {}
    for sec in secs:
        bloque = [x for x in cu if x["sec"] == sec]
        if not bloque:
            continue
        a = FILA0 + len(filas)
        for x in bloque:
            r, r8 = FILA0 + len(filas), idx[x["codigo"]]
            filas.append([x["codigo"], x["cuenta"], fx(f"{H8}C{r8}", x["nivel"]), fx(f"{H8}D{r8}", x["detalle"]),
                          fx(f"{H8}G{r8}", n2(x["ant"])), fx(f"{H8}H{r8}", n2(x["act"])), fx(f"F{r}-E{r}", n2(x["act"] - x["ant"])),
                          fx(f'IF(E{r}=0,"",G{r}/ABS(E{r}))', None if x["ant"] == 0 else (x["act"] - x["ant"]) / abs(x["ant"])),
                          fx(f'IF({H8}K{r8}="","",{H8}K{r8})', x["vert"])])
            niv = int(x["nivel"] or 1)
            estilos.append({"tipo": "titulo", "grupo": 0} if niv <= 1 else
                           {"sangria": niv - 1, "col": "Cuenta", "grupo": min(7, niv - 1)})
        b = FILA0 + len(filas) - 1
        det = [x for x in bloque if x["detalle"] == "Sí"]
        ta, tc = sum(x["ant"] for x in det), sum(x["act"] for x in det)
        rt = b + 1
        sif = lambda c: f'SUMIFS({c}{a}:{c}{b},$D${a}:$D${b},"Sí")'  # noqa: E731
        filas.append([None, f"{TXT_TOTAL_SECCION}: {sec.lower()}", None, None, fx(sif("E"), n2(ta)), fx(sif("F"), n2(tc)),
                      fx(f"F{rt}-E{rt}", n2(tc - ta)), fx(f'IF(E{rt}=0,"",G{rt}/ABS(E{rt}))', None if ta == 0 else (tc - ta) / abs(ta)),
                      None])
        estilos.append({"tipo": "total"})
        totales[sec] = (rt, ta, tc)
        f7 = F7[sec]
        if sec in ("Ingresos", "Costos", "Gastos"):
            f_ant = f'IF({PRELIM},IF({f_hay_eri},{S7}H{f7},{S7}F{f7}*{_par("mesesTranscurridos")}/12),{S7}F{f7})'
            v_ant = (s7["eri"][sec] if hay_eri else s7["ant"][sec] * meses / 12) if prelim else s7["ant"][sec]
        else:
            f_ant, v_ant = f"{S7}F{f7}", s7["ant"][sec]
        rc = rt + 1
        filas.append([None, TXT_CUADRE_SECCION, None, None, fx(f"E{rt}-({f_ant})", n2(ta - v_ant)),
                      fx(f"F{rt}-{S7}G{f7}", n2(tc - s7["act"][sec])), None, None,
                      fx(f'IF(AND(ABS(E{rc})<0.005,ABS(F{rc})<0.005),"Cuadra","Revisar la jerarquía")',
                         "Cuadra" if abs(ta - v_ant) < 0.005 and abs(tc - s7["act"][sec]) < 0.005 else "Revisar la jerarquía")])
        estilos.append({"tipo": "control"})
    if secs[0] == "Activo" and all(k in totales for k in secs):
        (ra, aa, ac), (rp, pa, pc), (rpt, ta_, tc_) = (totales[k] for k in secs)
        k9 = "Resultado del período (según el balance)"
        res_a, res_c = s7["ant"]["Resultado del balance"], s7["act"]["Resultado del balance"]
        rr = FILA0 + len(filas)
        filas.append([None, TXT_RESULTADO_ESF, None, None, fx(f"{E9}C{F9[k9]}", n2(res_a)), fx(f"{E9}D{F9[k9]}", n2(res_c)),
                      fx(f"F{rr}-E{rr}", n2(res_c - res_a)), None, None])
        estilos.append({"tipo": "total"})
        filas.append([None, TXT_PASIVO_PATRIMONIO, None, None, fx(f"E{rp}+E{rpt}+E{rr}", n2(pa + ta_ + res_a)),
                      fx(f"F{rp}+F{rpt}+F{rr}", n2(pc + tc_ + res_c)), None, None, None])
        estilos.append({"tipo": "total"})
        rd = rr + 2
        da, dc = aa - (pa + ta_ + res_a), ac - (pc + tc_ + res_c)
        filas.append([None, TXT_DIF_ACTIVO, None, None, fx(f"E{ra}-E{rd - 1}", n2(da)), fx(f"F{ra}-F{rd - 1}", n2(dc)), None, None,
                      fx(f'IF(AND(ABS(E{rd})<0.005,ABS(F{rd})<0.005),"Cuadra","Revisar el balance")',
                         "Cuadra" if abs(da) < 0.005 and abs(dc) < 0.005 else "Revisar el balance")])
        estilos.append({"tipo": "control"})
    if secs[0] == "Ingresos" and all(k in totales for k in secs):
        rr = FILA0 + len(filas)
        (ri, ia_, ic), (rco, ca, cc), (rg, ga, gc) = (totales[k] for k in secs)
        filas.append([None, TXT_RESULTADO_ERI, None, None, fx(f"E{ri}-E{rco}-E{rg}", n2(ia_ - ca - ga)),
                      fx(f"F{ri}-F{rco}-F{rg}", n2(ic - cc - gc)), fx(f"F{rr}-E{rr}", n2((ic - cc - gc) - (ia_ - ca - ga))),
                      fx(f'IF(E{rr}=0,"",G{rr}/ABS(E{rr}))', None if ia_ - ca - ga == 0 else
                         ((ic - cc - gc) - (ia_ - ca - ga)) / abs(ia_ - ca - ga)), None])
        estilos.append({"tipo": "total"})
    return filas, estilos


def _sumarias(cu: list, notas: list, umbral: float) -> tuple[list, list]:
    """Cédulas sumarias (lead schedules): un bloque por rubro con la cuenta del rubro, sus subcuentas con
    sangría, el total de las cuentas de detalle y el cuadre. Saldos por fórmula a 08_Horizontal; los ajustes
    del auditor se escriben en las cuentas de detalle y suben por fórmula a sus cuentas superiores."""
    filas, estilos = [], []
    u = _par("umbralVarPct")
    idx = {x["codigo"]: i for i, x in enumerate(cu)}
    rubros = [x for x in cu if _es_rubro(x)]
    for k, rb in enumerate(rubros, start=1):
        ref_pt = f"S-{k:02d}"
        bloque = [rb] + [x for x in cu if x is not rb and _debajo(x["codigo"], rb["codigo"])]
        a = FILA0 + len(filas)
        fila_de = {x["codigo"]: a + j for j, x in enumerate(bloque)}
        for j, x in enumerate(bloque):
            r, r8 = a + j, FILA0 + idx[x["codigo"]]
            detalles = [y for y in bloque if y is not x and y["detalle"] == "Sí" and _debajo(y["codigo"], x["codigo"])]
            if x["detalle"] == "Sí" or not detalles:
                h_cel = None                                   # el auditor escribe aquí sus ajustes
            else:
                h_cel = fx("+".join(f"N(H{fila_de[y['codigo']]})" for y in detalles), 0.0)
            nota = ", ".join(f"Nota {n_['nota']}" for n_ in notas
                             if any(x["codigo"] == pf or _debajo(x["codigo"], pf) for pf in n_["pref"]))
            filas.append([
                ref_pt, x["codigo"], x["cuenta"],
                fx(f"{H8}C{r8}", x["nivel"]), fx(f"{H8}D{r8}", x["detalle"]),
                fx(f"{H8}G{r8}", n2(x["ant"])), fx(f"{H8}H{r8}", n2(x["act"])), h_cel,
                fx(f"G{r}+N(H{r})", n2(x["act"])), fx(f"I{r}-F{r}", n2(x["act"] - x["ant"])),
                fx(f'IF(F{r}=0,"",J{r}/ABS(F{r}))', None if x["ant"] == 0 else (x["act"] - x["ant"]) / abs(x["ant"])),
                nota,
                fx(f'IF(F{r}=0,IF(G{r}<>0,"Nueva",""),IF(G{r}=0,"Baja",IF(ABS(J{r}/F{r})>={u}/100,"Supera el umbral","")))',
                   _marca(x["ant"], x["act"], umbral)),
            ])
            estilos.append({"tipo": "titulo"} if j == 0 else {"sangria": x["nivel"] - rb["nivel"], "col": "Cuenta"})
        b = a + len(bloque) - 1
        det = [x for x in bloque if x["detalle"] == "Sí"]
        ta, tc = sum(x["ant"] for x in det), sum(x["act"] for x in det)
        rt = b + 1
        sif = lambda c: f'SUMIFS({c}{a}:{c}{b},$E${a}:$E${b},"Sí")'  # noqa: E731
        filas.append([ref_pt, None, TXT_TOTAL_SUMARIA, None, None, fx(sif("F"), n2(ta)), fx(sif("G"), n2(tc)),
                      fx(sif("H"), 0.0), fx(sif("I"), n2(tc)), fx(f"I{rt}-F{rt}", n2(tc - ta)),
                      fx(f'IF(F{rt}=0,"",J{rt}/ABS(F{rt}))', None if ta == 0 else (tc - ta) / abs(ta)), None, None])
        estilos.append({"tipo": "total"})
        rc = rt + 1
        da, dc = rb["ant"] - ta, rb["act"] - tc
        filas.append([ref_pt, None, TXT_CUADRE_SUMARIA, None, None, fx(f"F{a}-F{rt}", n2(da)), fx(f"G{a}-G{rt}", n2(dc)),
                      None, fx(f"I{a}-I{rt}", n2(dc)), None, None, None,
                      fx(f'IF(AND(ABS(F{rc})<0.005,ABS(G{rc})<0.005,ABS(I{rc})<0.005),"Cuadra","Revisar la jerarquía")',
                         "Cuadra" if abs(da) < 0.005 and abs(dc) < 0.005 else "Revisar la jerarquía")])
        estilos.append({"tipo": "control"})
    return filas, estilos


def _tipo_efecto(v: float) -> str:
    return "Origen" if v > 0.005 else "Aplicación" if v < -0.005 else "Sin efecto"


def _f_tipo(c: str) -> str:
    return f'IF({c}>0.005,"Origen",IF({c}<-0.005,"Aplicación","Sin efecto"))'


def _cifra_var(etq: str, ref_: str, v: float) -> tuple[str, str]:
    """« (inventario +US$ 1.234,00)»: fórmula y valor de la variación con signo, para la lectura causa-efecto."""
    return (f'"{etq} "&IF({ref_}>=0,"+","−")&"US$ "&FIXED(ABS({ref_}),2)',
            f"{etq} {'+' if v >= 0 else '−'}US$ {_num(abs(v))}")


def _causa_efecto(ev: dict, dv: dict, marco: str = MARCO_COMPLETAS) -> list:
    """Lectura causa-efecto de las variaciones (artefacto), con los montos: (concepto, clave del importe, fórmula, valor)."""
    inv, ven, caja, cxc = (ev[k] for k in ("Inventarios", "Ventas netas", "Efectivo y equivalentes", "Cuentas por cobrar"))
    di, dven, dc, dcx = (dv[k] for k in ("Inventarios", "Ventas netas", "Efectivo y equivalentes", "Cuentas por cobrar"))
    t = {k: segun_marco(v, marco) for k, v in CAUSA_EFECTO.items()}

    def montos(*pares):
        fs, vs = zip(*(_cifra_var(e_, r_, v_) for e_, r_, v_ in pares))
        return '&" ("&' + '&"; "&'.join(fs) + '&")"', " (" + "; ".join(vs) + ")"
    m_inv = montos(("inventario", inv, di), ("ventas", ven, dven))
    m_caja = montos(("efectivo", caja, dc), ("cartera", cxc, dcx))
    m_cv = montos(("efectivo", caja, dc), ("ventas", ven, dven))
    f_inv = (f'IF(ABS({inv})<=1,"{t["inv0"]}",IF({inv}>0,IF({ven}<0,"{t["inv_acum"]}",IF({ven}>0,"{t["inv_repo"]}","{t["inv_sin"]}")),'
             f'IF({ven}>0,"{t["inv_rot"]}","{t["inv_baja"]}")))' + m_inv[0])
    v_inv = (t["inv0"] if abs(di) <= 1 else (t["inv_acum"] if dven < 0 else t["inv_repo"] if dven > 0 else t["inv_sin"]) if di > 0
             else t["inv_rot"] if dven > 0 else t["inv_baja"]) + m_inv[1]
    f_caja = (f'IF(AND({caja}<0,{cxc}>0),"{t["caja_cartera"]}",IF(AND({caja}>0,{cxc}<0),"{t["caja_cobro"]}","{t["caja_sin"]}"))'
              + m_caja[0])
    v_caja = (t["caja_cartera"] if dc < 0 and dcx > 0 else t["caja_cobro"] if dc > 0 and dcx < 0 else t["caja_sin"]) + m_caja[1]
    f_cv = f'IF(AND({caja}<0,{ven}>0),"{t["caja_senal"]}","{t["caja_sin_senal"]}")' + m_cv[0]
    v_cv = (t["caja_senal"] if dc < 0 and dven > 0 else t["caja_sin_senal"]) + m_cv[1]
    out = [("Inventarios frente a ventas", "Inventarios", f_inv, v_inv), ("Efectivo frente a cartera", "Efectivo y equivalentes", f_caja, v_caja),
           ("Efectivo frente a ventas", "Efectivo y equivalentes", f_cv, v_cv)]
    for concepto, k, baja, sube in (("Cuentas por pagar", "Cuentas por pagar", t["cxp_baja"], t["cxp_sube"]),
                                    ("Deuda financiera", "Obligaciones financieras", t["deuda_baja"], t["deuda_sube"]),
                                    ("Resultado del período", "Utilidad neta", t["res_baja"], t["res_sube"])):
        c, v = ev[k], dv[k]
        mf, mv = _cifra_var("variación", c, v)
        out.append((concepto, k, f'IF(ABS({c})<=1,"{t["sin"]}",IF({c}<0,"{baja}","{sube}")&" ("&{mf}&")")',
                    t["sin"] if abs(v) <= 1 else (baja if v < 0 else sube) + f" ({mv})"))
    return out


CAUSA_EFECTO = {
    "inv0": "Sin movimiento relevante del inventario.",
    "inv_acum": "El inventario subió pese a menores ventas: posible acumulación o lento movimiento; revisar el valor neto realizable (NIC 2).",
    "inv_repo": "El inventario aumentó acompañando mayores ventas: reposición para sostener la demanda.",
    "inv_sin": "El inventario aumentó sin cambio en las ventas: revisar su rotación.",
    "inv_rot": "El inventario bajó mientras las ventas subieron: consistente con una mejor rotación.",
    "inv_baja": "El inventario disminuyó: verificar si responde a ventas, bajas o ajustes.",
    "caja_cartera": "El efectivo disminuyó mientras la cartera aumentó: parte de las ventas financia a clientes y drena caja.",
    "caja_cobro": "El efectivo aumentó y la cartera bajó: mejor cobranza que se tradujo en liquidez.",
    "caja_senal": "Señal a revisar: la caja cayó pese a mayores ventas; explicar el destino de los fondos (hoja 22).",
    "caja_sin_senal": "Sin señal: el efectivo no cayó frente a mayores ventas.",
    "caja_sin": "Sin relación destacable entre el efectivo y la cartera.",
    "cxp_baja": "Las cuentas por pagar se redujeron (se pagó a proveedores): uso de caja.",
    "cxp_sube": "Las cuentas por pagar aumentaron (más financiamiento de proveedores): fuente de caja; revisar plazos.",
    "deuda_baja": "La deuda financiera bajó (amortización): uso de caja que reduce el apalancamiento.",
    "deuda_sube": "La deuda financiera aumentó: fuente de caja que incrementa el apalancamiento; monitorear la cobertura.",
    "res_baja": "El resultado del período se deterioró respecto del período anterior.",
    "res_sube": "El resultado del período mejoró respecto del período anterior.",
    "sin": "Sin variación relevante.",
}


_DIAS = ("diasCartera", "diasInventario", "ciclo")
_DIAS_AJ = ("diasCartera", "diasInventario", "diasProveedores", "ciclo")


def _semaforo(k: str, v, fac: float = 1.0, pat: float | None = None) -> str:
    if k == "dias":
        return "Base"
    if v is None or v == "":
        return "Sin dato"
    if k in _PAT and pat is not None and pat <= 0:
        return NO_SIGNIFICATIVO
    if k == "diasProveedores":
        return "Referencia"
    if k in _RENT:
        return "Verde · Positivo" if v > 0 else "Rojo · Negativo" if v < 0 else "Amarillo · En el límite"
    verde, amarillo, (ev, ea, er) = ZONAS[k]
    if k in _DIAS:
        v = v * fac
    ok = lambda c: eval(f"{v}{c}".replace("=0", "==0") if c.startswith("=") else f"{v}{c}")  # noqa: E731,S307
    return f"Verde · {ev}" if ok(verde) else f"Amarillo · {ea}" if ok(amarillo) else f"Rojo · {er}"


def _f_semaforo(k: str, c: str, pat: str | None = None) -> str:
    if k == "dias":
        return '"Base"'
    if k in _PAT and pat:
        return f'IF(AND({c}<>"",{pat}<=0),"{NO_SIGNIFICATIVO}",{_f_semaforo(k, c)})'
    if k == "diasProveedores":
        return f'IF({c}="","Sin dato","Referencia")'
    if k in _RENT:
        return f'IF({c}="","Sin dato",IF({c}>0,"Verde · Positivo",IF({c}<0,"Rojo · Negativo","Amarillo · En el límite")))'
    verde, amarillo, (ev, ea, er) = ZONAS[k]
    cc = f"{c}*{FAC}" if k in _DIAS else c
    return f'IF({c}="","Sin dato",IF({cc}{verde},"Verde · {ev}",IF({cc}{amarillo},"Amarillo · {ea}","Rojo · {er}")))'


def _num(v, d: int = 2) -> str:
    """Cifra como la escribe FIXED(v; d) de Excel con separadores del Ecuador (miles «.», decimales «,»)."""
    t = f"{_xr(v, d):,.{d}f}"
    return t.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _lectura(k: str, v, pat: float | None = None, fac: float = 1.0) -> str:
    if v is None or v == "":
        return SIN_DATO
    if k in _PAT and pat is not None and pat <= 0:
        return LECTURA_PATRIMONIO
    antes, despues = LECTURA[k]
    cifra = _xr(v * fac, 2) if k in _DIAS_AJ else v
    txt = antes + _num(cifra) + despues
    if k in LECTURA_COND:
        cond, si, no = LECTURA_COND[k]
        txt += si if eval(f"{v}{cond}") else no  # noqa: S307
    return txt


def _f_lectura(k: str, c: str, pat: str | None = None, c_aj: str | None = None) -> str:
    """Lectura con la cifra: ``c`` es la celda del índice; ``c_aj`` la de los días ajustados al período."""
    if k in _PAT and pat:
        return f'IF(AND({c}<>"",{pat}<=0),"{LECTURA_PATRIMONIO}",{_f_lectura(k, c, None, c_aj)})'
    antes, despues = LECTURA[k]
    txt = f'"{antes}"&FIXED({c_aj if k in _DIAS_AJ and c_aj else c},2)&"{despues}"'
    if k in LECTURA_COND:
        cond, si, no = LECTURA_COND[k]
        txt += f'&IF({c}{cond},"{si}","{no}")'
    return f'IF({c}="","{SIN_DATO}",{txt})'


def _tendencia(k: str, va, vc, pat: float | None = None) -> str:
    if k not in MEJOR or va in (None, "") or vc in (None, ""):
        return "" if k not in MEJOR else "Sin dato"
    if k in _PAT and pat is not None and pat <= 0:
        return "No significativo"
    if vc == va:
        return "Sin cambio"
    return "Mejora" if (vc > va) == (MEJOR[k] == "alto") else "Empeora"


def _f_tendencia(k: str, r: int, pat: str) -> str | None:
    if k not in MEJOR:
        return None
    sube = "Mejora" if MEJOR[k] == "alto" else "Empeora"
    baja = "Empeora" if MEJOR[k] == "alto" else "Mejora"
    f_ = f'IF(OR(D{r}="",E{r}=""),"Sin dato",IF(E{r}=D{r},"Sin cambio",IF(E{r}>D{r},"{sube}","{baja}")))'
    return f'IF(AND(E{r}<>"",{pat}<=0),"No significativo",{f_})' if k in _PAT else f_


# --- «Cómo se calcula esta hoja» -----------------------------------------------------------------------------

EXPLICA = {
    "01_Resumen": {
        "Importe": ("Trae cada cifra de la hoja donde se calcula: activo, pasivo, patrimonio, ventas y utilidad de la hoja 09 "
                    "(Estados resumidos); las materialidades de la hoja 11; los riesgos altos de las hojas 12 y 13 y las "
                    "cuentas a revisar de la hoja 18."),
    },
    "03_Mapa": {
        "Sección": ("Toma la clasificación de la fila y la reduce a su sección: activo corriente y no corriente son «Activo», "
                    "pasivo corriente y no corriente son «Pasivo»; el resto queda igual."),
    },
    "BC": {
        "Nivel": ("Cuenta cuántas cuentas superiores de esta cuenta hay en el mismo balance (códigos que son el inicio de su "
                  "código) y le suma uno: 1 es la sección, 2 el grupo, 3 la cuenta de mayor y así sucesivamente."),
        "Detalle": ("Marca «Sí» cuando ninguna otra cuenta del balance empieza con este código: es una cuenta de detalle y solo "
                    "esas se suman, para no contar dos veces el saldo de una cuenta superior."),
        "Clasificación": ("Busca en la hoja 03 (Mapa de cuentas) el prefijo más largo con que empieza el código (sin puntos) y "
                          "trae su clasificación; si ningún prefijo coincide, la cuenta queda en «Otros»."),
        "Sección": ("Reduce la clasificación a su sección (Activo, Pasivo, Patrimonio, Ingresos, Costos, Gastos u Otros) para "
                    "sumar y presentar los saldos por estado financiero."),
        "Rubro del ERI": ("Ubica la cuenta en el estado de resultados: ingresos con código 41 o 42 son ventas y el resto otros "
                          "ingresos; los gastos con «financ» o «interés» en el nombre son financieros, los de impuesto a la renta "
                          "o participación van aparte y los demás son operativos."),
        "Saldo presentado": ("Multiplica el saldo del cliente por el signo de su sección de la hoja 07: así las cuentas acreedoras "
                             "(pasivo, patrimonio, ingresos) se presentan en positivo por naturaleza."),
        "Superior de la sección": ("Marca «Sí» en la cuenta más alta de su sección (ninguna cuenta superior del mismo balance es de "
                                   "esa sección): su saldo propio ya incluye el de sus subcuentas y es el que se suma (R1)."),
        "Diferencia con subcuentas": ("Resta del saldo de la cuenta la suma de sus subcuentas inmediatas (un nivel más abajo); en las "
                                      "cuentas de detalle es cero. Si no es cero, el archivo no cuadra por dentro y se usa el saldo propio."),
    },
    "07_Secciones": {
        "Bruto BC anterior": ("Suma el saldo tal como lo entregó el cliente de las cuentas más altas de esa sección en la hoja 04 "
                              "(balance del cierre anterior): su saldo propio ya incluye el de sus subcuentas (R1)."),
        "Bruto BC corte": "Suma el saldo del cliente de las cuentas más altas de esa sección en la hoja 05 (balance al corte).",
        "Bruto ERI anterior": ("Suma el saldo del cliente de las cuentas más altas de esa sección en la hoja 06 (resultados del año "
                               "anterior al mismo corte); queda en cero si no se entregó."),
        "Signo": ("Detecta cómo exporta el sistema del cliente: si en el balance al corte la suma de todas las secciones es cero "
                  "(deudor positivo y acreedor negativo), pasivo, patrimonio e ingresos llevan −1 para presentarse en positivo; "
                  "si cuadra la ecuación contable (todo en positivo por naturaleza), todas llevan 1. Así un déficit sigue negativo."),
        "BC anterior": ("Multiplica el total bruto del cierre anterior por el signo; en las filas de abajo calcula el resultado "
                        "(ingresos − costos − gastos), la utilidad antes de participación e impuestos y el cuadre del balance."),
        "BC corte": ("Hace lo mismo con el balance al corte: total presentado por sección, resultado del período y diferencia de "
                     "cuadre (activo − pasivo − patrimonio − resultado)."),
        "ERI anterior": ("Hace lo mismo con el estado de resultados del año anterior al mismo corte, para comparar ingresos, "
                         "costos y gastos del mismo número de meses."),
    },
    "15D_Notas_Detalle": {
        "Nivel": "Nivel de la cuenta en la jerarquía del plan de cuentas, tomado de la hoja 08.",
        "Saldo al cierre anterior": "Saldo presentado de la cuenta al cierre del año anterior (hoja 08). En el total, suma de "
                                    "las cuentas que forman la nota; en «Saldo auditado», el saldo de la nota en la hoja 15; en "
                                    "la diferencia, total del balance menos saldo auditado.",
        "Saldo al corte": "Saldo presentado de la cuenta a la fecha de corte (hoja 08); en el total, suma de las cuentas de la nota.",
        "Variación": "Saldo al corte menos saldo al cierre anterior.",
        "Variación %": "Variación dividida para el saldo al cierre anterior (en blanco si ese saldo es cero).",
        "Marca": "«Nueva», «Baja» o «Supera el umbral» según la variación de la cuenta; en la diferencia, «Coincide» si el balance "
                 "anterior es igual a la nota auditada y «Revisar (NIA 510)» si no.",
    },
    "15C_Composicion": {
        "Importe auditado": "En las líneas, el importe del informe auditado (hoja de datos del cliente). La suma toma solo las "
                            "líneas de saldo; el total, la línea «Total» de la nota; el saldo auditado viene de la hoja 15; la "
                            "diferencia es suma menos saldo auditado.",
        "Control": "«Coincide» si la suma de las líneas es igual al total de la nota y al saldo auditado; «Revisar» si no.",
    },
    "08S_Sumarias": {
        "Nivel": "Nivel de la cuenta en la jerarquía del plan de cuentas, tomado de la hoja 08.",
        "Detalle": "«Sí» si la cuenta no tiene subcuentas (cuenta de detalle), según la hoja 08.",
        "Saldo al cierre anterior": "Saldo presentado de la cuenta al cierre del año anterior, tomado de la hoja 08. En el "
                                    "total, suma de las cuentas de detalle del rubro.",
        "Saldo al corte": "Saldo presentado de la cuenta a la fecha de corte, tomado de la hoja 08. En el total, suma de las "
                          "cuentas de detalle del rubro.",
        "Ajustes del auditor": "En las cuentas de detalle la escribe el auditor (ajustes y reclasificaciones propuestos). En "
                               "las cuentas superiores y en el total es la suma de los ajustes de sus cuentas de detalle.",
        "Saldo ajustado": "Saldo al corte más los ajustes del auditor.",
        "Variación": "Saldo ajustado menos el saldo del cierre anterior.",
        "Variación %": "Variación dividida para el saldo del cierre anterior (en blanco si ese saldo es cero).",
        "Marca": "«Nueva» si la cuenta no tenía saldo al cierre anterior, «Baja» si no tiene saldo al corte y «Supera el "
                 "umbral» si la variación supera el umbral de variación de los parámetros. En la fila de cuadre, «Cuadra» si "
                 "el rubro es igual a la suma de sus cuentas de detalle.",
    },
    "08_Horizontal": {
        "Nivel": ("Cuenta las cuentas superiores de este código presentes en la unión de los balances (códigos que son el inicio "
                  "del suyo) y le suma uno."),
        "Detalle": ("Marca «Sí» si ningún otro código de esta hoja empieza con el de la fila: solo las cuentas de detalle entran "
                    "en las sumas de los estados resumidos."),
        "Clasificación": ("Busca en la hoja 03 el prefijo más largo con que empieza el código y trae su clasificación (activo "
                          "corriente, pasivo no corriente, ingresos…); sin coincidencia, «Otros»."),
        "Sección": "Reduce la clasificación a su sección, igual que en los balances de las hojas 04 a 06.",
        "Anterior": ("Trae el saldo presentado de la cuenta en la hoja 04 (R1: su saldo propio; si no está, la suma de sus "
                     "subcuentas de detalle). En la revisión preliminar, para ingresos, costos y gastos usa la hoja 06 (mismo corte "
                     "del año anterior) o, si no se entregó, el cierre anterior × meses transcurridos ÷ 12."),
        "Actual": ("Trae el saldo presentado de la cuenta en la hoja 05 (balance al corte): su saldo propio o, si no está, la suma "
                   "de sus subcuentas de detalle."),
        "Variación": "Resta el saldo anterior del actual: cuánto subió (positivo) o bajó (negativo) la cuenta.",
        "Variación %": "Divide la variación para el saldo anterior sin signo; queda en blanco si el saldo anterior es cero.",
        "Peso vertical": ("Divide el saldo actual para el activo total (cuentas del balance) o para las ventas netas (cuentas de "
                          "resultados) de la hoja 09."),
        "Rubro del ERI": "Ubica la cuenta en el estado de resultados con la misma regla de las hojas 04 a 06 (código 41/42 y palabras del nombre).",
        "Rubro para índices": ("Reconoce por el nombre las cuentas por cobrar, inventarios, cuentas por pagar y obligaciones "
                               "financieras que usan los índices de liquidez y actividad."),
        "Cuenta para índices": ("Marca «Sí» en la cuenta más alta de cada rubro (ninguna cuenta superior tiene el mismo rubro), para "
                                "sumar el rubro una sola vez con sus provisiones y subcuentas."),
        "Monto material": "Marca «Sí» cuando el saldo actual, sin signo, iguala o supera la materialidad de desempeño de la hoja 11.",
        "Variación material": "Marca «Sí» cuando la variación, sin signo, iguala o supera la materialidad de desempeño de la hoja 11.",
        "Superior de la sección": ("Marca «Sí» en la cuenta más alta de su sección (ninguna cuenta superior es de la misma sección): "
                                   "los totales de la hoja 09 suman esas cuentas y no sus subcuentas (R1)."),
        "Superior de la clasificación": ("Marca «Sí» en la cuenta más alta de su clasificación (activo no corriente, pasivo no "
                                         "corriente…), para sumar cada clasificación una sola vez."),
        "Superior del rubro del ERI": ("Marca «Sí» en la cuenta más alta de su rubro del estado de resultados (por ejemplo ventas), "
                                       "para sumar el rubro una sola vez."),
    },
    "09_Estados": {
        "Anterior": ("Suma en la hoja 08 la columna «Anterior» de las cuentas más altas de cada sección, clasificación o rubro "
                     "(R1); gastos financieros e impuestos salen de las cuentas de detalle por su nombre, los gastos operativos "
                     "son el total de gastos menos esos dos y los subtotales se calculan con las filas de arriba."),
        "Actual": ("Hace lo mismo con la columna «Actual» de la hoja 08; el resultado del período del balance viene de la hoja 07 "
                   "para comprobar el cuadre."),
        "Variación": "Resta el importe anterior del actual de cada rubro del estado resumido.",
        "Variación %": "Divide la variación para el importe anterior sin signo; en blanco si el anterior es cero.",
        "Vertical actual": "Divide el importe actual para el activo total (situación financiera) o para las ventas netas (resultados).",
        "Vertical anterior": ("Divide el importe anterior para el activo total o las ventas netas del período anterior, para comparar "
                              "el peso de cada rubro en los dos períodos."),
        "Observación": ("Si la variación porcentual, sin signo, iguala o supera el umbral de la hoja 02, pide revisar el rubro y "
                        "su respaldo; si no, queda en blanco."),
    },
    "10_Indices": {
        "Anterior": ("Calcula el índice con los importes «Anterior» de la hoja 09 según la fórmula de la columna «Cómo se "
                     "calcula», redondeado a dos decimales; en blanco si el divisor es cero."),
        "Actual": "Calcula el mismo índice con los importes «Actual» de la hoja 09, redondeado a dos decimales.",
        "Variación": "Resta el índice anterior del actual; queda en blanco si falta alguno de los dos.",
        "Semáforo": ("Compara el índice actual con los rangos de referencia de la firma (por ejemplo, razón corriente de 1,5 o "
                     "más es verde y menor a 1 es rojo) y lo califica en verde, amarillo o rojo. En una revisión preliminar los "
                     "días se comparan multiplicados por meses ÷ 12, porque sobre 365 salen mayores. Si el patrimonio total "
                     "es cero o negativo, los índices que dividen para el patrimonio (endeudamiento patrimonial y financiero, "
                     "multiplicador y ROE) quedan en rojo como «No significativo»."),
        "Lectura": ("Explica en palabras qué mide el índice con su cifra (por ejemplo, «por cada US$ 1 de pasivo corriente hay "
                    "US$ 2,00 de activo corriente»; en los días, la cifra ajustada al período) y, en liquidez y capital de "
                    "trabajo, si alcanza o no a cubrir el corto plazo. Con patrimonio cero o negativo, advierte que el índice no "
                    "es interpretable (NIA 570)."),
        "Actual ajustado al período": ("Solo en los índices de días: multiplica los días actuales por meses transcurridos ÷ 12 en "
                                       "una revisión preliminar (en la final queda igual), porque con ventas o costos de pocos meses "
                                       "los días sobre 365 salen inflados. Es la cifra que se compara con los 90 y 120 días de la hoja 13."),
        "Variación ajustada": ("Aplica el mismo ajuste (× meses ÷ 12 en la preliminar) a la variación de días; es la que se compara "
                               "con el umbral de deterioro de la rotación de la hoja 02."),
        "Tendencia": ("Compara el índice actual con el anterior según su sentido favorable: en liquidez y rentabilidad subir es "
                      "«Mejora»; en días y endeudamiento subir es «Empeora». Con patrimonio cero o negativo, los índices sobre el "
                      "patrimonio quedan «No significativo»."),
    },
    "11_Materialidad": {
        "Importe": ("Trae de la hoja 07 el total de cada posible base del período elegido (año anterior o corte actual); en la "
                    "materialidad global busca la base elegida en la hoja 02 y, en las filas de abajo, toma la global. En la revisión "
                    "preliminar con el corte actual, los ingresos, los gastos y la utilidad cubren solo los meses transcurridos: se "
                    "anualizan (× 12 ÷ meses) para que la materialidad sea la del ejercicio completo; el activo y el patrimonio no."),
        "Porcentaje": "Trae de la hoja 02 el porcentaje de la política de la firma para cada base, para el desempeño y para el umbral trivial.",
        "Materialidad": ("Multiplica el importe por el porcentaje y lo divide para 100. En la última fila, la materialidad "
                         "específica que el equipo registró en el cuestionario (hoja 24, MES-03) para partidas que requieren "
                         "una materialidad inferior (NIA 320 párr. 10)."),
        "Sustento": ("Explica el período de la base (automático: año anterior en la revisión preliminar y corte actual en la "
                     "final), la base elegida y su justificación: la del auditor o la automática, que muestra la base, el "
                     "porcentaje y la materialidad con sus cifras."),
        "Rango de práctica": "En la materialidad global trae el rango de práctica de la base elegida en la hoja 02.",
        "¿Dentro del rango?": ("Compara el porcentaje con el rango de práctica habitual de la profesión (política de la firma, "
                               "VERIFICAR): «Dentro del rango» o «Fuera del rango», que obliga a documentar el porqué (NIA 320 "
                               "párr. 14). " "En la materialidad específica: «Conforme» si es inferior a la global, «Revisar» si no."),
    },
    "12_Riesgos_CCI": {
        "¿Se probará el control?": ("«Sí» si la carta lo indica o si el ciclo del hallazgo confía en los controles (hoja 45): "
                                    "entonces se prueba su eficacia y el riesgo valorado considera el control."),
        "Clasificación de la deficiencia (NIA 265)": ("Deficiencia significativa si el hallazgo es riesgo significativo o de nivel "
                                                      "alto (se comunica por escrito al gobierno); si no, otra deficiencia que se "
                                                      "comunica a la dirección; pendiente mientras no esté calificado."),
        "Riesgo inherente": "Multiplica la probabilidad por el impacto (escala de 1 a 25); en blanco si falta alguna calificación.",
        "Riesgo valorado": ("Riesgo de incorrección material valorado: si el auditor probará la eficacia del control (columna "
                            "N), reduce el inherente según el control (inherente × (6 − control) ÷ 5; con control 1 queda igual); "
                            "si no lo probará, queda igual al inherente, porque un control no probado no reduce el riesgo "
                            "(NIA 315 revisada y NIA 330)."),
        "Nivel": ("Alto si el riesgo es significativo o si el residual iguala o supera el umbral alto de la hoja 02, medio si supera "
                  "el umbral medio y bajo en los demás casos; sin calificación completa queda pendiente del socio."),
        "¿Riesgo significativo?": ("Sí cuando el riesgo INHERENTE (antes de los controles) iguala o supera el umbral de riesgo "
                                   "significativo de la hoja 02 (NIA 315 párr. 32): un control fuerte baja el residual pero no "
                                   "quita la respuesta específica ni las pruebas sustantivas que exige la NIA 330 párr. 21."),
    },
    "14_Perfil": {
        "Detalle": ("En la identificación toma de la hoja 02 el corte, el tipo de revisión, el marco, si es encargo inicial "
                    " y el socio y el gerente; lo que está en blanco queda «[PENDIENTE]». Los demás datos "
                    "vienen del informe del año anterior (hoja de datos del cliente) y los que no tienen soporte quedan "
                    "«[PENDIENTE]»: no se completan por inferencia."),
    },
    "13_Riesgos_Balance": {
        "Valor observado": ("Trae el dato que dispara la condición: ventas, patrimonio o utilidad de la hoja 09, el índice de la "
                            "hoja 10 (en los días, la cifra y la variación ajustadas al período de las columnas I y J), la "
                            "variación de la cuenta de la hoja 08 o el importe del asunto del informe anterior (hoja 14)."),
        "¿Se presenta?": ("Evalúa la condición con el valor observado (capital de trabajo negativo, días de cartera ajustados "
                          "mayores a 90, aumento de días ajustado mayor al umbral de la hoja 02…); la presunción de "
                          "fraude en ingresos se presenta salvo que se refute en la hoja 02."),
    },
    "15_Notas": {
        "Saldo del balance anterior": ("Suma el saldo presentado de las cuentas de detalle de la hoja 04 cuyos códigos empiezan "
                                       "con los códigos de la nota: es el saldo de apertura según el balance del cliente."),
        "Diferencia": "Resta el saldo auditado de la nota del saldo del balance anterior: debe ser cero (NIA 510).",
        "Saldo al corte": "Suma el saldo presentado de las mismas cuentas en la hoja 05 (balance al corte).",
        "Variación": "Resta el saldo del balance anterior del saldo al corte: el movimiento de la nota en el período.",
        "Variación %": "Divide la variación para el saldo del balance anterior sin signo; en blanco si es cero.",
    },
    "16_Control": {
        "Importe": ("Trae la diferencia de cuadre de cada balance y el saldo fuera del mapa de la hoja 07, y la materialidad "
                    "global de la hoja 11."),
        "Cantidad": ("Cuenta las filas que cumplen el control en su hoja: anomalías altas (17), notas cargadas o que no concilian "
                     "(15), indicios de empresa en funcionamiento (13), hallazgos pendientes o cargados (12), informe anterior (14) y "
                     "cuentas que no suman sus subcuentas (04 y 05)."),
        "Estado": ("Conforme si el control se cumple; en los cuadres, «Revisar» si la diferencia no supera el 1 % del activo y "
                   "«Crítico» si lo supera; en los conteos, «Revisar» cuando hay casos que atender."),
    },
    "17_Anomalias": {
        "Importe": "Trae de la hoja 08 el saldo actual, el anterior o la variación de la cuenta, según el tipo de anomalía.",
        "¿Se presenta?": ("Vuelve a evaluar la condición con las cifras de la hoja 08 y la materialidad de desempeño: saldo "
                          "negativo, cuenta nueva o dada de baja, variación extrema o el mismo importe en varias cuentas."),
    },
    "18_Cuentas_Revisar": {
        "Sección": "Trae de la hoja 08 la sección de la cuenta (activo, pasivo, patrimonio, ingresos, costos o gastos).",
        "Saldo actual": "Trae de la hoja 08 el saldo actual de la cuenta.",
        "Variación": "Trae de la hoja 08 la variación de la cuenta frente al período anterior.",
        "Monto material": "Trae de la hoja 08 si el saldo actual alcanza la materialidad de desempeño.",
        "Variación material": "Trae de la hoja 08 si la variación alcanza la materialidad de desempeño.",
        "Riesgos de la hoja 13": ("Posibles riesgos de la hoja 13 que recaen en la cuenta (de su código o de su misma área) y que "
                                  "se presentan; los de empresa en funcionamiento son de toda la entidad y no marcan cuentas."),
        "¿Se revisa?": ("Marca «Sí» cuando la cuenta tiene monto material, variación material, un riesgo de la carta de control "
                        "interno de su misma área o un posible riesgo de la hoja 13: son las cuentas que el programa debe cubrir. "
                        "Si cambia la materialidad, cambia la marca."),
    },
    "19_Programa": {
        "Horas presupuestadas": ("Horas del procedimiento según su nivel, con las horas por nivel de la hoja 02 (política de la "
                                 "firma); cero si no aplica. La hoja 43 las reparte por rol."),
        "Supervisión": ("Revisión del socio para los riesgos altos, significativos o pendientes de calificación; del gerente para "
                        "los demás procedimientos."),
        "Nivel": ("Trae el nivel del riesgo de la hoja 12 (carta de control interno; «Significativo» si la hoja 12 lo marca como riesgo "
                  "significativo) o la severidad de la hoja 13 (posibles riesgos); "
                  "en las cuentas sin riesgo propio, «Medio» si su saldo o su variación es material y «Bajo» si no."),
        "Respuesta de auditoría (NIA 330)": ("Para los hallazgos de la carta de control interno trae la respuesta de la hoja 12; "
                                             "para los demás riesgos, la respuesta estándar de la herramienta."),
        "Herramienta del catálogo": "Trae de la hoja 12 la herramienta del catálogo AUD que ejecuta las pruebas del riesgo.",
        "Aseveraciones": ("Para los hallazgos de la carta, las aseveraciones de la hoja 12; para los demás, las que corresponden "
                          "al riesgo o a la sección de la cuenta."),
        "Oportunidad": ("Riesgo alto, significativo o pendiente de calificación: trabajo en la visita preliminar (controles) y en "
                        "la final (detalle al corte); medio: pruebas de detalle en la final; bajo: analíticos sustantivos en la final."),
        "Evidencia a obtener (PBC)": ("Si el nivel es «Significativo», antepone las pruebas de detalle del saldo y de las transacciones "
                                      "(NIA 330: un riesgo significativo no se cubre solo con analíticos); después, la evidencia de "
                                      "la carta de control interno o la estándar de la herramienta."),
        "Responsable": ("Trae de la hoja 02 el socio (riesgos altos, significativos o pendientes) o el gerente (los demás); si no "
                        "se registró, muestra «[PENDIENTE]» para que se complete antes de aprobar la planificación."),
        "Extensión (NIA 330 y 530)": ("En las cuentas con procedimiento propio, el tamaño de la muestra de la hoja 29 (o por qué no "
                                      "hay muestra); en los riesgos, la extensión según el nivel: alto o significativo, pruebas "
                                      "de detalle con confianza alta; medio, muestra con confianza media; bajo, analíticos "
                                      "sustantivos con el umbral de la materialidad de desempeño."),
        "¿Aplica?": ("«Sí» si el procedimiento sigue vigente: el riesgo de la hoja 13 se presenta o la cuenta sigue marcada para "
                     "revisión en la hoja 18. Los procedimientos de todo encargo siempre aplican. Sin materialidad (base cero o "
                     "negativa) queda «Pendiente: sin materialidad (NIA 320)»: no se puede fijar el alcance."),
    },
    "20_Narrativa": {
        "Importe": ("Trae la cifra de la hoja donde se calcula: estados resumidos (09), índices (10; los días, ajustados al "
                    "período en la revisión preliminar), el conteo de riesgos de las hojas 12 y 13 o, en causa-efecto, la variación "
                    "del rubro en la hoja 09. En el origen y el destino del efectivo suma los efectos de la hoja 22; la variación "
                    "de resultados acumulados (traspaso del resultado anterior) se suma al resultado del período, porque no es efectivo."),
        "Lectura": ("Escribe la conclusión con condiciones sobre las mismas cifras: si el activo creció, si el endeudamiento "
                    "supera el 70 %, el semáforo del índice y la recomendación que aplica o «No aplica»."),
    },
    "22_Origenes": {
        "Sección": "Trae de la hoja 08 la sección de la cuenta (activo, pasivo o patrimonio).",
        "Variación": ("Trae de la hoja 08 la variación de la cuenta; en la fila del resultado, la variación del resultado del período "
                      "según el balance (hoja 09)."),
        "Efecto en el efectivo": ("Un activo que sube consume efectivo (se cambia el signo); un pasivo o patrimonio que sube lo aporta. "
                                  "Abajo suma los efectos, trae la variación del efectivo de la hoja 09 y resta ambos: debe dar cero."),
        "Tipo": ("«Origen» si el efecto es positivo (fuente de efectivo), «Aplicación» si es negativo; en las cuentas de resultados "
                 "acumulados, «Traspaso de resultados», porque su variación es el resultado anterior que se traspasó y se lee junto "
                 "con el resultado del período; en la última fila dice si el puente cuadra con la variación del efectivo."),
    },
    "23_Audit_trail": {
        "Detalle": ("Remite a la hoja de parámetros o a la cédula donde se decide cada supuesto: tipo de revisión, comparativo de "
                    "resultados, signo de cada sección (hoja 07), base de días (hoja 10) y materialidad (hoja 11)."),
        "Valor": ("Cuenta las filas entregadas en cada hoja de datos y trae los meses transcurridos, las cuentas del mapa, la base "
                  "de días y la materialidad global de su hoja."),
    },
    "21_Estrategia": {
        "Decisión": ("Cada decisión remite a su origen: marco, tipo de revisión, fechas, equipo y respuestas Sí/No de la hoja 02; "
                     "las materialidades de la hoja 11; los riesgos del resumen y las cuentas a revisar de la hoja 18."),
    },
}

# En la planificación no hay «cifra del cliente frente a la recalculada»: el comparativo muestra los dos umbrales
# que guían el trabajo (graficos.TEXTOS los cambia solo para esta herramienta).
PANEL = {
    "poblacion": {"rotulo": "Activo total", "total": "activos"},
    "recalculado": {"rotulo": "Materialidad de desempeño", "total": "desempeno"},
    "registrado": {"rotulo": "Umbral de errores claramente insignificantes", "total": "trivial"},
    "textos": {"comparativo": "Umbrales de la planificación",
               "comparativo_sub": "Materialidad de desempeño (NIA 320) frente al umbral de errores claramente insignificantes (NIA 450), en USD.",
               "nota_recalculado": "NIA 320 párr. 11", "nota_registrado": "NIA 450 párr. 5",
               "problemas": "Asuntos para la planificación"},
    "composicion": {"rotulo": "Composición del activo", "hoja": "08_Horizontal", "etiqueta": "Cuenta", "valor": "Actual",
                    "donde": {"Sección": ["Activo"], "Nivel": ["3"]}},
    "distribucion": {"rotulo": "Costos y gastos por cuenta", "hoja": "08_Horizontal", "etiqueta": "Cuenta", "valor": "Actual",
                     "donde": {"Sección": ["Costos", "Gastos"], "Nivel": ["3"]}},
    # Tableros del artefacto de análisis: índices por grupo y analítico (anterior vs actual).
    "tableros": [
        {"rotulo": "Liquidez", "sub": "Veces · año anterior frente al corte.", "unidad": "veces", "hoja": "10_Indices",
         "etiqueta": "Indicador", "estado": "Semáforo",
         "filas": [{"fila": "Razón corriente (veces)", "mejor": "alto"}, {"fila": "Prueba ácida (veces)", "mejor": "alto"}]},
        {"rotulo": "Actividad", "sub": "Días · año anterior frente al corte.", "unidad": "días", "hoja": "10_Indices",
         "etiqueta": "Indicador", "estado": "Semáforo",
         "filas": [{"fila": "Días de cartera", "mejor": "bajo"}, {"fila": "Días de inventario", "mejor": "bajo"},
                   {"fila": "Días de proveedores"}, {"fila": "Ciclo de conversión del efectivo (días)", "mejor": "bajo"}]},
        {"rotulo": "Endeudamiento", "sub": "Veces · año anterior frente al corte.", "unidad": "veces", "hoja": "10_Indices",
         "etiqueta": "Indicador", "estado": "Semáforo",
         "filas": [{"fila": "Endeudamiento patrimonial (veces)", "mejor": "bajo"},
                   {"fila": "Multiplicador de apalancamiento (veces)", "mejor": "bajo"},
                   {"fila": "Endeudamiento financiero (veces)", "mejor": "bajo"}]},
        {"rotulo": "Rentabilidad", "sub": "Porcentaje · año anterior frente al corte.", "unidad": "%", "hoja": "10_Indices",
         "etiqueta": "Indicador", "estado": "Semáforo",
         "filas": [{"fila": x, "mejor": "alto"} for x in ("ROI operativo (%)", "Margen operativo (%)", "ROE (%)",
                                                          "Margen neto (%)", "Margen bruto (%)")]},
        {"rotulo": "Estructura del balance", "sub": "USD · año anterior frente al corte.", "unidad": "USD", "hoja": "09_Estados",
         "etiqueta": "Concepto",
         "filas": [{"fila": "Activo corriente"}, {"fila": "Activo no corriente"},
                   {"fila": "TOTAL PASIVO", "rotulo": "Pasivo total"},
                   {"fila": "PATRIMONIO TOTAL", "rotulo": "Patrimonio total", "mejor": "alto"}]},
        {"rotulo": "Estado de resultados", "sub": "USD · año anterior frente al corte.", "unidad": "USD", "hoja": "09_Estados",
         "etiqueta": "Concepto",
         "filas": [{"fila": "Ventas netas", "mejor": "alto"}, {"fila": "(−) Costo de ventas", "rotulo": "Costo de ventas"},
                   {"fila": "Utilidad bruta", "mejor": "alto"}, {"fila": "(−) Gastos operativos", "rotulo": "Gastos operativos"},
                   {"fila": "Utilidad neta", "mejor": "alto"}]},
    ],
}
for _k, _t in enumerate(PANEL["tableros"]):
    _t["series"] = [["Anterior", "Anterior"], ["Actual", "Actual"]]
    _t["seccion"] = "Índices financieros" if _k < 4 else "Analítico: estructura y resultados"


# --- origen del importe de cada problema --------------------------------------------------------------------

def _h(hojas, nombre):
    return next((x for x in hojas if x["name"] == nombre), None)


def _concepto(hoja_, columna, concepto):
    def f(hojas, e):
        h = _h(hojas, hoja_)
        if h is None:
            return None
        j = [c[0] for c in h["cols"]].index(columna)
        for i, fila in enumerate(h["rows"]):
            if _pr._texto(fila[0]) == concepto:
                return _pr.celda(hojas, hoja_, columna, i), fila[j]
        return None
    return f


def _por_prefijo(hoja_, columna, prefijo):
    """Fila cuya clave (prefijo(fila)) abre la descripción del problema seguida de «:»."""
    def f(hojas, e):
        h = _h(hojas, hoja_)
        if h is None:
            return None
        msg = e.get("message") or ""
        j = [c[0] for c in h["cols"]].index(columna)
        for i, fila in enumerate(h["rows"]):
            if msg.startswith(prefijo(fila) + ":"):
                return _pr.celda(hojas, hoja_, columna, i), fila[j]
        return None
    return f


REF_PROBLEMAS = {
    "BASE_NO_VALIDA": _concepto("11_Materialidad", "Importe", "Materialidad global"),       # importe de la base elegida
    "ESF_NO_CUADRA": _concepto("07_Secciones", "BC corte", "Diferencia de cuadre"),
    "ESF_ANTERIOR_NO_CUADRA": _concepto("07_Secciones", "BC anterior", "Diferencia de cuadre"),
    "CUENTAS_SIN_SECCION": _concepto("16_Control", "Importe", "Cuentas fuera del mapa (sección «Otros»)"),
    "RIESGO_FRAUDE_INGRESOS": _concepto("09_Estados", "Actual", "Ventas netas"),
    "CAPITAL_TRABAJO_NEGATIVO": _concepto("10_Indices", "Actual", "Capital de trabajo (USD)"),
    "PERDIDA_EJERCICIO": _concepto("09_Estados", "Actual", "Utilidad neta"),
    "PATRIMONIO_NEGATIVO": _concepto("09_Estados", "Actual", "PATRIMONIO TOTAL"),
    "VARIACION_MATERIAL": _por_prefijo("08_Horizontal", "Variación", lambda f: f"{_pr._texto(f[0])} {_pr._texto(f[1])}"),
    "INFORME_ANTERIOR": _por_prefijo("14_Perfil", "Importe (USD)", lambda f: _pr._texto(f[1])),
    "ANOMALIA": _por_prefijo("17_Anomalias", "Importe", lambda f: f"{_pr._texto(f[1])} {_pr._texto(f[2])} · {_pr._texto(f[0])}"),
    "NOTA_NO_CONCILIA": _por_prefijo("15_Notas", "Diferencia", lambda f: f"Nota {_pr._texto(f[0])}"),
    "DIFERENCIAS_MATERIALES": _concepto(enc_m.H30, "Importe de la diferencia", enc_m.TXT_DIF_TOTAL),
    "JERARQUIA_NO_SUMA": lambda hojas, e: (
        _por_prefijo("04_BC_Anterior", "Diferencia con subcuentas",
                     lambda f: f"{ETQ_BC['ant']} · {_pr._texto(f[0])} {_pr._texto(f[1])}")(hojas, e)
        or _por_prefijo("05_BC_Corte", "Diferencia con subcuentas",
                        lambda f: f"{ETQ_BC['act']} · {_pr._texto(f[0])} {_pr._texto(f[1])}")(hojas, e)),
}


# --- definición --------------------------------------------------------------------------------------------------

def definicion() -> dict:
    bc = ("Una fila por cuenta, tal como lo exporta el sistema contable, con TODOS los niveles (sección, grupo, cuenta y "
          "subcuentas): código, nombre y saldo. Los saldos acreedores pueden venir negativos: la herramienta detecta el signo "
          "de cada sección. No agregue filas de total fuera del plan de cuentas.")
    return {
        "name": "Planificación de la auditoría · balances, análisis, índices, materialidad, riesgos y programa (NIA 300, 315, 320, 330)",
        "area": "Planificación",
        "processor": "planificacion_nia",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Arma la planificación con los documentos de entrada del cronograma: balances de comprobación del cierre "
                    "anterior y del corte (y el estado de resultados del año anterior al mismo corte en la revisión preliminar), "
                    "carta de control interno, informe de auditoría y notas del año anterior. Calcula el análisis horizontal y "
                    "vertical de todas las cuentas, los estados resumidos, los índices con semáforo, la materialidad (NIA 320), la "
                    "matriz de riesgos de la carta de control interno y los posibles riesgos de los balances, de fraude (NIA 240) "
                    "y de empresa en funcionamiento (NIA 570); controla los saldos de apertura contra las notas (NIA 510), las anomalías y "
                    "la calidad del análisis; y propone las cuentas a revisar, el programa (NIA 330), la narrativa y la estrategia "
                    "global (NIA 300)."),
        "source": {"organization": "IAASB · Normas Internacionales de Auditoría (versión en español)", "type": "Norma de auditoría",
                   "date": "",
                   "document": ("NIA 300 párr. 7–13; NIA 315 (Revisada 2019) párr. 13–14, 19–32; NIA 320 párr. 10–14 y A3–A13; "
                                "NIA 450 párr. 5 y A2; NIA 240 párr. 26–27, 31–33 y 47; NIA 570 párr. 10 y A3; NIA 510 párr. 6; "
                                "NIA 520; NIA 330 párr. 5–7, 15, 18 y 21; NIA 260 párr. 15. VERIFICAR la numeración contra el "
                                "texto oficial vigente."),
                   "url": "https://www.iaasb.org/standards-pronouncements"},
        "nia": [
            {"document": "NIA 300", "section": "párr. 7–13", "requirement": "Establecer la estrategia global y el plan de auditoría; en un encargo inicial, considerar los saldos de apertura."},
            {"document": "NIA 315 (Revisada 2019)", "section": "párr. 13–14, 19–32",
             "requirement": "Procedimientos de valoración del riesgo (indagación, analíticos, observación); entendimiento de la entidad y de su control interno; riesgos significativos."},
            {"document": "NIA 320", "section": "párr. 10–14", "requirement": "Determinar y documentar la materialidad global y la de ejecución (desempeño)."},
            {"document": "NIA 450", "section": "párr. 5", "requirement": "Acumular las incorrecciones salvo las claramente insignificantes."},
            {"document": "NIA 240", "section": "párr. 26–27, 31–33, 47",
             "requirement": "Presunción de fraude en ingresos (refutable y documentada) y respuesta a la elusión de controles por la dirección."},
            {"document": "NIA 570", "section": "párr. 10", "requirement": "Considerar los hechos o condiciones sobre la empresa en funcionamiento al valorar el riesgo."},
            {"document": "NIA 510", "section": "párr. 6", "requirement": "Obtener evidencia de que los saldos de apertura no contienen incorrecciones y concuerdan con los estados auditados."},
            {"document": "NIA 520", "section": "párr. 5–7", "requirement": "Procedimientos analíticos: expectativas, diferencias e investigación."},
            {"document": "NIA 330", "section": "párr. 5–7, 15, 18, 21", "requirement": "Respuestas a los riesgos valorados; procedimientos sustantivos en cada saldo material."},
            {"document": "NIGC 1 y NIA 220 (Revisada)", "section": "aceptación, ética e independencia (VERIFICAR)",
             "requirement": "Aceptación y continuidad, requerimientos de ética e independencia del equipo, segregación entre quien prepara y quien revisa."},
            {"document": "NIA 210", "section": "párr. 6–10", "requirement": "Condiciones previas del encargo y carta de encargo."},
            {"document": "NIA 260 (Revisada)", "section": "párr. 14–17", "requirement": "Comunicar al gobierno las responsabilidades, el alcance y el momento, los riesgos significativos y la independencia."},
            {"document": "NIA 450", "section": "párr. 5 y 11", "requirement": "Acumular las incorrecciones no corregidas y evaluar su efecto frente a la materialidad."},
            {"document": "NIA 505 y NIA 501", "section": "párr. 7 (505) y 4 (501) — VERIFICAR", "requirement": "Confirmaciones externas y observación del recuento físico de inventarios."},
            {"document": "NIA 530", "section": "párr. 6–8 (VERIFICAR)", "requirement": "Diseño y tamaño de la muestra según el riesgo y el error tolerable."},
            {"document": "NIA 600 (Revisada)", "section": "materialidad del componente (VERIFICAR)", "requirement": "Componentes, materialidad inferior a la del grupo e instrucciones a los auditores de componentes."},
            {"document": "NIA 701 y NIGC 2", "section": "VERIFICAR", "requirement": "Asuntos clave de auditoría y revisión de calidad del encargo en entidades de interés público."},
        ],
        "calculo": [
            "Mapa de cuentas por prefijo del código (el más largo gana); nivel y cuentas de detalle por la jerarquía de los códigos; signo de presentación automático por sección.",
            "Análisis horizontal y vertical de TODAS las cuentas: en la revisión preliminar el balance compara el cierre anterior con el corte y los resultados comparan el mismo corte de ambos años (o el año anterior × meses ÷ 12).",
            "Estados resumidos, cuadre del balance e índices de liquidez, actividad (días del período), endeudamiento y rentabilidad (DuPont) con semáforo y lectura.",
            "Materialidad global = base × % de la firma; desempeño = global × % (50 % por defecto); errores claramente insignificantes = global × % (5 %).",
            "Carta de control interno: inherente = probabilidad × impacto; residual = inherente × (6 − control) ÷ 5; nivel según los umbrales de la firma.",
            "Posibles riesgos: fraude en ingresos y elusión de controles (NIA 240), indicios NIA 570, días de cartera e inventario, variaciones materiales y asuntos del informe anterior.",
            "Notas del año anterior contra el balance del cierre anterior (NIA 510); anomalías; control de calidad; cuentas a revisar; programa (NIA 330); narrativa y estrategia (NIA 300).",
        ],
        "fields": _BAL_ACT, "rules": [], "control": CONTROL, "primary": "materialidad",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, etq] for n, etq in CEDULAS],
        # A4 (NIA 230): cédulas clave con su preparó y revisó tomados de la bitácora (hoja 00_Firmas del libro).
        "firmas": ["11_Materialidad", "12_Riesgos_CCI", "13_Riesgos_Balance", "19_Programa", "21_Estrategia", enc_m.H24, enc_m.H25,
                   enc_m.H28, enc_m.H32],
        "program": [
            {"code": "PLA-01", "objective": "Perfil del encargo", "risk": "Planificar sin conocer la entidad ni los asuntos del año anterior",
             "assertion": "Encargo", "procedure": "Documentar la identificación, el marco, la opinión y los asuntos del informe de auditoría del año anterior",
             "evidence": "Informe de auditoría del año anterior", "criterion": "Perfil documentado con su fuente",
             "source": "NIA 300 párr. 7 y 13; NIA 315 párr. 19"},
            {"code": "PLA-02", "objective": "Balances y análisis horizontal", "risk": "Variaciones inusuales no detectadas",
             "assertion": "Todas", "procedure": "Comparar el balance de comprobación del corte con el del cierre anterior en todas las cuentas y niveles",
             "evidence": "Balances de comprobación", "criterion": "Variaciones materiales explicadas por la administración",
             "source": "NIA 315 párr. 14 b); NIA 520"},
            {"code": "PLA-03", "objective": "Estados resumidos e índices", "risk": "Condiciones financieras de riesgo no identificadas",
             "assertion": "Todas", "procedure": "Calcular los estados resumidos, el cuadre y los índices de liquidez, actividad, endeudamiento y rentabilidad",
             "evidence": "Estados resumidos e índices", "criterion": "Índices con semáforo y lectura", "source": "NIA 315 párr. A31; NIA 570 párr. A3"},
            {"code": "PLA-04", "objective": "Materialidad", "risk": "Materialidad inadecuada para los usuarios",
             "assertion": "Todas", "procedure": "Elegir la base y el porcentaje, calcular la materialidad global, de desempeño y el umbral claramente insignificante",
             "evidence": "Bases de materialidad", "criterion": "Materialidades calculadas y justificadas", "source": "NIA 320 párr. 10–11 y 14; NIA 450 párr. 5"},
            {"code": "PLA-05", "objective": "Identificación y valoración de riesgos", "risk": "Riesgos significativos sin respuesta",
             "assertion": "Todas", "procedure": "Valorar los hallazgos de la carta de control interno y los riesgos de los balances, de fraude y de empresa en funcionamiento",
             "evidence": "Carta de control interno; matriz de riesgos", "criterion": "Cada riesgo con nivel y respuesta",
             "source": "NIA 315 párr. 28–32; NIA 240 párr. 26–27, 31; NIA 570 párr. 10; NIA 265"},
            {"code": "PLA-06", "objective": "Saldos de apertura", "risk": "Saldos iniciales distintos de los estados auditados",
             "assertion": "Existencia, integridad", "procedure": "Cotejar el balance del cierre anterior con las notas a los estados financieros auditados",
             "evidence": "Notas del año anterior", "criterion": "Diferencias en cero o explicadas", "source": "NIA 510 párr. 6"},
            {"code": "PLA-07", "objective": "Programa, estrategia y plan", "risk": "Trabajo sin alcance, oportunidad ni recursos definidos",
             "assertion": "Todas", "procedure": "Definir las cuentas a revisar, el programa por riesgo con su herramienta del catálogo y la estrategia global",
             "evidence": "Programa y memorando de estrategia", "criterion": "Aprobados por el socio", "source": "NIA 300 párr. 7–12; NIA 330 párr. 5–7 y 18"},
            {"code": "PLA-08", "objective": "Comunicación con los responsables del gobierno", "risk": "Gobierno sin conocer el alcance ni los riesgos",
             "assertion": "Todas", "procedure": "Comunicar el alcance y el momento planificados y los riesgos significativos",
             "evidence": "Comunicación escrita o acta de reunión", "criterion": "Comunicación documentada", "source": "NIA 260 párr. 15"},
            {"code": "PLA-09", "objective": "Aceptación, condiciones del encargo, ética e independencia",
             "risk": "Aceptar o continuar un encargo sin condiciones previas, sin independencia o sin recursos",
             "assertion": "Encargo", "procedure": "Documentar la aceptación y continuidad, las condiciones previas, la carta de encargo, "
                                                  "el equipo y sus confirmaciones de independencia",
             "evidence": "Registros de la plataforma (independencia, aceptación y carta de encargo firmada)",
             "criterion": "Sin preguntas pendientes ni alertas sin resolver", "source": "NIGC 1; NIA 210; NIA 220 (Revisada); Código IESBA"},
            {"code": "PLA-10", "objective": "Discusión del equipo, fraude y control interno",
             "risk": "Riesgos de fraude o deficiencias de control no identificados",
             "assertion": "Todas", "procedure": "Documentar la discusión del equipo, las indagaciones y los factores de riesgo de fraude, "
                                                "los cinco componentes del control interno y los controles generales de TI",
             "evidence": "Carta de control interno, balances, informe anterior y registros de asistencia de la plataforma",
             "criterion": "Cada alerta con su riesgo y respuesta",
             "source": "NIA 315 (Revisada 2019) párr. 17 y 21–26; NIA 240 párr. 15–24"},
            {"code": "PLA-11", "objective": "Diferencias de auditoría (NIA 450)",
             "risk": "Incorrecciones acumuladas materiales", "assertion": "Todas",
             "procedure": "Acumular las diferencias de apertura y las salvedades no corregidas frente a la materialidad",
             "evidence": "Notas del año anterior (RQ-006) e informe anterior (RQ-005)", "criterion": "Acumulado bajo la materialidad",
             "source": "NIA 450 párr. 5 y 11; NIA 510 párr. 6"},
        ],
        "requests": [
            req("RQ-001", "Balance de comprobación al cierre del año anterior (auditado), con todas las cuentas y niveles",
                "balance_anterior", "PLA-02", "Análisis horizontal, saldos de apertura y base de la materialidad en la revisión preliminar",
                content=bc),
            req("RQ-002", "Balance de comprobación a la fecha de corte que se audita, con todas las cuentas y niveles",
                "balance_actual", "PLA-02", "Análisis horizontal, estados resumidos, índices y materialidad", content=bc),
            req("RQ-003", "Estado de resultados del año anterior al mismo corte (solo revisión preliminar)", "resultados_mismo_corte", "PLA-02",
                "Comparar ingresos, costos y gastos del mismo número de meses", required=False,
                content="Cuentas de ingresos, costos y gastos (códigos 4 en adelante) con su saldo al mismo corte del año anterior. "
                        "Si no se entrega, se prorratea el año anterior: diciembre ÷ 12 × meses transcurridos."),
            req("RQ-004", "Carta de control interno (hallazgos) con su calificación", "carta_control_interno", "PLA-05",
                "Matriz de riesgos del encargo", required=False, formats=("pdf", "docx", "xlsx", "csv"),
                content="Una fila por hallazgo de la carta de control interno: código, proceso, hallazgo, aseveraciones, "
                        "probabilidad, impacto y control de 1 a 5 (el socio los califica) y la respuesta de auditoría. "
                        "Puede subir la carta firmada en PDF o Word (la IA extrae la tabla, que usted revisa y confirma) "
                        "o transcribirla en Excel/CSV."),
            req("RQ-005", "Informe de auditoría del año anterior (identificación, opinión y asuntos)", "informe_anterior", "PLA-01",
                "Perfil del encargo y asuntos que pueden persistir", required=False, formats=("pdf", "docx", "xlsx", "csv"),
                content="Una fila por dato o asunto del informe: concepto, tipo (" + ", ".join(TIPOS_INFORME) + "), detalle, "
                        "importe si lo tiene y la fuente (párrafo o nota). Puede subir el informe firmado en PDF o Word "
                        "(la IA extrae la tabla, que usted revisa y confirma) o transcribirlo en Excel/CSV."),
            req("RQ-006", "Notas a los estados financieros auditados del año anterior (total de cada nota)", "notas_estados_financieros", "PLA-06",
                "Notas comparativas y saldos de apertura", required=False, formats=("pdf", "docx", "xlsx", "csv"),
                content="Una fila por nota de balance: número, título, códigos del balance que la forman (separados por coma) y "
                        "el saldo auditado de la nota. Puede subir las notas firmadas en PDF o Word (la IA extrae la tabla, "
                        "que usted revisa y confirma) o transcribirlas en Excel/CSV."),
            req("RQ-009", "Composición de las notas a los estados financieros auditados del año anterior (líneas de cada nota)",
                "notas_detalle", "PLA-06", "Desglose de cada nota y su cuadre con el saldo auditado", required=False,
                content="Una fila por línea de cada nota, tal como la presenta el informe auditado: número de nota, concepto, "
                        "importe y tipo (Saldo si forma el saldo, Movimiento si es la conciliación del año, Total si es el total)."),
            req("RQ-007", "Informe de auditoría, notas y carta de control interno del año anterior (documentos firmados)", None, "PLA-01",
                "Respaldo de los datos transcritos en RQ-004 a RQ-006", formats=("pdf", "docx"), use="soporte", required=False),
            req("RQ-008", "RUC actualizado de la entidad", "ruc_certificado", "PLA-01",
                "Identificación de la entidad, su actividad económica (CIIU) y sus obligaciones tributarias", required=False,
                formats=("pdf", "docx", "xlsx", "csv"),
                content="Datos del certificado del RUC (SRI): razón social, número de RUC, representante legal, actividades "
                        "económicas (CIIU), si está obligado a llevar contabilidad, tipo de contribuyente, agente de retención, "
                        "contribuyente especial, obligaciones tributarias, establecimientos y jurisdicción. Suba el certificado en "
                        "PDF (la IA lo lee y usted revisa) o transcríbalo en Excel/CSV."),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo (M19): «Comercial Andina de Ejemplo S.A.», cifras ficticias -------------------------------------------------

_NOMBRES = {
    "1": "ACTIVO", "11": "ACTIVO CORRIENTE", "1101": "EFECTIVO Y EQUIVALENTES", "110101": "Caja general", "110102": "Bancos locales",
    "1102": "INVERSIONES TEMPORALES", "1103": "CUENTAS POR COBRAR CLIENTES", "110301": "Clientes locales",
    "110302": "(-) Provisión cuentas incobrables", "110303": "Cuentas por cobrar compañías relacionadas", "1104": "INVENTARIOS", "110401": "Inventario de mercadería",
    "1105": "ACTIVOS POR IMPUESTOS CORRIENTES", "1106": "OTRAS CUENTAS POR COBRAR", "110601": "Anticipos a empleados",
    "12": "ACTIVO NO CORRIENTE", "1201": "PROPIEDAD, PLANTA Y EQUIPO", "120101": "Terrenos y edificios", "120102": "Maquinaria y equipo",
    "120103": "(-) Depreciación acumulada", "1202": "ACTIVOS POR DERECHO DE USO", "1203": "ACTIVOS INTANGIBLES",
    "2": "PASIVO", "21": "PASIVO CORRIENTE", "2101": "CUENTAS Y DOCUMENTOS POR PAGAR", "210101": "Proveedores locales",
    "210102": "Préstamos de accionistas",
    "2102": "OBLIGACIONES BANCARIAS CORTO PLAZO", "2103": "IMPUESTOS POR PAGAR", "2104": "BENEFICIOS SOCIALES POR PAGAR",
    "2105": "PASIVO POR ARRENDAMIENTO CORRIENTE", "22": "PASIVO NO CORRIENTE", "2201": "OBLIGACIONES BANCARIAS LARGO PLAZO",
    "2202": "JUBILACIÓN PATRONAL Y DESAHUCIO", "2203": "PASIVO POR ARRENDAMIENTO NO CORRIENTE",
    "3": "PATRIMONIO", "31": "CAPITAL", "3101": "Capital social", "32": "RESERVAS", "3201": "Reserva legal", "33": "RESULTADOS",
    "3301": "Resultados acumulados",
    "4": "INGRESOS", "41": "INGRESOS ORDINARIOS", "4101": "Ventas netas", "43": "OTROS INGRESOS", "4301": "Otros ingresos",
    "5": "GASTOS", "51": "GASTOS DE ADMINISTRACIÓN Y VENTAS", "5101": "Sueldos y beneficios sociales",
    "5102": "Gastos de administración y ventas", "5103": "Depreciaciones y amortizaciones", "52": "GASTOS FINANCIEROS",
    "5201": "Intereses bancarios", "53": "IMPUESTO A LA RENTA", "5301": "Impuesto a la renta del ejercicio",
    "6": "COSTOS", "61": "COSTO DE VENTAS", "6101": "Costo de ventas",
}
# Saldos por naturaleza (positivos) de las cuentas de detalle: cierre 2024 y cierre 2025.
_DIC24 = {"110101": 4900, "110102": 172000, "1102": 120000, "110301": 690500, "110302": -45900, "110401": 655400, "1105": 60100,
          "110601": 11900, "120101": 900000, "120102": 410000, "120103": -380900, "1202": 102000, "1203": 41300,
          "210101": 561200, "2102": 180000, "2103": 66900, "2104": 83600, "2105": 32000, "2201": 440000, "2202": 137800, "2203": 69900,
          "3101": 700000, "3201": 78600, "3301": 94750,
          "4101": 4215300, "4301": 17200, "5101": 441300, "5102": 368900, "5103": 63100, "5201": 55200, "5301": 98850, "6101": 2908600}
_DIC25 = {"110101": 5400, "110102": 180000, "1102": 120000, "110301": 812300, "110302": -48700, "110401": 956800, "1105": 64200,
          "110601": 12300, "120101": 900000, "120102": 480000, "120103": -412600, "1202": 96000, "1203": 38500,
          "210101": 604300, "2102": 250000, "2103": 71400, "2104": 88900, "2105": 34100, "2201": 420000, "2202": 146200, "2203": 64800,
          "3101": 700000, "3201": 96400, "3301": 360450,
          "4101": 4860500, "4301": 18400, "5101": 468900, "5102": 391700, "5103": 67500, "5201": 58300, "5301": 122550, "6101": 3402300}


def _tb(saldos: dict, clave: str, solo_resultados: bool = False) -> list[dict]:
    """Balance de comprobación como lo exporta el sistema: todas las cuentas con su total, deudor + y acreedor −."""
    filas = []
    for c in sorted(_NOMBRES):
        if solo_resultados and c[0] not in "4567":
            continue
        hojas_ = [h for h in saldos if h.startswith(c)]
        if not hojas_:
            continue
        v = sum(saldos[h] for h in hojas_) * (-1 if c[0] in "234" else 1)
        filas.append({"codigo": c, "cuenta": _NOMBRES[c], clave: f"{v:.2f}", "_row": len(filas) + 2})
    return filas


def _ci(id, proceso, hallazgo, aser, p, i, c, resp, probar=""):
    return {"id": id, "proceso": proceso, "hallazgo": hallazgo, "aseveraciones": aser, "probabilidad": p, "impacto": i,
            "control": c, "respuesta": resp, "probar_control": probar, "_row": 2}


_CARTA_EJ = [
    _ci("R01", "Ingresos", "Notas de crédito emitidas después del cierre sin aprobación de la gerencia.", "Ocurrencia; corte",
        "4", "5", "1", "Revisar las notas de crédito de enero y su aprobación; prueba de corte de la última semana de diciembre."),
    _ci("R02", "Inventarios", "No se realizan tomas físicas periódicas y las diferencias con el kárdex no se concilian.",
        "Existencia; valuación", "4", "4", "2", "Observar la toma física al cierre y conciliar el kárdex con la contabilidad."),
    _ci("R03", "Cuentas por cobrar", "La provisión de incobrables no se calcula con un modelo de pérdida crediticia esperada.",
        "Valuación", "4", "4", "2", "Recalcular la pérdida crediticia esperada con la antigüedad de la cartera (NIIF 9)."),
    _ci("R04", "Beneficios a empleados", "El cálculo actuarial de jubilación patronal no se actualizó en el año.", "Valuación; integridad",
        "3", "4", "3", "Obtener el estudio actuarial al cierre y evaluar la competencia del actuario (NIA 500 y 620).", "Sí"),
    _ci("R05", "Sistema ERP y accesos", "Usuarios con acceso de administrador en el ERP sin segregación de funciones.", "Todas",
        "4", "4", "1", "Evaluar los controles generales de TI y ampliar las pruebas de asientos de diario."),
    _ci("R06", "Caja y bancos", "Conciliaciones bancarias sin firma de revisión.", "Existencia", "", "3", "", ""),
]
_INFORME_EJ = [
    {"concepto": "Entidad auditada", "tipo": "Identificación", "detalle": "Comercial Andina de Ejemplo S.A. (datos ficticios)",
     "importe": "", "fuente": "Informe 2024 · Nota 1", "_row": 2},
    {"concepto": "Actividad", "tipo": "Identificación", "detalle": "Comercialización al por mayor de productos de consumo masivo",
     "importe": "", "fuente": "Informe 2024 · Nota 1", "_row": 3},
    {"concepto": "RUC", "tipo": "Identificación", "detalle": "0999999999001 (ficticio)", "importe": "",
     "fuente": "Informe 2024 · Nota 1", "_row": 4},
    {"concepto": "País y moneda funcional", "tipo": "Identificación", "detalle": "Ecuador · dólar de los Estados Unidos (USD)",
     "importe": "", "fuente": "Informe 2024 · Nota 2", "_row": 5},
    {"concepto": "Opinión del año anterior", "tipo": "Opinión", "detalle": "Con salvedades (por el asunto de jubilación patronal)",
     "importe": "", "fuente": "Informe 2024 · Opinión", "_row": 6},
    {"concepto": "Jubilación patronal", "tipo": "Salvedad",
     "detalle": "La provisión no se ajustó al cálculo actuarial al cierre; el pasivo estaría subestimado.",
     "importe": "18500.00", "fuente": "Informe 2024 · Fundamento de la opinión", "_row": 7},
    {"concepto": "Proveedor principal vinculado", "tipo": "Entendimiento",
     "detalle": "El 60 % de las compras se hace a un proveedor del exterior vinculado al accionista mayoritario.",
     "importe": "", "fuente": "Informe 2024 · Nota 20 (partes relacionadas)",
     "enfoque": "Riesgo de partes relacionadas y precios de transferencia: confirmar saldos y evaluar los términos (NIA 550).",
     "_row": 8},
    {"concepto": "Ventas concentradas en el último trimestre", "tipo": "Entendimiento",
     "detalle": "Cerca del 40 % de las ventas del año se factura entre octubre y diciembre (temporada navideña).",
     "importe": "", "fuente": "Informe 2024 · Nota 18 (ingresos)",
     "enfoque": "Riesgo de corte de ingresos al cierre: ampliar la prueba de corte y revisar las notas de crédito posteriores (NIA 240).",
     "_row": 9},
    {"concepto": "Constitución e historia", "tipo": "Contexto",
     "detalle": "Sociedad anónima constituida en 1998; distribuye productos de consumo masivo en la Costa y la Sierra.",
     "importe": "", "fuente": "Informe 2024 · Nota 1", "_row": 10},
    {"concepto": "Sistema de información", "tipo": "Contexto",
     "detalle": "ERP integrado para ventas, inventarios y contabilidad, con cierres mensuales.",
     "importe": "", "fuente": "Carta de control interno 2024", "_row": 11},
]
_NOTAS_DEF = [("3", "Efectivo y equivalentes de efectivo", ["1101"]), ("4", "Cuentas por cobrar comerciales y otras", ["1103", "1106"]),
              ("5", "Inventarios", ["1104"]), ("6", "Propiedad, planta y equipo", ["1201"]), ("10", "Obligaciones bancarias", ["2102", "2201"]),
              ("12", "Cuentas y documentos por pagar", ["2101"]), ("13", "Beneficios a empleados", ["2104", "2202"])]


def _notas_de(saldos: dict, movimientos: dict | None = None, dif13: float = 1000.0) -> tuple[list, list]:
    """Notas del año anterior (total de cada nota) y su composición línea por línea, a partir de los saldos auditados.
    La nota 13 lleva a propósito 1.000 más que el balance (beneficios sociales) para ejercitar el control NIA 510."""
    notas, det = [], []
    for k, (n, titulo, pref) in enumerate(_NOTAS_DEF):
        lineas = [(_NOMBRES[h].strip().capitalize(), float(saldos[h])) for h in sorted(saldos) if any(h.startswith(pf) for pf in pref)]
        if n == "13":
            lineas[0] = (lineas[0][0], lineas[0][1] + dif13)
        total = sum(v for _, v in lineas)
        notas.append({"nota": n, "titulo": titulo, "codigos": ", ".join(pref), "saldo_auditado": f"{total:.2f}", "_row": k + 2})
        for c, v in lineas + [("Total", total)]:
            det.append({"nota": n, "concepto": c, "importe": f"{v:.2f}", "tipo": "Total" if c == "Total" else "Saldo",
                        "_row": len(det) + 2})
        for c, v in (movimientos or {}).get(n, []):
            det.append({"nota": n, "concepto": c, "importe": f"{v:.2f}", "tipo": "Movimiento", "_row": len(det) + 2})
    return notas, det


# Movimiento del año de propiedad, planta y equipo (informativo): saldo inicial + adiciones − depreciación = saldo final.
_NOTAS_EJ, _NOTAS_DET_EJ = _notas_de(_DIC24, {"6": [("Saldo al inicio del año", 950000.0), ("Adiciones", 42200.0),
                                                  ("Depreciación del año", -63100.0)]})

# Ejemplo de control (a mano): activo 3.204.200 = pasivo 1.679.700 + patrimonio 1.156.850 + resultado 367.650.
# Ingresos 4.878.900 × 1 % = materialidad 48.789,00; desempeño 50 % = 24.394,50; trivial 5 % = 2.439,45.
# Nota 13: balance 83.600 + 137.800 = 221.400 contra 222.400 auditado → diferencia −1.000 (NIA 510).
def _mi(integrante, rol, anios, fecha="2025-09-10", amenazas="", salvaguardas=""):
    return {"integrante": integrante, "rol": rol, "fecha": fecha, "amenazas": amenazas, "salvaguardas": salvaguardas, "anios": anios}


# Registros con un clic en la plataforma del ejemplo ficticio (la plataforma los inyecta en parametros["_encargo"]).
_REGISTROS_EJ = {
    "equipo": [_mi("CPA Andrea Vélez (ficticio)", "Socio", 3), _mi("CPA Luis Mora (ficticio)", "Gerente", 3),
               _mi("Ana Torres (ficticio)", "Senior", 2, "2025-09-11", "Un familiar trabaja en el área de ventas del cliente",
                   "No participa en las pruebas de ingresos; revisión del gerente"),
               _mi("Pedro Ruiz (ficticio)", "Asistente", 1, "2025-09-12", "Tiene acciones de una empresa relacionada del cliente")],
    "asistencia": [{"integrante": "CPA Andrea Vélez (ficticio)", "rol": "Socio", "fecha": "2025-10-10"},
                   {"integrante": "CPA Luis Mora (ficticio)", "rol": "Gerente", "fecha": "2025-10-10"},
                   {"integrante": "Ana Torres (ficticio)", "rol": "Senior", "fecha": "2025-10-10"}],
    "aceptacion": {"actor": "CPA Andrea Vélez (ficticio)", "fecha": "2025-09-01"},
    "carta": {"actor": "CPA Luis Mora (ficticio)", "fecha": "2025-09-05", "detalle": ""},
    "comunicacion": {"actor": "CPA Andrea Vélez (ficticio)", "fecha": "2025-10-20", "detalle": "Reunión con el directorio"},
}
_REGISTROS_EIP = {**_REGISTROS_EJ, "enfoque": [
    {"ciclo": "Tesorería y financiamiento", "decision": "Sustantivo", "actor": "CPA Andrea Vélez (ficticio)", "fecha": "2025-10-15",
     "motivo": "Las conciliaciones bancarias no se revisan: preferimos pruebas sustantivas."}], "indagaciones": [
    {"actor": "CPA Luis Mora (ficticio)", "fecha": "2025-10-12", "tema": "Partes relacionadas", "procedimiento": "Indagación",
     "persona": "Gerente general (ficticio)", "resumen": "Los préstamos de accionistas y la cuenta con la relacionada son nuevos en 2025."},
    {"actor": "Ana Torres (ficticio)", "fecha": "2025-10-13", "tema": "Sector, actividad y regulación", "procedimiento": "Observación",
     "persona": "Jefe de bodega (ficticio)", "resumen": "Recorrido por la bodega principal y el proceso de despacho."}],
    "consultas": [
    {"actor": "CPA Luis Mora (ficticio)", "fecha": "2025-10-14", "tipo": "consulta", "tema": "Tratamiento del litigio laboral",
     "estado": "Abierta", "detalle": "Consulta al área técnica sobre la provisión."}],
    "equipo": [_mi("CPA Andrea Vélez (ficticio)", "Socio", 7), *_REGISTROS_EJ["equipo"][1:3],
                                              _mi("CPA Marta Ríos (ficticio)", "Revisor de calidad", 2)]}


_ANTERIOR_EJ = {"version": 1, "fecha": "2025-10-20",
                "totales": {"materialidad": "45000.00", "desempeno": "22500.00", "trivial": "2250.00"},
                "riesgos": [{"rubro": "Ingresos", "cond": "Presunción de fraude en el reconocimiento de ingresos", "sev": "Significativo",
                             "presenta": "Sí", "riesgo": "Incorrección material por fraude en ingresos (ocurrencia y corte)"},
                            {"rubro": "Liquidez", "cond": "Razón corriente menor a 1", "sev": "Alto", "presenta": "Sí",
                             "riesgo": "El activo corriente no cubre el pasivo corriente"}]}


EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"tipoRevision": "Final", "baseMaterialidad": "Ingresos", "pctIngresos": 1, "pctDesempeno": 50, "pctTrivial": 5,
                   "fechaPreliminar": "2025-10-15", "fechaFinal": "2026-01-20", "fechaInforme": "2026-03-31",
                   "socio": "CPA Andrea Vélez (ficticio)", "gerente": "CPA Luis Mora (ficticio)",
                   "expertos": "Actuario para jubilación patronal",
                   "_encargo": {"registros": _REGISTROS_EJ, "firma": "Audit Consulting"}},
    "datasets": {"balance_anterior": _tb(_DIC24, "saldo_anterior"), "balance_actual": _tb(_DIC25, "saldo_actual"),
                 "carta_control_interno": _CARTA_EJ, "informe_anterior": _INFORME_EJ, "notas_estados_financieros": _NOTAS_EJ,
                 "notas_detalle": _NOTAS_DET_EJ},
}

# Revisión preliminar al 31-ago-2026: balance de diciembre 2025 contra agosto 2026; resultados de agosto 2026 contra
# agosto 2025 (8 meses). Bancos cuadra el balance: pasivo + patrimonio + resultado − demás activos.
_AGO26 = {"110101": 6100, "1102": 120000, "110301": 905400, "110302": -50100, "110401": 1012300, "1105": 58900, "110601": 14800,
          "120101": 900000, "120102": 505000, "120103": -457600, "1202": 92000, "1203": 36600,
          "210101": 655800, "2102": 300000, "2103": 64300, "2104": 97500, "2105": 34900, "2201": 380000, "2202": 150200, "2203": 61400,
          "3101": 700000, "3201": 96400, "3301": 728100,
          "4101": 3420000, "4301": 11000, "5101": 322000, "5102": 268000, "5103": 46000, "5201": 40000, "5301": 72000, "6101": 2410000}
_res26 = 3420000 + 11000 - (322000 + 268000 + 46000 + 40000 + 72000 + 2410000)
_pas26 = sum(_AGO26[c] for c in _AGO26 if c[0] in "23")
_AGO26["110102"] = _pas26 + _res26 - sum(_AGO26[c] for c in _AGO26 if c[0] == "1")
_AGO25 = {"4101": 2980000, "4301": 10500, "5101": 300000, "5102": 250000, "5103": 42000, "5201": 37000, "5301": 60000, "6101": 2120000}
_PRELIM = {"balance_anterior": _tb(_DIC25, "saldo_anterior"), "balance_actual": _tb(_AGO26, "saldo_actual"),
           "resultados_mismo_corte": _tb(_AGO25, "saldo_eri", solo_resultados=True), "carta_control_interno": _CARTA_EJ, "informe_anterior": _INFORME_EJ,
           "notas_estados_financieros": _notas_de(_DIC25)[0], "notas_detalle": _notas_de(_DIC25)[1]}

# Pérdida (NIIF para las PYMES, encargo inicial, sin documentos del año anterior): costo de ventas +700.000 y sin impuesto;
# proveedores +577.450 para que el balance siga cuadrando. Utilidad antes de participación e impuestos = −209.800.
_PERD25 = {**_DIC25, "6101": 4102300, "5301": 0, "210101": 604300 + 577450}
# Patrimonio en déficit: resultados acumulados pasan a +1.800.000 (deudor); bancos baja lo mismo. Debe verse negativo (R2).
_DEF = 2160450
_DELTA_DEF = {"3301": _DEF, "33": _DEF, "3": _DEF, "110102": -_DEF, "1101": -_DEF, "11": -_DEF, "1": -_DEF}
_DEFICIT = [{**x, "saldo_actual": f"{float(x['saldo_actual']) + _DELTA_DEF[x['codigo']]:.2f}"} if x["codigo"] in _DELTA_DEF else x
            for x in _tb(_DIC25, "saldo_actual")]
_EIP_DATOS = {**EJEMPLO["datasets"],
              "balance_actual": _tb({**_DIC25, "110303": 50000, "210102": 50000}, "saldo_actual"),
              "carta_control_interno": [*_CARTA_EJ, _ci("R07", "Nómina", "La nómina se procesa en una empresa tercerizada y hay un "
                                                    "litigio laboral pendiente con ex trabajadores.", "Integridad", "3", "3", "3", "")]}
ESCENARIOS = [
    ("base", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("preliminar_eri", _PRELIM, {"tipoRevision": "Preliminar", "mesesTranscurridos": 8, "baseMaterialidad": "Ingresos"}, "2026-08-31"),
    ("preliminar_prorrateo", {k: v for k, v in _PRELIM.items() if k != "resultados_mismo_corte"},
     {"tipoRevision": "Preliminar", "mesesTranscurridos": 8, "baseMaterialidad": "Activos totales"}, "2026-08-31"),
    ("perdida_pymes", {"balance_anterior": _tb(_DIC24, "saldo_anterior"), "balance_actual": _tb(_PERD25, "saldo_actual")},
     {"baseMaterialidad": "Utilidad antes de impuestos", "pctUAI": 5, "encargoInicial": "Sí", "_marco": MARCO_PYMES}, "2025-12-31"),
    ("patrimonio_deficit", {"balance_anterior": _tb(_DIC24, "saldo_anterior"), "balance_actual": _DEFICIT,
                            "carta_control_interno": _CARTA_EJ, "notas_estados_financieros": _NOTAS_EJ, "notas_detalle": _NOTAS_DET_EJ},
     {"baseMaterialidad": "Activos totales", "estadosAnteriores": "No auditados"}, "2025-12-31"),
    # Entidad de interés público: revisor de calidad registrado y un socio que alcanzó los años de rotación; además (M1–M21)
    # partes relacionadas nuevas, nómina tercerizada con un litigio, indagaciones, consultas y la versión anterior.
    ("eip", _EIP_DATOS, {**EJEMPLO["parametros"], "interesPublico": "Sí", "_anterior": _ANTERIOR_EJ,
                         "_encargo": {"registros": _REGISTROS_EIP, "firma": "Audit Consulting",
                                      "ficha": {"activity": "Comercialización al por mayor de productos de consumo masivo"}}},
     "2025-12-31"),
]
