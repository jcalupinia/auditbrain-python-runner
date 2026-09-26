"""Registros del encargo con un clic (decisión del dueño, 2026-09-26): independencia, asistencia a la discusión,
aceptación del socio, carta de encargo firmada y comunicación al gobierno. La planificación los recibe en
``parametros["_encargo"]`` y los muestra en la hoja 00_Registros."""
import datetime

from backend.app.aud.niif.ciclo import servicio
from backend.app.aud.niif.procesadores import planificacion_encargo as enc
from backend.app.aud.niif.procesadores import planificacion_nia as m
from backend.app.context import service as ctx
from backend.app.context.models import Project
from backend.app.db.session import SessionLocal
from tests.test_aud_ciclo_http import BASE, FICHA, _staff_con_proyecto
from tests.test_aud_niif_fichas import _h


def _reg(client, tok, pid, **datos):
    return client.post(f"{BASE}/proyectos/{pid}/registros", headers=_h(tok), json=datos)


def test_registros_reglas_y_anulacion(client):
    tok, pid = _staff_con_proyecto(client)
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA).status_code == 200
    assert _reg(client, tok, pid, tipo="otro").status_code == 400
    assert "rol" in _reg(client, tok, pid, tipo="independencia", rol="Jefe").json()["detail"]
    # La aceptación la hace el socio, después de confirmar su independencia como socio.
    r = _reg(client, tok, pid, tipo="aceptacion")
    assert r.status_code == 400 and "socio" in r.json()["detail"]
    r = _reg(client, tok, pid, tipo="independencia", rol="Socio", nombre="CPA Socia", amenazas="", anio_desde="2020")
    assert r.status_code == 201, r.text
    assert _reg(client, tok, pid, tipo="aceptacion").status_code == 201
    manana = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    assert "posterior a hoy" in _reg(client, tok, pid, tipo="carta", fecha=manana).json()["detail"]
    assert _reg(client, tok, pid, tipo="carta", fecha="2025-09-05", limitaciones="Sin acceso a sucursal").status_code == 201
    assert "medio" in _reg(client, tok, pid, tipo="comunicacion").json()["detail"]
    assert _reg(client, tok, pid, tipo="comunicacion", medio="Reunión con el directorio").status_code == 201
    assert _reg(client, tok, pid, tipo="asistencia", rol="Socio", nombre="CPA Socia", fecha="2025-10-10").status_code == 201
    # Un segundo clic reemplaza al anterior (queda anulado, no se borra).
    r = _reg(client, tok, pid, tipo="independencia", rol="Socio", nombre="CPA Socia", amenazas="Préstamo del cliente",
             salvaguardas="Préstamo cancelado")
    assert r.status_code == 201
    datos = client.get(f"{BASE}/proyectos/{pid}/registros", headers=_h(tok)).json()
    e = datos["encargo"]
    assert e["firma"] == "Audit Consulting"
    assert len(e["registros"]["equipo"]) == 1 and e["registros"]["equipo"][0]["amenazas"] == "Préstamo del cliente"
    assert e["registros"]["equipo"][0]["anios"] == 1                    # el reemplazo ya no trae el año declarado
    assert e["registros"]["carta"] == {"actor": "CPA Socia", "fecha": "2025-09-05", "detalle": "Sin acceso a sucursal"}
    assert e["registros"]["aceptacion"]["actor"] == "CPA Socia"
    rid = next(x["id"] for x in datos["registros"] if x["tipo"] == "comunicacion")
    assert client.delete(f"{BASE}/proyectos/{pid}/registros/{rid}", headers=_h(tok)).json() == {"ok": True}
    assert "comunicacion" not in client.get(f"{BASE}/proyectos/{pid}/registros", headers=_h(tok)).json()["encargo"]["registros"]
    assert client.delete(f"{BASE}/proyectos/{pid}/registros/{rid}", headers=_h(tok)).status_code == 400
    # Otra persona no anula lo que registró otro.
    db = SessionLocal()
    try:
        from backend.app.aud.niif.ciclo.models import RegistroEncargo
        otro = db.query(RegistroEncargo).filter(RegistroEncargo.project_id == pid, RegistroEncargo.anulado_en.is_(None)).first()
        assert otro is not None
        try:
            servicio.anular_registro(db, pid, otro.id, "otra@firma.ec", False)
            assert False, "debió negarse"
        except servicio.ReglaIncumplida as ex:
            assert "Solo quien hizo el registro" in str(ex)
    finally:
        db.close()


