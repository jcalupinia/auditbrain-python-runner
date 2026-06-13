"""Regression test: A1 NO debe contener cas de Conciliación Tributaria.

REPORTE CLIENTE (2026-06-13, ICT_17): el cliente pintó en rojo en MAPEO A1 una
cadena larga de casilleros que NO debían trasladarse al A1 porque son CÁLCULOS
derivados de la Conciliación Tributaria — no tienen contrapartida contable directa
con balance.

Lógica del cliente (verbatim):
  "llegamos a la UTILIDAD DEL EJERCICIO cas 801 (o pérdida si gastos > ingresos),
   luego cas 803 PARTICIPACIÓN TRABAJADORES, luego cas 850 IMPUESTO A LA RENTA
   CAUSADO, y por último cas 889 GASTO/INGRESO POR IMPUESTO A LA RENTA DIFERIDO.
   De ahí nace la operación para llegar a la utilidad después de participación
   trabajadores e impuesto a la renta, y con el impuesto diferido se llega a la
   utilidad integral, que debería cuadrar con cas 615 UTILIDAD DEL EJERCICIO
   (o 616 PÉRDIDA DEL EJERCICIO) del patrimonio."

Cas que SÍ pertenecen al A1 (tienen cuenta contable y cuadran):
  801, 803, 850, 889, 615, 616.

Cas que NO pertenecen al A1 (cálculos derivados sin contraparte contable):
  - Subtotales conciliación tributaria 10XX:
      1025 UTILIDAD BRUTA
      1030 TOTAL GASTOS OPERACIONALES
      1040 UTILIDAD OPERACIONAL
      1055 TOTAL GASTOS FINANCIEROS NO OPERACIONALES
      1065 UTILIDAD ANTES DE PARTICIPACIÓN
      1075 UTILIDAD ANTES DE IMPUESTO A LA RENTA
      1099 UTILIDAD DESPUÉS DE IMPUESTO A LA RENTA
  - Ajustes y cálculos 8XX:
      805-809  Rentas exentas, gastos no deducibles, atribuidos
      816, 817 Generación/reversión diferencias temporarias jubilares
      836, 843, 849  Utilidad gravable y aplicaciones ZEDE
      854      Impuesto a la renta causado mayor al anticipo reducido
      857      Retenciones en la fuente
      865, 869, 871  Saldo impuesto a pagar, anticipo próximo año
      888      Gasto/ingreso por impuesto a la renta CORRIENTE (duplica al 850)
      899      Detalle imputación multa
      902      Total impuesto a pagar
      999      Total pagado

NOTA: cas 888 también va excluido porque el cliente lo considera duplicado
conceptualmente con cas 850 (IMPUESTO A LA RENTA CAUSADO). Si se mantiene,
se "duplica" la información tributaria en el A1.
"""
from __future__ import annotations

import pytest

from backend.app.ict.fillers.a1_mapeo import A1Filler


# Cas que el cliente marcó en rojo en MAPEO A1 (ICT_17, FOSFORERA 2025) y
# explicó que NO debían trasladarse. Son cálculos derivados sin contrapartida
# contable directa con el balance.
CAS_EXCLUIDOS_CONCILIACION = [
    # Subtotales conciliación tributaria
    "1025", "1030", "1040", "1055", "1065", "1075", "1099",
    # Ajustes tributarios 8XX
    "805", "806", "807", "808", "809",
    "816", "817",
    "836", "843", "849",
    "854", "857", "865", "869", "871",
    "888",  # duplica al 850 según el cliente
    "899", "902", "999",
]

# Cas que SÍ deben quedar en A1 (la cadena contable de la utilidad integral)
CAS_QUE_QUEDAN_EN_A1 = [
    "801",   # UTILIDAD DEL EJERCICIO
    "803",   # PARTICIPACIÓN A TRABAJADORES
    "850",   # IMPUESTO A LA RENTA CAUSADO
    "889",   # GASTO (INGRESO) POR IMPUESTO A LA RENTA DIFERIDO
    "615",   # UTILIDAD DEL EJERCICIO PATRIMONIO
    "616",   # PERDIDA DEL EJERCICIO PATRIMONIO
]


class TestA1ExcluyeConciliacionTributaria:
    """Validación de que A1 NO traslada cas de Conciliación Tributaria."""

    @pytest.mark.parametrize("cas", CAS_EXCLUIDOS_CONCILIACION)
    def test_cas_excluido_de_conciliacion(self, cas):
        """Cada cas listado como 'cálculo derivado' debe quedar excluido del A1.

        El filler A1 expone `_es_cas_conciliacion_tributaria(cas)` que True
        bloquea la emisión del cas en MAPEO A1.
        """
        assert A1Filler._es_cas_conciliacion_tributaria(cas) is True, (
            f"cas {cas} debería estar excluido de A1 (cálculo derivado "
            f"de Conciliación Tributaria, sin contraparte contable). "
            f"Reportado por cliente en ICT_17 pintándolo en rojo."
        )

    @pytest.mark.parametrize("cas", CAS_QUE_QUEDAN_EN_A1)
    def test_cas_cadena_contable_NO_excluido(self, cas):
        """Los cas de la cadena contable (801, 803, 850, 889, 615, 616) NO
        deben quedar excluidos — son los únicos del bloque utilidad-integral
        con cuenta contable real."""
        assert A1Filler._es_cas_conciliacion_tributaria(cas) is False, (
            f"cas {cas} es parte de la CADENA CONTABLE de la utilidad "
            f"integral (cliente lo dejó SIN rojo). NO debe excluirse."
        )
