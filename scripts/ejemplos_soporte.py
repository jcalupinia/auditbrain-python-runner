"""Genera los DOCUMENTOS DE EVIDENCIA DE MUESTRA de los requerimientos de soporte
de las herramientas NIIF (lo que se pide al cliente para poder ejecutar la prueba:
estados bancarios, confirmaciones, políticas, actas, informes de perito, contratos,
facturas, mayores y cédulas de sustento).

A diferencia de ``ejemplos_lote.py`` (poblaciones que alimentan el cálculo, derivadas
del EJEMPLO del procesador), aquí cada requerimiento de SOPORTE no tiene dataset: se
arma un documento de muestra profesional y ficticio en el primer formato aceptado
(PDF para narrativos, XLSX para tabulares), clasificado por su naturaleza. Todo lleva
el aviso «EJEMPLO · datos ficticios» y datos ligados al ejemplo de cálculo donde es
natural, para que el cliente vea qué debe entregar.

Determinista: el PDF de WeasyPrint es estable; los XLSX/DOCX se reescriben con fechas
fijas. Los archivos comiteados no cambian entre corridas.

Uso:
    python scripts/ejemplos_soporte.py                 # escribe los documentos del lote 1
    python scripts/ejemplos_soporte.py --verificar     # valida que cada archivo se generó y abre
    python scripts/ejemplos_soporte.py --manifiesto     # fragmento JS para ejemplosRequerimientos.js
    python scripts/ejemplos_soporte.py cxc_cartera      # solo esa herramienta
"""
from __future__ import annotations

import os
import re
import sys
import unicodedata
import zipfile
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.aud.niif.procesadores import PROCESADORES  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(RAIZ, "frontend", "public", "ejemplos")
NOTA = "EJEMPLO · datos ficticios"
FIRMA = "AuditConsulting Auditores Cía. Ltda."
CLIENTE = "Comercial Andina de Ejemplo S.A."
RUC = "1790000000001"
CORTE = "31/12/2025"
_FIX_DT = (2026, 1, 15, 0, 0, 0)
_FIX = b"2026-01-15T00:00:00Z"

LOTE1 = [
    "efectivo_equivalentes", "cxc_cartera", "inversiones_instrumentos",
    "inventarios_costos", "ppe_propiedad_planta", "propiedades_inversion",
]

# Paleta sobria (identidad AuditConsulting / SIGMANSERVICE).
NAVY, GOLD, GRIS = "#0A2342", "#C7A83C", "#6B7280"


def _slug(t):
    s = unicodedata.normalize("NFD", str(t or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:48]


def _normalizar_zip(path):
    with zipfile.ZipFile(path) as z:
        items = [(i.filename, i.external_attr, z.read(i.filename)) for i in z.infolist()]
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, attr, data in items:
            if nombre == "docProps/core.xml":
                data = re.sub(rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:(?:created|modified)>)",
                              rb"\g<1>" + _FIX + rb"\g<2>", data)
            zi = zipfile.ZipInfo(nombre, date_time=_FIX_DT)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = attr
            z.writestr(zi, data)
    os.replace(tmp, path)


# --- clasificación por naturaleza del documento -----------------------------------

def clasificar(doc: str) -> str:
    t = _slug(doc)
    if "confirmacion" in t or "confirmaciones" in t:
        return "confirmacion"
    if "politica" in t:
        return "politica"
    if "acta" in t or "instrucciones_del_recuento" in t or "cambios_de_uso" in t:
        return "acta"
    if "estados_bancarios" in t or "estado_de_cuenta" in t or "conciliaciones" in t or "estados_de_cuenta" in t:
        return "estado_banc"
    if any(k in t for k in ("perito", "tasacion", "valuacion", "valuaciones", "precios", "vector", "revaluacion", "informe")):
        return "informe_val"
    if any(k in t for k in ("contrato", "pagare", "prospecto", "escritura", "arrendamiento", "titulos", "certificados", "certificado")):
        return "contrato"
    if any(k in t for k in ("factura", "guia", "recibo", "aviso", "dividendos")):
        return "comprobante"
    return "cedula"


# --- filas de tie-in con el ejemplo de cálculo ------------------------------------

def _rows(pid, ds, n=3):
    E = getattr(PROCESADORES[pid], "EJEMPLO", None)
    filas = (E or {}).get("datasets", {}).get(ds, []) if E else []
    return [{k: v for k, v in f.items() if k != "_row"} for f in filas[:n]]


# --- tablas específicas de los requerimientos tabulares (XLSX) --------------------

