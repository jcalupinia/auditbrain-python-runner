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
  opinión, salvedades, énfasis, empresa en marcha, asuntos clave).
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
   de fraude en ingresos y elusión de controles (NIA 240); indicios de empresa en marcha (NIA 570); asuntos
   del informe anterior. Control de calidad, anomalías, cuentas principales a revisar, programa (NIA 330),
   narrativa y estrategia global (NIA 300).

Las NIA se citan por su numeración en la versión en español del IAASB (NIA clarificadas; NIA 315 Revisada
2019). Pendiente M03: cotejar cada párrafo citado con el texto oficial vigente (VERIFICAR).
"""
from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

from backend.app.aud.niif.procesadores import problemas as _pr
from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num lo usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_fecha, a_num, campo, es_pymes, fx, hoja, m, n2, norm, problema, r2, ref, req,
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
]
TIPOS_INFORME = ("Identificación", "Opinión", "Salvedad", "Énfasis", "Empresa en marcha", "Asunto clave", "Otro asunto")
_INFORME = [
    campo("concepto", "Concepto", alias=("concepto", "asunto", "tema"), ejemplo="Jubilación patronal"),
    campo("tipo", "Tipo", alias=("tipo", "clase", "categoria", "categoría"), ejemplo="Salvedad"),
    campo("detalle", "Detalle", alias=("detalle", "descripcion", "descripción", "texto"),
          ejemplo="La provisión no se ajustó al cálculo actuarial al cierre."),
    campo("importe", "Importe (USD)", "number", requerido=False, alias=("importe", "monto", "valor", "efecto"), ejemplo="18500.00"),
    campo("fuente", "Fuente o referencia", requerido=False, alias=("fuente", "referencia", "pagina", "página", "parrafo", "párrafo"),
          ejemplo="Informe 2024 · Fundamento de la opinión"),
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
CAMPOS = {"balance_anterior": _BAL_ANT, "balance_actual": _BAL_ACT, "resultados_mismo_corte": _ERI_ANT, "carta_control_interno": _CARTA,
          "informe_anterior": _INFORME, "notas_estados_financieros": _NOTAS}
TIPOS = {k: k for k in CAMPOS}
DATASETS = tuple(TIPOS)
PRINCIPAL = "balance_actual"
CONTROL = "saldo_actual"

# --- parámetros ---------------------------------------------------------------------------------------------------

CLASIFICACIONES = ("Activo", "Activo corriente", "Activo no corriente", "Pasivo", "Pasivo corriente", "Pasivo no corriente",
                   "Patrimonio", "Ingresos", "Costos", "Gastos", "Otros")
SECCIONES = ("Activo", "Pasivo", "Patrimonio", "Ingresos", "Costos", "Gastos", "Otros")
MAPA_DEFECTO = ("1=Activo; 11=Activo corriente; 12=Activo no corriente; 101=Activo corriente; 102=Activo no corriente; "
                "2=Pasivo; 21=Pasivo corriente; 22=Pasivo no corriente; 201=Pasivo corriente; 202=Pasivo no corriente; "
                "3=Patrimonio; 4=Ingresos; 5=Gastos; 6=Costos; 7=Gastos")
UAI = "Utilidad antes de participación e impuestos"
BASES = ("Ingresos", "Activos totales", "Patrimonio", "Gastos totales", UAI)
_ALIAS_BASE = {"ingresos": "Ingresos", "ventas": "Ingresos", "activos": "Activos totales", "activostotales": "Activos totales",
               "activo": "Activos totales", "patrimonio": "Patrimonio", "gastos": "Gastos totales", "gastostotales": "Gastos totales",
               "costosygastos": "Gastos totales", "utilidadantesdeimpuestos": UAI, "uai": UAI,
               "utilidadantesdeparticipacioneimpuestos": UAI}
PERIODOS_BASE = ("Automático", "Año anterior", "Corte actual")
PARAMETROS = {
    "tipoRevision": "Final", "mesesTranscurridos": 12, "mapaCuentas": MAPA_DEFECTO,
    "baseMaterialidad": "Ingresos", "periodoBase": "Automático",
    "pctIngresos": 1, "pctActivos": 1, "pctPatrimonio": 1, "pctGastos": 0.5, "pctUAI": 5,
    "pctDesempeno": 50, "pctTrivial": 5, "justificacion": "",
    "umbralVarPct": 15, "umbralVarExtrema": 100, "umbralAlto": 15, "umbralMedio": 8, "umbralDiasRotacion": 15,
    "encargoInicial": "No", "interesPublico": "No", "auditoriaGrupo": "No",
    "refutarIngresos": "No", "motivoRefutacion": "",
    "enfoque": "Sustantivo con pruebas de controles clave",
    "fechaPreliminar": "", "fechaFinal": "", "fechaInforme": "",
    "socio": "", "gerente": "", "expertos": "",
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
    "umbralAlto": "Matriz de riesgos: riesgo residual desde el cual el nivel es Alto (escala 1–25)",
    "umbralMedio": "Matriz de riesgos: riesgo residual desde el cual el nivel es Medio (escala 1–25)",
    "encargoInicial": "Encargo inicial: primer año de auditoría (Sí / No)",
    "interesPublico": "Entidad de interés público o cotizada (Sí / No)",
    "auditoriaGrupo": "Auditoría de un grupo o de un componente (Sí / No)",
    "refutarIngresos": "Se refuta la presunción de fraude en el reconocimiento de ingresos (Sí / No)",
    "motivoRefutacion": "Motivo documentado de la refutación (NIA 240 párr. 47)",
    "enfoque": "Enfoque general de la auditoría",
    "fechaPreliminar": "Fecha de la visita preliminar",
    "fechaFinal": "Fecha de la visita final",
    "fechaInforme": "Fecha prevista de entrega del informe",
    "socio": "Socio del encargo", "gerente": "Gerente o encargado del equipo",
    "expertos": "Uso de expertos (actuario, tasador, especialista en TI…)",
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


def _tipo_informe(v) -> str | None:
    k = norm(v)
    return next((t for t in TIPOS_INFORME if norm(t) == k), None)


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
    """a es una cuenta superior de c (regla del código de la fila c)."""
    return len(a) < len(c) and ((c + ".").startswith(a + ".") if "." in c else c.startswith(a))


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
        if _busca(nombre, "bancari", "financ", "préstamo", "prestamo", "sobregiro"):
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
                    "saldo": float(v) if v is not None else 0.0, "_row": f.get("_row")})
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


SEV_INFORME = {"Salvedad": "Alto", "Empresa en marcha": "Alto", "Énfasis": "Medio", "Asunto clave": "Medio", "Otro asunto": "Bajo"}
NORMA_INFORME = {"Salvedad": "NIA 705 y 710", "Empresa en marcha": "NIA 570", "Énfasis": "NIA 706", "Asunto clave": "NIA 701",
                 "Otro asunto": "NIA 706"}
EFECTO_INFORME = {
    "Identificación": "Dato del perfil del encargo (entidad, actividad, marco, período).",
    "Opinión": "Punto de partida: si la opinión fue modificada, evaluar si la causa persiste (NIA 710).",
    "Salvedad": "Riesgo alto: verificar si el asunto se corrigió; si persiste, afecta la opinión de este año (NIA 705 y 710).",
    "Énfasis": "Evaluar si el asunto sigue vigente y su revelación (NIA 706).",
    "Empresa en marcha": "Riesgo alto: actualizar la evaluación de la administración y la revelación (NIA 570).",
    "Asunto clave": "Considerar como posible riesgo significativo del año (NIA 701 y 315).",
    "Otro asunto": "Tener presente en la planificación (NIA 706).",
}
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
    ("ct", "Balances", "Capital de trabajo", "Capital de trabajo negativo", "Riesgo de liquidez y de empresa en marcha", "Alto",
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
     "Pérdidas: indicio de deterioro (NIC 36) y de empresa en marcha", "Alto", "NIA 570",
     "Evaluar la hipótesis de empresa en marcha y el deterioro de los activos de larga vida.", SIN_HERRAMIENTA),
    ("patrimonio", "Balances", "Patrimonio", "Patrimonio total nulo o negativo",
     "Patrimonio comprometido: causal de disolución y duda sobre la empresa en marcha", "Alto", "NIA 570",
     "Evaluar los planes de capitalización y la revelación de la incertidumbre material.", HERRAMIENTAS["Patrimonio"]),
    ("cartera", "Balances", "Cuentas por cobrar", "Días de cartera superiores a 90",
     "Posible incobrabilidad: evaluar el deterioro de la cartera (NIIF 9)", "Medio", "NIA 540",
     "Antigüedad de saldos, cobros posteriores y modelo de pérdida crediticia esperada.", HERRAMIENTAS["Cuentas por cobrar"]),
    ("inventario", "Balances", "Inventarios", "Días de inventario superiores a 120",
     "Lento movimiento: posible obsolescencia y ajuste al valor neto realizable (NIC 2)", "Medio", "NIA 501",
     "Rotación por ítem, valor neto realizable y observación de la toma física.", HERRAMIENTAS["Inventarios"]),
    ("rotCartera", "Balances", "Cuentas por cobrar", "Los días de cartera aumentaron más que el umbral de la hoja 02",
     "Deterioro de la cobranza: posible incobrabilidad (NIIF 9)", "Medio", "NIA 540",
     "Comparar la antigüedad de la cartera entre períodos y los cobros posteriores al corte.", HERRAMIENTAS["Cuentas por cobrar"]),
    ("rotInventario", "Balances", "Inventarios", "Los días de inventario aumentaron más que el umbral de la hoja 02",
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
    u_dias = _pnum(p, "umbralDiasRotacion", 0, 3650)
    if u_medio > u_alto:
        raise ValueError("Matriz de riesgos: el umbral Medio no puede superar al Alto.")
    sino = {k: _psino(p, k) for k in ("encargoInicial", "interesPublico", "auditoriaGrupo", "refutarIngresos")}
    fechas = {}
    for k in ("fechaPreliminar", "fechaFinal", "fechaInforme"):
        v = str(p.get(k) or "").strip()
        if v and a_fecha(v) is None:
            raise ValueError(f"{ETIQUETAS_PARAM[k]}: fecha inválida.")
        fechas[k] = a_fecha(v).isoformat() if v else None
    marco = MARCO_PYMES if es_pymes(p) else MARCO_COMPLETAS
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
        """R1: el saldo propio de la cuenta en ese balance; si no está, la suma de sus subcuentas de detalle."""
        propio = [x["pres"] for x in fuentes[k] if x["codigo"] == c]
        if propio:
            return propio[0]
        return sum(x["pres"] for x in fuentes[k] if x["detalle"] == "Sí" and _debajo(x["codigo"], c))

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
        archivos[ds] = (txt or ("Entregado por el cliente" if filas_ else "No entregado"), len(filas_))

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
        res = None if inh is None or co is None else inh * (6 - co) / 5
        nivel = "Pendiente de calificación" if res is None else "Alto" if res >= u_alto else "Medio" if res >= u_medio else "Bajo"
        proceso = str(f.get("proceso", "") or "").strip()
        hallazgo = str(f.get("hallazgo", "") or "").strip()
        carta.append({"id": str(f.get("id", "")).strip(), "proceso": proceso, "hallazgo": hallazgo,
                      "aser": str(f.get("aseveraciones", "") or "").strip(), "p": pr, "i": im, "c": co, "inh": inh, "res": res,
                      "nivel": nivel, "respuesta": str(f.get("respuesta", "") or "").strip(),
                      "herramienta": _herramienta(proceso + " " + hallazgo)})

    # 8 · informe del año anterior y notas
    informe = []
    for f in datasets.get("informe_anterior") or []:
        t = _tipo_informe(f.get("tipo")) or "Otro asunto"
        v = a_num(f.get("importe")) if str(f.get("importe", "") or "").strip() else None
        informe.append({"concepto": str(f.get("concepto", "") or "").strip(), "tipo": t, "detalle": str(f.get("detalle", "") or "").strip(),
                        "importe": None if v is None else float(v), "fuente": str(f.get("fuente", "") or "").strip()})
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

    # 9 · posibles riesgos (NIA 240, 570, balances e informe anterior) — mismo orden que la hoja 13
    ia, ip = ind["act"], est9["act"]
    # A2: en un corte parcial los días sobre 365 salen mayores; los umbrales se comparan con días × meses ÷ 12.
    fac = meses / 12 if prelim else 1.0

    def dvar(k):
        return None if ind["act"][k] is None or ind["ant"][k] is None else _xr(ind["act"][k] - ind["ant"][k], 2)
    valor = {"presuncion": ip["Ventas netas"], "elusion": None, "ct": ia["capitalTrabajo"], "rc": ia["razonCorriente"],
             "end": ia["endTotal"], "end80": ia["endTotal"], "perdida": ip["Utilidad neta"], "patrimonio": ip["PATRIMONIO TOTAL"],
             "cartera": ia["diasCartera"], "inventario": ia["diasInventario"], "rotCartera": dvar("diasCartera"),
             "rotInventario": dvar("diasInventario")}

    def presenta(cod_, v):
        if cod_ == "presuncion":
            return "No (refutada)" if sino["refutarIngresos"] == "Sí" else "Sí"
        if cod_ == "elusion":
            return "Sí"
        if v is None:
            return "No"
        return "Sí" if {"ct": v < 0, "rc": v < 1, "end": v > 70, "end80": v > 80, "perdida": v < 0, "patrimonio": v <= 0,
                        "cartera": v * fac > 90, "inventario": v * fac > 120, "rotCartera": v > u_dias,
                        "rotInventario": v > u_dias}[cod_] else "No"

    riesgos = []
    for cod_, origen, rubro, cond, rsg, sev, norma, resp, herr in _RIESGOS_BALANCE:
        riesgos.append({"cod": cod_, "origen": origen, "rubro": rubro, "cond": cond, "valor": valor[cod_],
                        "presenta": presenta(cod_, valor[cod_]), "riesgo": rsg, "sev": sev, "norma": norma, "resp": resp, "herr": herr})
    nivel3 = [x for x in cuentas if x["nivel"] == 3 and x["sec"] in SECCIONES[:6]]
    top_var = sorted([x for x in nivel3 if alcanza(x["var"])], key=lambda x: -abs(x["var"]))[:6]
    for x in top_var:
        riesgos.append({"cod": "variacion", "cuenta": x["codigo"], "origen": "Balances", "rubro": f"{x['codigo']} {x['cuenta']}",
                        "cond": "Variación superior a la materialidad de desempeño", "valor": x["var"], "presenta": "Sí",
                        "riesgo": "Variación material sin explicación documentada; requiere sustento", "sev": "Medio",
                        "norma": "NIA 520", "resp": "Obtener y corroborar la explicación de la administración.",
                        "herr": _herramienta(x["cuenta"], x["sec"])})
    for j, x in enumerate(informe):
        if x["tipo"] in SEV_INFORME:
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
    for k, r_ in enumerate(riesgos):
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
    anomalias = sorted(anomalias, key=lambda a: orden[a["sev"]])[:20]

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
        revisar.append({"x": x, "riesgo": rk["id"] if rk else "", "herr": _herramienta(x["cuenta"], x["sec"]),
                        "revisa": "Sí" if x["material"] == "Sí" or x["varMaterial"] == "Sí" or rk else "No"})
    revisar.sort(key=lambda r_: -abs(r_["x"]["act"]))

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
    if hay_eri and not prelim:
        probs.append(problema("ERI_NO_USADO", "Se entregó el estado de resultados del año anterior al mismo corte, pero la revisión "
                                              "es final: los resultados se comparan diciembre contra diciembre y ese anexo no se usa.", 0))

    n_altos = sum(1 for r_ in carta if r_["nivel"] == "Alto") + sum(
        1 for r_ in riesgos if r_["presenta"] == "Sí" and r_["sev"] in ("Alto", "Significativo"))
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
    detalle = {"corte": corte_a.isoformat(), "marco": marco, "tipo": tipo, "meses": meses, "dias": dias, "mapa": mapa,
               "base": base_nombre, "periodo": periodo, "periodoParam": periodo_param, "pct": pct, "bases": bases,
               "pctBase": pct_base, "umbrales": {"var": umbral_var, "ext": umbral_ext, "alto": u_alto, "medio": u_medio, "dias": u_dias},
               "sino": sino, "fechas": fechas, "fuentes": fuentes, "hayEri": hay_eri, "bruto": bruto, "signo": signo, "sec7": sec7,
               "cuentas": cuentas, "est9": est9, "ind": ind,
               "materialidad": {"base": base_valor, "global": mat, "desempeno": desemp, "trivial": triv},
               "justificacion": justif, "carta": carta, "informe": informe, "notas": notas, "riesgos": riesgos,
               "anomalias": anomalias, "revisar": revisar, "nivelRevisar": lvl, "parametros": p,
               "origenes": origenes, "puente": puente, "archivos": archivos, "fac": fac,
               "otrosAbs": sum(abs(x["saldo"]) for x in fuentes["act"] if x["sec"] == "Otros" and x["detalle"] == "Sí")}
    return {"engine": VERSION, "rows": filas, "totals": totales, "labels": etiquetas, "primary": "materialidad",
            "exceptions": probs, "schedule": [], "detalle": detalle}


def _indices(e: dict, dias: float) -> dict:
    """Índices del período con el mismo redondeo (ROUND 2) que la hoja 10."""
    ac, pc, inv, cxc, cxp = e["Activo corriente"], e["Pasivo corriente"], e["Inventarios"], e["Cuentas por cobrar"], e["Cuentas por pagar"]
    act_, pas, pnc, patt, obl = e["TOTAL ACTIVO"], e["TOTAL PASIVO"], e["Pasivo no corriente"], e["PATRIMONIO TOTAL"], e["Obligaciones financieras"]
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
    i["endFinanciero"] = q(obl, patt)
    i["endPatrimonial"] = q(pas, patt)
    i["multiplicador"] = q(act_, patt)
    i["margenBruto"] = q(ub, ven, 100)
    i["margenOperativo"] = q(uo, ven, 100)
    i["margenNeto"] = q(un, ven, 100)
    i["roi"] = q(uo, act_, 100)
    i["roe"] = q(un, patt, 100)
    # R5: el margen operativo es utilidad operativa ÷ ventas para que el DuPont reproduzca el ROI.
    # Los componentes del DuPont se multiplican sin redondear, para que reproduzcan el ROI y el ROE.
    i["dupontRoi"] = None if not ven or not act_ else _xr(uo / ven * 100 * (ven / act_), 2)
    i["dupont"] = None if not ven or not act_ or not patt else _xr(un / ven * 100 * (ven / act_) * (act_ / patt), 2)
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
            probs.append(problema(code, f"{r_['codigo']}: {r_['cond']} ({m(r_['valor'])}): indicio sobre la empresa en marcha "
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
    if sino["refutarIngresos"] == "Sí" and not str(p.get("motivoRefutacion") or "").strip():
        probs.append(problema("REFUTACION_SIN_MOTIVO", "Se refutó la presunción de fraude en ingresos sin documentar el motivo "
                                                       "(NIA 240 párr. 47).", 0))
    for r_ in carta:
        if r_["nivel"] == "Alto":
            probs.append(problema("RIESGO_CCI_ALTO", f"{r_['id']}: {r_['proceso']} · riesgo residual alto en la carta de control interno; "
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


# --- cédulas con fórmulas ------------------------------------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen de la planificación"), ("02_Parametros", "Parámetros"),
    ("03_Mapa", "Mapa de cuentas (prefijo del código → clasificación)"),
    ("04_BC_Anterior", "Balance de comprobación al cierre anterior"), ("05_BC_Corte", "Balance de comprobación al corte"),
    ("06_ERI_Anterior", "Estado de resultados del año anterior al mismo corte"),
    ("07_Secciones", "Totales por sección, signo de presentación y cuadre"),
    ("08_Horizontal", "Análisis horizontal y vertical de todas las cuentas"),
    ("09_Estados", "Estados financieros resumidos"), ("10_Indices", "Índices financieros"),
    ("11_Materialidad", "Materialidad (NIA 320 y 450)"), ("12_Riesgos_CCI", "Matriz de riesgos de la carta de control interno"),
    ("13_Riesgos_Balance", "Posibles riesgos: NIA 240, empresa en marcha, balances e informe anterior"),
    ("14_Perfil", "Perfil del encargo según el informe del año anterior"),
    ("15_Notas", "Notas comparativas y saldos de apertura (NIA 510)"), ("16_Control", "Control de calidad del análisis"),
    ("17_Anomalias", "Anomalías en las cuentas"), ("18_Cuentas_Revisar", "Cuentas principales a revisar"),
    ("19_Programa", "Programa de procedimientos (NIA 330)"), ("20_Narrativa", "Narrativa ejecutiva"),
    ("21_Estrategia", "Estrategia global de auditoría (NIA 300)"),
    ("22_Origenes", "Orígenes y aplicaciones de efectivo (lectura causa-efecto)"), ("23_Audit_trail", "Audit trail (NIA 230)"),
    ("24_Problemas", "Asuntos para la planificación"),
]
_PAR = ["corte", "marco", "tipoRevision", "mesesTranscurridos", "mapaCuentas", "baseMaterialidad", "periodoBase", "pctIngresos",
        "pctActivos", "pctPatrimonio", "pctGastos", "pctUAI", "pctDesempeno", "pctTrivial", "justificacion", "umbralVarPct",
        "umbralVarExtrema", "umbralDiasRotacion", "umbralAlto", "umbralMedio", "encargoInicial", "interesPublico", "auditoriaGrupo", "refutarIngresos",
        "motivoRefutacion", "enfoque", "fechaPreliminar", "fechaFinal", "fechaInforme", "socio", "gerente", "expertos"]
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
LECTURA = {
    "diasCartera": "Días promedio que la empresa tarda en cobrar a sus clientes (sobre 365 días).",
    "diasInventario": "Días promedio que el inventario permanece en bodega antes de venderse.",
    "diasProveedores": "Días promedio que la empresa se financia con sus proveedores (sobre el costo de ventas).",
    "ciclo": "Días que el efectivo queda inmovilizado en el ciclo operativo (cartera + inventario − proveedores).",
    "rotacionActivo": "Ventas del período que genera cada dólar de activos.",
    "endTotal": "Porcentaje de los activos financiado con deuda de terceros.",
    "endLP": "Porcentaje de los activos financiado con deuda de largo plazo.",
    "endFinanciero": "Deuda financiera (bancos y obligaciones) por cada dólar de patrimonio.",
    "endPatrimonial": "Deuda con terceros por cada dólar de patrimonio.",
    "multiplicador": "Veces que los activos equivalen al patrimonio (multiplicador de apalancamiento).",
    "margenBruto": "De cada 100 dólares vendidos, lo que queda después del costo de ventas.",
    "margenOperativo": "De cada 100 dólares vendidos, lo que queda como utilidad operativa.",
    "margenNeto": "De cada 100 dólares vendidos, lo que se convierte en utilidad final.",
    "roi": "Utilidad operativa del período por cada 100 dólares de activos.",
    "dupontRoi": "El ROI descompuesto en margen operativo × rotación del activo: debe reproducir el ROI.",
    "roe": "Utilidad neta del período por cada 100 dólares de patrimonio.",
    "dupont": "El ROE descompuesto en margen neto × rotación del activo × multiplicador: debe reproducir el ROE.",
}
LECTURA_COND = {
    "razonCorriente": ("<1", "El activo corriente no alcanza a cubrir el pasivo corriente.", "El activo corriente cubre el pasivo corriente."),
    "pruebaAcida": ("<1", "Sin inventarios, los activos líquidos no cubren el pasivo corriente.",
                    "Sin inventarios, los activos líquidos cubren el pasivo corriente."),
    "capitalTrabajo": ("<0", "Déficit: el pasivo corriente supera al activo corriente (presión de liquidez).",
                       "El activo corriente supera al pasivo corriente: hay margen para operar."),
}
SIN_DATO = "No hay datos suficientes para calcular este indicador."
LECTURA_DIAS = ("Año completo: los días se calculan sobre 365.",
                "Corte parcial: con ventas y costos de pocos meses sobre 365 días, los días salen mayores que los reales (R4).")
_MAT = ["Período de la base"] + list(BASES) + ["Materialidad global", "Materialidad de desempeño",
                                               "Umbral de errores claramente insignificantes", "Justificación de la base"]
F11 = {k: FILA0 + i for i, k in enumerate(_MAT)}
_REF_BASE7 = {"Ingresos": "Ingresos", "Activos totales": "Activo", "Patrimonio": "Patrimonio", "Gastos totales": "Gastos totales", UAI: UAI}
_PCT_BASE = {"Ingresos": "pctIngresos", "Activos totales": "pctActivos", "Patrimonio": "pctPatrimonio", "Gastos totales": "pctGastos",
             UAI: "pctUAI"}
CONTROLES = ["Cuadre del balance al corte", "Cuadre del balance del cierre anterior", "Cuentas fuera del mapa (sección «Otros»)",
             "Materialidad definida", "Anomalías de severidad alta", "Notas del año anterior cargadas",
             "Notas que no concilian con el balance anterior (NIA 510)", "Indicios de empresa en marcha (NIA 570)",
             "Riesgos de la carta de control interno pendientes de calificación", "Carta de control interno cargada",
             "Informe de auditoría del año anterior cargado", "Cuentas superiores que no suman sus subcuentas (R1)"]
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

P_, MP, B4, B5, B6, S7, H8, E9, I10, M11, R12, R13, P14, N15, A17, C18 = (ref(n) for n in (
    "02_Parametros", "03_Mapa", "04_BC_Anterior", "05_BC_Corte", "06_ERI_Anterior", "07_Secciones", "08_Horizontal", "09_Estados",
    "10_Indices", "11_Materialidad", "12_Riesgos_CCI", "13_Riesgos_Balance", "14_Perfil", "15_Notas", "17_Anomalias",
    "18_Cuentas_Revisar"))
DESEMP = f"{M11}$D${F11['Materialidad de desempeño']}"


def _ge(expr: str, factor: str = "") -> str:
    """|expr| ≥ materialidad de desempeño; falso si no hay materialidad (base ≤ 0)."""
    return f'AND({DESEMP}<>"",ABS({expr})>={DESEMP}{factor})'


def _par(k):
    return f"{P_}$B${PAR[k]}"


PRELIM = f'{_par("tipoRevision")}="Preliminar"'
FAC = f'IF({PRELIM},{_par("mesesTranscurridos")}/12,1)'


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
            f'IF({f}="Pasivo",IF({_s(b, "bancari", "financ", "préstamo", "prestamo", "sobregiro")},"Obligaciones financieras",'
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
    mt = d["materialidad"]
    pv = lambda k: None if p.get(k) in (None, "") else p.get(k)  # noqa: E731

    # 02 · parámetros (valores del encargo y juicio del auditor)
    fch = d["fechas"]
    val = {"corte": d["corte"], "marco": d["marco"], "tipoRevision": d["tipo"], "mesesTranscurridos": d["meses"],
           "mapaCuentas": "; ".join(f"{a}={b}" for a, b in d["mapa"]), "baseMaterialidad": d["base"], "periodoBase": d["periodoParam"],
           **{k: d["pct"][k] for k in d["pct"]}, "justificacion": pv("justificacion"), "umbralVarPct": d["umbrales"]["var"],
           "umbralVarExtrema": d["umbrales"]["ext"], "umbralDiasRotacion": d["umbrales"]["dias"],
           "umbralAlto": d["umbrales"]["alto"], "umbralMedio": d["umbrales"]["medio"],
           **d["sino"], "motivoRefutacion": pv("motivoRefutacion"), "enfoque": pv("enfoque"), **fch,
           "socio": pv("socio"), "gerente": pv("gerente"), "expertos": pv("expertos")}
    sustento = {"corte": "Ficha del encargo", "marco": "Ficha del encargo", "tipoRevision": "Cronograma del encargo",
                "mesesTranscurridos": "Solo prorratea el ERI del año anterior si no se entrega al mismo corte",
                "mapaCuentas": "Plan de cuentas del cliente; la hoja 03 lo muestra como tabla (edítela allí)",
                "baseMaterialidad": "NIA 320 párr. A3–A5: juicio profesional", "periodoBase": "NIA 320 párr. A5–A6",
                "pctDesempeno": "NIA 320 párr. 11 y A12: política de la firma", "pctTrivial": "NIA 450 párr. 5 y A2: política de la firma",
                "justificacion": "NIA 320 párr. 14 (documentación)", "umbralAlto": "Política de la firma (mapa de calor 5 × 5)",
                "umbralMedio": "Política de la firma (mapa de calor 5 × 5)", "encargoInicial": "NIA 300 párr. 13 y NIA 510",
                "interesPublico": "NIA 701", "auditoriaGrupo": "NIA 600", "refutarIngresos": "NIA 240 párr. 26 y 47",
                "motivoRefutacion": "NIA 240 párr. 47", "enfoque": "NIA 300 párr. 8", "socio": "NIA 220", "gerente": "NIA 220",
                "expertos": "NIA 300 párr. 8 e) y NIA 620"}
    parametros = [[ETIQUETAS_PARAM.get(k, {"corte": "Corte del ejercicio", "marco": "Marco de información financiera"}.get(k, k)),
                   val.get(k), sustento.get(k, "Política de la firma" if k.startswith(("pct", "umbral")) else "Cronograma del encargo")]
                  for k in _PAR]

    # 03 · mapa
    mapa = [[a, b, fx(_f_seccion(f"B{FILA0 + i}"), _seccion_de(b))] for i, (a, b) in enumerate(d["mapa"])]

    # 04 / 05 / 06 · balances de comprobación
    bc_ant = _hoja_bc("04_BC_Anterior", CEDULAS[3][1], fu["ant"], "Saldo al cierre anterior", nm,
                      "Balance de comprobación al cierre del año anterior (auditado), exportado del sistema contable.")
    bc_act = _hoja_bc("05_BC_Corte", CEDULAS[4][1], fu["act"], "Saldo al corte", nm,
                      "Balance de comprobación a la fecha de corte que se audita, exportado del sistema contable.")
    bc_eri = _hoja_bc("06_ERI_Anterior", CEDULAS[5][1], fu["eri"], "Saldo al mismo corte del año anterior", nm,
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
            ta_, tp, pnc, pt = e("TOTAL ACTIVO", c9), e("TOTAL PASIVO", c9), e("Pasivo no corriente", c9), e("PATRIMONIO TOTAL", c9)
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
        fila.append(fx(_f_semaforo(k, f"E{r}"), _semaforo(k, vc, d["fac"])))
        if k == "dias":
            fila.append(fx(f'IF({PRELIM},"{LECTURA_DIAS[1]}","{LECTURA_DIAS[0]}")', LECTURA_DIAS[d["tipo"] == "Preliminar"]))
        else:
            fila.append(fx(_f_lectura(k, f"E{r}"), _lectura(k, vc)))
        indices.append(fila)

    # 11 · materialidad
    per = f"$E${F11['Período de la base']}"
    rb = f"$A${F11[BASES[0]]}:$A${F11[BASES[-1]]}"
    materialidad = [["Período de la base", None, None, None,
                     fx(f'IF({_par("periodoBase")}="Automático",IF({PRELIM},"Año anterior","Corte actual"),{_par("periodoBase")})',
                        d["periodo"])]]
    for b in BASES:
        r = F11[b]
        f7 = F7[_REF_BASE7[b]]
        materialidad.append([b, fx(f'IF({per}="Año anterior",{S7}F{f7},{S7}G{f7})', n2(d["bases"][b])),
                             fx(_par(_PCT_BASE[b]), d["pctBase"][b]), fx(f"B{r}*C{r}/100", n2(d["bases"][b] * d["pctBase"][b] / 100)),
                             "Política de la firma; NIA 320 párr. A4 y A8 (ejemplos, no porcentajes prescritos)"])
    rg, rd = F11["Materialidad global"], F11["Materialidad de desempeño"]
    materialidad += [
        ["Materialidad global", fx(f"INDEX($B${F11[BASES[0]]}:$B${F11[BASES[-1]]},MATCH({_par('baseMaterialidad')},{rb},0))", n2(mt["base"])),
         fx(f"INDEX($C${F11[BASES[0]]}:$C${F11[BASES[-1]]},MATCH({_par('baseMaterialidad')},{rb},0))", d["pctBase"][d["base"]]),
         fx(f'IF(B{rg}<=0,"",B{rg}*C{rg}/100)', n2(mt["global"])),
         fx(f'"Base elegida: "&{_par("baseMaterialidad")}&" ("&LOWER({per})&"); NIA 320 párr. 10"',
            f"Base elegida: {d['base']} ({d['periodo'].lower()}); NIA 320 párr. 10")],
        ["Materialidad de desempeño", fx(f"D{rg}", n2(mt["global"])), fx(_par("pctDesempeno"), d["pct"]["pctDesempeno"]),
         fx(f'IF(B{rd}="","",B{rd}*C{rd}/100)', n2(mt["desempeno"])), "NIA 320 párr. 11 y A12 (práctica: 50 %–75 %)"],
        ["Umbral de errores claramente insignificantes", fx(f"D{rg}", n2(mt["global"])), fx(_par("pctTrivial"), d["pct"]["pctTrivial"]),
         fx(f'IF(B{F11["Umbral de errores claramente insignificantes"]}="","",B{F11["Umbral de errores claramente insignificantes"]}'
            f'*C{F11["Umbral de errores claramente insignificantes"]}/100)',
            n2(mt["trivial"])), "NIA 450 párr. 5 y A2: no se acumulan los errores menores"],
        ["Justificación de la base", None, None, None,
         fx(f'IF({_par("justificacion")}<>"",{_par("justificacion")},' + "".join(
             f'IF({_par("baseMaterialidad")}="{b}","{JUSTIFICACION[b]}",' for b in BASES[:-1]) + f'"{JUSTIFICACION[BASES[-1]]}"'
            + ")" * (len(BASES) - 1) + ")", d["justificacion"])],
    ]

    # 12 · matriz de la carta de control interno
    matriz = []
    for i, x in enumerate(carta):
        r = FILA0 + i
        matriz.append([x["id"], x["proceso"], x["hallazgo"], x["aser"], x["p"], x["i"], x["c"],
                       fx(f'IF(OR(E{r}="",F{r}=""),"",E{r}*F{r})', _txt(x["inh"])),
                       fx(f'IF(OR(H{r}="",G{r}=""),"",H{r}*(6-G{r})/5)', _txt(x["res"])),
                       fx(f'IF(I{r}="","Pendiente de calificación",IF(I{r}>={_par("umbralAlto")},"Alto",IF(I{r}>={_par("umbralMedio")},"Medio","Bajo")))',
                          x["nivel"]),
                       x["respuesta"] or RESPUESTA_DEFECTO, x["herramienta"]])

    # 13 · posibles riesgos
    fila8 = {x["codigo"]: FILA0 + i for i, x in enumerate(cu)}
    ref_valor = {"presuncion": f"{E9}D{F9['Ventas netas']}", "ct": f"{I10}E{F10['capitalTrabajo']}", "rc": f"{I10}E{F10['razonCorriente']}",
                 "end": f"{I10}E{F10['endTotal']}", "perdida": f"{E9}D{F9['Utilidad neta']}", "patrimonio": f"{E9}D{F9['PATRIMONIO TOTAL']}",
                 "cartera": f"{I10}E{F10['diasCartera']}", "inventario": f"{I10}E{F10['diasInventario']}",
                 "end80": f"{I10}E{F10['endTotal']}", "rotCartera": f"{I10}F{F10['diasCartera']}",
                 "rotInventario": f"{I10}F{F10['diasInventario']}"}
    cond_f = {"ct": "E{r}<0", "perdida": "E{r}<0", "patrimonio": "E{r}<=0"}
    cond_v = {"rc": "E{r}<1", "end": "E{r}>70", "end80": "E{r}>80", "cartera": "E{r}*" + FAC + ">90",
              "inventario": "E{r}*" + FAC + ">120", "rotCartera": "E{r}>" + _par("umbralDiasRotacion"),
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
            valor = fx(f"{P14}D{FILA0 + x['idx']}", n2(x["valor"]))
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
        else:
            pres = x["presenta"]
        posibles.append([x["codigo"], x["origen"], x["rubro"], x["cond"], valor, pres, x["riesgo"], x["sev"], x["norma"]])

    # 14 · perfil
    perfil = [[x["tipo"], x["concepto"], x["detalle"], n2(x["importe"]), x["fuente"], EFECTO_INFORME[x["tipo"]]] for x in informe]

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

    # 16 · control de calidad
    n12, n13, n14, n15, n17 = len(carta), len(riesgos), len(informe), len(notas), len(anom)
    dif_act, dif_ant, otros = d["sec7"]["act"]["Diferencia de cuadre"], d["sec7"]["ant"]["Diferencia de cuadre"], d["otrosAbs"]

    def est_cuadre(v, activo):
        return "Conforme" if abs(v) < 0.01 else "Revisar" if abs(v) <= abs(activo) * 0.01 else "Crítico"
    altas = sum(1 for x in anom if x["sev"] == "Alto")
    ind570 = sum(1 for x in riesgos if x["norma"] == "NIA 570" and x["presenta"] == "Sí")
    pend = sum(1 for x in carta if x["nivel"].startswith("Pendiente"))
    no_conc = sum(1 for x in notas if abs(x["dif"]) >= 0.01)
    n_jer = sum(1 for k in ("ant", "act") for x in fu[k] if abs(x["difsub"]) >= 0.01)
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
         fx(f'IF(C{FILA0 + 4}>0,"Crítico",IF(COUNTIF({_rng(A17, "F", n17)},"Sí")>0,"Revisar","Conforme"))',
            "Crítico" if altas else "Revisar" if anom else "Conforme"),
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
        [CONTROLES[10], None, fx(f"COUNTA({_rng(P14, 'A', n14)})", n14), fx(f'IF(C{FILA0 + 10}>0,"Conforme","Revisar")',
                                                                           "Conforme" if n14 else "Revisar"),
         "Identificación, opinión y asuntos del informe de auditoría anterior."],
        [CONTROLES[11], None,
         fx(f"SUMPRODUCT((ABS({_rng(B4, 'K', n4)})>=0.01)*1)+SUMPRODUCT((ABS({_rng(B5, 'K', n5)})>=0.01)*1)", n_jer),
         fx(f'IF(C{FILA0 + 11}>0,"Revisar","Conforme")', "Revisar" if n_jer else "Conforme"),
         "Se usa el saldo propio de la cuenta; la diferencia se muestra en las hojas 04 y 05 y no se fuerza."],
    ]

    # 18 · cuentas a revisar
    cuentas_rev = []
    for i, x in enumerate(rev):
        rr, r = fila8[x["x"]["codigo"]], FILA0 + i
        cuentas_rev.append([x["x"]["codigo"], x["x"]["cuenta"], fx(f"{H8}F{rr}", x["x"]["sec"]), fx(f"{H8}H{rr}", n2(x["x"]["act"])),
                            fx(f"{H8}I{rr}", n2(x["x"]["var"])), fx(f"{H8}O{rr}", x["x"]["material"]),
                            fx(f"{H8}P{rr}", x["x"]["varMaterial"]), x["riesgo"], x["herr"],
                            fx(f'IF(OR(F{r}="Sí",G{r}="Sí",H{r}<>""),"Sí","No")', x["revisa"])])

    # 19 · programa (NIA 330)
    def oport(celda, v):
        f_ = (f'IF(OR({celda}="Alto",{celda}="Significativo"),"{OPORTUNIDAD_ALTO}",IF({celda}="Medio","{OPORTUNIDAD_MEDIO}",'
              f'"{OPORTUNIDAD_BAJO}"))')
        return fx(f_, OPORTUNIDAD_ALTO if v in ("Alto", "Significativo") else OPORTUNIDAD_MEDIO if v == "Medio" else OPORTUNIDAD_BAJO)
    programa = []
    for i, x in enumerate(carta):
        r12, r = FILA0 + i, FILA0 + len(programa)
        programa.append([f"PT-{len(programa) + 1:02d}", x["proceso"], x["id"], fx(f"{R12}J{r12}", x["nivel"]),
                         fx(f"{R12}K{r12}", x["respuesta"] or RESPUESTA_DEFECTO), fx(f"{R12}L{r12}", x["herramienta"]),
                         oport(f"D{r}", x["nivel"])])
    for i, x in enumerate(riesgos):
        if x["presenta"] != "Sí":
            continue
        r = FILA0 + len(programa)
        programa.append([f"PT-{len(programa) + 1:02d}", x["rubro"], x["codigo"], fx(f"{R13}H{FILA0 + i}", x["sev"]), x["resp"], x["herr"],
                         oport(f"D{r}", x["sev"])])

    # 20 · narrativa
    ia, ip, ia_ant = ind["act"], e9["act"], e9["ant"]

    def i10(k, c="E"):
        return f"{I10}{c}{F10[k]}"
    va = None if ia_ant["TOTAL ACTIVO"] == 0 else (ip["TOTAL ACTIVO"] - ia_ant["TOTAL ACTIVO"]) / abs(ia_ant["TOTAL ACTIVO"])
    f_va = f"{E9}F{F9['TOTAL ACTIVO']}"
    lect_act = ("Sin saldo comparable del período anterior." if va is None else
                "El activo total se mantiene estable frente al período anterior." if abs(va) < 0.05 else
                "El activo total creció respecto del período anterior." if va > 0 else "El activo total disminuyó respecto del período anterior.")
    n_alto_cci = sum(1 for x in carta if x["nivel"] == "Alto")
    n_pres = sum(1 for x in riesgos if x["presenta"] == "Sí")
    narrativa = [
        ["Hechos", "Activo total", fx(f"{E9}D{F9['TOTAL ACTIVO']}", n2(ip["TOTAL ACTIVO"])),
         fx(f'IF({f_va}="","Sin saldo comparable del período anterior.",IF(ABS({f_va})<0.05,"El activo total se mantiene estable frente al '
            f'período anterior.",IF({f_va}>0,"El activo total creció respecto del período anterior.","El activo total disminuyó respecto '
            f'del período anterior.")))', lect_act)],
        ["Hechos", "Pasivo total", fx(f"{E9}D{F9['TOTAL PASIVO']}", n2(ip["TOTAL PASIVO"])),
         fx(f'IF({i10("endTotal")}="","",IF({i10("endTotal")}>70,"Más del 70 % del activo se financia con terceros.",'
            f'"El financiamiento con terceros no supera el 70 % del activo."))',
            "" if ia["endTotal"] is None else "Más del 70 % del activo se financia con terceros." if ia["endTotal"] > 70 else
            "El financiamiento con terceros no supera el 70 % del activo.")],
        ["Hechos", "Patrimonio total", fx(f"{E9}D{F9['PATRIMONIO TOTAL']}", n2(ip["PATRIMONIO TOTAL"])),
         fx(f'IF(C{FILA0 + 2}<=0,"Patrimonio comprometido: indicio de empresa en marcha (NIA 570).","Patrimonio positivo.")',
            "Patrimonio comprometido: indicio de empresa en marcha (NIA 570)." if ip["PATRIMONIO TOTAL"] <= 0 else "Patrimonio positivo.")],
        ["Hechos", "Utilidad neta del período", fx(f"{E9}D{F9['Utilidad neta']}", n2(ip["Utilidad neta"])),
         fx(f'IF(C{FILA0 + 3}<0,"Resultado negativo en el período.","Resultado positivo en el período.")',
            "Resultado negativo en el período." if ip["Utilidad neta"] < 0 else "Resultado positivo en el período.")],
    ]
    for k in ("razonCorriente", "endTotal", "margenNeto", "roe", "diasCartera", "diasInventario"):
        v = ia[k]
        nombre = next(n_ for kk, n_, *_r in INDICES if kk == k)
        narrativa.append(["Análisis", nombre, fx(i10(k), "" if v is None else v),
                          fx(f'{i10(k, "G")}&": "&{i10(k, "H")}', f"{_semaforo(k, v, d['fac'])}: {_lectura(k, v)}")])
    narrativa += [
        ["Riesgos", "Riesgos altos de la carta de control interno", fx(f'COUNTIF({_rng(R12, "J", n12)},"Alto")', n_alto_cci),
         fx(f'IF(C{FILA0 + 10}>0,"Tienen respuesta específica en el programa (NIA 330).","Sin riesgos altos en la carta de control interno.")',
            "Tienen respuesta específica en el programa (NIA 330)." if n_alto_cci else "Sin riesgos altos en la carta de control interno.")],
        ["Riesgos", "Posibles riesgos presentes (NIA 240, balances e informe anterior)", fx(f'COUNTIF({_rng(R13, "F", n13)},"Sí")', n_pres),
         fx(f'IF(C{FILA0 + 11}>0,"Cada riesgo presente tiene su respuesta en el programa (hoja 19).","Sin riesgos adicionales.")',
            "Cada riesgo presente tiene su respuesta en el programa (hoja 19)." if n_pres else "Sin riesgos adicionales.")],
        ["Riesgos", "Indicios de empresa en marcha (NIA 570)",
         fx(f'COUNTIFS({_rng(R13, "I", n13)},"NIA 570",{_rng(R13, "F", n13)},"Sí")', ind570),
         fx(f'IF(C{FILA0 + 12}>0,"Evaluar la capacidad de continuar y su revelación (NIA 570).","Sin indicios en los indicadores evaluados.")',
            "Evaluar la capacidad de continuar y su revelación (NIA 570)." if ind570 else "Sin indicios en los indicadores evaluados.")],
    ]
    # causa-efecto (lectura de las variaciones del artefacto), sobre las variaciones de la hoja 09
    dv = {k: e9["act"][k] - e9["ant"][k] for k in ("Inventarios", "Ventas netas", "Efectivo y equivalentes", "Cuentas por cobrar",
                                                  "Cuentas por pagar", "Obligaciones financieras", "Utilidad neta")}
    ev = {k: f"{E9}E{F9[k]}" for k in dv}
    for concepto, clave, f_, v_ in _causa_efecto(ev, dv):
        narrativa.append(["Causa-efecto", concepto, fx(ev[clave], n2(dv[clave])), fx(f_, v_)])

    ref_rec = {"rc": "razonCorriente", "end": "endTotal", "cartera": "diasCartera", "inventario": "diasInventario"}
    for nombre, k, cond, si, no in RECOMENDACIONES:
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

    # 21 · estrategia
    def txt(k, valor):
        return fx(f'IF({_par(k)}="","",{_par(k)})', valor)
    sino = d["sino"]
    ref_ing = "No refutada: riesgo significativo (NIA 240 párr. 26)"
    n_rev = len(rev)
    riesgos_altos = float(res["totals"]["riesgosAltos"])
    estrategia = [
        ["Marco de información financiera", fx(_par("marco"), d["marco"]), "NIA 300 párr. 8 a)"],
        ["Tipo de revisión", fx(_par("tipoRevision"), d["tipo"]), "Cronograma del encargo"],
        ["Períodos comparados", fx(f'IF({PRELIM},"Balance: cierre anterior contra el corte; resultados: mismo corte de ambos años",'
                                   '"Balance y resultados: diciembre anterior contra diciembre actual")',
                                   "Balance: cierre anterior contra el corte; resultados: mismo corte de ambos años" if d["tipo"] == "Preliminar"
                                   else "Balance y resultados: diciembre anterior contra diciembre actual"), "NIA 315 párr. 14 b); NIA 520"],
        ["Enfoque general", txt("enfoque", pv("enfoque") or ""), "NIA 300 párr. 8"],
        ["Encargo inicial", fx(f'IF({_par("encargoInicial")}="Sí","Sí: procedimientos sobre saldos de apertura (NIA 510)","No")',
                               "Sí: procedimientos sobre saldos de apertura (NIA 510)" if sino["encargoInicial"] == "Sí" else "No"),
         "NIA 300 párr. 13"],
        ["Entidad de interés público o cotizada", fx(f'IF({_par("interesPublico")}="Sí","Sí: comunicar asuntos clave de auditoría (NIA 701)","No")',
                                                     "Sí: comunicar asuntos clave de auditoría (NIA 701)" if sino["interesPublico"] == "Sí" else "No"),
         "NIA 300 párr. 8 b)"],
        ["Auditoría de un grupo o componente", fx(f'IF({_par("auditoriaGrupo")}="Sí","Sí: coordinar con el equipo del grupo (NIA 600)","No")',
                                                  "Sí: coordinar con el equipo del grupo (NIA 600)" if sino["auditoriaGrupo"] == "Sí" else "No"),
         "NIA 300 párr. 8 a)"],
        ["Base de la materialidad", fx(f'{_par("baseMaterialidad")}&" ("&LOWER({M11}$E${F11["Período de la base"]})&")"',
                                       f"{d['base']} ({d['periodo'].lower()})"), "NIA 320 párr. A3–A5"],
        ["Materialidad global", fx(f"{M11}$D${F11['Materialidad global']}", n2(mt["global"])), "NIA 320 párr. 10"],
        ["Materialidad de desempeño", fx(DESEMP, n2(mt["desempeno"])), "NIA 320 párr. 11"],
        ["Umbral de errores claramente insignificantes", fx(f"{M11}$D${F11['Umbral de errores claramente insignificantes']}", n2(mt["trivial"])),
         "NIA 450 párr. 5"],
        ["Riesgos altos o significativos", fx(f"{ref('01_Resumen')}B{FILA0 + list(res['labels']).index('riesgosAltos')}", riesgos_altos),
         "NIA 315 párr. 32; NIA 330 párr. 15 y 21"],
        ["Cuentas principales a revisar", fx(f'COUNTIF({_rng(C18, "J", n_rev)},"Sí")', float(res["totals"]["cuentasRevisar"])),
         "NIA 330 párr. 18"],
        ["Presunción de fraude en ingresos", fx(f'IF({_par("refutarIngresos")}="Sí","Refutada: "&{_par("motivoRefutacion")},"{ref_ing}")',
                                                ("Refutada: " + str(pv("motivoRefutacion") or "")) if sino["refutarIngresos"] == "Sí" else ref_ing),
         "NIA 240 párr. 26 y 47"],
        ["Visita preliminar", txt("fechaPreliminar", fch["fechaPreliminar"] or ""), "NIA 300 párr. 8 c)"],
        ["Visita final", txt("fechaFinal", fch["fechaFinal"] or ""), "NIA 300 párr. 8 c)"],
        ["Entrega del informe", txt("fechaInforme", fch["fechaInforme"] or ""), "NIA 300 párr. 8 b)"],
        ["Socio del encargo", txt("socio", pv("socio") or ""), "NIA 220; NIA 300 párr. 8 e)"],
        ["Gerente o encargado", txt("gerente", pv("gerente") or ""), "NIA 300 párr. 8 e) y 11"],
        ["Uso de expertos", txt("expertos", pv("expertos") or ""), "NIA 300 párr. 8 e) y NIA 620"],
        ["Comunicación con los responsables del gobierno", "Alcance y momento planificados de la auditoría y riesgos significativos",
         "NIA 260 párr. 15"],
    ]

    # 22 · orígenes y aplicaciones
    origenes_h = []
    for x in d["origenes"]:
        r, rr = FILA0 + len(origenes_h), fila8[x["codigo"]]
        origenes_h.append([x["codigo"], x["cuenta"], fx(f"{H8}F{rr}", x["sec"]), fx(f"{H8}I{rr}", n2(x["var"])),
                           fx(f'IF(C{r}="Activo",-D{r},D{r})', n2(x["efecto"])), fx(_f_tipo(f"E{r}"), _tipo_efecto(x["efecto"]))])
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
    trail = [[f"{etq} ({rq})", arch[ds][0], fx(f"COUNTA({_rng(pref, 'A', n)})", n)]
             for etq, rq, ds, pref, n in (
                 ("Balance de comprobación del cierre anterior", "RQ-001", "balance_anterior", B4, n4),
                 ("Balance de comprobación al corte", "RQ-002", "balance_actual", B5, n5),
                 ("Resultados del año anterior al mismo corte", "RQ-003", "resultados_mismo_corte", B6, n6),
                 ("Carta de control interno", "RQ-004", "carta_control_interno", R12, len(carta)),
                 ("Informe de auditoría del año anterior", "RQ-005", "informe_anterior", P14, len(informe)),
                 ("Notas a los estados financieros del año anterior", "RQ-006", "notas_estados_financieros", N15, len(notas)))]
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
        ["Materialidad (NIA 320)", fx(f"{M11}E{F11['Materialidad global']}", f"Base elegida: {d['base']} ({d['periodo'].lower()}); NIA 320 párr. 10"),
         fx(f"{M11}D{F11['Materialidad global']}", n2(mt["global"]))],
        ["Motor de cálculo", VERSION, None],
        ["Aprobación (R10)", "El papel se publica solo con la aprobación del socio en el ciclo del Command Center.", None],
    ]

    # 01 · resumen
    ref_res = {"activos": f"{E9}D{F9['TOTAL ACTIVO']}", "pasivos": f"{E9}D{F9['TOTAL PASIVO']}",
               "patrimonio": f"{E9}D{F9['PATRIMONIO TOTAL']}", "ventas": f"{E9}D{F9['Ventas netas']}",
               "resultado": f"{E9}D{F9['Utilidad neta']}", "materialidad": f"N({M11}D{F11['Materialidad global']})",
               "desempeno": f"N({DESEMP})", "trivial": f"N({M11}D{F11['Umbral de errores claramente insignificantes']})",
               "riesgosAltos": (f'COUNTIF({_rng(R12, "J", n12)},"Alto")+COUNTIFS({_rng(R13, "F", n13)},"Sí",{_rng(R13, "H", n13)},"Alto")'
                                f'+COUNTIFS({_rng(R13, "F", n13)},"Sí",{_rng(R13, "H", n13)},"Significativo")'),
               "cuentasRevisar": f'COUNTIF({_rng(C18, "J", n_rev)},"Sí")'}
    t = {k: float(v) for k, v in res["totals"].items()}
    resumen = [[res["labels"][k], fx(ref_res[k], n2(t[k]))] for k in res["labels"]]

    return [
        hoja("01_Resumen", CEDULAS[0][1], [["Concepto", "t"], ["Importe", "n"]], resumen, explica=EXPLICA["01_Resumen"]),
        hoja("02_Parametros", CEDULAS[1][1], [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Mapa", CEDULAS[2][1], [["Prefijo del código", "t"], ["Clasificación", "t"], ["Sección", "t"]], mapa,
             explica=EXPLICA["03_Mapa"]),
        bc_ant, bc_act, bc_eri,
        hoja("07_Secciones", CEDULAS[6][1], [["Concepto", "t"], ["Bruto BC anterior", "n"], ["Bruto BC corte", "n"],
                                            ["Bruto ERI anterior", "n"], ["Signo", "i"], ["BC anterior", "n"], ["BC corte", "n"],
                                            ["ERI anterior", "n"]], secciones, explica=EXPLICA["07_Secciones"]),
        hoja("08_Horizontal", CEDULAS[7][1], [["Código", "t"], ["Cuenta", "t"], ["Nivel", "i"], ["Detalle", "t"], ["Clasificación", "t"],
                                             ["Sección", "t"], ["Anterior", "n"], ["Actual", "n"], ["Variación", "n"], ["Variación %", "p"],
                                             ["Peso vertical", "p"], ["Rubro del ERI", "t"], ["Rubro para índices", "t"],
                                             ["Cuenta para índices", "t"], ["Monto material", "t"], ["Variación material", "t"],
                                             ["Superior de la sección", "t"], ["Superior de la clasificación", "t"],
                                             ["Superior del rubro del ERI", "t"]],
             horizontal, explica=EXPLICA["08_Horizontal"]),
        hoja("09_Estados", CEDULAS[8][1], [["Concepto", "t"], ["Estado", "t"], ["Anterior", "n"], ["Actual", "n"], ["Variación", "n"],
                                          ["Variación %", "p"], ["Vertical actual", "p"], ["Vertical anterior", "p"],
                                          ["Observación", "t"]], estados,
             explica=EXPLICA["09_Estados"]),
        hoja("10_Indices", CEDULAS[9][1], [["Indicador", "t"], ["Categoría", "t"], ["Cómo se calcula", "t"], ["Anterior", "n"],
                                          ["Actual", "n"], ["Variación", "n"], ["Semáforo", "t"], ["Lectura", "t"]], indices,
             explica=EXPLICA["10_Indices"]),
        hoja("11_Materialidad", CEDULAS[10][1], [["Concepto", "t"], ["Importe", "n"], ["Porcentaje", "n"], ["Materialidad", "n"],
                                                ["Sustento", "t"]], materialidad, explica=EXPLICA["11_Materialidad"]),
        hoja("12_Riesgos_CCI", CEDULAS[11][1], [["Código del hallazgo", "t"], ["Proceso o área", "t"], ["Hallazgo o riesgo", "t"],
                                               ["Aseveraciones", "t"], ["Probabilidad (1–5)", "i"], ["Impacto (1–5)", "i"],
                                               ["Control (1–5)", "i"], ["Riesgo inherente", "n"], ["Riesgo residual", "n"], ["Nivel", "t"],
                                               ["Respuesta de auditoría", "t"], ["Herramienta del catálogo", "t"]], matriz,
             explica=EXPLICA["12_Riesgos_CCI"]),
        hoja("13_Riesgos_Balance", CEDULAS[12][1], [["Código", "t"], ["Origen", "t"], ["Rubro o área", "t"], ["Condición observada", "t"],
                                                   ["Valor observado", "n"], ["¿Se presenta?", "t"], ["Posible riesgo", "t"],
                                                   ["Severidad", "t"], ["Norma", "t"]], posibles, explica=EXPLICA["13_Riesgos_Balance"]),
        hoja("14_Perfil", CEDULAS[13][1], [["Tipo", "t"], ["Concepto", "t"], ["Detalle", "t"], ["Importe (USD)", "n"],
                                          ["Fuente o referencia", "t"], ["Efecto en la planificación", "t"]], perfil),
        hoja("15_Notas", CEDULAS[14][1], [["Nota", "t"], ["Título de la nota", "t"], ["Cuentas del balance (códigos)", "t"],
                                         ["Saldo auditado según la nota", "n"], ["Saldo del balance anterior", "n"], ["Diferencia", "n"],
                                         ["Saldo al corte", "n"], ["Variación", "n"], ["Variación %", "p"]], notas_h,
             explica=EXPLICA["15_Notas"]),
        hoja("16_Control", CEDULAS[15][1], [["Control", "t"], ["Importe", "n"], ["Cantidad", "i"], ["Estado", "t"], ["Detalle", "t"]],
             control, explica=EXPLICA["16_Control"]),
        hoja("17_Anomalias", CEDULAS[16][1], [["Tipo", "t"], ["Código", "t"], ["Cuenta", "t"], ["Detalle", "t"], ["Importe", "n"],
                                             ["¿Se presenta?", "t"], ["Severidad", "t"]], anomalias, explica=EXPLICA["17_Anomalias"]),
        hoja("18_Cuentas_Revisar", CEDULAS[17][1], [["Código", "t"], ["Cuenta", "t"], ["Sección", "t"], ["Saldo actual", "n"],
                                                   ["Variación", "n"], ["Monto material", "t"], ["Variación material", "t"],
                                                   ["Riesgo de la carta de CI", "t"], ["Herramienta del catálogo", "t"],
                                                   ["¿Se revisa?", "t"]], cuentas_rev, explica=EXPLICA["18_Cuentas_Revisar"]),
        hoja("19_Programa", CEDULAS[18][1], [["PT", "t"], ["Área o rubro", "t"], ["Riesgo", "t"], ["Nivel", "t"],
                                            ["Respuesta de auditoría (NIA 330)", "t"], ["Herramienta del catálogo", "t"], ["Oportunidad", "t"]],
             programa, explica=EXPLICA["19_Programa"]),
        hoja("20_Narrativa", CEDULAS[19][1], [["Bloque", "t"], ["Concepto", "t"], ["Importe", "n"], ["Lectura", "t"]], narrativa,
             explica=EXPLICA["20_Narrativa"]),
        hoja("21_Estrategia", CEDULAS[20][1], [["Aspecto", "t"], ["Decisión", "x"], ["Sustento", "t"]], estrategia,
             explica=EXPLICA["21_Estrategia"]),
        hoja("22_Origenes", CEDULAS[21][1], [["Código", "t"], ["Cuenta", "t"], ["Sección", "t"], ["Variación", "n"],
                                            ["Efecto en el efectivo", "n"], ["Tipo", "t"]], origenes_h, explica=EXPLICA["22_Origenes"]),
        hoja("23_Audit_trail", CEDULAS[22][1], [["Concepto", "t"], ["Detalle", "t"], ["Valor", "n"]], trail,
             explica=EXPLICA["23_Audit_trail"]),
        hoja("24_Problemas", CEDULAS[23][1], [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e_["code"], e_["message"], n2(float(e_["amount"]))] for e_ in res["exceptions"]]),
    ]


OBS_VARIACION = "Variación superior al umbral: revisar el rubro y su documentación de respaldo."


def _tipo_efecto(v: float) -> str:
    return "Origen" if v > 0.005 else "Aplicación" if v < -0.005 else "Sin efecto"


def _f_tipo(c: str) -> str:
    return f'IF({c}>0.005,"Origen",IF({c}<-0.005,"Aplicación","Sin efecto"))'


def _causa_efecto(ev: dict, dv: dict) -> list:
    """Lectura causa-efecto de las variaciones (artefacto): (concepto, clave del importe, fórmula, valor)."""
    inv, ven, caja, cxc = (ev[k] for k in ("Inventarios", "Ventas netas", "Efectivo y equivalentes", "Cuentas por cobrar"))
    di, dven, dc, dcx = (dv[k] for k in ("Inventarios", "Ventas netas", "Efectivo y equivalentes", "Cuentas por cobrar"))
    t = CAUSA_EFECTO
    f_inv = (f'IF(ABS({inv})<=1,"{t["inv0"]}",IF({inv}>0,IF({ven}<0,"{t["inv_acum"]}",IF({ven}>0,"{t["inv_repo"]}","{t["inv_sin"]}")),'
             f'IF({ven}>0,"{t["inv_rot"]}","{t["inv_baja"]}")))')
    v_inv = (t["inv0"] if abs(di) <= 1 else (t["inv_acum"] if dven < 0 else t["inv_repo"] if dven > 0 else t["inv_sin"]) if di > 0
             else t["inv_rot"] if dven > 0 else t["inv_baja"])
    f_caja = (f'IF(AND({caja}<0,{cxc}>0),"{t["caja_cartera"]}",IF(AND({caja}>0,{cxc}<0),"{t["caja_cobro"]}",'
              f'IF(AND({caja}<0,{ven}>0,OR({cxc}<0,ABS({cxc})<ABS({caja}))),"{t["caja_senal"]}","{t["caja_sin"]}")))')
    v_caja = (t["caja_cartera"] if dc < 0 and dcx > 0 else t["caja_cobro"] if dc > 0 and dcx < 0 else
              t["caja_senal"] if dc < 0 and dven > 0 and (dcx < 0 or abs(dcx) < abs(dc)) else t["caja_sin"])
    out = [("Inventarios frente a ventas", "Inventarios", f_inv, v_inv), ("Efectivo frente a cartera", "Efectivo y equivalentes", f_caja, v_caja)]
    for concepto, k, baja, sube in (("Cuentas por pagar", "Cuentas por pagar", t["cxp_baja"], t["cxp_sube"]),
                                    ("Deuda financiera", "Obligaciones financieras", t["deuda_baja"], t["deuda_sube"]),
                                    ("Resultado del período", "Utilidad neta", t["res_baja"], t["res_sube"])):
        c, v = ev[k], dv[k]
        out.append((concepto, k, f'IF(ABS({c})<=1,"{t["sin"]}",IF({c}<0,"{baja}","{sube}"))',
                    t["sin"] if abs(v) <= 1 else baja if v < 0 else sube))
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


def _semaforo(k: str, v, fac: float = 1.0) -> str:
    if k == "dias":
        return "Base"
    if v is None or v == "":
        return "Sin dato"
    if k == "diasProveedores":
        return "Referencia"
    if k in _RENT:
        return "Verde · Positivo" if v > 0 else "Rojo · Negativo" if v < 0 else "Amarillo · En el límite"
    verde, amarillo, (ev, ea, er) = ZONAS[k]
    if k in _DIAS:
        v = v * fac
    ok = lambda c: eval(f"{v}{c}".replace("=0", "==0") if c.startswith("=") else f"{v}{c}")  # noqa: E731,S307
    return f"Verde · {ev}" if ok(verde) else f"Amarillo · {ea}" if ok(amarillo) else f"Rojo · {er}"


def _f_semaforo(k: str, c: str) -> str:
    if k == "dias":
        return '"Base"'
    if k == "diasProveedores":
        return f'IF({c}="","Sin dato","Referencia")'
    if k in _RENT:
        return f'IF({c}="","Sin dato",IF({c}>0,"Verde · Positivo",IF({c}<0,"Rojo · Negativo","Amarillo · En el límite")))'
    verde, amarillo, (ev, ea, er) = ZONAS[k]
    cc = f"{c}*{FAC}" if k in _DIAS else c
    return f'IF({c}="","Sin dato",IF({cc}{verde},"Verde · {ev}",IF({cc}{amarillo},"Amarillo · {ea}","Rojo · {er}")))'


def _lectura(k: str, v) -> str:
    if v is None or v == "":
        return SIN_DATO
    if k in LECTURA_COND:
        cond, si, no = LECTURA_COND[k]
        return si if eval(f"{v}{cond}") else no  # noqa: S307
    return LECTURA[k]


def _f_lectura(k: str, c: str) -> str:
    if k in LECTURA_COND:
        cond, si, no = LECTURA_COND[k]
        return f'IF({c}="","{SIN_DATO}",IF({c}{cond},"{si}","{no}"))'
    return f'IF({c}="","{SIN_DATO}","{LECTURA[k]}")'


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
                     "días se comparan multiplicados por meses ÷ 12, porque sobre 365 salen mayores."),
        "Lectura": ("Explica en palabras qué mide el índice y, en liquidez y capital de trabajo, si el resultado alcanza o no a "
                    "cubrir el corto plazo."),
    },
    "11_Materialidad": {
        "Importe": ("Trae de la hoja 07 el total de cada posible base del período elegido (año anterior o corte actual); en la "
                    "materialidad global busca la base elegida en la hoja 02 y, en las filas de abajo, toma la global."),
        "Porcentaje": "Trae de la hoja 02 el porcentaje de la política de la firma para cada base, para el desempeño y para el umbral trivial.",
        "Materialidad": "Multiplica el importe por el porcentaje y lo divide para 100.",
        "Sustento": ("Explica el período de la base (automático: año anterior en la revisión preliminar y corte actual en la "
                     "final), la base elegida y su justificación, escrita por el auditor o la automática según la base."),
    },
    "12_Riesgos_CCI": {
        "Riesgo inherente": "Multiplica la probabilidad por el impacto (escala de 1 a 25); en blanco si falta alguna calificación.",
        "Riesgo residual": ("Reduce el riesgo inherente según el control: con control 1 (no existe) queda igual y cada punto más de "
                            "control lo baja un 20 % (inherente × (6 − control) ÷ 5)."),
        "Nivel": ("Alto si el residual iguala o supera el umbral alto de la hoja 02, medio si supera el umbral medio y bajo en los "
                  "demás casos; sin calificación completa queda pendiente del socio."),
    },
    "13_Riesgos_Balance": {
        "Valor observado": ("Trae el dato que dispara la condición: ventas, patrimonio o utilidad de la hoja 09, el índice de la "
                            "hoja 10, la variación de la cuenta de la hoja 08 o el importe del asunto del informe anterior (hoja 14)."),
        "¿Se presenta?": ("Evalúa la condición con el valor observado (capital de trabajo negativo, días de cartera mayores a 90 "
                          "—por meses ÷ 12 en la preliminar—, aumento de días mayor al umbral de la hoja 02…); la presunción de "
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
                     "(15), indicios de empresa en marcha (13), hallazgos pendientes o cargados (12), informe anterior (14) y "
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
        "¿Se revisa?": ("Marca «Sí» cuando la cuenta tiene monto material, variación material o un riesgo de la carta de control "
                        "interno de su misma área: son las cuentas que el programa debe cubrir. Si cambia la materialidad, cambia la marca."),
    },
    "19_Programa": {
        "Nivel": "Trae el nivel del riesgo de la hoja 12 (carta de control interno) o la severidad de la hoja 13 (posibles riesgos).",
        "Respuesta de auditoría (NIA 330)": ("Para los hallazgos de la carta de control interno trae la respuesta de la hoja 12; "
                                             "para los demás riesgos, la respuesta estándar de la herramienta."),
        "Herramienta del catálogo": "Trae de la hoja 12 la herramienta del catálogo AUD que ejecuta las pruebas del riesgo.",
        "Oportunidad": ("Riesgo alto o significativo: trabajo en la visita preliminar (controles) y en la final (detalle al corte); "
                        "medio: pruebas de detalle en la final; bajo: analíticos sustantivos en la final."),
    },
    "20_Narrativa": {
        "Importe": ("Trae la cifra de la hoja donde se calcula: estados resumidos (09), índices (10), el conteo de riesgos de "
                    "las hojas 12 y 13 o, en causa-efecto, la variación del rubro en la hoja 09."),
        "Lectura": ("Escribe la conclusión con condiciones sobre las mismas cifras: si el activo creció, si el endeudamiento "
                    "supera el 70 %, el semáforo del índice y la recomendación que aplica o «No aplica»."),
    },
    "22_Origenes": {
        "Sección": "Trae de la hoja 08 la sección de la cuenta (activo, pasivo o patrimonio).",
        "Variación": ("Trae de la hoja 08 la variación de la cuenta; en la fila del resultado, la variación del resultado del período "
                      "según el balance (hoja 09)."),
        "Efecto en el efectivo": ("Un activo que sube consume efectivo (se cambia el signo); un pasivo o patrimonio que sube lo aporta. "
                                  "Abajo suma los efectos, trae la variación del efectivo de la hoja 09 y resta ambos: debe dar cero."),
        "Tipo": ("«Origen» si el efecto es positivo (fuente de efectivo), «Aplicación» si es negativo; en la última fila dice si el "
                 "puente cuadra con la variación del efectivo."),
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
         "etiqueta": "Indicador", "filas": ["Razón corriente (veces)", "Prueba ácida (veces)"]},
        {"rotulo": "Actividad", "sub": "Días · año anterior frente al corte.", "unidad": "días", "hoja": "10_Indices",
         "etiqueta": "Indicador", "filas": ["Días de cartera", "Días de inventario", "Días de proveedores",
                                            "Ciclo de conversión del efectivo (días)"]},
        {"rotulo": "Endeudamiento", "sub": "Veces · año anterior frente al corte.", "unidad": "veces", "hoja": "10_Indices",
         "etiqueta": "Indicador", "filas": ["Endeudamiento patrimonial (veces)", "Multiplicador de apalancamiento (veces)",
                                            "Endeudamiento financiero (veces)"]},
        {"rotulo": "Rentabilidad", "sub": "Porcentaje · año anterior frente al corte.", "unidad": "%", "hoja": "10_Indices",
         "etiqueta": "Indicador", "filas": ["ROI operativo (%)", "Margen operativo (%)", "ROE (%)", "Margen neto (%)",
                                            "Margen bruto (%)"]},
        {"rotulo": "Estructura del balance", "sub": "USD · año anterior frente al corte.", "unidad": "USD", "hoja": "09_Estados",
         "etiqueta": "Concepto", "filas": ["Activo corriente", "Activo no corriente", ["TOTAL PASIVO", "Pasivo total"],
                                          ["PATRIMONIO TOTAL", "Patrimonio total"]]},
        {"rotulo": "Estado de resultados", "sub": "USD · año anterior frente al corte.", "unidad": "USD", "hoja": "09_Estados",
         "etiqueta": "Concepto", "filas": ["Ventas netas", ["(−) Costo de ventas", "Costo de ventas"], "Utilidad bruta",
                                           ["(−) Gastos operativos", "Gastos operativos"], "Utilidad neta"]},
    ],
}
for _t in PANEL["tableros"]:
    _t["series"] = [["Anterior", "Anterior"], ["Actual", "Actual"]]


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
                    "y de empresa en marcha (NIA 570); controla los saldos de apertura contra las notas (NIA 510), las anomalías y "
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
             "assertion": "Todas", "procedure": "Valorar los hallazgos de la carta de control interno y los riesgos de los balances, de fraude y de empresa en marcha",
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
                "Matriz de riesgos del encargo", required=False,
                content="Una fila por hallazgo de la carta de control interno: código, proceso, hallazgo, aseveraciones, "
                        "probabilidad, impacto y control de 1 a 5 (el socio los califica) y la respuesta de auditoría."),
            req("RQ-005", "Informe de auditoría del año anterior (identificación, opinión y asuntos)", "informe_anterior", "PLA-01",
                "Perfil del encargo y asuntos que pueden persistir", required=False,
                content="Una fila por dato o asunto del informe: concepto, tipo (" + ", ".join(TIPOS_INFORME) + "), detalle, "
                        "importe si lo tiene y la fuente (párrafo o nota)."),
            req("RQ-006", "Notas a los estados financieros auditados del año anterior (total de cada nota)", "notas_estados_financieros", "PLA-06",
                "Notas comparativas y saldos de apertura", required=False,
                content="Una fila por nota de balance: número, título, códigos del balance que la forman (separados por coma) y "
                        "el saldo auditado de la nota."),
            req("RQ-007", "Informe de auditoría, notas y carta de control interno del año anterior (documentos firmados)", None, "PLA-01",
                "Respaldo de los datos transcritos en RQ-004 a RQ-006", formats=("pdf", "docx"), use="soporte", required=False),
            req("RQ-008", "RUC actualizado de la entidad", None, "PLA-01", "Identificación de la entidad y su actividad",
                formats=("pdf",), use="soporte", required=False),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo (M19): «Comercial Andina de Ejemplo S.A.», cifras ficticias -------------------------------------------------

_NOMBRES = {
    "1": "ACTIVO", "11": "ACTIVO CORRIENTE", "1101": "EFECTIVO Y EQUIVALENTES", "110101": "Caja general", "110102": "Bancos locales",
    "1102": "INVERSIONES TEMPORALES", "1103": "CUENTAS POR COBRAR CLIENTES", "110301": "Clientes locales",
    "110302": "(-) Provisión cuentas incobrables", "1104": "INVENTARIOS", "110401": "Inventario de mercadería",
    "1105": "ACTIVOS POR IMPUESTOS CORRIENTES", "1106": "OTRAS CUENTAS POR COBRAR", "110601": "Anticipos a empleados",
    "12": "ACTIVO NO CORRIENTE", "1201": "PROPIEDAD, PLANTA Y EQUIPO", "120101": "Terrenos y edificios", "120102": "Maquinaria y equipo",
    "120103": "(-) Depreciación acumulada", "1202": "ACTIVOS POR DERECHO DE USO", "1203": "ACTIVOS INTANGIBLES",
    "2": "PASIVO", "21": "PASIVO CORRIENTE", "2101": "CUENTAS Y DOCUMENTOS POR PAGAR", "210101": "Proveedores locales",
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


def _ci(id, proceso, hallazgo, aser, p, i, c, resp):
    return {"id": id, "proceso": proceso, "hallazgo": hallazgo, "aseveraciones": aser, "probabilidad": p, "impacto": i,
            "control": c, "respuesta": resp, "_row": 2}


_CARTA_EJ = [
    _ci("R01", "Ingresos", "Notas de crédito emitidas después del cierre sin aprobación de la gerencia.", "Ocurrencia; corte",
        "4", "5", "1", "Revisar las notas de crédito de enero y su aprobación; prueba de corte de la última semana de diciembre."),
    _ci("R02", "Inventarios", "No se realizan tomas físicas periódicas y las diferencias con el kárdex no se concilian.",
        "Existencia; valuación", "4", "4", "2", "Observar la toma física al cierre y conciliar el kárdex con la contabilidad."),
    _ci("R03", "Cuentas por cobrar", "La provisión de incobrables no se calcula con un modelo de pérdida crediticia esperada.",
        "Valuación", "4", "4", "2", "Recalcular la pérdida crediticia esperada con la antigüedad de la cartera (NIIF 9)."),
    _ci("R04", "Beneficios a empleados", "El cálculo actuarial de jubilación patronal no se actualizó en el año.", "Valuación; integridad",
        "3", "4", "3", "Obtener el estudio actuarial al cierre y evaluar la competencia del actuario (NIA 500 y 620)."),
    _ci("R05", "Sistema ERP y accesos", "Usuarios con acceso de administrador en el ERP sin segregación de funciones.", "Todas",
        "4", "4", "1", "Evaluar los controles generales de TI y ampliar las pruebas de asientos de diario."),
    _ci("R06", "Caja y bancos", "Conciliaciones bancarias sin firma de revisión.", "Existencia", "3", "3", "", ""),
]
_INFORME_EJ = [
    {"concepto": "Entidad auditada", "tipo": "Identificación", "detalle": "Comercial Andina de Ejemplo S.A. (datos ficticios)",
     "importe": "", "fuente": "Informe 2024 · Nota 1", "_row": 2},
    {"concepto": "Actividad", "tipo": "Identificación", "detalle": "Comercialización al por mayor de productos de consumo masivo",
     "importe": "", "fuente": "Informe 2024 · Nota 1", "_row": 3},
    {"concepto": "Opinión del año anterior", "tipo": "Opinión", "detalle": "Con salvedades (por el asunto de jubilación patronal)",
     "importe": "", "fuente": "Informe 2024 · Opinión", "_row": 4},
    {"concepto": "Jubilación patronal", "tipo": "Salvedad",
     "detalle": "La provisión no se ajustó al cálculo actuarial al cierre; el pasivo estaría subestimado.",
     "importe": "18500.00", "fuente": "Informe 2024 · Fundamento de la opinión", "_row": 5},
]
_NOTAS_EJ = [
    {"nota": "3", "titulo": "Efectivo y equivalentes de efectivo", "codigos": "1101", "saldo_auditado": "176900.00", "_row": 2},
    {"nota": "4", "titulo": "Cuentas por cobrar comerciales y otras", "codigos": "1103, 1106", "saldo_auditado": "656500.00", "_row": 3},
    {"nota": "5", "titulo": "Inventarios", "codigos": "1104", "saldo_auditado": "655400.00", "_row": 4},
    {"nota": "6", "titulo": "Propiedad, planta y equipo", "codigos": "1201", "saldo_auditado": "929100.00", "_row": 5},
    {"nota": "10", "titulo": "Obligaciones bancarias", "codigos": "2102, 2201", "saldo_auditado": "620000.00", "_row": 6},
    {"nota": "12", "titulo": "Cuentas y documentos por pagar", "codigos": "2101", "saldo_auditado": "561200.00", "_row": 7},
    {"nota": "13", "titulo": "Beneficios a empleados", "codigos": "2104, 2202", "saldo_auditado": "222400.00", "_row": 8},
]

# Ejemplo de control (a mano): activo 3.204.200 = pasivo 1.679.700 + patrimonio 1.156.850 + resultado 367.650.
# Ingresos 4.878.900 × 1 % = materialidad 48.789,00; desempeño 50 % = 24.394,50; trivial 5 % = 2.439,45.
# Nota 13: balance 83.600 + 137.800 = 221.400 contra 222.400 auditado → diferencia −1.000 (NIA 510).
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"tipoRevision": "Final", "baseMaterialidad": "Ingresos", "pctIngresos": 1, "pctDesempeno": 50, "pctTrivial": 5,
                   "fechaPreliminar": "2025-10-15", "fechaFinal": "2026-01-20", "fechaInforme": "2026-03-31",
                   "socio": "Socio del encargo", "gerente": "Gerente de auditoría", "expertos": "Actuario para jubilación patronal"},
    "datasets": {"balance_anterior": _tb(_DIC24, "saldo_anterior"), "balance_actual": _tb(_DIC25, "saldo_actual"),
                 "carta_control_interno": _CARTA_EJ, "informe_anterior": _INFORME_EJ, "notas_estados_financieros": _NOTAS_EJ},
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
           "resultados_mismo_corte": _tb(_AGO25, "saldo_eri", solo_resultados=True), "carta_control_interno": _CARTA_EJ, "informe_anterior": _INFORME_EJ}

# Pérdida (NIIF para las PYMES, encargo inicial, sin documentos del año anterior): costo de ventas +700.000 y sin impuesto;
# proveedores +577.450 para que el balance siga cuadrando. Utilidad antes de participación e impuestos = −209.800.
_PERD25 = {**_DIC25, "6101": 4102300, "5301": 0, "210101": 604300 + 577450}
# Patrimonio en déficit: resultados acumulados pasan a +1.800.000 (deudor); bancos baja lo mismo. Debe verse negativo (R2).
_DEF = 2160450
_DELTA_DEF = {"3301": _DEF, "33": _DEF, "3": _DEF, "110102": -_DEF, "1101": -_DEF, "11": -_DEF, "1": -_DEF}
_DEFICIT = [{**x, "saldo_actual": f"{float(x['saldo_actual']) + _DELTA_DEF[x['codigo']]:.2f}"} if x["codigo"] in _DELTA_DEF else x
            for x in _tb(_DIC25, "saldo_actual")]
ESCENARIOS = [
    ("base", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("preliminar_eri", _PRELIM, {"tipoRevision": "Preliminar", "mesesTranscurridos": 8, "baseMaterialidad": "Ingresos"}, "2026-08-31"),
    ("preliminar_prorrateo", {k: v for k, v in _PRELIM.items() if k != "resultados_mismo_corte"},
     {"tipoRevision": "Preliminar", "mesesTranscurridos": 8, "baseMaterialidad": "Activos totales"}, "2026-08-31"),
    ("perdida_pymes", {"balance_anterior": _tb(_DIC24, "saldo_anterior"), "balance_actual": _tb(_PERD25, "saldo_actual")},
     {"baseMaterialidad": "Utilidad antes de impuestos", "pctUAI": 5, "encargoInicial": "Sí", "_marco": MARCO_PYMES}, "2025-12-31"),
    ("patrimonio_deficit", {"balance_anterior": _tb(_DIC24, "saldo_anterior"), "balance_actual": _DEFICIT,
                            "carta_control_interno": _CARTA_EJ}, {"baseMaterialidad": "Activos totales"}, "2025-12-31"),
]
