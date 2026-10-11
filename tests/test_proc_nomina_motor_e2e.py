"""Motor de nómina 2.0 de punta a punta con un juego de datos FICTICIO.

Corre ``nomina_beneficios.correr_prueba`` sobre los insumos ficticios de «Comercial Andina de
Ejemplo S.A.» (``tests/fixtures/nomina_ficticia``) y verifica que:
  - produce las 15 cédulas declaradas en ``CEDULAS``;
  - cada .xlsx abre con openpyxl (no se corrompe → Excel no levanta «reparaciones»);
  - ninguna celda guardada como TEXTO quedaría interpretada por Excel como fórmula rota
    (texto que empieza con ``=`` y no es una fórmula; los rótulos con +/-/@ son texto normal).

No usa LibreOffice ni red ni datos de cliente reales: los insumos se generan en un temporal.
La paridad al centavo del motor se validó aparte contra el cliente de referencia (ya retirado);
aquí se prueba que el flujo completo corre y entrega cédulas sanas con datos genéricos.
"""
import io

import openpyxl
import pytest

from tests.fixtures import nomina_ficticia as ff
from backend.app.aud.niif.procesadores import nomina_beneficios as nb


@pytest.fixture(scope="module")
def cedulas(tmp_path_factory):
    home = tmp_path_factory.mktemp("nomina_home")
    ins = tmp_path_factory.mktemp("nomina_in")
    out = home / "out"
    archivos = ff.generar(str(ins))
    assert nb.datos_minimos(archivos)
    return nb.correr_prueba(archivos, ff.FICHA, str(home), str(out))


def test_entrega_las_15_cedulas(cedulas):
    assert set(cedulas) == set(nb.CEDULAS)
    assert len(cedulas) == 15


def test_cada_cedula_abre_sin_reparaciones(cedulas):
    problemas = []
    for nombre, data in cedulas.items():
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data))
        except Exception as e:  # noqa: BLE001
            problemas.append(f"{nombre}: no abre ({e})")
            continue
        for ws in wb.worksheets:
            for fila in ws.iter_rows():
                for c in fila:
                    # Texto que empieza con «=» y NO es una fórmula → Excel lo repararía.
                    if isinstance(c.value, str) and c.value.startswith("=") and c.data_type != "f":
                        problemas.append(f"{nombre}!{ws.title}!{c.coordinate}: texto '=' no-fórmula")
    assert not problemas, problemas
