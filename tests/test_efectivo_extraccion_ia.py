"""Extracción por IA en Efectivo y equivalentes: el frontend ofrece «Extraer con IA»
en cada requerimiento con dataset que acepta PDF, así que el backend DEBE aceptarlos.

Bug reportado por el dueño (2026-10-06): los botones «Extraer con IA» devolvían
«Este documento no admite extracción por IA» para TODOS los documentos de Efectivo
(conciliaciones, estados de cuenta, anexo), porque el procesador no declaraba
``EXTRACCION_DATASETS`` → el backend (``servicio.py``) rechazaba la acción
``extraer_ia`` para cualquier dataset, aunque el frontend sí mostraba el botón.
"""
import json

from backend.app.aud.niif.ciclo import extraccion_ia as ex
from backend.app.aud.niif.procesadores import efectivo_equivalentes as m


def test_extraccion_datasets_cubre_los_6_datasets_con_campos():
    assert m.EXTRACCION_DATASETS == ("cuentas", "partidas", "libro_mayor",
                                     "estado_cuenta", "conciliacion_anterior", "arqueo")
    for ds in m.EXTRACCION_DATASETS:
        assert ds in m.DATASETS, ds
        assert m.kind(ds) in m.CAMPOS, ds


def test_frontend_y_backend_alineados():
    """Cada requerimiento con dataset que acepta PDF (lo que el frontend usa para
    ofrecer «Extraer con IA», `admiteExtraccionIA`) debe ser extraíble en el backend."""
    ofrecidos = [r["dataset"] for r in m.definicion()["requests"]
                 if r.get("dataset") and "pdf" in (r.get("formats") or [])]
    assert ofrecidos, "se esperaba al menos un requerimiento con dataset que acepta PDF"
    faltan = [d for d in ofrecidos if d not in m.EXTRACCION_DATASETS]
    assert not faltan, f"el frontend ofrece extraer datasets que el backend rechaza: {faltan}"


def _chat_con(filas):
    class _Resp:
        def __init__(self, content):
            self.content = content
            self.model = "modelo-falso"
            self.tokens_in = self.tokens_out = None
    return lambda messages, system=None: _Resp(json.dumps({"filas": filas}))


def test_partidas_de_conciliacion_se_extraen_por_ia_y_validan():
    """Una partida conciliatoria transcrita por IA (chat falso, sin red) pasa la
    validación real del procesador — el esquema sale de los CAMPOS de partidas."""
    filas = [
        {"id": "P-01", "cuenta": "1.1.02.01", "tipo": "Cheque pendiente", "referencia": "Cheque 1203",
         "fecha_origen": "2025-12-28", "importe": 1500.0, "fecha_liquidacion": "2026-01-05"},
    ]
    out = ex.extraer_filas(m.CAMPOS[m.kind("partidas")], "texto del PDF de la conciliación BCO PICHINCHA",
                           enums=m.EXTRACCION_ENUMS.get("partidas"),
                           instrucciones=m.EXTRACCION_INSTRUCCIONES.get("partidas"), chat=_chat_con(filas))
    assert out["n"] == 1
    v = m.validar_filas("partidas", out["rows"])
    assert v["ok"], v["errors"]


def test_estado_de_cuenta_se_extrae_por_ia_y_valida():
    """Un movimiento del estado de cuenta bancario transcrito por IA pasa la validación."""
    filas = [
        {"cuenta": "1.1.02.01", "fecha": "2025-12-15", "documento": "Transferencia 0098",
         "debito": 0.0, "credito": 3200.0},
    ]
    out = ex.extraer_filas(m.CAMPOS[m.kind("estado_cuenta")], "texto del PDF EC BG AGOSTO",
                           instrucciones=m.EXTRACCION_INSTRUCCIONES.get("estado_cuenta"), chat=_chat_con(filas))
    assert out["n"] == 1
    v = m.validar_filas("estado_cuenta", out["rows"])
    assert v["ok"], v["errors"]


# --------------------------------------------------------------------------- #
#  Extremo a extremo por HTTP: reproduce el escenario del dueño                 #
#  (subir el PDF del estado de cuenta → «Extraer con IA» → confirmar →          #
#   procesar → la tabla extraída alimenta el dataset). Antes del fix, la        #
#   acción extraer_ia respondía «Este documento no admite extracción por IA».   #
# --------------------------------------------------------------------------- #
import io  # noqa: E402

from openpyxl import load_workbook  # noqa: E402