def tabla(pid, rid, req):
    """(titulo, columnas, filas) para un requerimiento cuyo primer formato es XLSX."""
    if pid == "cxc_cartera" and rid == "RQ-002":
        filas = [[r["id"], r["cliente"], r.get("saldo", ""), 0, 0] for r in _rows(pid, "cartera")]
        return ("Mayor de cuentas por cobrar, deterioro y descuentos",
                ["Documento", "Cliente", "Saldo al corte", "Deterioro registrado", "Intereses registrados"], filas)
    if pid == "inventarios_costos" and rid == "RQ-006":
        return ("Ventas y precios posteriores al cierre; costos de terminación y venta",
                ["Ítem", "Fecha venta posterior", "Precio de venta", "Costo de terminación", "Costo de venta"],
                [["A-001", "15/01/2026", 4.0, 0, 0.3], ["A-002", "20/01/2026", 2.0, 0, 0.1]])
    if pid == "inventarios_costos" and rid == "RQ-009":
        return ("Inventario de terceros o en consignación (excluir de la existencia propia)",
                ["Ítem", "Propietario", "Cantidad", "Ubicación", "Observación"],
                [["C-501", "Distribuidora Beta S.A.", 200, "BOD2", "En consignación"],
                 ["C-502", "Importadora Gamma S.A.", 50, "BOD2", "Mercadería de terceros"]])
    if pid == "inventarios_costos" and rid == "RQ-010":
        return ("Costeo estándar y lista de precios de los productos terminados",
                ["Producto terminado", "Costo estándar", "Precio de lista", "Margen"],
                [["PT-01 Ensamble A", 18.5, 25.0, 6.5], ["PT-02 Ensamble B", 12.0, 15.0, 3.0]])
    if pid == "ppe_propiedad_planta" and rid == "RQ-006":
        return ("Cálculo del importe recuperable (mayor entre valor en uso y valor razonable menos costos de venta)",
                ["Activo / UGE", "Valor en libros", "Valor en uso", "Valor razonable − costos", "Importe recuperable", "Deterioro"],
                [["EDIF-01 Edificio administrativo", 376250, 390000, 385000, 390000, 0]])
    if pid == "propiedades_inversion" and rid == "RQ-007":
        return ("Gastos directos de operación por inmueble (NIC 40.75 f))",
                ["Inmueble", "Gastos que generaron renta", "Gastos sin renta asociada"],
                [["IP-01 Edificio de oficinas Norte", 6200, 0], ["IP-02 Terreno Samborondón", 0, 1500]])
    if pid == "propiedades_inversion" and rid == "RQ-008":
        return ("Base fiscal de los inmuebles (impuesto diferido)",
                ["Inmueble", "Base contable", "Base fiscal", "Diferencia temporaria"],
                [["IP-01 Edificio de oficinas Norte", 720000, 480000, 240000],
                 ["IP-02 Terreno Samborondón", 380000, 300000, 80000]])
    if pid == "propiedades_inversion" and rid == "RQ-009":
        return ("Auxiliar del superávit de revaluación por inmueble y su arrastre en patrimonio",
                ["Inmueble", "Superávit inicial", "Movimiento del año", "Superávit final"],
                [["IP-01 Edificio de oficinas Norte", 200000, 20000, 220000]])
    # genérica: eco del contenido pedido
    return (req.get("document", "Documento de sustento"),
            ["Concepto", "Detalle", "Importe"],
            [["(complete con su información)", req.get("purpose", ""), 0]])


# --- render XLSX ------------------------------------------------------------------

def escribir_xlsx(ruta, titulo, columnas, filas, req):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Datos"
    thin = Side(style="thin", color="D0D0D0")
    borde = Border(left=thin, right=thin, top=thin, bottom=thin)
    ws["A1"] = titulo
    ws["A1"].font = Font(name="Calibri", size=12, bold=True, color="0A2342")
    ws["A2"] = f"{NOTA} — {CLIENTE} (RUC {RUC}) · Corte {CORTE}"
    ws["A2"].font = Font(name="Calibri", size=9, italic=True, color="6B7280")
    hdr = 4
    for j, c in enumerate(columnas, start=1):
        cel = ws.cell(row=hdr, column=j, value=c)
        cel.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        cel.fill = PatternFill("solid", fgColor="0A2342")
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cel.border = borde
    for i, fila in enumerate(filas, start=hdr + 1):
        for j, v in enumerate(fila, start=1):
            cel = ws.cell(row=i, column=j, value=v)
            cel.font = Font(name="Calibri", size=9)
            cel.border = borde
            if isinstance(v, (int, float)):
                cel.number_format = "#,##0.00"
                cel.alignment = Alignment(horizontal="right")
    for j, c in enumerate(columnas, start=1):
        ws.column_dimensions[chr(64 + j)].width = max(16, min(38, len(str(c)) + 6))
    lee = wb.create_sheet("Léame")
    lee["A1"] = NOTA
    lee["A3"] = req.get("document", "")
    lee["A5"] = req.get("purpose", "")
    if req.get("content"):
        lee["A7"] = req["content"]
    lee["A9"] = ("Documento de evidencia de muestra con datos ficticios. Reemplace las filas por las de "
                 "su empresa; es el sustento que la prueba requiere del cliente.")
    wb.active = 0
    creado = datetime(2026, 1, 15)
    wb.properties.creator = f"{FIRMA} · Ejemplo de evidencia"
    wb.properties.created = creado
    wb.properties.modified = creado
    wb.save(ruta)
    _normalizar_zip(ruta)


