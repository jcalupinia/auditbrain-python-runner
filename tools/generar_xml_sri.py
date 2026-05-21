"""Genera el XML de la Declaracion Patrimonial del SRI a partir del libro Excel
producido por declaracion_patrimonial_excel.py.

Lee las hojas de cada modulo, toma los valores de la columna del anio indicado
y reconstruye el XML respetando las etiquetas y el orden del esquema del SRI.

ALCANCE ACTUAL: se generan la cabecera, el bloque de patrimonio, la
justificacion y los 4 modulos cuyas etiquetas XML estan confirmadas a partir de
un XML real del SRI (dinero, vehiculos, bienes inmuebles y pasivos). Los otros
4 modulos de activo (derechos representativos de capital, cuentas por cobrar,
bienes muebles, derechos y otros activos) se incorporaran cuando se disponga de
un XML real del SRI que los contenga, para confirmar sus etiquetas exactas.

Uso:
    python tools/generar_xml_sri.py LIBRO.xlsx [SALIDA.xml] [--anio AAAA]
"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import load_workbook

ENCODING_XML = "ISO-8859-1"

# Modulos con etiquetas XML confirmadas. Para cada uno:
#   hoja, contenedor, detalle, y la lista ordenada de elementos a emitir.
# Cada elemento: (encabezado_columna_en_excel | None, etiqueta_xml, es_codigo)
#   - si encabezado es None se trata de un caso especial resuelto en codigo.
MODULOS_XML = {
    "dinero": {
        "hoja": "Dinero", "contenedor": "dinero", "detalle": "detalleDinero",
        "elementos": [
            ("Dinero en", "dineroEn", True),
            ("Tipo de inversion", "tipoInversion", True),
            ("Ubicacion", "ubicacion", True),
            ("Pais", "pais", True),
            (None, "_ifi", False),
            ("Tipo de moneda", "tipoMoneda", False),
            ("__valor__", "saldo", False),
            ("Partes relacionadas", "partesRelacionadas", True),
        ],
    },
    "vehiculos": {
        "hoja": "Vehiculos", "contenedor": "vehiculos",
        "detalle": "detalleVehiculos",
        "elementos": [
            ("Tipo de vehiculo", "tipoVehiculo", True),
            ("Registro / placa / chasis", "placa", False),
            ("Ubicacion", "ubicacion", True),
            ("Pais", "pais", True),
            ("__valor__", "valor", False),
        ],
    },
    "inmuebles": {
        "hoja": "Bienes Inmuebles", "contenedor": "bienesInmuebles",
        "detalle": "detalleBienesInmuebles",
        "elementos": [
            ("Tipo de inmueble", "tipoInmueble", True),
            ("Ubicacion", "ubicacion", True),
            ("Pais", "codPais", True),
            ("Provincia", "provincia", True),
            ("Canton", "canton", True),
            ("Fecha de inscripcion", "fechaInscripcion", False),
            ("Clave catastral", "claveCat", False),
            ("__valor__", "valor", False),
        ],
    },
    "pasivo": {
        "hoja": "Pasivos", "contenedor": "pasivo", "detalle": "detallePasivo",
        "elementos": [
            ("Tipo de acreedor", "tipoAcreedor", True),
            ("Domicilio del acreedor", "domicilioAcreedor", True),
            ("__valor__", "valorDeuda", False),
            ("Pais", "paisAcreedor", True),
            ("Nombre del acreedor", "nombreAcreedor", False),
            ("Tipo de identificacion", "tipoIdentificacionAcreedor", True),
            ("N. de identificacion", "numeroIdentificacionAcreedor", False),
            ("N. registro Banco Central", "numeroRegistroBancoCentral", False),
            ("Partes relacionadas", "partesRelacionadas", True),
        ],
    },
}

MODULOS_PENDIENTES = [
    "Derechos de Capital", "Cuentas por Cobrar", "Bienes Muebles",
    "Derechos", "Otros Activos",
]


def _code(v):
    """Extrae el codigo de un valor 'codigo - descripcion'."""
    if v is None:
        return ""
    s = str(v).strip()
    return s.split(" - ", 1)[0].strip() if " - " in s else s


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _esc(texto):
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _header_cols(ws):
    """Devuelve (n_desc, col_valores_por_anio) leyendo la fila 5."""
    valores = {}
    n_desc = 0
    for col in range(1, ws.max_column + 1):
        h = ws.cell(row=5, column=col).value
        if not h:
            continue
        if str(h).startswith("Valor "):
            anio = str(h).replace("Valor", "").strip()
            valores[anio] = col
        elif not valores:
            n_desc = col
    return n_desc, valores


def _leer_modulo(wb, hoja, anio):
    """Lee las filas de detalle de una hoja de modulo para el anio dado."""
    ws = wb[hoja]
    n_desc, valores = _header_cols(ws)
    col_val = valores.get(str(anio)) or min(valores.values())
    # encabezados descriptivos
    headers = [ws.cell(row=5, column=c).value for c in range(1, n_desc + 1)]
    filas = []
    r = 6
    while r <= ws.max_row:
        primera = ws.cell(row=r, column=1).value
        if primera == "TOTAL":
            break
        registro = {headers[c - 1]: ws.cell(row=r, column=c).value
                    for c in range(1, n_desc + 1)}
        registro["__valor__"] = _num(ws.cell(row=r, column=col_val).value)
        filas.append(registro)
        r += 1
    return filas


def _datos_generales(wb):
    """Lee la hoja 'Datos del XML' en un diccionario por etiqueta."""
    ws = wb["Datos del XML"]
    datos = {}
    for r in range(1, ws.max_row + 1):
        etiqueta = ws.cell(row=r, column=1).value
        valor = ws.cell(row=r, column=2).value
        if etiqueta:
            datos[str(etiqueta).strip()] = valor
    return datos


def _justificacion(wb):
    """Devuelve la lista de codigos de justificacion con monto asignado."""
    if "Justificacion" not in wb.sheetnames:
        return []
    ws = wb["Justificacion"]
    codigos = []
    for r in range(1, ws.max_row + 1):
        etiqueta = ws.cell(row=r, column=2).value
        monto = ws.cell(row=r, column=5).value
        if etiqueta and " - " in str(etiqueta) and _num(monto) > 0:
            codigos.append(_code(etiqueta))
    return codigos


def _detalle_xml(detalle_tag, elementos, registro):
    """Construye un bloque <detalle...> a partir de un registro de fila."""
    lineas = [f"<{detalle_tag}>"]
    for header, tag, _es_codigo in elementos:
        if tag == "_ifi":
            inst = registro.get("Institucion financiera")
            if not inst:
                continue
            txt = str(inst).strip()
            if " - " in txt and _code(txt).isdigit():
                lineas.append(f"    <ifiEcuador>{_code(txt)}</ifiEcuador>")
            else:
                lineas.append(f"    <nombreIfiExterior>{_esc(txt)}"
                               f"</nombreIfiExterior>")
            continue
        if header == "__valor__":
            valor = registro.get("__valor__", 0.0)
            lineas.append(f"    <{tag}>{valor:.2f}</{tag}>")
            continue
        crudo = registro.get(header)
        if crudo is None or str(crudo).strip() == "":
            continue
        valor = _code(crudo) if _es_codigo else str(crudo).strip()
        lineas.append(f"    <{tag}>{_esc(valor)}</{tag}>")
    lineas.append(f"</{detalle_tag}>")
    return "\n".join(lineas)


def _patrimonio_anio(wb, anio):
    """Patrimonio neto (activos - pasivos) calculado para un anio dado."""
    act = sum(f["__valor__"]
              for k in ("dinero", "vehiculos", "inmuebles")
              for f in _leer_modulo(wb, MODULOS_XML[k]["hoja"], anio))
    pas = sum(f["__valor__"]
              for f in _leer_modulo(wb, MODULOS_XML["pasivo"]["hoja"], anio))
    return round(act - pas, 2)


def generar_xml(libro: Path, anio: int) -> str:
    wb = load_workbook(libro, data_only=True)
    dg = _datos_generales(wb)

    tipo_dec = _code(dg.get("Tipo de declaracion"))
    tipo_ident = _code(dg.get("Tipo de identificacion"))
    num_ident = dg.get("Numero de identificacion") or ""
    nombre = dg.get("Nombre del declarante") or ""
    tipo_ident_cony = _code(dg.get("Identificacion del conyuge"))
    num_ident_cony = dg.get("Numero ident. conyuge") or ""
    nombre_cony = dg.get("Nombre del conyuge") or ""
    total_creditos = _num(dg.get("Total creditos"))

    # El patrimonio del anio anterior se calcula con la columna del anio
    # previo si existe en el libro; si no, se toma el dato del XML original.
    _, columnas = _header_cols(wb["Dinero"])
    anios_libro = {int(a) for a in columnas if a.isdigit()}
    if (anio - 1) in anios_libro:
        anio_anterior = _patrimonio_anio(wb, anio - 1)
    else:
        anio_anterior = _num(dg.get("Patrimonio del anio anterior"))

    modulos = {k: _leer_modulo(wb, v["hoja"], anio)
               for k, v in MODULOS_XML.items()}

    total_activos = sum(
        f["__valor__"] for k in ("dinero", "vehiculos", "inmuebles")
        for f in modulos[k])
    total_pasivos = sum(f["__valor__"] for f in modulos["pasivo"])
    total_declarado = round(total_activos - total_pasivos, 2)
    diff = round(total_declarado - anio_anterior, 2)

    soc = total_declarado if tipo_dec == "SOC" else 0.0
    ind = total_declarado if tipo_dec == "IND" else 0.0
    if tipo_dec not in ("SOC", "IND"):
        soc = total_declarado

    out = ['<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>',
           "<decPat>"]
    out.append(f"    <anio>{anio}</anio>")
    out.append(f"    <tipoDec>{_esc(tipo_dec)}</tipoDec>")
    out.append(f"    <tipoIdent>{_esc(tipo_ident)}</tipoIdent>")
    out.append(f"    <numIdent>{_esc(num_ident)}</numIdent>")
    out.append(f"    <nombre>{_esc(nombre)}</nombre>")
    if tipo_ident_cony:
        out.append(f"    <tipoIdentCony>{_esc(tipo_ident_cony)}</tipoIdentCony>")
    if num_ident_cony:
        out.append(f"    <numIdentCony>{_esc(num_ident_cony)}</numIdentCony>")
    if nombre_cony:
        out.append(f"    <nombreCony>{_esc(nombre_cony)}</nombreCony>")
    out.append(f"    <totalCreditos>{total_creditos:.2f}</totalCreditos>")

    # patrimonio
    out.append("    <patrimonio>")
    out.append(f"        <totalDeclarado>{total_declarado:.2f}"
               f"</totalDeclarado>")
    out.append("        <atribuibleHijos>0.00</atribuibleHijos>")
    out.append(f"        <sociedadConyugal>{soc:.2f}</sociedadConyugal>")
    out.append(f"        <individual>{ind:.2f}</individual>")
    out.append(f"        <anioAnterior>{anio_anterior:.2f}</anioAnterior>")
    if diff >= 0:
        out.append(f"        <crecimientoPat>{diff:.2f}</crecimientoPat>")
    else:
        out.append(f"        <decrecimientoPat>{abs(diff):.2f}"
                    f"</decrecimientoPat>")
    just = _justificacion(wb)
    out.append("    <justificacion>")
    for cod in just:
        out.append("<detalleJustificacion>")
        out.append(f"    <justificVariacion>{_esc(cod)}</justificVariacion>")
        out.append("</detalleJustificacion>")
    out.append("</justificacion></patrimonio>")

    # modulos confirmados
    for key in ("dinero", "vehiculos", "inmuebles", "pasivo"):
        spec = MODULOS_XML[key]
        filas = [f for f in modulos[key] if f["__valor__"] > 0]
        out.append(f"<{spec['contenedor']}>")
        for f in filas:
            out.append(_detalle_xml(spec["detalle"], spec["elementos"], f))
        out.append(f"</{spec['contenedor']}>")

    out.append("</decPat>")
    return "\n".join(out)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    opts = {a.split("=")[0]: a.split("=")[1]
            for a in argv[1:] if a.startswith("--") and "=" in a}
    if not args:
        print(__doc__)
        return 1
    libro = Path(args[0])
    if not libro.exists():
        print(f"No existe el libro: {libro}")
        return 1

    wb = load_workbook(libro, data_only=True, read_only=True)
    _, valores = _header_cols(wb["Dinero"])
    wb.close()
    anios = sorted(int(a) for a in valores if a.isdigit())
    anio = int(opts.get("--anio", anios[-1] if anios else 2025))

    salida = Path(args[1]) if len(args) > 1 else libro.with_name(
        f"DeclaracionPatrimonial_{anio}.xml")
    xml = generar_xml(libro, anio)
    salida.write_bytes(xml.encode(ENCODING_XML, errors="replace"))
    print(f"XML generado: {salida}  (anio {anio})")
    print("Modulos pendientes de etiquetas XML reales: "
          + ", ".join(MODULOS_PENDIENTES))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
