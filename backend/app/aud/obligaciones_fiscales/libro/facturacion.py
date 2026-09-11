"""Cuadro No. 2 · Ingresos IVA vs facturación (pestaña del modelo del auditor).

Compara lo DECLARADO en el F-104 (casilleros 401-418 y 431/441, año completo)
contra lo FACTURADO electrónicamente según los XML autorizados del SRI que
sube el auditor, sueltos o dentro de un .zip.

Las rutas de nodos salen de las plantillas oficiales del SRI (factura V1.0.0 a
V2.1.0): los cuatro esquemas traen los mismos campos que usa este cuadro.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from backend.app.aud.obligaciones_fiscales.libro.estilos import (
    BORDE,
    BORDE_TOTAL,
    FONT_DATA,
    FONT_ENCABEZADO_TABLA,
    FONT_TITULO_CEDULA,
    FONT_TOTAL,
    FORMATO_NUM,
    RELLENO_TOTAL,
)
from backend.app.ict.fillers.source_data_sheets import _safe_text

SHEET_CUADRO = "Ingresos IVA vs facturación"
SHEET_DATOS = "DATOS FACTURACIÓN"

# Tabla 17 de la ficha técnica de comprobantes electrónicos del SRI:
# codigoPorcentaje del IVA (codigo=2). El XSD NO la enumera —es un patrón libre
# [0-9]+—, así que un código fuera de esta tabla se reporta, no se adivina.
TRAMO_POR_CODIGO = {
    "0": "cero",      # 0%
    "2": "gravada",   # 12%
    "3": "gravada",   # 14%
    "4": "gravada",   # 15%
    "5": "gravada",   # 5%
    "8": "gravada",   # IVA diferenciado
    "10": "gravada",  # 13%
    "6": "exento",    # no objeto de impuesto
    "7": "exento",    # exento de IVA
}
_TIPOS = {
    "factura": ("Factura", "infoFactura"),
    "notaCredito": ("Nota de crédito", "infoNotaCredito"),
}

# Límites al abrir lo que sube el usuario (frontera de confianza).
MAX_XML_POR_ZIP = 20000
MAX_BYTES_XML = 5 * 1024 * 1024
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)


@dataclass
class Comprobante:
    clave: str = ""
    tipo: str = ""
    numero: str = ""
    fecha: str = ""
    periodo: str | None = None
    comprador: str = ""
    exportacion: bool = False
    lineas: list[tuple[str, float, float]] = field(default_factory=list)  # (tramo, base, iva)
    errores: list[str] = field(default_factory=list)


def _texto(nodo, ruta: str) -> str:
    return (nodo.findtext(ruta) or "").strip()


def leer_comprobante(datos: bytes, _envuelto: bool = False) -> Comprobante:
    """Lee una factura o nota de crédito, suelta o dentro de <autorizacion>."""
    if b"<!DOCTYPE" in datos.upper():
        return Comprobante(errores=["XML con DOCTYPE: un comprobante del SRI no lo lleva; se rechaza."])
    try:
        raiz = etree.fromstring(datos, _PARSER)
    except etree.XMLSyntaxError as e:
        return Comprobante(errores=[f"XML inválido: {e}"])

    # Así lo descarga el portal del SRI: el comprobante viaja como texto CDATA
    # con su propia declaración <?xml?>, por eso se vuelve a bytes. Un solo
    # nivel: no hay sobres dentro de sobres.
    if raiz.tag == "autorizacion" and not _envuelto:
        interno = (raiz.findtext("comprobante") or "").strip()
        if not interno:
            return Comprobante(errores=["<autorizacion> sin <comprobante>."])
        return leer_comprobante(interno.encode("utf-8"), _envuelto=True)

    if raiz.tag not in _TIPOS:
        return Comprobante(errores=[f"<{raiz.tag}> no es factura ni nota de crédito; se omite."])
    tipo, tag_info = _TIPOS[raiz.tag]
    trib, info = raiz.find("infoTributaria"), raiz.find(tag_info)
    if trib is None or info is None:
        return Comprobante(tipo=tipo, errores=[f"{tipo} sin infoTributaria/{tag_info}."])

    c = Comprobante(
        clave=_texto(trib, "claveAcceso"),
        tipo=tipo,
        numero="-".join(_texto(trib, t) for t in ("estab", "ptoEmi", "secuencial")),
        fecha=_texto(info, "fechaEmision"),
        comprador=_texto(info, "razonSocialComprador"),
        exportacion=_texto(info, "comercioExterior").upper() == "EXPORTADOR",
    )
    try:
        _dia, mes, anio = c.fecha.split("/")
        c.periodo = f"{int(anio):04d}-{int(mes):02d}"
    except ValueError:
        c.errores.append(f"fechaEmision ilegible: {c.fecha!r}")

    for imp in info.iterfind("totalConImpuestos/totalImpuesto"):
        if _texto(imp, "codigo") != "2":
            continue  # ICE / IRBPNR no entran al cuadro de IVA
        cod = _texto(imp, "codigoPorcentaje")
        tramo = TRAMO_POR_CODIGO.get(cod)
        if tramo is None:
            c.errores.append(f"codigoPorcentaje de IVA desconocido: {cod!r}")
            continue
        try:
            c.lineas.append((tramo, float(_texto(imp, "baseImponible") or 0),
                             float(_texto(imp, "valor") or 0)))
        except ValueError:
            c.errores.append(f"importe ilegible en totalImpuesto (codigoPorcentaje {cod})")
    return c


def _xmls_de(ruta: Path) -> tuple[list[tuple[str, bytes]], list[str]]:
    if ruta.suffix.lower() != ".zip":
        return [(ruta.name, ruta.read_bytes())], []
    salida, errores = [], []
    with zipfile.ZipFile(ruta) as zf:
        miembros = [i for i in zf.infolist() if i.filename.lower().endswith(".xml")]
        if len(miembros) > MAX_XML_POR_ZIP:
            return [], [f"{ruta.name}: trae {len(miembros)} XML; el máximo por .zip es {MAX_XML_POR_ZIP}."]
        for i in miembros:
            # Se lee con tope en vez de confiar en file_size: la cabecera del
            # .zip la escribe quien lo arma y puede mentir.
            with zf.open(i) as f:
                datos = f.read(MAX_BYTES_XML + 1)
            if len(datos) > MAX_BYTES_XML:
                errores.append(f"{i.filename}: supera {MAX_BYTES_XML // 1024 // 1024} MB; se omite.")
                continue
            salida.append((i.filename, datos))
    return salida, errores


def leer_facturas(paths: list[Path]) -> tuple[list[Comprobante], list[str]]:
    """Lee XML sueltos y .zip. Un comprobante repetido (misma clave) cuenta una vez."""
    comprobantes: list[Comprobante] = []
    errores: list[str] = []
    vistas: set[str] = set()
    for ruta in paths:
        try:
            archivos, errs = _xmls_de(ruta)
        except zipfile.BadZipFile:
            errores.append(f"{ruta.name}: .zip dañado; se omite.")
            continue
        errores.extend(errs)
        for nombre, datos in archivos:
            c = leer_comprobante(datos)
            errores.extend(f"{nombre}: {e}" for e in c.errores)
            if not c.lineas:
                continue
            if c.clave in vistas:
                errores.append(f"{nombre}: comprobante {c.clave} duplicado; se cuenta una sola vez.")
                continue
            vistas.add(c.clave)
            comprobantes.append(c)
    return comprobantes, errores


def fila_del_cuadro(tramo: str, exportacion: bool) -> int:
    # ponytail: el XML no distingue activos fijos, 0% con/sin derecho a crédito
    # tributario ni exportación de servicios; esas filas (7, 9-11, 13) quedan en
    # cero del lado facturado y cuadran en el total. Afinar si hay dato para ello.
    if exportacion:
        return 12
    return {"gravada": 6, "cero": 8, "exento": 15}[tramo]


# ---- hojas del libro --------------------------------------------------------

_ENCABEZADO_DATOS = ["Clave de acceso", "Tipo", "Número", "Fecha", "Período", "Comprador",
                     "Tramo IVA", "Fila del cuadro", "Base imponible", "IVA"]

# (fila, etiqueta del modelo, casillero bruto, casillero neto, columna declarada)
# Columna declarada: 2 = (a) tarifa 0%, 3 = (b) tarifa ≠ 0%, 4 = (c) exportaciones.
_FILAS = [
    (6, "Ventas locales (excluye activos fijos) gravadas tarifa diferente de cero", "401", "411", 3),
    (7, "Ventas de activos fijos gravadas tarifa diferente de cero", "402", "412", 3),
    (8, "Ventas locales (excluye activos fijos) gravadas tarifa 0% que no dan derecho a crédito tributario", "403", "413", 2),
    (9, "Ventas de activos fijos gravadas tarifa 0% que no dan derecho a crédito tributario", "404", "414", 2),
    (10, "Ventas locales (excluye activos fijos) gravadas tarifa 0% que dan derecho a crédito tributario", "405", "415", 2),
    (11, "Ventas de activos fijos gravadas tarifa 0% que dan derecho a crédito tributario", "406", "416", 2),
    (12, "Exportaciones de bienes", "407", "417", 4),
    (13, "Exportaciones de servicios", "408", "418", 4),
]
_FILA_NO_OBJETO = (15, "Transferencias no objeto o exentas de iva", "431", "441", 2)

_NOTAS = [
    "Facturación electrónica: sale de los XML autorizados subidos (hoja DATOS FACTURACIÓN). "
    "El XML no distingue activos fijos, 0% con o sin derecho a crédito tributario (todo el 0% "
    "va a la fila 8) ni exportación de servicios: esas filas se comparan en el total (fila 14).",
    "Facturación física (columnas J y K) y comprobantes anulados: se completan a mano; "
    "el XML no informa anulaciones.",
]


def _sumifs(tipo: str, fila: int) -> str:
    d = f"'{SHEET_DATOS}'!"
    return f'=SUMIFS({d}$I:$I,{d}$B:$B,"{tipo}",{d}$H:$H,{fila})'


def _hoja_datos(wb, comprobantes: list[Comprobante]) -> None:
    if SHEET_DATOS in wb.sheetnames:
        del wb[SHEET_DATOS]
    ws = wb.create_sheet(SHEET_DATOS)
    ws.cell(1, 1, "DATOS FACTURACIÓN · comprobantes electrónicos autorizados").font = FONT_TITULO_CEDULA
    for j, texto in enumerate(_ENCABEZADO_DATOS, 1):
        c = ws.cell(3, j, texto)
        c.font, c.border = FONT_ENCABEZADO_TABLA, BORDE
    fila = 4
    for comp in comprobantes:
        for tramo, base, iva in comp.lineas:
            valores = [comp.clave, comp.tipo, comp.numero, comp.fecha, comp.periodo or "",
                       _safe_text(comp.comprador), tramo,
                       fila_del_cuadro(tramo, comp.exportacion), base, iva]
            for j, v in enumerate(valores, 1):
                c = ws.cell(fila, j, v)
                c.font, c.border = FONT_DATA, BORDE
                if j >= 9:
                    c.number_format = FORMATO_NUM
            fila += 1
    ws.freeze_panes = "A4"
    if fila > 4:
        ws.auto_filter.ref = f"A3:J{fila - 1}"
    for letra, ancho in zip("ABCDEFGHIJ", (52, 16, 20, 12, 10, 40, 11, 10, 15, 13)):
        ws.column_dimensions[letra].width = ancho


def _encabezado_cuadro(ws) -> None:
    ws.cell(1, 1, "CUADRO No. 2  INGRESOS IVA VS FACTURACIÓN").font = FONT_TITULO_CEDULA
    textos = {
        (3, 1): "Detalle", (3, 2): "DECLARACIÓN IMPUESTO AL VALOR AGREGADO",
        (3, 7): "FACTURACIÓN ELECTRÓNICA", (3, 10): "FACTURACIÓN FÍSICA",
        (3, 13): "TOTAL FACTURACIÓN", (3, 14): "DIFERENCIA",
    }
    fila4 = ["Tarifa 0% de iva o exentas de IVA", "Tarifa diferente de 0% de IVA", "Exportaciones",
             "Notas de crédito", "Valor neto de Ingresos", "Emitidas", "Anuladas / Notas de crédito",
             "Valor neto electrónicas", "Emitidas", "Anuladas / Notas de crédito", "Valor Neto físicas"]
    fila5 = ["(a)", "(b)", "(c)", "(d)", "(e=a+b+c-d)", "(f)", "(g)", "(h=f-g)",
             "(i)", "(j)", "(k=i-j)", "(l=h+k)", "(m=e-l)"]
    for (f, col), t in textos.items():
        ws.cell(f, col, t)
    for j, t in enumerate(fila4, 2):
        ws.cell(4, j, t)
    for j, t in enumerate(fila5, 2):
        ws.cell(5, j, t)
    for rango in ("A3:A5", "B3:F3", "G3:I3", "J3:L3", "M3:M4", "N3:N4"):
        ws.merge_cells(rango)
    for f in (3, 4, 5):
        for col in range(1, 15):
            c = ws.cell(f, col)
            c.font, c.border = FONT_ENCABEZADO_TABLA, BORDE


def _fila_cuadro(ws, fila, etiqueta, bruto, neto, col_declarada, dir_f104) -> None:
    rb, rn = dir_f104.get(("ANUAL", bruto)), dir_f104.get(("ANUAL", neto))
    ws.cell(fila, 1, etiqueta)
    for col in (2, 3, 4):
        ws.cell(fila, col, f"={rb}" if col == col_declarada and rb else 0)
    ws.cell(fila, 5, f"={rb}-{rn}" if rb and rn else 0)  # NC declaradas = bruto − neto
    ws.cell(fila, 6, f"=B{fila}+C{fila}+D{fila}-E{fila}")
    ws.cell(fila, 7, _sumifs("Factura", fila))
    ws.cell(fila, 8, _sumifs("Nota de crédito", fila))
    ws.cell(fila, 9, f"=G{fila}-H{fila}")
    ws.cell(fila, 10, 0)
    ws.cell(fila, 11, 0)
    ws.cell(fila, 12, f"=J{fila}-K{fila}")
    ws.cell(fila, 13, f"=I{fila}+L{fila}")
    ws.cell(fila, 14, f"=F{fila}-M{fila}")
    for col in range(1, 15):
        c = ws.cell(fila, col)
        c.font, c.border = FONT_DATA, BORDE
        if col > 1:
            c.number_format = FORMATO_NUM


def _hoja_cuadro(wb, dir_f104: dict) -> None:
    if SHEET_CUADRO in wb.sheetnames:
        del wb[SHEET_CUADRO]
    ws = wb.create_sheet(SHEET_CUADRO)
    _encabezado_cuadro(ws)
    for args in _FILAS:
        _fila_cuadro(ws, *args, dir_f104)

    # Total: el modelo del auditor no sumaba la columna (a) en esta fila; aquí sí.
    ws.cell(14, 1, "Total ventas y otras operaciones")
    for col in (2, 3, 4, 5, 7, 8, 10, 11):
        letra = "ABCDEFGHIJKLMN"[col - 1]
        ws.cell(14, col, f"=SUM({letra}6:{letra}13)")
    for col, formula in ((6, "=B14+C14+D14-E14"), (9, "=G14-H14"), (12, "=J14-K14"),
                         (13, "=I14+L14"), (14, "=F14-M14")):
        ws.cell(14, col, formula)
    for col in range(1, 15):
        c = ws.cell(14, col)
        c.font, c.fill, c.border = FONT_TOTAL, RELLENO_TOTAL, BORDE_TOTAL
        if col > 1:
            c.number_format = FORMATO_NUM

    _fila_cuadro(ws, *_FILA_NO_OBJETO, dir_f104)
    for i, nota in enumerate(_NOTAS):
        ws.cell(17 + i, 1, nota).font = FONT_DATA

    ws.column_dimensions["A"].width = 62
    for letra in "BCDEFGHIJKLMN":
        ws.column_dimensions[letra].width = 15
    ws.freeze_panes = "B6"


def construir_hojas_facturacion(wb, comprobantes: list[Comprobante], dir_f104: dict) -> None:
    """Crea el cuadro y su hoja de detalle. Sin XML, el cuadro sale igual:
    el lado declarado ya tiene valor para el auditor."""
    _hoja_datos(wb, comprobantes)
    _hoja_cuadro(wb, dir_f104)
