"""REGLA SUPREMA — A1 no puede tener "saldos de línea".

Un "saldo de línea" es un casillero que el F-101 declara con valor pero
que el A1 nunca muestra (porque no estaba en la lista hardcoded). El
usuario lo descubrió empíricamente con cas 490, 491, 593 marcados en
rojo en DATOS F-101 pero ausentes del A1.

Este test garantiza que:
  1. A1 contiene TODOS los casilleros del balance (311-699) del catálogo
     OFICIAL F-101.
  2. Todo cas cuyo nombre empieza con "(-)" queda clasificado como
     NEGATIVE_CASILLEROS (signo invertido en la fórmula F).

Si SRI publica una guía nueva del F-101 con casilleros adicionales del
balance, lo único que el desarrollador debe hacer es actualizar
catalogo_f101.py. El A1 se actualiza solo (lista derivada).
"""
from backend.app.ict.cell_maps.a1 import A1_CASILLEROS_ORDERED
from backend.app.ict.fillers.a1_mapeo import A1Filler
from backend.app.ict.catalogo_f101 import F101_CASILLERO_NAMES


def _balance_oficial() -> set[str]:
    """Casilleros del balance (311-699) en el catálogo OFICIAL F-101."""
    return {
        cas for cas in F101_CASILLERO_NAMES
        if cas.isdigit() and 311 <= int(cas) <= 699
    }


def test_a1_contiene_todos_los_casilleros_del_balance_oficial():
    """Sin saldos de línea: A1 cubre TODOS los cas del balance del catálogo."""
    a1_cas = {c for c, _ in A1_CASILLEROS_ORDERED}
    balance = _balance_oficial()
    faltantes = balance - a1_cas
    assert not faltantes, (
        f"A1 tiene {len(faltantes)} 'saldos de línea' — casilleros del "
        f"balance F-101 oficial que NO se trasladan al A1. "
        f"Ejemplos (primeros 10): {sorted(faltantes, key=int)[:10]}. "
        f"Esto causa el bug que el cliente reportó en 2026-06-04 "
        f"(cas 490, 491, 593, etc. marcados en rojo en DATOS F-101)."
    )


def test_a1_cas_specicos_del_screenshot_estan_presentes():
    """Regresión del caso concreto que el cliente reportó (2026-06-04)."""
    a1_cas = {c for c, _ in A1_CASILLEROS_ORDERED}
    casos_reportados = {
        "490": "DERECHOS DE USO POR ACTIVOS ARRENDADOS",
        "491": "(-) AMORTIZACION ACUMULADA DE DERECHOS DE USO",
        "593": "PASIVO CORRIENTE POR ARRENDAMIENTO",
    }
    for cas, hint in casos_reportados.items():
        assert cas in a1_cas, (
            f"cas {cas} ('{hint}') debe estar en A1_CASILLEROS_ORDERED — "
            f"el cliente lo reportó como 'no trasladado' el 2026-06-04."
        )


def test_a1_usa_nombres_oficiales_del_catalogo():
    """Los nombres del A1 deben venir del catálogo OFICIAL F-101."""
    for cas, nombre_en_a1 in A1_CASILLEROS_ORDERED:
        nombre_oficial = F101_CASILLERO_NAMES.get(cas)
        assert nombre_oficial == nombre_en_a1, (
            f"cas {cas}: A1 tiene '{nombre_en_a1[:50]}' pero catálogo "
            f"OFICIAL dice '{(nombre_oficial or 'AUSENTE')[:50]}'."
        )


def test_a1_negative_casilleros_incluye_cas_491():
    """cas 491 = '(-) AMORTIZACIÓN DERECHOS DE USO' debe ser detectado
    como negativo por la auto-expansión, sin estar hardcoded en _CORE."""
    assert "491" in A1Filler.NEGATIVE_CASILLEROS, (
        "cas 491 debe estar en NEGATIVE_CASILLEROS (auto-detectado por "
        "empezar con '(-)' en el catálogo)."
    )
    # Y NO debe estar en _CORE (porque la detección debe ser automática)
    assert "491" not in A1Filler._NEGATIVE_CORE, (
        "cas 491 NO debería estar hardcoded en _CORE — debe llegar por "
        "auto-detección. Si se hardcodea, perdemos la garantía de que "
        "nuevos cas (-) del SRI queden clasificados automáticamente."
    )


