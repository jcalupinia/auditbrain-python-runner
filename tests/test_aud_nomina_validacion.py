"""Validación de formato de los documentos de la prueba de nómina.

Verifica que el validador diga con claridad qué documento y qué cabecera corregir, que
NUNCA reviente, y que un rol/mayor mal formado se reporte como bloqueante (en vez de dejar
que el motor reviente luego con un error críptico o se quede «procesando»).

Sin datos de cliente: encabezados genéricos y filas ficticias.
"""
from openpyxl import Workbook

from backend.app.aud.niif.procesadores.nomina import validacion as V


def _xlsx(tmp_path, nombre, headers, filas, hoja="Hoja1"):
    p = tmp_path / nombre
    wb = Workbook()
    ws = wb.active
    ws.title = hoja
    ws.append(headers)
    for f in filas:
        ws.append(f)
    wb.save(p)
    return str(p)


def test_validar_rol_unificado_ok_con_advertencia_de_beneficios(tmp_path):
    # Rol tipo «unificado»: trae empleado y sueldo (procesable) pero no los beneficios con
    # nombres reconocibles → OK con advertencia (no bloquea), no revienta.
    p = _xlsx(tmp_path, "rol.xlsx", ["MES", "Cédula", "Nombres", "Sueldo", "CARGO"],
              [["ENERO", "1700000000", "FULANO DE TAL", "500", "Operario"]], hoja="Roles_Unificados")
    r = V.validar_rol(p, "rol.xlsx")
    assert r["ok"] is True
    assert not r["problemas"]
    assert any("saldrán en cero" in w for w in r["advertencias"])


def test_validar_rol_sin_empleado_ni_sueldo_bloquea_con_mensaje_claro(tmp_path):
    p = _xlsx(tmp_path, "rol.xlsx", ["Col1", "Col2", "Col3"], [["a", "b", "c"]])
    r = V.validar_rol(p, "rol.xlsx")
    assert r["ok"] is False
    assert any("empleado" in pr.lower() and "sueldo" in pr.lower() for pr in r["problemas"])


def test_validar_mayor_sin_columnas_esenciales_bloquea(tmp_path):
    p = _xlsx(tmp_path, "mayor.xlsx", ["ColA", "ColB", "ColC"], [["x", "y", "z"]])
    r = V.validar_mayor(p, "mayor.xlsx")
    assert r["ok"] is False
    assert r["problemas"]


def test_validar_prueba_consolida_y_bloquea(tmp_path):
    # Falta RQ-003 y el rol está mal → bloqueante, con resumen accionable.
    arch = [
        {"requerimiento": "RQ-002", "ruta": _xlsx(tmp_path, "anexo.xlsx", ["Cod", "Desc", "S1", "", "", "S2"],
                                                  [["5BS.21203.001", "APORTE", 10, "", "", 12]]), "nombre": "anexo.xlsx"},
        {"requerimiento": "RQ-004", "ruta": _xlsx(tmp_path, "mayor.xlsx", ["Fecha", "Nºcuenta", "Descripción", "Importe"],
                                                  [["2026-01-31", "2.01.05", "IESS", 100]]), "nombre": "mayor.xlsx"},
        {"requerimiento": "RQ-006", "ruta": _xlsx(tmp_path, "rol.xlsx", ["Col1", "Col2"], [["a", "b"]]), "nombre": "rol.xlsx"},
    ]
    d = V.validar_prueba(arch)
    assert d["bloqueante"] is True
    assert any("RQ-003" in f for f in d["faltan_requerimientos"])
    assert "Rol de pagos" in d["resumen"]


def test_validacion_nunca_revienta_con_archivo_basura(tmp_path):
    p = tmp_path / "basura.xlsx"
    p.write_bytes(b"esto no es un xlsx")
    for rq in ("RQ-002", "RQ-003", "RQ-004", "RQ-006"):
        r = V.validar_documento(rq, str(p), "basura.xlsx")
        assert r["ok"] is False
        assert r["problemas"]
