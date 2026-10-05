"""Retención de pruebas (lugar de paso) y control de duplicados en la creación.

Decisión del dueño (2026-10-04):
- El Command Center no guarda las pruebas: se borran solas tras la descarga (gracia)
  y, en todo caso, a las 8 h de creadas (aprobadas incluidas).
- No se permite crear una prueba nueva si ya hay una ABIERTA de la misma herramienta
  en el mismo ejercicio: hay que modificar la existente.

Ajuste 2026-10-05: el trabajo EN CURSO (prueba ABIERTA, estado ≠ APROBADO, sin
descargar) NO se autopurga aunque pase de las 8 h; el tope duro solo alcanza a las
aprobadas o ya descargadas. Evita perder una planificación a medio armar.
"""
import datetime

from backend.app.aud.niif.ciclo import retencion, servicio
from backend.app.aud.niif.ciclo.models import Prueba
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal

from tests.test_aud_ciclo_http import BASE, FICHA, _prueba_vnr, _staff_con_proyecto
from tests.test_aud_niif_fichas import _h


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _mk_prueba(db, project_id, *, estado="PRUEBA_SELECCIONADA", creada_en=None, descargada_en=None):
    reg = {"engagement": {"client": "X", "cutoff": "2025-12-31"}}
    if descargada_en is not None:
        reg["descargada_en"] = descargada_en.isoformat()
    p = Prueba(project_id=project_id, version=1, estado=estado, origen="vnr",
               definicion={"id": "vnr", "name": "VNR"}, registro=reg, revision=1)
    db.add(p)
    db.flush()
    if creada_en is not None:
        p.creada_en = creada_en
    db.commit()
    return p.id


def test_purga_a_las_8h_aprobadas_pero_no_el_trabajo_en_curso(client):
    _tok, pid = _staff_con_proyecto(client)
    db = SessionLocal()
    try:
        # En curso (no aprobada) y sin descargar: NO se borra aunque pase de 8 h
        # (protege la planificación a medio armar). Cambio 2026-10-05.
        vieja_en_curso = _mk_prueba(db, pid, creada_en=_ahora() - datetime.timedelta(hours=9))
        # Aprobada y vieja: sí se borra (papel terminado, lugar de paso).
        vieja_aprob = _mk_prueba(db, pid, estado="APROBADO", creada_en=_ahora() - datetime.timedelta(hours=9))
        reciente = _mk_prueba(db, pid, creada_en=_ahora() - datetime.timedelta(hours=1))
    finally:
        db.close()

    res = retencion.purgar_once()
    assert res["purgadas"] >= 1

    db = SessionLocal()
    try:
        assert db.get(Prueba, vieja_en_curso) is not None   # trabajo en curso protegido
        assert db.get(Prueba, vieja_aprob) is None           # aprobada sí se borra
        assert db.get(Prueba, reciente) is not None          # la reciente sigue
    finally:
        db.close()


def test_en_curso_descargada_si_se_purga_pasada_la_gracia(client):
    """Si una prueba en curso SÍ se descargó, ya se archivó: se purga tras la gracia
    (la protección es solo para el trabajo en curso que nunca se bajó)."""
    _tok, pid = _staff_con_proyecto(client)
    gracia = settings.AUD_CICLO_POST_DOWNLOAD_TTL_MINUTES
    db = SessionLocal()
    try:
        en_curso_descargada = _mk_prueba(
            db, pid, creada_en=_ahora() - datetime.timedelta(hours=1),
            descargada_en=_ahora() - datetime.timedelta(minutes=gracia + 5))
    finally:
        db.close()

    retencion.purgar_once()

    db = SessionLocal()
    try:
        assert db.get(Prueba, en_curso_descargada) is None
    finally:
        db.close()


def test_purga_tras_la_descarga_pasada_la_gracia(client):
    _tok, pid = _staff_con_proyecto(client)
    gracia = settings.AUD_CICLO_POST_DOWNLOAD_TTL_MINUTES
    db = SessionLocal()
    try:
        # Creada hace poco (no vence por las 8 h) pero descargada hace más que la gracia.
        descargada_vieja = _mk_prueba(db, pid, creada_en=_ahora() - datetime.timedelta(minutes=gracia + 20),
                                      descargada_en=_ahora() - datetime.timedelta(minutes=gracia + 5))
        # Descargada recién: dentro de la gracia, NO se borra (puede bajar otros formatos).
        descargada_reciente = _mk_prueba(db, pid, creada_en=_ahora() - datetime.timedelta(minutes=gracia + 20),
                                         descargada_en=_ahora())
    finally:
        db.close()

    retencion.purgar_once()

    db = SessionLocal()
    try:
        assert db.get(Prueba, descargada_vieja) is None
        assert db.get(Prueba, descargada_reciente) is not None
    finally:
        db.close()


def test_marcar_descargada_registra_el_sello(client):
    _tok, pid = _staff_con_proyecto(client)
    db = SessionLocal()
    try:
        pidp = _mk_prueba(db, pid)
        p = db.get(Prueba, pidp)
        assert "descargada_en" not in (p.registro or {})
        servicio.marcar_descargada(db, p)
        p = db.get(Prueba, pidp)
        assert (p.registro or {}).get("descargada_en")
    finally:
        db.close()


def test_no_se_crea_una_prueba_abierta_duplicada(client):
    tok, pid = _staff_con_proyecto(client)
    _prueba_vnr(client, tok, pid)  # primera VNR (abierta) → 201
    # Segunda VNR en el mismo ejercicio: bloqueada con el código para «Modificar».
    r = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": "vnr"})
    assert r.status_code == 409, r.text
    det = r.json()["detail"]
    assert det["code"] == "PRUEBA_ABIERTA_EXISTE"
    assert det["pruebaId"]
    # Otra herramienta (PCE) sí se permite: no es la misma prueba.
    assert client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": "pce"}).status_code == 201


def test_aprobada_no_bloquea_una_version_nueva(client):
    tok, pid = _staff_con_proyecto(client)
    db = SessionLocal()
    try:
        _mk_prueba(db, pid, estado="APROBADO")   # aprobada: no es «abierta»
    finally:
        db.close()
    # Con solo una APROBADA de VNR, crear otra VNR debe permitirse (nueva versión).
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA).status_code == 200
    r = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": "vnr"})
    assert r.status_code == 201, r.text
