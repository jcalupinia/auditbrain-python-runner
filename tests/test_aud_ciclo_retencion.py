"""Retención de pruebas (lugar de paso) y control de duplicados en la creación.

Decisión del dueño (2026-10-04):
- El Command Center no guarda las pruebas: se borran solas tras la descarga (gracia)
  y, en todo caso, a las 8 h de creadas.
- No se permite crear una prueba nueva si ya hay una ABIERTA de la misma herramienta
  en el mismo ejercicio: hay que modificar la existente.

Ajuste 2026-10-05: el trabajo EN CURSO (prueba ABIERTA, estado ≠ APROBADO, sin
descargar) NO se autopurga aunque pase de las 8 h.

Ajuste 2026-10-06 ("previsualizar ≠ archivar"): el trabajo EN CURSO tampoco se
autopurga por previsualizar/descargar su papel (el auditor lo previsualiza decenas
de veces mientras lo arma). El borrado por descarga y el tope duro de 8 h aplican
SOLO a pruebas TERMINADAS (APROBADO). Un borrador abierto solo se limpia tras una
inactividad larga (AUD_CICLO_ABIERTA_INACTIVA_HORAS), medida desde la última
actividad. Corrige la pérdida de planificaciones a medio armar al previsualizarlas.
"""
import datetime

from sqlalchemy import update

from backend.app.aud.niif.ciclo import retencion, servicio
from backend.app.aud.niif.ciclo.models import Prueba
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal

from tests.test_aud_ciclo_http import BASE, FICHA, _prueba_vnr, _staff_con_proyecto
from tests.test_aud_niif_fichas import _h


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _mk_prueba(db, project_id, *, estado="PRUEBA_SELECCIONADA", creada_en=None,
               actualizada_en=None, descargada_en=None):
    reg = {"engagement": {"client": "X", "cutoff": "2025-12-31"}}
    if descargada_en is not None:
        reg["descargada_en"] = descargada_en.isoformat()
    p = Prueba(project_id=project_id, version=1, estado=estado, origen="vnr",
               definicion={"id": "vnr", "name": "VNR"}, registro=reg, revision=1)
    db.add(p)
    db.flush()
    # Se fijan con un UPDATE core (no por atributo) para que el ``onupdate`` de
    # ``actualizada_en`` no pise el valor de prueba al hacer commit.
    vals = {}
    if creada_en is not None:
        vals["creada_en"] = creada_en
    # Por defecto, la última actividad = la creación (una prueba recién creada y sin tocar).
    vals["actualizada_en"] = actualizada_en if actualizada_en is not None else (creada_en or _ahora())
    db.execute(update(Prueba).where(Prueba.id == p.id).values(**vals))
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


def test_en_curso_descargada_NO_se_purga_previsualizar_no_es_archivar(client):
    """Previsualizar ≠ archivar (2026-10-06): una prueba EN CURSO que se descargó/
    previsualizó NO se borra, aunque pase la gracia. El auditor previsualiza el
    borrador decenas de veces mientras lo arma; antes eso lo autodestruía a los 30 min."""
    _tok, pid = _staff_con_proyecto(client)
    gracia = settings.AUD_CICLO_POST_DOWNLOAD_TTL_MINUTES
    db = SessionLocal()
    try:
        # Previsualizada hace más que la gracia, pero sigue activa (actividad reciente).
        en_curso_previsualizada = _mk_prueba(
            db, pid, creada_en=_ahora() - datetime.timedelta(hours=2),
            actualizada_en=_ahora() - datetime.timedelta(minutes=gracia + 5),
            descargada_en=_ahora() - datetime.timedelta(minutes=gracia + 5))
    finally:
        db.close()

    retencion.purgar_once()

    db = SessionLocal()
    try:
        assert db.get(Prueba, en_curso_previsualizada) is not None   # trabajo activo protegido
    finally:
        db.close()


def test_abierta_se_purga_tras_inactividad_larga(client):
    """Backstop: un borrador ABIERTO que nadie toca por más de
    AUD_CICLO_ABIERTA_INACTIVA_HORAS sí se limpia (no acumular drafts abandonados)."""
    _tok, pid = _staff_con_proyecto(client)
    horas = settings.AUD_CICLO_ABIERTA_INACTIVA_HORAS
    db = SessionLocal()
    try:
        abandonada = _mk_prueba(db, pid, creada_en=_ahora() - datetime.timedelta(hours=horas + 100),
                                actualizada_en=_ahora() - datetime.timedelta(hours=horas + 1))
        activa = _mk_prueba(db, pid, creada_en=_ahora() - datetime.timedelta(hours=horas + 100),
                            actualizada_en=_ahora() - datetime.timedelta(minutes=5))
    finally:
        db.close()

    retencion.purgar_once()

    db = SessionLocal()
    try:
        assert db.get(Prueba, abandonada) is None        # inactiva de sobra → se limpia
        assert db.get(Prueba, activa) is not None         # actividad reciente → protegida
    finally:
        db.close()


def test_purga_tras_la_descarga_pasada_la_gracia(client):
    """La gracia post-descarga aplica SOLO a pruebas TERMINADAS (APROBADO)."""
    _tok, pid = _staff_con_proyecto(client)
    gracia = settings.AUD_CICLO_POST_DOWNLOAD_TTL_MINUTES
    db = SessionLocal()
    try:
        # Aprobada, creada hace poco (no vence por las 8 h) pero descargada hace más que la gracia.
        descargada_vieja = _mk_prueba(db, pid, estado="APROBADO",
                                      creada_en=_ahora() - datetime.timedelta(minutes=gracia + 20),
                                      descargada_en=_ahora() - datetime.timedelta(minutes=gracia + 5))
        # Aprobada descargada recién: dentro de la gracia, NO se borra (puede bajar otros formatos).
        descargada_reciente = _mk_prueba(db, pid, estado="APROBADO",
                                         creada_en=_ahora() - datetime.timedelta(minutes=gracia + 20),
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
