# -*- coding: utf-8 -*-
"""Semáforo de proceso pesado + caché del motor de nómina (anti-OOM con uso concurrente)."""
import types

import pytest

from backend.app.aud.niif.procesadores import concurrencia
from backend.app.aud.niif.ciclo import nomina_cache, servicio


class FakeArch:
    def __init__(self, req, comp, nombre, sha, tam, clase="source", estado="ok"):
        self.requerimiento, self.componente, self.nombre = req, comp, nombre
        self.sha256, self.tamano, self.clase, self.estado = sha, tam, clase, estado


def _p(pid):
    return types.SimpleNamespace(id=pid, registro={"engagement": {"client": "X S.A.", "ruc": "1", "year": 2025},
                                                   "run": {"ok": True}})


def test_firma_cambia_con_los_insumos_y_es_estable():
    eng = {"client": "X S.A."}
    a1 = [FakeArch("RQ-002", "anexo", "a.xlsx", "sha-1", 10)]
    a2 = [FakeArch("RQ-002", "anexo", "a.xlsx", "sha-2", 10)]  # mismo archivo, contenido distinto
    assert nomina_cache.firma(a1, eng) != nomina_cache.firma(a2, eng)
    assert nomina_cache.firma(a1, eng) == nomina_cache.firma(list(a1), eng)  # estable
    # un archivo rechazado o de soporte no cuenta para la firma
    a3 = a1 + [FakeArch("RQ-099", "x", "b.xlsx", "sha-9", 5, estado="rechazado")]
    assert nomina_cache.firma(a1, eng) == nomina_cache.firma(a3, eng)


def test_semaforo_rechaza_cuando_no_hay_cupo():
    # Con el único cupo tomado, pedir otro sin espera lanza ProcesoOcupado (→ 429 en el router).
    with concurrencia.limite_proceso_pesado():
        with pytest.raises(concurrencia.ProcesoOcupado):
            with concurrencia.limite_proceso_pesado(timeout=0.01):
                pass
    # Liberado el cupo, se vuelve a conceder.
    with concurrencia.limite_proceso_pesado(timeout=0.01):
        pass


def test_cedulas_nomina_reusa_la_cache(monkeypatch):
    pid = 987654
    nomina_cache.invalidar(pid)
    llamadas = {"n": 0}

    def fake_correr(db, p, con_extras=False):
        llamadas["n"] += 1
        ced = {"DO-2_x.xlsx": b"PK-fake"}
        return (ced, {"prog": {}}) if con_extras else ced

    monkeypatch.setattr(servicio, "archivos", lambda db, pid_: [FakeArch("RQ-002", "anexo", "a.xlsx", "sha", 10)])
    monkeypatch.setattr(servicio, "correr_nomina", fake_correr)
    p = _p(pid)
    c1 = servicio.cedulas_nomina(None, p)
    c2 = servicio.cedulas_nomina(None, p)
    assert c1 == c2 == {"DO-2_x.xlsx": b"PK-fake"}
    assert llamadas["n"] == 1, "la segunda llamada debe salir de la caché (no re-correr el motor)"
    # Cambiar el insumo invalida la caché por firma: vuelve a correr.
    monkeypatch.setattr(servicio, "archivos", lambda db, pid_: [FakeArch("RQ-002", "anexo", "a.xlsx", "sha-NUEVO", 10)])
    servicio.cedulas_nomina(None, p)
    assert llamadas["n"] == 2
    nomina_cache.invalidar(pid)


def test_invalidar_olvida_lo_cacheado():
    pid = 987655
    nomina_cache.guardar_cedulas(pid, "f1", {"a.xlsx": b"x"}, {"e": 1})
    assert nomina_cache.obtener(pid, "f1")["cedulas"] == {"a.xlsx": b"x"}
    nomina_cache.invalidar(pid)
    assert nomina_cache.obtener(pid, "f1") is None
    # Firma distinta nunca devuelve lo viejo.
    nomina_cache.guardar_cedulas(pid, "f1", {"a.xlsx": b"x"})
    assert nomina_cache.obtener(pid, "f2") is None
    nomina_cache.invalidar(pid)
