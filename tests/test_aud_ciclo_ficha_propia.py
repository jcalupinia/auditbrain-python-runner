"""Una ficha con programa, requerimientos y cálculos condicionales propios.

Es el formato del encargo NIIF (``docs/niif/ENCARGO_CHATGPT_PRUEBAS_NIIF.md``):
la ficha trae su programa y sus requerimientos, y el ciclo los usa en vez de los
genéricos. La definición es la misma que el espejo compara contra el sitio.
"""
import copy
import json
from pathlib import Path

import pytest

from tests.test_aud_ciclo_evidencia import XLSX_VNR, _leer, _subir
from tests.test_aud_ciclo_http import BASE, FICHA, _accion, _staff_con_proyecto
from tests.test_aud_niif_fichas import _crear, _h

ESPEJO = json.loads(
    (Path(__file__).resolve().parents[1] / "backend/app/aud/niif/ciclo/espejo_datos.json").read_text(encoding="utf-8")
)
ANTIGUEDAD = next(c["d"] for c in ESPEJO["definiciones"] if c["nombre"] == "antigüedad con plan")
FILAS = [
    {"id": "A", "due_date": "2025-12-15", "exposure": "1000", "recorded_allowance": "0"},
    {"id": "B", "due_date": "2025-10-01", "exposure": "500", "recorded_allowance": "40"},
]


@pytest.fixture(autouse=True)
def disco_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_CICLO_DIR", str(tmp_path / "aud_pruebas"))
    monkeypatch.setenv("AUD_CICLO_MIN_LIBRE_MB", "0")


def test_el_motor_del_portal_calcula_dias_tramos_y_condiciones(client):
    tok, _ = _staff_con_proyecto(client)
    r = client.post("/api/v1/aud/niif/motor/ejecutar", headers=_h(tok),
                    json={"definicion": ANTIGUEDAD, "filas": FILAS, "parametros": {"cutoff": "2025-12-31"}})
    assert r.status_code == 200, r.text
    filas = r.json()["rows"]
    # A: 16 días → 1 %, no vencida → ajuste 0. B: 91 días → 20 % → 100, vencida → ajuste 100.
    assert [(x["dias"], x["tasa"], x["pce"], x["vencida"], x["ajuste"]) for x in filas] == [
        ("16.00", "0.010000", "10.00", "0.00", "0.00"),
        ("91.00", "0.200000", "100.00", "1.00", "100.00"),
    ]
    sin_corte = client.post("/api/v1/aud/niif/motor/ejecutar", headers=_h(tok),
                            json={"definicion": ANTIGUEDAD, "filas": FILAS})
    assert sin_corte.status_code == 400 and "fecha de corte" in sin_corte.json()["detail"]


def test_ficha_con_programa_y_requerimientos_propios_de_punta_a_punta(client):
    tok, pid = _staff_con_proyecto(client)
    ficha = _crear(client, tok)
    client.post(f"/api/v1/aud/niif/fichas/{ficha['id']}/estado", headers=_h(tok), json={"estado": "probada"})

    # Guardar exige correrla, y los días hasta «corte» necesitan la fecha.
    url = f"{BASE}/fichas/{ficha['id']}/definicion"
    r = client.put(url, headers=_h(tok), json={"definicion": ANTIGUEDAD, "filas": FILAS})
    assert r.status_code == 400 and "fecha de corte" in r.json()["detail"]
    mala = copy.deepcopy(ANTIGUEDAD)
    mala["requests"][1]["procedure"] = "OTRO"
    r = client.put(url, headers=_h(tok), json={"definicion": mala, "filas": FILAS, "parametros": {"cutoff": "2025-12-31"}})
    assert r.status_code == 400 and "RQ-002: vincule un procedimiento" in r.json()["detail"]
    r = client.put(url, headers=_h(tok), json={"definicion": ANTIGUEDAD, "filas": FILAS, "parametros": {"cutoff": "2025-12-31"}})
    assert r.status_code == 200, r.text

    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA).status_code == 200
    p = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": f"ficha:{ficha['id']}"}).json()
    p = _accion(client, tok, p, "research").json()
    p = _accion(client, tok, p, "generate_program").json()

    # El programa es el de la ficha, con la norma de cada procedimiento.
    prog = p["registro"]["program"]
    assert [x["code"] for x in prog] == ["CXC01-01", "CXC01-02"]
    assert prog[1]["reference"] == "NIIF 9 párr. 5.5.15"
    assert prog[1]["procedure"] == "Recalcular."

    fuentes = p["registro"]["sources"]
    fuentes[0].update(verified=True, section="par. 5.5.15", date="vigente", procedures=["CXC01-02"])
    fuentes[1].update(verified=True, document="NIA 500", section="par. A49", date="vigente", procedures=["CXC01-01"])
    p = _accion(client, tok, p, "approve_program", {"program": prog, "sources": fuentes}).json()
    assert p["estado"] == "PROGRAMA_APROBADO", p
    p = _accion(client, tok, p, "generate_request").json()

    # Los requerimientos son los de la ficha: formatos, componentes, uso y reporte.
    reqs = p["registro"]["requests"]
    assert [x["id"] for x in reqs] == ["RQ-001", "RQ-002"]
    assert reqs[0]["format"] == "XLSX / CSV" and reqs[0]["components"] == ["Quito", "Guayaquil"]
    assert reqs[0]["use"] == "calculo" and reqs[0]["report"] == "Cartera por vencimiento"
    assert reqs[1]["required"] is False
    p = _accion(client, tok, p, "approve_request", {"requests": reqs}).json()
    assert p["estado"] == "REQUERIMIENTO_APROBADO", p

    # La subida respeta los formatos de la ficha y exige el componente.
    r = _subir(client, tok, p, "RQ-001", "cartera.pdf", b"%PDF", "Quito")
    assert r.status_code == 400 and "XLSX, CSV" in r.json()["detail"]
    assert _subir(client, tok, p, "RQ-001", "cartera_quito.xlsx", XLSX_VNR, "Quito").status_code == 201
    p = _leer(client, tok, p)
    assert any("faltan Guayaquil" in h for h in p["huecos"])
    # RQ-002 es opcional: no deja hueco.
    assert not any("RQ-002" in h for h in p["huecos"])
