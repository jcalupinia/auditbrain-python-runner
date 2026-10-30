"""Corte-driven: las herramientas de nómina calculan al período auditado de la ficha.

Decisión del dueño (2026-10-30): «en este momento estamos en auditorías preliminares; todas las
herramientas deben calcular al corte que se establece en la tarjeta del cliente (fecha + preliminar/
final)». El período auditado va de enero al mes de corte; el pasivo se revisa por el movimiento del
año del mayor y el gasto por el período. Diciembre (cierre calendario) conserva el comportamiento
histórico (verificado aparte con PROPHAR, cero diferencias).

Sin datos reales de cliente.
"""
import tempfile

from backend.app.aud.niif.procesadores import nomina_beneficios as m
from backend.app.aud.niif.procesadores.nomina.rutas import Rutas


def _rutas(corte, ejercicio=0, visit=""):
    return Rutas(home="", out="", anexo="", rol="", consolidado="",
                 ejercicio=ejercicio, corte=corte, visit=visit)


def test_corte_diciembre_es_cierre_calendario():
    r = _rutas("2025-12-31", ejercicio=2025, visit="final")
    assert r.mes_corte == 12
    assert r.anio_corte == 2025
    assert r.es_preliminar is False


def test_corte_julio_es_visita_preliminar():
    r = _rutas("2026-07-31", ejercicio=2026, visit="preliminar")
    assert r.mes_corte == 7                 # período auditado = enero … julio
    assert r.anio_corte == 2026
    assert r.es_preliminar is True


def test_anio_del_corte_si_falta_el_ejercicio():
    # Sin ejercicio en la ficha, el año sale del corte.
    r = _rutas("2026-07-31")
    assert r.anio_corte == 2026
    assert r.mes_corte == 7


def test_corte_invalido_cae_a_diciembre():
    # Una fecha ausente o malformada no debe reventar: cae al cierre calendario.
    assert _rutas("").mes_corte == 12
    assert _rutas("2026-13-31").mes_corte == 12   # mes fuera de rango
    assert _rutas("").anio_corte == 2025


def test_resolver_captura_la_visita_de_la_ficha():
    archivos = [
        {"requerimiento": "RQ-002", "nombre": "Anexo.xlsx", "ruta": "/data/anexo.xlsx"},
        {"requerimiento": "RQ-003", "nombre": "Consolidado.xlsx", "ruta": "/data/consol.xlsx"},
        {"requerimiento": "RQ-004", "nombre": "LM_GASTO_NOMINA.xlsx", "ruta": "/data/g.xlsx"},
        {"requerimiento": "RQ-004", "nombre": "LM_PASIVO_IESS_POR_PAGAR.xlsx", "ruta": "/data/i.xlsx"},
        {"requerimiento": "RQ-004", "nombre": "LM_PASIVO_BENEFICIOS_SOCIALES.xlsx", "ruta": "/data/b.xlsx"},
        {"requerimiento": "RQ-006", "nombre": "Rol.xlsx", "ruta": "/data/rol.xlsx"},
    ]
    ficha = {"client": "Comercial Andina de Ejemplo S.A.", "ruc": "1790000000001",
             "year": 2026, "cutoff": "2026-07-31", "preparer": "JV", "reviewer": "Socio",
             "framework": "NIIF para las PYMES", "visit": "preliminar"}
    home = tempfile.mkdtemp(); out = tempfile.mkdtemp()
    r = m.resolver(archivos, ficha, home, out)
    assert r.visit == "preliminar"
    assert r.corte == "2026-07-31" and r.ejercicio == 2026
    assert r.mes_corte == 7 and r.es_preliminar is True
