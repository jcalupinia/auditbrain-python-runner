"""Verificación empírica del motor contra el mayor real de un cliente.

Los archivos NO se commitean (repo público): se leen de la carpeta apuntada
por AUD_OF_FIXTURES_DIR y el test hace skip si no está.

Verdad de referencia: el archivo BASE DE IMPUESTOS.xlsx que el auditor arma
a mano, cuyas hojas por categoría tienen exactamente estos conteos.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.app.aud.obligaciones_fiscales.mayor.clasificador import clasificar
from backend.app.aud.obligaciones_fiscales.mayor.cuentas import perfilar
from backend.app.aud.obligaciones_fiscales.mayor.reader import leer_mayor

MOVIMIENTOS_POR_CATEGORIA = {
    "IVA_COMPRAS": 550,
    "IVA_RETENIDO": 58,
    "IVA_VENTAS": 155,
    "RET_RENTA": 1254,
    "RET_IVA": 236,
    "VENTAS": 2427,
}
TOTAL_MOVIMIENTOS = 4680
TOTAL_CUENTAS = 28

pytestmark = pytest.mark.skipif(
    not os.getenv("AUD_OF_FIXTURES_DIR"),
    reason="Requiere AUD_OF_FIXTURES_DIR con el mayor real del cliente",
)


@pytest.fixture(scope="module")
def lectura():
    ruta = Path(os.environ["AUD_OF_FIXTURES_DIR"]) / "MAYOR DE IMPUESTOS.xlsx"
    if not ruta.exists():
        pytest.skip(f"No está {ruta}")
    return leer_mayor(ruta.read_bytes())


@pytest.fixture(scope="module")
def resultados(lectura):
    return {r.codigo: r for r in clasificar(perfilar(lectura.movimientos))}


def test_lee_todos_los_movimientos_del_mayor(lectura):
    assert lectura.mapeo_suficiente, lectura.columnas_faltantes
    assert len(lectura.movimientos) == TOTAL_MOVIMIENTOS


def test_identifica_las_veintiocho_cuentas(lectura):
    assert len(perfilar(lectura.movimientos)) == TOTAL_CUENTAS


def test_ninguna_cuenta_queda_sin_categoria(resultados):
    sin_categoria = [r.codigo for r in resultados.values() if r.categoria is None]
    assert not sin_categoria, f"Cuentas sin clasificar: {sin_categoria}"


def test_los_conteos_por_categoria_coinciden_con_el_trabajo_manual(lectura, resultados):
    conteo: dict[str, int] = {}
    for m in lectura.movimientos:
        categoria = resultados[m.codigo].categoria
        conteo[categoria] = conteo.get(categoria, 0) + 1

    assert conteo == MOVIMIENTOS_POR_CATEGORIA


def test_las_tarifas_de_retencion_se_extraen_del_nombre(resultados):
    """El desglose por porcentaje depende de esto."""
    assert resultados["2.1.7.2.8"].tarifa == 2.75
    assert resultados["2.1.7.2.9"].tarifa == 1.75
    assert resultados["2.1.7.3.3"].tarifa == 100.0


def test_la_propagacion_por_rama_resuelve_la_cuenta_sin_tarifa(resultados):
    """'Retencion imptos relacion dependencia' no dice el porcentaje:
    la resuelven sus hermanas 2.1.7.2.*."""
    r = resultados["2.1.7.2.11"]
    assert r.categoria == "RET_RENTA"
    assert r.confianza == "alta"


def test_casi_todas_las_cuentas_se_resuelven_sin_intervencion(resultados, capsys):
    """Documenta cuánto trabajo le queda al auditor en el primer uso."""
    por_confianza: dict[str, list[str]] = {}
    for r in resultados.values():
        por_confianza.setdefault(r.confianza, []).append(f"{r.codigo} {r.nombre}")
    with capsys.disabled():
        for nivel in ("alta", "media", "baja"):
            cuentas = por_confianza.get(nivel, [])
            print(f"\n  confianza {nivel}: {len(cuentas)} cuenta(s)")
            for c in cuentas:
                print(f"    - {c}")
    assert len(por_confianza.get("alta", [])) >= 20
