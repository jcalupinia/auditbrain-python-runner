"""Nómina 2.0 (bespoke): definición, resolución de archivos de la prueba y mínimos.

La herramienta 2.0 no usa el camino genérico (CAMPOS/ejecutar/libro.html): su cara
es el panel propio y su motor son los generadores de ``procesadores/nomina/``. La
paridad al centavo del motor y las 15 cédulas se verifican con los generadores y
LibreOffice (fuera de esta suite); aquí se prueba el envoltorio con datos ficticios.
"""
import tempfile

from backend.app.aud.niif.procesadores import nomina_beneficios as m
from backend.app.aud.niif.procesadores.nomina.rutas import Rutas


def test_definicion_2_0():
    d = m.definicion()
    assert d["processor"] == "nomina_beneficios"
    assert d["area"] == "Nómina" and m.RUBRO == "NOMINA"
    assert d.get("bespoke") is True              # cara propia (panel), no libro.html
    assert d["name"] and d["summary"] and d["legal"]
    ids = [r["id"] for r in d["requests"]]
    assert ids == [f"RQ-00{i}" for i in range(1, 9)]
    # RQ-002/003/004/006 son obligatorios; RQ-001/005/007/008 opcionales.
    # RQ-005 (comprobantes) es opcional a propósito: el motor corre sin ellos (datos_minimos
    # no los exige) y DO-9/DO-10 quedan pendientes hasta cargarlos. Si fuera obligatorio
    # bloquearía «Procesar» pese a que la herramienta entrega 13/15 cédulas sin comprobantes.
    req = {r["id"]: r for r in d["requests"]}
    assert all(req[x]["required"] for x in ("RQ-002", "RQ-003", "RQ-004", "RQ-006"))
    assert all(not req[x]["required"] for x in ("RQ-001", "RQ-005", "RQ-007", "RQ-008"))
    assert "RQ-005" not in {"RQ-002", "RQ-003", "RQ-004", "RQ-006"}  # no está entre los mínimos del motor
    assert len(d["program"]) >= 10               # DO-1..DO-12
    assert len(m.CEDULAS) == 15


def test_estado_y_actuarial_fuera_del_catalogo():
    # La parte actuarial (PAY-13..) sale del catálogo en la 2.0.
    d = m.definicion()
    texto = " ".join(p["objective"] for p in d["program"]).lower()
    assert "actuarial" not in texto and "jubila" not in texto
    assert not hasattr(m, "ejecutar")            # ya no es procesador genérico


def test_resolver_mapea_los_requerimientos():
    archivos = [
        {"requerimiento": "RQ-002", "nombre": "Anexo.xlsx", "ruta": "/data/anexo.xlsx"},
        {"requerimiento": "RQ-003", "componente": "Sierra", "nombre": "Consolidado.xlsx", "ruta": "/data/consol.xlsx"},
        {"requerimiento": "RQ-003", "componente": "Exclusiones", "nombre": "Exclusiones.xlsx", "ruta": "/data/exc.xlsx"},
        {"requerimiento": "RQ-004", "nombre": "LM_GASTO_NOMINA.xlsx", "ruta": "/data/g.xlsx"},
        {"requerimiento": "RQ-004", "nombre": "LM_PASIVO_IESS_POR_PAGAR.xlsx", "ruta": "/data/i.xlsx"},
        {"requerimiento": "RQ-004", "nombre": "LM_PASIVO_BENEFICIOS_SOCIALES.xlsx", "ruta": "/data/b.xlsx"},
        {"requerimiento": "RQ-006", "nombre": "Rol.xlsx", "ruta": "/data/rol.xlsx"},
    ]
    ficha = {"client": "Comercial Andina de Ejemplo S.A.", "ruc": "1790000000001",
             "year": 2026, "cutoff": "2026-12-31", "preparer": "JV", "reviewer": "Socio",
             "framework": "NIIF para las PYMES"}
    home = tempfile.mkdtemp(); out = tempfile.mkdtemp()
    r = m.resolver(archivos, ficha, home, out)
    assert isinstance(r, Rutas)
    assert r.anexo == "/data/anexo.xlsx" and r.rol == "/data/rol.xlsx"
    assert r.consolidado == "/data/consol.xlsx" and r.exclusiones == "/data/exc.xlsx"
    assert r.lm_gasto == "/data/g.xlsx" and r.lm_iess == "/data/i.xlsx" and r.lm_bs == "/data/b.xlsx"
    assert r.cliente == "Comercial Andina de Ejemplo S.A." and r.ejercicio == 2026
    assert r.corte == "2026-12-31" and r.marco == "NIIF para las PYMES"
    assert r.logo  # logo de la firma del encargo


