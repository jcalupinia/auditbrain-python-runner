"""El HTML del artefacto de planificación muestra las secciones CUALITATIVAS reales del
cliente (Perfil del encargo, Matriz de riesgos), no el ejemplo LANSEY hardcodeado.

El motor del artefacto recalcula las pestañas con números desde las balanzas, pero el
Perfil y la Matriz de riesgos venían fijos con el ejemplo LANSEY. Ahora se arman desde las
cédulas que ya calcula el procesador (hoja 14_Perfil, hoja 12_Riesgos_CCI) y se inyectan en
AUDITIA; la plantilla usa los reales si vienen y cae al ejemplo LANSEY solo como respaldo.
"""
import re

from backend.app.aud.niif.procesadores import artefacto_html as A
from backend.app.aud.niif.procesadores import datos_cliente
from backend.app.aud.niif.procesadores import planificacion_nia as P


def _hojas_ejemplo():
    ej = P.EJEMPLO
    run = P.ejecutar(ej["datasets"], ej.get("parametros", {}), ej["corte"])
    return datos_cliente.con_datos(P, run, ej.get("datasets") or {}), ej


def test_construir_cualitativos_desde_cedulas():
    hojas, _ = _hojas_ejemplo()
    cual = A.construir_cualitativos(hojas)
    # Matriz de riesgos: del ejemplo (carta de control interno), no de LANSEY.
    assert cual["risks"], "debe haber riesgos"
    r0 = cual["risks"][0]
    assert set(r0) >= {"id", "proc", "desc", "aser", "p", "i", "c", "inh", "res", "cls", "resp"}
    assert r0["cls"] in ("ALTO", "MEDIO", "BAJO", "PEND")
    assert "planta improductiva" not in r0["desc"]  # no es el riesgo R01 de LANSEY
    # Perfil: identificación real (entidad del ejemplo), no "LANSEY S.A.".
    ident = cual["perfil"]["ident"]
    assert ident and len(ident[0]) == 3
    texto_ident = " ".join(c for fila in ident for c in fila)
    assert "LANSEY" not in texto_ident
    assert set(cual["perfil"]) == {"ident", "obs", "ctx"}
    # Programa de auditoría: del procesador (hoja 19), no de LANSEY (sin RECAMIER).
    assert cual["prog"], "debe haber programa"
    assert len(cual["prog"][0]) == 4 and cual["prog"][0][0].startswith("PT")
    assert "RECAMIER" not in " ".join(c for fila in cual["prog"] for c in fila)


def test_render_inyecta_override_con_datos_reales():
    hojas, ej = _hojas_ejemplo()
    html = A.render({}, {"client": "Comercial Andina de Ejemplo S.A."}, ej.get("parametros", {}),
                    ej.get("datasets"), hojas=hojas).decode()
    # El override reasigna los globales ANTES del render del motor.
    assert "RISKS=A.risks" in html and "PERFIL=A.perfil" in html and "PROG=A.prog" in html
    assert "__AUDITIA_OVERRIDE__" not in html  # placeholder siempre reemplazado
    # AUDITIA lleva los datos reales.
    m = re.search(r"var AUDITIA=(\{.*?\});", html)
    import json
    cfg = json.loads(m.group(1))
    assert "risks" in cfg and "perfil" in cfg
    # El ejemplo LANSEY queda SOLO como respaldo (literal en la plantilla), no en AUDITIA.
    assert "LANSEY" not in json.dumps(cfg.get("risks")) + json.dumps(cfg.get("perfil"))


def test_render_sin_hojas_cae_al_respaldo_lansey():
    html = A.render({}, {"client": "X"}, {}, {}, hojas=None).decode()
    # Sin cédulas no hay override: la plantilla usa el ejemplo LANSEY de respaldo.
    assert "RISKS=A.risks" not in html
    assert "__AUDITIA_OVERRIDE__" not in html  # placeholder reemplazado por cadena vacía
    assert "var RISKS=[" in html  # literal de respaldo intacto
