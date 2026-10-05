"""El Excel del papel de trabajo NO puede levantar el cuadro de «reparaciones».

Síntoma reportado por el dueño (2026-10-03): al abrir el Excel de Efectivo, Excel
avisaba «pudo abrir el archivo reparando… Parte quitada: /xl/drawings/drawing1.xml
(Forma de dibujo)». Eso ocurre cuando el XML de un dibujo (portada: logos + gráficos
nativos) NO está bien formado.

El test `test_aud_papel_premium` solo comprobaba que `openpyxl.load_workbook` abra el
archivo, pero openpyxl NO valida los dibujos: un drawing mal formado pasa ese test y
aun así Excel lo repara. Aquí validamos cada `xl/drawings/drawing*.xml` con un parser
XML real, para todas las herramientas del catálogo.

El punto frágil es `libro._imagenes_con_marco`, que inyecta `<a:xfrm>` por regex en el
XML del dibujo; ahora valida el resultado y, si no parsea, conserva el original.
"""
import io
import zipfile
from xml.etree import ElementTree as ET

from backend.app.aud.niif import ejercicio_modelo as em
from backend.app.aud.niif.procesadores import PROCESADORES, libro


def _papel(pid):
    mod = PROCESADORES[pid]
    d = mod.definicion()
    ds, par, corte = em.escenario(mod)
    reg = em._reg(d, mod, ds, par, corte)
    return libro.xlsx(d, reg, [], 1, "APROBADO")


def _drawings_bien_formados(data: bytes) -> list[str]:
    malos = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in z.namelist():
            if n.startswith("xl/drawings/drawing") and n.endswith(".xml"):
                try:
                    ET.fromstring(z.read(n))
                except ET.ParseError as e:
                    malos.append(f"{n}: {e}")
    return malos


def test_efectivo_dibujos_de_la_portada_son_xml_valido():
    malos = _drawings_bien_formados(_papel("efectivo_equivalentes"))
    assert not malos, f"Dibujos mal formados (Excel levantaría «reparaciones»): {malos}"


def test_todas_las_herramientas_emiten_dibujos_validos():
    fallos = {}
    for pid in PROCESADORES:
        malos = _drawings_bien_formados(_papel(pid))
        if malos:
            fallos[pid] = malos
    assert not fallos, f"Herramientas con dibujos mal formados: {fallos}"


def test_imagenes_con_marco_conserva_el_dibujo_si_la_regex_rompe_el_xml():
    # Un drawing donde la cirugía por regex produciría XML inválido debe quedar INTACTO.
    roto = (
        '<?xml version="1.0"?>'
        '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">'
        '<ext cx="100" cy="200"/><pic><spPr></malformado></xdr:wsDr>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/drawings/drawing1.xml", roto)
    salida = libro._imagenes_con_marco(buf.getvalue())
    with zipfile.ZipFile(io.BytesIO(salida)) as z:
        # Se conserva el original tal cual (no se inyectó el marco que rompería el XML).
        assert z.read("xl/drawings/drawing1.xml").decode("utf-8") == roto
