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


def test_poblacion_sintetica_4274_persistencia_conciliacion(tmp_path):
    """Volumen y totales equivalentes al control, sin publicar datos del cliente."""
    from sqlalchemy import select, func
    from backend.app.ingesta.ingesta_masiva import filas, datasets
    import csv

    importes = (
        [Decimal("15904263.34")] + [Decimal("1")] * 861
        + [Decimal("-15397283.21")] + [Decimal("-1")] * 3000
        + [Decimal("0")] * 411
    )
    assert len(importes) == 4274
    archivo = tmp_path / "mayor_4274.csv"
    with archivo.open("w", newline="", encoding="utf-8") as fh:
        escritor = csv.writer(fh)
        escritor.writerow(["Nºcuenta", "Fecha L/M", "Importe"])
        for i, importe in enumerate(importes):
            escritor.writerow(["101", "2025-01-01", str(importe)])
    engine = create_engine("sqlite:///" + str(tmp_path / "test4274.sqlite"))
    crear_tablas(engine)
    resultado = ingerir_archivo(
        engine, archivo, cliente_id="prueba", encargo_id="aislado",
        periodo="2025", tipo_documento="mayor", lote=317,
        mapeo_confirmado={"cuenta": 0, "fecha": 1, "importe": 2},
        positivo_es="debe",
    )
    assert resultado["estado"] == "completado"
    assert resultado["total_filas"] == 4274
    assert resultado["filas_revision"] == 0
    with engine.connect() as conn:
        total_persistido = conn.execute(
            select(func.count()).select_from(filas).where(
                filas.c.dataset_id == resultado["dataset_id"]
            )
        ).scalar_one()
    assert total_persistido == 4274
    debe = haber = original = Decimal("0")
    desde = 0
    while True:
        pagina = consultar_filas(engine, resultado["dataset_id"],
            cliente_id="prueba", encargo_id="aislado", limite=317,
            desde_fila=desde)
        if not pagina:
            break
        for fila in pagina:
            assert not fila["errores"]
            datos = fila["datos"]
            debe += Decimal(datos["debe"])
            haber += Decimal(datos["haber"])
            original += Decimal(datos["importe_original"])
        desde = pagina[-1]["numero_fila"]
    assert debe == Decimal("15905124.34")
    assert haber == Decimal("15400283.21")
    assert original == Decimal("504841.13")
    assert debe - haber == original