from backend.app.aud.niif.ciclo import extraccion_ia  # noqa: E402
from tests.test_aud_ciclo_evidencia import _leer, _subir  # noqa: E402
from tests.test_aud_ciclo_http import BASE, FICHA, _accion, _staff_con_proyecto  # noqa: E402
from tests.test_aud_niif_fichas import _h  # noqa: E402

ESTADO_CUENTA_IA = [
    {"cuenta": "1.1.02.01", "fecha": "2025-12-10", "documento": "MARCA_IA_EC: depósito 889",
     "debito": 0.0, "credito": 4100.0},
    {"cuenta": "1.1.02.01", "fecha": "2025-12-22", "documento": "Comisión mantenimiento",
     "debito": 12.5, "credito": 0.0},
]


def _modelo_cuentas(client, tok, p):
    r = client.get(f"{BASE}/pruebas/{p['id']}/modelo/RQ-001", headers=_h(tok))
    assert r.status_code == 200, r.text
    wb = load_workbook(io.BytesIO(r.content))
    keys = [c["key"] for c in m.CAMPOS["cuentas"]]
    for f in m.EJEMPLO["datasets"]["cuentas"]:
        wb["Datos"].append([f.get(k, "") for k in keys])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def test_estado_de_cuenta_pdf_se_extrae_confirma_y_alimenta_el_dataset(client, monkeypatch):
    # La IA no se llama de verdad: texto fijo + chat falso (reemplaza la cadena de proveedores).
    monkeypatch.setattr(extraccion_ia, "texto_de_documento", lambda nombre, datos: "Texto del estado de cuenta.")
    monkeypatch.setattr(extraccion_ia, "_chat_por_defecto", lambda: _chat_con(ESTADO_CUENTA_IA))

    tok, pid = _staff_con_proyecto(client)
    ficha = {**FICHA, "visit": "Preliminar"}  # preliminar: solo RQ-001 es obligatorio
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=ficha).status_code == 200
    p = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok),
                    json={"origen": "proc:efectivo_equivalentes"}).json()
    p = _accion(client, tok, p, "research").json()
    p = _accion(client, tok, p, "generate_program").json()
    prog = p["registro"]["program"]
    fuentes = p["registro"]["sources"]
    for s in fuentes:
        s.update(verified=True, section="párr. aplicable", date="vigente", procedures=[x["code"] for x in prog])
    p = _accion(client, tok, p, "approve_program", {"program": prog, "sources": fuentes}).json()
    p = _accion(client, tok, p, "generate_request").json()
    p = _accion(client, tok, p, "approve_request", {"requests": p["registro"]["requests"]}).json()
    assert p["estado"] == "REQUERIMIENTO_APROBADO", p

    # El anexo de cuentas (RQ-001) por el camino tabular; el estado de cuenta (RQ-010) como PDF.
    p = _leer(client, tok, p)
    assert _subir(client, tok, p, "RQ-001", "Anexo.xlsx", _modelo_cuentas(client, tok, p)).status_code == 201
    p = _leer(client, tok, p)
    assert _subir(client, tok, p, "RQ-010", "EC BG AGOSTO.pdf", b"%PDF-1.4 estado de cuenta").status_code == 201

    p = _leer(client, tok, p)
    arch = {a["requerimiento"]: a["id"] for a in p["archivos"]}
    ec_id = arch["RQ-010"]

    # 1) «Extraer con IA» sobre el PDF: antes devolvía «no admite extracción por IA».
    r = _accion(client, tok, p, "extraer_ia", {"fileId": ec_id})
    assert r.status_code == 200, r.text
    p = r.json()
    extr = p["registro"]["extraccion"][str(ec_id)]
    assert extr["dataset"] == "estado_cuenta" and len(extr["rows"]) == 2
    assert extr["validation"]["ok"], extr["validation"]

    # 2) El auditor revisa y confirma.
    p = _accion(client, tok, p, "guardar_extraccion", {"fileId": ec_id, "rows": extr["rows"]}).json()

    # 3) Al procesar, las filas extraídas alimentan el dataset estado_cuenta.
    mapa = {c["key"]: i for i, c in enumerate(m.CAMPOS["cuentas"])}
    p = _accion(client, tok, p, "map_validate", {"datasets": {
        "cuentas": [{"fileId": arch["RQ-001"], "sheet": "Datos", "header": 1, "mapping": mapa}]}}).json()
    ec = p["registro"]["datasets"]["estado_cuenta"]
    assert len(ec) == 2 and "MARCA_IA_EC" in json.dumps(ec, ensure_ascii=False)