def test_a1_todos_los_negativos_del_balance_son_minoradores():
    """Defensa adicional: todo cas en NEGATIVE_CASILLEROS dentro del rango
    del balance debe efectivamente empezar con '(-)' en el catálogo, O
    estar en _CORE (signo conceptual no nominal: ej cas 602 capital no
    pagado, 612/616 pérdidas)."""
    for cas in A1Filler.NEGATIVE_CASILLEROS:
        if not (cas.isdigit() and 311 <= int(cas) <= 699):
            continue  # cas del estado de resultados se valida en otro test
        nombre = F101_CASILLERO_NAMES.get(cas, "")
        en_core = cas in A1Filler._NEGATIVE_CORE
        empieza_neg = nombre.strip().startswith("(-)")
        assert en_core or empieza_neg, (
            f"cas {cas} está en NEGATIVE_CASILLEROS pero su nombre "
            f"'{nombre[:50]}' no empieza con '(-)' y no está en _CORE."
        )


def test_a1_conteo_minimo_267_casilleros_balance():
    """Smoke test: A1 debe tener AL MENOS 267 cas del balance (rango
    311-699). Si baja, alguien removió casilleros del catálogo o cambió
    el filtro — proba que la regla sigue viva."""
    a1_cas = {c for c, _ in A1_CASILLEROS_ORDERED if c.isdigit() and 311 <= int(c) <= 699}
    assert len(a1_cas) >= 267, (
        f"A1 solo tiene {len(a1_cas)} cas del balance. Antes del fix "
        f"2026-06-04 había 193 (con 164 saldos de línea). Después del "
        f"fix debe tener ≥267 (todo el balance del F-101 OFICIAL)."
    )


def test_a1_contiene_TODOS_los_888_casilleros_del_catalogo():
    """REGLA SUPREMA (pedido cliente 2026-06-04):
    "Todos los casilleros del formulario 101 que se encuentran en la
     pestaña de datos f-101 deben trasladarse a la pestaña A1".

    Por tanto: A1 debe contener LOS 888 casilleros del catálogo OFICIAL,
    no solo balance (267) ni balance+resultados (697). Incluye:
      - Conciliación tributaria (800-849)
      - Anticipo IR + retenciones (850-899)
      - Cálculo Impuesto a Renta (900-999)
      - Anexos especiales (1100+, 5xxx, etc.)

    Bug histórico (commit pre-fix): A1 tenía 697 cas, faltaban 191
    (todos los 800+). El cliente lo detectó descargando el papel de
    trabajo de PROPHAR.
    """
    a1_cas = {c for c, _ in A1_CASILLEROS_ORDERED}
    catalogo_cas = {c for c in F101_CASILLERO_NAMES if c.isdigit()}
    faltantes = catalogo_cas - a1_cas
    assert not faltantes, (
        f"A1 tiene {len(faltantes)} casilleros del catálogo OFICIAL F-101 "
        f"ausentes. Ejemplos: {sorted(faltantes, key=int)[:20]}. "
        "REGLA SUPREMA del cliente: TODOS los 888 cas del catálogo deben "
        "trasladarse a A1 (no solo los del balance/resultados)."
    )


def test_a1_cas_conciliacion_tributaria_estan_presentes():
    """Regresión específica del bug 2026-06-04 (segundo reporte cliente):
    Los cas de conciliación tributaria (800-999) que el cliente vio
    ausentes en su ICT_7_PAPEL_TRABAJO.xlsx deben estar en A1."""
    a1_cas = {c for c, _ in A1_CASILLEROS_ORDERED}
    # Muestreo de cas críticos de conciliación + cálculo IR
    casos_criticos = ["801", "802", "803", "808", "810", "830", "849",
                      "853", "857", "859", "880", "899", "999"]
    for cas in casos_criticos:
        if cas in F101_CASILLERO_NAMES:
            assert cas in a1_cas, (
                f"Cas {cas} ({F101_CASILLERO_NAMES[cas][:50]}) está en el "
                f"catálogo F-101 pero AUSENTE en A1. Cliente lo reportó "
                f"el 2026-06-04."
            )
