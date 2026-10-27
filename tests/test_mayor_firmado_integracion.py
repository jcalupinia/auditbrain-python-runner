"""Pruebas de integracion del mayor firmado en SQLite aislado."""
from decimal import Decimal
from sqlalchemy import create_engine
from backend.app.ingesta.ingesta_masiva import crear_tablas, ingerir_archivo, consultar_filas

def test_mayor_firmado_persiste_y_concilia(tmp_path):
    archivo = tmp_path / "mayor.csv"
    archivo.write_text("Cuenta,Fecha,Importe\n101,2025-01-01,125.50\n102,2025-01-02,-30\n103,2025-01-03,0\n", encoding="utf-8")
    engine = create_engine("sqlite:///" + str(tmp_path / "aislada.db"))
    crear_tablas(engine)
    resultado = ingerir_archivo(engine, archivo, cliente_id="cliente-prueba",
        encargo_id="auditoria", periodo="2025", tipo_documento="mayor",
        mapeo_confirmado={"cuenta":0,"fecha":1,"importe":2}, positivo_es="debe")
    assert resultado["estado"] == "completado"
    assert resultado["total_filas"] == 3
    assert resultado["filas_revision"] == 0
    registros = consultar_filas(engine, resultado["dataset_id"],
        cliente_id="cliente-prueba", encargo_id="auditoria")
    assert sum(Decimal(r["datos"]["debe"]) for r in registros) == Decimal("125.50")
    assert sum(Decimal(r["datos"]["haber"]) for r in registros) == Decimal("30")
    assert sum(Decimal(r["datos"]["importe_original"]) for r in registros) == Decimal("95.50")

def test_rechaza_polaridad_sin_confirmar(tmp_path):
    import pytest
    archivo = tmp_path / "mayor.csv"
    archivo.write_text("Cuenta,Fecha,Importe\n101,2025-01-01,100\n", encoding="utf-8")
    engine = create_engine("sqlite:///" + str(tmp_path / "aislada.db"))
    crear_tablas(engine)
    with pytest.raises(ValueError, match="positivo_es"):
        ingerir_archivo(engine, archivo, cliente_id="c", encargo_id="e", periodo="2025",
            tipo_documento="mayor", mapeo_confirmado={"cuenta":0,"fecha":1,"importe":2})
