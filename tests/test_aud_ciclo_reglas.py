"""Reglas del ciclo portadas a Python, contra el sitio.

La primera mitad compara con ``espejo.json``, que genera el JavaScript del
sitio (``frontend/src/aud/niif/espejo/generar.mjs``): caso por caso, Python
tiene que dar el mismo estado o el mismo mensaje. Si alguien cambia la regla en
un solo lado, esto se pone rojo.

La segunda mitad cubre lo que no se puede ejecutar fuera del sitio
(``research.ts`` importa el Worker de Cloudflare; ``engagement-context.ts``
depende de zod y del servidor): se prueban con los mensajes literales del sitio.
"""
import json
from pathlib import Path

import pytest

from backend.app.aud.niif.ciclo import reglas
from backend.app.aud.niif.ciclo.reglas import ReglaIncumplida

ESPEJO = json.loads(
    (Path(__file__).resolve().parents[1] / "backend/app/aud/niif/ciclo/espejo.json").read_text(encoding="utf-8")
)


# --- espejo del sitio --------------------------------------------------------

def test_los_estados_son_los_del_sitio():
    assert list(reglas.ESTADOS) == ESPEJO["estados"]
    assert list(reglas.PUEDEN_APROBAR) == ESPEJO["pueden_aprobar"]


def test_el_catalogo_es_el_del_sitio():
    assert reglas.CATALOGO == ESPEJO["catalogo"]


@pytest.mark.parametrize("caso", ESPEJO["transiciones"], ids=lambda c: f"{c['accion']}@{c['t']['state']}/{c['rol']}")
def test_transicion_igual_que_el_sitio(caso):
    esperado = caso["esperado"]
    if "ok" in esperado:
        assert reglas.transicion(caso["t"], caso["accion"], caso["rol"]) == esperado["ok"]
    else:
        with pytest.raises(ReglaIncumplida) as e:
            reglas.transicion(caso["t"], caso["accion"], caso["rol"])
        assert str(e.value) == esperado["error"]


@pytest.mark.parametrize("caso", ESPEJO["programas"], ids=lambda c: f"{c['definicion'] if isinstance(c['definicion'], str) else 'custom'}/{c['marco']}")
def test_programa_igual_que_el_sitio(caso):
    d = reglas.CATALOGO[caso["definicion"]] if isinstance(caso["definicion"], str) else caso["definicion"]
    assert reglas.crear_programa(d, {"framework": caso["marco"]}) == caso["esperado"]


# --- fuentes (research.ts) ---------------------------------------------------

VERIFICADA = {"verified": True, "document": "NIC 2", "section": "par. 9", "date": "vigente"}


def _fuentes(**cambios):
    niif = {**reglas.fuentes_oficiales(reglas.CATALOGO["vnr"], "NIIF completas", "Ecuador", False)[0], **VERIFICADA, "procedures": ["VNR-01"]}
    nia = {**reglas.fuentes_oficiales(reglas.CATALOGO["vnr"], "NIIF completas", "Ecuador", False)[1], **VERIFICADA, "document": "NIA 540", "procedures": ["VNR-02"]}
    t = {"sources": [niif, nia], "taxApplicable": False, "taxScope": ""}
    t.update(cambios)
    return t


def test_fuentes_oficiales_por_marco_y_tributo():
    completas = reglas.fuentes_oficiales(reglas.CATALOGO["vnr"], "NIIF completas", "Ecuador", True)
    assert [s["category"] for s in completas] == ["NIIF", "NIA", "TRIBUTARIA"]
    assert completas[0]["url"] == reglas.CATALOGO["vnr"]["source"]["url"]
    assert completas[2]["organization"] == "SRI"
    pymes = reglas.fuentes_oficiales(reglas.CATALOGO["vnr"], "NIIF para las PYMES", "Perú", False)
    assert pymes[0]["document"] == "NIIF para las PYMES: edición y sección aplicables"
    assert len(pymes) == 2
    assert not any(s["verified"] for s in completas + pymes)


def test_fuentes_completas_pasan():
    assert reglas.verificar_fuentes(_fuentes()) is True


def test_una_fuente_sin_https_se_rechaza():
    t = _fuentes()
    t["sources"][0]["url"] = "http://www.ifrs.org/"
    with pytest.raises(ReglaIncumplida, match="categoría, enlace HTTPS y procedimientos"):
        reglas.verificar_fuentes(t)


def test_falta_verificar_la_nia():
    t = _fuentes()
    t["sources"][1]["verified"] = False
    with pytest.raises(ReglaIncumplida, match="vigencia de la fuente NIA"):
        reglas.verificar_fuentes(t)


