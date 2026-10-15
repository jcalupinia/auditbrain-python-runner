# -*- coding: utf-8 -*-
"""Cubre la selección de pruebas del refresco masivo (`scripts/refrescar_todas_las_pruebas.py`).

El script aplica la acción `refrescar` (el botón «Actualizar prueba») a TODAS las pruebas
abiertas en una sola pasada. Lo crítico —y lo que se prueba aquí sin correr el motor— es QUÉ
pruebas toca: solo las ejecutadas (con `registro['run']`) y NO aprobadas (NIA 230: una versión
aprobada es inmutable). El recorrido completo con el motor real se verifica en
`tests/test_aud_ciclo_nomina.py` (producirBespoke de punta a punta)."""
import importlib.util
import os
import types

_RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "scripts", "refrescar_todas_las_pruebas.py")
_spec = importlib.util.spec_from_file_location("refrescar_todas_las_pruebas", _RUTA)
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)


def _prueba(pid, estado, run, processor="nomina_beneficios"):
    """Objeto mínimo con los atributos que lee `es_candidata` (duck-typing, sin DB)."""
    return types.SimpleNamespace(
        id=pid, estado=estado,
        definicion={"processor": processor},
        registro={"run": {"bespoke": True}} if run else {},
    )


def test_solo_refresca_ejecutadas_y_no_aprobadas():
    ejecutada = _prueba(1, "RESULTADOS_ANALIZADOS", run=True)
    sin_ejecutar = _prueba(2, "DOCUMENTACION_RECIBIDA", run=False)
    aprobada = _prueba(3, "APROBADO", run=True)
    assert R.es_candidata(ejecutada) is True
    assert R.es_candidata(sin_ejecutar) is False      # no ejecutada → no hay run que actualizar
    assert R.es_candidata(aprobada) is False           # aprobada → inmutable (NIA 230)


def test_filtro_por_processor_y_por_ids():
    a = _prueba(10, "PRUEBA_EJECUTADA", run=True, processor="nomina_beneficios")
    b = _prueba(11, "PRUEBA_EJECUTADA", run=True, processor="cxc_cartera")
    # Filtro por procesador: solo la de nómina.
    assert R.es_candidata(a, processor="nomina_beneficios") is True
    assert R.es_candidata(b, processor="nomina_beneficios") is False
    # Filtro por ids: solo la 10.
    assert R.es_candidata(a, ids={10}) is True
    assert R.es_candidata(b, ids={10}) is False


def test_dry_run_no_modifica_y_cuenta_candidatas(monkeypatch):
    """`refrescar_todas(dry_run=True)` lista las candidatas y NO llama a `aplicar_accion`."""
    pruebas = [
        _prueba(1, "RESULTADOS_ANALIZADOS", run=True),
        _prueba(2, "DOCUMENTACION_RECIBIDA", run=False),   # se omite
        _prueba(3, "APROBADO", run=True),                  # se omite
    ]
    # Stub de _candidatas para no tocar la base real.
    monkeypatch.setattr(R, "_candidatas", lambda db, Prueba, processor, ids:
                        [p for p in pruebas if R.es_candidata(p, processor, ids)])
    # Si alguien intentara refrescar en dry-run, esto lo delataría.
    from backend.app.aud.niif.ciclo import servicio
    llamadas = []
    monkeypatch.setattr(servicio, "aplicar_accion",
                        lambda *a, **k: llamadas.append(a) or (_ for _ in ()).throw(AssertionError("no debe llamarse en dry-run")))
    res = R.refrescar_todas(db=None, dry_run=True, log=lambda *a, **k: None)
    assert res["total"] == 1 and res["ok"] == 0 and res["error"] == 0
    assert llamadas == []
