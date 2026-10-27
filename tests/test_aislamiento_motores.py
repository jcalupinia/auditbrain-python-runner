"""Aislamiento entre los motores de las pruebas NIIF (encargo de aislamiento).

Cada motor del catálogo (procesador con ``RUBRO``) debe ser AUTOSUFICIENTE: su
tarjeta (``RUBRO``), su anexo principal (``PRINCIPAL``) y su ficha
(``definicion()``) son SUYOS, no los de otra herramienta. Criterio de éxito del
encargo: si un motor se rompe o cambia, ningún otro debe cambiar su rubro, su
principal ni su ficha.

El nombre del módulo ``aislado.py`` ya está tomado por el aislamiento de MEMORIA
(subproceso); este archivo cubre el aislamiento de ACOPLAMIENTO entre motores.
"""
import pytest

from backend.app.aud.niif import procesadores
from backend.app.aud.niif.ciclo import servicio


def _motores_catalogo() -> dict:
    """Motores VISIBLES del catálogo: tienen ``RUBRO`` y no están ocultos."""
    ocultos = getattr(servicio, "OCULTAR_PROCESADOR", set())
    return {pid: mod for pid, mod in procesadores.PROCESADORES.items()
            if getattr(mod, "RUBRO", None) and pid not in ocultos}


def test_hay_motores_que_revisar():
    # Guardia: si el registro queda vacío, los demás tests pasarían en falso.
    assert len(_motores_catalogo()) >= 18


def test_cada_rubro_tiene_un_solo_motor():
    """Un rubro = un motor por tarjeta: ningún ``RUBRO`` lo comparten dos motores
    (la colisión histórica era ``cxc_cartera`` y ``pce_cohortes_niif9`` en «CXC»)."""
    por_rubro: dict[str, list[str]] = {}
    for pid, mod in _motores_catalogo().items():
        por_rubro.setdefault(mod.RUBRO, []).append(pid)
    repetidos = {r: pids for r, pids in por_rubro.items() if len(pids) > 1}
    assert not repetidos, f"RUBRO compartido por varios motores: {repetidos}"


def test_cada_motor_declara_su_propio_principal_en_su_ficha():
    """El ``PRINCIPAL`` del motor es un anexo (``dataset``) de SU propia
    ``definicion()``. Así el mensaje de «falta el anexo» del frontend nombra el
    requerimiento de ESTA herramienta, no un texto fijo de otra."""
    for pid, mod in _motores_catalogo().items():
        if getattr(mod, "BESPOKE", False):
            continue  # nómina 2.0 lee archivos crudos: sin datasets ni principal
        principal = getattr(mod, "PRINCIPAL", None)
        assert principal, f"{pid}: no declara PRINCIPAL"
        d = mod.definicion()
        datasets = {r.get("dataset") for r in (d.get("requests") or []) if r.get("dataset")}
        assert principal in datasets, (
            f"{pid}: su PRINCIPAL '{principal}' no está entre sus propios anexos {sorted(datasets)}")


def test_ninguna_ficha_lleva_el_rubro_de_otro_motor():
    """La identidad (name/area/summary) de un motor no contiene el ``RUBRO`` de
    OTRO motor: la ficha no arrastra texto ajeno."""
    rubros = {mod.RUBRO for mod in _motores_catalogo().values()}
    for pid, mod in _motores_catalogo().items():
        d = mod.definicion()
        texto = " ".join(str(d.get(k, "")) for k in ("name", "area", "summary"))
        for ajeno in rubros - {mod.RUBRO}:
            assert ajeno not in texto, f"{pid}: su ficha menciona el rubro ajeno '{ajeno}'"


def test_mutacion_un_motor_roto_no_contamina_a_los_demas(monkeypatch):
    """Prueba de MUTACIÓN: se daña un motor a propósito (RUBRO colisionado +
    ``definicion()`` que explota) y se verifica que TODOS los demás conservan su
    rubro, su principal y su ficha utilizable. Si esto falla, un motor roto
    arrastra a los otros (lo que el encargo prohíbe)."""
    motores = _motores_catalogo()
    victima = "efectivo_equivalentes"
    assert victima in motores
    sanos_antes = {pid: (mod.RUBRO, getattr(mod, "PRINCIPAL", None))
                   for pid, mod in motores.items() if pid != victima}

    mod_victima = procesadores.PROCESADORES[victima]

    def _explota(*a, **k):
        raise RuntimeError("motor dañado a propósito (prueba de mutación)")

    monkeypatch.setattr(mod_victima, "RUBRO", "CXC", raising=False)   # colisión forzada
    monkeypatch.setattr(mod_victima, "definicion", _explota, raising=False)

    for pid, (rubro, principal) in sanos_antes.items():
        mod = procesadores.PROCESADORES[pid]
        assert mod.RUBRO == rubro, f"{pid}: su RUBRO cambió al romper {victima}"
        assert getattr(mod, "PRINCIPAL", None) == principal, f"{pid}: su PRINCIPAL cambió al romper {victima}"
        mod.definicion()  # su ficha se sigue construyendo sin tocar al motor roto
