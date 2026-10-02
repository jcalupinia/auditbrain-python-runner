"""Las herramientas del catálogo refrescan su POLÍTICA (formatos aceptados y la bandera
obligatorio/opcional) desde la definición viva del procesador, aun en pruebas ya creadas.

Los requerimientos se congelan en la prueba al generarla. Cuando el dueño cambia el
catálogo —amplía los formatos aceptados (p. ej. Efectivo/Caja-Bancos ahora admite PDF y
JPG además de Excel) o vuelve OPCIONAL un anexo que antes era obligatorio (p. ej.
Inventarios: solo el inventario valorado RQ-001 queda obligatorio)— ese cambio debe verse
también en pruebas viejas. De lo contrario el selector/validación seguiría filtrando solo
xlsx/csv y el gate de cobertura seguiría exigiendo documentos que ya son opcionales.
`servicio._politica_catalogo_viva` + `_con_politica_viva` (y el atajo `requests_vivos`)
re-derivan `formats` y `required` de la definición viva y los superponen al leer la prueba
y al validar, sin tocar el resto del requerimiento.
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


def test_con_politica_viva_toca_formats_y_required_por_id():
    requests = [
        {"id": "RQ-002", "document": "Partidas", "dataset": "partidas", "formats": ["xlsx", "csv"], "required": True},
        {"id": "RX-99", "document": "Otro", "formats": ["xlsx"], "required": True},  # no está en el catálogo vivo
    ]
    politica = {"RQ-002": {"formats": ["xlsx", "csv", "pdf", "jpg", "jpeg"], "required": False}}
    out = servicio._con_politica_viva(requests, politica)
    assert out[0]["formats"] == ["xlsx", "csv", "pdf", "jpg", "jpeg"]
    assert out[0]["required"] is False  # el catálogo lo volvió opcional
    assert out[0]["document"] == "Partidas" and out[0]["dataset"] == "partidas"  # lo demás intacto
    assert out[1]["formats"] == ["xlsx"] and out[1]["required"] is True  # sin match por id: conserva el suyo


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


def test_inventarios_refresca_required_en_prueba_vieja():
    # Regresión: una prueba de inventarios ya creada congeló RQ-003 (movimiento) como
    # obligatorio. El catálogo vivo lo volvió opcional; debe heredarse sin re-generar.
    viejos = [
        {"id": "RQ-001", "document": "Inventario valorado", "dataset": "inventario",
         "formats": ["xlsx", "csv"], "required": True, "status": "PENDIENTE"},
        {"id": "RQ-003", "document": "Movimiento del inventario por línea vendida", "dataset": "movimiento",
         "formats": ["xlsx", "csv"], "required": True, "status": "PENDIENTE"},
    ]
    p = SimpleNamespace(
        origen="proc:inventarios_costos",
        estado="REQUERIMIENTO_APROBADO",
        registro={"requests": [dict(r) for r in viejos]},
        definicion={"processor": "inventarios_costos", "requests": [dict(r) for r in viejos]},
    )
    vivos = {r["id"]: r for r in servicio.requests_vivos(p)}
    assert vivos["RQ-001"]["required"] is True   # el inventario valorado sigue obligatorio
    assert vivos["RQ-003"]["required"] is False  # el movimiento pasó a opcional
    # Y lo mismo por la vista completa (_t), que alimenta el banner y la definición del frontend.
    salida = servicio._t(p)
    req3 = next(r for r in salida["requests"] if r["id"] == "RQ-003")
    assert req3["required"] is False and req3["document"] == "Movimiento del inventario por línea vendida"


def test_prueba_que_no_es_del_catalogo_no_se_toca():
    viejos = [{"id": "RQ-001", "document": "X", "formats": ["xlsx"], "required": True}]
    p = SimpleNamespace(
        origen="ficha:123",  # no es proc: → no se refresca
        estado="REQUERIMIENTO_APROBADO",
        registro={"requests": [dict(r) for r in viejos]},
        definicion={"requests": [dict(r) for r in viejos]},
    )
    salida = servicio._t(p)
    assert salida["requests"][0]["formats"] == ["xlsx"]
    assert salida["requests"][0]["required"] is True
