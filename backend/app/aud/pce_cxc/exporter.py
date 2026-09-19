"""Excel del papel de trabajo de pérdidas crediticias esperadas (AUD.PCE_CXC).

Este es el entregable que el auditor archiva y que su revisor debe poder
recalcular: trece hojas donde lo calculado es fórmula de Excel (no un número
pegado). Solo son valores fijos los datos de origen (``02-Fuentes``,
``03-Cohorte``) y los parámetros (``01-Parametros``); todo lo demás -pérdida
esperada, provisiones, diferencias, cuadres- se escribe como fórmula para que
cambiar un parámetro (p. ej. el factor prospectivo) recalcule el libro entero.

Reglas de fórmulas (ver también CLAUDE.md, sección de anexos):
  - Funciones permitidas: ``SUM``, ``SUMIFS``, ``COUNTIFS``, ``INDEX``,
    ``MATCH``, ``IF``, ``ABS``, ``ROUND``, ``MAX`` y ``MIN`` (las dos últimas
    para los acotamientos de la norma: el piso cero y el techo del importe en
    libros bruto de ``05-Matriz``, y el exceso sobre el tope acumulado del
    10 % de ``09-Tributario``). Prohibidas: ``INDIRECT``, ``OFFSET``, matrices
    dinámicas y vínculos externos -ninguna se usa aquí-.
  - Una banda o fila sin medir NUNCA se escribe como 0,00: se rotula
    "SIN MEDIR" (texto, no fórmula) para que no se confunda con una pérdida
    cero real.
  - LAS FÓRMULAS APLICAN LOS MISMOS ACOTAMIENTOS QUE EL MOTOR. La celda
    recalculada tiene que dar, al centavo, la pérdida esperada que archivó la
    corrida: si el motor acota y el libro no, quien rehace la cuenta desde el
    papel obtiene una pérdida negativa (nota de crédito) o mayor que la
    cartera (factor prospectivo desbocado), y el papel contradice a la
    pantalla y a la base. ``ROUND`` de Excel redondea medio hacia afuera del
    cero, el mismo criterio de ``motor.redondear``.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.workbook.defined_name import DefinedName

# Los motivos de acotamiento los define el motor: el papel los TRADUCE a texto,
# no los vuelve a escribir. Un motivo nuevo que el exportador no conozca cae en
# el rótulo genérico, nunca en un "SIN ACOTAR" que sería mentira.
from backend.app.aud.pce_cxc.cortes import ROLES_DE_CORTE
from backend.app.aud.pce_cxc.motor import PISO_CERO, TECHO_SALDO
# Todo texto del cliente entra por aquí: ver el docstring de `texto.py` y el de
# `_Formula`, unas líneas más abajo.
from backend.app.aud.pce_cxc.texto import empieza_como_formula, limpiar_texto

# ---------------------------------------------------------------------------
# Formato (CLAUDE.md: Calibri 9 en datos, 10 negrita en totales, 11 negrita en
# encabezados de bloque, bordes finos, doble en TOTAL, anchos explícitos,
# numéricos a la derecha con #,##0.00).
# ---------------------------------------------------------------------------
FORMATO_MONEDA = "#,##0.00"
#: El factor prospectivo se escribe como FACTOR, no como porcentaje: 1,000 es
#: «sin ajuste», que es lo que dicen la pantalla, el parámetro que se guarda
#: con la corrida y los dos mensajes de error del módulo.
FORMATO_FACTOR = "0.000"
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
FUENTE_DATOS_ALERTA = Font(name="Calibri", size=9, bold=True, color="9C0006")
FUENTE_TOTAL_ALERTA = Font(name="Calibri", size=10, bold=True, color="9C0006")

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
#: Tres cortes son tres FECHAS: sus importes no se netean en un total.
NO_SUMABLE_ENTRE_CORTES = "NO SUMABLE (tres cortes, tres fechas)"
NOTA_CORTES_NO_SUMABLES = (
    "Cada fila es un corte con su propia fecha, así que estas columnas NO se totalizan: sumar la "
    "cartera no leída de t-2, la de t-1 y la de t presentaba como «lo que no se pudo leer» una "
    "cifra que no existe en ningún corte (con signos opuestos llegaba a netear hasta casi cero). "
    "Lo que no se pudo leer se lee corte por corte, en su propia fila. La cartera no leída del "
    "CORTE ACTUAL es la que afecta a la medición -es el corte que fija la exposición- y tiene su "
    "hallazgo en 10-Hallazgos; la de los cortes t-2 y t-1 mueve las TASAS y tiene el suyo. "
    "El ROL de cada fila lo fija la POSICIÓN en que se subió el archivo, no su nombre: por eso "
    "cada fila imprime, al lado del rol, la FECHA DE CORTE que el auditor declaró para ese "
    "archivo. Las tres fechas van en orden cronológico estricto y la herramienta rechaza la "
    "corrida si no lo están: con el orden cambiado no falla nada, se mide otra cosa.")
#: Rótulo de la banda cuya política de deterioro el cliente no proporcionó:
#: no se compara, y no vale 0 %.
TEXTO_SIN_COMPARAR = "SIN COMPARAR"

#: Rótulos del acotamiento que actuó. El papel NUNCA acota en silencio: hay
#: una columna (o una fila) que dice cuál cota movió la cifra y otra que
#: conserva el cálculo sin acotar. Cada rótulo corresponde a un motivo de
#: ``motor.acotar``, y ``motor.COTAS`` los ata a la celda que los imprime.
ACOTADO_PISO = "PISO CERO (NIIF 9 5.5.15)"
ACOTADO_TASA = "TASA ACOTADA AL 100 % (NIIF 9 B5.5.35)"
ACOTADO_TECHO = "TECHO DEL IMPORTE EN LIBROS BRUTO (NIIF 9 B5.5.35)"
ACOTADO_TECHO_CARTERA = "TECHO DE LA CARTERA ESTRATIFICADA"
ACOTADO_EXPOSICION_CASO = "ACOTADO A LA EXPOSICIÓN DEL CASO (NIIF 9 B5.5.35)"
SIN_ACOTAR = "SIN ACOTAR"
#: El tope tributario del 10 % sobre una cartera estratificada neta acreedora:
#: un tope negativo no es un límite, así que no se concluye sobre él.
TOPE_NO_CONTRASTABLE = ("NO CONTRASTABLE — la cartera estratificada es NETA ACREEDORA y su 10 % "
                        "sale negativo")
#: Corridas anteriores al campo que se imprime: el papel dice que el dato no
#: se registró, nunca un 0,00 ni un "SIN ACOTAR" que esa corrida no afirmó.
NO_REGISTRADO = "NO REGISTRADO EN ESTA CORRIDA"
NOTA_ACOTAMIENTOS = (
    "La pérdida esperada de cada banda se acota como manda la norma y el papel lo declara: "
    "no puede ser negativa (NIIF 9 5.5.15 — una nota de crédito no genera «ganancia esperada») "
    "ni superar el importe en libros bruto de su banda, y la tasa ajustada por el factor "
    "prospectivo no puede pasar del 100 % (NIIF 9 B5.5.35). La columna «Pérdida sin acotar» "
    "conserva el cálculo puro y la columna «Acotamiento aplicado» dice cuál de las TRES cotas "
    "actuó -el piso cero, el techo de la tasa o el techo del importe en libros bruto-, "
    "distinguiéndolas desde estas mismas celdas: con los valores que escribe la herramienta el "
    "techo del importe en libros no puede morder, pero las columnas «Factor prospectivo», «LGD» y "
    "«Factor de descuento» están para que el revisor las cambie, y ahí sí muerde. Recalcular la "
    "columna «Pérdida esperada» desde estas mismas celdas devuelve, al centavo, la cifra "
    "archivada en la corrida.")
NOTA_SIN_MEDIR_INDIVIDUAL = (
    "El saldo sin medir de un cliente evaluado individualmente se acota a SU PROPIA exposición "
    "(NIIF 9 B5.5.35): la exposición del cliente es el NETO de sus bandas y lo sin medir suma "
    "solo las positivas, así que sin la cota un cliente con una nota de crédito declaraba más "
    "saldo sin medir que cartera. La columna «Saldo sin medir SIN ACOTAR» conserva el importe "
    "previo a la cota y la columna «Acotamiento del saldo sin medir» dice si actuó: recalcular "
    "la columna «Saldo sin medir» desde estas mismas celdas devuelve, al centavo, lo archivado "
    "en la corrida.")

#: Qué significa el valor de la celda del factor prospectivo. Va en la celda
#: de al lado porque el papel INVITA a editarla, y una celda editable cuya
#: convención no se declara es una invitación a equivocarse por 1,0.
NOTA_CONVENCION_FACTOR = (
    "FACTOR por el que se multiplica la tasa observada de esta banda: 1,000 = sin ajuste (la tasa "
    "observada no se toca), 1,100 = 10 % más de pérdida esperada. Es la misma convención que usa "
    "la pantalla y la que viaja en los parámetros de la corrida. Tiene que ser mayor que 0,000: "
    "un factor de 0,000 anularía la pérdida esperada de todas las bandas y uno negativo invertiría "
    "su signo. Cambiar este valor recalcula, en 05-Matriz, las bandas de {segmento}. El ajuste "
    "exige justificación escrita (NIIF 9 B5.5.51-52): sin ella el motor lo deja en 1,000 y emite "
    "el hallazgo «Ausencia del componente prospectivo».")

NOTA_SIN_MEDIR_NO_SE_NETEA = (
    "Las dos cifras son reales y ninguna sustituye a la otra. La MAGNITUD (B10) suma la exposición "
    "sin medir deudora y la acreedora EN VALOR ABSOLUTO: una banda sin tasa no compensa a otra, "
    "porque ninguna de las dos se midió, y es la cifra que decide si la medición está completa, la "
    "que dispara el hallazgo «Cartera sin tasa histórica» y la que muestra la pantalla. La NETA "
    "(B11) las suma con su signo, y es la única que puede restarse de la cartera ESTRATIFICADA "
    "(B5), que también es neta: por eso «Cartera medida» (B12) sale de B11 y no de B10, y por eso "
    "B12 + B10 NO da B5. Netear las dos bandas antes de declararlas era lo que permitía que "
    "+20.000 sin tasa y -20.000 sin tasa se presentaran como «SIN MEDIR 0,00» sobre 40.000 de "
    "cartera que nadie midió. Para cerrar la diferencia: apruebe una tasa sustituta para esas "
    "bandas, o reclasifique los saldos acreedores a pasivo (anticipos de clientes).")

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

class _Formula(str):
    """Una fórmula ESCRITA POR EL PAPEL: lo único que llega a Excel como fórmula.

    El texto que empieza por «=» es fórmula para `openpyxl`, y el papel escribe
    dos clases de texto que empiezan así: las fórmulas que redacta este módulo
    y el nombre de un cliente, de un archivo o de un documento que redactó el
    CLIENTE. No se pueden distinguir mirando la cadena, así que la marca va en
    el tipo: `_celda` escribe como fórmula lo que sea `_Formula` y **como texto
    todo lo demás**.

    La regla queda del lado seguro por construcción, igual que `motor.acotar`
    obliga a recibir el motivo: un sumidero nuevo que imprima texto del cliente
    queda saneado sin que nadie se acuerde de sanearlo, y quien quiera escribir
    una fórmula tiene que decirlo. Ver `tests/test_pce_saneamiento.py`.
    """

    __slots__ = ()


def _f(formula: str) -> _Formula:
    """Marca una cadena como fórmula del papel (ver `_Formula`)."""
    return _Formula(formula)


def _celda(ws, fila: int, col: int, valor, *, formato: str | None = None,
           alineacion: Alignment | None = None, total: bool = False):
    """Escribe un valor (o una `_Formula`) y aplica el estilo estándar de la hoja.

    TODO texto que no sea `_Formula` se escribe como TEXTO, aunque empiece por
    «=»: se conserva el dato tal cual -un papel que cambia el nombre del deudor
    deja de ser evidencia- y se le quita a Excel la posibilidad de evaluarlo.
    Cuando además empieza por un inicio de fórmula se marca con `quotePrefix`,
    el prefijo de literal de Excel, que es lo que impide que se reinterprete al
    PEGAR la celda en otra hoja.
    """
    if isinstance(valor, str) and not isinstance(valor, _Formula):
        valor = limpiar_texto(valor)
    c = ws.cell(fila, col, valor)
    if isinstance(valor, str) and not isinstance(valor, _Formula):
        c.data_type = "s"
        if empieza_como_formula(valor):
            c.quotePrefix = True
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


def _tramos_visibles(resultado: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Filas de la matriz que dicen algo, y cuántas se dejaron fuera.

    ``service.analizar`` inicializa todas las bandas para los dos segmentos, así
    que la mayoría de las combinaciones sale con exposición 0,00 y sin tasa. Esa
    fila no es una pérdida cero medida (no hay tasa) ni una banda sin medir con
    cartera (no hay exposición): es una combinación que no existe en la cartera,
    y rotularla "SIN MEDIR" diluye la señal de las bandas que sí tienen saldo
    sin medir. Se omite del papel -declarando cuántas, nunca en silencio-; el
    universo completo de bandas queda en ``04-Tasas``.
    """
    tramos = (resultado.get("matriz") or {}).get("tramos") or []
    visibles = [t for t in tramos
                if abs(_numero(t.get("exposicion")) or 0.0) > 0.005
                or t.get("tasa_perdida") is not None]
    return visibles, len(tramos) - len(visibles)