# --- render PDF (WeasyPrint desde HTML) -------------------------------------------

def _tabla_html(columnas, filas):
    th = "".join(f"<th>{c}</th>" for c in columnas)
    trs = "".join("<tr>" + "".join(f"<td>{'' if v is None else v}</td>" for v in f) + "</tr>" for f in filas)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def cuerpo_html(cat, pid, rid, req):
    doc = req.get("document", "")
    purpose = req.get("purpose", "")
    content = req.get("content", "")
    if cat == "confirmacion":
        tercero = {"cxc_cartera": "el cliente", "inversiones_instrumentos": "el custodio / casa de valores"}.get(pid, "el banco")
        rows = _rows("cxc_cartera", "cartera", 2) if pid == "cxc_cartera" else _rows("efectivo_equivalentes", "cuentas", 2)
        cuerpo = ("<p>Por medio de la presente, y a solicitud de nuestros auditores externos "
                  f"<strong>{FIRMA}</strong>, confirmamos los saldos mantenidos con <strong>{CLIENTE}</strong> "
                  f"al {CORTE}:</p>")
        if pid == "cxc_cartera":
            cuerpo += _tabla_html(["Documento", "Saldo confirmado (USD)"], [[r["id"], r.get("saldo", "")] for r in rows])
        else:
            cuerpo += _tabla_html(["Cuenta", "Saldo confirmado (USD)", "¿Restricciones?"],
                                  [[r["nombre"], r.get("saldo_banco", ""), "Ninguna"] for r in rows])
        cuerpo += (f"<p>La información responde exclusivamente al requerimiento de confirmación dirigido a {tercero}. "
                   "Firma y sello autorizados a continuación.</p>"
                   "<div class='firmas'><div>_____________________<br>Firma autorizada</div>"
                   "<div>_____________________<br>Sello institucional</div></div>")
        return "Carta de confirmación (respuesta recibida)", cuerpo
    if cat == "politica":
        return "Política contable", (
            f"<p>{purpose}. Documento aprobado por la administración de {CLIENTE}.</p>"
            "<h3>1. Reconocimiento y medición</h3><p>Se aplica el marco contable vigente del encargo. "
            "Los criterios se documentan y revisan al cierre de cada ejercicio.</p>"
            "<h3>2. Estimaciones y juicios</h3><p>Tramos, tasas, vidas útiles o supuestos se sustentan en "
            "evidencia histórica y se aprueban por el nivel competente.</p>"
            "<h3>3. Revelación</h3><p>Se revela la composición y los cambios de política conforme a la norma aplicable.</p>"
            + (f"<p class='muted'>Contenido mínimo esperado: {content}</p>" if content else ""))
    if cat == "acta":
        return "Acta", (
            f"<p>En la ciudad de Quito, siendo el {CORTE}, se reúnen los responsables designados por "
            f"<strong>{CLIENTE}</strong> para dejar constancia de: {purpose}.</p>"
            "<h3>Desarrollo</h3><p>Se ejecutó el procedimiento con la presencia del personal autorizado y del "
            "auditor observador. Los resultados se anexan y forman parte integrante de esta acta.</p>"
            + (f"<p class='muted'>Alcance: {content}</p>" if content else "")
            + "<div class='firmas'><div>_____________________<br>Responsable de la entidad</div>"
              "<div>_____________________<br>Auditor observador</div></div>")
    if cat == "estado_banc":
        rows = _rows("efectivo_equivalentes", "cuentas", 3)
        tabla_html = _tabla_html(["Cuenta", "Saldo según banco (USD)"], [[r["nombre"], r.get("saldo_banco", "")] for r in rows])
        return "Estado de cuenta bancario", (
            f"<p>Estado de cuenta emitido a nombre de <strong>{CLIENTE}</strong> correspondiente al mes de corte "
            f"({CORTE}) y su ventana posterior de depuración. {purpose}.</p>" + tabla_html +
            "<p class='muted'>Se adjuntan los movimientos del período que sustentan las partidas conciliatorias.</p>")
    if cat == "informe_val":
        return "Informe de valoración / tasación", (
            f"<p>Informe emitido por perito independiente registrado, a solicitud de <strong>{CLIENTE}</strong>, "
            f"con fecha de referencia {CORTE}. {purpose}.</p>"
            "<h3>Metodología</h3><p>Se aplicó un enfoque de mercado con jerarquía de valor razonable Nivel 2, "
            "usando transacciones comparables y variables observables.</p>"
            "<h3>Conclusión de valor</h3><p>El valor razonable estimado consta en el anexo de la prueba (datos ficticios). "
            "El perito declara independencia y competencia técnica.</p>"
            + (f"<p class='muted'>Debe sustentar: {content}</p>" if content else ""))
    if cat == "contrato":
        return "Contrato / título", (
            f"<p>Instrumento suscrito por <strong>{CLIENTE}</strong> que sustenta: {purpose}.</p>"
            "<h3>Cláusulas relevantes</h3><ul><li>Partes, objeto y plazo.</li>"
            "<li>Tasa, flujos contractuales o condiciones de la garantía.</li>"
            "<li>Fechas de inicio, vencimiento y liquidación.</li></ul>"
            + (f"<p class='muted'>Contenido esperado: {content}</p>" if content else "")
            + "<div class='firmas'><div>_____________________<br>Representante legal</div>"
              "<div>_____________________<br>Contraparte</div></div>")
    if cat == "comprobante":
        return "Comprobante / aviso", (
            f"<p>Documento emitido dentro del giro de <strong>{CLIENTE}</strong> que respalda: {purpose}.</p>"
            + _tabla_html(["Documento", "Fecha", "Detalle", "Importe (USD)"],
                          [["F-1001", CORTE, "Sustento de la operación (ejemplo)", "0.00"]])
            + (f"<p class='muted'>Debe evidenciar: {content}</p>" if content else ""))
    # cédula por defecto (pdf de una tabla)
    titulo, cols, filas = tabla(pid, rid, req)
    return "Cédula de sustento", f"<p>{purpose}.</p>" + _tabla_html(cols, filas)


