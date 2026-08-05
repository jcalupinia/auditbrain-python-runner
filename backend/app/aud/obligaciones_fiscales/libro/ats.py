"""Parser del Anexo Transaccional Simplificado (ATS) del SRI Ecuador.

El cliente puede entregar el ATS en dos formatos:

- **PDF** ("Talón Resumen" que emite el SRI): una hoja por período con los
  totales ya agregados. Es el nivel de detalle que DM8 necesita (compara
  totales mensuales, no comprobante por comprobante). Implementado y
  verificado empíricamente contra un anexo real (ver
  ``tests/test_of_libro_ats_real_cliente.py``).
- **XML**: el formato de origen del anexo antes de generarse el talón.
  **Pendiente de implementar**: no se contó con una muestra real de XML del
  SRI al construir este parser (el spec del proyecto lo documenta
  expresamente). ``parse_ats_xml`` NO inventa nombres de nodo: si detecta
  XML devuelve un :class:`ResumenATS` vacío con un error explícito en vez
  de fingir que el parseo funcionó.

Trampas del formato PDF (verificadas contra un anexo real de diciembre 2025):

1. El rótulo "BI tarifa 12%" es histórico: es la base gravada con tarifa
   distinta de cero, aunque la vigente sea 15%. Se lee por POSICIÓN de
   columna, nunca por el rótulo.
2. Los nombres largos de concepto de retención de renta se parten en varias
   líneas de texto, con el código y los números quedando en la línea del
   medio. Una fila sin nombre propio en el talón NUNCA hereda el nombre de
   la fila anterior (regla del CLAUDE.md del proyecto).
3. Hay códigos alfanuméricos (p. ej. "303A") y de 4 dígitos (p. ej. "3440").
4. Los importes están en formato regional variable: se delega en
   ``_parse_amount_sri`` de ``cedulas/base.py``.
5. El período viene como "DICIEMBRE 2025", no como "12/2025".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import pdfplumber

from backend.app.aud.obligaciones_fiscales.cedulas.base import (
    _MES_ES_TO_NUM,
    _parse_amount_sri,
)

_CODE_RE = re.compile(r"^\d{3,4}[A-Z]?$")
_AMOUNT_RE = re.compile(r"^-?\d+(?:[.,]\d+)*$")

# Líneas de encabezado de columna del talón: se descartan siempre que
# aparezcan, en vez de tratarse como texto de un nombre de concepto.
_ENCABEZADOS_COLUMNA = {
    "No. Base Valor",
    "Cod. Concepto de Retención",
    "Registros Imponible Retenido",
    "Operación Concepto de Retención Valor Retenido",
    "Cod. Transacción No. Registros BI tarifa 0% BI tarifa 12% BI No Objeto IVA Valor IVA",
}

# Casilleros de importaciones "Valor Neto" del F-104 (compras). Se restan del
# casillero 519 para aproximar las compras 0% del ATS. Mapeo tomado del spec
# (docs/superpowers/specs/2026-08-04-mayor-general-impuestos-design.md); a
# diferencia de los demás cruces de DM8, este NO forma parte de la lista de
# cruces verificados empíricamente con diciembre 2025 (esa lista no incluye
# "compras 0%") — revisar con un caso real que tenga importaciones.


@dataclass
class BloqueBase:
    """Un bloque COMPRAS o VENTAS del talón: fila TOTAL: leída por posición."""

    bi_0: float = 0.0
    bi_gravada: float = 0.0
    bi_no_objeto: float = 0.0
    iva: float = 0.0


@dataclass
class RetencionRenta:
    """Una fila del bloque RETENCION EN LA FUENTE DE IMPUESTO A LA RENTA."""

    codigo: str
    concepto: str
    n_registros: float
    base_imponible: float
    valor_retenido: float


@dataclass
class RetencionIVA:
    """Una fila del bloque RETENCION EN LA FUENTE DE IVA (por porcentaje)."""

    operacion: str
    concepto: str
    porcentaje: float | None
    valor_retenido: float


@dataclass
class ResumenATS:
    """Resultado del parseo de un Talón Resumen (o, a futuro, un XML) del ATS."""

    periodo: str | None  # "YYYY-MM"
    ruc: str | None = None
    razon_social: str | None = None
    estado: str | None = None
    secuencial: str | None = None
    compras: BloqueBase = field(default_factory=BloqueBase)
    ventas: BloqueBase = field(default_factory=BloqueBase)
    comprobantes_anulados: int | None = None
    retenciones_renta: list[RetencionRenta] = field(default_factory=list)
    retenciones_renta_base_total: float = 0.0
    retenciones_renta_valor_total: float = 0.0
    retenciones_iva: list[RetencionIVA] = field(default_factory=list)
    retenciones_iva_total: float = 0.0
    iva_que_le_retuvieron: float = 0.0
    renta_que_le_retuvieron: float = 0.0
    errores: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers de bajo nivel
# ---------------------------------------------------------------------------


def _is_amount(token: str) -> bool:
    return bool(_AMOUNT_RE.match(token))


def _seccion(lines: list[str], inicio: str, fin: str | None) -> list[str]:
    """Devuelve las líneas estrictamente entre dos marcadores (exclusive)."""
    try:
        i = next(idx for idx, l in enumerate(lines) if l.strip().upper() == inicio.upper())
    except StopIteration:
        return []
    j = len(lines)
    if fin:
        for idx in range(i + 1, len(lines)):
            if lines[idx].strip().upper() == fin.upper():
                j = idx
                break
    return lines[i + 1 : j]


def _es_encabezado_columna(line: str) -> bool:
    return line.strip() in _ENCABEZADOS_COLUMNA


# ---------------------------------------------------------------------------
# Cabecera del talón
# ---------------------------------------------------------------------------


def _buscar_ruc(texto: str) -> str | None:
    m = re.search(r"RUC:\s*(\d+)", texto)
    return m.group(1) if m else None


def _buscar_periodo(texto: str) -> str | None:
    m = re.search(r"Periodo:\s*([A-ZÁÉÍÓÚÑ]+)\s+(\d{4})", texto, re.IGNORECASE)
    if not m:
        return None
    mes = _MES_ES_TO_NUM.get(m.group(1).upper())
    if not mes:
        return None
    return f"{m.group(2)}-{mes}"


def _buscar_estado(texto: str) -> str | None:
    m = re.search(r"Estado:\s*(.+)", texto)
    return m.group(1).strip() if m else None


def _buscar_secuencial(texto: str) -> str | None:
    m = re.search(r"Secuencial Anexo:\s*(\S+)", texto)
    return m.group(1) if m else None


def _buscar_razon_social(lines: list[str]) -> str | None:
    try:
        i = next(idx for idx, l in enumerate(lines) if l.strip().upper() == "ANEXO TRANSACCIONAL")
    except StopIteration:
        return None
    for j in range(i + 1, len(lines)):
        linea = lines[j].strip()
        if linea.upper().startswith("RUC:"):
            break
        if linea:
            return linea
    return None


# ---------------------------------------------------------------------------
# Bloques COMPRAS / VENTAS
# ---------------------------------------------------------------------------


def _bloque_totales(lines: list[str], *, inicio: str, fin: str | None) -> BloqueBase | None:
    for linea in _seccion(lines, inicio, fin):
        if linea.strip().upper().startswith("TOTAL:"):
            numeros = re.findall(r"-?\d+(?:[.,]\d+)*", linea)
            if len(numeros) >= 4:
                bi_0, bi_gravada, bi_no_objeto, iva = numeros[:4]
                return BloqueBase(
                    bi_0=_parse_amount_sri(bi_0) or 0.0,
                    bi_gravada=_parse_amount_sri(bi_gravada) or 0.0,
                    bi_no_objeto=_parse_amount_sri(bi_no_objeto) or 0.0,
                    iva=_parse_amount_sri(iva) or 0.0,
                )
    return None


def _buscar_anulados(lines: list[str]) -> int | None:
    for linea in lines:
        if "Comprobantes Anulados" in linea:
            m = re.search(r"(\d+)\s*$", linea.strip())
            if m:
                return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Bloque RETENCION EN LA FUENTE DE IMPUESTO A LA RENTA
# ---------------------------------------------------------------------------


def _parse_fila_renta(line: str) -> dict | None:
    """Intenta leer una línea como '<código> [<nombre>] <n_reg> <base> <valor>'.

    Se parte de derecha a izquierda: los últimos dos tokens son montos, el
    tercero desde el final es el número de registros (entero), el primero
    es el código, y todo lo que quede en medio es el nombre inline (puede
    ser vacío: es el caso de las filas cuyo nombre viene partido en líneas
    separadas). Devuelve None si la línea no tiene esta forma.
    """
    tokens = line.split()
    if len(tokens) < 4:
        return None
    if not _CODE_RE.match(tokens[0]):
        return None
    if not (_is_amount(tokens[-1]) and _is_amount(tokens[-2]) and tokens[-3].isdigit()):
        return None
    return {
        "codigo": tokens[0],
        "nombre_inline": " ".join(tokens[1:-3]).strip(),
        "n_registros": float(tokens[-3]),
        "base_imponible": _parse_amount_sri(tokens[-2]) or 0.0,
        "valor_retenido": _parse_amount_sri(tokens[-1]) or 0.0,
    }


def _parse_retenciones_renta(lines: list[str]) -> list[RetencionRenta]:
    filas: list[RetencionRenta] = []
    prefijo: list[str] = []
    pendiente: dict | None = None

    def _cerrar(sufijo: str | None = None) -> None:
        nonlocal pendiente
        if pendiente is None:
            return
        partes = [pendiente["nombre_inline"]]
        if sufijo:
            partes.append(sufijo)
        nombre = " ".join(p for p in partes if p).strip()
        filas.append(
            RetencionRenta(
                codigo=pendiente["codigo"],
                concepto=nombre,
                n_registros=pendiente["n_registros"],
                base_imponible=pendiente["base_imponible"],
                valor_retenido=pendiente["valor_retenido"],
            )
        )
        pendiente = None

    for raw in lines:
        linea = raw.strip()
        if not linea or _es_encabezado_columna(linea) or linea.upper().startswith("TOTAL"):
            continue
        fila = _parse_fila_renta(linea)
        if fila is not None:
            # Cualquier fila pendiente sin sufijo queda cerrada tal cual:
            # NUNCA hereda el nombre de la fila que sigue.
            _cerrar()
            if fila["nombre_inline"]:
                nombre_previo = " ".join(prefijo).strip()
                fila["nombre_inline"] = (nombre_previo + " " + fila["nombre_inline"]).strip()
                prefijo = []
                pendiente = fila
                _cerrar()
            else:
                fila["nombre_inline"] = " ".join(prefijo).strip()
                prefijo = []
                pendiente = fila
        else:
            if pendiente is not None:
                _cerrar(sufijo=linea)
            else:
                prefijo.append(linea)
    _cerrar()
    return filas


def _totales_renta(lines: list[str]) -> tuple[float, float]:
    for linea in lines:
        if linea.strip().upper().startswith("TOTAL:"):
            numeros = re.findall(r"-?\d+(?:[.,]\d+)*", linea)
            if len(numeros) >= 2:
                base, valor = numeros[-2], numeros[-1]
                return _parse_amount_sri(base) or 0.0, _parse_amount_sri(valor) or 0.0
    return 0.0, 0.0


# ---------------------------------------------------------------------------
# Bloque RETENCION EN LA FUENTE DE IVA
# ---------------------------------------------------------------------------


def _extraer_porcentaje(concepto: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", concepto)
    if m:
        return _parse_amount_sri(m.group(1))
    return None


def _parse_retenciones_iva(lines: list[str]) -> list[RetencionIVA]:
    filas: list[RetencionIVA] = []
    for raw in lines:
        linea = raw.strip()
        if not linea or _es_encabezado_columna(linea) or linea.upper().startswith("TOTAL"):
            continue
        tokens = linea.split()
        if len(tokens) < 3 or not _is_amount(tokens[-1]):
            continue
        operacion = tokens[0]
        concepto = " ".join(tokens[1:-1])
        valor = _parse_amount_sri(tokens[-1]) or 0.0
        filas.append(
            RetencionIVA(
                operacion=operacion,
                concepto=concepto,
                porcentaje=_extraer_porcentaje(concepto),
                valor_retenido=valor,
            )
        )
    return filas


def _total_simple(lines: list[str]) -> float:
    for linea in lines:
        if linea.strip().upper().startswith("TOTAL:"):
            numeros = re.findall(r"-?\d+(?:[.,]\d+)*", linea)
            if numeros:
                return _parse_amount_sri(numeros[-1]) or 0.0
    return 0.0


# ---------------------------------------------------------------------------
# Bloque RESUMEN DE RETENCIONES QUE LE EFECTUARON EN EL PERIODO
# ---------------------------------------------------------------------------


def _parse_le_efectuaron(lines: list[str]) -> tuple[float, float]:
    iva = 0.0
    renta = 0.0
    for raw in lines:
        linea = raw.strip()
        if not linea or _es_encabezado_columna(linea) or linea.upper().startswith("TOTAL"):
            continue
        tokens = linea.split()
        if len(tokens) < 3 or not _is_amount(tokens[-1]):
            continue
        concepto = " ".join(tokens[1:-1])
        valor = _parse_amount_sri(tokens[-1]) or 0.0
        if "IVA" in concepto.upper():
            iva = valor
        elif "RENTA" in concepto.upper():
            renta = valor
    return iva, renta


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def parse_ats_texto(texto: str) -> ResumenATS:
    """Parsea el texto ya extraído de un Talón Resumen (PDF → texto plano)."""
    errores: list[str] = []
    lines = [l for l in texto.splitlines()]

    ruc = _buscar_ruc(texto)
    razon_social = _buscar_razon_social(lines)
    periodo = _buscar_periodo(texto)
    estado = _buscar_estado(texto)
    secuencial = _buscar_secuencial(texto)

    compras = _bloque_totales(lines, inicio="COMPRAS", fin="VENTAS")
    ventas = _bloque_totales(lines, inicio="VENTAS", fin="COMPROBANTES ANULADOS")
    anulados = _buscar_anulados(
        _seccion(lines, "COMPROBANTES ANULADOS", "RESUMEN DE RETENCIONES - AGENTE DE RETENCION")
    )

    seccion_renta = _seccion(
        lines,
        "RETENCION EN LA FUENTE DE IMPUESTO A LA RENTA",
        "RETENCION EN LA FUENTE DE IVA",
    )
    retenciones_renta = _parse_retenciones_renta(seccion_renta)
    renta_base_total, renta_valor_total = _totales_renta(seccion_renta)

    seccion_iva = _seccion(
        lines,
        "RETENCION EN LA FUENTE DE IVA",
        "RESUMEN DE RETENCIONES QUE LE EFECTUARON EN EL PERIODO",
    )
    retenciones_iva = _parse_retenciones_iva(seccion_iva)
    iva_total = _total_simple(seccion_iva)

    seccion_le_efectuaron = _seccion(
        lines, "RESUMEN DE RETENCIONES QUE LE EFECTUARON EN EL PERIODO", None
    )
    iva_le_retuvieron, renta_le_retuvieron = _parse_le_efectuaron(seccion_le_efectuaron)

    if periodo is None:
        errores.append("No se detectó el período del anexo (línea 'Periodo: <MES> <AÑO>').")
    if compras is None:
        errores.append("No se encontró el bloque COMPRAS o su fila TOTAL:.")
    if ventas is None:
        errores.append("No se encontró el bloque VENTAS o su fila TOTAL:.")

    return ResumenATS(
        periodo=periodo,
        ruc=ruc,
        razon_social=razon_social,
        estado=estado,
        secuencial=secuencial,
        compras=compras or BloqueBase(),
        ventas=ventas or BloqueBase(),
        comprobantes_anulados=anulados,
        retenciones_renta=retenciones_renta,
        retenciones_renta_base_total=renta_base_total,
        retenciones_renta_valor_total=renta_valor_total,
        retenciones_iva=retenciones_iva,
        retenciones_iva_total=iva_total,
        iva_que_le_retuvieron=iva_le_retuvieron,
        renta_que_le_retuvieron=renta_le_retuvieron,
        errores=errores,
    )


def parse_ats_pdf(pdf_bytes: bytes) -> ResumenATS:
    """Lee un Talón Resumen en PDF y devuelve su :class:`ResumenATS`."""
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as e:  # noqa: BLE001
        return ResumenATS(periodo=None, errores=[f"No se pudo abrir el PDF del ATS: {e}"])
    if not texto.strip():
        return ResumenATS(periodo=None, errores=["El PDF del ATS no tiene texto extraíble."])
    return parse_ats_texto(texto)


def parse_ats_xml(xml_bytes: bytes) -> ResumenATS:
    """Rama XML del ATS — **pendiente de implementar**.

    No se contó con una muestra real de un ATS en formato XML del SRI al
    construir este parser (ver el spec de diseño del proyecto). Para no
    fingir un parseo exitoso con nombres de nodo inventados, esta función
    devuelve un :class:`ResumenATS` vacío con un error explícito. Cuando
    se disponga de una muestra real, implementar aquí el parseo (lxml/
    ElementTree) siguiendo el mismo contrato que ``parse_ats_pdf``.
    """
    return ResumenATS(
        periodo=None,
        errores=[
            "Parser de ATS en formato XML pendiente de implementar: no se "
            "contó con una muestra real de un anexo XML del SRI al construir "
            "este módulo. Suba el Talón Resumen en PDF, o complete "
            "parse_ats_xml con la estructura real de nodos cuando haya una "
            "muestra disponible."
        ],
    )


def parse_ats(contenido: bytes, nombre_archivo: str) -> ResumenATS:
    """Despacha el parseo del ATS a PDF o XML según extensión/contenido."""
    ext = Path(nombre_archivo).suffix.lower()
    if ext == ".pdf":
        return parse_ats_pdf(contenido)
    if ext == ".xml":
        return parse_ats_xml(contenido)
    cabecera = contenido[:8].lstrip()
    if cabecera.startswith(b"%PDF"):
        return parse_ats_pdf(contenido)
    if cabecera.startswith(b"<"):
        return parse_ats_xml(contenido)
    return ResumenATS(
        periodo=None,
        errores=[f"{nombre_archivo}: formato no reconocido para el ATS (ni PDF ni XML)."],
    )


def parse_all_ats(paths: list[Path]) -> tuple[dict[str, ResumenATS], list[str]]:
    """Lee varios ATS (PDF o XML), los agrupa por período "YYYY-MM"."""
    por_periodo: dict[str, ResumenATS] = {}
    errores: list[str] = []
    for ruta in paths:
        resumen = parse_ats(ruta.read_bytes(), ruta.name)
        errores.extend(f"{ruta.name}: {e}" for e in resumen.errores)
        if not resumen.periodo:
            errores.append(f"{ruta.name}: sin período detectado, se omite del libro.")
            continue
        if resumen.periodo in por_periodo:
            errores.append(
                f"Período {resumen.periodo} duplicado en {ruta.name}; se mantiene el primero"
            )
            continue
        por_periodo[resumen.periodo] = resumen
    return por_periodo, errores