def test_niif_solo_de_ifrs_org():
    t = _fuentes()
    t["sources"][0]["url"] = "https://www.normas-niif.com/nic2"
    with pytest.raises(ReglaIncumplida, match="IFRS Foundation o IAASB/IFAC"):
        reglas.verificar_fuentes(t)


def test_con_tributo_exige_fuente_tributaria_y_alcance():
    with pytest.raises(ReglaIncumplida, match="fuente TRIBUTARIA"):
        reglas.verificar_fuentes(_fuentes(taxApplicable=True))
    t = _fuentes(taxApplicable=True)
    t["sources"].append({**reglas.fuentes_oficiales(reglas.CATALOGO["vnr"], "NIIF completas", "Ecuador", True)[2], **VERIFICADA, "document": "LRTI", "procedures": []})
    with pytest.raises(ReglaIncumplida, match="tratamiento tributario revisado"):
        reglas.verificar_fuentes(t)
    t["taxScope"] = "Deducibilidad del deterioro de inventarios, art. 10 LRTI"
    assert reglas.verificar_fuentes(t) is True


# --- programa (save_program y approve_program de route.ts) -------------------

def test_programa_incompleto_o_duplicado():
    prog = reglas.crear_programa(reglas.CATALOGO["vnr"], {"framework": "NIIF completas"})
    reglas.validar_programa(prog, [])
    with pytest.raises(ReglaIncumplida, match="Complete programa y fuentes"):
        reglas.validar_programa([], [])
    with pytest.raises(ReglaIncumplida, match="Complete cada procedimiento"):
        reglas.validar_programa([{**prog[0], "risk": " "}], [])
    with pytest.raises(ReglaIncumplida, match="duplicados"):
        reglas.validar_programa([prog[0], prog[0]], [])


def test_cada_procedimiento_necesita_una_fuente_verificada():
    prog = reglas.crear_programa(reglas.CATALOGO["vnr"], {"framework": "NIIF completas"})
    t = {**_fuentes(), "program": prog}
    with pytest.raises(ReglaIncumplida, match="procedimiento VNR-03"):
        reglas.vincular_fuentes(t)
    t["sources"][1]["procedures"] = ["VNR-02", "VNR-03"]
    aprobado = reglas.vincular_fuentes(t)
    assert [p["state"] for p in aprobado] == ["APROBADO"] * 3
    assert aprobado[2]["source"]["category"] == "NIA"


# --- ficha del encargo (engagement-context.ts) -------------------------------

FICHA = {
    "client": "Empresa Ejemplo S.A.", "ruc": "1791961048001", "activity": "Comercio", "year": "2025",
    "cutoff": "2025-12-31", "preparer": "Ana Preparadora", "reviewer": "Luis Revisor",
    "firm": "Audit Consulting", "framework": "NIIF completas", "country": "Ecuador",
    "currency": "USD", "visit": "Final", "edition": "2025", "adoption": "", "reuseScope": "one",
}


def test_ficha_valida_se_normaliza():
    f = reglas.validar_ficha_encargo(FICHA)
    assert f["year"] == 2025
    assert f["deferredTax"] is False


@pytest.mark.parametrize("campo,valor", [("framework", "IFRS"), ("currency", "usd"), ("visit", "Intermedia"), ("cutoff", "2025-02-30"), ("preparer", "A")])
def test_ficha_invalida_usa_el_mensaje_del_sitio(campo, valor):
    with pytest.raises(ReglaIncumplida) as e:
        reglas.validar_ficha_encargo({**FICHA, campo: valor})
    assert str(e.value) == "Complete cliente, responsables, firma, marco, país, moneda, visita, edición y fecha válidos."


def test_corte_fuera_del_ejercicio():
    with pytest.raises(ReglaIncumplida, match="corresponder al ejercicio"):
        reglas.validar_ficha_encargo({**FICHA, "cutoff": "2024-12-31"})


def test_ruc_ecuatoriano_de_13_digitos():
    with pytest.raises(ReglaIncumplida, match="RUC de 13 dígitos"):
        reglas.validar_ficha_encargo({**FICHA, "ruc": "179196104"})
    assert reglas.validar_ficha_encargo({**FICHA, "country": "Perú", "ruc": "20100070970"})["ruc"] == "20100070970"


def test_la_ficha_completa_exige_moneda_visita_y_edicion():
    with pytest.raises(ReglaIncumplida):
        reglas.validar_ficha_encargo({**FICHA, "edition": ""})
    assert reglas.validar_ficha_encargo({**FICHA, "edition": ""}, completa=False)["edition"] == ""
