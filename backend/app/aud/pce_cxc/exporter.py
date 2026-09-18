"""Excel del papel de trabajo de pérdidas crediticias esperadas (AUD.PCE_CXC).

Este es el entregable que el auditor archiva y que su revisor debe poder
recalcular: trece hojas donde lo calculado es fórmula de Excel (no un número
pegado). Solo son valores fijos los datos de origen (``02-Fuentes``,
``03-Cohorte``) y los parámetros (``01-Parametros``); todo lo demás -pérdida
esperada, provisiones, diferencias, cuadres- se escribe como fórmula para que
cambiar un parámetro (p. ej. el factor prospectivo) recalcule el libro entero.

Reglas de fórmulas (ver también CLAUDE.md, sección de anexos):
  - Funciones permitidas: ``SUM``, ``SUMIFS``, ``COUNTIFS``, ``INDEX``,
    ``MATCH``, ``IF``, ``ABS``, ``ROUND`` y ``MAX`` (esta última para el
    exceso no deducible de ``09-Tributario``, según el propio diseño de esa
    hoja). Prohibidas: ``INDIRECT``, ``OFFSET``, matrices dinámicas y
    vínculos externos -ninguna se usa aquí-.
  - Una banda o fila sin medir NUNCA se escribe como 0,00: se rotula
    "SIN MEDIR" (texto, no fórmula) para que no se confunda con una pérdida
    cero real.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.workbook.defined_name import DefinedName

# ---------------------------------------------------------------------------
# Formato (CLAUDE.md: Calibri 9 en datos, 10 negrita en totales, 11 negrita en
# encabezados de bloque, bordes finos, doble en TOTAL, anchos explícitos,
# numéricos a la derecha con #,##0.00).
# ---------------------------------------------------------------------------
FORMATO_MONEDA = "#,##0.00"
FORMATO_PORCENTAJE = "0.00%"
FORMATO_ENTERO = "#,##0"

FUENTE_DATOS = Font(name="Calibri", size=9)
FUENTE_DATOS_NEGRITA = Font(name="Calibri", size=9, bold=True)
FUENTE_TOTAL = Font(name="Calibri", size=10, bold=True)
FUENTE_BLOQUE = Font(name="Calibri", size=11, bold=True, color="0A2342")
FUENTE_ENCABEZADO_COL = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
FUENTE_HIPERVINCULO = Font(name="Calibri", size=9, color="0563C1", underline="single")
FUENTE_TITULO = Font(name="Calibri", size=14, bold=True, color="0A2342")

FUENTE_ALERTA = Font(name="Calibri", size=11, bold=True, color="9C0006")

RELLENO_ENCABEZADO = PatternFill("solid", fgColor="0A2342")  # navy (identidad de la firma)
RELLENO_TOTAL = PatternFill("solid", fgColor="FBF3DC")       # dorado muy claro
RELLENO_BLOQUE = PatternFill("solid", fgColor="D9E2EC")      # azul grisáceo claro
RELLENO_ALERTA = PatternFill("solid", fgColor="FFE3E3")      # rojo muy claro

THIN = Side(style="thin", color="000000")
DOUBLE = Side(style="double", color="000000")
BORDE_DATOS = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BORDE_TOTAL = Border(left=THIN, right=THIN, top=DOUBLE, bottom=DOUBLE)

ALIN_IZQ = Alignment(horizontal="left", vertical="center", wrap_text=True)
ALIN_DER = Alignment(horizontal="right", vertical="center")
ALIN_CEN = Alignment(horizontal="center", vertical="center", wrap_text=True)

SEGMENTOS_TEXTO = "SIN MEDIR"

#: La pantalla rotula el papel como preliminar arriba y abajo. El libro que se
#: archiva tiene que decir lo mismo: mientras el Socio no lo revise y apruebe,
#: esto no es una conclusión de auditoría.
AVISO_PRELIMINAR = ("PAPEL DE TRABAJO PRELIMINAR — pendiente de revisión y aprobación del "
                    "Socio responsable. No usar como conclusión de auditoría.")
ESTADO_PRELIMINAR = "PRELIMINAR — pendiente de revisión y aprobación del Socio responsable"
#: Lo que no se registró no se deja en blanco (una celda vacía se lee como
#: "no aplica"): se declara que está pendiente.
SIN_REGISTRAR = "(pendiente)"
#: Corridas guardadas antes de que la pantalla enviara `fecha_emision`: el dato
#: no existe y no se inventa con la fecha de la descarga.
SIN_FECHA_EMISION = "(no registrada en la corrida)"
#: Marca temporal de las propiedades del documento cuando la corrida no trae
#: ninguna fecha. No es un dato del papel -no se imprime en ninguna celda-,
#: es metadato del archivo; fijarlo es lo que evita que dos descargas de la
#: misma corrida difieran en `docProps/core.xml`.
EPOCA_SIN_FECHA = datetime(2000, 1, 1)


# ---------------------------------------------------------------------------
# Helpers de estilo, reutilizados por las trece hojas
# ---------------------------------------------------------------------------

def _celda(ws, fila: int, col: int, valor, *, formato: str | None = None,
           alineacion: Alignment | None = None, total: bool = False):
    """Escribe un valor (o fórmula) y aplica el estilo estándar de la hoja."""
    c = ws.cell(fila, col, valor)
    c.font = FUENTE_TOTAL if total else FUENTE_DATOS
    c.border = BORDE_TOTAL if total else BORDE_DATOS
    if total:
        c.fill = RELLENO_TOTAL
    if formato:
        c.number_format = formato
    if alineacion:
        c.alignment = alineacion
    return c


def _encabezados(ws, fila: int, textos: list[str]) -> None:
    for i, t in enumerate(textos, start=1):
        c = ws.cell(fila, i, t)
        c.font = FUENTE_ENCABEZADO_COL
        c.fill = RELLENO_ENCABEZADO
        c.border = BORDE_DATOS
        c.alignment = ALIN_CEN
    ws.row_dimensions[fila].height = 28
    ws.freeze_panes = ws.cell(fila + 1, 1).coordinate


def _bloque(ws, fila: int, texto: str, num_cols: int) -> None:
    ws.cell(fila, 1, texto)
    for col in range(1, num_cols + 1):
        c = ws.cell(fila, col)
        c.font = FUENTE_BLOQUE
        c.fill = RELLENO_BLOQUE
    if num_cols > 1:
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=num_cols)


def _anchos(ws, mapa: dict[str, float]) -> None:
    for col, w in mapa.items():
        ws.column_dimensions[col].width = w


def _fecha_emision(parametros: dict[str, Any]) -> tuple[str, datetime]:
    """Fecha con la que se emitió el papel: la de la corrida, nunca la de hoy.

    Devuelve el texto que se imprime y la marca temporal con la que se sellan
    las propiedades del documento. `date.today()` haría que dos descargas de la
    misma corrida dieran papeles distintos, y `models.py` guarda la corrida
    precisamente para reproducirlo "tal como se emitió".
    """
    crudo = str(parametros.get("fecha_emision") or "").strip()
    if crudo:
        try:
            d = date.fromisoformat(crudo)
        except ValueError:
            d = None
        if d is not None:
            return d.isoformat(), datetime(d.year, d.month, d.day)
    # Sin fecha de emisión registrada se declara el vacío. Para el metadato del
    # archivo se cae a la fecha de corte, que sí viaja en la corrida.
    for candidata in reversed([str(f) for f in (parametros.get("fechas") or [])]):
        try:
            d = date.fromisoformat(candidata)
        except ValueError:
            continue
        return SIN_FECHA_EMISION, datetime(d.year, d.month, d.day)
    return SIN_FECHA_EMISION, EPOCA_SIN_FECHA


def _numero(valor: Any) -> float | None:
    """``None`` explícito se preserva (banda sin medir); todo lo demás, a float."""
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

def construir_excel(resultado: dict[str, Any], parametros: dict[str, Any]) -> bytes:
    """Arma el papel de trabajo completo (trece hojas) a partir del resultado
    de ``service.analizar`` y los parámetros con los que se corrió.

    ``resultado`` y ``parametros`` nunca se mutan.
    """
    wb = Workbook()
    wb.remove(wb.active)

    fecha_texto, marca = _fecha_emision(parametros)
    # Las propiedades del documento se sellan con la fecha de la corrida: por
    # defecto openpyxl pone `datetime.now()`, que vuelve distinto el paquete en
    # cada descarga aunque ninguna celda cambie.
    wb.properties.created = marca
    wb.properties.modified = marca

    refs: dict[str, Any] = {}
    _caratula(wb, resultado, parametros, fecha_texto)
    _parametros(wb, resultado, parametros, refs)
    _fuentes(wb, resultado)
    _cohorte(wb, resultado, refs)
    _tasas(wb, resultado, parametros, refs)
    _matriz(wb, resultado, refs)
    _individual(wb, resultado, refs)
    _politica(wb, resultado, refs)
    _conciliacion(wb, resultado, refs)
    _tributario(wb, resultado, refs)
    _hallazgos(wb, resultado)
    _pendientes(wb, resultado)
    _bitacora(wb, resultado, fecha_texto)

    wb.calculation.fullCalcOnLoad = True
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


# ---------------------------------------------------------------------------
# 00-Caratula
# ---------------------------------------------------------------------------

_INDICE = [
    ("01-Parametros", "Parámetros de la estimación"),
    ("02-Fuentes", "Fuentes y trazabilidad de la carga"),
    ("03-Cohorte", "Detalle de la cohorte"),
    ("04-Tasas", "Tasas observadas"),
    ("05-Matriz", "Matriz de pérdida esperada"),
    ("06-Individual", "Evaluación individual"),
    ("07-Politica", "Comparación contra la política del cliente"),
    ("08-Conciliacion", "Conciliación con estados financieros"),
    ("09-Tributario", "Efecto tributario (LORTI)"),
    ("10-Hallazgos", "Hallazgos de auditoría"),
    ("11-Pendientes", "Información pendiente"),
    ("12-Bitacora", "Bitácora del cálculo"),
]


def _caratula(wb: Workbook, resultado: dict[str, Any], parametros: dict[str, Any],
              fecha_emision: str) -> None:
    ws = wb.create_sheet("00-Caratula")
    ws.cell(1, 1, "PAPEL DE TRABAJO — PÉRDIDA CREDITICIA ESPERADA, CUENTAS POR COBRAR")
    ws.cell(1, 1).font = FUENTE_TITULO
    ws.merge_cells("A1:B1")

    # El aviso va inmediatamente bajo el título, antes que cualquier cifra: es
    # lo primero que tiene que leer quien abra el archivo permanente.
    c = ws.cell(2, 1, AVISO_PRELIMINAR)
    c.font = FUENTE_ALERTA
    c.fill = RELLENO_ALERTA
    c.alignment = ALIN_IZQ
    ws.cell(2, 2).fill = RELLENO_ALERTA
    ws.merge_cells("A2:B2")
    ws.row_dimensions[2].height = 30

    fechas = parametros.get("fechas") or []
    fecha_corte = fechas[-1] if fechas else ""

    _bloque(ws, 3, "Datos generales", 2)
    _encabezados(ws, 4, ["Concepto", "Valor"])
    filas = [
        ("Estado del papel", ESTADO_PRELIMINAR),
        ("Entidad", parametros.get("entidad", "")),
        ("RUC", parametros.get("ruc", "")),
        ("Fecha de corte", fecha_corte),
        ("Moneda", parametros.get("moneda", "USD")),
        ("Marco contable", parametros.get("marco", "NIIF 9 - Deterioro de cartera comercial")),
        ("Referencia del papel", parametros.get("referencia", "PT-PCE-CXC")),
        ("Preparado por", parametros.get("preparado_por") or SIN_REGISTRAR),
        ("Revisado por", parametros.get("revisado_por") or SIN_REGISTRAR),
        ("Fecha de emisión del papel", fecha_emision),
    ]
    fila = 5
    for concepto, valor in filas:
        _celda(ws, fila, 1, concepto, alineacion=ALIN_IZQ)
        _celda(ws, fila, 2, valor, alineacion=ALIN_IZQ)
        fila += 1

    fila += 1
    _bloque(ws, fila, "Índice", 2)
    fila += 1
    _encabezados(ws, fila, ["Hoja", "Contenido"])
    fila += 1
    for hoja, titulo in _INDICE:
        c = _celda(ws, fila, 1, hoja, alineacion=ALIN_IZQ)
        c.hyperlink = f"#'{hoja}'!A1"
        c.font = FUENTE_HIPERVINCULO
        _celda(ws, fila, 2, titulo, alineacion=ALIN_IZQ)
        fila += 1

    _anchos(ws, {"A": 30, "B": 55})
    ws.sheet_view.showGridLines = False


# ---------------------------------------------------------------------------
# 01-Parametros
# ---------------------------------------------------------------------------

def _parametros(wb: Workbook, resultado: dict[str, Any], parametros: dict[str, Any],
                refs: dict[str, Any]) -> None:
    ws = wb.create_sheet("01-Parametros")
    _encabezados(ws, 1, ["Parámetro", "Valor", "Fuente"])

    bitacora = resultado.get("bitacora") or {}
    conciliacion = resultado.get("conciliacion") or {}
    exposicion = resultado.get("exposicion") or {}

    # El ajuste prospectivo del papel es POR SEGMENTO, no global: el motor
    # mide cada segmento por separado (service.analizar llama a medir_ecl una
    # vez por segmento, cada uno con su propio factor) y 05-Matriz debe
    # resolver, fila por fila, el factor del segmento de esa fila -antes se
    # escribía una sola celda global y toda la matriz recalculaba con el
    # factor de un único "segmento principal", desalineándose en silencio de
    # lo que el motor concluyó para el resto de segmentos-.
    #
    # El factor debe ser el que el motor REALMENTE APLICÓ
    # (resultado["matriz"]["ajuste_prospectivo"]), no el solicitado en parámetros:
    # cuando se pide sin justificación escrita, el motor lo rechaza y aplica 1,0.
    # Si esa clave no existe (resultado antiguo), caer a parámetros por
    # retrocompatibilidad; si tampoco está, 1,0.
    #
    # Retrocompatibilidad: en corridas antiguas, ajuste_prospectivo era un
    # escalar (float), no un diccionario por segmento. Si es un número,
    # interpretarlo como el mismo ajuste para ambos segmentos.
    ajuste_valor = resultado.get("matriz", {}).get("ajuste_prospectivo")

    if isinstance(ajuste_valor, dict) and ajuste_valor:
        # Formato nuevo: diccionario por segmento
        ajuste_no_relacionados = float(ajuste_valor.get("NO-RELACIONADOS", 1.0)) - 1.0
        ajuste_relacionados = float(ajuste_valor.get("RELACIONADOS", 1.0)) - 1.0
    elif isinstance(ajuste_valor, (int, float)) and ajuste_valor != 0:
        # Formato antiguo: escalar no cero. Aplicar a ambos segmentos.
        # Un valor de 0.05 significa factor 1,05 → ajuste 0,05.
        ajuste_no_relacionados = float(ajuste_valor)
        ajuste_relacionados = float(ajuste_valor)
    elif isinstance(ajuste_valor, (int, float)) and ajuste_valor == 0:
        # Formato antiguo: escalar cero. Sin ajuste para ambos segmentos.
        ajuste_no_relacionados = 0.0
        ajuste_relacionados = 0.0
    else:
        # No hay ajuste en resultado: leer de parámetros por retrocompatibilidad
        factor_dict = parametros.get("factor_prospectivo") or {}
        ajuste_no_relacionados = float(factor_dict.get("NO-RELACIONADOS", 1.0)) - 1.0
        ajuste_relacionados = float(factor_dict.get("RELACIONADOS", 1.0)) - 1.0

    saldo_contable = conciliacion.get("saldo_contable")
    if saldo_contable is None:
        saldo_contable = exposicion.get("segun_archivo")

    # Filas 2 a 8: fijas por posición porque 05-Matriz referencia los nombres
    # definidos AjusteProspectivoNoRelacionados / AjusteProspectivoRelacionados
    # (y esta función define los otros nombres en las celdas que se documentan
    # abajo).
    _celda(ws, 2, 1, "Materialidad", alineacion=ALIN_IZQ)
    _celda(ws, 2, 2, _numero(parametros.get("materialidad")), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    _celda(ws, 2, 3, "Definida por el socio del encargo", alineacion=ALIN_IZQ)

    _celda(ws, 3, 1, "Umbral de evaluación individual", alineacion=ALIN_IZQ)
    _celda(ws, 3, 2, _numero(parametros.get("umbral_individual")), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    _celda(ws, 3, 3, "Definido por el socio del encargo", alineacion=ALIN_IZQ)

    _celda(ws, 4, 1, "Umbral de incumplimiento (días)", alineacion=ALIN_IZQ)
    _celda(ws, 4, 2, _numero(bitacora.get("umbral_incumplimiento")) or 730, formato=FORMATO_ENTERO,
           alineacion=ALIN_DER)
    # El plazo lo fija la entidad. NIIF 9 B5.5.37 presume el incumplimiento a
    # los 90 días de mora y esa presunción es refutable: citarla como si la
    # norma trajera un defecto de 730 días atribuye a la NIIF una decisión que
    # es de la administración y que el papel tiene que sustentar.
    _celda(ws, 4, 3, "Política de la entidad. NIIF 9 B5.5.37 presume el incumplimiento a los "
                     "90 días de mora; es una presunción refutable y la entidad la refuta con "
                     "este plazo, que debe quedar sustentado en el papel.",
           alineacion=ALIN_IZQ)

    _celda(ws, 5, 1, "Ajuste prospectivo — NO-RELACIONADOS (terceros)", alineacion=ALIN_IZQ)
    _celda(ws, 5, 2, ajuste_no_relacionados, formato=FORMATO_PORCENTAJE, alineacion=ALIN_DER)
    _celda(ws, 5, 3, "Cambiar este valor recalcula, en 05-Matriz, las bandas de NO-RELACIONADOS",
           alineacion=ALIN_IZQ)

    _celda(ws, 6, 1, "Ajuste prospectivo — RELACIONADOS", alineacion=ALIN_IZQ)
    _celda(ws, 6, 2, ajuste_relacionados, formato=FORMATO_PORCENTAJE, alineacion=ALIN_DER)
    _celda(ws, 6, 3, "Cambiar este valor recalcula, en 05-Matriz, las bandas de RELACIONADOS",
           alineacion=ALIN_IZQ)

    _celda(ws, 7, 1, "Saldo contable (cartera según EEFF, total)", alineacion=ALIN_IZQ)
    _celda(ws, 7, 2, _numero(saldo_contable), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    _celda(ws, 7, 3, "Estados financieros auditados", alineacion=ALIN_IZQ)

    _celda(ws, 8, 1, "Justificación del ajuste prospectivo", alineacion=ALIN_IZQ)
    _celda(ws, 8, 2, "", alineacion=ALIN_IZQ)
    _celda(ws, 8, 3, str(parametros.get("justificacion_prospectivo") or "(sin justificación registrada)"),
           alineacion=ALIN_IZQ)

    wb.defined_names.add(DefinedName("Materialidad", attr_text="'01-Parametros'!$B$2"))
    wb.defined_names.add(DefinedName("UmbralIndividual", attr_text="'01-Parametros'!$B$3"))
    wb.defined_names.add(DefinedName("AjusteProspectivoNoRelacionados", attr_text="'01-Parametros'!$B$5"))
    wb.defined_names.add(DefinedName("AjusteProspectivoRelacionados", attr_text="'01-Parametros'!$B$6"))
    # Alias de compatibilidad: "AjusteProspectivo" (sin sufijo de segmento) se
    # conserva porque test_pce_exporter.py todavía lo busca por ese nombre;
    # equivale al factor de terceros (NO-RELACIONADOS), el mismo segmento que
    # antes se usaba como "segmento principal" cuando el ajuste era global.
    wb.defined_names.add(DefinedName("AjusteProspectivo", attr_text="'01-Parametros'!$B$5"))
    wb.defined_names.add(DefinedName("SaldoContable", attr_text="'01-Parametros'!$B$7"))

    fila = 10
    _bloque(ws, fila, "Cartera según EEFF por segmento", 3)
    fila += 1
    eeff = parametros.get("eeff") or {}
    if eeff:
        for segmento, valor in eeff.items():
            _celda(ws, fila, 1, f"Cartera EEFF — {segmento}", alineacion=ALIN_IZQ)
            _celda(ws, fila, 2, _numero(valor), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
            _celda(ws, fila, 3, "Estados financieros auditados", alineacion=ALIN_IZQ)
            fila += 1
    else:
        _celda(ws, fila, 1, "(sin desglose de cartera EEFF por segmento)", alineacion=ALIN_IZQ)
        _celda(ws, fila, 2, "", alineacion=ALIN_IZQ)
        _celda(ws, fila, 3, "", alineacion=ALIN_IZQ)
        fila += 1

    _anchos(ws, {"A": 42, "B": 20, "C": 46})
    refs["parametros"] = {"ajuste_prospectivo_no_relacionados_row": 5,
                          "ajuste_prospectivo_relacionados_row": 6, "saldo_contable_row": 7}


# ---------------------------------------------------------------------------
# 02-Fuentes
# ---------------------------------------------------------------------------

def _mapeo_texto(mapeo: Any) -> str:
    if isinstance(mapeo, dict):
        return "; ".join(f"{k} → {v}" for k, v in mapeo.items())
    return str(mapeo or "")


def _fuentes(wb: Workbook, resultado: dict[str, Any]) -> None:
    ws = wb.create_sheet("02-Fuentes")
    encabezado = ["Archivo", "Hoja", "Fila de encabezado", "Mapeo de columnas", "Formato de fecha",
                  "Documentos", "Duplicados exactos", "Documentos repetidos", "Descartados", "Total"]
    _encabezados(ws, 1, encabezado)
    cortes = (resultado.get("bitacora") or {}).get("cortes") or []

    primera = 2
    if cortes:
        ultima = primera + len(cortes) - 1
        for i, corte in enumerate(cortes, start=primera):
            _celda(ws, i, 1, corte.get("archivo", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 2, corte.get("hoja", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 3, corte.get("fila_encabezado"), formato=FORMATO_ENTERO, alineacion=ALIN_CEN)
            _celda(ws, i, 4, _mapeo_texto(corte.get("mapeo")), alineacion=ALIN_IZQ)
            _celda(ws, i, 5, corte.get("formato_fecha", ""), alineacion=ALIN_CEN)
            _celda(ws, i, 6, corte.get("documentos"), formato=FORMATO_ENTERO, alineacion=ALIN_DER)
            _celda(ws, i, 7, corte.get("duplicados_exactos"), formato=FORMATO_ENTERO, alineacion=ALIN_DER)
            _celda(ws, i, 8, corte.get("documentos_repetidos"), formato=FORMATO_ENTERO, alineacion=ALIN_DER)
            _celda(ws, i, 9, corte.get("descartados"), formato=FORMATO_ENTERO, alineacion=ALIN_DER)
            _celda(ws, i, 10, _numero(corte.get("total")), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    else:
        ultima = primera
        _celda(ws, primera, 1, "(sin cortes registrados en la bitácora de esta corrida)", alineacion=ALIN_IZQ)
        for col in range(2, 11):
            _celda(ws, primera, col, None, alineacion=ALIN_IZQ)

    fila_total = ultima + 1
    _celda(ws, fila_total, 9, "TOTAL", total=True, alineacion=ALIN_IZQ)
    _celda(ws, fila_total, 10, f"=SUM(J{primera}:J{ultima})", formato=FORMATO_MONEDA, total=True,
           alineacion=ALIN_DER)
    for col in (1, 2, 3, 4, 5, 6, 7, 8):
        _celda(ws, fila_total, col, None, total=True)

    _anchos(ws, {"A": 22, "B": 16, "C": 12, "D": 40, "E": 16, "F": 12, "G": 14, "H": 16, "I": 12, "J": 16})


# ---------------------------------------------------------------------------
# 03-Cohorte y 04-Tasas comparten el orden de filas (segmento, banda) para que
# 04-Tasas pueda referenciar por número de fila exacto a 03-Cohorte.
# ---------------------------------------------------------------------------

def _pares_segmento_banda(resultado: dict[str, Any]) -> list[tuple[str, str]]:
    detalle = resultado.get("detalle_cohorte") or {}
    pares: list[tuple[str, str]] = []
    for segmento, bandas in detalle.items():
        for banda in bandas:
            pares.append((segmento, banda))
    return pares


def _cohorte(wb: Workbook, resultado: dict[str, Any], refs: dict[str, Any]) -> None:
    ws = wb.create_sheet("03-Cohorte")
    _encabezados(ws, 1, ["Segmento", "Banda", "Documentos", "Exposición inicial",
                         "Remanente al corte", "Resuelto"])
    detalle = resultado.get("detalle_cohorte") or {}
    pares = _pares_segmento_banda(resultado)

    primera = 2
    if pares:
        ultima = primera + len(pares) - 1
        for i, (segmento, banda) in zip(range(primera, ultima + 1), pares):
            d = detalle[segmento][banda]
            _celda(ws, i, 1, segmento, alineacion=ALIN_IZQ)
            _celda(ws, i, 2, banda, alineacion=ALIN_IZQ)
            _celda(ws, i, 3, _numero(d.get("documentos")), formato=FORMATO_ENTERO, alineacion=ALIN_DER)
            _celda(ws, i, 4, _numero(d.get("inicial")), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
            _celda(ws, i, 5, _numero(d.get("remanente")), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
            _celda(ws, i, 6, f"=D{i}-E{i}", formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    else:
        ultima = primera
        _celda(ws, primera, 1, "(sin bandas en la cohorte de esta corrida)", alineacion=ALIN_IZQ)
        for col in range(2, 7):
            _celda(ws, primera, col, None)

    fila_total = ultima + 1
    _celda(ws, fila_total, 2, "TOTAL", total=True, alineacion=ALIN_IZQ)
    _celda(ws, fila_total, 1, None, total=True)
    _celda(ws, fila_total, 3, f"=SUM(C{primera}:C{ultima})", formato=FORMATO_ENTERO, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 4, f"=SUM(D{primera}:D{ultima})", formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 5, f"=SUM(E{primera}:E{ultima})", formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 6, f"=SUM(F{primera}:F{ultima})", formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)

    _anchos(ws, {"A": 22, "B": 20, "C": 14, "D": 18, "E": 18, "F": 16})
    refs["cohorte"] = {"pares": pares, "primera": primera, "ultima": ultima, "hay_datos": bool(pares)}


def _tasas(wb: Workbook, resultado: dict[str, Any], parametros: dict[str, Any], refs: dict[str, Any]) -> None:
    ws = wb.create_sheet("04-Tasas")
    _encabezados(ws, 1, ["Segmento", "Banda", "Tasa observada", "Origen (observada o sustituida)",
                         "Justificación de la sustitución"])
    tasas = resultado.get("tasas") or {}
    sustitutas = parametros.get("tasas_sustitutas") or {}
    cohorte_refs = refs.get("cohorte") or {}
    pares = cohorte_refs.get("pares") or []
    primera = 2

    if pares and cohorte_refs.get("hay_datos"):
        ultima = primera + len(pares) - 1
        for i, (segmento, banda) in zip(range(primera, ultima + 1), pares):
            observada = (tasas.get(segmento) or {}).get(banda)
            sustituta = sustitutas.get(f"{segmento}|{banda}")
            if observada is not None:
                origen, justificacion = "Observada", ""
            elif sustituta and str(sustituta.get("justificacion", "")).strip():
                origen = "Sustituida"
                justificacion = sustituta.get("justificacion", "")
            else:
                origen, justificacion = "SIN MEDIR", ""
            _celda(ws, i, 1, segmento, alineacion=ALIN_IZQ)
            _celda(ws, i, 2, banda, alineacion=ALIN_IZQ)
            # Ratio empírico remanente/inicial de la cohorte, sea o no la tasa
            # finalmente aplicada (eso lo dice la columna "Origen"). Guardado
            # con IF (no IFERROR: fuera de las funciones permitidas) para no
            # mostrar #¡DIV/0! cuando la banda no tuvo cartera inicial.
            _celda(ws, i, 3, f"=IF('03-Cohorte'!D{i}=0,\"SIN BASE\",'03-Cohorte'!E{i}/'03-Cohorte'!D{i})",
                   formato=FORMATO_PORCENTAJE, alineacion=ALIN_DER)
            _celda(ws, i, 4, origen, alineacion=ALIN_CEN)
            _celda(ws, i, 5, justificacion, alineacion=ALIN_IZQ)
    else:
        ultima = primera
        _celda(ws, primera, 1, "(sin bandas en la cohorte de esta corrida)", alineacion=ALIN_IZQ)
        for col in range(2, 6):
            _celda(ws, primera, col, None)

    _anchos(ws, {"A": 22, "B": 20, "C": 16, "D": 24, "E": 44})


# ---------------------------------------------------------------------------
# 05-Matriz — el corazón auditable del papel: AjusteProspectivoNoRelacionados
# y AjusteProspectivoRelacionados son nombres definidos en 01-Parametros; cada
# fila resuelve el que corresponde a SU segmento (columna A de esa fila), así
# que cambiar cualquiera de los dos valores en Excel recalcula solo las bandas
# de ese segmento -nunca las del otro-.
# ---------------------------------------------------------------------------

def _matriz(wb: Workbook, resultado: dict[str, Any], refs: dict[str, Any]) -> None:
    ws = wb.create_sheet("05-Matriz")
    _encabezados(ws, 1, ["Segmento", "Banda", "Exposición", "Tasa aplicada", "Factor prospectivo",
                         "Pérdida esperada"])
    tramos = (resultado.get("matriz") or {}).get("tramos") or []
    primera = 2

    if tramos:
        ultima = primera + len(tramos) - 1
        for i, t in zip(range(primera, ultima + 1), tramos):
            _celda(ws, i, 1, t.get("segmento", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 2, t["tramo"], alineacion=ALIN_IZQ)
            _celda(ws, i, 3, _numero(t["exposicion"]), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
            if t.get("tasa_perdida") is None:
                _celda(ws, i, 4, "SIN MEDIR", alineacion=ALIN_CEN)
                _celda(ws, i, 5, "", alineacion=ALIN_CEN)
                _celda(ws, i, 6, "SIN MEDIR", alineacion=ALIN_CEN)
                continue
            _celda(ws, i, 4, _numero(t["tasa_perdida"]), formato=FORMATO_PORCENTAJE, alineacion=ALIN_DER)
            # El factor prospectivo es por segmento: se resuelve el nombre
            # definido según el segmento de ESTA fila (columna A), no un
            # nombre único compartido por toda la matriz.
            _celda(ws, i, 5, f'=IF(A{i}="RELACIONADOS",AjusteProspectivoRelacionados,'
                             f'AjusteProspectivoNoRelacionados)',
                   formato=FORMATO_PORCENTAJE, alineacion=ALIN_DER)
            _celda(ws, i, 6, f"=C{i}*D{i}*(1+E{i})", formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    else:
        ultima = primera
        _celda(ws, primera, 1, "(sin tramos medidos en esta corrida)", alineacion=ALIN_IZQ)
        for col in range(2, 7):
            _celda(ws, primera, col, None)

    fila_total = ultima + 1
    _celda(ws, fila_total, 2, "TOTAL", total=True, alineacion=ALIN_IZQ)
    _celda(ws, fila_total, 1, None, total=True)
    _celda(ws, fila_total, 3, f"=SUM(C{primera}:C{ultima})", formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 4, None, total=True)
    _celda(ws, fila_total, 5, None, total=True)
    _celda(ws, fila_total, 6, f"=SUM(F{primera}:F{ultima})", formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)

    _anchos(ws, {"A": 20, "B": 26, "C": 18, "D": 16, "E": 18, "F": 18})
    refs["matriz"] = {"primera": primera, "ultima": ultima, "fila_total": fila_total,
                      "col_exposicion": "C", "col_banda": "B", "col_perdida": "F"}


# ---------------------------------------------------------------------------
# 06-Individual
# ---------------------------------------------------------------------------

_RE_SEGMENTO = re.compile(r"^(.*)\s\(([^()]+)\)\s*$")


def _partir_identificacion(identificacion: str) -> tuple[str, str]:
    """``"ALFA (NO-RELACIONADOS)"`` -> ``("ALFA", "NO-RELACIONADOS")``.

    ``service.analizar`` arma la identificación de cada caso individual como
    ``"{cliente} ({segmento})"``; el segmento no viaja como campo propio en
    ``individual.casos``, así que se recupera parseando el texto (no se
    inventa el dato, se extrae del que ya existe).
    """
    m = _RE_SEGMENTO.match(identificacion or "")
    if m:
        return m.group(1), m.group(2)
    return identificacion or "", ""


def _estado_caso(caso: dict[str, Any]) -> str:
    if _numero(caso.get("saldo_sin_tasa")) and caso["saldo_sin_tasa"] > 0.005:
        return "Parcialmente sin medir"
    if "provisional" in str(caso.get("sustento") or "").lower():
        return "Medido con tasa de matriz (provisional)"
    return "Estimación propia justificada"


def _individual(wb: Workbook, resultado: dict[str, Any], refs: dict[str, Any]) -> None:
    ws = wb.create_sheet("06-Individual")
    _encabezados(ws, 1, ["Cliente", "Segmento", "Exposición", "Recuperación estimada",
                         "Pérdida esperada", "Sustento", "Estado"])
    casos = (resultado.get("individual") or {}).get("casos") or []
    primera = 2

    if casos:
        ultima = primera + len(casos) - 1
        for i, caso in zip(range(primera, ultima + 1), casos):
            cliente, segmento = _partir_identificacion(caso.get("identificacion", ""))
            _celda(ws, i, 1, cliente, alineacion=ALIN_IZQ)
            _celda(ws, i, 2, segmento, alineacion=ALIN_IZQ)
            _celda(ws, i, 3, _numero(caso.get("saldo")), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
            _celda(ws, i, 4, _numero(caso.get("recuperacion_estimada")), formato=FORMATO_MONEDA,
                   alineacion=ALIN_DER)
            _celda(ws, i, 5, f"=C{i}-D{i}", formato=FORMATO_MONEDA, alineacion=ALIN_DER)
            _celda(ws, i, 6, caso.get("sustento", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 7, _estado_caso(caso), alineacion=ALIN_IZQ)
    else:
        ultima = primera
        _celda(ws, primera, 1, "(sin saldos evaluados individualmente en esta corrida)", alineacion=ALIN_IZQ)
        for col in range(2, 8):
            _celda(ws, primera, col, None)

    fila_total = ultima + 1
    _celda(ws, fila_total, 1, "TOTAL", total=True, alineacion=ALIN_IZQ)
    _celda(ws, fila_total, 2, None, total=True)
    _celda(ws, fila_total, 3, f"=SUM(C{primera}:C{ultima})", formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 4, f"=SUM(D{primera}:D{ultima})", formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 5, f"=SUM(E{primera}:E{ultima})", formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 6, None, total=True)
    _celda(ws, fila_total, 7, None, total=True)

    _anchos(ws, {"A": 24, "B": 18, "C": 16, "D": 18, "E": 16, "F": 40, "G": 26})
    refs["individual"] = {"primera": primera, "ultima": ultima, "fila_total": fila_total,
                          "col_exposicion": "C", "col_perdida": "E"}


# ---------------------------------------------------------------------------
# 07-Politica
# ---------------------------------------------------------------------------

def _politica(wb: Workbook, resultado: dict[str, Any], refs: dict[str, Any]) -> None:
    ws = wb.create_sheet("07-Politica")
    _encabezados(ws, 1, ["Banda", "Banda de origen", "Exposición", "Tasa de la política",
                         "Provisión política", "PCE recálculo", "Diferencia"])
    filas_pol = (resultado.get("politica") or {}).get("filas") or []
    matriz_refs = refs.get("matriz") or {}
    primera = 2

    if filas_pol:
        ultima = primera + len(filas_pol) - 1
        for i, f in zip(range(primera, ultima + 1), filas_pol):
            _celda(ws, i, 1, f.get("banda", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 2, f.get("banda_origen", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 3, _numero(f.get("exposicion")), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
            _celda(ws, i, 4, _numero(f.get("tasa_politica")), formato=FORMATO_PORCENTAJE, alineacion=ALIN_DER)
            _celda(ws, i, 5, f"=C{i}*D{i}", formato=FORMATO_MONEDA, alineacion=ALIN_DER)
            if f.get("ecl") is None:
                # Ninguna banda del segmento tuvo tasa observada ni sustituta:
                # no se recalcula desde 05-Matriz porque ahí tampoco hay nada
                # medido para esa banda. Se rotula, no se pone en cero.
                _celda(ws, i, 6, "SIN MEDIR", alineacion=ALIN_CEN)
                _celda(ws, i, 7, "SIN MEDIR", alineacion=ALIN_CEN)
            else:
                sumifs = (f"=SUMIFS('05-Matriz'!{matriz_refs['col_perdida']}{matriz_refs['primera']}:"
                         f"{matriz_refs['col_perdida']}{matriz_refs['ultima']},"
                         f"'05-Matriz'!{matriz_refs['col_banda']}{matriz_refs['primera']}:"
                         f"{matriz_refs['col_banda']}{matriz_refs['ultima']},A{i})")
                _celda(ws, i, 6, sumifs, formato=FORMATO_MONEDA, alineacion=ALIN_DER)
                _celda(ws, i, 7, f"=F{i}-E{i}", formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    else:
        ultima = primera
        _celda(ws, primera, 1, "(sin bandas de política en esta corrida)", alineacion=ALIN_IZQ)
        for col in range(2, 8):
            _celda(ws, primera, col, None)

    fila_total = ultima + 1
    _celda(ws, fila_total, 2, "TOTAL", total=True, alineacion=ALIN_IZQ)
    _celda(ws, fila_total, 1, None, total=True)
    _celda(ws, fila_total, 3, f"=SUM(C{primera}:C{ultima})", formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 4, None, total=True)
    _celda(ws, fila_total, 5, f"=SUM(E{primera}:E{ultima})", formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 6, f"=SUM(F{primera}:F{ultima})", formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 7, f"=SUM(G{primera}:G{ultima})", formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)

    _anchos(ws, {"A": 20, "B": 20, "C": 16, "D": 16, "E": 16, "F": 16, "G": 16})
    refs["politica"] = {"primera": primera, "ultima": ultima, "fila_total": fila_total}


# ---------------------------------------------------------------------------
# 08-Conciliacion
# ---------------------------------------------------------------------------

def _conciliacion(wb: Workbook, resultado: dict[str, Any], refs: dict[str, Any]) -> None:
    ws = wb.create_sheet("08-Conciliacion")
    _encabezados(ws, 1, ["Concepto", "Importe"])

    conciliacion = resultado.get("conciliacion") or {}
    exposicion = resultado.get("exposicion") or {}
    matriz_refs = refs["matriz"]
    individual_refs = refs["individual"]

    _celda(ws, 2, 1, "Cartera del archivo (según carga original)", alineacion=ALIN_IZQ)
    _celda(ws, 2, 2, _numero(exposicion.get("segun_archivo")), formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    _celda(ws, 3, 1, "Cartera según EEFF", alineacion=ALIN_IZQ)
    tiene_eeff = conciliacion.get("saldo_contable") is not None
    if tiene_eeff:
        _celda(ws, 3, 2, "=SaldoContable", formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    else:
        _celda(ws, 3, 2, "SIN EEFF (no conciliado)", alineacion=ALIN_CEN)

    _celda(ws, 4, 1, "Partida conciliatoria", alineacion=ALIN_IZQ)
    if tiene_eeff:
        _celda(ws, 4, 2, "=B2-B3", formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    else:
        _celda(ws, 4, 2, "N/A", alineacion=ALIN_CEN)

    _celda(ws, 5, 1, "Cartera medida (05-Matriz + 06-Individual)", alineacion=ALIN_IZQ)
    formula_medida = (f"='05-Matriz'!{matriz_refs['col_exposicion']}{matriz_refs['fila_total']}"
                      f"+'06-Individual'!{individual_refs['col_exposicion']}{individual_refs['fila_total']}")
    _celda(ws, 5, 2, formula_medida, formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    _celda(ws, 6, 1, "Estado", alineacion=ALIN_IZQ)
    if tiene_eeff:
        _celda(ws, 6, 2, '=IF(ABS(B4)<0.01,"CUADRA","DIFERENCIA")', alineacion=ALIN_CEN)
    else:
        _celda(ws, 6, 2, "N/A (sin EEFF para conciliar)", alineacion=ALIN_CEN)

    _anchos(ws, {"A": 42, "B": 22})


# ---------------------------------------------------------------------------
# 09-Tributario
# ---------------------------------------------------------------------------

def _tributario(wb: Workbook, resultado: dict[str, Any], refs: dict[str, Any]) -> None:
    ws = wb.create_sheet("09-Tributario")
    _encabezados(ws, 1, ["Concepto", "Importe"])

    tributario = resultado.get("tributario") or {}
    matriz_refs = refs["matriz"]
    individual_refs = refs["individual"]

    _celda(ws, 2, 1, "Provisión contable (PCE total)", alineacion=ALIN_IZQ)
    formula_pce = (f"='05-Matriz'!{matriz_refs['col_perdida']}{matriz_refs['fila_total']}"
                  f"+'06-Individual'!{individual_refs['col_perdida']}{individual_refs['fila_total']}")
    _celda(ws, 2, 2, formula_pce, formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    _celda(ws, 3, 1, "1% del ejercicio (límite anual, LORTI art. 10 núm. 11)", alineacion=ALIN_IZQ)
    _celda(ws, 3, 2, "=SaldoContable*0.01", formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    _celda(ws, 4, 1, "Tope acumulado 10%", alineacion=ALIN_IZQ)
    _celda(ws, 4, 2, "=SaldoContable*0.1", formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    _celda(ws, 5, 1, "Exceso no deducible", alineacion=ALIN_IZQ)
    _celda(ws, 5, 2, "=MAX(0,B2-B3)", formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    _celda(ws, 6, 1, "Nota", alineacion=ALIN_IZQ)
    _celda(ws, 6, 2, tributario.get("nota", ""), alineacion=ALIN_IZQ)

    _anchos(ws, {"A": 46, "B": 22})


# ---------------------------------------------------------------------------
# 10-Hallazgos
# ---------------------------------------------------------------------------

def _hallazgos(wb: Workbook, resultado: dict[str, Any]) -> None:
    ws = wb.create_sheet("10-Hallazgos")
    _encabezados(ws, 1, ["#", "Hallazgo", "Riesgo", "Condición", "Criterio", "Causa", "Efecto",
                         "Recomendación"])
    hallazgos = resultado.get("hallazgos") or []
    if hallazgos:
        for i, h in enumerate(hallazgos, start=2):
            _celda(ws, i, 1, i - 1, alineacion=ALIN_CEN)
            _celda(ws, i, 2, h.get("titulo", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 3, h.get("riesgo", ""), alineacion=ALIN_CEN)
            _celda(ws, i, 4, h.get("condicion", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 5, h.get("criterio", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 6, h.get("causa", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 7, h.get("efecto", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 8, h.get("recomendacion", ""), alineacion=ALIN_IZQ)
    else:
        _celda(ws, 2, 1, "", alineacion=ALIN_CEN)
        _celda(ws, 2, 2, "(sin hallazgos en esta corrida)", alineacion=ALIN_IZQ)
        for col in range(3, 9):
            _celda(ws, 2, col, None)

    _anchos(ws, {"A": 6, "B": 32, "C": 12, "D": 36, "E": 30, "F": 30, "G": 30, "H": 36})


# ---------------------------------------------------------------------------
# 11-Pendientes
# ---------------------------------------------------------------------------

def _pendientes(wb: Workbook, resultado: dict[str, Any]) -> None:
    ws = wb.create_sheet("11-Pendientes")
    _encabezados(ws, 1, ["Variable", "Efecto si no se obtiene", "Criticidad", "Responsable"])
    pendientes = resultado.get("pendientes") or []
    if pendientes:
        for i, p in enumerate(pendientes, start=2):
            _celda(ws, i, 1, p.get("variable", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 2, p.get("efecto", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 3, p.get("criticidad", ""), alineacion=ALIN_CEN)
            _celda(ws, i, 4, p.get("responsable", ""), alineacion=ALIN_IZQ)
    else:
        _celda(ws, 2, 1, "(sin pendientes en esta corrida)", alineacion=ALIN_IZQ)
        for col in range(2, 5):
            _celda(ws, 2, col, None)

    _anchos(ws, {"A": 34, "B": 46, "C": 14, "D": 22})


# ---------------------------------------------------------------------------
# 12-Bitacora
# ---------------------------------------------------------------------------

def _bitacora(wb: Workbook, resultado: dict[str, Any], fecha_emision: str) -> None:
    ws = wb.create_sheet("12-Bitacora")
    _encabezados(ws, 1, ["Concepto", "Detalle"])

    bitacora = resultado.get("bitacora") or {}
    cortes = bitacora.get("cortes") or []
    trazabilidad = resultado.get("trazabilidad")
    factores = (resultado.get("exposicion") or {}).get("factores_anclaje") or {}

    cortes_texto = "; ".join(f"{c.get('archivo', '')} ({c.get('fecha', '')})" for c in cortes) or "(sin cortes)"
    transformaciones_texto = "; ".join(
        f"{c.get('archivo', '')}: mapeo={_mapeo_texto(c.get('mapeo'))}, formato_fecha={c.get('formato_fecha', '')}"
        for c in cortes
    ) or "(sin transformaciones registradas)"
    factores_texto = ", ".join(f"{k}: {v}" for k, v in factores.items()) or "(sin factores de anclaje)"
    trazabilidad_texto = f"{trazabilidad:.1%}" if isinstance(trazabilidad, (int, float)) else ""

    filas = [
        ("Método", bitacora.get("metodo", "")),
        ("Descuento", bitacora.get("descuento", "")),
        ("Bandas", ", ".join(bitacora.get("bandas") or [])),
        ("Umbral de incumplimiento (días)", bitacora.get("umbral_incumplimiento", "")),
        ("Umbral de evaluación individual", bitacora.get("umbral_individual", "")),
        ("Cortes cargados", cortes_texto),
        ("Factores de anclaje a EEFF", factores_texto),
        ("Trazabilidad de la cohorte", trazabilidad_texto),
        ("Transformaciones aplicadas por archivo", transformaciones_texto),
        ("Versión y fecha de generación", f"PT-PCE-CXC v1.0 — emitido {fecha_emision}"),
    ]
    for i, (concepto, detalle) in enumerate(filas, start=2):
        _celda(ws, i, 1, concepto, alineacion=ALIN_IZQ)
        _celda(ws, i, 2, detalle, alineacion=ALIN_IZQ)

    _anchos(ws, {"A": 34, "B": 70})
