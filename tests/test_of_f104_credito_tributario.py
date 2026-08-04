"""Regresión: bloque de SALDO CRÉDITO TRIBUTARIO del F-104 (605-608 / 615-619).

Bug detectado 2026-08-04 con el F-104 real de un cliente 2025: tanto el
catálogo oficial (``catalogo_f104.py``) como ``ALL_CASILLEROS`` del extractor
saltaban de 614 a 620, así que el sistema NUNCA extraía el bloque de saldo de
crédito tributario. De ese bloque dependen:

  · DM3 "Revisión de saldos"  → Crédito tributario = casillero 615 + 617
  · DM6 "IVA" columna T {19}  → Crédito del mes anterior = casillero 605 + 606
  · DM6 "IVA" columna Z {25}  → Saldo para el próximo mes = casillero 615 + 617

TRAMPA DEL PDF (por eso este test existe): la línea del casillero 605 MENCIONA
el 615 —"(trasládese el campo 615 de la declaración del período anterior)"—
y la del 606 menciona el 617. Un parser ingenuo le asignaría al 615 el valor
del 605. Los importes de este test son sintéticos: NUNCA se commitean cifras
de clientes a este repositorio público.

El casillero 616 NO EXISTE en el formulario: el bloque salta de 615 a 617.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.app.aud.obligaciones_fiscales.cedulas.base import find_casillero_value
from backend.app.aud.obligaciones_fiscales.cedulas.f104_extractor import (
    ALL_CASILLEROS,
    extract_f104,
)
from backend.app.ict.catalogo_f104 import F104_CASILLERO_NAMES

# Casilleros del bloque, en el orden del formulario.
CAS_MES_ANTERIOR = ["605", "606", "607", "608"]
CAS_PROXIMO_MES = ["615", "617", "618", "619"]
CAS_BLOQUE = CAS_MES_ANTERIOR + CAS_PROXIMO_MES

# Estructura EXACTA de las líneas del PDF oficial del SRI (importes sintéticos).
TEXTO_BLOQUE_CREDITO = """\
(-) Saldo crédito tributario del mes anterior
. Por adquisiciones e importaciones (trasládese el campo 615 de la declaración del período 605 111.11
anterior)
. Por retenciones en la fuente de IVA que le han sido efectuadas (trasládese el campo 617 de la declaración del período 606 222.22
anterior)
. Por compensación de IVA por ventas efectuadas con medio (trasládese el campo 618 de la declaración del período 607 333.33
electrónico anterior)
. Por compensación de IVA por ventas efectuadas en zonas afectadas (trasládese el campo 619 de la declaración del período 608 444.44
- Ley de solidaridad, restitución de crédito tributario en resoluciones anterior)
administrativas o sentencias judiciales de última instancia
(-) Retenciones en la fuente de IVA que le han sido efectuadas en este período 609 555.55
Saldo crédito tributario para el próximo mes
. Por adquisiciones e importaciones 615 666.66
. Por retenciones en la fuente de IVA que le han sido efectuadas 617 777.77
. Por compensación de IVA por ventas efectuadas con medio electrónico 618 888.88
. Por compensación de IVA por ventas efectuadas en zonas afectadas - Ley de solidaridad, restitución de crédito tributario en 619 999.99
resoluciones administrativas o sentencias judiciales de última instancia
SUBTOTAL A PAGAR Si (601-602-603-604-605-606-607-608-609-622- 620 0.00
"""


class TestCatalogoOficial:
    def test_bloque_credito_tributario_esta_en_el_catalogo(self):
        faltantes = [c for c in CAS_BLOQUE if c not in F104_CASILLERO_NAMES]
        assert not faltantes, (
            f"Casilleros del bloque de crédito tributario ausentes del "
            f"catálogo oficial: {faltantes}"
        )

    def test_casillero_616_no_existe_en_el_formulario(self):
        assert "616" not in F104_CASILLERO_NAMES, (
            "El F-104 salta de 615 a 617; el 616 no existe y no debe inventarse."
        )

    def test_cada_casillero_tiene_nombre_propio(self):
        """605 y 615 comparten glosa en el PDF; el catálogo debe distinguirlos."""
        nombres = {c: F104_CASILLERO_NAMES.get(c, "") for c in CAS_BLOQUE}
        assert len(set(nombres.values())) == len(CAS_BLOQUE), (
            f"Nombres duplicados en el bloque: {nombres}"
        )
        for cas in CAS_MES_ANTERIOR:
            assert "mes anterior" in nombres[cas].lower(), (
                f"cas {cas} debe identificarse como saldo del MES ANTERIOR: "
                f"{nombres[cas]!r}"
            )
        for cas in CAS_PROXIMO_MES:
            assert "próximo mes" in nombres[cas].lower(), (
                f"cas {cas} debe identificarse como saldo para el PRÓXIMO MES: "
                f"{nombres[cas]!r}"
            )


class TestExtractor:
    def test_all_casilleros_cubre_el_bloque(self):
        faltantes = [c for c in CAS_BLOQUE if c not in ALL_CASILLEROS]
        assert not faltantes, (
            f"ALL_CASILLEROS no extrae del PDF: {faltantes}. DM3 y DM6 "
            f"quedarían en blanco."
        )

    def test_all_casilleros_es_subconjunto_del_catalogo(self):
        faltantes = [c for c in ALL_CASILLEROS if c not in F104_CASILLERO_NAMES]
        assert not faltantes, f"Casilleros extraídos sin nombre oficial: {faltantes}"


class TestTrampaDeLaLineaReferenciada:
    """La línea del 605 menciona al 615: no deben confundirse."""

    @pytest.mark.parametrize(
        "casillero,esperado",
        [
            ("605", 111.11),
            ("606", 222.22),
            ("607", 333.33),
            ("608", 444.44),
            ("609", 555.55),
            ("615", 666.66),
            ("617", 777.77),
            ("618", 888.88),
            ("619", 999.99),
            ("620", 0.0),
        ],
    )
    def test_valor_por_casillero(self, casillero, esperado):
        assert find_casillero_value(TEXTO_BLOQUE_CREDITO, casillero) == esperado

    def test_615_no_toma_el_valor_del_605(self):
        """El fallo clásico: 'campo 615 ... 605 111.11' → 615 = 111.11."""
        assert find_casillero_value(TEXTO_BLOQUE_CREDITO, "615") != 111.11

    def test_617_no_toma_el_valor_del_606(self):
        assert find_casillero_value(TEXTO_BLOQUE_CREDITO, "617") != 222.22


@pytest.mark.skipif(
    not os.getenv("AUD_OF_FIXTURES_DIR"),
    reason="Requiere AUD_OF_FIXTURES_DIR con los F-104 reales del cliente "
           "(datos de cliente: NO se commitean a este repo público)",
)
class TestPDFRealDelCliente:
    def test_extrae_el_bloque_completo_de_un_f104_real(self):
        carpeta = Path(os.environ["AUD_OF_FIXTURES_DIR"]) / "104"
        pdfs = sorted(carpeta.glob("*.pdf"))
        assert pdfs, f"Sin PDFs F-104 en {carpeta}"

        data = extract_f104(pdfs[0].read_bytes())
        assert data is not None, f"No se pudo parsear {pdfs[0].name}"

        cas = data["casilleros"]
        vacios = [c for c in CAS_BLOQUE if cas.get(c) is None]
        assert not vacios, (
            f"El F-104 real trae el bloque pero el extractor devolvió None "
            f"para: {vacios}"
        )
