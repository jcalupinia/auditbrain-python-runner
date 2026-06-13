"""Regression test: catálogo F-101 marca como (INFORMATIVO) SOLO los cas
que el PDF SRI Ecuador 2025 efectivamente marca como tal.

REPORTE CLIENTE (2026-06-13, ICT_17): cas 618 (SUPERAVIT REVALUACION PPE)
no se traslada al A1. Verificado empíricamente: el catálogo lo marca como
"(CASILLERO INFORMATIVO)" pero el PDF F-101 SRI 2025 (página 9, fila
"Propiedades, Planta y Equipo 618 0.00") NO dice INFORMATIVO.

Causa raíz: el extractor del catálogo arrastró el sufijo "(INFORMATIVO)"
del cas anterior en algunos rangos (bug stateful prohibido en CLAUDE.md).

Tests:
1. Los 14 cas reportados como mal marcados YA NO deben tener INFORMATIVO
2. Los 36 cas correctamente marcados deben mantener INFORMATIVO
3. Validación contra PDF SRI 2025 si está disponible
"""
from __future__ import annotations

import pytest
from backend.app.ict.catalogo_f101 import F101_CASILLERO_NAMES
from backend.app.ict.fillers.source_data_sheets import _es_informativo


# Cas reportados con etiqueta (INFORMATIVO) incorrecta — el PDF SRI 2025
# NO los marca así. Cliente perdió plata real por este bug (PROPHAR
# tenía $895K en cas 618, $437K en cas 888, $37K en cas 889).
CAS_FALSAMENTE_INFORMATIVOS = [
    "618",   # SUPERAVIT POR REVALUACION DE PROPIEDADES, PLANTA Y EQUIPO
    "619",   # SUPERAVIT POR REVALUACION DE ACTIVOS INTANGIBLES
    "620",   # OTROS SUPERAVIT POR REVALUACION
    "880",   # GANANCIAS Y PERDIDAS POR REVALUACIONES PPE
    "881",   # GANANCIAS Y PERDIDAS POR REVALUACIONES ACTIVOS INTANGIBLES
    "882",   # GANANCIAS Y PERDIDAS POR REVALUACIONES OTROS
    "883",   # GANANCIAS Y PERDIDAS POR INVERSIONES EN INSTRUMENTOS PATRIMONIO
    "885",   # GANANCIAS Y PERDIDAS ACTUARIALES
    "886",   # PARTE EFECTIVA GANANCIAS Y PERDIDAS INSTRUMENTOS COBERTURA
    "887",   # OTROS (NO informativo en PDF SRI)
    "888",   # GASTO (INGRESO) POR IMPUESTO A LA RENTA CORRIENTE
    "889",   # GASTO (INGRESO) POR IMPUESTO A LA RENTA DIFERIDO
    "1160",  # INGRESOS CONSOLIDADOS SUJETOS AL IRU
    "6152",  # INGRESOS BRUTOS TOTALES SEGUN CONTABILIDAD
]


# Cas correctamente marcados como INFORMATIVO según PDF SRI 2025.
# La lista no es exhaustiva — son ejemplos representativos para
# evitar que la corrección remueva por error a cas legítimos.
CAS_CORRECTAMENTE_INFORMATIVOS = [
    "460", "461", "462", "463", "464", "465", "466", "467",
    "468", "470", "471", "472", "473", "474", "475", "476",
    "591", "592",
    "626", "627",     # Dividendos declarados/pagados (informativo)
    "6141", "6151",   # Ingresos por reembolso, dinero electrónico
    "7905", "7907",   # Costos en fideicomisos, dinero electrónico
]


class TestCatalogoInformativos:
    """Validación del catálogo F-101: solo cas que el SRI marca informativos
    deben estar marcados como informativos en el catálogo Python."""

    @pytest.mark.parametrize("cas", CAS_FALSAMENTE_INFORMATIVOS)
    def test_cas_NO_es_informativo(self, cas):
        """Los 14 cas mal marcados deben dejar de aparecer como informativos.
        Si fallan, el catálogo aún tiene "(INFORMATIVO)" / "(CASILLERO
        INFORMATIVO)" en sus nombres → corregir catalogo_f101.py.
        """
        nombre = F101_CASILLERO_NAMES.get(cas, "")
        assert nombre, f"cas {cas} debe existir en catálogo"
        upper = nombre.upper()
        assert "INFORMATIVO" not in upper, (
            f"cas {cas} marcado como INFORMATIVO en catálogo pero el PDF SRI 2025 "
            f"NO lo marca así. Nombre actual: {nombre!r}. "
            f"Causa raíz: extractor del catálogo arrastró el sufijo del cas "
            f"anterior (bug stateful)."
        )
        assert _es_informativo(nombre, cas) is False, (
            f"_es_informativo({cas}) debe ser False — cas no es informativo según SRI"
        )

    @pytest.mark.parametrize("cas", CAS_CORRECTAMENTE_INFORMATIVOS)
    def test_cas_si_es_informativo(self, cas):
        """Los cas que el PDF SRI sí marca como (informativo) deben mantener
        la marca en el catálogo."""
        nombre = F101_CASILLERO_NAMES.get(cas, "")
        assert nombre, f"cas {cas} debe existir en catálogo"
        upper = nombre.upper()
        assert "INFORMATIVO" in upper, (
            f"cas {cas} debería estar marcado INFORMATIVO según PDF SRI. "
            f"Nombre actual: {nombre!r}"
        )

    def test_total_cas_informativos_es_36(self):
        """Después del fix, debe haber exactamente 36 cas con (INFORMATIVO)
        en el catálogo (50 - 14 falsamente marcados = 36)."""
        cuenta = sum(1 for n in F101_CASILLERO_NAMES.values()
                     if "INFORMATIVO" in n.upper())
        assert cuenta == 36, (
            f"Esperaba 36 cas con INFORMATIVO, encontré {cuenta}. "
            f"Si > 36: aún hay cas mal marcados. Si < 36: se removió alguno legítimo."
        )