def _numero(valor: Any) -> float | None:
    """``None`` explícito se preserva (banda sin medir); todo lo demás, a float."""
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _como_diccionario(valor: Any) -> dict:
    """Un parámetro que se espera como objeto, tolerando lo que traiga la corrida.

    El exportador lee corridas YA GUARDADAS: sus parámetros no vuelven a pasar
    por la validación de entrada del servicio, así que aquí cualquier forma
    inesperada tiene que dar un papel que dice lo que sabe, nunca un HTTP 500
    al descargar. `x or {}` no alcanzaba: un número o una cadena son
    verdaderos y el `.get` siguiente levantaba `AttributeError`.
    """
    return valor if isinstance(valor, dict) else {}


def _ajustes_prospectivos_de_parametros(valor: Any) -> tuple[float, float]:
    """Ajuste (factor - 1) por segmento leído de los PARÁMETROS de la corrida.

    Admite el escalar de las corridas antiguas -el mismo factor para todos los
    segmentos-, que es exactamente la rama de retrocompatibilidad en la que el
    exportador reventaba con un 500 al llamar `.get` sobre un número.
    """
    if isinstance(valor, dict):
        no_rel = _numero(valor.get("NO-RELACIONADOS"))
        rel = _numero(valor.get("RELACIONADOS"))
        return ((1.0 if no_rel is None else no_rel) - 1.0,
                (1.0 if rel is None else rel) - 1.0)
    unico = _numero(valor) if not isinstance(valor, (bool, list, tuple, set)) else None
    if unico is None:
        return 0.0, 0.0
    return unico - 1.0, unico - 1.0


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

