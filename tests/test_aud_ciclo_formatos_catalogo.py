"""Las herramientas del catálogo refrescan los FORMATOS aceptados desde la definición
viva del procesador, aun en pruebas ya creadas.

Los requerimientos se congelan en la prueba al generarla. Cuando el dueño amplía los
formatos aceptados de una herramienta (p. ej. Efectivo/Caja-Bancos ahora admite PDF y
JPG además de Excel), ese cambio del catálogo debe verse también en pruebas viejas —de
lo contrario el selector de archivos y la validación de subida seguirían filtrando solo
xlsx/csv. `servicio._formatos_catalogo_vivos` + `_con_formatos_vivos` re-derivan el
`formats` de la definición viva y lo superponen al leer la prueba y al validar la subida,
sin tocar el resto del requerimiento.
"""
from types import SimpleNamespace

from backend.app.aud.niif.ciclo import servicio
from backend.app.aud.niif.procesadores import efectivo_equivalentes as efectivo


def _formatos_vivos_rq(rq_id: str) -> list:
    reqs = efectivo.definicion()["requests"]
    return next(r["formats"] for r in reqs if r["id"] == rq_id)


def test_definicion_viva_de_efectivo_admite_pdf_y_jpg():
    # Base del arreglo: el catálogo ya acepta PDF/JPG en los requerimientos de datos.
    for rq in ("RQ-001", "RQ-002", "RQ-009", "RQ-010"):
        fmts = set(_formatos_vivos_rq(rq))
        assert {"pdf", "jpg"} <= fmts, (rq, fmts)


def test_con_formatos_vivos_solo_toca_formats_y_por_id():
    requests = [
        {"id": "RQ-002", "document": "Partidas", "dataset": "partidas", "formats": ["xlsx", "csv"]},
        {"id": "RX-99", "document": "Otro", "formats": ["xlsx"]},  # no está en el catálogo vivo
    ]
    vivos = {"RQ-002": ["xlsx", "csv", "pdf", "jpg", "jpeg"]}
    out = servicio._con_formatos_vivos(requests, vivos)
    assert out[0]["formats"] == ["xlsx", "csv", "pdf", "jpg", "jpeg"]
    assert out[0]["document"] == "Partidas" and out[0]["dataset"] == "partidas"  # lo demás intacto
    assert out[1]["formats"] == ["xlsx"]  # sin match por id: conserva el suyo


def test_prueba_del_catalogo_refresca_formatos_al_leer():
    # Prueba «vieja»: sus requerimientos quedaron congelados solo con xlsx/csv.
    viejos = [{"id": "RQ-002", "document": "Partidas conciliatorias", "dataset": "partidas",
               "formats": ["xlsx", "csv"], "status": "PENDIENTE"}]
    p = SimpleNamespace(
        origen="proc:efectivo_equivalentes",
        estado="REQUERIMIENTO_APROBADO",
        registro={"requests": [dict(r) for r in viejos]},
        definicion={"processor": "efectivo_equivalentes", "requests": [dict(r) for r in viejos]},
    )
    salida = servicio._t(p)
    fmts = next(r["formats"] for r in salida["requests"] if r["id"] == "RQ-002")
    assert "pdf" in fmts and "jpg" in fmts, fmts
    # También en la definición que viaja al frontend.
    fmts_def = next(r["formats"] for r in salida["definition"]["requests"] if r["id"] == "RQ-002")
    assert "pdf" in fmts_def and "jpg" in fmts_def


def test_prueba_que_no_es_del_catalogo_no_se_toca():
    viejos = [{"id": "RQ-001", "document": "X", "formats": ["xlsx"]}]
    p = SimpleNamespace(
        origen="ficha:123",  # no es proc: → no se refresca
        estado="REQUERIMIENTO_APROBADO",
        registro={"requests": [dict(r) for r in viejos]},
        definicion={"requests": [dict(r) for r in viejos]},
    )
    salida = servicio._t(p)
    assert salida["requests"][0]["formats"] == ["xlsx"]
