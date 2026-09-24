"""Pruebas del export tabular para Power BI del ICT (P2-F, REP-011)."""
import io
import zipfile

from backend.app.ict.export_bi import (
    TABLAS,
    build_bi_dataset,
    export_bi_csv_zip,
)

CTX = {
    "session_data": {"razon_social": "PROPHAR S.A.", "ruc": "1791859596001",
                     "ejercicio_fiscal": "2025"},
    "excepciones": {
        "columnas": [{"clave": "monto", "titulo": "Monto", "tipo": "monto"}],
        "filas": [
            {"hash": "a1", "anexo": "A5", "severidad": "P0", "monto": "12500.00",
             "nia": "NIA 240", "mensaje": "x", "casillero": "7999", "estado": "abierta"},
            {"hash": "b2", "anexo": "A2", "severidad": "P2", "monto": "800.50",
             "nia": "NIA 500", "mensaje": "y", "casillero": "6001", "estado": "abierta"},
        ],
        "resumen": {"total_excepciones": 2, "monto_total": "13300.50"},
        "run_id": "run_1"},
    "parametros": {"materialidad": "50000.00", "confianza": 95},
    "sello": {"version_app": "1.0", "version_motor": "motor-1.4.0",
              "run_id": "run_1", "hash_salida": "abcd"},
}


def test_dataset_tiene_las_cinco_tablas():
    ds = build_bi_dataset(CTX)
    assert {t.nombre for t in ds.tablas} == set(TABLAS)
    assert [t.nombre for t in ds.tablas] == list(TABLAS)  # orden estable


def test_hechos_una_fila_por_excepcion():
    ds = build_bi_dataset(CTX)
    hechos = ds.por_nombre("hechos_excepciones")
    assert hechos is not None
    assert len(hechos.filas) == 2
    # monto normalizado con punto decimal, sin separador de miles
    montos = [f[hechos.columnas.index("monto")] for f in hechos.filas]
    assert "12500.00" in montos and "800.50" in montos


def test_dim_encargo_toma_session_y_sello():
    ds = build_bi_dataset(CTX)
    enc = ds.por_nombre("dim_encargo")
    assert enc.filas[0][enc.columnas.index("ruc")] == "1791859596001"
    assert enc.filas[0][enc.columnas.index("hash_salida")] == "abcd"


def test_zip_trae_cinco_csv_con_bom_y_puntoycoma():
    data = export_bi_csv_zip(CTX)
    z = zipfile.ZipFile(io.BytesIO(data))
    nombres = set(z.namelist())
    assert nombres == {f"{t}.csv" for t in TABLAS}
    hechos = z.read("hechos_excepciones.csv")
    assert hechos.startswith(b"\xef\xbb\xbf")   # BOM UTF-8
    assert b";" in hechos
    assert b"12500.00" in hechos                 # punto decimal


def test_dataset_vacio_no_rompe():
    ds = build_bi_dataset({})
    assert {t.nombre for t in ds.tablas} == set(TABLAS)
    assert ds.por_nombre("hechos_excepciones").filas == []
    # los catálogos fijos siguen presentes
    assert len(ds.por_nombre("dim_severidad").filas) == 3
