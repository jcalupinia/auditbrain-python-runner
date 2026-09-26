"""Base legal tributaria sugerida por herramienta y gate de «Confirmar base técnica».

- La sugerencia está presente en las 18 herramientas de catálogo + pérdidas
  incurridas + PCE, y viaja en la definición (``tributario_sugerido``).
- El gate rechaza taxScope vacío o con «VERIFICAR» sin resolver.
- Ninguna cita marcada VERIFICAR se presenta como vigente (lleva el prefijo).
"""
import pytest

from backend.app.aud.niif import base_legal
from backend.app.aud.niif.ciclo import reglas, servicio
from backend.app.aud.niif.ciclo.reglas import ReglaIncumplida
from backend.app.aud.niif.procesadores import PROCESADORES


def test_sugerencia_presente_en_catalogo_y_en_ficha_pi_pce():
    catalogo = [pid for pid, m in PROCESADORES.items() if getattr(m, "RUBRO", None)]
    assert len(catalogo) == 19   # 18 herramientas NIIF + la planificación de la auditoría
    for pid in catalogo + ["perdidas_incurridas_s11", "pce_simplificada_niif9"]:
        s = base_legal.sugerencia(pid)
        assert s and s["texto"] and s["citas"], pid
        for c in s["citas"]:
            assert c["norma"] and c["ref"] and c["dice"] and c["efecto"]


def test_definicion_procesador_incluye_tributario_sugerido():
    d = servicio._definicion_procesador({**PROCESADORES["perdidas_incurridas_s11"].definicion(), "id": "custom"})
    assert d["tributario_sugerido"]["texto"].startswith("Base legal sugerida")
    # Pérdidas incurridas cita el Art. 10 núm. 11 (incobrables) confirmado, sin VERIFICAR.
    assert "Art. 10 núm. 11" in d["tributario_sugerido"]["texto"]
    assert d["tributario_sugerido"]["tiene_verificar"] is False


def test_citas_verificar_llevan_el_prefijo_y_no_se_presentan_como_vigentes():
    # Una herramienta con cita por confirmar debe marcarla explícitamente.
    s = base_legal.sugerencia("inventarios_costos")
    assert s["tiene_verificar"] is True
    assert "VERIFICAR — " in s["texto"]


def test_el_tratamiento_tributario_aparece_en_el_papel_exportado():
    from backend.app.aud.niif.procesadores import libro

    d = PROCESADORES["perdidas_incurridas_s11"].definicion()
    reg = {"engagement": {"client": "C", "ruc": "1", "framework": "NIIF para las PYMES"}, "run": {},
           "taxApplicable": True, "taxScope": "LRTI Art. 10 núm. 11: incobrables 1 % anual, tope 10 %.",
           "taxScopeMeta": {"resumen": "aceptó la base legal sugerida tal cual", "actor": "user@x", "fecha": "2026-09-23T10:00:00"}}
    antes, _ = libro._contexto(d, reg, [], 1, "MUESTRA")
    caratula = next(h for h in antes if h["name"] == "00_Caratula")
    conceptos = {r[0]: r[1] for r in caratula["rows"]}
    assert "Art. 10 núm. 11" in conceptos["Tratamiento tributario revisado"]
    assert "aceptó la base legal sugerida" in conceptos["Sustento tributario · revisión"]


def test_gate_rechaza_vacio_y_verificar():
    # ``validar_tratamiento_tributario`` es el gate que corre approve_program.
    with pytest.raises(ReglaIncumplida, match="Describa el tratamiento"):
        reglas.validar_tratamiento_tributario({"taxApplicable": True, "taxScope": ""})
    with pytest.raises(ReglaIncumplida, match="VERIFICAR"):
        reglas.validar_tratamiento_tributario({"taxApplicable": True, "taxScope": "VERIFICAR — confirmar el artículo"})
    # Texto resuelto: no bloquea. Sin tratamiento aplicable: tampoco.
    assert reglas.validar_tratamiento_tributario({"taxApplicable": True, "taxScope": "LRTI Art. 10 núm. 11: 1 % anual, tope 10 %."})
    assert reglas.validar_tratamiento_tributario({"taxApplicable": False, "taxScope": ""})
