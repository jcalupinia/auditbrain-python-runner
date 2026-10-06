"""Propiedad, planta y equipo: recálculo de depreciación, bajas, revaluación, deterioro, costos por
préstamos, componentes, desmantelamiento y conciliación del auxiliar con el mayor.

Versión simple que cumple la norma (NIC 16 / Sección 17):

1. Cada fila del auxiliar es un elemento o una parte (componente) con su propia vida útil: las partes
   significativas se deprecian por separado (NIC 16.43–47; PYMES 17.16). Toda adición del año que no
   forme parte de un elemento ya existente se registra como fila propia con su fecha de disponibilidad.
2. Depreciación lineal del período = (costo − residual) ÷ vida útil (meses) × 12 × días en uso ÷ días del
   año, sin pasar del importe depreciable pendiente (NIC 16.50, 53, 55; PYMES 17.18–17.22). Empieza cuando
   el activo está disponible para su uso y cesa en la baja; las construcciones en curso no se deprecian.
   Otros métodos (unidades producidas, saldo decreciente) no se recalculan: quedan en blanco (M22).
3. Valor neto en libros = costo − depreciación acumulada − deterioro acumulado.
4. Bajas: ganancia/pérdida = producto − valor neto en libros a la fecha de baja (NIC 16.68, 71; PYMES 17.28–17.30).
5. Revaluación (fecha de revaluación = corte): el aumento va a resultados hasta revertir el decremento previo
   del mismo activo reconocido en resultados y el resto a otro resultado integral (NIC 16.39; PYMES 17.15C);
   la disminución va a ORI hasta el superávit previo del activo y el resto a resultados (NIC 16.40; PYMES
   17.15D); clase completa (16.36; 17.15). Sin el dato del decremento previo, todo queda en ORI y se avisa.
6. Deterioro: pérdida = max(importe en libros − importe recuperable, 0) (NIC 36.59; PYMES 27.5). Si el activo
   está revaluado, la pérdida se imputa primero contra el superávit de revaluación de ese activo y solo el
   exceso a resultados (NIC 36.60–61; PYMES 27.6); sin el superávit informado no se reparte y se avisa.
7. Costos por préstamos (NIIF completas). Con el anexo de préstamos para la construcción se calcula por
   activo: el préstamo específico aporta el costo financiero del período realmente incurrido menos los
   rendimientos de la inversión temporal de esos fondos (NIC 23.12) y los préstamos generales aportan la
   tasa de capitalización —media ponderada de sus costos por intereses— aplicada a los desembolsos del
   activo financiados con ellos (NIC 23.14). Lo capitalizado en el período no excede el total de costos
   por préstamos incurridos (tope del párrafo 14). Sin el anexo se mantiene la estimación por desembolso
   con la tasa de capitalización del parámetro y se avisa. En PYMES todo costo por préstamos es gasto
   (Sección 25.2, ediciones 2015 y 2025): no se capitaliza nada y lo capitalizado es ajuste.
8. Desmantelamiento: provisión = costo estimado ÷ (1 + tasa)^años (NIC 16.16 c, NIC 37.45–47; PYMES 17.10 c
   y 21.7 b). El ajuste se separa en dos efectos (CINIIF 1): la actualización financiera del período (saldo
   inicial de la provisión × tasa) es costo financiero de resultados (1.8; NIC 37.60; PYMES 21.11) y el
   cambio de estimación va contra el costo del activo (1.5 a).
9. Conciliación auxiliar-mayor del costo y de la depreciación acumulada (roll-forward).
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores import problemas
from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja,
    m, problema, r2, ref, req, suma, validar_campos, validar_definicion_generica,
)

VERSION = "ppe_propiedad_planta 1.0"
RUBRO = "ACTIVOS_FIJOS"

_ACTIVOS = [
    campo("id", "Código del activo", alias=("codigo", "código", "activo", "codigo activo", "placa"), ejemplo="VEH-01"),
    campo("descripcion", "Descripción", alias=("detalle", "nombre", "descripcion del activo"), ejemplo="Camioneta 4x4"),
    campo("clase", "Clase", alias=("grupo", "tipo de activo", "cuenta", "categoria"), ejemplo="Vehículos"),
    campo("elemento", "Elemento al que pertenece (componente)", requerido=False, alias=("componente de", "elemento principal", "activo padre"), ejemplo=""),
    campo("fecha_uso", "Fecha disponible para uso", "date", requerido=False, alias=("fecha de uso", "fecha de activacion", "fecha inicio depreciacion", "fecha de compra"), ejemplo="2023-07-01"),
    campo("costo_inicial", "Costo al inicio del año", "number", alias=("costo inicial", "saldo inicial costo", "costo historico", "costo ajustado", "valor adquirido"), ejemplo="40000"),
    campo("adiciones", "Adiciones del año", "number", requerido=False, alias=("altas", "adiciones", "compras del año"), ejemplo="0"),
    campo("residual", "Valor residual", "number", requerido=False, alias=("valor residual", "residual", "valor de salvamento"), ejemplo="4000"),
    campo("vida_meses", "Vida útil (meses)", "number", requerido=False, alias=("vida util", "vida util meses", "meses de vida"), ejemplo="60"),
    campo("metodo", "Método de depreciación", requerido=False, alias=("metodo", "método"), ejemplo="Lineal"),
    campo("dep_acum_inicial", "Depreciación acumulada inicial", "number", requerido=False, alias=("dep acumulada inicial", "depreciacion acumulada inicial"), ejemplo="10800"),
    campo("dep_acum_cliente", "Depreciación acumulada del cliente al corte", "number", requerido=False,
          alias=("depreciacion acumulada", "dep acum", "depreciacion acum ajustada", "depreciacion acumulada al corte", "depreciacion acumulada ajustada"), ejemplo="16800"),
    campo("dep_registrada", "Depreciación del año registrada", "number", requerido=False, alias=("depreciacion del año", "gasto depreciacion", "depreciacion del mes", "gasto del periodo"), ejemplo="6000"),
    campo("vida_dias", "Vida útil (días)", "number", requerido=False, alias=("vida util dias", "dias de vida", "vida util en dias"), ejemplo="1826"),
    campo("pct_depreciacion", "% de depreciación anual", "number", requerido=False, alias=("porcentaje depreciacion", "tasa depreciacion", "% depreciacion", "porcentaje de depreciacion"), ejemplo="20"),
    campo("deterioro_acum", "Deterioro acumulado", "number", requerido=False, alias=("deterioro", "perdida por deterioro acumulada"), ejemplo="0"),
    campo("importe_recuperable", "Importe recuperable", "number", requerido=False, alias=("valor recuperable", "recuperable"), ejemplo=""),
    campo("valor_revaluado", "Valor revaluado al corte", "number", requerido=False, alias=("valor razonable", "avaluo", "valor de tasacion"), ejemplo=""),
    campo("superavit_previo", "Superávit de revaluación previo", "number", requerido=False, alias=("superavit", "reserva de revaluacion"), ejemplo=""),
    campo("decremento_previo", "Decremento previo del mismo activo reconocido en resultados", "number", requerido=False,
          alias=("decremento previo", "perdida por revaluacion previa", "disminucion previa en resultados"), ejemplo=""),
    campo("fecha_baja", "Fecha de baja", "date", requerido=False, alias=("baja", "fecha venta", "fecha de retiro"), ejemplo=""),
    campo("producto_baja", "Producto de la baja", "number", requerido=False, alias=("precio de venta", "producto", "valor de venta"), ejemplo=""),
    campo("resultado_baja", "Ganancia (pérdida) registrada en la baja", "number", requerido=False, alias=("utilidad en venta", "resultado venta"), ejemplo=""),
]
_ADICIONES = [
    campo("id", "N° de documento", alias=("documento", "factura", "comprobante"), ejemplo="AD-01"),
    campo("activo", "Código del activo", alias=("codigo", "activo"), ejemplo="OBRA-01"),
    campo("fecha", "Fecha del desembolso", "date", alias=("fecha", "fecha factura"), ejemplo="2025-03-01"),
    campo("descripcion", "Descripción", requerido=False, alias=("detalle", "concepto"), ejemplo="Avance de obra"),
    campo("tipo", "Tipo (capitalizable / reparación / mantenimiento)", requerido=False, alias=("tipo", "naturaleza"), ejemplo="Capitalizable"),
    campo("importe", "Importe", "number", alias=("valor", "monto", "importe"), ejemplo="150000"),
    campo("apto", "Activo apto (Sí/No)", requerido=False, alias=("activo apto", "apto"), ejemplo="Sí"),
    campo("intereses", "Intereses capitalizados registrados", "number", requerido=False, alias=("intereses capitalizados", "intereses"), ejemplo="9000"),
]
_PRESTAMOS = [
    campo("id", "N° de préstamo o contrato", alias=("prestamo", "préstamo", "contrato", "credito", "crédito", "documento"), ejemplo="PR-01"),
    campo("tipo", "Tipo (Específico / General)", requerido=False, alias=("tipo", "tipo de prestamo", "naturaleza", "clase de prestamo"), ejemplo="Específico"),
    campo("activo", "Activo u obra financiada (solo los específicos)", requerido=False,
          alias=("activo", "obra", "codigo activo", "activo apto", "destino"), ejemplo="OBRA-01"),
    campo("descripcion", "Descripción", requerido=False, alias=("detalle", "banco", "entidad", "concepto"), ejemplo="Banco X · nave industrial"),
    campo("importe", "Importe del préstamo vigente en el período", "number", requerido=False,
          alias=("capital", "principal", "monto", "saldo del prestamo"), ejemplo="120000"),
    campo("tasa", "Tasa nominal anual (%)", "number", requerido=False, alias=("tasa", "tasa anual", "interes"), ejemplo="9"),
    campo("costo_financiero", "Costo financiero del período realmente incurrido", "number", requerido=False,
          alias=("costo financiero", "intereses del periodo", "intereses devengados", "gasto financiero"), ejemplo="9000"),
    campo("rendimientos", "Rendimientos de la inversión temporal de esos fondos (solo los específicos)", "number", requerido=False,
          alias=("rendimientos", "rendimiento inversion temporal", "intereses ganados", "rendimientos financieros"), ejemplo="1200"),
]
# Variaciones: saldos por cuenta del balance (año anterior vs corte) → cédula sumaria. La variación se calcula.
_VARIACIONES = [
    campo("cuenta", "Cuenta contable", alias=("cuenta", "codigo cuenta", "código cuenta", "cuenta contable"), ejemplo="12010102"),
    campo("descripcion", "Descripción", requerido=False, alias=("detalle", "nombre", "descripcion de la cuenta"), ejemplo="Terreno parqueadero"),
    campo("saldo_anterior", "Saldo año anterior", "number", alias=("ano anterior", "año anterior", "saldo inicial", "saldo 2025", "periodo anterior"), ejemplo="264000"),
    campo("saldo_actual", "Saldo al corte", "number", alias=("ano actual", "año actual", "saldo final", "saldo 2026", "saldo al corte", "periodo actual"), ejemplo="264000"),
]
# Libro mayor de PP&E: una fila por movimiento del período → cédula de movimiento y conciliación.
_MAYOR = [
    campo("cuenta", "Cuenta contable", alias=("cuenta", "codigo cuenta", "código cuenta"), ejemplo="12010206"),
    campo("descripcion", "Descripción de la cuenta", requerido=False, alias=("detalle", "nombre de la cuenta"), ejemplo="Equipo de computación"),
    campo("fecha", "Fecha del movimiento", requerido=False, alias=("fecha", "fecha asiento", "fecha comprobante"), ejemplo="2026-02-18"),
    campo("comprobante", "N° de comprobante", requerido=False, alias=("comp", "comp.", "comprobante", "asiento"), ejemplo="120437"),
    campo("documento", "N° de documento", requerido=False, alias=("dmcto", "dmcto.", "documento", "doc"), ejemplo="49342"),
    campo("tipo", "Tipo de asiento", requerido=False, alias=("tp", "tipo", "tipo asiento"), ejemplo="VO"),
    campo("debe", "Debe", "number", requerido=False, alias=("debe", "debito", "débito", "cargo"), ejemplo="1500"),
    campo("haber", "Haber", "number", requerido=False, alias=("haber", "credito", "crédito", "abono"), ejemplo="0"),
    campo("importe", "Importe (valor neto del movimiento)", "number", requerido=False, alias=("valor", "monto", "importe", "saldo"), ejemplo="1500"),
]
# Facturas (adiciones y salidas): se extraen por IA del PDF (EXTRACCION_DATASETS) y se cruzan con las
# adiciones del detalle y las bajas del auxiliar en el vaucheo. Los dos datasets comparten estos campos.
_FACTURA = [
    campo("codigo_activo", "Código del activo", requerido=False, alias=("codigo", "código", "activo", "codigo activo", "placa"), ejemplo="2145"),
    campo("proveedor", "Proveedor / Cliente", requerido=False, alias=("proveedor", "razon social", "cliente", "adquiriente", "comprador", "emisor"), ejemplo="Comercial XYZ S.A."),
    campo("ruc", "RUC / Identificación", requerido=False, alias=("ruc", "ruc/ci", "identificacion", "cedula", "ci"), ejemplo="1790012345001"),
    campo("fecha", "Fecha de emisión", "date", requerido=False, alias=("fecha", "fecha emision", "fecha de emision"), ejemplo="2026-06-30"),
    campo("numero", "N° de factura (estab-ptoEmisión-secuencial)", requerido=False, alias=("factura", "numero", "número", "comprobante", "no factura", "secuencial"), ejemplo="001-041-000000528"),
    campo("total", "Total (subtotal sin IVA)", "number", requerido=False, alias=("total", "valor total", "importe", "monto", "valor", "subtotal", "subtotal sin impuestos", "base imponible"), ejemplo="52.17"),
    campo("descripcion", "Detalle", requerido=False, alias=("detalle", "descripcion", "concepto", "bien o servicio"), ejemplo="Equipo celular"),
]
# Política contable de PP&E: una fila por rubro con la vida útil y, si consta, el umbral de capitalización.
# Se extrae por IA del PDF/Word de la política (RQ-004) para la columna «vida útil según política».
_POLITICA = [
    campo("rubro", "Rubro / clase de activo", alias=("rubro", "clase", "grupo", "categoria", "tipo de activo", "cuenta"), ejemplo="Vehículos"),
    campo("vida_util_anios", "Vida útil (años)", "number", alias=("vida util", "vida util anios", "años", "anios", "vida", "vida util años"), ejemplo="5"),
    campo("umbral_capitalizacion", "Umbral de capitalización", "number", requerido=False,
          alias=("umbral", "monto minimo", "capitaliza desde", "valor minimo", "umbral de capitalizacion"), ejemplo="100"),
]
CAMPOS = {"activos": _ACTIVOS, "adiciones": _ADICIONES, "prestamos": _PRESTAMOS, "variaciones": _VARIACIONES,
          "mayor": _MAYOR, "factura": _FACTURA, "politica": _POLITICA}
TIPOS = {"activos": "activos", "adiciones": "adiciones", "prestamos": "prestamos", "variaciones": "variaciones",
         "mayor": "mayor", "facturas_adiciones": "factura", "facturas_salidas": "factura", "politica": "politica"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "activos"
# Datasets que se pueblan extrayendo por IA el texto de los PDF/Word (facturas y política), con revisión del auditor.
EXTRACCION_DATASETS = ("facturas_adiciones", "facturas_salidas", "politica")
# Guía común para leer una factura electrónica del SRI (RIDE), que trae DOS partes (emisor y adquirente) y el
# secuencial partido en tres bloques. La instrucción se indexa por DATASET (no por tipo): servicio.py busca
# EXTRACCION_INSTRUCCIONES[dataset], así que las claves deben ser «facturas_adiciones» y «facturas_salidas».
_FACTURA_RIDE = (
    "El documento es una FACTURA ELECTRÓNICA del SRI de Ecuador (RIDE). Devuelve UNA sola fila por factura. "
    "Estructura del RIDE: en la CABECERA constan la razón social y el R.U.C. de 13 dígitos del EMISOR (quien vende "
    "o emite); más abajo, en «Razón Social / Nombres y Apellidos» e «Identificación», constan los del ADQUIRENTE "
    "(el comprador). Reglas de transcripción, campo por campo:\n"
    "- numero: arma el comprobante completo con sus TRES partes establecimiento-puntoEmisión-secuencial unidas con "
    "guiones (por ejemplo 001-041-000000528), aunque en el documento vengan en líneas o celdas separadas.\n"
    "- fecha: la «Fecha Emisión» del comprobante.\n"
    "- total: el «SUBTOTAL SIN IMPUESTOS» (la base imponible, sin IVA), que es el valor que se capitaliza y se "
    "registra en el mayor; solo si el documento no desglosa impuestos, usa el «VALOR TOTAL».\n"
    "- codigo_activo: si en «Referencias» o en «Información Adicional» consta el código del activo (por ejemplo "
    "«Activo Fijo 2145»), tómalo de ahí; NO uses el código genérico de la línea del detalle (por ejemplo «AFI»).\n"
    "- descripcion: el detalle del bien de la línea.\n"
    "No inventes datos: lo que no aparezca, déjalo vacío (null)."
)
EXTRACCION_INSTRUCCIONES = {
    "facturas_adiciones":
        _FACTURA_RIDE + "\nEsta es una factura de COMPRA (adición de activo fijo). En «proveedor» pon la razón social "
        "del EMISOR (el proveedor que vende, el de la cabecera) y en «ruc» su R.U.C. de 13 dígitos; NO pongas los "
        "datos del comprador. Estos datos (proveedor, RUC, fecha y número) sirven para cotejar que la compra conste "
        "en el libro mayor y para el vaucheo.",
    "facturas_salidas":
        _FACTURA_RIDE + "\nEsta es una factura de VENTA o baja de activo fijo, que normalmente emite el propio cliente "
        "auditado. En «proveedor» (que aquí es el CLIENTE/comprador) pon la razón social del ADQUIRENTE («Razón Social "
        "/ Nombres y Apellidos») y en «ruc» su identificación; NO pongas los datos del emisor (el cliente auditado). "
        "Estos datos (cliente, RUC, fecha y número) sirven para cotejar que la venta conste en el libro mayor y para "
        "el vaucheo.",
    "politica": ("La política contable fija la vida útil por rubro de propiedad, planta y equipo. Extraiga una fila por "
                 "rubro (edificios, maquinaria, muebles, vehículos, equipos de cómputo, etc.) con su vida útil en años y, "
                 "si consta, el umbral mínimo para capitalizar. No invente: lo que no aparezca, déjelo vacío."),
}
EXTRACCION_ENUMS = {}
CONTROL = "costo_inicial"
TOTAL_EJEMPLO = "ajusteResultado"

# Dashboard (formato en graficos.py): la población es el costo de los activos del auxiliar; la cifra
# que el auditor recalcula frente a la registrada es la depreciación del año, comparada solo en los activos
# que se pudieron recalcular (un método no lineal queda sin recálculo), así la brecha es el ajuste de depreciación.
PANEL = {
    "poblacion":    {"rotulo": "Costo de activos evaluados", "hoja": "04_Depreciacion", "col": "Costo"},
    "recalculado":  {"rotulo": "Depreciación recalculada", "total": "depRecalculada"},
    "registrado":   {"rotulo": "Depreciación registrada (activos recalculados)", "hoja": "04_Depreciacion",
                     "col": "Depreciación registrada", "con_valor": "Depreciación recalculada"},
    "composicion":  {"rotulo": "Depreciación por activo", "hoja": "04_Depreciacion", "etiqueta": "Código",
                     "valor": "Depreciación recalculada"},
    "distribucion": {"rotulo": "Costo por clase de activo", "hoja": "05_Vidas_residual", "etiqueta": "Clase", "valor": "Costo"},
    # Tablero premium: categoría FIJA que calcula el módulo (estado del activo: En uso / En construcción / Baja,
    # columna «Estado» de la cédula 04, no la «Clase» libre del cliente), con dos columnas comparables en USD
    # (costo bruto frente al valor neto en libros). Las barras salen por fórmula SUMIFS de la cédula 19.
    "tableros": [
        {"rotulo": "Costo y valor neto por estado del activo",
         "sub": "USD · costo bruto frente al valor neto en libros, por estado del activo (NIC 16).",
         "unidad": "USD", "hoja": "19_Resumen_estado", "etiqueta": "Estado",
         "series": [["Costo", "Costo"], ["Valor neto en libros", "Valor neto en libros"]],
         "filas": ["En uso", "En construcción", "Baja"],
         "seccion": "Resumen por estado del activo"},
    ],
}

PARAMETROS = {
    "tolerancia": 1, "tasaCapitalizacion": None, "umbralComponente": 10, "umbralRevisarComponentes": None,
    "costoDesmantelamiento": None, "aniosDesmantelamiento": None, "tasaDesmantelamiento": None,
    "provisionDesmantelamiento": None, "provisionDesmantelamientoInicial": None, "mayorCosto": None, "mayorDepAcum": None,
    # Vida útil NIIF por clase (años), confirmada por el auditor. Se aplica a los activos de esa clase que no traen
    # vida propia en el auxiliar; en blanco, esos activos quedan «vida útil pendiente» (sin defaults automáticos).
    "vidaInmuebles": None, "vidaInstalacionesMaquinaria": None, "vidaMuebles": None, "vidaVehiculos": None, "vidaEquipoComputo": None,
}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "tolerancia": "Tolerancia por activo (importe)", "tasaCapitalizacion": "Tasa de capitalización de intereses (% anual)",
    "umbralComponente": "Parte significativa desde (% del costo del elemento)",
    "umbralRevisarComponentes": "Revisar componentes de elementos con costo desde",
    "costoDesmantelamiento": "Desmantelamiento: costo estimado futuro", "aniosDesmantelamiento": "Desmantelamiento: años hasta el desembolso",
    "tasaDesmantelamiento": "Desmantelamiento: tasa de descuento antes de impuestos (%)",
    "provisionDesmantelamiento": "Provisión de desmantelamiento registrada (cierre)",
    "provisionDesmantelamientoInicial": "Provisión de desmantelamiento registrada al inicio del ejercicio",
    "mayorCosto": "Mayor: costo al cierre", "mayorDepAcum": "Mayor: depreciación acumulada al cierre",
    "vidaInmuebles": "Vida útil NIIF (años) · Inmuebles y construcciones",
    "vidaInstalacionesMaquinaria": "Vida útil NIIF (años) · Instalaciones, maquinaria y equipos",
    "vidaMuebles": "Vida útil NIIF (años) · Muebles y enseres",
    "vidaVehiculos": "Vida útil NIIF (años) · Vehículos y equipo de transporte",
    "vidaEquipoComputo": "Vida útil NIIF (años) · Equipos de cómputo y software",
}


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    v = validar_campos(CAMPOS[tipo], filas)
    if tipo == "activos":
        for f in filas:
            vida = a_num(f.get("vida_meses")) if str(f.get("vida_meses", "") or "").strip() else None
            if vida is not None and vida <= 0:
                v["errors"].append({"row": f.get("_row"), "field": "vida_meses", "message": "Vida útil: use meses mayores que cero (en blanco si no se deprecia, p. ej. terrenos)."})
        v["ok"] = not v["errors"]
    return v


# --- cálculo -----------------------------------------------------------------

def _t(v) -> str:
    return str(v if v is not None else "").strip()


def _opc(v):
    """Número opcional: None si la celda viene vacía."""
    return a_num(v) if _t(v) else None


def _hace_un_anio(d):
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # 29 de febrero
        return d.replace(year=d.year - 1, day=28)


def _lineal(metodo: str) -> bool:
    return metodo == "" or "lineal" in metodo.lower()


# Cubetas de vida útil NIIF por clase (parámetros que confirma el auditor). El orden importa: se prueba cómputo
# antes que «equipo» y transporte antes que el genérico, para que «equipo de computación» y «equipo de transporte»
# caigan en su cubeta correcta y no en maquinaria.
_BUCKETS_VIDA = (
    ("vidaEquipoComputo", ("comput", "informat", "software", "hardware", "servidor", "laptop", "impresora", "tecnolog")),
    ("vidaVehiculos", ("vehic", "transport", "camion", "camión", "autom", "moto", "furgon", "furgón", "montacarga")),
    ("vidaMuebles", ("mueble", "enser")),
    ("vidaInmuebles", ("inmueble", "edifici", "construc", "local", "bodega", "nave", "galpon", "galpón")),
    ("vidaInstalacionesMaquinaria", ("maquinar", "instalac", "equipo", "herramient", "planta")),
)


def _es_terreno(clase: str) -> bool:
    return "terreno" in (clase or "").lower()


def _clase_bucket(clase: str):
    """Mapea la clase / tipo de activo del auxiliar a su cubeta de vida útil por clase (parámetros del auditor).
    Devuelve None para terrenos (no se deprecian) o clases no reconocidas: la vida queda pendiente de confirmar.
    Es robusto a tildes para que «Vehículos», «Eq. Cómputo», etc. caigan en su cubeta."""
    import unicodedata as _ud
    c = "".join(ch for ch in _ud.normalize("NFD", (clase or "").lower()) if _ud.category(ch) != "Mn")
    if not c or _es_terreno(c):
        return None
    for clave, palabras in _BUCKETS_VIDA:
        if any(w in c for w in palabras):
            return clave
    return None


def _tot(filas, k):
    """Total de una columna de la cédula de capitalización: vacío si algún activo quedó sin medir (M22)."""
    return None if any(f[k] is None for f in filas) else sum(f[k] for f in filas)


def _p(p, k):
    v = p.get(k)
    return None if v is None or _t(v) == "" else float(a_num(v))


# Recálculo fiscal (SRI). Tasas máximas de depreciación por clase (RALRTI Art. 28 núm. 6) y tope de vehículos
# (LRTI Art. 10 núm. 7). Son máximos legales; la base NIIF (vida útil) es independiente y la fija el auditor.
TOPE_VEHICULO = 35000.0
# Días por año para el método de depreciación por días (criterio del papel de trabajo del auditor y del SRI).
DIAS_ANIO_VIDA = 365
_TASA_FISCAL = {"vidaInmuebles": 0.05, "vidaInstalacionesMaquinaria": 0.10, "vidaMuebles": 0.10,
                "vidaVehiculos": 0.20, "vidaEquipoComputo": 0.3333}
# Vida útil por defecto según la normativa del SRI (inversa de la tasa máxima del Art. 28): cuando el auxiliar NO
# trae vida útil y el auditor no la fijó por parámetro, el papel usa esta vida del SRI para recalcular (criterio de
# auditoría), en vez de dejar el activo sin recálculo. El activo queda marcado como «vida según SRI».
_VIDA_SRI_ANIOS = {"vidaInmuebles": 20, "vidaInstalacionesMaquinaria": 10, "vidaMuebles": 10,
                   "vidaVehiculos": 5, "vidaEquipoComputo": 3}


def _tasa_fiscal(clase):
    """Tasa máxima de depreciación fiscal (SRI Art. 28) por clase; None para terrenos o clases no mapeadas."""
    return _TASA_FISCAL.get(_clase_bucket(clase))


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    # EDATE(corte;-12)+1: primer día del ejercicio.
    from datetime import timedelta
    inicio = _hace_un_anio(corte_a) + timedelta(days=1)
    dias_anio = (corte_a - inicio).days + 1
    pymes = es_pymes(p)
    tol = _p(p, "tolerancia") or 0.0
    tasa_cap = _p(p, "tasaCapitalizacion")

    activos = []
    for f in datasets.get("activos") or []:
        if not _t(f.get("id")):
            continue
        clase = _t(f.get("clase"))
        vida = _opc(f.get("vida_meses"))
        if vida is not None and vida <= 0:
            raise ValueError(f"Activo {_t(f.get('id'))}: la vida útil debe ser mayor que cero.")
        # Vida útil NIIF cuando el activo no trae vida propia: primero la que confirmó el auditor por clase (parámetro);
        # si no la fijó, se usa por defecto la vida del SRI (Art. 28) para recalcular como criterio de auditoría. Solo
        # las clases no reconocidas (o terrenos) quedan pendientes.
        vida_por_clase = vida_sri = False
        if vida is None:
            _bkt = _clase_bucket(clase)
            _anios = _p(p, _bkt) if _bkt else None
            if (_anios is None or _anios <= 0) and _bkt:
                _anios = _VIDA_SRI_ANIOS.get(_bkt)  # fallback: vida útil del SRI
                vida_sri = _anios is not None
            if _anios is not None and _anios > 0:
                vida, vida_por_clase = _anios * 12, True
        a = {"id": _t(f.get("id")), "desc": _t(f.get("descripcion")), "clase": clase, "elemento": _t(f.get("elemento")),
             "uso": fecha(f.get("fecha_uso")) if _t(f.get("fecha_uso")) else None, "ci": _opc(f.get("costo_inicial")) or 0.0,
             "ad": _opc(f.get("adiciones")), "res": _opc(f.get("residual")), "vida": vida, "vidaPorClase": vida_por_clase, "vidaSRI": vida_sri, "metodo": _t(f.get("metodo")),
             "dai": _opc(f.get("dep_acum_inicial")) if _t(f.get("dep_acum_inicial")) != "" else _opc(f.get("dep_acum_cliente")),
             "dreg": _opc(f.get("dep_registrada")), "dac": _opc(f.get("dep_acum_cliente")),
             "det": _opc(f.get("deterioro_acum")),
             "rec": _opc(f.get("importe_recuperable")), "rev": _opc(f.get("valor_revaluado")), "sup": _opc(f.get("superavit_previo")),
             "decPrev": _opc(f.get("decremento_previo")),
             "baja": fecha(f.get("fecha_baja")) if _t(f.get("fecha_baja")) else None, "prod": _opc(f.get("producto_baja")),
             "resreg": _opc(f.get("resultado_baja")), "_row": f.get("_row")}
        if a["baja"] and not inicio <= a["baja"] <= corte_a:
            raise ValueError(f"Activo {a['id']}: la fecha de baja debe estar dentro del ejercicio ({inicio.isoformat()} a {corte_a.isoformat()}).")
        activos.append(a)
    if not activos:
        raise ValueError("Cargue el auxiliar de propiedad, planta y equipo por activo.")

    # 2–3 · depreciación y valor neto en libros (misma aritmética que el Excel).
    for a in activos:
        a["costo"] = a["ci"] + (a["ad"] or 0)
        a["depr"] = max(a["costo"] - (a["res"] or 0), 0)
        if a["uso"] is None:
            a["dias"] = 0
        else:
            hasta = min(a["baja"], corte_a) if a["baja"] else corte_a
            a["dias"] = max((hasta - max(a["uso"], inicio)).days + 1, 0)
        if not _lineal(a["metodo"]):
            a["dep"] = None
        elif a["vida"] is None or a["dias"] == 0:
            a["dep"] = 0.0
        else:
            a["dep"] = min(a["depr"] / a["vida"] * 12 * a["dias"] / dias_anio, max(a["depr"] - (a["dai"] or 0), 0))
        a["dif"] = None if a["dep"] is None or a["dreg"] is None else a["dep"] - a["dreg"]
        a["acum"] = None if a["dep"] is None else (a["dai"] or 0) + a["dep"]
        a["nbv"] = None if a["acum"] is None else a["costo"] - a["acum"] - (a["det"] or 0)
        a["total_dep"] = None if a["acum"] is None else ("Sí" if a["depr"] > 0 and a["acum"] >= a["depr"] - 0.005 else "No")
        a["estado"] = "Baja" if a["baja"] else ("En construcción" if a["uso"] is None else "En uso")
        a["remanente"] = None if a["vida"] is None or a["acum"] is None or a["depr"] == 0 else max(a["depr"] - a["acum"], 0) / a["depr"] * a["vida"]
        a["resid_pct"] = None if a["costo"] == 0 else (a["res"] or 0) / a["costo"]
    vivos = [a for a in activos if a["estado"] != "Baja"]

    # Recálculo fiscal (SRI Art. 28): tasa máxima por clase, tope de vehículos (Art. 10 núm. 7) y diferencia con la
    # depreciación NIIF. Es la base tributaria (deducible) frente a la NIIF; no altera el ajuste contable a resultados.
    for a in activos:
        bkt = _clase_bucket(a["clase"])
        a["tasa_fiscal"] = _TASA_FISCAL.get(bkt)
        es_veh = bkt == "vidaVehiculos"
        if a["tasa_fiscal"] is None or not _lineal(a["metodo"]) or a["dias"] == 0:
            a["base_fiscal"] = a["dep_fiscal"] = a["dif_fiscal"] = None
            a["exceso_veh"] = 0.0
        else:
            factor = a["dias"] / dias_anio
            sobre_tope = es_veh and a["costo"] > TOPE_VEHICULO
            a["base_fiscal"] = TOPE_VEHICULO if sobre_tope else a["costo"]
            a["dep_fiscal"] = a["base_fiscal"] * a["tasa_fiscal"] * factor
            a["exceso_veh"] = (a["costo"] - TOPE_VEHICULO) * a["tasa_fiscal"] * factor if sobre_tope else 0.0
            a["dif_fiscal"] = None if a["dep"] is None else a["dep"] - a["dep_fiscal"]

    # Fase 5 · política contable: vida útil por rubro, extraída por IA de la política (RQ-004). Se mapea cada
    # rubro a la clase NIIF (_clase_bucket) para aplicar su vida útil a los activos de esa clase.
    import unicodedata as _ud
    _sin_tildes = lambda s: "".join(c for c in _ud.normalize("NFD", str(s or "")) if _ud.category(c) != "Mn")
    _bucket_pol = lambda x: _clase_bucket(_sin_tildes(x))  # robusto a tildes (p. ej. «Vehículos»)
    mapa_pol = {}
    for f in datasets.get("politica") or []:
        bkt = _bucket_pol(f.get("rubro"))
        va = _opc(f.get("vida_util_anios"))
        if bkt and va and va > 0:
            mapa_pol[bkt] = va

    # Fase 2 · recálculo comparativo. Reproduce el método del papel de trabajo del auditor
    # (depreciación diaria × días, como en las cédulas por clase del «DE») y compara tres
    # criterios de vida útil por activo: anexo/NIIF, SRI (Art. 28) y política (se conecta en
    # la lectura de la política). Aditivo: no altera dep/acum/ajusteResultado.
    for a in activos:
        # Depreciación acumulada del cliente al corte: la informada en el anexo si viene; si no,
        # apertura (dep. acum. inicial) + gasto del año registrado por el cliente.
        a["acum_cliente"] = a["dac"] if a.get("dac") is not None else ((a["dai"] or 0) + (a["dreg"] or 0))
        # Días acumulados desde que el activo quedó disponible para uso hasta el corte (o la baja).
        if a["uso"] is None:
            a["dias_acum"] = 0
        else:
            hasta = min(a["baja"], corte_a) if a["baja"] else corte_a
            a["dias_acum"] = max((hasta - a["uso"]).days + 1, 0)
        # Vidas útiles en años por criterio.
        a["vida_anios_anexo"] = (a["vida"] / 12) if a["vida"] else None     # NIIF: del anexo o la clase confirmada
        _ts = a.get("tasa_fiscal")
        a["vida_anios_sri"] = (1.0 / _ts) if _ts else None                  # SRI Art. 28: 1 / tasa máxima
        a["vida_anios_pol"] = mapa_pol.get(_bucket_pol(a["clase"]))         # política contable (si se cargó)

        def _por_dias(vida_anios, base):
            """Método por días: diaria = base / (vida años × 365); gasto del período y acumulada al corte,
            topados por el importe depreciable y por la vida. Devuelve (diaria, gasto, acumulada)."""
            if not vida_anios or vida_anios <= 0 or not base or base <= 0 or not _lineal(a["metodo"]):
                return (None, None, None)
            vida_dias = vida_anios * DIAS_ANIO_VIDA
            diaria = base / vida_dias
            gasto = min(diaria * a["dias"], base) if a["dias"] else 0.0
            acum = min(diaria * min(a["dias_acum"], vida_dias), base)
            return (diaria, gasto, acum)

        a["diaria_anexo"], a["gasto_dias_anexo"], a["acum_dias_anexo"] = _por_dias(a["vida_anios_anexo"], a["depr"])
        # SRI: base deducible (con tope de vehículos) y sin valor residual (criterio fiscal).
        a["diaria_sri"], a["gasto_dias_sri"], a["acum_dias_sri"] = _por_dias(a["vida_anios_sri"], a.get("base_fiscal"))
        # Política contable (si se cargó): mismo método por días con la vida útil de la política.
        a["diaria_pol"], a["gasto_dias_pol"], a["acum_dias_pol"] = _por_dias(a["vida_anios_pol"], a["depr"])
        # Diferencias del auditor (método días, criterio NIIF/anexo) frente al cliente.
        a["dif_gasto_dias"] = None if a["gasto_dias_anexo"] is None or a["dreg"] is None else a["gasto_dias_anexo"] - a["dreg"]
        a["dif_acum_dias"] = None if a["acum_dias_anexo"] is None else a["acum_dias_anexo"] - a["acum_cliente"]

    # Componentes: elementos con más de una fila.
    grupo = lambda a: a["elemento"] or a["id"]
    conteo = {}
    for a in activos:
        conteo[grupo(a)] = conteo.get(grupo(a), 0) + 1
    comp = [a for a in activos if conteo[grupo(a)] > 1]
    umbral = _p(p, "umbralComponente") or 0.0
    for a in comp:
        tot = sum(x["costo"] for x in comp if grupo(x) == grupo(a))
        a["costo_elem"] = tot
        a["part"] = None if tot == 0 else a["costo"] / tot
        a["signif"] = "" if a["part"] is None else ("Sí" if a["part"] >= umbral / 100 else "No")

    # 4 · bajas.
    bajas = [a for a in activos if a["baja"]]
    for a in bajas:
        a["nbv_baja"] = None if a["acum"] is None else a["costo"] - a["acum"] - (a["det"] or 0)
        a["res_calc"] = None if a["nbv_baja"] is None else (a["prod"] or 0) - a["nbv_baja"]
        a["res_dif"] = None if a["res_calc"] is None or a["resreg"] is None else a["res_calc"] - a["resreg"]

    # 5 · revaluación al corte. NIC 16.39 (2.ª frase) y PYMES 17.15C: el aumento va a resultados hasta revertir un
    # decremento anterior del mismo activo reconocido en resultados; sin ese dato, todo queda en ORI y se avisa.
    reval = [a for a in vivos if a["rev"] is not None and a["nbv"] is not None]
    for a in reval:
        d = a["rev"] - a["nbv"]
        s = a["sup"] or 0
        a["rev_dif"] = d
        if d >= 0:
            a["rev_res"] = 0.0 if a["decPrev"] is None else min(d, a["decPrev"])
            a["rev_ori"] = d - a["rev_res"]
        else:
            a["rev_ori"] = -min(-d, s)
            a["rev_res"] = d + min(-d, s)

    # 6 · deterioro. NIC 36.60-61 y PYMES 27.6: en un activo revaluado la pérdida es un decremento de revaluación:
    # primero contra el superávit remanente de ese activo (ORI) y solo el exceso a resultados.
    deter = [a for a in vivos if a["rec"] is not None]
    for a in deter:
        a["libros"] = a["rev"] if a["rev"] is not None else a["nbv"]
        a["perdida"] = None if a["libros"] is None else max(a["libros"] - a["rec"], 0)
        a["supPrev"] = a["sup"] or 0.0
        a["revOri"] = a["rev_ori"] if "rev_ori" in a else 0.0
        a["supRem"] = max(a["supPrev"] + a["revOri"], 0)
        revaluado = a["rev"] is not None or a["sup"] is not None
        if a["perdida"] is None:
            a["detORI"], a["detRes"] = None, None
        elif not revaluado:
            a["detORI"], a["detRes"] = 0.0, a["perdida"]
        elif a["sup"] is None:                       # revaluado sin dato de superávit: no se reparte (M22)
            a["detORI"], a["detRes"] = None, a["perdida"]
        else:
            a["detORI"] = min(a["perdida"], a["supRem"])
            a["detRes"] = a["perdida"] - a["detORI"]

    # 7 · adiciones y costos por préstamos.
    por_id = {a["id"]: a for a in activos}
    adiciones = []
    for f in datasets.get("adiciones") or []:
        if not _t(f.get("id")) and not _t(f.get("activo")):
            continue
        x = {"id": _t(f.get("id")), "activo": _t(f.get("activo")), "fecha": fecha(f.get("fecha")), "desc": _t(f.get("descripcion")),
             "tipo": _t(f.get("tipo")), "importe": _opc(f.get("importe")) or 0.0, "apto": _t(f.get("apto")),
             "int": _opc(f.get("intereses")), "_row": f.get("_row")}
        if x["fecha"] is None:
            raise ValueError(f"Adición {x['id']}: indique la fecha del desembolso.")
        act = por_id.get(x["activo"])
        fin = corte_a if act is None or act["uso"] is None else min(act["uso"], corte_a)
        es_apto = x["apto"].lower() in ("sí", "si")
        x["dias"] = 0 if pymes or not es_apto else max((fin - max(x["fecha"], inicio)).days, 0)
        x["cap"] = 0.0 if x["dias"] == 0 else (None if tasa_cap is None else x["importe"] * tasa_cap / 100 * x["dias"] / dias_anio)
        x["int_dif"] = None if x["cap"] is None else x["cap"] - (x["int"] or 0)
        low = x["tipo"].lower()
        x["capitalizable"] = "No: gasto (NIC 16.12)" if ("repar" in low or "manten" in low) else "Sí"
        x["existe"] = act is not None
        adiciones.append(x)

    # 7 bis · anexo de préstamos para la construcción (NIC 23.12 y 14).
    prestamos = []
    for f in datasets.get("prestamos") or []:
        if not _t(f.get("id")):
            continue
        tp = _t(f.get("tipo")).lower()
        y = {"id": _t(f.get("id")), "tipo": "Específico" if tp.startswith("esp") else ("General" if tp.startswith("gen") else ""),
             "activo": _t(f.get("activo")), "desc": _t(f.get("descripcion")), "importe": _opc(f.get("importe")),
             "tasa": _opc(f.get("tasa")), "costo": _opc(f.get("costo_financiero")), "rend": _opc(f.get("rendimientos")),
             "_row": f.get("_row")}
        # NIC 23.12: en el específico lo capitalizable es el costo realmente asumido menos los rendimientos de la
        # inversión temporal de esos fondos. Sin uno de los dos datos el importe queda vacío (M22).
        y["cap_esp"] = None if y["tipo"] != "Específico" or y["costo"] is None or y["rend"] is None else y["costo"] - y["rend"]
        prestamos.append(y)

    # NIC 23.14: tasa de capitalización = media ponderada de los costos por intereses de los préstamos genéricos.
    generales = [y for y in prestamos if y["tipo"] == "General"]
    if not generales:
        tasa_gen = 0.0
    elif any(y["importe"] is None or y["costo"] is None for y in generales) or sum(y["importe"] or 0 for y in generales) == 0:
        tasa_gen = None
    else:
        tasa_gen = sum(y["costo"] for y in generales) / sum(y["importe"] for y in generales)

    esp_por_activo = {}
    for y in prestamos:
        if y["tipo"] == "Específico" and y["activo"]:
            esp_por_activo.setdefault(y["activo"], []).append(y)
    capit = []
    if prestamos:
        orden = []
        for x in adiciones:
            if (x["dias"] > 0 or (x["int"] or 0) != 0) and x["activo"] not in orden:
                orden.append(x["activo"])
        for k in esp_por_activo:
            if k not in orden:
                orden.append(k)
        for k in orden:
            ads = [x for x in adiciones if x["activo"] == k]
            esps = esp_por_activo.get(k, [])
            des = sum(x["importe"] for x in ads if x["dias"] > 0)
            base = sum(x["importe"] * x["dias"] for x in ads) / dias_anio
            imp = None if any(y["importe"] is None for y in esps) else sum(y["importe"] for y in esps)
            cap_e = 0.0 if pymes else (None if any(y["cap_esp"] is None for y in esps) else sum(y["cap_esp"] for y in esps))
            pct = None if imp is None else (0.0 if des == 0 else max(1 - imp / des, 0))
            bg = None if pct is None else base * pct
            cg = 0.0 if pymes else (None if bg is None or tasa_gen is None else bg * tasa_gen)
            capit.append({"activo": k, "desemb": des, "base": base, "esp_imp": imp, "esp_cap": cap_e, "pct": pct,
                          "base_gen": bg, "tasa": 0.0 if pymes else tasa_gen, "cap_gen": cg,
                          "antes": None if cap_e is None or cg is None else cap_e + cg,
                          "reg": sum(x["int"] or 0 for x in ads)})
    # Tope del párrafo 14: lo capitalizado en el período no excede los costos por préstamos incurridos.
    tope_inc = sum(y["costo"] for y in prestamos if y["costo"] is not None)
    tope_antes = sum(a["antes"] for a in capit if a["antes"] is not None)
    tope_completo = bool(prestamos) and all(y["costo"] is not None for y in prestamos) and all(a["antes"] is not None for a in capit)
    factor = None if not tope_completo else (1.0 if tope_antes <= tope_inc else tope_inc / tope_antes)
    for a in capit:
        a["factor"] = factor
        a["final"] = None if a["antes"] is None else (a["antes"] if factor is None else a["antes"] * factor)
        a["dif"] = None if a["final"] is None else a["final"] - a["reg"]
    if prestamos:                    # con anexo el capitalizable se mide por activo, no por desembolso
        for x in adiciones:
            x["cap"], x["int_dif"] = None, None

    # 8 · desmantelamiento.
    # CINIIF 1.5 a / 1.8 (PYMES 21.7 b y 21.11): el cambio de estimación va contra el costo del activo; la reversión
    # del descuento del período (saldo inicial de la provisión × tasa) es costo financiero del ejercicio.
    cd, an, td = _p(p, "costoDesmantelamiento"), _p(p, "aniosDesmantelamiento"), _p(p, "tasaDesmantelamiento")
    prov_reg = _p(p, "provisionDesmantelamiento")
    prov_ini = _p(p, "provisionDesmantelamientoInicial")
    if prov_ini is None and prov_reg is None:
        prov_ini = 0.0                               # sin provisión registrada al cierre no hay saldo inicial que actualizar
    vp = None if cd is None or an is None or td is None else cd / (1 + td / 100) ** an
    act = None if vp is None or prov_ini is None or td is None else prov_ini * td / 100
    dif = None if vp is None else vp - (prov_reg or 0)
    desm = {"costo": cd, "anios": an, "tasa": td, "vp": vp, "registrada": prov_reg, "inicial": prov_ini, "dif": dif,
            "actualizacion": act, "cambio": None if dif is None or act is None else dif - act}

    # 9 · roll-forward y conciliación con el mayor (datos registrados).
    s = lambda it, k: sum(x[k] or 0 for x in it)
    rf = {"ci": s(activos, "ci"), "ad": s(activos, "ad"), "costoBajas": s(bajas, "costo")}
    rf["costoFinal"] = rf["ci"] + rf["ad"] - rf["costoBajas"]
    rf["mayorCosto"] = _p(p, "mayorCosto")
    rf["difCosto"] = None if rf["mayorCosto"] is None else rf["costoFinal"] - rf["mayorCosto"]
    rf["dai"] = s(activos, "dai")
    rf["dreg"] = s(activos, "dreg")
    rf["depBajas"] = s(bajas, "dai") + s(bajas, "dreg")
    rf["depFinalReg"] = rf["dai"] + rf["dreg"] - rf["depBajas"]
    rf["mayorDep"] = _p(p, "mayorDepAcum")
    rf["difDep"] = None if rf["mayorDep"] is None else rf["depFinalReg"] - rf["mayorDep"]
    rf["depFinalCalc"] = sum(a["acum"] for a in vivos if a["acum"] is not None)
    rf["nbv"] = sum(a["nbv"] for a in vivos if a["nbv"] is not None)
    rf["costoVivos"] = sum(a["costo"] for a in vivos)
    rf["adDetalle"] = sum(x["importe"] for x in adiciones) if adiciones else None
    rf["difAd"] = None if rf["adDetalle"] is None else rf["ad"] - rf["adDetalle"]

    # Fase 3 · sumaria (variaciones del balance), movimiento del libro mayor y conciliación de saldos.
    # Cada cuenta del balance se clasifica en costo o depreciación por su descripción (las de depreciación
    # suelen tener saldo acreedor; se comparan en valor absoluto con la depreciación acumulada del auxiliar).
    _es_dep = lambda t: "deprecia" in (t or "").lower()
    variaciones = []
    for f in datasets.get("variaciones") or []:
        if not _t(f.get("cuenta")):
            continue
        sa = _opc(f.get("saldo_anterior")) or 0.0
        sc = _opc(f.get("saldo_actual")) or 0.0
        variaciones.append({"cuenta": _t(f.get("cuenta")), "desc": _t(f.get("descripcion")), "ant": sa, "act": sc,
                            "var": sc - sa, "tipo": "Depreciación" if _es_dep(f.get("descripcion")) else "Costo",
                            "_row": f.get("_row")})
    costo_balance = sum(v["act"] for v in variaciones if v["tipo"] == "Costo")
    dep_balance = abs(sum(v["act"] for v in variaciones if v["tipo"] == "Depreciación"))

    # Movimiento del período agregado por cuenta (débitos, créditos, neto y número de asientos).
    mov = {}
    for f in datasets.get("mayor") or []:
        if not _t(f.get("cuenta")):
            continue
        cta = _t(f.get("cuenta"))
        e = mov.setdefault(cta, {"cuenta": cta, "desc": _t(f.get("descripcion")), "debe": 0.0, "haber": 0.0, "n": 0})
        imp = _opc(f.get("importe"))
        deb = _opc(f.get("debe"))
        hab = _opc(f.get("haber"))
        if deb is None and hab is None and imp is not None:  # una sola columna de importe con signo
            deb, hab = (imp, 0.0) if imp >= 0 else (0.0, -imp)
        e["debe"] += deb or 0.0
        e["haber"] += hab or 0.0
        e["n"] += 1
        if not e["desc"]:
            e["desc"] = _t(f.get("descripcion"))
    mayor = sorted(mov.values(), key=lambda x: x["cuenta"])
    for e in mayor:
        e["neto"] = e["debe"] - e["haber"]

    # Conciliación de saldos del cliente: auxiliar (anexo) frente al balance (variaciones).
    concil = {"costo_aux": rf["costoFinal"], "costo_bal": (costo_balance if variaciones else None),
              "dep_aux": rf["depFinalReg"], "dep_bal": (dep_balance if variaciones else None)}
    concil["dif_costo"] = None if concil["costo_bal"] is None else concil["costo_aux"] - concil["costo_bal"]
    concil["dif_dep"] = None if concil["dep_bal"] is None else concil["dep_aux"] - concil["dep_bal"]

    # Fase 4 · vaucheo de facturas (extraídas por IA de los PDF). Cada factura de adición se cruza con las
    # adiciones del detalle por el código del activo; cada factura de salida, con las bajas del auxiliar.
    def _facturas(ds_key, tipo):
        out = []
        for f in datasets.get(ds_key) or []:
            if not (_t(f.get("numero")) or _t(f.get("proveedor")) or _opc(f.get("total")) is not None):
                continue
            out.append({"tipo": tipo, "cod": _t(f.get("codigo_activo")), "prov": _t(f.get("proveedor")),
                        "ruc": _t(f.get("ruc")), "fecha": _t(f.get("fecha")), "num": _t(f.get("numero")),
                        "total": _opc(f.get("total")), "desc": _t(f.get("descripcion")), "_row": f.get("_row")})
        return out
    fact_ad = _facturas("facturas_adiciones", "Adición")
    fact_ba = _facturas("facturas_salidas", "Baja")
    ad_por_cod = {}
    for x in adiciones:
        ad_por_cod[x["activo"]] = ad_por_cod.get(x["activo"], 0.0) + (x["importe"] or 0.0)
    ba_por_cod = {a["id"]: (a["prod"] or 0.0) for a in bajas}
    vaucheo = []
    for fa in fact_ad + fact_ba:
        reg_monto = ad_por_cod.get(fa["cod"]) if fa["tipo"] == "Adición" else ba_por_cod.get(fa["cod"])
        dif = None if reg_monto is None or fa["total"] is None else fa["total"] - reg_monto
        estado = ("Sin registro en libros" if reg_monto is None
                  else ("Conciliado" if dif is not None and abs(dif) <= tol else "Diferencia"))
        vaucheo.append({**fa, "reg": reg_monto, "dif": dif, "estado": estado})
    # Adiciones y bajas que no tienen factura de soporte (solo se evalúa si se cargó alguna factura de ese tipo).
    cods_ad = {f["cod"] for f in fact_ad if f["cod"]}
    cods_ba = {f["cod"] for f in fact_ba if f["cod"]}
    ad_sin = [c for c in ad_por_cod if c and c not in cods_ad] if fact_ad else []
    ba_sin = [a["id"] for a in bajas if a["id"] not in cods_ba] if fact_ba else []

    aj = {"ajusteDep": sum(a["dif"] for a in activos if a["dif"] is not None),
          "deterioroAdicional": sum(a["perdida"] for a in deter if a["perdida"] is not None),
          "deterioroORI": sum(a["detORI"] for a in deter if a["detORI"] is not None),
          "deterioroResultado": sum(a["detRes"] for a in deter if a["detRes"] is not None),
          "ajusteBajas": sum(a["res_dif"] for a in bajas if a["res_dif"] is not None),
          "ajusteIntereses": (sum(a["dif"] for a in capit if a["dif"] is not None) if prestamos
                             else sum(x["int_dif"] for x in adiciones if x["int_dif"] is not None)),
          "revaluacionORI": sum(a["rev_ori"] for a in reval), "revaluacionResultado": sum(a["rev_res"] for a in reval),
          "ajusteDesmantelamiento": desm["cambio"], "desmantelamientoFinanciero": desm["actualizacion"]}
    aj["ajusteResultado"] = (-aj["ajusteDep"] - aj["deterioroResultado"] + aj["ajusteBajas"] + aj["ajusteIntereses"]
                             + aj["revaluacionResultado"] - (desm["actualizacion"] or 0))

    # Problemas.
    pr = []
    for a in activos:
        if a["dep"] is None:
            pr.append(problema("METODO_NO_RECALCULADO", f"{a['id']}: la herramienta no recalcula el método «{a['metodo']}»; el recálculo se apoya en el cálculo del cliente y en el patrón de consumo (NIC 16.60–62).", 0))
        if a["dif"] is not None and abs(a["dif"]) > tol:
            pr.append(problema("DEPRECIACION_DIFERENTE", f"{a['id']}: depreciación recalculada {m(a['dep'])} ≠ registrada {m(a['dreg'])} (NIC 16.50; PYMES 17.18).", a["dif"]))
        if a["estado"] == "En construcción" and (a["dreg"] or 0) > 0:
            pr.append(problema("DEPRECIACION_EN_CONSTRUCCION", f"{a['id']}: se registró depreciación de un activo que aún no está disponible para su uso (NIC 16.55; PYMES 17.20).", a["dreg"]))
        if a["total_dep"] == "Sí" and a["estado"] == "En uso":
            pr.append(problema("TOTALMENTE_DEPRECIADO_EN_USO", f"{a['id']}: totalmente depreciado y aún en uso; revise la vida útil y el residual (NIC 16.51; PYMES 17.19).", a["costo"]))
        if (a["res"] or 0) > a["costo"]:
            pr.append(problema("RESIDUAL_EXCEDE_COSTO", f"{a['id']}: el valor residual iguala o supera el importe en libros: la depreciación es nula (NIC 16.54); verifique el soporte de la estimación (NIC 16.51; NIA 540).", (a["res"] or 0) - a["costo"]))
    # Vida útil NIIF por clase pendiente de confirmar: activos en uso, método lineal, sin vida (ni propia ni por
    # clase) y que no son terrenos. El recálculo de su depreciación espera hasta que el auditor confirme la vida.
    pendientes = {}
    for a in vivos:
        if a["vida"] is None and _lineal(a["metodo"]) and a["uso"] is not None and not _es_terreno(a["clase"]):
            pendientes.setdefault(a["clase"] or "(sin clase)", []).append(a["id"])
    for clase_p, ids in sorted(pendientes.items()):
        pr.append(problema("VIDA_UTIL_CLASE_PENDIENTE",
                           f"Clase «{clase_p}»: {len(ids)} activo(s) sin vida útil NIIF definida; su depreciación no se recalcula mientras la "
                           f"clase no tenga vida útil en los parámetros de la prueba (NIC 16.50, 57; PYMES 17.18, 17.21).", 0))
    umbral_rev = _p(p, "umbralRevisarComponentes")
    if umbral_rev is not None:
        for a in vivos:
            if conteo[grupo(a)] == 1 and a["costo"] >= umbral_rev and a["vida"] is not None:
                pr.append(problema("REVISAR_COMPONENTES", f"{a['id']}: elemento de costo {m(a['costo'])} sin partes registradas; puede tener partes significativas con vida distinta (NIC 16.43–44; PYMES 17.16).", 0))
    for a in bajas:
        if a["res_dif"] is not None and abs(a["res_dif"]) > tol:
            pr.append(problema("BAJA_MAL_CALCULADA", f"{a['id']}: resultado de la baja recalculado {m(a['res_calc'])} ≠ registrado {m(a['resreg'])} (NIC 16.71; PYMES 17.30).", a["res_dif"]))
        elif a["res_calc"] is not None and a["resreg"] is None:
            pr.append(problema("BAJA_SIN_RESULTADO", f"{a['id']}: baja sin ganancia o pérdida registrada; la recalculada es {m(a['res_calc'])}.", a["res_calc"]))
    clases_rev = {a["clase"] for a in vivos if a["rev"] is not None}
    for c in sorted(clases_rev):
        faltan = [a["id"] for a in vivos if a["clase"] == c and a["rev"] is None]
        if faltan:
            pr.append(problema("REVALUACION_CLASE_INCOMPLETA", f"Clase {c}: se revaluó una parte; también deben revaluarse {', '.join(faltan)} (NIC 16.36; PYMES 17.15 y 17.15B).", 0))
    for a in deter:
        if a["perdida"]:
            reparto = ("" if a["detORI"] in (None, 0) else
                       f" Activo revaluado: {m(a['detORI'])} contra el superávit de revaluación y {m(a['detRes'])} a resultados (NIC 36.60-61; PYMES 27.6).")
            pr.append(problema("DETERIORO", f"{a['id']}: importe en libros {m(a['libros'])} mayor que el importe recuperable {m(a['rec'])} (NIC 36.59; PYMES 27.5).{reparto}", a["perdida"]))
    sin_sup = [a["id"] for a in deter if a["perdida"] and a["detORI"] is None]
    if sin_sup:
        pr.append(problema("DETERIORO_SIN_SUPERAVIT", f"Activos revaluados con deterioro y sin superávit de revaluación previo informado: {', '.join(sin_sup)}. "
                           "La pérdida se imputa primero contra el superávit de ese activo y solo el exceso a resultados (NIC 36.60-61; PYMES 27.6). "
                           "Sin el dato del superávit previo, la pérdida queda íntegra en resultados.",
                           sum(a["perdida"] for a in deter if a["perdida"] and a["detORI"] is None)))
    sin_dec = [a["id"] for a in reval if a["decPrev"] is None]
    if sin_dec:
        pr.append(problema("REVALUACION_SIN_DECREMENTO_PREVIO", f"Activos revaluados sin el dato «decremento previo del mismo activo reconocido en resultados»: "
                           f"{', '.join(sin_dec)}. El aumento por revaluación va a resultados hasta revertir ese decremento anterior (NIC 16.39; PYMES 17.15C). "
                           "Sin ese dato, el aumento queda íntegro en otro resultado integral.",
                           sum(a["rev_ori"] for a in reval if a["decPrev"] is None and a["rev_dif"] > 0)))
    if pymes:
        cap_pymes = sum(x["int"] or 0 for x in adiciones)
        if cap_pymes > 0.005:
            pr.append(problema("INTERESES_CAPITALIZADOS_PYMES", f"En NIIF para las PYMES los costos por préstamos son gasto (Sección 25.2): se capitalizaron {m(cap_pymes)}.", -cap_pymes))
        if prestamos:
            pr.append(problema("PRESTAMOS_NO_SE_CAPITALIZAN_PYMES", "Se cargó el anexo de préstamos para la construcción, pero en NIIF para las PYMES todos los costos por "
                               "préstamos se reconocen como gasto del período (Sección 25.2, igual en las ediciones 2015 y 2025): no hay tasa de capitalización ni "
                               "préstamo específico que capitalizar. El anexo sirve para identificar el costo financiero del período y su presentación en resultados."))
    else:
        if not prestamos:
            if tasa_cap is None and any(x["apto"].lower() in ("sí", "si") for x in adiciones):
                pr.append(problema("TASA_CAPITALIZACION_FALTANTE", "Hay adiciones de activos aptos y no consta la tasa de capitalización (NIC 23.14): sus costos por préstamos no se recalculan.", 0))
            if any(a["estado"] == "En construcción" for a in activos) or any(x["apto"].lower() in ("sí", "si") for x in adiciones):
                pr.append(problema("SIN_ANEXO_PRESTAMOS", "Hay activos en construcción o adiciones de activos aptos y no se cargó el anexo de préstamos para la "
                                   "construcción: no se puede separar el préstamo específico —costo financiero realmente incurrido menos los rendimientos de la inversión "
                                   "temporal de esos fondos (NIC 23.12)— de los préstamos generales —tasa de capitalización (NIC 23.14)— ni comprobar el tope de los "
                                   "costos por préstamos incurridos en el período (NIC 23.14). Sin ese anexo se aplica la tasa de capitalización del parámetro a cada desembolso.", 0))
            for x in adiciones:
                if x["int_dif"] is not None and abs(x["int_dif"]) > tol:
                    pr.append(problema("INTERESES_DIFERENCIA", f"{x['id']}: intereses capitalizables {m(x['cap'])} ≠ capitalizados {m(x['int'] or 0)} (NIC 23.8, 14).", x["int_dif"]))
        else:
            if tasa_cap is not None and tasa_gen is not None and abs(tasa_gen * 100 - tasa_cap) > 0.005:
                pr.append(problema("TASA_CAPITALIZACION_DIFIERE", f"La tasa de capitalización del parámetro ({tasa_cap:.4f} %) no coincide con la media ponderada de los "
                                   f"préstamos generales del anexo ({tasa_gen * 100:.4f} %): se usa la del anexo (NIC 23.14).", 0))
            if factor is None:
                pr.append(problema("TOPE_NO_VERIFICABLE", "No se puede comprobar el tope del párrafo 14 (lo capitalizado no excede los costos por préstamos incurridos en "
                                   "el período): no consta el costo financiero de algún préstamo o el capitalizable de algún activo en el anexo de préstamos.", 0))
            elif factor < 1:
                pr.append(problema("TOPE_COSTOS_PRESTAMOS", f"El capitalizable calculado {m(tope_antes)} excede los costos por préstamos incurridos en el período "
                                   f"{m(tope_inc)}: se limita a estos últimos (NIC 23.14). Exceso que no se capitaliza: {m(tope_antes - tope_inc)}.", tope_antes - tope_inc))
            for a in capit:
                if a["dif"] is not None and abs(a["dif"]) > tol:
                    pr.append(problema("INTERESES_DIFERENCIA", f"{a['activo']}: costos por préstamos capitalizables {m(a['final'])} ≠ capitalizados {m(a['reg'])} "
                                       "(NIC 23.12 el específico, 23.14 los generales y el tope).", a["dif"]))
    for y in prestamos:
        if not y["tipo"]:
            pr.append(problema("PRESTAMO_SIN_TIPO", f"{y['id']}: sin tipo declarado (específico NIC 23.12 / general NIC 23.14); sin el tipo no entra en el cálculo.", 0))
        if y["costo"] is None:
            pr.append(problema("PRESTAMO_SIN_COSTO_FINANCIERO", f"{y['id']}: sin costo financiero del período realmente incurrido; sin él no se mide el capitalizable "
                               "ni el tope del párrafo 14 (NIC 23.12 y 14).", 0))
        if y["tipo"] == "Específico":
            if y["rend"] is None:
                pr.append(problema("PRESTAMO_SIN_RENDIMIENTOS", f"{y['id']}: préstamo específico sin el dato de rendimientos de la inversión temporal de esos fondos; lo "
                                   "capitalizable es el costo realmente incurrido menos esos rendimientos (NIC 23.12). Un rendimiento no informado no se asume en cero.", 0))
            if not y["activo"]:
                pr.append(problema("PRESTAMO_SIN_ACTIVO", f"{y['id']}: préstamo específico sin el activo u obra financiada declarada; su costo capitalizable no se asigna (NIC 23.12).", 0))
            elif y["activo"] not in por_id:
                pr.append(problema("PRESTAMO_ACTIVO_NO_EXISTE", f"{y['id']}: el activo {y['activo']} que financia no está en el auxiliar.", 0))
        if y["tipo"] == "General" and (y["importe"] is None or y["costo"] is None):
            pr.append(problema("PRESTAMO_GENERAL_INCOMPLETO", f"{y['id']}: préstamo general sin importe o sin costo financiero del período; sin ambos no se calcula la tasa "
                               "de capitalización, que es la media ponderada de los costos de todos los préstamos genéricos (NIC 23.14).", 0))
    for x in adiciones:
        if x["capitalizable"] != "Sí":
            pr.append(problema("ADICION_GASTO_CAPITALIZADO", f"{x['id']}: «{x['tipo']}» capitalizado; las reparaciones y el mantenimiento son gasto (NIC 16.12; PYMES 17.15); el mantenimiento mayor o las inspecciones generales pueden capitalizarse (NIC 16.13–14).", x["importe"]))
        if not x["existe"]:
            pr.append(problema("ADICION_SIN_ACTIVO", f"{x['id']}: el activo {x['activo']} no está en el auxiliar.", x["importe"]))
    if rf["difAd"] is not None and abs(rf["difAd"]) > tol:
        pr.append(problema("ADICIONES_NO_CONCILIAN", f"Adiciones del auxiliar {m(rf['ad'])} ≠ detalle de adiciones {m(rf['adDetalle'])}.", rf["difAd"]))
    if vp is None:
        pr.append(problema("DESMANTELAMIENTO_NO_EVALUADO", "No consta estimación de desmantelamiento: la existencia de la obligación no está evaluada (NIC 16.16 c, NIC 37; PYMES 17.10 c, Sección 21).", 0))
    elif vp > 0.005 and not prov_reg:
        pr.append(problema("DESMANTELAMIENTO_NO_RECONOCIDO", f"Obligación de desmantelamiento no reconocida: valor presente {m(vp)} (NIC 16.16 c, NIC 37.45; Sección 21 (21.7 b)).", vp))
    elif abs(desm["dif"]) > tol:
        pr.append(problema("DESMANTELAMIENTO_DIFERENCIA", f"Provisión de desmantelamiento registrada {m(prov_reg)} ≠ valor presente {m(vp)}: diferencia {m(desm['dif'])}"
                           + ("." if act is None else f", de la que {m(act)} es la actualización financiera del período (a resultados, costo financiero: CINIIF 1.8; "
                              f"NIC 37.60; PYMES 21.11) y {m(desm['cambio'])} el cambio de estimación contra el costo del activo (CINIIF 1.5 a)."), desm["dif"]))
    if vp is not None and prov_ini is None:
        pr.append(problema("SIN_PROVISION_DESMANTELAMIENTO_INICIAL", "Hay provisión de desmantelamiento registrada y no consta su saldo al inicio del "
                           "ejercicio: no se separa la actualización financiera del período (saldo inicial × tasa, a resultados: CINIIF 1.8; PYMES 21.11) "
                           "del cambio de estimación (contra el costo del activo: CINIIF 1.5 a)."))
    for k, lab in (("difCosto", "del costo"), ("difDep", "de la depreciación acumulada")):
        mk = "mayorCosto" if k == "difCosto" else "mayorDep"
        if rf[mk] is None:
            pr.append(problema("SIN_MAYOR", f"No consta el saldo {lab} según el mayor: la conciliación con el auxiliar queda sin cotejar.", 0))
        elif abs(rf[k]) > tol:
            pr.append(problema("CONCILIACION_AUXILIAR_MAYOR", f"Auxiliar y mayor no concilian en el saldo {lab}: diferencia {m(rf[k])}.", rf[k]))

    # Conciliación del auxiliar con el balance (sumaria de variaciones).
    for k, lab in (("dif_costo", "del costo"), ("dif_dep", "de la depreciación acumulada")):
        if concil[k] is not None and abs(concil[k]) > tol:
            pr.append(problema("SUMARIA_NO_CONCILIA", f"Auxiliar y balance (sumaria) no concilian en el saldo {lab}: diferencia {m(concil[k])}.", concil[k]))

    # Vaucheo de facturas: diferencias de monto, facturas sin registro y altas/bajas sin soporte.
    for v in vaucheo:
        etq = f"{v['tipo']} {v['cod'] or v['num'] or v['prov'] or ''}".strip()
        if v["estado"] == "Diferencia":
            pr.append(problema("VAUCHEO_DIFERENCIA", f"{etq}: la factura ({m(v['total'])}) difiere de lo registrado ({m(v['reg'])}): {m(v['dif'])}.", v["dif"]))
        elif v["estado"] == "Sin registro en libros":
            pr.append(problema("FACTURA_SIN_REGISTRO", f"{etq}: la factura {v['num'] or ''} no cruza con ninguna {v['tipo'].lower()} registrada.", v["total"] or 0))
    for c in ad_sin:
        pr.append(problema("ADICION_SIN_FACTURA", f"La adición del activo {c} no tiene factura de soporte cargada.", ad_por_cod.get(c) or 0))
    for c in ba_sin:
        pr.append(problema("BAJA_SIN_FACTURA", f"La baja del activo {c} no tiene factura de venta de soporte cargada.", ba_por_cod.get(c) or 0))

    for a in activos:
        if (a.get("exceso_veh") or 0) > tol:
            pr.append(problema("VEHICULO_TOPE_FISCAL", f"{a['id']}: el costo {m(a['costo'])} supera USD {int(TOPE_VEHICULO):,}; la "
                               f"depreciación sobre el exceso no es deducible (diferencia permanente): {m(a['exceso_veh'])} (LRTI Art. 10 núm. 7).", a["exceso_veh"]))

    totales, etiquetas = {}, {}
    for k, lab, v in (
        ("costoFinal", "Costo al cierre (auxiliar)", rf["costoFinal"]),
        ("depRecalculada", "Depreciación del año recalculada", sum(a["dep"] for a in activos if a["dep"] is not None)),
        ("depRegistrada", "Depreciación del año registrada", rf["dreg"]),
        ("ajusteDep", "Diferencia de depreciación (recalculada − registrada)", aj["ajusteDep"]),
        ("nbv", "Valor neto en libros recalculado (activos medidos)", rf["nbv"]),
        ("deterioroAdicional", "Pérdida por deterioro adicional", aj["deterioroAdicional"]),
        ("deterioroORI", "Deterioro contra el superávit de revaluación (ORI)", aj["deterioroORI"]),
        ("deterioroResultado", "Deterioro a resultados", aj["deterioroResultado"]),
        ("ajusteBajas", "Diferencia en resultado de bajas", aj["ajusteBajas"]),
        # M22: si algún activo quedó sin medir, el total no se presenta (no es cero, es desconocido).
        ("capitalizableEspecificos", "Capitalizable de préstamos específicos (NIC 23.12)", _tot(capit, "esp_cap") if prestamos else None),
        ("capitalizableGenerales", "Capitalizable de préstamos generales (NIC 23.14)", _tot(capit, "cap_gen") if prestamos else None),
        ("costosPrestamosIncurridos", "Costos por préstamos incurridos en el período (tope NIC 23.14)",
         tope_inc if prestamos and all(y["costo"] is not None for y in prestamos) else None),
        ("capitalizablePeriodo", "Costos por préstamos capitalizables del período (después del tope)",
         _tot(capit, "final") if prestamos else None),
        ("ajusteIntereses", "Ajuste de intereses capitalizados", aj["ajusteIntereses"]),
        ("revaluacionORI", "Revaluación a otro resultado integral", aj["revaluacionORI"]),
        ("revaluacionResultado", "Revaluación a resultados", aj["revaluacionResultado"]),
        ("provDesmantelamiento", "Provisión de desmantelamiento (valor presente)", vp),
        ("ajusteDesmantelamiento", "Desmantelamiento: cambio de estimación (contra el costo del activo)", desm["cambio"]),
        ("desmantelamientoFinanciero", "Desmantelamiento: actualización financiera del período (costo financiero)", desm["actualizacion"]),
        ("difCosto", "Diferencia auxiliar − mayor (costo)", rf["difCosto"]),
        ("difDepAcum", "Diferencia auxiliar − mayor (depreciación acumulada)", rf["difDep"]),
        ("ajusteResultado", "Efecto neto de los ajustes en resultados", aj["ajusteResultado"]),
    ):
        if v is not None:
            totales[k], etiquetas[k] = r2(v), lab

    iso = lambda d: d.isoformat() if d else ""
    filas = [{"id": a["id"], "descripcion": a["desc"], "clase": a["clase"], "estado": a["estado"], "costo": r2(a["costo"]),
              "depRecalculada": "" if a["dep"] is None else r2(a["dep"]), "depRegistrada": "" if a["dreg"] is None else r2(a["dreg"]),
              "diferencia": "" if a["dif"] is None else r2(a["dif"]), "nbv": "" if a["nbv"] is None else r2(a["nbv"]),
              "_row": a["_row"]} for a in activos]
    limpia = lambda it: [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in x.items()} for x in it]
    detalle = {"cortes": {"actual": corte_a.isoformat(), "inicio": inicio.isoformat()}, "diasAnio": dias_anio,
               "marco": MARCO_PYMES if pymes else MARCO_COMPLETAS, "edicion": edicion_pymes(p) if pymes else "",
               "activos": limpia(activos), "adiciones": limpia(adiciones), "prestamos": limpia(prestamos),
               "capitalizacion": limpia(capit), "tope": {"incurridos": tope_inc, "antes": tope_antes, "factor": factor},
               "desmantelamiento": desm, "rollforward": rf, "ajustes": aj, "parametros": p,
               "variaciones": variaciones, "mayor": mayor, "conciliacion": concil,
               "vaucheo": vaucheo, "vaucheoAdSin": ad_sin, "vaucheoBaSin": ba_sin}
    return {"engine": VERSION, "rows": filas, "totals": totales, "labels": etiquetas, "primary": "ajusteResultado",
            "exceptions": pr, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Auxiliar", "Auxiliar de activos (datos del cliente)"),
    ("04_Depreciacion", "Recálculo de depreciación y VNL"), ("05_Vidas_residual", "Vidas útiles, residual y método"),
    ("06_Componentes", "Componentes"), ("07_Bajas", "Bajas"), ("08_Revaluacion", "Revaluación"), ("09_Deterioro", "Deterioro"),
    ("10_Adiciones", "Adiciones y costos por préstamos"), ("11_Prestamos", "Préstamos para la construcción"),
    ("12_Capitalizacion", "Capitalización de costos por préstamos por activo"), ("13_Desmantelamiento", "Desmantelamiento"),
    ("14_Roll_forward", "Movimiento del año y conciliación auxiliar-mayor"), ("15_Ajustes", "Ajustes propuestos"),
    ("16_Problemas", "Problemas encontrados"), ("17_Conclusion", "Indicadores y conclusión"),
    ("18_Lectura", "Lectura de resultados"), ("19_Resumen_estado", "Resumen por estado del activo"),
    ("20_Fiscal", "Recálculo fiscal (SRI Art. 28) y conciliación NIIF"),
    ("21_Comparativo", "Recálculo comparativo por días (auditor vs cliente)"),
    ("22_Guia_NIIF_SRI", "Guía comparativa NIIF vs SRI"),
    ("23_Sumaria", "Sumaria de cuentas (variaciones del balance)"),
    ("24_Movimiento_mayor", "Movimiento del período (libro mayor)"),
    ("25_Conciliacion", "Conciliación de saldos (auxiliar vs balance)"),
    ("26_Vaucheo", "Vaucheo de facturas (adiciones y bajas)"),
    ("27_Resumen_hallazgos", "Resumen de hallazgos por categoría"),
]


def _categoria_hallazgo(code: str) -> str:
    c = (code or "").upper()
    if "VAUCHEO" in c or "FACTURA" in c:
        return "Vaucheo de facturas"
    if "CONCILIA" in c or "MAYOR" in c or "SUMARIA" in c:
        return "Conciliación de saldos"
    if "DEPRECIA" in c or "VIDA" in c or "VEHICULO" in c:
        return "Depreciación y vidas útiles"
    if "REVALU" in c or "DETERIORO" in c:
        return "Revaluación y deterioro"
    if "PRESTAMO" in c or "INTERES" in c or "TOPE" in c or "DESMANTEL" in c:
        return "Costos por préstamos y desmantelamiento"
    if "BAJA" in c:
        return "Bajas"
    if "ADICION" in c:
        return "Adiciones"
    return "Otros"
P = ref("02_Parametros")
FIS = ref("20_Fiscal")
AUX, DEP, BAJ, REV, DET, ADI, PRE, CAP, DES, RF, AJ = (
    ref(n) for n in ("03_Auxiliar", "04_Depreciacion", "07_Bajas", "08_Revaluacion", "09_Deterioro", "10_Adiciones",
                     "11_Prestamos", "12_Capitalizacion", "13_Desmantelamiento", "14_Roll_forward", "15_Ajustes"))
_PAR = ["corte", "inicio", "diasAnio", "marco", "edicion", "tolerancia", "tasaCapitalizacion", "umbralComponente",
        "umbralRevisarComponentes", "costoDesmantelamiento", "aniosDesmantelamiento", "tasaDesmantelamiento",
        "provisionDesmantelamiento", "provisionDesmantelamientoInicial", "mayorCosto", "mayorDepAcum",
        "vidaInmuebles", "vidaInstalacionesMaquinaria", "vidaMuebles", "vidaVehiculos", "vidaEquipoComputo"]
PAR = {k: f"{P}$B${FILA0 + i}" for i, k in enumerate(_PAR)}


def _rng(h: str, col: str, n: int) -> str:
    return f"{h}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _si(celda: str) -> str:
    """Celda opcional: vacía queda vacía (M22)."""
    return f'IF({celda}="","",{celda})'


def _hoja(hojas, nombre):
    return next((x for x in hojas if x["name"] == nombre), None)


def _celda_fila(hoja, columna, es_fila):
    """Celda de «columna» en la fila que cumple ``es_fila(texto de la primera columna, descripción)``.
    Si varias filas cumplen, prefiere la que tiene el importe del problema."""
    def ref(hojas, e):
        h = _hoja(hojas, hoja)
        if not h:
            return None
        msg, imp = e.get("message") or "", problemas._num(e.get("amount"))
        j = [c[0] for c in h["cols"]].index(columna)
        hallados = [(i, f) for i, f in enumerate(h.get("rows") or []) if es_fila(problemas._texto(f[0]), msg)]
        for i, f in hallados:
            v = problemas._num(f[j])
            if imp is None or (v is not None and abs(abs(v) - abs(imp)) < problemas.TOL):
                return problemas.celda(hojas, hoja, columna, i), f[j]
        return (problemas.celda(hojas, hoja, columna, hallados[0][0]), hallados[0][1][j]) if hallados else None
    return ref


def _codigo(hoja, columna):
    """Fila del activo, adición o préstamo con cuyo código abre la descripción («CÓDIGO: …»)."""
    return _celda_fila(hoja, columna, lambda t, msg: bool(t) and msg.startswith(t + ":"))


def _concepto(hoja, inicio, columna="Importe"):
    """Fila de la cédula cuyo «Concepto» empieza por ``inicio``."""
    return _celda_fila(hoja, columna, lambda t, msg: t.startswith(inicio))


def _suma_listados(hoja, columna, antes, despues, filtro=None):
    """Suma la «columna» de los activos que la descripción lista entre ``antes`` y ``despues``."""
    def ref(hojas, e):
        h = _hoja(hojas, hoja)
        msg = e.get("message") or ""
        if not h or antes not in msg:
            return None
        ids = {x.strip() for x in msg.split(antes, 1)[1].split(despues, 1)[0].split(",")}
        cols = [c[0] for c in h["cols"]]
        j = cols.index(columna)
        idx = [i for i, f in enumerate(h.get("rows") or [])
               if problemas._texto(f[0]) in ids and (filtro is None or filtro(cols, f))]
        if not idx:
            return None
        formula = "+".join(problemas.celda(hojas, hoja, columna, i) for i in idx)
        return formula, sum(problemas._num(h["rows"][i][j]) or 0 for i in idx)
    return ref


def _residual_excede(hojas, e):
    """Valor residual − costo del activo (05)."""
    h = _hoja(hojas, "05_Vidas_residual")
    msg = e.get("message") or ""
    for i, f in enumerate(h["rows"] if h else []):
        t = problemas._texto(f[0])
        if t and msg.startswith(t + ":"):
            return (f"{problemas.celda(hojas, h['name'], 'Valor residual', i)}-{problemas.celda(hojas, h['name'], 'Costo', i)}",
                    (problemas._num(f[4]) or 0) - (problemas._num(f[5]) or 0))
    return None


def _intereses_diferencia(hojas, e):
    """Capitalizable − capitalizado: por activo (12) si hay anexo de préstamos; por adición (10) si no."""
    if "costos por préstamos capitalizables" in (e.get("message") or ""):
        return _codigo("12_Capitalizacion", "Diferencia")(hojas, e)
    return _codigo("10_Adiciones", "Diferencia")(hojas, e)


def _exceso_tope(hojas, e):
    """Capitalizable antes del tope (TOTAL de 12) − costos por préstamos incurridos (TOTAL de 11)."""
    cap, pre = _hoja(hojas, "12_Capitalizacion"), _hoja(hojas, "11_Prestamos")
    if not cap or not pre or not cap.get("total") or not pre.get("total"):
        return None
    ja = [c[0] for c in cap["cols"]].index("Capitalizable antes del tope")
    jc = [c[0] for c in pre["cols"]].index("Costo financiero del período")
    formula = (f"{problemas.celda(hojas, cap['name'], 'Capitalizable antes del tope', len(cap['rows']))}"
               f"-{problemas.celda(hojas, pre['name'], 'Costo financiero del período', len(pre['rows']))}")
    return formula, (problemas._num(cap["total"][ja]) or 0) - (problemas._num(pre["total"][jc]) or 0)


def _conciliacion_mayor(hojas, e):
    """Diferencia auxiliar − mayor del saldo que nombra la descripción (costo o depreciación acumulada), hoja 14."""
    cual = "(costo)" if "saldo del costo" in (e.get("message") or "") else "(depreciación)"
    return _concepto("14_Roll_forward", f"Diferencia auxiliar − mayor {cual}")(hojas, e)


def _conciliacion_balance(hojas, e):
    """Diferencia auxiliar − balance del saldo que nombra la descripción (costo o depreciación), hoja 25."""
    cual = "Costo" if "del costo" in (e.get("message") or "") else "Depreciación acumulada"
    return _concepto("25_Conciliacion", cual, "Diferencia")(hojas, e)


# De qué celda sale el importe de cada problema (ver procesadores/problemas.py).
REF_PROBLEMAS = {
    "DEPRECIACION_DIFERENTE": _codigo("04_Depreciacion", "Diferencia"),                 # depreciación recalculada − registrada
    "DEPRECIACION_EN_CONSTRUCCION": _codigo("04_Depreciacion", "Depreciación registrada"),  # depreciación registrada de la obra
    "TOTALMENTE_DEPRECIADO_EN_USO": _codigo("05_Vidas_residual", "Costo"),             # costo del activo depreciado en uso
    "VEHICULO_TOPE_FISCAL": _codigo("20_Fiscal", "Exceso vehículo no deducible"),      # depreciación sobre el exceso del tope (SRI)
    "RESIDUAL_EXCEDE_COSTO": _residual_excede,                                         # valor residual − costo
    "BAJA_MAL_CALCULADA": _codigo("07_Bajas", "Diferencia"),                           # resultado recalculado − registrado
    "BAJA_SIN_RESULTADO": _codigo("07_Bajas", "Resultado recalculado"),                # resultado de baja no registrado
    "DETERIORO": _codigo("09_Deterioro", "Pérdida adicional"),                         # importe en libros − recuperable
    "DETERIORO_SIN_SUPERAVIT": _suma_listados(                                         # pérdida de los revaluados sin superávit previo
        "09_Deterioro", "Pérdida adicional", "previo informado: ", ". La pérdida"),
    "REVALUACION_SIN_DECREMENTO_PREVIO": _suma_listados(                               # aumento enviado íntegro al ORI
        "08_Revaluacion", "A otro resultado integral", "en resultados»: ", ". El aumento",
        lambda cols, f: (problemas._num(f[cols.index("Diferencia")]) or 0) > 0),
    "INTERESES_CAPITALIZADOS_PYMES": ("10_Adiciones", "Intereses capitalizados", "total"),  # intereses capitalizados (−, PYMES: gasto)
    "TOPE_COSTOS_PRESTAMOS": _exceso_tope,                                             # capitalizable − costos incurridos (NIC 23.14)
    "INTERESES_DIFERENCIA": _intereses_diferencia,                                     # capitalizable − capitalizado
    "ADICION_GASTO_CAPITALIZADO": _codigo("10_Adiciones", "Importe"),                  # reparación capitalizada
    "ADICION_SIN_ACTIVO": _codigo("10_Adiciones", "Importe"),                          # adición de un activo que no está en el auxiliar
    "ADICIONES_NO_CONCILIAN": _concepto("14_Roll_forward", "Diferencia adiciones auxiliar − detalle"),  # auxiliar − detalle
    "DESMANTELAMIENTO_NO_RECONOCIDO": _concepto("13_Desmantelamiento", "Valor presente"),  # valor presente no provisionado
    "DESMANTELAMIENTO_DIFERENCIA": _concepto("13_Desmantelamiento", "Ajuste total"),   # valor presente − registrada al cierre
    "CONCILIACION_AUXILIAR_MAYOR": _conciliacion_mayor,                                # auxiliar − mayor (costo o depreciación)
    "SUMARIA_NO_CONCILIA": _conciliacion_balance,                                      # auxiliar − balance (costo o depreciación)
}


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p = d["parametros"]
    A = d["activos"]
    AD = d["adiciones"]
    PRS, CP = d["prestamos"], d["capitalizacion"]
    rf, aj, ds = d["rollforward"], d["ajustes"], d["desmantelamiento"]
    n, nad, npr, ncap = len(A), len(AD), len(PRS), len(CP)
    fila = {a["id"]: FILA0 + i for i, a in enumerate(A)}
    pv = lambda k: None if p.get(k) in (None, "") else float(a_num(p.get(k)))

    parametros = [
        ["Corte del ejercicio", d["cortes"]["actual"], "Ficha del encargo"],
        ["Inicio del ejercicio", d["cortes"]["inicio"], "Un año antes del corte + 1 día"],
        ["Días del ejercicio", fx(f"B{FILA0}-B{FILA0 + 1}+1", d["diasAnio"]), "Base de la fracción de tiempo"],
        ["Marco contable", d["marco"], "PYMES: costos por préstamos a gasto (Sección 25.2)" if d["marco"] == MARCO_PYMES else "NIC 23: capitaliza en activos aptos"],
        ["Edición PYMES", d["edicion"], "2015 y 2025: mismo tratamiento (resumen oficial de cambios 2025: Secc. 25 editorial; Secc. 27 consecuencial; "
                                      "Secc. 17 sin cambios en revaluación, componentes ni bajas); la 3.ª edición rige desde el 1-1-2027"],
        ["Tolerancia por activo (importe)", pv("tolerancia"), "Juicio del auditor (materialidad de ejecución)"],
        ["Tasa de capitalización (% anual)", pv("tasaCapitalizacion"), "NIC 23.14: media ponderada de los préstamos genéricos"],
        ["Parte significativa desde (% del elemento)", pv("umbralComponente"), "NIC 16.43; juicio del auditor"],
        ["Revisar componentes desde (costo)", pv("umbralRevisarComponentes"), "NIC 16.44; en blanco: no se revisa"],
        ["Desmantelamiento: costo estimado futuro", pv("costoDesmantelamiento"), "NIC 16.16 c; PYMES 17.10 c"],
        ["Desmantelamiento: años hasta el desembolso", pv("aniosDesmantelamiento"), "Estimación técnica"],
        ["Desmantelamiento: tasa antes de impuestos (%)", pv("tasaDesmantelamiento"), "NIC 37.47"],
        ["Provisión de desmantelamiento registrada (cierre)", pv("provisionDesmantelamiento"), "Mayor contable"],
        ["Provisión de desmantelamiento registrada al inicio", pv("provisionDesmantelamientoInicial"),
         "Mayor contable: base de la actualización financiera del período (CINIIF 1.8; NIC 37.60; PYMES 21.11). En blanco y sin provisión al cierre: 0"],
        ["Mayor: costo al cierre", pv("mayorCosto"), "Mayor contable"],
        ["Mayor: depreciación acumulada al cierre", pv("mayorDepAcum"), "Mayor contable"],
        ["Vida útil NIIF (años) · Inmuebles y construcciones", pv("vidaInmuebles"), "Confirmada por el auditor; se aplica a los activos de la clase sin vida propia"],
        ["Vida útil NIIF (años) · Instalaciones, maquinaria y equipos", pv("vidaInstalacionesMaquinaria"), "Confirmada por el auditor"],
        ["Vida útil NIIF (años) · Muebles y enseres", pv("vidaMuebles"), "Confirmada por el auditor"],
        ["Vida útil NIIF (años) · Vehículos y equipo de transporte", pv("vidaVehiculos"), "Confirmada por el auditor"],
        ["Vida útil NIIF (años) · Equipos de cómputo y software", pv("vidaEquipoComputo"), "Confirmada por el auditor"],
    ]

    # 03 · auxiliar tal como lo entregó el cliente.
    aux = [[a["id"], a["desc"], a["clase"], a["elemento"], a["uso"] or None, a["ci"], a["ad"], a["res"], a["vida"], a["metodo"],
            a["dai"], a["dreg"], a["det"], a["rec"], a["rev"], a["sup"], a["decPrev"], a["baja"] or None, a["prod"], a["resreg"]] for a in A]

    # 04 · depreciación y VNL (fila alineada con 03).
    tol = pv("tolerancia") or 0.0
    dep = []
    for i, a in enumerate(A):
        r = FILA0 + i
        X = lambda c: f"{AUX}{c}{r}"
        dias = f'IF({X("E")}="",0,MAX(IF({X("R")}<>"",MIN({X("R")},{PAR["corte"]}),{PAR["corte"]})-MAX({X("E")},{PAR["inicio"]})+1,0))'
        dep.append([
            a["id"], fx(f'{X("F")}+{X("G")}', a["costo"]), fx(f'MAX(B{r}-{X("H")},0)', a["depr"]), fx(dias, a["dias"]),
            fx(f'IF(NOT(OR({X("J")}="",ISNUMBER(SEARCH("lineal",{X("J")})))),"",IF(OR({X("I")}="",D{r}=0),0,'
               f'MIN(C{r}/{X("I")}*12*D{r}/{PAR["diasAnio"]},MAX(C{r}-{X("K")},0))))', a["dep"]),
            fx(_si(X("L")), a["dreg"]), fx(f'IF(OR(E{r}="",F{r}=""),"",E{r}-F{r})', a["dif"]),
            fx(f'IF(E{r}="","",{X("K")}+E{r})', a["acum"]), fx(f'{X("M")}', a["det"] or 0.0),
            fx(f'IF(H{r}="","",B{r}-H{r}-I{r})', a["nbv"]),
            fx(f'IF(H{r}="","",IF(AND(C{r}>0,H{r}>=C{r}-0.005),"Sí","No"))', a["total_dep"]),
            fx(f'IF({X("R")}<>"","Baja",IF({X("E")}="","En construcción","En uso"))', a["estado"]),
            fx(f'IF(G{r}="","",IF(ABS(G{r})>{PAR["tolerancia"]},"Alerta","Conforme"))',
               "" if a["dif"] is None else ("Alerta" if abs(a["dif"]) > tol else "Conforme")),
            # N: dep. acumulada del cliente = apertura (aux K) + gasto del año del cliente (col F).
            fx(f'{X("K")}+IF(F{r}="",0,F{r})', (a["dai"] or 0) + (a["dreg"] or 0)),
            # O: diferencia de dep. acumulada = auditor (H) − cliente (N).
            fx(f'IF(H{r}="","",H{r}-N{r})', None if a["acum"] is None else a["acum"] - ((a["dai"] or 0) + (a["dreg"] or 0))),
        ])

    # 05 · vidas útiles, residual y método.
    vidas = []
    for i, a in enumerate(A):
        r = FILA0 + i
        vidas.append([a["id"], a["clase"], a["metodo"], fx(_si(f"{AUX}I{r}"), a["vida"]), fx(f"{AUX}H{r}", a["res"] or 0.0),
                      fx(f"{DEP}B{r}", a["costo"]), fx(f'IF(F{r}=0,"",E{r}/F{r})', a["resid_pct"]), fx(_si(f"{DEP}H{r}"), a["acum"]),
                      fx(f'IF(OR(D{r}="",H{r}="",{DEP}C{r}=0),"",MAX({DEP}C{r}-H{r},0)/{DEP}C{r}*D{r})', a["remanente"]),
                      fx(f'IF(AND({DEP}K{r}="Sí",{DEP}L{r}="En uso"),"Sí","No")', "Sí" if a["total_dep"] == "Sí" and a["estado"] == "En uso" else "No"),
                      fx(f'IF(E{r}>F{r},"Sí","No")', "Sí" if (a["res"] or 0) > a["costo"] else "No")])

    # 20 · recálculo fiscal (SRI Art. 28) y conciliación con la depreciación NIIF (cédula 04).
    fiscal = []
    for i, a in enumerate(A):
        r = FILA0 + i
        tasa = a.get("tasa_fiscal")
        veh = _clase_bucket(a["clase"]) == "vidaVehiculos"
        df = a.get("dif_fiscal")
        if tasa is None:
            obs = "Sin tasa fiscal (terreno o clase no mapeada)."
        elif df is None:
            obs = ""
        else:
            partes = []
            if (a.get("exceso_veh") or 0) > tol:
                partes.append(f"Exceso de vehículo no deducible (permanente): {m(a['exceso_veh'])}.")
            partes.append(f"NIIF mayor que fiscal: diferencia temporaria {m(df)}." if df > tol
                          else (f"Fiscal mayor que NIIF: {m(-df)}." if df < -tol else "Sin diferencia."))
            obs = " ".join(partes)
        base_form = f"MIN(C{r},{TOPE_VEHICULO})" if veh else f"C{r}"
        fiscal.append([
            a["id"], a["clase"], fx(f"{DEP}B{r}", a["costo"]),
            fx("" if tasa is None else str(tasa), "" if tasa is None else tasa),
            fx("" if a.get("base_fiscal") is None else base_form, "" if a.get("base_fiscal") is None else a["base_fiscal"]),
            fx("" if a.get("dep_fiscal") is None else f"E{r}*D{r}*{DEP}D{r}/{PAR['diasAnio']}",
               "" if a.get("dep_fiscal") is None else a["dep_fiscal"]),
            fx(f"{DEP}E{r}", a["dep"]),
            fx(f'IF(OR(F{r}="",G{r}=""),"",G{r}-F{r})', df),
            fx(f'MAX(({DEP}B{r}-{TOPE_VEHICULO})*D{r}*{DEP}D{r}/{PAR["diasAnio"]},0)' if veh else "0", a.get("exceso_veh") or 0.0),
            obs,
        ])
    ex_fiscal = {
        "Costo": "Costo del activo, traído de la columna «Costo» de la hoja 04 (Recálculo de depreciación); es la base sobre la que "
                 "se aplica el límite y la tasa fiscal para el recálculo tributario.",
        "Tasa fiscal máx. (SRI)": "Porcentaje máximo anual de depreciación deducible por clase (RALRTI Art. 28 núm. 6): inmuebles 5 %, "
                                  "instalaciones, maquinaria, equipos y muebles 10 %, vehículos 20 %, cómputo y software 33 %; terrenos no se deprecian.",
        "Base deducible": f"Costo del activo; en vehículos, limitada a USD {int(TOPE_VEHICULO):,} (LRTI Art. 10 núm. 7).",
        "Dep. fiscal del año": "Base deducible × tasa máxima × días en uso ÷ días del ejercicio.",
        "Dep. NIIF del año": "Depreciación del año recalculada por el auditor con la vida útil NIIF (cédula 04).",
        "Diferencia NIIF − fiscal": "Depreciación NIIF menos la fiscal deducible; positiva cuando la NIIF excede el máximo fiscal (suele ser diferencia temporaria).",
        "Exceso vehículo no deducible": "Depreciación sobre el costo del vehículo que supera el tope: diferencia permanente no deducible.",
    }

    # 06 · componentes.
    comp = [a for a in A if "part" in a]
    nc = len(comp)
    componentes = []
    for i, a in enumerate(comp):
        r, s = FILA0 + i, fila[a["id"]]
        componentes.append([a["id"], a["elemento"] or a["id"], fx(f"{DEP}B{s}", a["costo"]),
                            fx(f"SUMIF($B${FILA0}:$B${FILA0 + nc - 1},B{r},$C${FILA0}:$C${FILA0 + nc - 1})", a["costo_elem"]),
                            fx(f'IF(D{r}=0,"",C{r}/D{r})', a["part"]),
                            fx(f'IF(E{r}="","",IF(E{r}>={PAR["umbralComponente"]}/100,"Sí","No"))', a["signif"]),
                            fx(_si(f"{AUX}I{s}"), a["vida"]), a["metodo"]])

    # 07 · bajas.
    B = [a for a in A if a["baja"]]
    bajas = []
    for i, a in enumerate(B):
        r, s = FILA0 + i, fila[a["id"]]
        bajas.append([a["id"], a["baja"], fx(f"{DEP}B{s}", a["costo"]), fx(_si(f"{DEP}H{s}"), a["acum"]), fx(f"{AUX}M{s}", a["det"] or 0.0),
                      fx(f'IF(D{r}="","",C{r}-D{r}-E{r})', a["nbv_baja"]), fx(f"{AUX}S{s}", a["prod"] or 0.0),
                      fx(f'IF(F{r}="","",G{r}-F{r})', a["res_calc"]), fx(_si(f"{AUX}T{s}"), a["resreg"]),
                      fx(f'IF(OR(H{r}="",I{r}=""),"",H{r}-I{r})', a["res_dif"])])

    # 08 · revaluación.
    R = [a for a in A if "rev_dif" in a]
    frev = {a["id"]: FILA0 + i for i, a in enumerate(R)}
    revs = []
    for i, a in enumerate(R):
        r, s = FILA0 + i, fila[a["id"]]
        revs.append([a["id"], a["clase"], fx(f"{DEP}J{s}", a["nbv"]), fx(f"{AUX}O{s}", a["rev"]), fx(f"D{r}-C{r}", a["rev_dif"]),
                     fx(f"{AUX}P{s}", a["sup"] or 0.0), fx(_si(f"{AUX}Q{s}"), a["decPrev"]),
                     fx(f'IF(E{r}>=0,IF(G{r}="",E{r},E{r}-MIN(E{r},G{r})),-MIN(-E{r},F{r}))', a["rev_ori"]),
                     fx(f'IF(E{r}>=0,IF(G{r}="",0,MIN(E{r},G{r})),E{r}+MIN(-E{r},F{r}))', a["rev_res"])])

    # 09 · deterioro (NIC 36.60-61 / PYMES 27.6: primero contra el superávit del activo revaluado).
    D = [a for a in A if "perdida" in a]
    deter = []
    for i, a in enumerate(D):
        r, s = FILA0 + i, fila[a["id"]]
        ori_anio = f"{REV}H{frev[a['id']]}" if a["id"] in frev else "0"
        deter.append([a["id"], a["clase"], fx(f'IF({AUX}O{s}<>"",{AUX}O{s},{DEP}J{s})', a["libros"]), fx(f"{AUX}N{s}", a["rec"]),
                      fx(f'IF(C{r}="","",MAX(C{r}-D{r},0))', a["perdida"]),
                      fx(f'IF({AUX}P{s}="",0,{AUX}P{s})', a["supPrev"]), fx(ori_anio, a["revOri"]), fx(f"MAX(F{r}+G{r},0)", a["supRem"]),
                      fx(f'IF(E{r}="","",IF(AND({AUX}O{s}="",{AUX}P{s}=""),0,IF({AUX}P{s}="","",MIN(E{r},H{r}))))', a["detORI"]),
                      fx(f'IF(E{r}="","",IF(I{r}="",E{r},E{r}-I{r}))', a["detRes"])])

    # 10 · adiciones y costos por préstamos.
    adic = []
    ra, re_ = _rng(AUX, "A", n), _rng(AUX, "E", n)
    for i, x in enumerate(AD):
        r = FILA0 + i
        mt = f"MATCH(B{r},{ra},0)"
        fin = f'IF(ISNA({mt}),{PAR["corte"]},IF(INDEX({re_},{mt})="",{PAR["corte"]},MIN(INDEX({re_},{mt}),{PAR["corte"]})))'
        # Con anexo de préstamos el capitalizable se mide por activo en la cédula 12 (NIC 23.12 y 14).
        cap_f = '""' if npr else f'IF(I{r}=0,0,IF({PAR["tasaCapitalizacion"]}="","",F{r}*{PAR["tasaCapitalizacion"]}/100*I{r}/{PAR["diasAnio"]}))'
        adic.append([x["id"], x["activo"], x["fecha"], x["desc"], x["tipo"], x["importe"], x["apto"], x["int"],
                     fx(f'IF(OR({PAR["marco"]}="{MARCO_PYMES}",NOT(OR(G{r}="Sí",G{r}="Si"))),0,MAX({fin}-MAX(C{r},{PAR["inicio"]}),0))', x["dias"]),
                     fx(cap_f, x["cap"]), fx(f'IF(J{r}="","",J{r}-H{r})', x["int_dif"]),
                     fx(f'IF(OR(ISNUMBER(SEARCH("repar",E{r})),ISNUMBER(SEARCH("manten",E{r}))),"No: gasto (NIC 16.12)","Sí")', x["capitalizable"])])

    # 11 · préstamos para la construcción (datos del cliente).
    prest = []
    for i, y in enumerate(PRS):
        r = FILA0 + i
        prest.append([y["id"], y["tipo"], y["activo"], y["desc"], y["importe"], y["tasa"], y["costo"], y["rend"],
                      fx(f'IF(B{r}<>"Específico","",IF(OR(G{r}="",H{r}=""),"",G{r}-H{r}))', y["cap_esp"])])

    # 12 · capitalización por activo: específico (NIC 23.12) + generales (NIC 23.14) y tope del párrafo 14.
    PB, PC, PE, PG, PI = (_rng(PRE, c, npr) for c in ("B", "C", "E", "G", "I"))
    ADB, ADF, ADH, ADD = (_rng(ADI, c, nad) for c in ("B", "F", "H", "I"))
    ngen, pym = f'COUNTIF({PB},"General")', f'{PAR["marco"]}="{MARCO_PYMES}"'
    okgen = f'SUMPRODUCT(({PB}="General")*ISNUMBER({PE})*ISNUMBER({PG}))'
    tasa_f = (f'IF({pym},0,IF({ngen}=0,0,IF(OR({okgen}<{ngen},SUMIFS({PE},{PB},"General")=0),"",'
              f'SUMIFS({PG},{PB},"General")/SUMIFS({PE},{PB},"General"))))')
    rj = f"$J${FILA0}:$J${FILA0 + max(ncap, 1) - 1}"
    factor_f = (f'IF(OR(SUMPRODUCT(--ISNUMBER({PG}))<{npr},COUNT({rj})<{ncap}),"",'
                f'IF(SUM({rj})<=SUM({PG}),1,SUM({PG})/SUM({rj})))')
    capit = []
    for i, a in enumerate(CP):
        r = FILA0 + i
        nesp = f'SUMPRODUCT(({PB}="Específico")*({PC}=A{r}))'
        okimp = f'SUMPRODUCT(({PB}="Específico")*({PC}=A{r})*ISNUMBER({PE}))'
        okcap = f'SUMPRODUCT(({PB}="Específico")*({PC}=A{r})*ISNUMBER({PI}))'
        capit.append([
            a["activo"],
            fx(f'SUMIFS({ADF},{ADB},A{r},{ADD},">0")' if nad else "0", a["desemb"]),
            fx(f'SUMPRODUCT(({ADB}=A{r})*{ADF}*{ADD})/{PAR["diasAnio"]}' if nad else "0", a["base"]),
            fx(f'IF({nesp}=0,0,IF({okimp}<{nesp},"",SUMIFS({PE},{PB},"Específico",{PC},A{r})))', a["esp_imp"]),
            fx(f'IF({pym},0,IF({nesp}=0,0,IF({okcap}<{nesp},"",SUMIFS({PI},{PB},"Específico",{PC},A{r}))))', a["esp_cap"]),
            fx(f'IF(D{r}="","",IF(B{r}=0,0,MAX(1-D{r}/B{r},0)))', a["pct"]),
            fx(f'IF(F{r}="","",C{r}*F{r})', a["base_gen"]), fx(tasa_f, a["tasa"]),
            fx(f'IF(OR(G{r}="",H{r}=""),"",G{r}*H{r})', a["cap_gen"]),
            fx(f'IF(OR(E{r}="",I{r}=""),"",E{r}+I{r})', a["antes"]), fx(factor_f, a["factor"]),
            fx(f'IF(J{r}="","",IF(K{r}="",J{r},J{r}*K{r}))', a["final"]),
            fx(f'SUMIFS({ADH},{ADB},A{r})' if nad else "0", a["reg"]),
            fx(f'IF(L{r}="","",L{r}-M{r})', a["dif"]),
        ])
    sc = lambda k: sum(a[k] for a in CP if a[k] is not None)

    # 13 · desmantelamiento.
    b = lambda k: f"B{FILA0 + k}"
    desm = [
        ["Costo estimado futuro", fx(_si(PAR["costoDesmantelamiento"]), ds["costo"])],
        ["Años hasta el desembolso", fx(_si(PAR["aniosDesmantelamiento"]), ds["anios"])],
        ["Tasa de descuento antes de impuestos (%)", fx(_si(PAR["tasaDesmantelamiento"]), ds["tasa"])],
        ["Valor presente = costo ÷ (1 + tasa)^años", fx(f'IF(OR({b(0)}="",{b(1)}="",{b(2)}=""),"",{b(0)}/(1+{b(2)}/100)^{b(1)})', ds["vp"])],
        ["Provisión registrada al cierre", fx(_si(PAR["provisionDesmantelamiento"]), ds["registrada"])],
        ["Provisión registrada al inicio del ejercicio",
         fx(f'IF({PAR["provisionDesmantelamientoInicial"]}<>"",{PAR["provisionDesmantelamientoInicial"]},'
            f'IF({PAR["provisionDesmantelamiento"]}="",0,""))', ds["inicial"])],
        ["Actualización financiera del período = inicial × tasa → resultados, costo financiero (CINIIF 1.8; NIC 37.60; PYMES 21.11)",
         fx(f'IF(OR({b(3)}="",{b(5)}="",{b(2)}=""),"",{b(5)}*{b(2)}/100)', ds["actualizacion"])],
        ["Ajuste total = valor presente − registrada al cierre", fx(f'IF({b(3)}="","",{b(3)}-IF({b(4)}="",0,{b(4)}))', ds["dif"])],
        ["Cambio de estimación = ajuste total − actualización → costo del activo (CINIIF 1.5 a; PYMES 21.7 b)",
         fx(f'IF(OR({b(7)}="",{b(6)}=""),"",{b(7)}-{b(6)})', ds["cambio"])],
    ]

    # 14 · roll-forward.
    c = lambda k: f"B{FILA0 + k}"
    rfw = [
        ["Costo al inicio (auxiliar)", fx(f"SUM({_rng(AUX, 'F', n)})", rf["ci"])],
        ["(+) Adiciones del año", fx(f"SUM({_rng(AUX, 'G', n)})", rf["ad"])],
        ["(−) Costo de las bajas", fx(f'SUMIF({_rng(DEP, "L", n)},"Baja",{_rng(DEP, "B", n)})', rf["costoBajas"])],
        ["Costo al cierre (auxiliar)", fx(f"{c(0)}+{c(1)}-{c(2)}", rf["costoFinal"])],
        ["Costo al cierre según el mayor", fx(_si(PAR["mayorCosto"]), rf["mayorCosto"])],
        ["Diferencia auxiliar − mayor (costo)", fx(f'IF({c(4)}="","",{c(3)}-{c(4)})', rf["difCosto"])],
        ["Depreciación acumulada al inicio", fx(f"SUM({_rng(AUX, 'K', n)})", rf["dai"])],
        ["(+) Depreciación del año registrada", fx(f"SUM({_rng(AUX, 'L', n)})", rf["dreg"])],
        ["(−) Depreciación acumulada de las bajas", fx(f'SUMIF({_rng(DEP, "L", n)},"Baja",{_rng(AUX, "K", n)})+SUMIF({_rng(DEP, "L", n)},"Baja",{_rng(AUX, "L", n)})', rf["depBajas"])],
        ["Depreciación acumulada al cierre (registrada)", fx(f"{c(6)}+{c(7)}-{c(8)}", rf["depFinalReg"])],
        ["Depreciación acumulada según el mayor", fx(_si(PAR["mayorDepAcum"]), rf["mayorDep"])],
        ["Diferencia auxiliar − mayor (depreciación)", fx(f'IF({c(10)}="","",{c(9)}-{c(10)})', rf["difDep"])],
        ["Depreciación acumulada al cierre recalculada (activos medidos)", fx(f'SUMIF({_rng(DEP, "L", n)},"<>Baja",{_rng(DEP, "H", n)})', rf["depFinalCalc"])],
        ["Valor neto en libros recalculado (activos medidos)", fx(f'SUMIF({_rng(DEP, "L", n)},"<>Baja",{_rng(DEP, "J", n)})', rf["nbv"])],
        ["Adiciones según el detalle", fx(f"SUM({_rng(ADI, 'F', nad)})", rf["adDetalle"]) if nad else None],
        ["Diferencia adiciones auxiliar − detalle", fx(f"{c(1)}-{c(14)}", rf["difAd"]) if nad else None],
    ]

    # 15 · ajustes propuestos.
    s = lambda col, h, nn: f"SUM({_rng(h, col, nn)})" if nn else "0"
    ajus = [
        ["Depreciación recalculada − registrada", fx(s("G", DEP, n), aj["ajusteDep"]), "Gasto por depreciación", "(−) Depreciación acumulada", "NIC 16.50; PYMES 17.18"],
        ["Deterioro a resultados", fx(s("J", DET, len(D)), aj["deterioroResultado"]), "Pérdida por deterioro", "(−) Deterioro acumulado",
         "NIC 36.59–61; PYMES 27.5–27.6: en un activo revaluado, primero contra el superávit y solo el exceso a resultados"],
        ["Resultado de bajas recalculado − registrado", fx(s("J", BAJ, len(B)), aj["ajusteBajas"]), "Resultado en baja de activos", "Propiedad, planta y equipo", "NIC 16.68, 71; PYMES 17.28–17.30"],
        ["Costos por préstamos capitalizables − capitalizados",
         fx(s("N", CAP, ncap) if npr else s("K", ADI, nad), aj["ajusteIntereses"]),
         "Construcciones en curso / Gasto financiero", "Gasto financiero / Construcciones en curso",
         "Sección 25.2 (PYMES: todo a gasto)" if d["marco"] == MARCO_PYMES else
         ("NIC 23.12 (específico: costo real − rendimientos), 23.14 (generales: tasa de capitalización) y el tope del 23.14"
          if npr else "NIC 23.8, 14 (estimación por desembolso: falta el anexo de préstamos)")],
        ["Revaluación a otro resultado integral", fx(s("H", REV, len(R)), aj["revaluacionORI"]), "Propiedad, planta y equipo", "Superávit de revaluación (ORI)", "NIC 16.39–40; PYMES 17.15C–17.15D"],
        ["Revaluación a resultados", fx(s("I", REV, len(R)), aj["revaluacionResultado"]), "Pérdida por revaluación / Reversión de decremento previo", "Propiedad, planta y equipo",
         "NIC 16.39 (aumento que revierte un decremento previo en resultados) y 16.40; PYMES 17.15C–17.15D"],
        ["Deterioro contra el superávit de revaluación", fx(s("I", DET, len(D)), aj["deterioroORI"]), "Superávit de revaluación (ORI)", "(−) Deterioro acumulado",
         "NIC 36.60–61; PYMES 27.6"],
        ["Desmantelamiento: cambio de estimación", fx(f"{DES}B{FILA0 + 8}", ds["cambio"]) if ds["cambio"] is not None else None,
         "Propiedad, planta y equipo (costo)", "Provisión por desmantelamiento", "CINIIF 1.5 a; NIC 16.16 c; NIC 37.45; PYMES 21.7 b"],
        ["Desmantelamiento: actualización financiera del período", fx(f"{DES}B{FILA0 + 6}", ds["actualizacion"]) if ds["actualizacion"] is not None else None,
         "Costo financiero (resultados)", "Provisión por desmantelamiento", "CINIIF 1.8; NIC 37.60; PYMES 21.11"],
        ["Efecto neto en resultados",
         fx(f'-B{FILA0}-B{FILA0 + 1}+B{FILA0 + 2}+B{FILA0 + 3}+B{FILA0 + 5}-IF(B{FILA0 + 8}="",0,B{FILA0 + 8})', aj["ajusteResultado"]), "", "",
         "− depreciación − deterioro a resultados + bajas + intereses + revaluación a resultados − actualización financiera del desmantelamiento"],
    ]

    # Estilos de cédula sumaria (una entrada por fila de datos, o None):
    _sg = {"sangria": 1, "col": "Concepto"}
    # 13 · Desmantelamiento: las variables del valor presente sangradas y los importes calculados (valor
    # presente, ajuste total y cambio de estimación) como subtotales con filete.
    estilos_desm = [_sg, _sg, _sg, {"tipo": "total"}, None, None, None, {"tipo": "total"}, {"tipo": "total"}]
    # 14 · Roll-forward: los movimientos del costo y de la depreciación sangrados bajo sus subtotales de
    # cierre, y las diferencias auxiliar − mayor como líneas de control.
    estilos_rfw = [
        None,               # 0 · Costo al inicio (auxiliar)
        _sg,                # 1 · (+) Adiciones del año
        _sg,                # 2 · (−) Costo de las bajas
        {"tipo": "total"},  # 3 · Costo al cierre (auxiliar)
        None,               # 4 · Costo al cierre según el mayor
        {"tipo": "control"},  # 5 · Diferencia auxiliar − mayor (costo)
        None,               # 6 · Depreciación acumulada al inicio
        _sg,                # 7 · (+) Depreciación del año registrada
        _sg,                # 8 · (−) Depreciación acumulada de las bajas
        {"tipo": "total"},  # 9 · Depreciación acumulada al cierre (registrada)
        None,               # 10 · Depreciación acumulada según el mayor
        {"tipo": "control"},  # 11 · Diferencia auxiliar − mayor (depreciación)
        None,               # 12 · Depreciación acumulada al cierre recalculada
        {"tipo": "total"},  # 13 · Valor neto en libros recalculado
        None,               # 14 · Adiciones según el detalle
        {"tipo": "control"},  # 15 · Diferencia adiciones auxiliar − detalle
    ]
    # 15 · Ajustes propuestos: cada ajuste es una partida independiente; solo el efecto neto es subtotal.
    estilos_ajus = [None] * (len(ajus) - 1) + [{"tipo": "total"}]

    celda = {"costoFinal": f"{RF}B{FILA0 + 3}", "depRecalculada": f"SUM({_rng(DEP, 'E', n)})", "depRegistrada": f"{RF}B{FILA0 + 7}",
             "ajusteDep": f"{AJ}B{FILA0}", "nbv": f"{RF}B{FILA0 + 13}", "deterioroAdicional": f"SUM({_rng(DET, 'E', len(D))})",
             "deterioroORI": f"{AJ}B{FILA0 + 6}", "deterioroResultado": f"{AJ}B{FILA0 + 1}",
             "capitalizableEspecificos": f"{CAP}E{FILA0 + ncap}", "capitalizableGenerales": f"{CAP}I{FILA0 + ncap}",
             "costosPrestamosIncurridos": f"{PRE}G{FILA0 + npr}", "capitalizablePeriodo": f"{CAP}L{FILA0 + ncap}",
             "ajusteBajas": f"{AJ}B{FILA0 + 2}", "ajusteIntereses": f"{AJ}B{FILA0 + 3}", "revaluacionORI": f"{AJ}B{FILA0 + 4}",
             "revaluacionResultado": f"{AJ}B{FILA0 + 5}", "provDesmantelamiento": f"{DES}B{FILA0 + 3}",
             "ajusteDesmantelamiento": f"{AJ}B{FILA0 + 7}", "desmantelamientoFinanciero": f"{AJ}B{FILA0 + 8}",
             "difCosto": f"{RF}B{FILA0 + 5}", "difDepAcum": f"{RF}B{FILA0 + 11}", "ajusteResultado": f"{AJ}B{FILA0 + 9}"}
    valor = {"costoFinal": rf["costoFinal"], "depRecalculada": sum(a["dep"] for a in A if a["dep"] is not None), "depRegistrada": rf["dreg"],
             "nbv": rf["nbv"], "provDesmantelamiento": ds["vp"], "difCosto": rf["difCosto"], "difDepAcum": rf["difDep"],
             "capitalizableEspecificos": sc("esp_cap"), "capitalizableGenerales": sc("cap_gen"),
             "costosPrestamosIncurridos": d["tope"]["incurridos"], "capitalizablePeriodo": sc("final"), **aj}
    resumen = [[res["labels"][k], fx(celda[k], valor[k])] for k in res["labels"]]

    # 17 · Indicadores y conclusión (con semáforo coloreable en «Estado»).
    tt = {k: float(v) for k, v in res["totals"].items()}
    PROB = ref("16_Problemas")
    nprob = len(res["exceptions"])
    pct_v = None if tt["costoFinal"] == 0 else abs(tt["ajusteResultado"]) / tt["costoFinal"]
    r2f, r3f, r5f, r6f = FILA0 + 2, FILA0 + 3, FILA0 + 5, FILA0 + 6
    est = lambda cond, alto, ok="Conforme": (alto if cond else ok)
    conclusion = [
        [res["labels"]["costoFinal"], fx(celda["costoFinal"], tt["costoFinal"]), None, None, ""],
        [res["labels"]["nbv"] + " (resultado principal)", fx(celda["nbv"], tt["nbv"]), None, None,
         fx(f'IF(ABS(B{r3f})>0.005,"Revisar","Conforme")', est(abs(tt["ajusteResultado"]) > 0.005, "Revisar"))],
        [res["labels"]["ajusteDep"], fx(celda["ajusteDep"], tt["ajusteDep"]), None, None,
         fx(f'IF(ABS(B{r2f})>0.005,"Alerta","Conforme")', est(abs(tt["ajusteDep"]) > 0.005, "Alerta"))],
        [res["labels"]["ajusteResultado"], fx(celda["ajusteResultado"], tt["ajusteResultado"]), None, None,
         fx(f'IF(ABS(B{r3f})>0.005,"Alerta","Conforme")', est(abs(tt["ajusteResultado"]) > 0.005, "Alerta"))],
        ["% del efecto neto en resultados sobre el costo al cierre", None,
         fx(f'IF(B{FILA0}=0,"",ABS(B{r3f})/B{FILA0})', pct_v), None,
         fx(f'IF(C{FILA0 + 4}="","",IF(ABS(B{r3f})>0.005,"Revisar","Conforme"))',
            "" if pct_v is None else est(abs(tt["ajusteResultado"]) > 0.005, "Revisar"))],
        ["Diferencia auxiliar − mayor (costo)", fx(celda["difCosto"], rf["difCosto"]), None, None,
         fx(f'IF(B{r5f}="","",IF(ABS(B{r5f})>0.005,"Alerta","Conforme"))',
            "" if rf["difCosto"] is None else est(abs(rf["difCosto"]) > 0.005, "Alerta"))],
        ["Problemas encontrados", None, None, fx(f"COUNTA({_rng(PROB, 'A', nprob)})", nprob),
         fx(f'IF(D{r6f}>0,"Revisar","Conforme")', est(nprob > 0, "Revisar"))],
    ]
    ex_conclusion = {
        "Importe": ("Cada indicador trae su cifra de la hoja que la calcula: el costo al cierre y la diferencia con el mayor, de "
                    "la hoja 14 (Movimiento del año); el valor neto en libros, la diferencia de depreciación y el efecto neto "
                    "en resultados, de la hoja 15 (Ajustes propuestos)."),
        "Porcentaje": ("Divide el efecto neto en resultados en valor absoluto entre el costo al cierre para medir su peso "
                       "relativo; queda en blanco si el costo al cierre es cero."),
        "Cantidad": ("Cuenta cuántos problemas se detectaron leyendo la columna de códigos de la hoja 16 (Problemas "
                     "encontrados)."),
        "Estado": ("Semáforo del indicador: «Alerta» cuando un ajuste o una diferencia dejan de ser cero, «Revisar» cuando el "
                   "efecto neto en resultados o los problemas piden atención y «Conforme» cuando el indicador no presenta "
                   "desviaciones."),
    }

    # 18 · Lectura de resultados (causa-efecto con las cifras embebidas por FIXED).
    _fix = lambda cell: f"FIXED({cell},2)"
    cita_dep = "Sección 17" if d["marco"] == MARCO_PYMES else "NIC 16.60-62"
    lectura = [
        ["Resultado principal",
         fx(f'"El valor neto en libros auditado de la propiedad, planta y equipo es de US$ "&{_fix(celda["nbv"])}&", sobre un costo al cierre de US$ "&{_fix(celda["costoFinal"])}&" (hojas 15 y 14)."',
            f"El valor neto en libros auditado de la propiedad, planta y equipo es de US$ {m(tt['nbv'])}, sobre un costo al cierre de US$ {m(tt['costoFinal'])} (hojas 15 y 14).")],
        ["Efecto neto en resultados",
         fx(f'"El efecto neto de los ajustes en resultados es de US$ "&{_fix(celda["ajusteResultado"])}&"; su registro corrige la depreciación, el deterioro y los demás ajustes del ejercicio (hoja 15)."',
            f"El efecto neto de los ajustes en resultados es de US$ {m(tt['ajusteResultado'])}; su registro corrige la depreciación, el deterioro y los demás ajustes del ejercicio (hoja 15).")],
        ["Depreciación",
         fx(f'"La depreciación del año recalculada es de US$ "&{_fix(celda["depRecalculada"])}&", con una diferencia de US$ "&{_fix(celda["ajusteDep"])}&" frente a la registrada, que debe corregirse ({cita_dep})."',
            f"La depreciación del año recalculada es de US$ {m(tt['depRecalculada'])}, con una diferencia de US$ {m(tt['ajusteDep'])} frente a la registrada, que debe corregirse ({cita_dep}).")],
        ["Deterioro y revaluación",
         fx(f'"El deterioro adicional recalculado suma US$ "&{_fix(celda["deterioroAdicional"])}&" y la revaluación reconocida en resultados US$ "&{_fix(celda["revaluacionResultado"])}&", que afectan el valor del activo y el resultado del período (NIC 36 y NIC 16.39-40)."',
            f"El deterioro adicional recalculado suma US$ {m(tt['deterioroAdicional'])} y la revaluación reconocida en resultados US$ {m(tt['revaluacionResultado'])}, que afectan el valor del activo y el resultado del período (NIC 36 y NIC 16.39-40).")],
        ["Cierre",
         fx(f'"En conjunto, sobre un costo al cierre de US$ "&{_fix(celda["costoFinal"])}&", los hallazgos exigen registrar los ajustes propuestos (hoja 15) y revelar la conciliación del movimiento del ejercicio."',
            f"En conjunto, sobre un costo al cierre de US$ {m(tt['costoFinal'])}, los hallazgos exigen registrar los ajustes propuestos (hoja 15) y revelar la conciliación del movimiento del ejercicio.")],
    ]
    ex_lectura = {"Detalle": ("Redacta en lenguaje del auditor la lectura causa-efecto de los resultados e inserta cada cifra "
                              "con FIXED desde la hoja 15 (Ajustes propuestos) y la hoja 14 (Movimiento del año): el valor neto en "
                              "libros y el costo al cierre, el efecto neto en resultados, la diferencia de depreciación y el "
                              "deterioro y la revaluación del ejercicio.")}

    # 19 · resumen por estado del activo. El estado (En uso / En construcción / Baja) es la clasificación FIJA
    # que calcula el módulo en la columna L de la cédula 04 —a diferencia de la «Clase», que es un texto libre
    # del cliente—; cada celda es una fórmula SUMIFS/COUNTIF sobre ese detalle, con el mismo valor en Python.
    ESTADOS = ["En uso", "En construcción", "Baja"]
    dLl, dBc, dHc, dJc = (_rng(DEP, col, n) for col in ("L", "B", "H", "J"))
    resumen_estado = []
    for i, cat in enumerate(ESTADOS):
        r = FILA0 + i
        grupo = [a for a in A if a["estado"] == cat]
        resumen_estado.append([
            cat,
            fx(f"COUNTIF({dLl},A{r})", len(grupo)),
            fx(f"SUMIFS({dBc},{dLl},A{r})", sum(a["costo"] for a in grupo)),
            fx(f"SUMIFS({dHc},{dLl},A{r})", sum(a["acum"] or 0 for a in grupo)),
            fx(f"SUMIFS({dJc},{dLl},A{r})", sum(a["nbv"] or 0 for a in grupo)),
        ])
    fe = FILA0 + len(ESTADOS) - 1
    total_estado = ["TOTAL", suma("B", fe, n), suma("C", fe, sum(a["costo"] for a in A)),
                    suma("D", fe, sum(a["acum"] or 0 for a in A)), suma("E", fe, sum(a["nbv"] or 0 for a in A))]
    ex_estado = {
        "Cantidad": "Cuenta cuántos activos hay en cada estado leyendo la columna «Estado» de la hoja 04 (Recálculo de "
                    "depreciación y VNL).",
        "Costo": "Suma el costo (costo inicial más adiciones) de los activos de cada estado, tomándolo de la hoja 04 "
                 "(Recálculo de depreciación y VNL).",
        "Depreciación acumulada": "Suma la depreciación acumulada recalculada de los activos de cada estado, desde la hoja 04 "
                                  "(Recálculo de depreciación y VNL); los activos sin recálculo (método no lineal) no suman.",
        "Valor neto en libros": "Suma el valor neto en libros recalculado (costo menos depreciación acumulada menos deterioro) de "
                                "los activos de cada estado, desde la hoja 04 (Recálculo de depreciación y VNL).",
    }

    # --- «Cómo se calcula esta hoja»: explicación humana por columna calculada -------------
    ex_resumen = {"Importe": "Trae cada concepto de su hoja: costo y diferencias con el mayor de la hoja 14 (Movimiento del año), "
                             "depreciación de las hojas 04 y 14, ajustes de la hoja 15 (Ajustes propuestos), deterioro de la hoja 09, "
                             "costos por préstamos de las hojas 11 y 12 y desmantelamiento de la hoja 13."}
    ex_par = {"Valor": "Son los datos de la ficha del encargo y del mayor; la única fila calculada es «Días del ejercicio»: fecha de "
                       "corte menos fecha de inicio, más un día."}
    ex_dep = {
        "Costo": "Suma el costo inicial y las adiciones del año del activo, tomados de la hoja 03 (Auxiliar de activos).",
        "Importe depreciable": "Costo menos el valor residual de la hoja 03 (Auxiliar de activos), sin bajar de cero: es lo que se "
                               "reparte durante la vida útil.",
        "Días en uso": "Cuenta los días del ejercicio en que el activo estuvo disponible: desde su fecha de disponibilidad (o el "
                       "inicio del ejercicio) hasta el corte o la fecha de baja. Si no tiene fecha de disponibilidad (en "
                       "construcción), es cero.",
        "Depreciación recalculada": "Solo para el método lineal: importe depreciable ÷ vida útil en meses × 12 × días en uso ÷ días "
                                    "del ejercicio, sin pasar de lo que queda por depreciar. Otros métodos quedan en blanco; sin "
                                    "vida útil o sin días en uso da cero.",
        "Depreciación registrada": "Trae la depreciación del año que registró el cliente, desde la hoja 03 (Auxiliar de activos); "
                                   "en blanco si no la informó.",
        "Diferencia": "Depreciación recalculada menos registrada; en blanco si falta alguna de las dos.",
        "Dep. acumulada recalculada": "Suma la depreciación acumulada al inicio de la hoja 03 (Auxiliar de activos) y la "
                                      "depreciación recalculada del año; en blanco si no se recalculó.",
        "Deterioro acumulado": "Trae el deterioro acumulado que registró el cliente para el activo, desde la hoja 03 (Auxiliar de "
                               "activos).",
        "Valor neto en libros": "Costo menos depreciación acumulada recalculada menos deterioro acumulado; en blanco si la "
                                "depreciación no se recalculó.",
        "Totalmente depreciado": "«Sí» cuando la depreciación acumulada recalculada ya cubre todo el importe depreciable; «No» si "
                                 "no; en blanco si no se recalculó.",
        "Estado": "«Baja» si el activo tiene fecha de baja en la hoja 03, «En construcción» si aún no tiene fecha de disponibilidad "
                  "para uso y «En uso» en los demás casos.",
        "Semáforo": ("Estado del activo: «Alerta» si la diferencia entre la depreciación recalculada y la registrada supera la "
                     "tolerancia de la hoja 02 (Parámetros), «Conforme» si está dentro de ella. Queda en blanco si no se recalculó "
                     "la depreciación (método no lineal o sin datos)."),
        "Dep. acumulada cliente": "Depreciación acumulada del cliente al corte: suma la acumulada al inicio informada en la hoja 03 "
                                  "(Auxiliar de activos) y el gasto de depreciación del año que el cliente registró (columna "
                                  "«Depreciación registrada»).",
        "Dif. dep. acumulada": "Depreciación acumulada recalculada por el auditor (columna «Dep. acumulada recalculada») menos la del "
                               "cliente; positiva cuando el auditor calcula más acumulada que la registrada. En blanco si no se "
                               "recalculó la depreciación.",
    }
    ex_vidas = {
        "Vida útil (meses)": "Trae la vida útil en meses informada en la hoja 03 (Auxiliar de activos); en blanco si no se informó.",
        "Valor residual": "Trae el valor residual del activo desde la hoja 03 (Auxiliar de activos); si está vacío, cero.",
        "Costo": "Trae el costo del activo (costo inicial más adiciones) desde la hoja 04 (Recálculo de depreciación y VNL).",
        "Residual % del costo": "Divide el valor residual para el costo, para ver si el residual es razonable; en blanco si el "
                                "costo es cero.",
        "Dep. acumulada recalculada": "Trae la depreciación acumulada recalculada desde la hoja 04 (Recálculo de depreciación y "
                                      "VNL); en blanco si allí no se recalculó.",
        "Vida remanente (meses)": "Parte de la vida útil que queda: importe depreciable pendiente (hoja 04) sobre el importe "
                                  "depreciable total, por la vida útil en meses. En blanco si falta la vida útil o la depreciación.",
        "Totalmente depreciado en uso": "«Sí» cuando en la hoja 04 el activo figura totalmente depreciado y sigue en uso: señal "
                                        "de que la vida útil estimada fue corta.",
        "Residual mayor que el costo": "«Sí» si el valor residual supera al costo del activo, lo que no es razonable; «No» en "
                                       "caso contrario.",
    }
    ex_comp = {
        "Costo de la parte": "Trae el costo de esta parte (componente) desde la hoja 04 (Recálculo de depreciación y VNL).",
        "Costo del elemento": "Suma el costo de todas las partes de esta hoja que pertenecen al mismo elemento: es el costo total "
                              "del elemento.",
        "% del elemento": "Divide el costo de la parte para el costo total del elemento; en blanco si el elemento no tiene costo.",
        "Parte significativa": "«Sí» si el % del elemento alcanza el umbral de parte significativa de la hoja 02 (Parámetros), por "
                               "lo que debe depreciarse por separado; «No» si no llega.",
        "Vida útil (meses)": "Trae la vida útil en meses de la parte desde la hoja 03 (Auxiliar de activos); en blanco si no se "
                             "informó.",
    }
    ex_bajas = {
        "Costo": "Trae el costo del activo dado de baja desde la hoja 04 (Recálculo de depreciación y VNL).",
        "Dep. acumulada a la baja": "Trae la depreciación acumulada recalculada hasta la fecha de baja, desde la hoja 04; en blanco "
                                    "si no se pudo recalcular.",
        "Deterioro": "Trae el deterioro acumulado del activo desde la hoja 03 (Auxiliar de activos).",
        "VNL a la baja": "Costo menos depreciación acumulada a la baja menos deterioro: es el valor en libros que sale con la baja "
                         "(en blanco si falta la depreciación acumulada).",
        "Producto": "Trae lo que se cobró por la baja (venta o indemnización) desde la hoja 03 (Auxiliar de activos); si está "
                    "vacío, cero.",
        "Resultado recalculado": "Producto de la baja menos el valor neto en libros a la baja: positivo es ganancia y negativo "
                                 "pérdida.",
        "Resultado registrado": "Trae la ganancia o pérdida en la baja que registró el cliente, desde la hoja 03; en blanco si no "
                                "la informó.",
        "Diferencia": "Resultado recalculado menos resultado registrado; en blanco si falta alguno de los dos.",
    }
    ex_rev = {
        "VNL al corte": "Trae el valor neto en libros recalculado al corte desde la hoja 04 (Recálculo de depreciación y VNL).",
        "Valor revaluado": "Trae el valor revaluado del activo (según el perito) desde la hoja 03 (Auxiliar de activos).",
        "Diferencia": "Valor revaluado menos valor neto en libros: positivo es aumento y negativo disminución por revaluación.",
        "Superávit previo": "Trae el superávit de revaluación que ya tenía el activo, desde la hoja 03 (Auxiliar de activos).",
        "Decremento previo en resultados": "Trae la disminución por revaluación que se llevó antes a resultados, desde la hoja 03; "
                                           "en blanco si no se informó.",
        "A otro resultado integral": "Si es aumento, va a ORI lo que excede al decremento previo llevado a resultados (todo, si ese "
                                     "dato está vacío). Si es disminución, se carga a ORI solo hasta el superávit previo.",
        "A resultados": "Si es aumento, va a resultados solo lo que revierte el decremento previo (cero si ese dato está vacío). "
                        "Si es disminución, va a resultados lo que excede al superávit previo.",
    }
    ex_det = {
        "Importe en libros": "Usa el valor revaluado de la hoja 03 si el activo se revaluó; si no, el valor neto en libros de la "
                             "hoja 04 (Recálculo de depreciación y VNL).",
        "Importe recuperable": "Trae el importe recuperable estimado del activo desde la hoja 03 (Auxiliar de activos).",
        "Pérdida adicional": "Importe en libros menos importe recuperable, sin bajar de cero: es la pérdida por deterioro. En "
                             "blanco si no hay importe en libros.",
        "Superávit previo": "Trae el superávit de revaluación previo del activo desde la hoja 03 (Auxiliar de activos); si está "
                            "vacío, cero.",
        "Revaluación del año a ORI": "Trae lo que la revaluación del año llevó a ORI en la hoja 08 (Revaluación); cero si el "
                                     "activo no se revaluó este año.",
        "Superávit disponible": "Suma el superávit previo y la revaluación del año a ORI, sin bajar de cero: es el colchón contra "
                                "el que se carga primero el deterioro.",
        "Contra el superávit (ORI)": "Carga la pérdida contra el superávit disponible, hasta agotarlo. Si el activo no está "
                                     "revaluado ni tiene superávit, es cero; si está revaluado pero falta el superávit, queda en "
                                     "blanco.",
        "A resultados": "La pérdida que no se cargó al superávit va a resultados; si no se pudo repartir (celda anterior en "
                        "blanco), va toda la pérdida.",
    }
    if npr:
        ex_ad_int = ("Con el anexo de préstamos los intereses capitalizables se miden por activo en la hoja 12 (Capitalización de "
                     "costos por préstamos), por eso aquí quedan en blanco.")
        ex_ad_dif = ("Intereses capitalizables menos intereses capitalizados por el cliente; con el anexo de préstamos queda en "
                     "blanco porque la comparación se hace en la hoja 12.")
    else:
        ex_ad_int = ("Importe de la adición × tasa de capitalización de la hoja 02 (Parámetros) × días de capitalización ÷ días del "
                     "ejercicio. Cero si no hay días; en blanco si no hay tasa.")
        ex_ad_dif = "Intereses capitalizables recalculados menos los intereses que el cliente capitalizó en esta adición."
    ex_adic = {
        "Días de capitalización": "Para adiciones de activos aptos (y solo en NIIF completas): días desde la fecha de la adición (o "
                                  "el inicio del ejercicio) hasta que el activo está disponible para uso según la hoja 03, o hasta el "
                                  "corte. Si no, cero.",
        "Intereses capitalizables": ex_ad_int,
        "Diferencia": ex_ad_dif,
        "Capitalizable": "«No: gasto» si el tipo de adición es una reparación o un mantenimiento, que no se capitalizan; «Sí» en "
                         "los demás casos.",
    }
    ex_pre = {"Capitalizable del específico (NIC 23.12)": "Solo para préstamos específicos: costo financiero del período menos "
                                                          "los rendimientos de la inversión temporal de esos fondos. En blanco "
                                                          "para préstamos generales o si falta un dato."}
    ex_cap = {
        "Desembolsos aptos del período": "Suma las adiciones de este activo en la hoja 10 (Adiciones) que tienen días de "
                                         "capitalización.",
        "Base ponderada por tiempo": "Suma cada adición del activo en la hoja 10 multiplicada por sus días de capitalización y la "
                                     "divide para los días del ejercicio: es el desembolso promedio del año.",
        "Préstamo específico: importe": "Suma el importe de los préstamos específicos de este activo en la hoja 11 (Préstamos); "
                                        "cero si no tiene y en blanco si alguno no trae importe.",
        "Capitalizable del específico (NIC 23.12)": "Suma lo capitalizable de los préstamos específicos del activo en la hoja 11. "
                                                    "Es cero en PYMES o sin préstamo específico, y en blanco si falta un dato.",
        "% financiado con préstamos generales": "Parte de los desembolsos que no cubre el préstamo específico: 1 − importe "
                                                "específico ÷ desembolsos, sin bajar de cero. Cero si no hubo desembolsos.",
        "Base financiada con generales": "Multiplica la base ponderada por tiempo por el % financiado con préstamos generales.",
        "Tasa de capitalización (NIC 23.14)": "Media ponderada de los préstamos generales de la hoja 11: su costo financiero total "
                                              "÷ su importe total. Cero en PYMES o sin generales; en blanco si falta un dato.",
        "Capitalizable de los generales": "Multiplica la base financiada con generales por la tasa de capitalización; en blanco si "
                                          "falta alguno de los dos.",
        "Capitalizable antes del tope": "Suma lo capitalizable del préstamo específico y de los generales para este activo.",
        "Factor del tope (NIC 23.14)": "Si lo capitalizable de todos los activos no supera el costo financiero incurrido de la hoja "
                                       "11, es 1; si lo supera, es costo incurrido ÷ capitalizable total, para no pasar del tope. "
                                       "En blanco si falta algún dato.",
        "Capitalizable del período": "Capitalizable antes del tope multiplicado por el factor del tope (si el factor está en "
                                     "blanco, se deja sin reducir).",
        "Intereses capitalizados registrados": "Suma los intereses que el cliente capitalizó en las adiciones de este activo, según "
                                               "la hoja 10 (Adiciones).",
        "Diferencia": "Capitalizable del período menos intereses capitalizados registrados: positivo falta capitalizar y negativo "
                      "se capitalizó de más.",
    }
    ex_desm = {"Importe": "Toma de la hoja 02 (Parámetros) el costo futuro, los años, la tasa y la provisión registrada; calcula el "
                          "valor presente (costo ÷ (1 + tasa)^años), la actualización del año (provisión inicial × tasa) y separa "
                          "el ajuste total en actualización y cambio de estimación."}
    ex_rf = {"Importe": "Arma el movimiento del año con las sumas de la hoja 03 (costo, adiciones, depreciación) y de la hoja 04 "
                        "(bajas y valores recalculados), lo compara con el mayor de la hoja 02 y cuadra las adiciones con la hoja 10."}
    ex_aj = {"Importe": "Suma la diferencia de cada prueba desde su hoja (04 depreciación, 09 deterioro, 07 bajas, 12 o 10 intereses, "
                        "08 revaluación, 13 desmantelamiento); la última fila combina esos ajustes para dar el efecto neto en "
                        "resultados."}

    fin = lambda nn: FILA0 + nn - 1
    # 21 · recálculo comparativo por días (método del papel de trabajo del auditor) y comparación con el cliente.
    # Cada cifra es una fórmula (fx) que referencia la cédula 04 (costo, días, cliente) y las columnas de la propia
    # fila, para que el cálculo quede auditable en el Excel (no valores pegados).
    comparativo = []
    for i, a in enumerate(A):
        r = FILA0 + i
        comparativo.append([
            a["id"], a["clase"],
            fx(f"{DEP}B{r}", a["costo"]),                                               # C Costo (04)
            fx(f"{DEP}C{r}", a["depr"]),                                                # D Valor a depreciar (04)
            fx(f'IF({AUX}I{r}="","",{AUX}I{r}/12)', a.get("vida_anios_anexo")),         # E Vida anexo (años)
            fx(f'IF({FIS}D{r}="","",1/{FIS}D{r})', a.get("vida_anios_sri")),            # F Vida SRI (1/tasa)
            fx("", a.get("vida_anios_pol")),                                            # G Vida política (de la política)
            fx(f'IF(OR(E{r}="",D{r}=""),"",D{r}/(E{r}*{DIAS_ANIO_VIDA}))', a.get("diaria_anexo")),  # H Dep. diaria
            fx(f"{DEP}D{r}", a["dias"]),                                                # I Días gasto (04)
            fx(f'IF(H{r}="","",MIN(H{r}*I{r},D{r}))', a.get("gasto_dias_anexo")),       # J Gasto auditor (días)
            fx(f'IF({AUX}E{r}="","",{PAR["corte"]}-{AUX}E{r}+1)', a.get("dias_acum")),  # K Días acumulados
            fx(f'IF(OR(H{r}="",E{r}=""),"",MIN(H{r}*MIN(K{r},E{r}*{DIAS_ANIO_VIDA}),D{r}))', a.get("acum_dias_anexo")),  # L Dep. acum. auditor
            fx(f"{DEP}F{r}", a["dreg"]),                                                # M Gasto cliente (04)
            fx(f"{DEP}N{r}", a.get("acum_cliente")),                                    # N Dep. acum. cliente (04)
            fx(f'IF(OR(J{r}="",M{r}=""),"",J{r}-M{r})', a.get("dif_gasto_dias")),       # O Dif. gasto
            fx(f'IF(OR(L{r}="",N{r}=""),"",L{r}-N{r})', a.get("dif_acum_dias")),        # P Dif. dep. acum.
            fx(f'IF(E{r}="","",100/E{r})', (100.0 / a["vida_anios_anexo"]) if a.get("vida_anios_anexo") else None),  # Q % dep. cliente
            fx(f'IF(F{r}="","",100/F{r})', (100.0 / a["vida_anios_sri"]) if a.get("vida_anios_sri") else None),      # R % dep. SRI
            fx(f"{FIS}F{r}", a.get("dep_fiscal")),                                      # S Gasto SRI (fiscal, 04 Art. 28)
            fx(f"{DEP}J{r}", a.get("nbv")),                                             # T Valor NIIF (VNL)
        ])
    _sg = lambda k: sum(a.get(k) or 0 for a in A)
    total_comp = ["TOTAL", "", suma("C", fin(n), sum(a["costo"] for a in A)), None, None, None, None, None, None,
                  suma("J", fin(n), _sg("gasto_dias_anexo")), None, suma("L", fin(n), _sg("acum_dias_anexo")),
                  suma("M", fin(n), _sg("dreg")), suma("N", fin(n), _sg("acum_cliente")),
                  suma("O", fin(n), _sg("dif_gasto_dias")), suma("P", fin(n), _sg("dif_acum_dias")),
                  None, None, suma("S", fin(n), sum(a.get("dep_fiscal") or 0 for a in A)),
                  suma("T", fin(n), sum(a.get("nbv") or 0 for a in A if a.get("nbv") is not None))] if n else None
    ex_comp21 = {
        "Código": "Código del activo en el anexo del cliente (hoja 03), para rastrear cada cálculo hasta su origen.",
        "Clase": "Clase o grupo del activo según el anexo del cliente; determina la vida útil por rubro.",
        "Costo": "Costo del activo traído de la hoja 04 (Recálculo de depreciación y VNL): base del cálculo.",
        "Valor a depreciar": "Costo menos el valor residual (base depreciable según el criterio NIIF, NIC 16.53).",
        "Vida anexo (años)": "Vida útil del anexo del cliente (o la confirmada por el auditor para la clase).",
        "Vida SRI (años)": "Vida útil tributaria: 1 ÷ tasa máxima del SRI (Art. 28), para contrastar.",
        "Vida política (años)": "Vida útil que fija la política contable del cliente para el rubro (extraída de la política, si se cargó).",
        "Dep. diaria (anexo)": "Valor a depreciar ÷ (vida en años × 365): depreciación por día, como en el papel de trabajo.",
        "Días gasto": "Días que el activo estuvo en uso dentro del ejercicio (del inicio o la activación, hasta el corte o la baja).",
        "Gasto auditor (días)": "Depreciación diaria × días del período: gasto recalculado por el auditor por el método de días.",
        "Días acumulados": "Días desde que el activo quedó disponible para uso hasta el corte (topados por la vida útil).",
        "Dep. acum. auditor (días)": "Depreciación diaria × días acumulados: depreciación acumulada recalculada por el auditor.",
        "Gasto cliente": "Depreciación del año registrada por el cliente (anexo).",
        "Dep. acum. cliente": "Depreciación acumulada del cliente al corte (del anexo; si no viene, apertura + gasto del año).",
        "Dif. gasto": "Gasto del auditor (días) menos el del cliente.",
        "Dif. dep. acum.": "Depreciación acumulada del auditor (días) menos la del cliente.",
        "% dep. cliente": "Porcentaje anual implícito del cliente: 100 ÷ vida útil del anexo (en años).",
        "% dep. SRI": "Porcentaje anual máximo del SRI (Art. 28): 100 ÷ vida tributaria (inmuebles 5 %, maquinaria/muebles 10 %, vehículos 20 %, cómputo 33,33 %).",
        "Gasto SRI (fiscal)": "Depreciación fiscal del período según el SRI (hoja 20): base deducible × tasa × días/365, con el tope de USD 35.000 en vehículos.",
        "Valor NIIF (VNL)": "Valor neto en libros NIIF al corte (hoja 04): costo − depreciación acumulada recalculada − deterioro.",
    }

    # 22 · guía comparativa NIIF vs SRI (totales por criterio) para orientar al auditor y al cliente.
    _dsum = lambda k: sum(a[k] for a in A if a.get(k) is not None)
    guia = [
        ["Gasto de depreciación del período", fx("", _dsum("dep")),
         fx("", _sg("gasto_dias_anexo")), fx("", _sg("gasto_dias_sri")), fx("", _sg("gasto_dias_pol")), fx("", _sg("dreg"))],
        ["Depreciación acumulada al corte", fx("", _dsum("acum")),
         fx("", _sg("acum_dias_anexo")), fx("", _sg("acum_dias_sri")), fx("", _sg("acum_dias_pol")), fx("", _sg("acum_cliente"))],
    ]
    ex_guia = {
        "Concepto": "Comparación de la depreciación bajo cada criterio para orientar la decisión; no sustituye el ajuste contable (cédula 15).",
        "NIIF (meses)": "Recálculo NIIF por meses con la vida útil del anexo/clase (cédula 04).",
        "NIIF (días)": "Recálculo NIIF por días con la vida útil del anexo/clase (método del papel de trabajo).",
        "SRI (días)": "Recálculo con la vida útil tributaria máxima del SRI (Art. 28), por días.",
        "Política (días)": "Recálculo con la vida útil que fija la política contable del cliente (si se cargó la política).",
        "Cliente": "Cifras registradas por el cliente en el anexo.",
    }

    # 23 · sumaria de cuentas (variaciones del balance).
    VAR = d.get("variaciones") or []
    sumaria = [[v["cuenta"], v["desc"], v["tipo"], v["ant"], v["act"], fx(f"E{FILA0+i}-D{FILA0+i}", v["var"])]
               for i, v in enumerate(VAR)]
    nv = len(VAR)
    total_sumaria = ["TOTAL", "", "", suma("D", FILA0 + max(nv, 1) - 1, sum(v["ant"] for v in VAR)),
                     suma("E", FILA0 + max(nv, 1) - 1, sum(v["act"] for v in VAR)),
                     suma("F", FILA0 + max(nv, 1) - 1, sum(v["var"] for v in VAR))] if nv else None
    ex_sumaria = {
        "Cuenta": "Cuenta contable del balance.", "Tipo": "Clasificación por su descripción: costo (saldo deudor) o depreciación acumulada (saldo acreedor).",
        "Saldo año anterior": "Saldo de la cuenta al cierre del ejercicio anterior, según el balance del cliente.",
        "Saldo al corte": "Saldo de la cuenta a la fecha de corte del encargo, según el balance del cliente.",
        "Variación": "Saldo al corte menos el del año anterior: base del análisis del movimiento del período.",
    }

    # 24 · movimiento del período (libro mayor), agregado por cuenta.
    MAY = d.get("mayor") or []
    movim = [[e["cuenta"], e["desc"], fx("", e["debe"]), fx("", e["haber"]),
              fx(f"C{FILA0+i}-D{FILA0+i}", e["neto"]), fx("", e["n"])] for i, e in enumerate(MAY)]
    nm = len(MAY)
    total_mov = ["TOTAL", "", suma("C", FILA0 + max(nm, 1) - 1, sum(e["debe"] for e in MAY)),
                 suma("D", FILA0 + max(nm, 1) - 1, sum(e["haber"] for e in MAY)),
                 suma("E", FILA0 + max(nm, 1) - 1, sum(e["neto"] for e in MAY)),
                 suma("F", FILA0 + max(nm, 1) - 1, sum(e["n"] for e in MAY))] if nm else None
    ex_mov = {
        "Cuenta": "Cuenta contable del libro mayor.", "Débitos": "Suma de los cargos del período (altas y aumentos).",
        "Créditos": "Suma de los abonos del período (bajas, depreciación y ajustes).",
        "Movimiento neto": "Débitos menos créditos del período: aumento (si es positivo) o disminución del saldo de la cuenta.",
        "N° asientos": "Cantidad de movimientos (asientos) registrados en la cuenta durante el período.",
    }

    # 25 · conciliación de saldos: auxiliar (anexo) vs balance (sumaria).
    co = d.get("conciliacion") or {}
    concil_rows = []
    def _concil_fila(concepto, aux, bal, dif):
        r = FILA0 + len(concil_rows)
        concil_rows.append([concepto, fx("", aux), fx("", bal), fx(f'IF(OR(B{r}="",C{r}=""),"",B{r}-C{r})', dif)])
    if co.get("costo_bal") is not None:
        _concil_fila("Costo", co["costo_aux"], co["costo_bal"], co["dif_costo"])
    if co.get("dep_bal") is not None:
        _concil_fila("Depreciación acumulada", co["dep_aux"], co["dep_bal"], co["dif_dep"])
    ex_concil = {
        "Concepto": "Saldo conciliado: costo o depreciación acumulada.",
        "Auxiliar": "Saldo al corte según el anexo de activos fijos.",
        "Balance": "Saldo al corte según la sumaria del balance (variaciones).",
        "Diferencia": "Auxiliar menos balance; fuera de tolerancia se reporta como hallazgo.",
    }

    # 26 · vaucheo de facturas (extraídas por IA de los PDF) contra las adiciones y las bajas.
    VCH = d.get("vaucheo") or []
    vauch_rows = [[v["tipo"], v["cod"], v["prov"], v["ruc"], v["fecha"], v["num"],
                   fx("", v["total"]), fx("", v["reg"]),
                   fx(f'IF(OR(G{FILA0+i}="",H{FILA0+i}=""),"",G{FILA0+i}-H{FILA0+i})', v["dif"]), v["estado"]]
                  for i, v in enumerate(VCH)]
    ex_vauch = {
        "Tipo": "Adición (factura de compra) o Baja (factura de venta).",
        "Código del activo": "Código del activo relacionado en el anexo, para cruzar con el detalle.",
        "Proveedor / Cliente": "Razón social del proveedor (en una compra) o del cliente/adquirente (en una venta), "
                               "extraída del RIDE; sirve para cotejarla contra el tercero del libro mayor.",
        "RUC": "R.U.C. o identificación de la contraparte, extraído del RIDE; permite confirmar que la compra o "
               "venta registrada en el mayor corresponde a ese tercero.",
        "Fecha": "Fecha de emisión de la factura; debe caer en el período y cruzar con la fecha del asiento en el mayor.",
        "N° factura": "Secuencial completo del comprobante (estab-ptoEmisión-secuencial); se cruza con el N° de "
                      "documento del movimiento en el libro mayor.",
        "Total": "Subtotal sin IVA de la factura extraído del PDF (revíselo: la IA solo transcribe lo que leyó).",
        "Registrado en libros": "Importe de la adición (detalle) o de la baja (producto de la venta) que cruza por código.",
        "Diferencia": "Total de la factura menos lo registrado; fuera de tolerancia se reporta como hallazgo.",
        "Estado": "Conciliado, Diferencia o Sin registro en libros.",
    }

    # 27 · resumen de hallazgos por categoría (consolida la cédula 16 para una lectura ejecutiva).
    cat = {}
    for e in res["exceptions"]:
        k = _categoria_hallazgo(e.get("code"))
        g = cat.setdefault(k, {"n": 0, "imp": 0.0})
        g["n"] += 1
        g["imp"] += abs(float(e.get("amount") or 0))
    _hz = sorted(cat.items(), key=lambda kv: (-kv[1]["imp"], kv[0]))
    resumen_hz = [[k, fx("", v["n"]), fx("", v["imp"])] for k, v in _hz]
    nhz = len(resumen_hz)
    total_hz = ["TOTAL", suma("B", FILA0 + max(nhz, 1) - 1, sum(v["n"] for v in cat.values())),
                suma("C", FILA0 + max(nhz, 1) - 1, sum(v["imp"] for v in cat.values()))] if nhz else None
    ex_hz = {
        "Categoría": "Agrupa los hallazgos de la cédula 16 por tema de auditoría.",
        "N° de hallazgos": "Cantidad de hallazgos (excepciones) detectados en esa categoría de auditoría.",
        "Importe (valor absoluto)": "Suma del valor absoluto de los importes de los hallazgos de la categoría.",
    }

    _todas = [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen, explica=ex_resumen),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros, explica=ex_par),
        hoja("03_Auxiliar", "Auxiliar de activos (datos del cliente)",
             [["Código", "t"], ["Descripción", "t"], ["Clase", "t"], ["Elemento", "t"], ["Disponible para uso", "d"], ["Costo inicial", "n"],
              ["Adiciones", "n"], ["Valor residual", "n"], ["Vida útil (meses)", "i"], ["Método", "t"], ["Dep. acum. inicial", "n"],
              ["Dep. del año registrada", "n"], ["Deterioro acumulado", "n"], ["Importe recuperable", "n"], ["Valor revaluado", "n"],
              ["Superávit previo", "n"], ["Decremento previo en resultados", "n"], ["Fecha de baja", "d"], ["Producto de la baja", "n"],
              ["Resultado de baja registrado", "n"]], aux),
        hoja("04_Depreciacion", "Recálculo de depreciación y VNL",
             [["Código", "t"], ["Costo", "n"], ["Importe depreciable", "n"], ["Días en uso", "i"], ["Depreciación recalculada", "n"],
              ["Depreciación registrada", "n"], ["Diferencia", "n"], ["Dep. acumulada recalculada", "n"], ["Deterioro acumulado", "n"],
              ["Valor neto en libros", "n"], ["Totalmente depreciado", "t"], ["Estado", "t"], ["Semáforo", "t"],
              ["Dep. acumulada cliente", "n"], ["Dif. dep. acumulada", "n"]], dep,
             ["TOTAL", suma("B", fin(n), sum(a["costo"] for a in A)), None, None, suma("E", fin(n), valor["depRecalculada"]),
              suma("F", fin(n), rf["dreg"]), suma("G", fin(n), aj["ajusteDep"]), None, None, None, "", "", "",
              suma("N", fin(n), sum((a["dai"] or 0) + (a["dreg"] or 0) for a in A)),
              suma("O", fin(n), sum(a["acum"] - ((a["dai"] or 0) + (a["dreg"] or 0)) for a in A if a["acum"] is not None))],
             explica=ex_dep, colores=["Semáforo"]),
        hoja("05_Vidas_residual", "Vidas útiles, residual y método",
             [["Código", "t"], ["Clase", "t"], ["Método", "t"], ["Vida útil (meses)", "i"], ["Valor residual", "n"], ["Costo", "n"],
              ["Residual % del costo", "p"], ["Dep. acumulada recalculada", "n"], ["Vida remanente (meses)", "n"],
              ["Totalmente depreciado en uso", "t"], ["Residual mayor que el costo", "t"]], vidas, explica=ex_vidas),
        hoja("06_Componentes", "Componentes",
             [["Código", "t"], ["Elemento", "t"], ["Costo de la parte", "n"], ["Costo del elemento", "n"], ["% del elemento", "p"],
              ["Parte significativa", "t"], ["Vida útil (meses)", "i"], ["Método", "t"]], componentes, explica=ex_comp),
        hoja("07_Bajas", "Bajas",
             [["Código", "t"], ["Fecha de baja", "d"], ["Costo", "n"], ["Dep. acumulada a la baja", "n"], ["Deterioro", "n"],
              ["VNL a la baja", "n"], ["Producto", "n"], ["Resultado recalculado", "n"], ["Resultado registrado", "n"], ["Diferencia", "n"]], bajas,
             ["TOTAL", "", None, None, None, None, None, None, None, suma("J", fin(len(B)), aj["ajusteBajas"])] if B else None, explica=ex_bajas),
        hoja("08_Revaluacion", "Revaluación",
             [["Código", "t"], ["Clase", "t"], ["VNL al corte", "n"], ["Valor revaluado", "n"], ["Diferencia", "n"], ["Superávit previo", "n"],
              ["Decremento previo en resultados", "n"], ["A otro resultado integral", "n"], ["A resultados", "n"]], revs,
             ["TOTAL", "", None, None, None, None, None, suma("H", fin(len(R)), aj["revaluacionORI"]),
              suma("I", fin(len(R)), aj["revaluacionResultado"])] if R else None, explica=ex_rev),
        hoja("09_Deterioro", "Deterioro",
             [["Código", "t"], ["Clase", "t"], ["Importe en libros", "n"], ["Importe recuperable", "n"], ["Pérdida adicional", "n"],
              ["Superávit previo", "n"], ["Revaluación del año a ORI", "n"], ["Superávit disponible", "n"],
              ["Contra el superávit (ORI)", "n"], ["A resultados", "n"]], deter,
             ["TOTAL", "", None, None, suma("E", fin(len(D)), aj["deterioroAdicional"]), None, None, None,
              suma("I", fin(len(D)), aj["deterioroORI"]), suma("J", fin(len(D)), aj["deterioroResultado"])] if D else None, explica=ex_det),
        hoja("10_Adiciones", "Adiciones y costos por préstamos",
             [["Documento", "t"], ["Activo", "t"], ["Fecha", "d"], ["Descripción", "t"], ["Tipo", "t"], ["Importe", "n"], ["Apto", "t"],
              ["Intereses capitalizados", "n"], ["Días de capitalización", "i"], ["Intereses capitalizables", "n"], ["Diferencia", "n"],
              ["Capitalizable", "t"]], adic,
             ["TOTAL", "", "", "", "", suma("F", fin(nad), rf["adDetalle"] or 0), "", suma("H", fin(nad), sum(x["int"] or 0 for x in AD)), None,
              None, suma("K", fin(nad), 0 if npr else aj["ajusteIntereses"]), ""] if nad else None, explica=ex_adic),
        hoja("11_Prestamos", "Préstamos para la construcción",
             [["Préstamo", "t"], ["Tipo", "t"], ["Activo u obra", "t"], ["Descripción", "t"], ["Importe del préstamo", "n"],
              ["Tasa nominal anual (%)", "n"], ["Costo financiero del período", "n"], ["(−) Rendimientos de la inversión temporal", "n"],
              ["Capitalizable del específico (NIC 23.12)", "n"]], prest,
             ["TOTAL", "", "", "", suma("E", fin(npr), sum(y["importe"] or 0 for y in PRS)), None,
              suma("G", fin(npr), d["tope"]["incurridos"]), suma("H", fin(npr), sum(y["rend"] or 0 for y in PRS)),
              suma("I", fin(npr), sum(y["cap_esp"] for y in PRS if y["cap_esp"] is not None))] if npr else None, explica=ex_pre),
        hoja("12_Capitalizacion", "Capitalización de costos por préstamos por activo",
             [["Activo", "t"], ["Desembolsos aptos del período", "n"], ["Base ponderada por tiempo", "n"],
              ["Préstamo específico: importe", "n"], ["Capitalizable del específico (NIC 23.12)", "n"],
              ["% financiado con préstamos generales", "p"], ["Base financiada con generales", "n"],
              ["Tasa de capitalización (NIC 23.14)", "p"], ["Capitalizable de los generales", "n"],
              ["Capitalizable antes del tope", "n"], ["Factor del tope (NIC 23.14)", "p"], ["Capitalizable del período", "n"],
              ["Intereses capitalizados registrados", "n"], ["Diferencia", "n"]], capit,
             ["TOTAL", suma("B", fin(ncap), sc("desemb")), suma("C", fin(ncap), sc("base")), suma("D", fin(ncap), sc("esp_imp")),
              suma("E", fin(ncap), sc("esp_cap")), None, suma("G", fin(ncap), sc("base_gen")), None,
              suma("I", fin(ncap), sc("cap_gen")), suma("J", fin(ncap), sc("antes")), None,
              suma("L", fin(ncap), sc("final")), suma("M", fin(ncap), sc("reg")), suma("N", fin(ncap), sc("dif"))] if ncap else None,
             explica=ex_cap),
        hoja("13_Desmantelamiento", "Desmantelamiento", [["Concepto", "t"], ["Importe", "n"]], desm, explica=ex_desm,
             estilos=estilos_desm),
        hoja("14_Roll_forward", "Movimiento del año y conciliación auxiliar-mayor", [["Concepto", "t"], ["Importe", "n"]], rfw, explica=ex_rf,
             estilos=estilos_rfw),
        hoja("15_Ajustes", "Ajustes propuestos", [["Ajuste", "t"], ["Importe", "n"], ["Débito (si positivo)", "t"], ["Crédito (si positivo)", "t"], ["Base", "t"]], ajus, explica=ex_aj,
             estilos=estilos_ajus),
        hoja("16_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], float(e["amount"])] for e in res["exceptions"]]),
        hoja("17_Conclusion", "Indicadores y conclusión",
             [["Indicador", "t"], ["Importe", "n"], ["Porcentaje", "p"], ["Cantidad", "i"], ["Estado", "t"]], conclusion,
             explica=ex_conclusion, colores=["Estado"]),
        hoja("18_Lectura", "Lectura de resultados", [["Concepto", "t"], ["Detalle", "t"]], lectura, explica=ex_lectura),
        hoja("19_Resumen_estado", "Resumen por estado del activo",
             [["Estado", "t"], ["Cantidad", "i"], ["Costo", "n"], ["Depreciación acumulada", "n"], ["Valor neto en libros", "n"]],
             resumen_estado, total_estado, explica=ex_estado),
        hoja("20_Fiscal", "Recálculo fiscal (SRI Art. 28) y conciliación NIIF",
             [["Código", "t"], ["Clase", "t"], ["Costo", "n"], ["Tasa fiscal máx. (SRI)", "p"], ["Base deducible", "n"],
              ["Dep. fiscal del año", "n"], ["Dep. NIIF del año", "n"], ["Diferencia NIIF − fiscal", "n"],
              ["Exceso vehículo no deducible", "n"], ["Observación", "t"]], fiscal,
             ["TOTAL", "", suma("C", fin(n), sum(a["costo"] for a in A)), None,
              suma("E", fin(n), sum(a["base_fiscal"] for a in A if a.get("base_fiscal") is not None)),
              suma("F", fin(n), sum(a["dep_fiscal"] for a in A if a.get("dep_fiscal") is not None)),
              suma("G", fin(n), sum(a["dep"] for a in A if a["dep"] is not None)),
              suma("H", fin(n), sum(a["dif_fiscal"] for a in A if a.get("dif_fiscal") is not None)),
              suma("I", fin(n), sum(a.get("exceso_veh") or 0 for a in A)), ""],
             explica=ex_fiscal),
        hoja("21_Comparativo", "Recálculo de depreciación (cliente · auditor · SRI · NIIF)",
             [["Código", "t"], ["Clase", "t"], ["Costo", "n"], ["Valor a depreciar", "n"], ["Vida anexo (años)", "n"],
              ["Vida SRI (años)", "n"], ["Vida política (años)", "n"], ["Dep. diaria (anexo)", "n"], ["Días gasto", "i"],
              ["Gasto auditor (días)", "n"], ["Días acumulados", "i"], ["Dep. acum. auditor (días)", "n"], ["Gasto cliente", "n"],
              ["Dep. acum. cliente", "n"], ["Dif. gasto", "n"], ["Dif. dep. acum.", "n"],
              ["% dep. cliente", "n"], ["% dep. SRI", "n"], ["Gasto SRI (fiscal)", "n"], ["Valor NIIF (VNL)", "n"]],
             comparativo, total_comp, explica=ex_comp21),
        hoja("22_Guia_NIIF_SRI", "Guía comparativa NIIF vs SRI",
             [["Concepto", "t"], ["NIIF (meses)", "n"], ["NIIF (días)", "n"], ["SRI (días)", "n"], ["Política (días)", "n"], ["Cliente", "n"]],
             guia, explica=ex_guia),
        hoja("23_Sumaria", "Sumaria de cuentas (variaciones del balance)",
             [["Cuenta", "t"], ["Descripción", "t"], ["Tipo", "t"], ["Saldo año anterior", "n"], ["Saldo al corte", "n"], ["Variación", "n"]],
             sumaria, total_sumaria, explica=ex_sumaria),
        hoja("24_Movimiento_mayor", "Movimiento del período (libro mayor)",
             [["Cuenta", "t"], ["Descripción", "t"], ["Débitos", "n"], ["Créditos", "n"], ["Movimiento neto", "n"], ["N° asientos", "i"]],
             movim, total_mov, explica=ex_mov),
        hoja("25_Conciliacion", "Conciliación de saldos (auxiliar vs balance)",
             [["Concepto", "t"], ["Auxiliar", "n"], ["Balance", "n"], ["Diferencia", "n"]],
             concil_rows, explica=ex_concil),
        hoja("26_Vaucheo", "Vaucheo de facturas (adiciones y bajas)",
             [["Tipo", "t"], ["Código del activo", "t"], ["Proveedor / Cliente", "t"], ["RUC", "t"], ["Fecha", "d"],
              ["N° factura", "t"], ["Total", "n"], ["Registrado en libros", "n"], ["Diferencia", "n"], ["Estado", "t"]],
             vauch_rows, explica=ex_vauch, colores=["Estado"]),
        hoja("27_Resumen_hallazgos", "Resumen de hallazgos por categoría",
             [["Categoría", "t"], ["N° de hallazgos", "i"], ["Importe (valor absoluto)", "n"]],
             resumen_hz, total_hz, explica=ex_hz),
    ]
    # Cédulas de análisis que solo se muestran cuando el cliente tiene ese hecho económico: si la empresa no tuvo
    # bajas, revaluación, deterioro, adiciones, préstamos, capitalización, componentes ni desmantelamiento, esas
    # pestañas no aparecen (el papel se queda con las cédulas que aplican a los datos cargados).
    _mostrar = {
        "06_Componentes": bool(componentes),
        "07_Bajas": bool(B),
        "08_Revaluacion": bool(R),
        "09_Deterioro": bool(D),
        "10_Adiciones": bool(nad),
        "11_Prestamos": bool(npr),
        "12_Capitalizacion": bool(ncap),
        "13_Desmantelamiento": ds.get("costo") is not None,
    }
    # Orden de presentación del papel de trabajo: primero las cédulas de trabajo del auditor en el flujo que sigue
    # el auditor (sumaria desde variaciones → conciliación → recálculo de depreciación → cédulas de análisis que
    # apliquen → movimiento del mayor → vaucheo → hallazgos); luego el soporte y el diagnóstico (que viajan OCULTOS
    # cuando la prueba declara `hojas_visibles`, pero se conservan porque el recálculo y el tablero los referencian).
    _ORDEN = ["23_Sumaria", "25_Conciliacion", "21_Comparativo",
              "06_Componentes", "07_Bajas", "08_Revaluacion", "09_Deterioro", "10_Adiciones",
              "11_Prestamos", "12_Capitalizacion", "13_Desmantelamiento",
              "24_Movimiento_mayor", "26_Vaucheo", "16_Problemas",
              "01_Resumen", "05_Vidas_residual", "20_Fiscal", "22_Guia_NIIF_SRI", "14_Roll_forward",
              "03_Auxiliar", "04_Depreciacion", "02_Parametros", "15_Ajustes",
              "17_Conclusion", "18_Lectura", "19_Resumen_estado", "27_Resumen_hallazgos"]
    _idx = {n: i for i, n in enumerate(_ORDEN)}
    visibles = [h for h in _todas if _mostrar.get(h["name"], True)]
    return sorted(visibles, key=lambda h: _idx.get(h["name"], 999))


# --- definición -------------------------------------------------------------------

def definicion() -> dict:
    aux = ("Una fila por activo o componente: código, descripción, clase, elemento (si es parte), fecha disponible para uso, "
           "costo inicial, adiciones, residual, vida útil en meses, método, depreciación acumulada inicial, depreciación del año "
           "registrada, deterioro acumulado; si aplica: importe recuperable, valor revaluado, superávit previo, fecha y producto de la baja "
           "y resultado registrado. Sin filas de total.")
    return {
        "name": "Propiedad, planta y equipo",
        "area": "Propiedad, planta y equipo",
        "processor": "ppe_propiedad_planta",
        # El papel de trabajo muestra solo las cédulas del flujo del auditor; las demás (resumen, parámetros,
        # auxiliar, vidas, fiscal, guía, roll-forward, ajustes, conclusión, lectura, resumen por estado y de
        # hallazgos, además de carátula/base técnica/anexo y cierre) viajan OCULTAS —no borradas— porque el
        # recálculo y el tablero las referencian por fórmula (ocultar evita romper con #REF!). «Procedimiento» es
        # 00_Programa. Las cédulas de análisis (bajas, revaluación, deterioro, adiciones, préstamos,
        # capitalización) solo existen —y por tanto solo se ven— cuando el cliente tiene ese hecho económico.
        "hojas_visibles": ["00_Programa", "23_Sumaria", "25_Conciliacion", "21_Comparativo",
                           "06_Componentes", "07_Bajas", "08_Revaluacion", "09_Deterioro", "10_Adiciones",
                           "11_Prestamos", "12_Capitalizacion", "24_Movimiento_mayor", "26_Vaucheo", "16_Problemas"],
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Recalcula por activo la depreciación, el valor neto en libros y el resultado de las bajas; evalúa vidas útiles, "
                    "residuales, componentes, revaluación, deterioro y la provisión de desmantelamiento; con el anexo de préstamos separa los "
                    "específicos (costo real menos los rendimientos de la inversión temporal) de los generales (tasa de capitalización) y aplica "
                    "el tope de los costos incurridos (NIC 23.12 y 14; en PYMES todo es gasto, Sección 25.2), y concilia el auxiliar con el mayor."),
        "source": {"organization": "IFRS Foundation — traducción oficial al español (NIIF 2023)", "type": "Norma contable", "date": "2026-09-22",
                   "document": ("NIC 16 párr. 12, 16 c, 31–42 (39, 40), 43–47, 50–62, 67–72; NIC 23 párr. 8, 12, 14, 20, 22; "
                                "NIC 36 párr. 18, 59–60; NIC 37 párr. 45, 47, 60; CINIIF 1 párr. 5 y 8"),
                   "url": "https://www.ifrs.org/content/dam/ifrs/publications/html-standards/spanish/2023/issued/ias16.html"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015 y 2025: Sección 17 (17.6, 17.10 c, 17.15–17.15D revaluación, 17.16 componentes, "
                                      "17.18–17.23 depreciación, 17.27–17.30 bajas), Sección 25 (25.2: costos por préstamos a gasto), "
                                      "Sección 27 (27.5–27.6 deterioro), Sección 21 (21.7 b desmantelamiento, 21.11 reversión del descuento); "
                                      "17.15 (mantenimiento diario a gasto). Numeración verificada en las ediciones 2015 y 2025."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 500", "section": "párr. 6–9", "requirement": "Evidencia suficiente y adecuada sobre existencia, integridad y valoración del auxiliar."},
            {"document": "NIA 510", "section": "párr. 6", "requirement": "Saldos iniciales: el costo y la depreciación acumulada iniciales se concilian con el cierre anterior; aplica en encargos iniciales; en recurrentes NIA 500/330."},
            {"document": "NIA 540 (Revisada)", "section": "párr. 13–30 y 32", "requirement": "Estimaciones: vidas útiles, residuales, importe recuperable, valor razonable y desmantelamiento."},
            {"document": "NIA 500", "section": "párr. A18 y A20", "requirement": "Inspección física de activos tangibles."},
            {"document": "NIA 500", "section": "párr. 8", "requirement": "Perito de la dirección (NIA 620 solo si lo contrata el auditor): evaluar su trabajo en revaluaciones y deterioro."},
        ],
        "calculo": [
            "Costo = costo inicial + adiciones del año; importe depreciable = costo − valor residual (NIC 16.53; PYMES 17.18).",
            "Depreciación lineal del período = importe depreciable ÷ vida útil (meses) × 12 × días en uso ÷ días del año, sin pasar del importe pendiente (NIC 16.50, 55; PYMES 17.20).",
            "Valor neto en libros = costo − depreciación acumulada − deterioro acumulado.",
            "Baja: ganancia o pérdida = producto − valor neto en libros a la fecha de baja (NIC 16.71; PYMES 17.30).",
            "Revaluación al corte: el aumento va a resultados hasta revertir el decremento previo del mismo activo reconocido en resultados y el resto a "
            "ORI (NIC 16.39; PYMES 17.15C); la disminución va a ORI hasta el superávit previo y el resto a resultados (NIC 16.40; PYMES 17.15D).",
            "Deterioro: pérdida = max(importe en libros − importe recuperable, 0) (NIC 36.59; PYMES 27.5). En activos revaluados, la pérdida va contra el "
            "superávit de ese activo (superávit previo + revaluación del año a ORI) y solo el exceso a resultados (NIC 36.60–61; PYMES 27.6).",
            "Costos por préstamos con el anexo de préstamos (solo NIIF completas): por activo, capitalizable = (costo financiero del período realmente "
            "incurrido en el préstamo específico − rendimientos de la inversión temporal de esos fondos, NIC 23.12) + (tasa de capitalización de los "
            "préstamos generales × desembolsos del activo financiados con ellos, NIC 23.14). La tasa de capitalización es la media ponderada de los costos "
            "por intereses de los préstamos genéricos (costo del período ÷ importe). Los desembolsos financiados con generales son los desembolsos aptos del "
            "activo ponderados por los días del período, por la proporción no cubierta por el préstamo específico = máx(1 − importe del específico ÷ "
            "desembolsos aptos, 0). Tope: lo capitalizado en el período no excede los costos por préstamos incurridos (NIC 23.14, última frase); si excede, "
            "se prorratea entre los activos.",
            "Costos por préstamos sin el anexo (estimación de respaldo): desembolso × tasa de capitalización del parámetro × días ÷ días del año (NIC 23.14), "
            "y se avisa que falta el anexo. En NIIF para las PYMES todo costo por préstamos es gasto del período (Sección 25.2, ediciones 2015 y 2025): no se "
            "capitaliza nada y lo capitalizado por el cliente es ajuste.",
            "Desmantelamiento: valor presente = costo estimado ÷ (1 + tasa)^años (NIC 37.45–47; PYMES 21.7 b). Ajuste total = valor presente − provisión "
            "registrada al cierre; de él, la actualización financiera del período = provisión al inicio × tasa va a resultados como costo financiero "
            "(CINIIF 1.8; NIC 37.60; PYMES 21.11) y el resto es cambio de estimación contra el costo del activo (CINIIF 1.5 a).",
            "Movimiento del año: costo y depreciación acumulada inicial + movimientos − bajas = cierre, conciliado con el mayor.",
        ],
        "fields": _ACTIVOS, "rules": [], "control": CONTROL, "primary": "ajusteResultado",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[a, b] for a, b in CEDULAS],
        "program": [
            {"code": "PPE-01", "objective": "Conciliación auxiliar-mayor", "risk": "Auxiliar incompleto o distinto del mayor", "assertion": "Integridad",
             "procedure": "Movimiento del año del costo y la depreciación acumulada y conciliación con el mayor", "evidence": "Auxiliar y mayor",
             "criterion": "Diferencia dentro de tolerancia o explicada", "source": "NIA 500 · NIA 510"},
            {"code": "PPE-02", "objective": "Adiciones", "risk": "Gastos capitalizados o adiciones sin soporte", "assertion": "Existencia / Clasificación",
             "procedure": "Examinar las adiciones y separar capital de gasto (reparación y mantenimiento)", "evidence": "Facturas, contratos, actas de recepción",
             "criterion": "Solo costos que cumplen NIC 16.7 y 16.16", "source": "NIC 16.12, 16 · PYMES 17.6, 17.10, 17.15"},
            {"code": "PPE-03", "objective": "Depreciación", "risk": "Depreciación mal calculada", "assertion": "Valoración",
             "procedure": "Recalcular la depreciación por activo desde la fecha disponible para uso", "evidence": "Auxiliar",
             "criterion": "Diferencias dentro de tolerancia", "source": "NIC 16.50–62 · PYMES 17.18–17.23"},
            {"code": "PPE-04", "objective": "Vidas útiles, residual, método y componentes", "risk": "Estimaciones desactualizadas; partes significativas sin separar", "assertion": "Valoración",
             "procedure": "Revisar activos totalmente depreciados en uso, residuales y partes significativas", "evidence": "Política contable, informes técnicos",
             "criterion": "NIIF: revisadas al cierre (NIC 16.51, 61); PYMES: si hay indicios (17.19)", "source": "NIC 16.43–47, 51, 61 · PYMES 17.16, 17.19"},
            {"code": "PPE-05", "objective": "Bajas", "risk": "Resultado de baja mal calculado u omitido", "assertion": "Exactitud",
             "procedure": "Recalcular el valor neto en libros a la baja y la ganancia o pérdida", "evidence": "Facturas de venta, actas de baja",
             "criterion": "Resultado recalculado igual al registrado", "source": "NIC 16.67–72 · PYMES 17.27–17.30"},
            {"code": "PPE-06", "objective": "Revaluación", "risk": "Superávit mal medido o clase incompleta", "assertion": "Valoración",
             "procedure": "Comparar el valor revaluado con el VNL y distribuir entre ORI y resultados", "evidence": "Informe del perito",
             "criterion": "Tratamiento según NIC 16.39–40", "source": "NIC 16.31–42 · PYMES 17.15–17.15D · NIA 620"},
            {"code": "PPE-07", "objective": "Deterioro", "risk": "Importe en libros superior al recuperable", "assertion": "Valoración",
             "procedure": "Comparar el importe en libros con el importe recuperable", "evidence": "Cálculo de valor en uso o valor razonable",
             "criterion": "Pérdida reconocida", "source": "NIC 36.59–61 · PYMES 27.5–27.6 (si el activo está revaluado, primero contra el superávit) · NIA 540"},
            {"code": "PPE-08", "objective": "Costos por préstamos", "risk": "Intereses capitalizados indebidamente o por encima de los incurridos",
             "assertion": "Valoración / Clasificación",
             "procedure": "Separar préstamos específicos y generales; recalcular por activo el capitalizable (específico: costo real menos los rendimientos de la "
                          "inversión temporal; generales: tasa de capitalización) y comprobar el tope de los costos incurridos en el período (NIIF completas); en "
                          "PYMES reversar lo capitalizado",
             "evidence": "Contratos de préstamo, tablas de amortización, mayor de gasto financiero y de rendimientos de inversiones temporales",
             "criterion": "NIC 23.12, 14 (incluido el tope) / Sección 25.2", "source": "NIC 23 · PYMES 25"},
            {"code": "PPE-09", "objective": "Desmantelamiento", "risk": "Obligación no reconocida o mal medida", "assertion": "Integridad / Valoración",
             "procedure": "Recalcular el valor presente de la obligación y compararlo con la provisión", "evidence": "Contratos, permisos ambientales, estimación técnica",
             "criterion": "Provisión igual al valor presente", "source": "NIC 16.16 c · NIC 37.45–47 · CINIIF 1 · Sección 21 (21.7 b)"},
        ],
        "requests": [
            req("RQ-011", "Variaciones de las cuentas de PP&E (saldos año anterior vs corte)", "variaciones", "PPE-01",
                "Cédula sumaria: saldos por cuenta del balance y su variación",
                content="Una fila por cuenta: cuenta contable, descripción, saldo del año anterior y saldo al corte. Sin filas de total."),
            req("RQ-010", "Libro mayor de propiedad, planta y equipo", "mayor", "PPE-01",
                "Movimiento del período y conciliación auxiliar-mayor (costo y depreciación acumulada)",
                content="Una fila por movimiento: cuenta, descripción, fecha, comprobante, documento, tipo de asiento y el importe (o debe y haber). Sin filas de total."),
            req("RQ-001", "Auxiliar de propiedad, planta y equipo por activo al corte", "activos", "PPE-01", "Población a recalcular y conciliar con el mayor", content=aux),
            req("RQ-002", "Detalle de adiciones del año por documento", "adiciones", "PPE-02", "Examen de adiciones y costos por préstamos", required=False,
                content="Una fila por documento: N° de documento, código del activo, fecha, descripción, tipo, importe, activo apto (Sí/No) e intereses capitalizados."),
            req("RQ-003", "Detalle de los préstamos para la construcción del período", "prestamos", "PPE-08",
                "Separar préstamos específicos y generales y medir el capitalizable por activo", required=False,
                content="Una fila por préstamo vigente en el período: N° de préstamo o contrato, tipo (Específico o General), activo u obra financiada "
                        "(solo los específicos), descripción, importe del préstamo, tasa nominal anual, costo financiero del período realmente incurrido y, "
                        "en los específicos, los rendimientos de la inversión temporal de esos fondos. Si no hubo inversión temporal, escriba 0."),
            req("RQ-004", "Política contable de vidas útiles, residuales y métodos", "politica", "PPE-04",
                "Sustento de estimaciones (vida útil por rubro). Cárguela como tabla (Excel/CSV) o como documento (PDF/Word): del PDF/Word se lee por IA.",
                required=False, formats=("xlsx", "csv", "pdf", "docx"), use="soporte"),
            req("RQ-012", "Facturas de las adiciones del año", "facturas_adiciones", "PPE-02",
                "Vaucheo de las adiciones: cárguelas como tabla (Excel/CSV) o como facturas PDF (se leen por IA).", required=False,
                formats=("xlsx", "csv", "pdf"), use="soporte"),
            req("RQ-005", "Informe del perito de la revaluación", None, "PPE-06", "Sustento del valor revaluado", required=False, formats=("pdf",), use="soporte"),
            req("RQ-006", "Cálculo del importe recuperable (valor en uso o valor razonable)", None, "PPE-07", "Sustento del deterioro", required=False,
                formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-007", "Contratos de préstamo, tablas de amortización y mayor de rendimientos de inversiones temporales", None, "PPE-08",
                "Sustento del costo financiero incurrido, de la tasa de capitalización y de los rendimientos del párrafo 23.12", required=False,
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-008", "Estimación técnica de desmantelamiento o restauración", None, "PPE-09", "Sustento de la provisión", required=False,
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-009", "Facturas de venta y actas de baja del año", "facturas_salidas", "PPE-05",
                "Vaucheo de las bajas: cárguelas como tabla (Excel/CSV) o como facturas PDF (se leen por IA).", required=False,
                formats=("xlsx", "csv", "pdf"), use="soporte"),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


def _a(id, desc, clase, uso, ci, **x):
    return {"id": id, "descripcion": desc, "clase": clase, "fecha_uso": uso, "costo_inicial": ci, "_row": 2, **x}


def _ad(id, activo, f, imp, **x):
    return {"id": id, "activo": activo, "fecha": f, "importe": imp, "_row": 2, **x}


def _pr(id, tipo, **x):
    return {"id": id, "tipo": tipo, "_row": 2, **x}


# Ejemplo de control (M19), corte 2025-12-31, año de 365 días:
# VEH-01: (40.000 − 4.000) ÷ 60 × 12 = 7.200 recalculado vs 6.000 registrado → +1.200.
# VEH-02 (baja 30-jun): 27.000 ÷ 60 × 12 × 181 ÷ 365 = 2.677,81; VNL = 30.000 − 21.600 − 2.677,81 = 5.722,19;
#   ganancia = 9.000 − 5.722,19 = 3.277,81 vs 1.500 registrada → +1.777,81.
# MAQ-01: VNL = 120.000 − 72.000 = 48.000 vs recuperable 40.000 → deterioro 8.000.
# Costos por préstamos con el anexo (NIC 23.12 y 14), OBRA-01:
#   desembolsos aptos 150.000 + 45.000 = 195.000; base ponderada (150.000 × 305 + 45.000 × 121) ÷ 365 = 140.260,27.
#   PR-01 específico: 9.000 de costo real − 1.200 de rendimientos = 7.800 (23.12).
#   Tasa de capitalización de los generales = (32.000 + 12.000) ÷ (400.000 + 100.000) = 8,80 % (23.14).
#   Proporción financiada con generales = 1 − 120.000 ÷ 195.000 = 38,4615 %; base 53.946,26 × 8,80 % = 4.747,27.
#   Capitalizable = 7.800 + 4.747,27 = 12.547,27; costos incurridos 53.000 → el tope no muerde (factor 1).
#   Capitalizado por el cliente 9.000 → ajuste +3.547,27. En PYMES no se capitaliza nada: −9.000 (Sección 25.2).
# Desmantelamiento: 50.000 ÷ 1,06^10 = 27.919,74 no reconocido; sin provisión registrada no hay descuento que
#   revertir: actualización financiera del período 0 y los 27.919,74 son cambio de estimación al costo (CINIIF 1.5 a).
# TERR-01 revaluado sin «decremento previo en resultados»: los 60.000 quedan en ORI y se avisa (NIC 16.39).
# MAQ-01 no está revaluado: los 8.000 de deterioro van íntegros a resultados (NIC 36.60-61 no aplica).
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"_marco": MARCO_COMPLETAS, "tolerancia": 1, "tasaCapitalizacion": 8, "umbralComponente": 10,
                   "umbralRevisarComponentes": 400000, "costoDesmantelamiento": 50000, "aniosDesmantelamiento": 10,
                   "tasaDesmantelamiento": 6, "mayorCosto": 1297000, "mayorDepAcum": 253000},
    "datasets": {
        "activos": [
            _a("EDIF-01", "Edificio administrativo", "Edificios", "2015-01-01", "500000", residual="50000", vida_meses="480", metodo="Lineal",
               dep_acum_inicial="112500", dep_registrada="11250"),
            _a("TERR-01", "Terreno planta", "Terrenos", "2015-01-01", "300000", dep_registrada="0", valor_revaluado="360000"),
            _a("TERR-02", "Terreno bodega", "Terrenos", "2018-05-01", "80000", dep_registrada="0"),
            _a("VEH-01", "Camioneta 4x4", "Vehículos", "2023-07-01", "40000", residual="4000", vida_meses="60", metodo="Lineal",
               dep_acum_inicial="10800", dep_registrada="6000"),
            _a("VEH-02", "Camión de reparto", "Vehículos", "2021-01-01", "30000", residual="3000", vida_meses="60", metodo="Lineal",
               dep_acum_inicial="21600", dep_registrada="2700", fecha_baja="2025-06-30", producto_baja="9000", resultado_baja="1500"),
            _a("MAQ-01", "Línea de envasado", "Maquinaria", "2020-01-01", "120000", vida_meses="120", metodo="Lineal",
               dep_acum_inicial="60000", dep_registrada="12000", importe_recuperable="40000"),
            _a("MAQ-01-M", "Motor de la línea de envasado", "Maquinaria", "2020-01-01", "30000", elemento="MAQ-01", vida_meses="60",
               metodo="Lineal", dep_acum_inicial="30000", dep_registrada="0"),
            _a("EQC-01", "Servidores", "Equipo de cómputo", "2024-01-01", "15000", vida_meses="36", metodo="Unidades producidas",
               dep_acum_inicial="5000", dep_registrada="4000"),
            _a("OBRA-01", "Nave industrial en construcción", "Construcciones en curso", "", "0", adiciones="200000", dep_registrada="1000"),
            _a("MOB-01", "Mobiliario de oficinas", "Muebles y enseres", "2025-04-01", "0", adiciones="12000", vida_meses="120", metodo="Lineal",
               dep_registrada="904.11"),
        ],
        "adiciones": [
            _ad("AD-01", "OBRA-01", "2025-03-01", "150000", descripcion="Avance de obra 1", tipo="Capitalizable", apto="Sí", intereses="9000"),
            _ad("AD-02", "OBRA-01", "2025-09-01", "45000", descripcion="Avance de obra 2", tipo="Capitalizable", apto="Sí", intereses="0"),
            _ad("AD-03", "OBRA-01", "2025-10-15", "5000", descripcion="Cubierta provisional", tipo="Reparación", apto="No"),
            _ad("AD-04", "MOB-01", "2025-04-01", "12000", descripcion="Escritorios y sillas", tipo="Capitalizable", apto="No"),
        ],
        "prestamos": [
            _pr("PR-01", "Específico", activo="OBRA-01", descripcion="Banco del Pacífico · nave industrial", importe="120000",
                tasa="9", costo_financiero="9000", rendimientos="1200"),
            _pr("PR-02", "General", descripcion="Banco Pichincha · capital de trabajo", importe="400000", tasa="8", costo_financiero="32000"),
            _pr("PR-03", "General", descripcion="Produbanco · línea de crédito", importe="100000", tasa="12", costo_financiero="12000"),
        ],
        "variaciones": [
            {"cuenta": "12010101", "descripcion": "Edificios", "saldo_anterior": "500000", "saldo_actual": "500000", "_row": 2},
            {"cuenta": "12010102", "descripcion": "Terrenos", "saldo_anterior": "380000", "saldo_actual": "380000", "_row": 3},
            {"cuenta": "12010103", "descripcion": "Maquinaria y equipo", "saldo_anterior": "150000", "saldo_actual": "150000", "_row": 4},
            {"cuenta": "12010104", "descripcion": "Vehículos", "saldo_anterior": "70000", "saldo_actual": "40000", "_row": 5},
            {"cuenta": "12010105", "descripcion": "Equipo de cómputo", "saldo_anterior": "15000", "saldo_actual": "15000", "_row": 6},
            {"cuenta": "12010106", "descripcion": "Muebles y enseres", "saldo_anterior": "0", "saldo_actual": "12000", "_row": 7},
            {"cuenta": "12010201", "descripcion": "Depreciación acumulada", "saldo_anterior": "253000", "saldo_actual": "281000", "_row": 8},
        ],
        "mayor": [
            {"cuenta": "12010106", "descripcion": "Muebles y enseres", "fecha": "2025-04-01", "comprobante": "CMP-120", "documento": "FAC-5521",
             "tipo": "VO", "debe": "12000", "haber": "0", "importe": "12000", "_row": 2},
            {"cuenta": "12010104", "descripcion": "Vehículos", "fecha": "2025-06-30", "comprobante": "CMP-215", "documento": "ND-048",
             "tipo": "VO", "debe": "0", "haber": "30000", "importe": "-30000", "_row": 3},
            {"cuenta": "12010201", "descripcion": "Depreciación acumulada", "fecha": "2025-12-31", "comprobante": "CMP-312", "documento": "AJ-900",
             "tipo": "ADJ", "debe": "0", "haber": "28000", "importe": "-28000", "_row": 4},
        ],
    },
}

# Sin el anexo de préstamos la herramienta sigue funcionando con la tasa del parámetro y avisa (SIN_ANEXO_PRESTAMOS):
# AD-01: 150.000 × 8 % × 305 ÷ 365 = 10.027,40 y AD-02: 45.000 × 8 % × 121 ÷ 365 = 1.193,42; capitalizado 9.000 → +2.220,82.
_SIN_PRESTAMOS = {k: v for k, v in EJEMPLO["datasets"].items() if k != "prestamos"}

# El tope del párrafo 14 muerde: mismo anexo pero un solo préstamo general de 40.000 con 6.000 de costo (tasa 15 %).
#   Capitalizable de los generales = 53.946,26 × 15 % = 8.091,94; con el específico 7.800 → 15.891,94 antes del tope.
#   Costos por préstamos incurridos en el período = 9.000 + 6.000 = 15.000 → factor 15.000 ÷ 15.891,94 = 0,943876…
#   Capitalizable del período = 15.000,00 (exceso no capitalizable 891,94); capitalizado 9.000 → ajuste +6.000,00.
_PRESTAMOS_TOPE = [
    _pr("PR-01", "Específico", activo="OBRA-01", descripcion="Banco del Pacífico · nave industrial", importe="120000",
        tasa="9", costo_financiero="9000", rendimientos="1200"),
    _pr("PR-02", "General", descripcion="Banco Pichincha · capital de trabajo", importe="40000", tasa="15", costo_financiero="6000"),
]
_TOPE = {**EJEMPLO["datasets"], "prestamos": _PRESTAMOS_TOPE}

# Anexo incompleto: el específico sin rendimientos y el general sin importe → los importes quedan vacíos (M22) y
# el tope no se puede comprobar; se emiten PRESTAMO_SIN_RENDIMIENTOS, PRESTAMO_GENERAL_INCOMPLETO y TOPE_NO_VERIFICABLE.
_MIN = {"activos": [_a("V-1", "Auto", "Vehículos", "2024-01-01", "10000", vida_meses="60", dep_registrada="2000")],
        "prestamos": [_pr("PR-X", "Específico", activo="V-1", importe="5000", tasa="9", costo_financiero="400"),
                      _pr("PR-Y", "General", descripcion="Línea sin importe informado", costo_financiero="800")]}

# Escenario de activos revaluados (NIC 16.39 · NIC 36.60-61 · CINIIF 1.5 y 1.8), recalculado a mano:
# EDIF-R: dep. 200.000 ÷ 480 × 12 = 5.000 (= registrada); acum. 25.000; VNL 175.000. Revaluado 185.000 → +10.000
#   con decremento previo en resultados 12.000 → los 10.000 van a resultados (16.39) y 0 a ORI. Deterioro:
#   185.000 − 170.000 = 15.000 contra el superávit disponible 30.000 + 0 → 15.000 a ORI y 0 a resultados (36.60-61).
# MAQ-R: dep. 100.000 ÷ 120 × 12 = 10.000 (= registrada); acum. 60.000; VNL 40.000. Revaluado 42.000 → +2.000 sin
#   decremento previo informado → todo a ORI y aviso. Deterioro 42.000 − 35.000 = 7.000 sin superávit informado →
#   no se reparte, queda en resultados y se avisa.
# Desmantelamiento: VP 27.919,74; registrada al cierre 26.500 → ajuste total 1.419,74; actualización del período
#   26.000 × 6 % = 1.560 (costo financiero); cambio de estimación 1.419,74 − 1.560 = −140,26 (contra el costo).
# Efecto neto en resultados = −0 − 7.000 + 0 + 0 + 10.000 − 1.560 = 1.440,00.
_REVALUADOS = {"activos": [
    _a("EDIF-R", "Edificio revaluado con deterioro", "Edificios", "2018-01-01", "200000", vida_meses="480", metodo="Lineal",
       dep_acum_inicial="20000", dep_registrada="5000", valor_revaluado="185000", superavit_previo="30000",
       decremento_previo="12000", importe_recuperable="170000"),
    _a("MAQ-R", "Máquina revaluada sin superávit informado", "Maquinaria", "2020-01-01", "100000", vida_meses="120", metodo="Lineal",
       dep_acum_inicial="50000", dep_registrada="10000", valor_revaluado="42000", importe_recuperable="35000"),
]}
PARAMETROS_REVALUADOS = {"_marco": MARCO_COMPLETAS, "tolerancia": 1, "costoDesmantelamiento": 50000, "aniosDesmantelamiento": 10,
                         "tasaDesmantelamiento": 6, "provisionDesmantelamiento": 26500, "provisionDesmantelamientoInicial": 26000,
                         "mayorCosto": 300000, "mayorDepAcum": 85000}
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2025"}, EJEMPLO["corte"]),
    ("sin_anexo_prestamos", _SIN_PRESTAMOS, EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("tope_costos_prestamos", _TOPE, EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("revaluados_desmantelamiento", _REVALUADOS, PARAMETROS_REVALUADOS, "2025-12-31"),
    ("minimo", _MIN, {}, "2025-12-31"),
]