def construir_excel(resultado: dict[str, Any], parametros: dict[str, Any]) -> bytes:
    """Arma el papel de trabajo completo (trece hojas) a partir del resultado
    de ``service.analizar`` y los parámetros con los que se corrió.

    ``resultado`` y ``parametros`` nunca se mutan.

    Las dos entradas se normalizan a diccionario ANTES de tocarlas: el
    exportador lee corridas ya guardadas, cuyos parámetros no vuelven a pasar
    por la validación de entrada del servicio, así que una corrida con
    ``parametros`` en forma de número, cadena o lista tiene que dar un papel
    que dice lo que sabe, nunca un HTTP 500 al descargar.
    """
    resultado = _como_diccionario(resultado)
    parametros = _como_diccionario(parametros)

    wb = Workbook()
    wb.remove(wb.active)

    fecha_texto, marca = _fecha_emision(parametros)
    # Las propiedades del documento se sellan con la fecha de la corrida: por
    # defecto openpyxl pone `datetime.now()`, que vuelve distinto el paquete en
    # cada descarga aunque ninguna celda cambie.
    wb.properties.created = marca
    wb.properties.modified = marca

    refs: dict[str, Any] = {}
    # Se resuelve una sola vez y antes de escribir ninguna hoja: 04-Tasas ordena
    # sus filas igual que 05-Matriz para poder referenciarlas por número de fila.
    visibles, omitidas = _tramos_visibles(resultado)
    refs["tramos_visibles"] = visibles
    refs["tramos_omitidos"] = omitidas

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

    # La fecha del papel es la del CORTE ACTUAL, que es el último de los tres.
    # Las tres llegan en orden cronológico estricto
    # (`cortes.validar_orden_cronologico`), así que `fechas[-1]` es la más
    # reciente por construcción, no por casualidad. El rótulo lo dice: antes
    # imprimía «Fecha de corte» a secas y, con los archivos al revés, esa
    # celda afirmaba como corte la fecha más ANTIGUA de las tres.
    fechas = parametros.get("fechas") or []
    fecha_corte = fechas[-1] if fechas else ""

    _bloque(ws, 3, "Datos generales", 2)
    _encabezados(ws, 4, ["Concepto", "Valor"])
    filas = [
        ("Estado del papel", ESTADO_PRELIMINAR),
        # Una celda vacía se lee como "no aplica": la entidad y su RUC o
        # están, o se declara que no se registraron, igual que "Preparado por"
        # y "Revisado por".
        ("Entidad", str(parametros.get("entidad") or "").strip() or SIN_REGISTRAR),
        ("RUC", str(parametros.get("ruc") or "").strip() or SIN_REGISTRAR),
        ("Fecha de corte (corte actual, t)", fecha_corte),
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
        # Formato nuevo: diccionario por segmento, ya en FACTOR.
        factor_no_relacionados = float(ajuste_valor.get("NO-RELACIONADOS", 1.0))
        factor_relacionados = float(ajuste_valor.get("RELACIONADOS", 1.0))
    elif isinstance(ajuste_valor, (int, float)):
        # Formato antiguo: un escalar que era el AJUSTE (0,05 = factor 1,05),
        # para los dos segmentos. Se traduce a factor aquí, que es la única
        # convención que sale al papel.
        factor_no_relacionados = 1.0 + float(ajuste_valor)
        factor_relacionados = 1.0 + float(ajuste_valor)
    else:
        # No hay ajuste en resultado: leer de parámetros por retrocompatibilidad
        # (admite el escalar de las corridas antiguas; ver
        # `_ajustes_prospectivos_de_parametros`).
        ajuste_no_relacionados, ajuste_relacionados = _ajustes_prospectivos_de_parametros(
            parametros.get("factor_prospectivo"))
        factor_no_relacionados = 1.0 + ajuste_no_relacionados
        factor_relacionados = 1.0 + ajuste_relacionados

    saldo_contable = conciliacion.get("saldo_contable")
    if saldo_contable is None:
        saldo_contable = exposicion.get("segun_archivo")

    # Filas 2 a 8: fijas por posición porque 05-Matriz referencia los nombres
    # definidos FactorProspectivoNoRelacionados / FactorProspectivoRelacionados
    # (y esta función define los otros nombres en las celdas que se documentan
    # abajo).
    # Materialidad y umbral individual son nombres definidos del libro
    # (`Materialidad`, `UmbralIndividual`): su celda NO puede quedar vacía. Una
    # celda vacía se lee como "cero" -y un nombre definido que apunta a una
    # celda vacía es una fórmula que recalcularía a cero sin avisar-, así que
    # el parámetro que no se registró se dice con todas sus letras.
    materialidad = _numero(parametros.get("materialidad"))
    _celda(ws, 2, 1, "Materialidad", alineacion=ALIN_IZQ)
    _celda(ws, 2, 2, SIN_REGISTRAR if materialidad is None else materialidad,
           formato=FORMATO_MONEDA,
           alineacion=ALIN_DER if materialidad is not None else ALIN_CEN)
    _celda(ws, 2, 3, "Definida por el socio del encargo", alineacion=ALIN_IZQ)

    umbral_individual = _numero(parametros.get("umbral_individual"))
    _celda(ws, 3, 1, "Umbral de evaluación individual", alineacion=ALIN_IZQ)
    _celda(ws, 3, 2, SIN_REGISTRAR if umbral_individual is None else umbral_individual,
           formato=FORMATO_MONEDA,
           alineacion=ALIN_DER if umbral_individual is not None else ALIN_CEN)
    _celda(ws, 3, 3, "Definido por el socio del encargo", alineacion=ALIN_IZQ)

    _celda(ws, 4, 1, "Umbral de incumplimiento (días)", alineacion=ALIN_IZQ)
    # `... or 730` convertía en 730 un cero guardado: el papel tiene que
    # reproducir la corrida tal como se emitió, así que solo la AUSENCIA del
    # dato cae al defecto del plan.
    umbral = _numero(bitacora.get("umbral_incumplimiento"))
    _celda(ws, 4, 2, 730 if umbral is None else umbral, formato=FORMATO_ENTERO,
           alineacion=ALIN_DER)
    # El plazo lo fija la entidad. NIIF 9 B5.5.37 presume el incumplimiento a
    # los 90 días de mora y esa presunción es refutable: citarla como si la
    # norma trajera un defecto de 730 días atribuye a la NIIF una decisión que
    # es de la administración y que el papel tiene que sustentar.
    _celda(ws, 4, 3, "Política de la entidad. NIIF 9 B5.5.37 presume el incumplimiento a los "
                     "90 días de mora; es una presunción refutable y la entidad la refuta con "
                     "este plazo, que debe quedar sustentado en el papel.",
           alineacion=ALIN_IZQ)

    # UNA SOLA CONVENCIÓN EN TODO EL LIBRO Y EN LA PANTALLA: el FACTOR por el
    # que se multiplica la tasa observada, donde 1,000 es «sin ajuste». Antes
    # esta celda guardaba `factor - 1` con formato de porcentaje y se rotulaba
    # «Ajuste prospectivo», mientras 05-Matriz llamaba «Factor prospectivo» a
    # la misma magnitud y compensaba con `(1+E)`: dos nombres y dos valores
    # separados por 1,0 para lo mismo. Y esta celda el papel INVITA a editarla,
    # así que declara qué significa su valor.
    _celda(ws, 5, 1, "Factor prospectivo — NO-RELACIONADOS (terceros)", alineacion=ALIN_IZQ)
    _celda(ws, 5, 2, factor_no_relacionados, formato=FORMATO_FACTOR, alineacion=ALIN_DER)
    _celda(ws, 5, 3, NOTA_CONVENCION_FACTOR.format(segmento="NO-RELACIONADOS"),
           alineacion=ALIN_IZQ)

    _celda(ws, 6, 1, "Factor prospectivo — RELACIONADOS", alineacion=ALIN_IZQ)
    _celda(ws, 6, 2, factor_relacionados, formato=FORMATO_FACTOR, alineacion=ALIN_DER)
    _celda(ws, 6, 3, NOTA_CONVENCION_FACTOR.format(segmento="RELACIONADOS"), alineacion=ALIN_IZQ)

    # `SaldoContable` también es nombre definido y `08-Conciliacion` B3 lo
    # referencia cuando la corrida trae EEFF. Sin EEFF ni total del archivo la
    # celda quedaba vacía: se declara, no se deja en blanco (esa hoja rotula su
    # B3 como «SIN EEFF (no conciliado)» en ese mismo caso).
    saldo_contable_numero = _numero(saldo_contable)
    _celda(ws, 7, 1, "Saldo contable (cartera según EEFF, total)", alineacion=ALIN_IZQ)
    _celda(ws, 7, 2, SIN_REGISTRAR if saldo_contable_numero is None else saldo_contable_numero,
           formato=FORMATO_MONEDA,
           alineacion=ALIN_DER if saldo_contable_numero is not None else ALIN_CEN)
    _celda(ws, 7, 3, "Estados financieros auditados", alineacion=ALIN_IZQ)

    _celda(ws, 8, 1, "Justificación del ajuste prospectivo", alineacion=ALIN_IZQ)
    _celda(ws, 8, 2, "", alineacion=ALIN_IZQ)
    _celda(ws, 8, 3, str(parametros.get("justificacion_prospectivo") or "(sin justificación registrada)"),
           alineacion=ALIN_IZQ)

    wb.defined_names.add(DefinedName("Materialidad", attr_text="'01-Parametros'!$B$2"))
    wb.defined_names.add(DefinedName("UmbralIndividual", attr_text="'01-Parametros'!$B$3"))
    wb.defined_names.add(DefinedName("FactorProspectivoNoRelacionados", attr_text="'01-Parametros'!$B$5"))
    wb.defined_names.add(DefinedName("FactorProspectivoRelacionados", attr_text="'01-Parametros'!$B$6"))
    # Alias sin sufijo de segmento: apunta al factor de terceros
    # (NO-RELACIONADOS), el mismo segmento que se usaba como "segmento
    # principal" cuando el ajuste era global. Ya no se llama
    # "AjusteProspectivo": un nombre definido que dice «ajuste» apuntando a una
    # celda que guarda el FACTOR es exactamente la ambigüedad que este cambio
    # cierra.
    wb.defined_names.add(DefinedName("FactorProspectivo", attr_text="'01-Parametros'!$B$5"))
    wb.defined_names.add(DefinedName("SaldoContable", attr_text="'01-Parametros'!$B$7"))

    fila = 10
    _bloque(ws, fila, "Cartera según EEFF por segmento", 3)
    fila += 1
    eeff = _como_diccionario(parametros.get("eeff"))
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
    """Qué se cargó de cada archivo y, sobre todo, qué NO se pudo leer.

    La hoja llevaba «Descartados» como CONTEO y ninguna columna de importe: el
    dinero que el lector no pudo leer no aparecía en ninguna celda de las trece
    hojas, ni siquiera cuando el anclaje a los estados financieros lo repartía
    sobre las filas que sí entraron. Ahora el importe tiene columna propia -con
    su total- y un bloque que lo desglosa por motivo y por archivo.
    """
    ws = wb.create_sheet("02-Fuentes")
    encabezado = ["Archivo", "Rol del corte", "Fecha del corte", "Hoja", "Fila de encabezado",
                  "Mapeo de columnas", "Formato de fecha", "Documentos", "Duplicados exactos",
                  "Documentos repetidos", "Descartados", "Cartera no leída", "Total"]
    _encabezados(ws, 1, encabezado)
    cortes = (resultado.get("bitacora") or {}).get("cortes") or []

    primera = 2
    if cortes:
        ultima = primera + len(cortes) - 1
        for i, corte in enumerate(cortes, start=primera):
            _celda(ws, i, 1, corte.get("archivo", ""), alineacion=ALIN_IZQ)
            # Qué corte es cada fila. El nombre del archivo lo pone el cliente y
            # puede decir cualquier cosa; el rol lo fija la herramienta por la
            # posición, y es lo que da sentido a la cifra de esta fila.
            _celda(ws, i, 2,
                   ROLES_DE_CORTE[i - primera] if i - primera < len(ROLES_DE_CORTE)
                   else "corte adicional", alineacion=ALIN_CEN)
            # La FECHA de este corte, en la misma fila que su rol: el rol lo
            # fija la posición, así que «corte actual (t)» no es contrastable
            # hasta que se lee, al lado, la fecha que el auditor declaró para
            # ese archivo. Las tres van en orden cronológico estricto
            # (`cortes.validar_orden_cronologico`).
            _celda(ws, i, 3, corte.get("fecha", ""), alineacion=ALIN_CEN)
            _celda(ws, i, 4, corte.get("hoja", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 5, corte.get("fila_encabezado"), formato=FORMATO_ENTERO, alineacion=ALIN_CEN)
            _celda(ws, i, 6, _mapeo_texto(corte.get("mapeo")), alineacion=ALIN_IZQ)
            _celda(ws, i, 7, corte.get("formato_fecha", ""), alineacion=ALIN_CEN)
            _celda(ws, i, 8, corte.get("documentos"), formato=FORMATO_ENTERO, alineacion=ALIN_DER)
            _celda(ws, i, 9, corte.get("duplicados_exactos"), formato=FORMATO_ENTERO, alineacion=ALIN_DER)
            _celda(ws, i, 10, corte.get("documentos_repetidos"), formato=FORMATO_ENTERO, alineacion=ALIN_DER)
            _celda(ws, i, 11, corte.get("descartados"), formato=FORMATO_ENTERO, alineacion=ALIN_DER)
            # Importe de las filas que no se pudieron leer (sin las repeticiones
            # idénticas, cuyo saldo ya entró con la primera aparición).
            no_leida = _numero(corte.get("cartera_no_leida"))
            c = _celda(ws, i, 12, 0.0 if no_leida is None else no_leida, formato=FORMATO_MONEDA,
                       alineacion=ALIN_DER)
            if no_leida is not None and abs(no_leida) > 0.005:
                c.font = FUENTE_DATOS_ALERTA
            _celda(ws, i, 13, _numero(corte.get("total")), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    else:
        ultima = primera
        _celda(ws, primera, 1, "(sin cortes registrados en la bitácora de esta corrida)", alineacion=ALIN_IZQ)
        for col in range(2, 14):
            _celda(ws, primera, col, None, alineacion=ALIN_IZQ)

    # NO HAY TOTAL QUE SUMAR. Cada fila es un corte con SU PROPIA fecha: la
    # cartera no leída de t-2, la de t-1 y la de t son tres magnitudes
    # distintas, y netearlas presentaba bajo el rótulo «lo que no se pudo leer»
    # una cifra que no existe en ningún corte. Lo mismo vale para el total de
    # cada archivo.
    fila_total = ultima + 1
    _celda(ws, fila_total, 11, "TOTAL", total=True, alineacion=ALIN_IZQ)
    _celda(ws, fila_total, 12, NO_SUMABLE_ENTRE_CORTES, total=True, alineacion=ALIN_CEN)
    _celda(ws, fila_total, 13, NO_SUMABLE_ENTRE_CORTES, total=True, alineacion=ALIN_CEN)
    for col in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
        _celda(ws, fila_total, col, None, total=True)

    nota = ws.cell(fila_total + 1, 1, NOTA_CORTES_NO_SUMABLES)
    nota.font = FUENTE_DATOS
    nota.alignment = ALIN_IZQ
    ws.merge_cells(start_row=fila_total + 1, start_column=1, end_row=fila_total + 1, end_column=13)
    ws.row_dimensions[fila_total + 1].height = 42

    fila = _descartes_por_motivo(ws, cortes, fila_total + 3)
    _control_corte_intermedio(ws, resultado, fila + 1)

    _anchos(ws, {"A": 22, "B": 22, "C": 16, "D": 16, "E": 12, "F": 40, "G": 16, "H": 12, "I": 14,
                 "J": 16, "K": 12, "L": 18, "M": 16})


def _descartes_por_motivo(ws, cortes: list[dict[str, Any]], fila: int) -> int:
    """Bloque con el importe que no se pudo leer, archivo por archivo y motivo
    por motivo.

    Un conteo no dice cuánta cartera se perdió ni por qué. Si no hubo descartes
    se dice eso: un bloque ausente se lee como "no aplica".
    """
    _bloque(ws, fila, "Detalle de lo descartado en la lectura (importe, no solo conteo)", 13)
    fila += 1
    detalle = [(c, m) for c in cortes for m in (c.get("descartados_por_motivo") or [])]
    if not detalle:
        _celda(ws, fila, 1, "Ninguna fila se descartó en la lectura de los tres cortes: la "
                            "cartera medida es la cartera completa de cada archivo.",
               alineacion=ALIN_IZQ)
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=13)
        return fila + 1

    congelado = ws.freeze_panes
    _encabezados(ws, fila, ["Archivo", "Motivo del descarte", "Filas", "Importe"])
    ws.freeze_panes = congelado
    fila += 1
    for corte, motivo in detalle:
        _celda(ws, fila, 1, corte.get("archivo", ""), alineacion=ALIN_IZQ)
        _celda(ws, fila, 2, str(motivo.get("motivo", "")), alineacion=ALIN_IZQ)
        _celda(ws, fila, 3, _numero(motivo.get("filas")), formato=FORMATO_ENTERO,
               alineacion=ALIN_DER)
        importe = _numero(motivo.get("importe"))
        c = _celda(ws, fila, 4, 0.0 if importe is None else importe, formato=FORMATO_MONEDA,
                   alineacion=ALIN_DER)
        if importe is not None and abs(importe) > 0.005:
            c.font = FUENTE_DATOS_ALERTA
        fila += 1
    nota = ws.cell(fila, 1,
                   "Las filas idénticas repetidas no restan cartera (su saldo ya entró con la "
                   "primera aparición) y por eso no suman en «Cartera no leída». El resto sí: "
                   "esa cartera no se midió, y con anclaje a los estados financieros su importe "
                   "se reparte sobre las filas que sí se leyeron.")
    nota.font = FUENTE_DATOS
    nota.alignment = ALIN_IZQ
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=13)
    ws.row_dimensions[fila].height = 30
    return fila + 1


TIPOS_INCONSISTENCIA = {
    "reaparece_tras_desaparecer": "Desaparece en el corte intermedio y reaparece en el actual",
    "remanente_mayor_que_intermedio": "El saldo del corte actual supera al del corte intermedio",
}


def _control_corte_intermedio(ws, resultado: dict[str, Any], fila: int) -> int:
    """Bloque de ``02-Fuentes`` con el control de la cohorte contra el corte t-1.

    El corte intermedio se le pide al cliente: el papel tiene que decir para
    qué sirvió. Si no se registró (corridas anteriores a este control) se dice
    eso, no se deja el hueco -un bloque ausente se lee como "no aplica"-.
    """
    control = resultado.get("control_corte_intermedio")
    _bloque(ws, fila, "Control del corte intermedio (coherencia de la cohorte entre los tres cortes)", 10)
    fila += 1
    if not control:
        _celda(ws, fila, 1, "El control del corte intermedio no se registró en esta corrida.",
               alineacion=ALIN_IZQ)
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=10)
        return fila + 1

    resumen = [
        ("Documentos de la cohorte (t-2)", control.get("documentos_cohorte"), FORMATO_ENTERO),
        ("Saldo inicial de la cohorte", _numero(control.get("saldo_cohorte")), FORMATO_MONEDA),
        ("Documentos todavía vivos en el corte intermedio (t-1)",
         control.get("vivos_en_intermedio"), FORMATO_ENTERO),
        ("Saldo de la cohorte en el corte intermedio (t-1)",
         _numero(control.get("saldo_en_intermedio")), FORMATO_MONEDA),
        ("Saldo de la cohorte en el corte actual (t) — remanente medido",
         _numero(control.get("saldo_en_actual")), FORMATO_MONEDA),
    ]
    for etiqueta, valor, formato in resumen:
        _celda(ws, fila, 1, etiqueta, alineacion=ALIN_IZQ)
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=4)
        _celda(ws, fila, 5, valor, formato=formato, alineacion=ALIN_DER)
        fila += 1

    if control.get("consistente"):
        _celda(ws, fila, 1, "Sin inconsistencias: ningún documento de la cohorte desaparece y "
                            "reaparece, ni crece de saldo entre el corte intermedio y el actual.",
               alineacion=ALIN_IZQ)
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=10)
        return fila + 1

    c = _celda(ws, fila, 1,
               f"{control.get('inconsistencias_total')} documento(s) con trayectoria imposible "
               f"entre los tres cortes; USD {_numero(control.get('inconsistencias_importe')) or 0:,.2f} "
               "del remanente que alimenta las tasas provienen de ellos.", alineacion=ALIN_IZQ)
    c.font = FUENTE_DATOS_ALERTA
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=10)
    fila += 1

    # `_encabezados` congela paneles; este es un bloque interior, así que se
    # conserva el congelado de la cabecera de la hoja.
    congelado = ws.freeze_panes
    _encabezados(ws, fila, ["Documento", "Inconsistencia", "Saldo en t-2", "Saldo en t-1",
                            "Saldo en t"])
    ws.freeze_panes = congelado
    fila += 1
    for caso in control.get("inconsistencias") or []:
        _celda(ws, fila, 1, caso.get("documento", ""), alineacion=ALIN_IZQ)
        _celda(ws, fila, 2, TIPOS_INCONSISTENCIA.get(caso.get("tipo"), caso.get("tipo", "")),
               alineacion=ALIN_IZQ)
        _celda(ws, fila, 3, _numero(caso.get("saldo_cohorte")), formato=FORMATO_MONEDA,
               alineacion=ALIN_DER)
        _celda(ws, fila, 4, _numero(caso.get("saldo_intermedio")), formato=FORMATO_MONEDA,
               alineacion=ALIN_DER)
        _celda(ws, fila, 5, _numero(caso.get("saldo_actual")), formato=FORMATO_MONEDA,
               alineacion=ALIN_DER)
        fila += 1
    if control.get("inconsistencias_total", 0) > len(control.get("inconsistencias") or []):
        _celda(ws, fila, 1, f"(se listan los primeros {len(control['inconsistencias'])} de "
                            f"{control['inconsistencias_total']})", alineacion=ALIN_IZQ)
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=10)
        fila += 1
    return fila


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
            _celda(ws, i, 6, _f(f"=D{i}-E{i}"), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    else:
        ultima = primera
        _celda(ws, primera, 1, "(sin bandas en la cohorte de esta corrida)", alineacion=ALIN_IZQ)
        for col in range(2, 7):
            _celda(ws, primera, col, None)

    fila_total = ultima + 1
    _celda(ws, fila_total, 2, "TOTAL", total=True, alineacion=ALIN_IZQ)
    _celda(ws, fila_total, 1, None, total=True)
    _celda(ws, fila_total, 3, _f(f"=SUM(C{primera}:C{ultima})"), formato=FORMATO_ENTERO, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 4, _f(f"=SUM(D{primera}:D{ultima})"), formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 5, _f(f"=SUM(E{primera}:E{ultima})"), formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 6, _f(f"=SUM(F{primera}:F{ultima})"), formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)

    _anchos(ws, {"A": 22, "B": 20, "C": 14, "D": 18, "E": 18, "F": 16})
    refs["cohorte"] = {"pares": pares, "primera": primera, "ultima": ultima, "hay_datos": bool(pares)}


def _nota_anomalia(anomalia: dict[str, Any]) -> str:
    """Por qué la tasa observada de esa banda se acotó, con las cifras a la vista."""
    inicial = _numero(anomalia.get("inicial")) or 0.0
    remanente = _numero(anomalia.get("remanente")) or 0.0
    bruta = _numero(anomalia.get("tasa_bruta")) or 0.0
    if anomalia.get("tipo") == "remanente_negativo":
        return (f"Tasa acotada al 0 %: el remanente al corte resultó negativo ({remanente:,.2f}) "
                f"sobre un saldo inicial de cohorte de {inicial:,.2f} (ratio crudo {bruta:,.2%}). "
                f"El origen del signo (notas de crédito imputadas al mismo documento, error de "
                f"carga) debe explicarse antes de aceptar la matriz.")
    return (f"Tasa acotada al 100 %: el remanente al corte ({remanente:,.2f}) superó el saldo "
            f"inicial de la cohorte ({inicial:,.2f}); el ratio crudo es {bruta:,.2%}. El origen "
            f"del incremento (nueva facturación reclasificada al mismo documento, reversión, "
            f"error de carga) debe explicarse antes de aceptar la matriz.")


def _tasas(wb: Workbook, resultado: dict[str, Any], parametros: dict[str, Any], refs: dict[str, Any]) -> None:
    """Una fila por cada banda que el papel tiene que sustentar.

    Tres correcciones conviven aquí:

    - El origen sigue la misma precedencia que ``service.analizar``: la tasa
      sustituida con justificación escrita manda sobre la observada. Antes era
      al revés, así que una sustitución justificada se presentaba como
      "Observada" y su justificación -la única evidencia del cambio- no se
      escribía en ninguna parte del papel.
    - La tasa aplicada es exactamente la que usa ``05-Matriz``, que la
      referencia desde aquí: una sola cifra por banda en todo el libro. Cuando
      sale de la cohorte se escribe como fórmula acotada entre 0 y 1, igual que
      ``cohortes.tasas_por_permanencia``; el ratio crudo se conserva en su
      propia columna porque es la evidencia de la que salió el acotamiento.
    - Las filas son el universo completo: todas las bandas de ``05-Matriz``
      -incluidas las que no tienen historia y el papel tiene que argumentar-
      más las que solo existen en la cohorte.
    """
    ws = wb.create_sheet("04-Tasas")
    _encabezados(ws, 1, ["Segmento", "Banda", "Ratio observado en la cohorte (remanente / inicial)",
                         "Tasa aplicada (la que usa 05-Matriz)", "Origen", "Justificación o nota"])
    tasas = resultado.get("tasas") or {}
    sustitutas = _como_diccionario(parametros.get("tasas_sustitutas"))
    anomalias = resultado.get("anomalias") or []
    cohorte_refs = refs.get("cohorte") or {}
    pares_cohorte = list(cohorte_refs.get("pares") or []) if cohorte_refs.get("hay_datos") else []
    primera_cohorte = cohorte_refs.get("primera", 2)

    # Mismo orden que 05-Matriz para que esa hoja referencie por número de fila.
    filas: list[tuple[str, str, dict[str, Any] | None]] = [
        (str(t.get("segmento") or ""), str(t.get("tramo") or ""), t)
        for t in (refs.get("tramos_visibles") or [])
    ]
    ya = {(s, b) for s, b, _ in filas}
    filas += [(s, b, None) for (s, b) in pares_cohorte if (s, b) not in ya]

    primera = 2
    filas_por_par: dict[tuple[str, str], int] = {}

    if filas:
        ultima = primera + len(filas) - 1
        for i, (segmento, banda, tramo) in zip(range(primera, ultima + 1), filas):
            filas_por_par.setdefault((segmento, banda), i)
            observada = (tasas.get(segmento) or {}).get(banda)
            sustituta = _como_diccionario(sustitutas.get(f"{segmento}|{banda}"))
            sustituida = bool(sustituta and str(sustituta.get("justificacion", "")).strip())
            anomalia = next((a for a in anomalias if a.get("segmento") == segmento
                             and a.get("banda") == banda), None)
            try:
                fila_coh = primera_cohorte + pares_cohorte.index((segmento, banda))
            except ValueError:
                fila_coh = None

            _celda(ws, i, 1, segmento, alineacion=ALIN_IZQ)
            _celda(ws, i, 2, banda, alineacion=ALIN_IZQ)
            # Ratio empírico de la cohorte, SIN acotar: es la evidencia. Guardado
            # con IF (no IFERROR: fuera de las funciones permitidas) para no
            # mostrar #¡DIV/0! cuando la banda no tuvo cartera inicial.
            if fila_coh is not None:
                _celda(ws, i, 3,
                       _f(f'=IF(\'03-Cohorte\'!D{fila_coh}=0,"SIN BASE",'
                       f'\'03-Cohorte\'!E{fila_coh}/\'03-Cohorte\'!D{fila_coh})'),
                       formato=FORMATO_PORCENTAJE, alineacion=ALIN_DER)
            else:
                _celda(ws, i, 3, "SIN COHORTE", alineacion=ALIN_CEN)

            # La tasa aplicada la manda el motor (`tasa_perdida` del tramo): así
            # 04-Tasas y 05-Matriz no pueden discrepar. Para una banda que solo
            # existe en la cohorte no hay tramo, y se documenta la que se
            # aplicaría.
            if tramo is not None:
                aplicada = _numero(tramo.get("tasa_perdida"))
            elif sustituida:
                aplicada = _numero(sustituta.get("tasa"))
            else:
                aplicada = _numero(observada)

            nota = ""
            if aplicada is None:
                origen = SEGMENTOS_TEXTO
                _celda(ws, i, 4, SEGMENTOS_TEXTO, alineacion=ALIN_CEN)
                if fila_coh is None:
                    nota = ("La cohorte no registra documentos en esta banda: sin historia propia "
                            "no se asume una tasa (NIIF 9 B5.5.35). Resuélvase por analogía con un "
                            "segmento comparable, dejando constancia, o declárese la limitación.")
                else:
                    nota = ("La cohorte no tiene cartera inicial en esta banda: no hay ratio que "
                            "calcular y no se asume una tasa (NIIF 9 B5.5.35).")
            elif sustituida:
                origen = "Sustituida"
                nota = str(sustituta.get("justificacion", ""))
                _celda(ws, i, 4, aplicada, formato=FORMATO_PORCENTAJE, alineacion=ALIN_DER)
            else:
                origen = "Observada"
                if anomalia is not None:
                    origen = ("Observada (acotada al 0 %)"
                              if anomalia.get("tipo") == "remanente_negativo"
                              else "Observada (acotada al 100 %)")
                    nota = _nota_anomalia(anomalia)
                # Solo se escribe como fórmula si la tasa aplicada es la misma
                # que se reconstruye desde 03-Cohorte; si no, manda el valor.
                if (fila_coh is not None and observada is not None
                        and abs(float(observada) - aplicada) < 1e-12):
                    _celda(ws, i, 4,
                           _f(f'=IF(C{i}="SIN BASE","SIN MEDIR",IF(C{i}>1,1,IF(C{i}<0,0,C{i})))'),
                           formato=FORMATO_PORCENTAJE, alineacion=ALIN_DER)
                else:
                    _celda(ws, i, 4, aplicada, formato=FORMATO_PORCENTAJE, alineacion=ALIN_DER)

            if tramo is None and aplicada is not None:
                nota = (f"{nota} Banda sin exposición en el corte actual: la tasa queda "
                        f"documentada pero no se aplica en 05-Matriz.").strip()

            _celda(ws, i, 5, origen, alineacion=ALIN_CEN)
            _celda(ws, i, 6, nota, alineacion=ALIN_IZQ)
    else:
        ultima = primera
        _celda(ws, primera, 1, "(sin bandas en la cohorte ni en la matriz de esta corrida)",
               alineacion=ALIN_IZQ)
        for col in range(2, 7):
            _celda(ws, primera, col, None)

    _anchos(ws, {"A": 22, "B": 20, "C": 22, "D": 20, "E": 26, "F": 56})
    refs["tasas"] = {"primera": primera, "ultima": ultima, "col_aplicada": "D",
                     "filas_por_par": filas_por_par}


# ---------------------------------------------------------------------------
# 05-Matriz — el corazón auditable del papel: FactorProspectivoNoRelacionados
# y FactorProspectivoRelacionados son nombres definidos en 01-Parametros; cada
# fila resuelve el que corresponde a SU segmento (columna A de esa fila), así
# que cambiar cualquiera de los dos valores en Excel recalcula solo las bandas
# de ese segmento -nunca las del otro-.
# ---------------------------------------------------------------------------

def _matriz(wb: Workbook, resultado: dict[str, Any], refs: dict[str, Any]) -> None:
    """Matriz de provisiones, con TODOS los factores del motor DENTRO de la fórmula.

    La columna H (pérdida esperada) reproduce ``motor.medir_ecl`` celda a celda:

        H = MIN(MAX(ROUND(exposición × MIN(tasa × factor; 1) × LGD × FD; 2); 0);
                MAX(exposición; 0))

    - ``MIN(tasa × factor; 1)`` es el techo de la tasa ajustada (``motor.py``:
      ``acotar(tasa_ajustada_bruta, techo=1.0)``). El FACTOR es el de
      ``01-Parametros``, con la convención que declara esa celda: 1,000 es
      «sin ajuste». Es una sola convención en todo el libro y en la pantalla;
      antes esta columna se llamaba «Factor prospectivo» y leía una celda que
      guardaba el factor MENOS UNO, así que las dos hojas nombraban la misma
      magnitud con 1,0 de diferencia.
    - ``× LGD × FD`` son la severidad de la pérdida y el factor de descuento.
      El servicio fija hoy ``lgd = 1.0`` y no descuenta, así que omitirlos no
      cambiaba ninguna cifra: por eso la divergencia estaba DORMIDA, y se
      habría despertado en silencio el día que la LGD dejara de ser 1. Van en
      columnas propias -como el factor prospectivo- para que cambiarlas en
      Excel recalcule la banda.
    - ``MAX(...; 0)`` es el piso cero: una nota de crédito deja la banda con
      exposición acreedora y su "pérdida" negativa neutralizaría la pérdida
      medida en las demás bandas del mismo segmento.
    - ``MIN(...; MAX(exposición; 0))`` es el techo del importe en libros bruto
      (NIIF 9 B5.5.35). Con los valores que escribe la herramienta no puede
      morder -la tasa va acotada al 100 %, la LGD validada en [0, 1] y el
      factor de descuento en (0, 1]-, pero las columnas del factor, la LGD y
      el descuento están para que el revisor las cambie, y ahí sí muerde: la
      columna J lo distingue del techo de la tasa comprobando si el producto ya
      acotado por la tasa supera la exposición.

    La columna I conserva el cálculo SIN acotar -que es la evidencia de que el
    acotamiento hizo falta- y la J declara cuál actuó.
    """
    ws = wb.create_sheet("05-Matriz")
    _encabezados(ws, 1, ["Segmento", "Banda", "Exposición", "Tasa aplicada", "Factor prospectivo",
                         "LGD", "Factor de descuento", "Pérdida esperada", "Pérdida sin acotar",
                         "Acotamiento aplicado"])
    tramos = refs.get("tramos_visibles") or []
    omitidas = refs.get("tramos_omitidos") or 0
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
                _celda(ws, i, 6, "", alineacion=ALIN_CEN)
                _celda(ws, i, 7, "", alineacion=ALIN_CEN)
                _celda(ws, i, 8, "SIN MEDIR", alineacion=ALIN_CEN)
                _celda(ws, i, 9, "SIN MEDIR", alineacion=ALIN_CEN)
                _celda(ws, i, 10, "SIN MEDIR", alineacion=ALIN_CEN)
                continue
            # La tasa vive en 04-Tasas y aquí se referencia: una sola cifra por
            # banda en todo el libro, y corregirla allá recalcula la matriz.
            tasas_refs = refs.get("tasas") or {}
            fila_tasa = (tasas_refs.get("filas_por_par") or {}).get(
                (str(t.get("segmento") or ""), str(t.get("tramo") or "")))
            if fila_tasa:
                _celda(ws, i, 4, _f(f"='04-Tasas'!{tasas_refs['col_aplicada']}{fila_tasa}"),
                       formato=FORMATO_PORCENTAJE, alineacion=ALIN_DER)
            else:
                _celda(ws, i, 4, _numero(t["tasa_perdida"]), formato=FORMATO_PORCENTAJE,
                       alineacion=ALIN_DER)
            # El factor prospectivo es por segmento: se resuelve el nombre
            # definido según el segmento de ESTA fila (columna A), no un
            # nombre único compartido por toda la matriz.
            _celda(ws, i, 5, _f(f'=IF(A{i}="RELACIONADOS",FactorProspectivoRelacionados,'
                             f'FactorProspectivoNoRelacionados)'),
                   formato=FORMATO_FACTOR, alineacion=ALIN_DER)
            # LGD y factor de descuento: los dos factores que el motor aplica y
            # la fórmula omitía. Una corrida anterior a estos campos no afirmó
            # "1": no los guardó, y el papel lo dice en vez de suponerlos.
            lgd = _numero(t.get("lgd"))
            factor_descuento = _numero(t.get("factor_descuento"))
            _celda(ws, i, 6, NO_REGISTRADO if lgd is None else lgd,
                   formato=FORMATO_PORCENTAJE,
                   alineacion=ALIN_DER if lgd is not None else ALIN_CEN)
            _celda(ws, i, 7, NO_REGISTRADO if factor_descuento is None else factor_descuento,
                   formato="0.000000",
                   alineacion=ALIN_DER if factor_descuento is not None else ALIN_CEN)
            # Sin los dos factores registrados la fórmula no puede referenciar
            # sus celdas (serían texto en una multiplicación): la corrida
            # antigua se mide como se midió, con los dos en 1.
            severidad = f"*F{i}*G{i}" if lgd is not None and factor_descuento is not None else ""
            # Pérdida esperada CON los acotamientos de la norma, igual que
            # `motor.medir_ecl` (ver el docstring de esta función). ROUND de
            # Excel redondea medio hacia afuera del cero, el mismo criterio
            # contable de `motor.redondear`.
            _celda(ws, i, 8,
                   _f(f"=MIN(MAX(ROUND(C{i}*MIN(D{i}*E{i},1){severidad},2),0),MAX(C{i},0))"),
                   formato=FORMATO_MONEDA, alineacion=ALIN_DER)
            # El cálculo puro, sin acotar: es la evidencia de cuánto separó el
            # acotamiento y la única forma de que el revisor lo vea.
            _celda(ws, i, 9, _f(f"=ROUND(C{i}*D{i}*E{i}{severidad},2)"), formato=FORMATO_MONEDA,
                   alineacion=ALIN_DER)
            # CUÁL de las tres cotas actuó, deducido de las celdas y no de lo
            # que el motor concluyó: las columnas LGD (F) y Factor de descuento
            # (G) existen para que el revisor las cambie, y con ellas el techo
            # del importe en libros -que con los valores del motor no puede
            # morder- sí muerde. Comparar solo H contra I no los distingue: las
            # dos cotas bajan la cifra. Se reconoce el techo comprobando si el
            # producto YA ACOTADO POR LA TASA supera la exposición; si no,
            # lo que bajó la cifra fue la tasa.
            producto_con_tasa_acotada = f"ROUND(C{i}*MIN(D{i}*E{i},1){severidad},2)"
            _celda(ws, i, 10,
                   _f(f'=IF(H{i}>I{i}+0.005,"{ACOTADO_PISO}",'
                   f'IF(H{i}<I{i}-0.005,'
                   f'IF({producto_con_tasa_acotada}>MAX(C{i},0)+0.005,'
                   f'"{ACOTADO_TECHO}","{ACOTADO_TASA}"),'
                   f'"{SIN_ACOTAR}"))'),
                   alineacion=ALIN_CEN)
    else:
        ultima = primera
        _celda(ws, primera, 1, "(sin tramos medidos en esta corrida)", alineacion=ALIN_IZQ)
        for col in range(2, 11):
            _celda(ws, primera, col, None)

    fila_total = ultima + 1
    _celda(ws, fila_total, 2, "TOTAL", total=True, alineacion=ALIN_IZQ)
    _celda(ws, fila_total, 1, None, total=True)
    _celda(ws, fila_total, 3, _f(f"=SUM(C{primera}:C{ultima})"), formato=FORMATO_MONEDA, total=True,
           alineacion=ALIN_DER)
    for col in (4, 5, 6, 7):
        _celda(ws, fila_total, col, None, total=True)
    _celda(ws, fila_total, 8, _f(f"=SUM(H{primera}:H{ultima})"), formato=FORMATO_MONEDA, total=True,
           alineacion=ALIN_DER)
    _celda(ws, fila_total, 9, _f(f"=SUM(I{primera}:I{ultima})"), formato=FORMATO_MONEDA, total=True,
           alineacion=ALIN_DER)
    _celda(ws, fila_total, 10, None, total=True)

    nota = ws.cell(fila_total + 2, 1, NOTA_ACOTAMIENTOS)
    nota.font = FUENTE_DATOS
    nota.alignment = ALIN_IZQ
    ws.merge_cells(start_row=fila_total + 2, start_column=1, end_row=fila_total + 2, end_column=10)
    ws.row_dimensions[fila_total + 2].height = 42

    if omitidas:
        c = ws.cell(fila_total + 4, 1,
                    f"Nota: {omitidas} combinaciones de segmento × banda no se listan por estar "
                    "sin exposición ni tasa observada. No son una pérdida cero medida: son "
                    "combinaciones que no existen en la cartera del corte. El universo completo "
                    "de bandas, con o sin historia, está en 04-Tasas.")
        c.font = FUENTE_DATOS
        c.alignment = ALIN_IZQ
        ws.merge_cells(start_row=fila_total + 4, start_column=1, end_row=fila_total + 4, end_column=10)
        ws.row_dimensions[fila_total + 4].height = 30

    _anchos(ws, {"A": 20, "B": 26, "C": 18, "D": 16, "E": 18, "F": 12, "G": 18, "H": 18, "I": 18,
                 "J": 34})
    refs["matriz"] = {"primera": primera, "ultima": ultima, "fila_total": fila_total,
                      "col_exposicion": "C", "col_banda": "B", "col_perdida": "H",
                      "col_lgd": "F", "col_descuento": "G",
                      "col_sin_acotar": "I", "col_acotamiento": "J"}


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


def _acotamiento_caso(caso: dict[str, Any]) -> str:
    """Qué cota de la norma movió la pérdida de este caso, si es que alguna.

    Una corrida anterior al campo `acotado` NO afirmó «sin acotar»: no guardó
    el dato. Decirlo es lo mismo que ya hace la columna de la recuperación
    estimada con su propio caso de retrocompatibilidad.
    """
    if "acotado" not in caso:
        return NO_REGISTRADO
    return {PISO_CERO: ACOTADO_PISO,
            TECHO_SALDO: ACOTADO_TECHO}.get(caso.get("acotado") or "", SIN_ACOTAR)


def _individual(wb: Workbook, resultado: dict[str, Any], refs: dict[str, Any]) -> None:
    """Saldos medidos uno por uno, con su saldo acreedor y sus acotamientos a la vista.

    Una nota de crédito dentro de un cliente de evaluación individual quedaba
    escondida: su saldo NETO era deudor, así que no entraba en «saldos
    acreedores» y el piso cero actuaba sobre ella sin que ninguna hoja ni
    ningún hallazgo lo dijeran. Aquí tiene columna propia -sumable, no dentro
    de una frase-, igual que la tiene en la matriz colectiva.

    EL SALDO SIN MEDIR SE ACOTA EN LA FÓRMULA, no fuera de ella:

        F = MIN(MAX(saldo sin medir sin acotar; 0); MAX(exposición del caso; 0))

    que es exactamente `motor.acotar_saldo_sin_medir`. La exposición de un
    cliente es el NETO de sus bandas y lo sin medir suma solo las positivas,
    así que un cliente con 300.000 en una banda sin tasa y una nota de crédito
    de 100.000 en otra declaraba 300.000 sin medir sobre 200.000 de exposición.
    La columna G conserva el importe SIN ACOTAR -la evidencia de que la cota
    hizo falta- y la J declara que actuó.
    """
    ws = wb.create_sheet("06-Individual")
    _encabezados(ws, 1, ["Cliente", "Segmento", "Exposición", "Recuperación estimada",
                         "Pérdida esperada", "Saldo sin medir",
                         "Saldo sin medir SIN ACOTAR", "Saldo acreedor incluido",
                         "Acotamiento de la pérdida", "Acotamiento del saldo sin medir",
                         "Sustento", "Estado"])
    casos = (resultado.get("individual") or {}).get("casos") or []
    primera = 2

    if casos:
        ultima = primera + len(casos) - 1
        for i, caso in zip(range(primera, ultima + 1), casos):
            cliente, segmento = _partir_identificacion(caso.get("identificacion", ""))
            _celda(ws, i, 1, cliente, alineacion=ALIN_IZQ)
            _celda(ws, i, 2, segmento, alineacion=ALIN_IZQ)
            _celda(ws, i, 3, _numero(caso.get("saldo")), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
            # La PCE es el dato medido (una estimación propia justificada o la
            # medición provisional con las tasas de la matriz) y la recuperación
            # la deriva el servicio como saldo - PCE. El papel deriva la misma
            # cifra en vez de recalcular la PCE: `motor.evaluar_individual`
            # redondea los tres importes por separado, así que C - D podía dar
            # un centavo más que la PCE persistida, y 09-Tributario se construye
            # sobre esta columna.
            ecl = _numero(caso.get("ecl"))
            if ecl is None:
                # Corridas antiguas que no guardaron la PCE del caso.
                _celda(ws, i, 4, _numero(caso.get("recuperacion_estimada")), formato=FORMATO_MONEDA,
                       alineacion=ALIN_DER)
                _celda(ws, i, 5, _f(f"=C{i}-D{i}"), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
            else:
                _celda(ws, i, 4, _f(f"=C{i}-E{i}"), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
                _celda(ws, i, 5, ecl, formato=FORMATO_MONEDA, alineacion=ALIN_DER)
            # `saldo_sin_tasa` viaja en el resultado desde que se le dio campo
            # propio, pero el papel solo lo dejaba dentro de la frase del
            # sustento: aquí es una columna sumable y, además, RECALCULADA
            # desde el importe sin acotar de la columna G.
            sin_medir = _numero(caso.get("saldo_sin_tasa"))
            sin_acotar = _numero(caso.get("saldo_sin_tasa_sin_acotar"))
            if sin_acotar is None:
                # Corridas anteriores al campo: se imprime lo que sí guardaron
                # y se dice que el importe sin acotar no se registró, en vez de
                # afirmar que coincidían.
                c = _celda(ws, i, 6, 0.0 if sin_medir is None else sin_medir,
                           formato=FORMATO_MONEDA, alineacion=ALIN_DER)
                _celda(ws, i, 7, NO_REGISTRADO, alineacion=ALIN_CEN)
                _celda(ws, i, 10, NO_REGISTRADO, alineacion=ALIN_CEN)
            else:
                c = _celda(ws, i, 6, _f(f"=MIN(MAX(G{i},0),MAX(C{i},0))"), formato=FORMATO_MONEDA,
                           alineacion=ALIN_DER)
                _celda(ws, i, 7, sin_acotar, formato=FORMATO_MONEDA, alineacion=ALIN_DER)
                # Las DOS cotas del saldo sin medir, distinguidas desde las
                # celdas: el piso cero (un saldo sin medir acreedor se lleva a
                # 0,00) y el techo de la exposición del caso. Antes solo se
                # miraba el techo, así que el piso movía el importe y la
                # columna decía «SIN ACOTAR».
                d = _celda(ws, i, 10,
                           _f('=IF(F{0}>G{0}+0.005,"{1}",IF(F{0}<G{0}-0.005,"{2}","{3}"))'.format(
                               i, ACOTADO_PISO, ACOTADO_EXPOSICION_CASO, SIN_ACOTAR)),
                           alineacion=ALIN_CEN)
                if caso.get("saldo_sin_tasa_acotado"):
                    d.font = FUENTE_DATOS_ALERTA
            if (sin_medir or 0.0) > 0.005:
                c.font = FUENTE_DATOS_ALERTA
            # Corridas anteriores a la columna: el papel dice que el dato no se
            # registró, no que valga 0,00.
            acreedor = _numero(caso.get("saldo_acreedor"))
            if "saldo_acreedor" not in caso or acreedor is None:
                _celda(ws, i, 8, NO_REGISTRADO, alineacion=ALIN_CEN)
            else:
                c = _celda(ws, i, 8, acreedor, formato=FORMATO_MONEDA, alineacion=ALIN_DER)
                if acreedor < -0.005:
                    c.font = FUENTE_DATOS_ALERTA
            c = _celda(ws, i, 9, _acotamiento_caso(caso), alineacion=ALIN_CEN)
            if caso.get("acotado"):
                c.font = FUENTE_DATOS_ALERTA
            _celda(ws, i, 11, caso.get("sustento", ""), alineacion=ALIN_IZQ)
            _celda(ws, i, 12, _estado_caso(caso), alineacion=ALIN_IZQ)
    else:
        ultima = primera
        _celda(ws, primera, 1, "(sin saldos evaluados individualmente en esta corrida)",
               alineacion=ALIN_IZQ)
        for col in range(2, 13):
            _celda(ws, primera, col, None)

    fila_total = ultima + 1
    _celda(ws, fila_total, 1, "TOTAL", total=True, alineacion=ALIN_IZQ)
    _celda(ws, fila_total, 2, None, total=True)
    for col in "CDEFGH":
        _celda(ws, fila_total, ord(col) - 64, _f(f"=SUM({col}{primera}:{col}{ultima})"),
               formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    for col in (9, 10, 11, 12):
        _celda(ws, fila_total, col, None, total=True)

    nota = ws.cell(fila_total + 2, 1, NOTA_SIN_MEDIR_INDIVIDUAL)
    nota.font = FUENTE_DATOS
    nota.alignment = ALIN_IZQ
    ws.merge_cells(start_row=fila_total + 2, start_column=1, end_row=fila_total + 2, end_column=12)
    ws.row_dimensions[fila_total + 2].height = 42

    _anchos(ws, {"A": 24, "B": 18, "C": 16, "D": 18, "E": 16, "F": 16, "G": 22, "H": 20,
                 "I": 34, "J": 36, "K": 40, "L": 26})
    refs["individual"] = {"primera": primera, "ultima": ultima, "fila_total": fila_total,
                          "col_exposicion": "C", "col_perdida": "E", "col_sin_medir": "F",
                          "col_sin_medir_sin_acotar": "G", "col_acreedor": "H",
                          "col_acotamiento": "I", "col_acotamiento_sin_medir": "J"}


# ---------------------------------------------------------------------------
# 07-Politica
# ---------------------------------------------------------------------------

def _politica(wb: Workbook, resultado: dict[str, Any], refs: dict[str, Any]) -> None:
    """Contrasta la política de deterioro del cliente contra la matriz medida.

    Una banda cuya tasa de política NO se ingresó no vale 0 %: se rotula
    ``SIN COMPARAR`` y se declara al pie. Escribir 0 % afirmaba, en nombre del
    cliente, que no provisiona esa banda -y de ahí salía un hallazgo de riesgo
    Alto sobre un dato que nunca se le pidió-.
    """
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
            sin_comparar = bool(f.get("sin_comparar")) or f.get("tasa_politica") is None
            if sin_comparar:
                # La política de esta banda no se pidió ni se ingresó: no hay
                # nada que multiplicar ni que diferenciar.
                _celda(ws, i, 4, TEXTO_SIN_COMPARAR, alineacion=ALIN_CEN)
                _celda(ws, i, 5, TEXTO_SIN_COMPARAR, alineacion=ALIN_CEN)
            else:
                _celda(ws, i, 4, _numero(f.get("tasa_politica")), formato=FORMATO_PORCENTAJE,
                       alineacion=ALIN_DER)
                # ROUND, igual que `service._comparar_politica`
                # (`redondear(exposicion * tasa)`): sin él la celda arrastra
                # todos los decimales del producto y `=SUM(E…)` acumula esas
                # fracciones contra la provisión archivada.
                _celda(ws, i, 5, _f(f"=ROUND(C{i}*D{i},2)"), formato=FORMATO_MONEDA,
                       alineacion=ALIN_DER)
            if sin_comparar:
                sumifs = (f"=SUMIFS('05-Matriz'!{matriz_refs['col_perdida']}{matriz_refs['primera']}:"
                          f"{matriz_refs['col_perdida']}{matriz_refs['ultima']},"
                          f"'05-Matriz'!{matriz_refs['col_banda']}{matriz_refs['primera']}:"
                          f"{matriz_refs['col_banda']}{matriz_refs['ultima']},A{i})")
                if f.get("ecl") is None:
                    _celda(ws, i, 6, SEGMENTOS_TEXTO, alineacion=ALIN_CEN)
                else:
                    _celda(ws, i, 6, _f(sumifs), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
                _celda(ws, i, 7, TEXTO_SIN_COMPARAR, alineacion=ALIN_CEN)
            elif f.get("ecl") is None:
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
                _celda(ws, i, 6, _f(sumifs), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
                _celda(ws, i, 7, _f(f"=F{i}-E{i}"), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    else:
        ultima = primera
        _celda(ws, primera, 1, "(sin bandas de política en esta corrida)", alineacion=ALIN_IZQ)
        for col in range(2, 8):
            _celda(ws, primera, col, None)

    # Un TOTAL que suma celdas de TEXTO da 0,00, y ese cero afirma lo mismo que
    # la hoja evita fila a fila: que el cliente no provisiona nada, o que la
    # pérdida medida es cero. Si no hay ni una banda comparable, el total dice
    # lo que pasa; si hay alguna, `SUM` ignora el texto y suma solo lo real.
    hay_politica = any(not (f.get("sin_comparar") or f.get("tasa_politica") is None)
                       for f in filas_pol)
    hay_medido = any(f.get("ecl") is not None for f in filas_pol)

    fila_total = ultima + 1
    _celda(ws, fila_total, 2, "TOTAL", total=True, alineacion=ALIN_IZQ)
    _celda(ws, fila_total, 1, None, total=True)
    _celda(ws, fila_total, 3, _f(f"=SUM(C{primera}:C{ultima})"), formato=FORMATO_MONEDA, total=True, alineacion=ALIN_DER)
    _celda(ws, fila_total, 4, None, total=True)
    if hay_politica:
        _celda(ws, fila_total, 5, _f(f"=SUM(E{primera}:E{ultima})"), formato=FORMATO_MONEDA,
               total=True, alineacion=ALIN_DER)
    else:
        _celda(ws, fila_total, 5, TEXTO_SIN_COMPARAR, total=True, alineacion=ALIN_CEN)
    if hay_medido:
        _celda(ws, fila_total, 6, _f(f"=SUM(F{primera}:F{ultima})"), formato=FORMATO_MONEDA,
               total=True, alineacion=ALIN_DER)
    else:
        _celda(ws, fila_total, 6, SEGMENTOS_TEXTO, total=True, alineacion=ALIN_CEN)
    if hay_politica and hay_medido:
        _celda(ws, fila_total, 7, _f(f"=SUM(G{primera}:G{ultima})"), formato=FORMATO_MONEDA,
               total=True, alineacion=ALIN_DER)
    else:
        _celda(ws, fila_total, 7, TEXTO_SIN_COMPARAR, total=True, alineacion=ALIN_CEN)

    sin_politica = (resultado.get("politica") or {}).get("bandas_sin_politica") or []
    if sin_politica:
        nota = ws.cell(fila_total + 2, 1,
                       f"La política de deterioro del cliente no fue proporcionada para "
                       f"{len(sin_politica)} banda(s): {', '.join(str(b) for b in sin_politica)}. "
                       "Esas filas quedan SIN COMPARAR; suponerlas en 0 % afirmaría, en nombre del "
                       "cliente, que no provisiona esas bandas.")
        nota.font = FUENTE_DATOS_ALERTA
        nota.alignment = ALIN_IZQ
        ws.merge_cells(start_row=fila_total + 2, start_column=1, end_row=fila_total + 2,
                       end_column=7)

    _anchos(ws, {"A": 20, "B": 20, "C": 16, "D": 16, "E": 16, "F": 16, "G": 16})
    refs["politica"] = {"primera": primera, "ultima": ultima, "fila_total": fila_total}


# ---------------------------------------------------------------------------
# 08-Conciliacion
# ---------------------------------------------------------------------------

def _conciliacion(wb: Workbook, resultado: dict[str, Any], refs: dict[str, Any]) -> None:
    """Conciliación con los EEFF y, sobre todo, qué parte de la cartera se midió.

    "Cartera medida" rotulaba la suma de las exposiciones de ``05-Matriz`` y
    ``06-Individual``, o sea la exposición total, incluidas las filas SIN MEDIR:
    excedía a la cifra de la pantalla exactamente en el importe sin medir, con
    la misma etiqueta. Además ninguna celda del libro totalizaba
    ``exposicion.sin_medir``, así que el KPI que la pantalla pinta en rojo no
    tenía contraparte en el papel que se archiva. Aquí cada concepto lleva su
    propia fila y la cartera medida es la misma cifra que muestra la pantalla:
    lo estratificado menos lo que no se pudo medir.
    """
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
        _celda(ws, 3, 2, _f("=SaldoContable"), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    else:
        _celda(ws, 3, 2, "SIN EEFF (no conciliado)", alineacion=ALIN_CEN)

    _celda(ws, 4, 1, "Partida conciliatoria (archivo menos EEFF)", alineacion=ALIN_IZQ)
    if tiene_eeff:
        _celda(ws, 4, 2, _f("=B2-B3"), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    else:
        _celda(ws, 4, 2, "N/A", alineacion=ALIN_CEN)

    _celda(ws, 5, 1, "Exposición estratificada (05-Matriz + 06-Individual)", alineacion=ALIN_IZQ)
    _celda(ws, 5, 2,
           _f(f"='05-Matriz'!{matriz_refs['col_exposicion']}{matriz_refs['fila_total']}"
           f"+'06-Individual'!{individual_refs['col_exposicion']}{individual_refs['fila_total']}"),
           formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    _celda(ws, 6, 1, "Exposición sin estratificar (EEFF que no se ubicó en ninguna banda)",
           alineacion=ALIN_IZQ)
    _celda(ws, 6, 2, _numero(exposicion.get("sin_estratificar")) or 0.0, formato=FORMATO_MONEDA,
           alineacion=ALIN_DER)

    _celda(ws, 7, 1, "Cartera total analizada (estratificada + sin estratificar)", alineacion=ALIN_IZQ)
    _celda(ws, 7, 2, _f("=B5+B6"), formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    # Rango de la exposición de `05-Matriz` seguido del rango de su columna de
    # pérdida, que es la que rotula SIN MEDIR. Lo usan las dos filas del
    # desglose por signo, así que se arma una sola vez.
    rango_sin_medir = (
        f"'05-Matriz'!{matriz_refs['col_exposicion']}{matriz_refs['primera']}:"
        f"{matriz_refs['col_exposicion']}{matriz_refs['ultima']},"
        f"'05-Matriz'!{matriz_refs['col_perdida']}{matriz_refs['primera']}:"
        f"{matriz_refs['col_perdida']}{matriz_refs['ultima']}")
    rango_exposicion = (
        f"'05-Matriz'!{matriz_refs['col_exposicion']}{matriz_refs['primera']}:"
        f"{matriz_refs['col_exposicion']}{matriz_refs['ultima']}")

    # LO SIN MEDIR NO SE NETEA ENTRE BANDAS. Una banda sin tasa con saldo
    # deudor y otra sin tasa con saldo acreedor no se compensan: ninguna de las
    # dos se midió. Sumarlas con signo hacía que +20.000 y -20.000 dieran
    # «Exposición SIN MEDIR 0,00» y que el módulo declarara medición completa
    # con 40.000 de cartera sin medición.
    #
    # Por eso hay cuatro filas y no una, y las cuatro se recalculan desde
    # `05-Matriz` y `06-Individual`:
    #
    #   B8  deudora    SUMIFS(... ">0")  más lo sin medir individual, que ya
    #                                    viene con piso cero
    #   B9  acreedora  SUMIFS(... "<0")
    #   B10 MAGNITUD = B8-B9  -> cuánta cartera quedó sin medición. Es la que
    #                            declara `medicion_completa`, la que dispara el
    #                            hallazgo y la que pinta la pantalla.
    #   B11 NETA     = B8+B9  -> lo único que se puede restar de una cartera
    #                            estratificada que también es neta.
    #
    # No hay `ABS` dentro de un `SUMIFS`, así que el desglose por signo tiene
    # celda propia en vez de esconderse dentro de una fórmula.
    _celda(ws, 8, 1, "Exposición SIN MEDIR — deudora (bandas sin tasa con saldo deudor y saldos "
                     "individuales sin tasa)", alineacion=ALIN_IZQ)
    c = _celda(ws, 8, 2,
               _f(f'=SUMIFS({rango_sin_medir},"{SEGMENTOS_TEXTO}",{rango_exposicion},">0")'
                  f"+'06-Individual'!{individual_refs['col_sin_medir']}"
                  f"{individual_refs['fila_total']}"),
               formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    if (_numero(exposicion.get("sin_medir_deudora")) or 0.0) > 0.005:
        c.font = FUENTE_DATOS_ALERTA

    _celda(ws, 9, 1, "Exposición SIN MEDIR — acreedora (bandas sin tasa con saldo acreedor: notas "
                     "de crédito y anticipos)", alineacion=ALIN_IZQ)
    c = _celda(ws, 9, 2,
               _f(f'=SUMIFS({rango_sin_medir},"{SEGMENTOS_TEXTO}",{rango_exposicion},"<0")'),
               formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    if (_numero(exposicion.get("sin_medir_acreedora")) or 0.0) < -0.005:
        c.font = FUENTE_DATOS_ALERTA

    _celda(ws, 10, 1, "Exposición SIN MEDIR (magnitud: la deudora más la acreedora en valor "
                      "absoluto, SIN netear)", alineacion=ALIN_IZQ)
    c = _celda(ws, 10, 2, _f("=B8-B9"), formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    if (_numero(exposicion.get("sin_medir")) or 0.0) > 0.005:
        c.font = FUENTE_DATOS_ALERTA

    _celda(ws, 11, 1, "Exposición SIN MEDIR NETA (la deudora más la acreedora con su signo: lo "
                      "que se resta de la cartera estratificada)", alineacion=ALIN_IZQ)
    _celda(ws, 11, 2, _f("=B8+B9"), formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    # La cota de `motor.resumen_deterioro` VIVE EN LA FÓRMULA, no solo en el
    # motor: la cartera medida cae entre 0,00 y la cartera estratificada. Con
    # la resta cruda, un caso individual sin tasa mayor que la cartera neta
    # imprimía aquí una cartera medida NEGATIVA bajo la misma etiqueta con la
    # que la pantalla pintaba 0,00.
    _celda(ws, 12, 1, "Cartera medida (estratificada menos la exposición sin medir NETA, acotada)",
           alineacion=ALIN_IZQ)
    _celda(ws, 12, 2, _f("=MIN(MAX(B13,0),MAX(B5,0))"), formato=FORMATO_MONEDA,
           alineacion=ALIN_DER)

    # Y no actúa en silencio: la resta cruda y el motivo tienen celda propia,
    # igual que `05-Matriz` imprime la pérdida sin acotar junto a la acotada.
    _celda(ws, 13, 1, "Cartera medida SIN ACOTAR (la resta, tal cual)", alineacion=ALIN_IZQ)
    _celda(ws, 13, 2, _f("=B5-B11"), formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    _celda(ws, 14, 1, "Acotamiento aplicado a la cartera medida", alineacion=ALIN_IZQ)
    c = _celda(ws, 14, 2,
               _f(f'=IF(B12>B13+0.005,"{ACOTADO_PISO}",'
               f'IF(B12<B13-0.005,"{ACOTADO_TECHO_CARTERA}","{SIN_ACOTAR}"))'),
               alineacion=ALIN_CEN)
    if (resultado.get("exposicion") or {}).get("medida_acotada"):
        c.font = FUENTE_DATOS_ALERTA

    # 09-Tributario aplica el tope del 10 % sobre la exposición estratificada
    # (fila 5): es la cartera a la que se refiere la provisión. Se referencia
    # desde aquí para que el libro tenga UNA sola celda con esa base.
    refs["conciliacion"] = {"fila_estratificada": 5, "col_importe": "B",
                            "fila_sin_medir_deudora": 8, "fila_sin_medir_acreedora": 9,
                            "fila_sin_medir_magnitud": 10, "fila_sin_medir_neta": 11,
                            "fila_medida": 12, "fila_medida_sin_acotar": 13,
                            "fila_acotamiento": 14}

    _celda(ws, 15, 1, "Estado", alineacion=ALIN_IZQ)
    if tiene_eeff:
        _celda(ws, 15, 2, _f('=IF(ABS(B4)<0.01,"CUADRA","DIFERENCIA")'), alineacion=ALIN_CEN)
    else:
        _celda(ws, 15, 2, "N/A (sin EEFF para conciliar)", alineacion=ALIN_CEN)

    _celda(ws, 16, 1, "Nota", alineacion=ALIN_IZQ)
    _celda(ws, 16, 2, "Una tasa cero por ausencia de historia no es evidencia de ausencia de "
                      "pérdida: la exposición sin medir no está provisionada en 0,00, está sin "
                      "medir (NIIF 9 B5.5.35). La cartera medida se acota a [0,00; cartera "
                      "estratificada]: cuando lo sin medir supera a la cartera estratificada, la "
                      "fila 14 lo declara y 10-Hallazgos lo recoge.", alineacion=ALIN_IZQ)

    _celda(ws, 17, 1, "Por qué la magnitud (B10) y la neta (B11) no coinciden",
           alineacion=ALIN_IZQ)
    _celda(ws, 17, 2, NOTA_SIN_MEDIR_NO_SE_NETEA, alineacion=ALIN_IZQ)
    ws.row_dimensions[17].height = 86

    _anchos(ws, {"A": 58, "B": 22})


# ---------------------------------------------------------------------------
# 09-Tributario
# ---------------------------------------------------------------------------

def _tributario(wb: Workbook, resultado: dict[str, Any], refs: dict[str, Any]) -> None:
    """Concilia la pérdida esperada contra los límites de la LORTI.

    El art. 10 num. 11 pone dos límites sobre magnitudes distintas: el 1 %
    limita la provisión DEL EJERCICIO (un flujo) y el 10 % la ACUMULADA (un
    stock). La PCE que mide este papel es acumulada, así que el exceso no
    deducible se calcula contra el tope del 10 %; restarle el 1 % era restar un
    flujo de un stock. El límite anual queda declarado como NO VERIFICABLE
    porque la herramienta no recibe el movimiento de la provisión del período.

    BASE DE LOS DOS PORCENTAJES: la EXPOSICIÓN ESTRATIFICADA (``08-Conciliacion``
    B5 = 05-Matriz + 06-Individual), no el saldo contable completo. El tope se
    aplica sobre la cartera a la que se refiere la provisión, y la provisión se
    midió únicamente sobre la cartera que se pudo ubicar en una banda: la parte
    de los EEFF que no aparece en el análisis de antigüedad
    (``exposicion.sin_estratificar``) no tiene pérdida medida, así que
    incluirla solo inflaría el tope y haría deducible una provisión que sobre
    su propia cartera excede el límite. Antes el motor usaba una base
    (la estratificada) y la fórmula del papel otra (``SaldoContable``): con
    cartera sin estratificar la pantalla decía que se excede el tope y el papel
    decía que no.

    La hoja concilia: en ningún caso sustituye la medición de NIIF 9.
    """
    ws = wb.create_sheet("09-Tributario")
    _encabezados(ws, 1, ["Concepto", "Importe"])

    tributario = resultado.get("tributario") or {}
    matriz_refs = refs["matriz"]
    individual_refs = refs["individual"]
    conciliacion_refs = refs.get("conciliacion") or {}
    base = (f"'08-Conciliacion'!{conciliacion_refs.get('col_importe', 'B')}"
            f"{conciliacion_refs.get('fila_estratificada', 5)}")

    _celda(ws, 2, 1, "Provisión contable acumulada (PCE total medida)", alineacion=ALIN_IZQ)
    formula_pce = (f"='05-Matriz'!{matriz_refs['col_perdida']}{matriz_refs['fila_total']}"
                  f"+'06-Individual'!{individual_refs['col_perdida']}{individual_refs['fila_total']}")
    _celda(ws, 2, 2, _f(formula_pce), formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    _celda(ws, 3, 1, "Tope de la provisión ACUMULADA: 10 % de la cartera ESTRATIFICADA "
                     "(LORTI art. 10 núm. 11)", alineacion=ALIN_IZQ)
    _celda(ws, 3, 2, _f(f"={base}*0.1"), formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    # El tope del 10 % solo es contrastable sobre una cartera POSITIVA. Con la
    # cartera estratificada neta acreedora (notas de crédito por encima de las
    # facturas) el tope sale negativo y `MAX(0;B2-B3)` daba un «exceso» con una
    # pérdida esperada de 0,00: el papel y la pantalla coincidían, pero los dos
    # en un absurdo. Lo que no se puede contrastar se declara, igual que el
    # límite anual del 1 % de la fila 7.
    _celda(ws, 4, 1, "Exceso sobre el tope acumulado del 10 % (no deducible)", alineacion=ALIN_IZQ)
    c = _celda(ws, 4, 2, _f(f'=IF({base}<=0,"{TOPE_NO_CONTRASTABLE}",MAX(0,B2-B3))'),
               formato=FORMATO_MONEDA, alineacion=ALIN_DER)
    if not tributario.get("tope_acumulado_verificable", True):
        c.font = FUENTE_DATOS_ALERTA

    _celda(ws, 5, 1, "1 % de la cartera ESTRATIFICADA — referencia del límite ANUAL de la "
                     "provisión del ejercicio", alineacion=ALIN_IZQ)
    _celda(ws, 5, 2, _f(f"={base}*0.01"), formato=FORMATO_MONEDA, alineacion=ALIN_DER)

    _celda(ws, 6, 1, "Provisión del ejercicio (movimiento del período)", alineacion=ALIN_IZQ)
    _celda(ws, 6, 2, "NO PROPORCIONADA", alineacion=ALIN_CEN)

    _celda(ws, 7, 1, "Límite del 1 % anual (LORTI art. 10 núm. 11)", alineacion=ALIN_IZQ)
    c = _celda(ws, 7, 2, "NO VERIFICABLE — exige el movimiento de la provisión del ejercicio "
                         "(saldo inicial, dotación, uso y reversión), que esta herramienta no "
                         "recibe. El 1 % limita la provisión DEL EJERCICIO, no la acumulada, así "
                         "que no se compara contra B2.", alineacion=ALIN_IZQ)
    c.font = FUENTE_DATOS_ALERTA

    _celda(ws, 8, 1, "Contrastabilidad del tope del 10 %", alineacion=ALIN_IZQ)
    c = _celda(ws, 8, 2,
               'Un tope del 10 % solo tiene lectura sobre una cartera POSITIVA. Si la cartera '
               'estratificada (08-Conciliacion B5) queda NETA ACREEDORA -las notas de crédito '
               'superan a las facturas-, el tope sale negativo y compararlo contra la provisión '
               'no concluye nada: la fila 4 lo declara NO CONTRASTABLE en vez de imprimir un '
               'exceso. Reclasifique los saldos acreedores a pasivo (anticipos de clientes) '
               'antes de conciliar el efecto tributario.', alineacion=ALIN_IZQ)
    if not tributario.get("tope_acumulado_verificable", True):
        c.font = FUENTE_DATOS_ALERTA

    _celda(ws, 9, 1, "Base de los dos porcentajes", alineacion=ALIN_IZQ)
    _celda(ws, 9, 2, "La cartera ESTRATIFICADA (08-Conciliacion B5 = 05-Matriz + 06-Individual), "
                     "que es la cartera a la que se refiere la provisión. NO se usa el saldo "
                     "contable completo: la parte de los estados financieros que no se pudo "
                     "ubicar en ninguna banda (exposición sin estratificar) no tiene pérdida "
                     "medida, e incluirla solo inflaría el tope. Es la misma base que aplica el "
                     "motor, así que la pantalla y este papel concluyen lo mismo.",
           alineacion=ALIN_IZQ)

    _celda(ws, 10, 1, "Nota", alineacion=ALIN_IZQ)
    _celda(ws, 10, 2, str(tributario.get("nota", "")) + " El tratamiento tributario concilia con la "
                     "medición contable: no la sustituye ni la condiciona (NIIF 9 5.5.15), y la "
                     "diferencia es temporaria.", alineacion=ALIN_IZQ)

    _anchos(ws, {"A": 62, "B": 26})


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
    # Medir sobre la exposición redondeada obliga a que el total sea la suma DE
    # LAS BANDAS REDONDEADAS, y esa suma puede quedar a unos centavos de la
    # cartera anclada. Esos centavos se reparten entre las bandas (un centavo
    # por banda, las de mayor resto primero) y aquí se declaran: sin esta línea
    # el ajuste existiría igual, pero en silencio.
    redondeo = (bitacora.get("redondeo_exposicion") or {})
    if redondeo:
        redondeo_texto = ("; ".join(f"{k}: {v:+d} centavo(s)" for k, v in redondeo.items())
                          + ". Repartidos entre las bandas de 05-Matriz, un centavo por banda "
                            "empezando por las de mayor resto, para que la exposición se mida "
                            "en centavos exactos sin desanclarse de la cartera según EEFF.")
    else:
        redondeo_texto = ("Ninguno: la suma de las bandas redondeadas ya daba la cartera anclada "
                          "al centavo.")
    trazabilidad_texto = f"{trazabilidad:.1%}" if isinstance(trazabilidad, (int, float)) else ""

    filas = [
        ("Método", bitacora.get("metodo", "")),
        ("Descuento", bitacora.get("descuento", "")),
        ("Bandas", ", ".join(bitacora.get("bandas") or [])),
        ("Umbral de incumplimiento (días)", bitacora.get("umbral_incumplimiento", "")),
        ("Umbral de evaluación individual", bitacora.get("umbral_individual", "")),
        ("Cortes cargados", cortes_texto),
        ("Factores de anclaje a EEFF", factores_texto),
        ("Ajuste por redondeo de la exposición", redondeo_texto),
        ("Trazabilidad de la cohorte", trazabilidad_texto),
        ("Transformaciones aplicadas por archivo", transformaciones_texto),
        ("Versión y fecha de generación", f"PT-PCE-CXC v1.0 — emitido {fecha_emision}"),
    ]
    for i, (concepto, detalle) in enumerate(filas, start=2):
        _celda(ws, i, 1, concepto, alineacion=ALIN_IZQ)
        _celda(ws, i, 2, detalle, alineacion=ALIN_IZQ)

    _anchos(ws, {"A": 34, "B": 70})