def escribir_pdf(ruta, cat, pid, rid, req):
    import weasyprint

    subtitulo, cuerpo = cuerpo_html(cat, pid, rid, req)
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><style>
    @page {{ size: A4; margin: 1.6cm; }}
    body {{ font-family: 'DejaVu Sans', Arial, sans-serif; color: #1a1a1a; font-size: 11px; }}
    .banner {{ background: {GOLD}; color: {NAVY}; font-weight: bold; padding: 4px 10px; border-radius: 4px;
               display: inline-block; letter-spacing: .04em; font-size: 10px; }}
    .head {{ border-bottom: 3px solid {NAVY}; padding-bottom: 8px; margin-bottom: 14px; }}
    .firm {{ color: {NAVY}; font-weight: bold; font-size: 13px; }}
    .meta {{ color: {GRIS}; font-size: 10px; }}
    h1 {{ color: {NAVY}; font-size: 16px; margin: 6px 0 2px; }}
    h2 {{ color: {NAVY}; font-size: 12px; margin: 2px 0 12px; font-weight: normal; }}
    h3 {{ color: {NAVY}; font-size: 12px; margin: 12px 0 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
    th {{ background: {NAVY}; color: #fff; font-size: 10px; padding: 5px 7px; text-align: left; }}
    td {{ border: 1px solid #d8d8d8; font-size: 10px; padding: 4px 7px; }}
    .muted {{ color: {GRIS}; font-size: 10px; }}
    .firmas {{ display: flex; gap: 40px; margin-top: 34px; color: {GRIS}; font-size: 10px; }}
    .foot {{ margin-top: 22px; border-top: 1px solid #ccc; padding-top: 6px; color: {GRIS}; font-size: 9px; }}
    </style></head><body>
    <div class="head">
      <span class="banner">{NOTA}</span>
      <div class="firm">{CLIENTE} · RUC {RUC}</div>
      <div class="meta">Corte {CORTE} · Requerimiento {rid} · Auditores: {FIRMA}</div>
    </div>
    <h1>{subtitulo}</h1>
    <h2>{req.get('document','')}</h2>
    {cuerpo}
    <div class="foot">Documento de evidencia de <strong>muestra</strong> con datos ficticios, generado para
    ilustrar el formato que el cliente debe entregar. No corresponde a una operación real.</div>
    </body></html>"""
    with open(ruta, "wb") as fh:
        fh.write(weasyprint.HTML(string=html).write_pdf())


# --- orquestación -----------------------------------------------------------------

def _soporte(pid):
    d = PROCESADORES[pid].definicion()
    out = []
    for r in d.get("requests", []):
        if r.get("dataset"):
            continue
        formats = r.get("formats", [])
        fmt = formats[0] if formats else "pdf"
        cat = clasificar(r.get("document", ""))
        nombre = f"{r['id']}_{_slug(r.get('document',''))}.{fmt}"
        out.append((r, fmt, cat, nombre))
    return out


def escribir(pids):
    total = 0
    for pid in pids:
        destino = os.path.join(PUB, pid)
        os.makedirs(destino, exist_ok=True)
        for r, fmt, cat, nombre in _soporte(pid):
            ruta = os.path.join(destino, nombre)
            if fmt == "xlsx":
                titulo, cols, filas = tabla(pid, r["id"], r)
                escribir_xlsx(ruta, titulo, cols, filas, r)
            elif fmt == "docx":
                escribir_docx(ruta, cat, pid, r["id"], r)
            else:
                escribir_pdf(ruta, cat, pid, r["id"], r)
            total += 1
        print(f"  {pid}: {len(_soporte(pid))} documento(s) de soporte")
    print(f"Escritos {total} documentos de evidencia de muestra.")


def escribir_docx(ruta, cat, pid, rid, req):
    from docx import Document

    subtitulo, _cuerpo = cuerpo_html(cat, pid, rid, req)
    doc = Document()
    doc.add_heading(f"{subtitulo} ({NOTA})", level=0)
    doc.add_paragraph(f"{CLIENTE} · RUC {RUC} · Corte {CORTE} · Requerimiento {rid}")
    doc.add_paragraph(req.get("document", ""))
    doc.add_paragraph(req.get("purpose", ""))
    if req.get("content"):
        doc.add_heading("Contenido esperado", level=1)
        doc.add_paragraph(req["content"])
    doc.add_paragraph("Documento de evidencia de muestra con datos ficticios; ilustra el formato que el "
                      "cliente debe entregar. No corresponde a una operación real.")
    doc.core_properties.author = f"{FIRMA} · Ejemplo de evidencia"
    doc.save(ruta)
    _normalizar_zip(ruta)


def manifiesto(pids):
    print("  // --- Lote 1 · documentos de evidencia de soporte (scripts/ejemplos_soporte.py) ---")
    for pid in pids:
        sop = _soporte(pid)
        if not sop:
            continue
        print(f"  // {pid}:")
        for r, fmt, cat, nombre in sop:
            print(f'  //   "{r["id"]}": "{nombre}",   ({fmt}, {cat})')


def verificar(pids) -> bool:
    from openpyxl import load_workbook
    ok = True
    for pid in pids:
        destino = os.path.join(PUB, pid)
        for r, fmt, cat, nombre in _soporte(pid):
            ruta = os.path.join(destino, nombre)
            if not os.path.exists(ruta):
                print(f"  [FALTA] {pid}/{nombre}")
                ok = False
                continue
            data = open(ruta, "rb").read()
            if fmt == "pdf":
                good = data[:5] == b"%PDF-" and len(data) > 1500
            elif fmt == "xlsx":
                try:
                    load_workbook(ruta)
                    good = True
                except Exception as e:  # noqa: BLE001
                    good = False
                    print(f"  [XLSX ROTO] {pid}/{nombre}: {e}")
            else:
                good = data[:2] == b"PK"
            print(f"  [{'OK' if good else 'MAL'}] {pid}/{nombre} ({fmt}, {cat}, {len(data)} B)")
            ok = ok and good
    print("RESULTADO:", "OK" if ok else "REVISAR")
    return ok


def _pids():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    pids = args or LOTE1
    faltan = [p for p in pids if p not in PROCESADORES]
    if faltan:
        raise SystemExit(f"Procesadores desconocidos: {faltan}")
    return pids


def main():
    pids = _pids()
    if "--manifiesto" in sys.argv:
        manifiesto(pids)
    elif "--verificar" in sys.argv:
        sys.exit(0 if verificar(pids) else 1)
    else:
        escribir(pids)


if __name__ == "__main__":
    main()