def test_logo_por_firma_del_encargo():
    # Decisión del dueño: mantener ambas firmas; la cédula usa el logo de la firma de la ficha.
    from backend.app.aud.niif.procesadores import marca
    assert m._logo_firma({"firm": "Partner Auditing"}).endswith("logo_partner_auditing.png")
    assert m._logo_firma({"firm": "AuditConsulting"}).endswith("logo_auditconsulting_oscuro.png")
    assert m._logo_firma({}).endswith("logo_auditconsulting_oscuro.png")
    # El asset de la segunda firma existe y es una imagen válida.
    assert (marca.ASSETS / marca.ARCHIVOS["partner_auditing"]).exists()


def test_datos_minimos():
    base = [{"requerimiento": q, "ruta": f"/x/{q}.xlsx"} for q in ("RQ-002", "RQ-003", "RQ-004", "RQ-006")]
    assert m.datos_minimos(base) is True
    assert m.datos_minimos(base[:-1]) is False   # falta el rol
    assert m.datos_minimos([]) is False


def test_do31_decimo_suma_mensualizado_a_la_provision():
    """DO-3.1, tabla «PROVISIONES REGISTRADAS»: el décimo tercero/cuarto SUMA el mensualizado
    pagado en el rol a la provisión (decisión del socio 2026-11-01), para que concilie con el
    gasto del mayor (provisión acumulada + lo ya pagado mensualizado; conjuntos disjuntos, sin
    doble conteo). La fórmula de cada mes debe referenciar la provisión (BL/BM) y el mensualizado
    (AD «D13 MENS» / AE «D14 MENS SIE»). DO-4 no se altera (lee el detalle por trabajador)."""
    import io
    import os
    import tempfile

    import openpyxl

    EJ = "frontend/public/ejemplos/nomina_beneficios"
    if not os.path.exists(f"{EJ}/RQ-006_rol_de_pagos_normal_y_pasantes.xlsx"):
        import pytest
        pytest.skip("faltan los ejemplos del repo")
    A = [("RQ-002", "RQ-002_anexo_de_nomina_saldos_por_cuenta.xlsx"),
         ("RQ-003", "RQ-003_consolidado_iess_por_region.xlsx"),
         ("RQ-004", "RQ-004_mayor_de_gasto_de_nomina.xlsx"),
         ("RQ-004", "RQ-004_mayor_de_iess_por_pagar.xlsx"),
         ("RQ-004", "RQ-004_mayor_de_beneficios_sociales_por_pagar.xlsx"),
         ("RQ-006", "RQ-006_rol_de_pagos_normal_y_pasantes.xlsx")]
    arch = [{"requerimiento": r, "ruta": f"{EJ}/{n}", "nombre": n} for r, n in A]
    d = tempfile.mkdtemp()
    ced = m.correr_prueba(arch, {"client": "Demo", "year": 2024, "cutoff": "2024-12-31"},
                          os.path.join(d, "h"), os.path.join(d, "o"))
    wb = openpyxl.load_workbook(io.BytesIO(ced["DO-3.1_Resumen_Roles_de_Pago.xlsx"]))
    ws = wb["DO3.1 Resumen Roles"]
    c31 = str(ws["C31"].value)   # Décimo tercero, Enero (fila 30 + mes 1)
    d31 = str(ws["D31"].value)   # Décimo cuarto, Enero
    assert "$BL$" in c31 and "$AD$" in c31, c31   # provisión D13 + mensualizado D13
    assert "$BM$" in d31 and "$AE$" in d31, d31   # provisión D14 + mensualizado D14
