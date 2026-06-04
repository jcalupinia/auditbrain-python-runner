"""REGRESSION TEST — Catálogos SRI sin nombres heredados (bug detectado por
verification-before-completion en sesión 2025-12-03).

CONTEXTO DEL BUG ORIGINAL:
  El extractor de la guía F-103 tenía lógica stateful (`current_concepto`)
  que "heredaba" el nombre del concepto anterior cuando llegaba a filas
  sin nombre propio. Esto causó que 10 casilleros TOTAL/PAGO del F-103
  (cas 499, 880, 890, 897-904, 999) quedaran con nombre "SUBTOTAL
  OPERACIONES EFECTUADAS CON EL EXTERIOR" (incorrecto, heredado del cas
  498).

LO QUE ESTE TEST DETECTA:
  Cualquier secuencia de N casilleros CONSECUTIVOS (en orden numérico) que
  compartan EXACTAMENTE el mismo nombre es un smell de extractor stateful
  con bug. Los catálogos oficiales SRI nunca tienen ese patrón (cada cas
  tiene un nombre único, salvo el sufijo "— Base imponible/Valor retenido"
  del F-103).

REGLA:
  Para cada catálogo, ningún nombre se repite en más de M casilleros
  consecutivos donde M está calibrado al máximo legítimo observado
  empíricamente:
    F-101: M=2 (cas 312/313 = Locales/Del exterior pueden compartir prefijo)
    F-103: M=3 (algunos cas tienen Base+Valor+otro)
    F-104: M=3 (Valor Bruto/Neto/Impuesto del mismo concepto)
"""

import pytest

from backend.app.ict.catalogo_f101 import F101_CASILLERO_NAMES
from backend.app.ict.catalogo_f103 import F103_CASILLERO_NAMES
from backend.app.ict.catalogo_f104 import F104_CASILLERO_NAMES


def _detectar_herencia(catalogo: dict, max_consecutivos_iguales: int) -> list:
    """Recorre el catálogo en orden numérico y devuelve grupos de
    casilleros consecutivos que comparten exactamente el mismo nombre,
    EXCEDIENDO el umbral permitido.

    Returns:
        list de tuplas (nombre, [cas1, cas2, ...]) con todos los grupos
        problemáticos (len > max_consecutivos_iguales).
    """
    sorted_cas = sorted(catalogo.keys(), key=lambda x: int(x) if x.isdigit() else 99999)
    grupos: list[tuple[str, list[str]]] = []
    actual_nombre = None
    actual_grupo: list[str] = []

    for cas in sorted_cas:
        nombre = catalogo[cas]
        if nombre == actual_nombre:
            actual_grupo.append(cas)
        else:
            if len(actual_grupo) > max_consecutivos_iguales:
                grupos.append((actual_nombre, actual_grupo[:]))
            actual_nombre = nombre
            actual_grupo = [cas]
    # último grupo
    if len(actual_grupo) > max_consecutivos_iguales:
        grupos.append((actual_nombre, actual_grupo[:]))

    return grupos


def test_f101_no_hereda_nombres_consecutivos():
    """F-101: ningún nombre debe repetirse en más de 2 casilleros consecutivos.
    Si pasa: el extractor heredó mal el nombre del concepto previo."""
    grupos = _detectar_herencia(F101_CASILLERO_NAMES, max_consecutivos_iguales=2)
    assert not grupos, (
        f"❌ F-101 tiene {len(grupos)} grupos de cas con nombre HEREDADO MAL:\n" +
        "\n".join(f"  • '{nombre[:50]}...' en cas {cas}" for nombre, cas in grupos[:5])
    )


def test_f103_no_hereda_nombres_consecutivos():
    """F-103: ningún nombre debe repetirse en más de 3 casilleros consecutivos.
    Cada concepto tiene Base imponible (302) + Valor retenido (352) — son
    NO consecutivos en el orden numérico, así que repetición consecutiva
    indica bug."""
    grupos = _detectar_herencia(F103_CASILLERO_NAMES, max_consecutivos_iguales=3)
    assert not grupos, (
        f"❌ F-103 tiene {len(grupos)} grupos de cas con nombre HEREDADO MAL:\n" +
        "\n".join(f"  • '{nombre[:50]}...' en cas {cas}" for nombre, cas in grupos[:5]) +
        "\n\nEste fue el bug original: cas 499/880/890/897-904/999 todos tenían "
        "'SUBTOTAL OPERACIONES EFECTUADAS CON EL EXTERIOR' por herencia."
    )


def test_f104_no_hereda_nombres_consecutivos():
    """F-104: cada concepto puede tener hasta 3 casilleros con nombre similar
    (Valor Bruto + Valor Neto + Impuesto Generado). Ningún nombre EXACTO
    debe repetirse en más de 3 casilleros consecutivos (el sufijo los
    diferencia)."""
    grupos = _detectar_herencia(F104_CASILLERO_NAMES, max_consecutivos_iguales=3)
    assert not grupos, (
        f"❌ F-104 tiene {len(grupos)} grupos de cas con nombre HEREDADO MAL:\n" +
        "\n".join(f"  • '{nombre[:50]}...' en cas {cas}" for nombre, cas in grupos[:5])
    )


def test_f103_cas_totales_tienen_nombre_correcto():
    """Casos específicos del bug original: cas TOTAL/PAGO del F-103 deben
    tener su nombre correcto, NO el heredado de SUBTOTAL EXTERIOR."""
    correcciones_esperadas = {
        "499": "TOTAL DE RETENCIÓN",      # debe contener
        "902": "TOTAL IMPUESTO A PAGAR",
        "999": "TOTAL PAGADO",
        "890": "Pago previo",
        "897": "Interés",
        "898": "Impuesto",
        "899": "Multa",
    }
    for cas, fragmento_esperado in correcciones_esperadas.items():
        nombre = F103_CASILLERO_NAMES.get(cas, "")
        assert fragmento_esperado.lower() in nombre.lower(), (
            f"Cas F-103 {cas} debe contener '{fragmento_esperado}', "
            f"obtuvo: '{nombre[:60]}'"
        )
        assert "SUBTOTAL OPERACIONES EFECTUADAS CON EL EXTERIOR" not in nombre, (
            f"Cas F-103 {cas} aún tiene el nombre HEREDADO MAL del bug "
            f"original: '{nombre[:80]}'"
        )


def test_f101_y_f104_totales_finales_tienen_nombre_correcto():
    """Mismo check para F-101 y F-104: TOTALES no deben heredar nombre."""
    # F-101 totales críticos
    f101_checks = {
        "499": "TOTAL",       # TOTAL DEL ACTIVO
        "699": "TOTAL",       # TOTAL PASIVO Y PATRIMONIO
        "6999": "INGRESOS",   # TOTAL INGRESOS
        "7999": "TOTAL",      # TOTAL COSTOS Y GASTOS
    }
    for cas, fragmento in f101_checks.items():
        nombre = F101_CASILLERO_NAMES.get(cas, "")
        assert fragmento.upper() in nombre.upper(), \
            f"Cas F-101 {cas} debe contener '{fragmento}', obtuvo: '{nombre[:60]}'"

    # F-104 totales críticos
    f104_checks = {
        "499": "IMPUESTO A LIQUIDAR",
        "529": "ADQUISICIONES",
        "999": "PAGADO",
    }
    for cas, fragmento in f104_checks.items():
        nombre = F104_CASILLERO_NAMES.get(cas, "")
        assert fragmento.upper() in nombre.upper(), \
            f"Cas F-104 {cas} debe contener '{fragmento}', obtuvo: '{nombre[:60]}'"