def test_anios_con_el_cliente_cuentan_los_encargos_anteriores(client):
    tok, pid = _staff_con_proyecto(client)
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA).status_code == 200
    assert _reg(client, tok, pid, tipo="independencia", rol="Gerente", nombre="CPA Gerente").status_code == 201
    db = SessionLocal()
    try:
        pr = db.get(Project, pid)
        nuevo = ctx.create_project(db, client_id=pr.client_id, name="Auditoría 2026", module_code="AUD",
                                   organization_id=pr.organization_id)
        pid2 = nuevo.id
    finally:
        db.close()
    assert client.put(f"{BASE}/proyectos/{pid2}/ficha", headers=_h(tok), json={**FICHA, "year": 2026, "cutoff": "2026-12-31"}).status_code == 200
    assert _reg(client, tok, pid2, tipo="independencia", rol="Gerente", nombre="CPA Gerente").status_code == 201
    eq = client.get(f"{BASE}/proyectos/{pid2}/registros", headers=_h(tok)).json()["encargo"]["registros"]["equipo"]
    assert eq[0]["anios"] == 2
    # El año declarado manda si da más años.
    assert _reg(client, tok, pid2, tipo="independencia", rol="Gerente", nombre="CPA Gerente", anio_desde="2019").status_code == 201
    eq = client.get(f"{BASE}/proyectos/{pid2}/registros", headers=_h(tok)).json()["encargo"]["registros"]["equipo"]
    assert eq[0]["anios"] == 8


def test_la_planificacion_usa_los_registros_de_la_plataforma(client):
    tok, pid = _staff_con_proyecto(client)
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA).status_code == 200
    _reg(client, tok, pid, tipo="independencia", rol="Socio", nombre="CPA Socia")
    _reg(client, tok, pid, tipo="aceptacion")
    _reg(client, tok, pid, tipo="asistencia", rol="Socio", nombre="CPA Socia", fecha="2025-10-10")
    assert m.USA_REGISTROS_ENCARGO is True
    db = SessionLocal()
    try:
        encargo = servicio.registros_encargo(db, pid)
    finally:
        db.close()
    e = m.EJEMPLO
    r = m.ejecutar(e["datasets"], {**{k: v for k, v in e["parametros"].items() if k not in ("socio", "gerente")}, "_encargo": encargo},
                   e["corte"])
    hojas = {h["name"]: h for h in m.hojas(r)}
    filas = hojas[enc.REG]["rows"]
    assert [f[0] for f in filas][:2] == [enc.TIPO_INDEP, enc.TIPO_ASIST]
    assert r["detalle"]["parametros"]["socio"] == "CPA Socia"
    ev = {x["codigo"]: x["estado"] for x in r["detalle"]["evals"]}
    assert ev["ACE-01"] == "Conforme" and ev["CON-02"] == "Pendiente" and ev["COM-01"] == "Pendiente"


def test_documentos_generados_por_la_plataforma(client):
    import io

    from docx import Document

    from backend.app.aud.niif.ciclo import documentos_encargo as docs

    tok, pid = _staff_con_proyecto(client)
    url = f"{BASE}/proyectos/{pid}/documentos"
    assert "ficha" in client.get(f"{url}/carta_encargo", headers=_h(tok)).json()["detail"]
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA).status_code == 200
    assert client.get(f"{url}/otro", headers=_h(tok)).status_code == 400
    _reg(client, tok, pid, tipo="independencia", rol="Socio", nombre="CPA Socia")
    _reg(client, tok, pid, tipo="carta", limitaciones="Sin acceso a la sucursal de Guayaquil")
    r = client.get(f"{url}/carta_encargo", headers=_h(tok))
    assert r.status_code == 200 and r.content.startswith(b"PK")
    texto = "\n".join(p.text for p in Document(io.BytesIO(r.content)).paragraphs)
    assert "Empresa Ejemplo S.A." in texto and "NIIF completas" in texto and "Sin acceso a la sucursal" in texto
    assert "AuditConsulting Auditores Cía. Ltda." in "\n".join(c.text for t in Document(io.BytesIO(r.content)).tables
                                                               for c in t._cells)
    # Sin planificación ejecutada, el acta y la carta de planificación marcan lo que falta (no inventan).
    for tipo in ("acta_discusion", "carta_planificacion"):
        r = client.get(f"{url}/{tipo}", headers=_h(tok))
        assert r.status_code == 200 and "[PENDIENTE]" in "\n".join(p.text for p in Document(io.BytesIO(r.content)).paragraphs)
    # Con la planificación del ejemplo: riesgos presentes, indicios de fraude y asuntos de la hoja 32.
    e = m.EJEMPLO
    run = {"hojas": m.hojas(m.ejecutar(e["datasets"], e["parametros"], e["corte"]))}
    encargo = e["parametros"]["_encargo"]
    acta = Document(io.BytesIO(docs.acta_discusion(FICHA, encargo, run)))
    celdas = [c.text for t in acta.tables for c in t._cells]
    assert "Ana Torres (ficticio)" in celdas and "RB-01" in celdas and "FRA-03" in celdas and "RB-03" not in celdas
    carta = Document(io.BytesIO(docs.carta_planificacion(FICHA, encargo, run)))
    celdas = [c.text for t in carta.tables for c in t._cells]
    assert "Responsabilidades del auditor" in celdas and "Riesgo significativo · RB-01" in celdas
    assert not any(c.startswith("Envío de la carta") for c in celdas)
