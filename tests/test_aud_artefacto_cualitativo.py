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


def test_corrida_real_sin_carta_no_muestra_lansey():
    """En una corrida real de un cliente, si falta el requerimiento de una sección (p. ej. la
    carta de control interno para los riesgos), esa sección queda VACÍA (del cliente), NUNCA
    con el ejemplo LANSEY. `siempre=True` fuerza el override aunque la sección esté vacía."""
    hojas = [
        {"name": "14_Perfil", "rows": [
            ["Identificación del encargo", None, None, None, None, None, None],
            [{"v": "Identificación"}, "Entidad auditada", {"v": "EMPRESA B S.A."}, None, {"v": "Informe B"}, "", ""],
        ]},
        {"name": "12_Riesgos_CCI", "rows": []},   # no se cargó la carta → sin riesgos
        {"name": "19_Programa", "rows": []},
    ]
    cual = A.construir_cualitativos(hojas, siempre=True)
    assert cual["risks"] == [] and cual["prog"] == []         # vacíos, no LANSEY
    assert cual["perfil"]["ident"], "el perfil sí tiene lo cargado"
    html = A.render({}, {"client": "EMPRESA B S.A."}, {}, {}, hojas=hojas).decode()
    # El override reasigna igual (presencia de clave), dejando las secciones vacías del cliente.
    assert "RISKS=A.risks;" in html and "PROG=A.prog;" in html
    import json
    cfg = json.loads(re.search(r"var AUDITIA=(\{.*?\});", html).group(1))
    assert cfg["risks"] == [] and "EMPRESA B" in json.dumps(cfg["perfil"])


def test_dos_companias_dan_datos_distintos():
    """La misma herramienta, dos compañías con requerimientos distintos → perfiles y riesgos
    distintos (se actualiza según la empresa y lo cargado en el requerimiento)."""
    hojas_b = [
        {"name": "14_Perfil", "rows": [
            [{"v": "Identificación"}, "Entidad auditada", {"v": "EMPRESA B S.A."}, None, {"v": "Informe B"}, "", ""]]},
        {"name": "12_Riesgos_CCI", "rows": [
            ["R01", {"v": "Tesorería"}, {"v": "Riesgo propio de EMPRESA B"}, {"v": "Existencia"},
             {"v": 5}, {"v": 4}, {"v": 3}, {"v": 20}, {"v": 12.0}, {"v": "Medio"}, {"v": "Procedimiento B"}]]},
    ]
    a = A.construir_cualitativos(_hojas_ejemplo()[0], siempre=True)
    b = A.construir_cualitativos(hojas_b, siempre=True)
    assert a["perfil"]["ident"][0][1] != b["perfil"]["ident"][0][1]
    assert a["risks"][0]["desc"] != b["risks"][0]["desc"]
    assert "EMPRESA B" in b["perfil"]["ident"][0][1]


def test_render_sin_hojas_cae_al_respaldo_lansey():
    html = A.render({}, {"client": "X"}, {}, {}, hojas=None).decode()
    # Sin cédulas no hay override: la plantilla usa el ejemplo LANSEY de respaldo.
    assert "RISKS=A.risks" not in html
    assert "__AUDITIA_OVERRIDE__" not in html  # placeholder reemplazado por cadena vacía
    assert "var RISKS=[" in html  # literal de respaldo intacto
