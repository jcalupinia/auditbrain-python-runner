"""Citación de evidencia: contrato, pdfplumber y Vision (P1-E)."""
import io
import sys
import types

import pytest

from backend.app.evidence import citation as C
from backend.app.evidence.citation import (
    BoundingBox,
    PaginaTexto,
    PalabraUbicada,
    SourceReference,
    hash_de_archivo,
    source_id_de,
)


def _v(x, y):
    return types.SimpleNamespace(x=x, y=y)


# --- Task 1: contrato -------------------------------------------------------
def test_hash_y_source_id():
    h = hash_de_archivo(b"abc")
    assert len(h) == 64 and h == hash_de_archivo(b"abc")
    a = source_id_de(h, "p3#cas550")
    assert a == source_id_de(h, "p3#cas550")
    assert a != source_id_de(h, "p4#cas550")


def test_bbox_desde_pdfplumber():
    b = BoundingBox.desde_palabra_pdfplumber({"x0": 1, "x1": 9, "top": 2, "bottom": 5})
    assert (b.x0, b.y0, b.x1, b.y1, b.unidad) == (1, 2, 9, 5, "pt")
    assert b.ancho == 8 and b.alto == 3


def test_bbox_desde_vision_norm_y_px():
    poly_norm = types.SimpleNamespace(
        normalized_vertices=[_v(0.1, 0.2), _v(0.5, 0.2), _v(0.5, 0.6), _v(0.1, 0.6)],
        vertices=[],
    )
    bn = BoundingBox.desde_bounding_poly_vision(poly_norm)
    assert bn.unidad == "norm" and (bn.x0, bn.y0, bn.x1, bn.y1) == (0.1, 0.2, 0.5, 0.6)

    poly_px = types.SimpleNamespace(
        normalized_vertices=[], vertices=[_v(10, 20), _v(50, 20), _v(50, 60), _v(10, 60)]
    )
    bp = BoundingBox.desde_bounding_poly_vision(poly_px)
    assert bp.unidad == "px" and (bp.x0, bp.x1) == (10, 50)


def test_bbox_normalizado():
    b = BoundingBox(10, 20, 50, 60, unidad="px", ancho_pagina=100, alto_pagina=200)
    n = b.normalizado()
    assert n.unidad == "norm" and n.x0 == 0.1 and n.y1 == 0.3
    assert n.normalizado() is n  # ya norm → igual


def test_source_reference_con_cita():
    sr = SourceReference(source_id="s", file_hash="h", filename="f.pdf")
    bbox = BoundingBox(1, 2, 3, 4)
    sr2 = sr.con_cita_documental(3, bbox)
    assert sr2.page == 3 and sr2.bounding_box is bbox
    assert sr.page is None  # frozen → copia, no mutación


# --- Task 2: pdfplumber -----------------------------------------------------
def _pdf_dos_paginas() -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(100, 700, "550 1234.56 total")
    c.showPage()
    c.drawString(120, 650, "pagina dos aqui")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_extraer_paginas_pdfplumber():
    paginas = C.extraer_paginas_pdfplumber(_pdf_dos_paginas())
    assert [p.numero for p in paginas] == [1, 2]
    assert all(p.ancho > 0 and p.alto > 0 for p in paginas)
    assert paginas[0].palabras and "550" in {w.texto for w in paginas[0].palabras}


def _pagina_mano() -> PaginaTexto:
    return PaginaTexto(
        numero=1, ancho=600, alto=800, texto="cas550 1,234.56 ... 1,234.56",
        palabras=[
            PalabraUbicada("cas550", BoundingBox(10, 10, 40, 20)),
            PalabraUbicada("1,234.56", BoundingBox(45, 10, 90, 20)),   # cercana al ancla
            PalabraUbicada("1,234.56", BoundingBox(300, 500, 345, 510)),  # lejana
        ],
    )


def test_localizar_y_desambiguar():
    p = _pagina_mano()
    assert C.localizar_en_pagina(p, "cas550").x0 == 10
    assert C.localizar_en_pagina(p, "NO_EXISTE") is None
    # con dos "1,234.56", el ancla elige la más cercana
    b = C.localizar_en_pagina(p, "1,234.56", cerca_de="cas550")
    assert b.x0 == 45


def test_source_reference_desde_pdfplumber():
    p = _pagina_mano()
    sr = C.source_reference_desde_pdfplumber(
        b"pdfbytes", "F103.pdf", p, column="cas349",
        original_value="1,234.56", normalized_value="1234.56", ancla="cas550",
    )
    assert sr.page == 1 and sr.bounding_box.x0 == 45
    assert sr.column == "cas349" and sr.metodo == "pdfplumber"
    assert sr.normalized_value == "1234.56"


# --- Task 3: Vision (fake, sin red) -----------------------------------------
def _fake_word(texto, vertices, confs):
    return types.SimpleNamespace(
        bounding_box=types.SimpleNamespace(normalized_vertices=[], vertices=vertices),
        symbols=[types.SimpleNamespace(text=t, confidence=c) for t, c in zip(texto, confs)],
    )


def _fake_file_response():
    word = _fake_word("550", [_v(10, 20), _v(40, 20), _v(40, 30), _v(10, 30)], [0.9, 0.8, 0.7])
    para = types.SimpleNamespace(words=[word])
    block = types.SimpleNamespace(paragraphs=[para])
    page = types.SimpleNamespace(width=600, height=800, blocks=[block])
    fta = types.SimpleNamespace(text="550", pages=[page])
    page_resp = types.SimpleNamespace(full_text_annotation=fta)
    return types.SimpleNamespace(responses=[page_resp])


def test_paginas_desde_respuestas():
    paginas = C._paginas_desde_respuestas([_fake_file_response()])
    assert len(paginas) == 1
    pg = paginas[0]
    assert pg.numero == 1 and pg.ancho == 600
    w = pg.palabras[0]
    assert w.texto == "550" and w.bbox.unidad == "px"
    assert abs(w.confianza - (0.9 + 0.8 + 0.7) / 3) < 1e-9


@pytest.fixture
def ocr_falso(monkeypatch):
    """Inyecta un ocr falso para no depender de google.cloud.vision ni de red."""
    fake = types.ModuleType("backend.app.utils.ocr")
    fake.OCRUnavailable = type("OCRUnavailable", (RuntimeError,), {})
    fake._MAX_PAGES_PER_BATCH = 5
    fake._available = True
    fake.is_available = lambda: fake._available
    fake._get_client = lambda: object()
    fake._split_pdf_pages = lambda b, n: [b]
    monkeypatch.setitem(sys.modules, "backend.app.utils.ocr", fake)
    return fake


def test_ocr_pdf_con_geometria(ocr_falso, monkeypatch):
    monkeypatch.setattr(C, "_pedir_anotaciones", lambda client, chunks: [_fake_file_response()])
    paginas = C.ocr_pdf_con_geometria(b"pdf")
    assert len(paginas) == 1 and paginas[0].palabras[0].texto == "550"


def test_ocr_pdf_con_geometria_no_disponible(ocr_falso):
    ocr_falso._available = False
    with pytest.raises(ocr_falso.OCRUnavailable):
        C.ocr_pdf_con_geometria(b"pdf")


def test_source_reference_desde_vision():
    pagina = C._paginas_desde_respuestas([_fake_file_response()])[0]
    sr = C.source_reference_desde_vision(
        "hash", "escaneo.pdf", pagina, "550", column="cas1", normalized_value="550")
    assert sr.metodo == "ocr" and sr.page == 1 and sr.bounding_box is not None
